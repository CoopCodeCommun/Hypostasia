# Trois defauts graves — revue de cloture du 11 aout — rapport

## Defaut 1 — la notification part, mais son destinataire ne voit rien

Confirme dans le code (`front/views_taches.py` filtrait tout en `owner=user` /
`page__owner=user`, alors que `_destinataires_de_notification` previent aussi
les proprietaires des carnets contenant la note).

**Notion d'acces retenue : `_est_proprietaire_page`** (`front/views.py:365`),
PAS `_utilisateur_a_acces_page`. Raison : `_destinataires_de_notification`
previent « le propriétaire de la note PLUS les propriétaires des carnets qui
la contiennent » — c'est exactement la definition de `_est_proprietaire_page`
(owner de la note OU owner d'un carnet contenant). `_utilisateur_a_acces_page`
est plus large : elle inclut aussi les lecteurs d'un carnet partage ou
public, qui ne sont PAS des destinataires de la notification. Utiliser cette
notion aurait montre le badge a des gens jamais notifies — un defaut
symetrique au defaut signale.

**Changements** :
- Nouvelle fonction `_filtre_proprietaire_page(prefixe, utilisateur)`
  (`front/views.py`, juste apres `_est_proprietaire_page`) : produit un `Q`
  reproduisant la meme regle en filtre de requete (pas un appel par objet),
  pour eviter le N+1 sur les listes de 30 taches. Sa docstring renvoie
  explicitement a `_est_proprietaire_page` comme source de verite unique.
- `front/views_taches.py` : `_calculer_etat_bouton`, `dropdown()` et
  `marquer_toutes_lues()` utilisent `_filtre_proprietaire_page(...).distinct()`
  (le join sur `appartenances_dossiers` duplique une ligne par carnet).
- `marquer_lue()` (TachesViewSet) : recupere l'objet par pk SEUL puis
  verifie l'acces avec `_est_proprietaire_page` (appel unique, pas de N+1
  puisque c'est une action `detail=True` sur un seul objet) ; refus ->
  `Http404`, jamais 403.
- `front/views.py` (`LectureViewSet.retrieve`, second chemin de marquage
  via `?marquer_lue=&type=`) : meme elargissement, via
  `_filtre_proprietaire_page`.

**Tests** (`front/tests/test_taches_ingestion.py`, classe
`NotificationDestinataireCarnetTest`) : un `prof` proprietaire d'un carnet
voit dans son bouton et son dropdown une ingestion ET une extraction sur une
note de `auteur` rangee dans son carnet ; il peut la marquer lue par les deux
chemins ; un `tiers` sans lien ne voit rien et recoit 404 (jamais 403,
verifie explicitement) au marquage. Un test `test_pas_de_n_plus_1_sur_le_dropdown`
verifie via `assertNumQueries(14)` que le nombre de requetes reste fixe
(14, jamais un multiple des taches rendues) apres l'ajout de 5 notes/jobs
supplementaires dans le meme carnet.

## Defaut 2 — un badge dont l'utilisateur ne peut plus sortir

Confirme : `_calculer_etat_bouton` comptait les ingestions `en_attente`/
`en_cours` sans aucune borne de temps, alors que `relancer_ingestion`
(`front/views.py`) traite un etat actif comme fantome au-dela de
`DELAI_INGESTION_FANTOME_MIN` (15 min).

**Changement** : `DELAI_INGESTION_FANTOME_MIN` est devenue une constante de
MODULE dans `front/views.py` (elle etait locale a `relancer_ingestion`) ;
`relancer_ingestion` et `front/views_taches.py._calculer_etat_bouton`
importent et utilisent la MEME constante. Le comptage exclut les pages dont
`ingestion_maj_le` est perime :
`exclude(ingestion_maj_le__lt=seuil_fantome)` — les `NULL` sont conserves
(NULL < seuil est indetermine en SQL, jamais vrai), reproduisant exactement
la regle « pas de date => pas fantome » de `relancer_ingestion`.

**Tests** (`IngestionFantomeTest`) : une ingestion `en_cours` avec
`ingestion_maj_le` > 15 min ne compte plus (echouait avant le fix, avec une
`ImportError` puisque la constante n'existait qu'en local avant ce
changement) ; une ingestion recente compte toujours ; une ingestion sans
date compte toujours (garde-fou pour ne pas faire disparaitre silencieusement
un etat qui n'a jamais ete horodate).

Non traite (hors perimetre du defaut signale, a noter pour memoire) : le
fait qu'une seule des trois formes d'ingestion (fichier Docling) puisse
etre relancee par `relancer_ingestion` — capture web et audio restent sans
chemin de relance manuel. Le brief demandait de reutiliser la constante de
detection fantome, pas d'ajouter un chemin de relance pour ces deux formes ;
je ne l'ai pas fait, pour ne pas depasser le perimetre demande.

## Defaut 3 — un horodatage manquant qui empoisonne le tri

Confirme : `core/views.py` (`PageViewSet.create`) ecrivait
`ingestion_etat="en_attente"` (chaine brute) sans poser `ingestion_maj_le`,
contrairement aux deux autres endroits (`front/views.py:2103` et `5657`).

**Changement** : le `.update()` pose maintenant `ingestion_etat=
EtatIngestion.EN_ATTENTE` (constante, plus de chaine brute) ET
`ingestion_maj_le=timezone.now()`, exactement le patron des deux autres
endroits. Imports ajoutes : `EtatIngestion` (depuis `.models`) et
`django.utils.timezone`.

**Test** (`front/tests/test_capture_web_docling.py`,
`test_une_capture_lance_l_ingestion_et_pose_l_etat`, assertion ajoutee) :
apres une capture web, `page.ingestion_maj_le` n'est plus `None`.

## Verification (TDD)

Pour chacun des trois defauts, les tests ont d'abord ete lances et ont
echoue (voir transcript de session) avant toute correction :
- defaut 3 : `AssertionError: unexpectedly None` sur `ingestion_maj_le`.
- defaut 2 : `ImportError` sur `DELAI_INGESTION_FANTOME_MIN` (constante
  encore locale), puis apres l'avoir rendue importable, le compteur restait
  a 1 sans la borne de temps.
- defaut 1 : 6 echecs (bouton, dropdown, marquage par les deux chemins,
  extraction) — le proprietaire du carnet ne voyait rien.

Suites lancees apres correction (toutes vertes) :
`front.tests.test_taches_ingestion` (20), `front.tests.test_capture_web_docling`
(7), `front.tests.test_ingestion_ui`, `hypostasis_extractor.tests.
test_notifications_ingestion`, `hypostasis_extractor.tests.test_ingestion_docling`
(76 au total), `core.tests` (212), plus les suites de permissions/routage/
corpus/elements potentiellement affectees par l'elargissement d'acces (125 +
78). `manage.py check` : aucun probleme.
