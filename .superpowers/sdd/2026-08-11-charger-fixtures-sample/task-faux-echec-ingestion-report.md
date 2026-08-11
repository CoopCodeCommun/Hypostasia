# Faux echec ECHOUEE sur ingestion deja faite — rapport

Date : 2026-08-11

## Defaut

`hypostasis_extractor/tasks_element.py` traitait « page deja ingeree » de deux
facons opposees : la garde d'entree (avant tout travail) posait `REUSSIE`,
mais quand ce meme constat remontait *depuis le service appele* — via un
retour `{"erreur": "page deja ingeree"}` (audio) ou une `ValueError` levee par
`creer_les_elements_d_une_page` (Docling, fichier et capture web) — la tache
le traitait comme un echec et posait `ECHOUEE`.

Ce n'est pas theorique : c'est une course entre deux executions Celery sur la
meme page. La perdante franchit la garde d'entree avant que la gagnante
n'ait fini d'ecrire, puis trouve la place prise quand elle essaie a son tour.
En base, ca laissait une page avec ses elements crees **et** un etat
`echouee` — une contradiction visible a l'ecran, comptee comme erreur non lue
par le badge de taches.

## Etendue reelle : les trois taches, pas seulement l'audio

Verification faite en lisant `hypostasis_extractor/services/ingestion_audio.py`
et `hypostasis_extractor/services/ingestion_docling.py` :

- **Audio** (`ingerer_une_transcription_diarisee_en_elements`) : le service
  `ingerer_une_transcription_diarisee` retourne explicitement
  `{"erreur": "page deja ingeree"}` quand `page.elements.exists()` est vrai a
  son entree — exactement le cas signale.
- **Fichier Docling** (`ingerer_un_fichier_avec_docling`) : le meme constat
  arrive sous une autre forme. `creer_les_elements_d_une_page` leve une
  `ValueError("La page N a deja des elements...")` si la place est prise a
  l'ecriture ; cette exception remontait jusqu'au `except Exception` generique
  de la tache, qui posait `ECHOUEE` avec un message de conversion ratee —
  fausse cause.
- **Capture web** (`ingerer_une_capture_web_avec_docling`) : meme
  `ValueError` depuis `creer_les_elements_d_une_page`, mais elle tombait dans
  le `except ValueError` deja present pour le cas « pas de HTML a decouper » —
  un DEUXIEME defaut latent, decouvert pendant l'audit : une course sur cette
  tache aurait affiche « cette page capturee n'a pas de contenu » alors que le
  contenu existait bel et bien.

Les trois taches avaient donc le meme defaut d'origine, sous trois habillages
differents.

## Correction

Ajout d'un filet partage, `_traiter_comme_deja_ingeree(page)`, qui pose
`REUSSIE` (`ingestion_etat`), previent l'utilisateur avec `status="completed"`
et rend `{"erreur": "page deja ingeree"}` — la meme reponse que la garde
d'entree dans ce cas.

Chaque tache l'appelle avant de traiter une exception comme un vrai echec :

- Audio : `if resultat.get("erreur") == "page deja ingeree":` avant le test
  generique `if "erreur" in resultat:` (qui reste ECHOUEE pour « aucun tour de
  parole »).
- Fichier Docling : `if page.elements.exists():` dans le `except Exception`.
- Capture web : le meme test, ajoute a la fois dans le `except ValueError`
  (pour ne plus confondre avec « pas de HTML ») et dans le `except Exception`
  generique qui suit.

Le choix de verifier `page.elements.exists()` plutot que de parser le texte
de l'exception est deliberement le plus robuste : il regarde l'etat reel de
la base, pas la formulation d'un message d'erreur qui pourrait changer.

Aucune modification de la course elle-meme (pas de verrou, pas de
`select_for_update`) : hors perimetre, demande explicitement.

## Reparation des donnees

Une seule page en contradiction trouvee : page 8,
`audio-FR-2locuteur-palaiscesar-14s.mp3`, 9 elements, `ingestion_etat=echouee`.
Reparee par `manage.py shell -c` (pas de migration) :
`ingestion_etat=REUSSIE`, `ingestion_detail=''`, `ingestion_maj_le=now()`.

Verification post-correction : requete sur toutes les pages `ECHOUEE` +
test `elements.exists()` sur chacune -> 0 page contradictoire restante.

## Tests

Trois tests ecrits dans
`hypostasis_extractor/tests/test_tasks_element.py`, classe
`IngestionDejaFaiteParUneExecutionConcurrenteTest` :

- `test_le_service_audio_page_deja_ingeree_reste_reussie` — mock du service
  audio pour rendre `{"erreur": "page deja ingeree"}`, assertion sur
  `ingestion_etat == REUSSIE`.
- `test_le_fichier_docling_deja_ingere_par_ailleurs_reste_reussi` — mock du
  service Docling avec un `side_effect` qui cree un element (simulant l'autre
  execution) puis leve la `ValueError` reelle.
- `test_la_capture_web_deja_ingeree_par_ailleurs_reste_reussie` — meme
  patron pour la capture web.

Les trois ont ete lances **avant** la correction et ont echoue avec les
messages attendus (`'echouee' != REUSSIE`, `{'erreur': 'capture sans html'}`,
etc.), confirmant le defaut sur les trois taches. Puis la correction a ete
appliquee et les trois passent.

## Resultat de la suite ciblee

```
docker exec hypostasia_web sh -c 'uv run python manage.py test \
    hypostasis_extractor.tests.test_tasks_element \
    hypostasis_extractor.tests.test_notifications_ingestion -v 1'
```

`Ran 27 tests ... OK` — aucune regression sur les tests existants
(notamment `test_une_ingestion_en_echec_previent_aussi`, qui verifie qu'une
vraie erreur de conversion sur une page sans element reste `ECHOUEE`).

`manage.py check` : aucun probleme.

## Reserves

- La course elle-meme n'est pas supprimee (hors perimetre demande) : elle
  peut toujours se produire, mais son issue est desormais honnete dans les
  trois taches.
- Le defaut latent trouve sur la capture web (confusion possible entre
  « pas de HTML » et « course ») n'avait pas ete signale par l'utilisateur ;
  il est corrige par la meme occasion puisqu'il partage la cause racine et le
  meme filet de correction.
- Seule la page 8 etait en contradiction au moment de l'audit ; si d'autres
  courses se sont produites et resolues autrement (par exemple une page dont
  `ingestion_etat` a ete ecrasee depuis par un cycle ulterieur reussi), elles
  ne laissent plus de trace observable et n'ont pas pu etre auditees.
