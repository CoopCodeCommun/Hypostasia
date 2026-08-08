# Changelog — Hypostasia V3

> Journal des modifications par phase. Format bilingue FR/EN.
> Reverse chronological order.

---

## 2026-08-08 — Couche corpus, phase C : permissions par les carnets

**Quoi / What :** les trois fonctions de permission de la couche corpus
(SPEC-corpus § 5.2) : `_utilisateur_a_acces_page`,
`_utilisateur_peut_ecrire_page`, `_est_proprietaire_page`, plus le helper
`_dossiers_contenant_la_page` (contrat prefetch, § 5.3).

**Pourquoi / Why :** sous le N-N, « le dossier de la page » n'existe plus.
L'acces se derive des carnets (le plus permissif gagne), la propriete
s'ELARGIT (owner de la note OU owner d'un carnet la contenant) — le prof
garde la moderation sur les captures des eleves, l'eleve garde ses droits.
Le comportement legacy (note sans carnet sans owner → tout authentifie)
est preserve.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | + les 3 fonctions + helper ; `_est_proprietaire_dossier` marquee DEPRECIEE (bascule des appelants en phase D, en un seul lot) |
| `core/tests/test_corpus_permissions.py` | 17 tests : carnet le plus permissif, anonyme sur carnet public, legacy, cas-piege (owner sans acces : les carnets decident), partage direct et par groupe, superuser (lecture oui / ecriture non), moderation du prof, droits de l'auteur, lecture != ecriture, zero requete avec prefetch (chemins sans DossierPartage) |

### Relecture / Review
Relecture adverse passee (8 aout) : 1 bloquant corrige — le bypass
superuser en ECRITURE, absent de la spec et de l'existant, a ete retire
(seule la lecture a un bypass, prescrit). 4 points « a trancher avant la
phase D » consignes dans la fiche A TESTER (ecriture des orphelines,
proprietaire sans lecture, dossiers legacy owner=None — 0 en dev —,
assertNumQueries de la vue de liste).

### Migration
- **Migration necessaire / Migration required :** Non. Aucun appelant
  converti : les vues existantes lisent toujours `page.dossier` (phase D).

---

## 2026-08-08 — Couche corpus, phase B : validation des categories

**Quoi / What :** la validation « qui n'a pas le droit de manquer »
(SPEC-corpus § 3.4) : une categorie appliquee a une appartenance doit venir
du carnet (ou de la base) de cette appartenance.

**Pourquoi / Why :** sans elle, le vocabulaire d'un carnet fuit dans un
autre — exactement ce que la categorie portee par la relation existe pour
empecher. Deux etages : le serializer (erreur de formulaire propre) et les
signaux m2m_changed (filet de securite, meme un .add() en shell est refuse).

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `core/services/corpus.py` | Les deux validateurs (cote carnet, cote base) |
| `core/signals.py` | Les deux signaux m2m_changed, avec le kwarg `reverse` gere dans les deux sens (le cas que la v1.0 de la spec cassait) |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/apps.py` | `ready()` importe les signaux |
| `core/serializers.py` | + `CategoriserUneNoteSerializer` |
| `core/tests/test_corpus_modele.py` | + 14 tests de validation (sens direct, inverse — nominal ET refus —, .set(), cote base, serializer : etrangere, introuvable, liste vide) |

### Relecture / Review
Relecture adverse passee (8 aout) : pas de bloquant. Correctifs appliques —
tests nominaux de la branche reverse (le seul trou par lequel une regression
sur LE point v1.0 serait passee), garde de contexte du serializer,
`dispatch_uid` sur les signaux, docstring honnete sur la limite du through
(les ecritures directes sur la table de liaison ne declenchent aucun signal),
borne `max_length=100` sur la liste.

### Piege documente / Documented pitfall
Une ValidationError levee par le signal sort du bloc atomique interne du
`.add()` : dans un test (ou une vue sous transaction), les requetes
suivantes exigent un savepoint (`with transaction.atomic():` autour de
l'appel refuse). Les tests montrent le patron.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-08 — Couche corpus, phase A : modeles, migrations, role_special

**Quoi / What :** le socle de donnees de la couche corpus
(SPEC-corpus-base-carnet-note.md v1.1 § 3, § 4.2, § 6.3) : les modeles
`BaseDeConnaissances`, `AppartenancePageDossier`, `AppartenanceDossierBase`,
`ListeDeCategories`, `CategorieDossier`, `CategorieBase`, le champ
`Dossier.role_special`, et les migrations de schema + donnees.

**Pourquoi / Why :** une note doit pouvoir vivre dans plusieurs carnets sans
duplication, avec un classement propre a chaque carnet — la categorie est un
attribut de la RELATION note-carnet, pas de la note. Et les carnets
« magiques » (« A ranger », « Mes imports ») etaient retrouves par leur nom :
les renommer cassait la capture et l'import.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | + 6 modeles corpus, + `RoleSpecialDossier`, + `Dossier.role_special` avec contrainte `unicite_role_special_par_proprietaire` |
| `core/migrations/0040_...py` | Schema : les 6 modeles + role_special + contraintes |
| `core/migrations/0041_creer_les_appartenances_depuis_la_fk.py` | Donnees, REVERSIBLE : une appartenance par page ayant un dossier, `integree_le=page.created_at`, bilan chiffre + controle d'integrite qui leve si les comptes different |
| `core/migrations/0042_estampiller_les_dossiers_speciaux.py` | Donnees, REVERSIBLE : pose `role_special` sur les carnets historiques (plus ancien seulement en cas d'homonymes, jamais sans owner) |
| `core/views.py` | `_resoudre_dossier` : fallback retrouve par `role_special`, plus par nom |
| `front/views.py` | `_obtenir_ou_creer_dossier_imports` : idem |
| `core/migrations/0043_...py` | Contrainte role_special reprise avec `nulls_distinct=False` (les fourre-tout sans owner sont limites aussi — retour de relecture) |
| `core/tests/` | `tests.py` (vide) converti en paquet : `test_corpus_modele.py` (18 tests), `test_corpus_migration.py` (4 tests MigrationExecutor), `test_role_special.py` (8 tests) |

### Decisions / Decisions
- `Page.dossier` reste en place, intouchee : la FK porte le « premier carnet »
  pendant la coexistence. Son retrait est la migration 3 de la spec, apres
  recette. / The FK stays during coexistence.
- La question ouverte n°1 de la spec (pages sans dossier -> « A ranger » ?)
  est tranchee de facon conservatrice : on ne les touche pas. Le comportement
  d'acces legacy (tout authentifie si owner=None) sera preserve par la
  phase C (§ 5.2). Sur la base de dev : 1 seule page concernee.
- L'extension continue de filtrer par nom (`popup.js`), sans casser : les noms
  par defaut ne changent pas (spec § 6.3). Reserve : un carnet special
  renomme AVANT la migration n'est pas estampille — un doublon apparaitra
  a la capture suivante (aucun cas sur la base de dev, verifie).
- Relecture adverse passee (8 aout) : 3 correctifs appliques — idempotence
  de 0042 sur base partiellement estampillee, controle d'integrite de 0041
  compte les lignes creees (pas la table), `nulls_distinct=False` sur la
  contrainte role_special. Chaque correctif a son test.

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0040`, `0041`,
  `0042`, `0043`. Appliquees sur la base de dev : 537 pages avec dossier ->
  537 appartenances (COHERENT), 14 « Mes imports » estampilles.

---

## 2026-08-05 — Ingestion Docling, simplifications, bascule des pages existantes

**Quoi / What :** Docling installe et branche, deux simplifications du modele, et
une commande de bascule des pages du moteur ANCIEN vers le moteur ELEMENT.

### Ingestion Docling / Docling ingestion
`services/ingestion_docling.py` convertit un fichier en ElementDocument. Verifie
sur un markdown avec titres, liste et tableau : 9 elements, labels corrects
(`title`, `section_header`, `text`, `list_item`, `table`), chemins de section
hierarchiques.

Deux points traites que Docling ne fait pas seul :
- **Les tableaux sont serialises en markdown.** Un tableau Docling n'a pas
  d'attribut texte : son contenu est dans sa structure. Sans serialisation, il
  arriverait vide et tout son contenu serait perdu pour l'analyse.
- **Chaque boite PDF garde SON numero de page.** `page_no` est unique au niveau
  de la provenance, alors que les boites sont une liste : un paragraphe a cheval
  sur deux pages aurait vu ses boites de la page 2 dessinees sur la page 1.

Chaine complete verifiee avec un appel LLM reel : Docling -> 9 elements ->
1 chunk -> 4 extractions -> 14 portions, dont 2 couvrant plusieurs elements.

### Deux simplifications / Two simplifications
| Quoi / What | Pourquoi / Why |
|---|---|
| `ElementDocument.element_parent` supprime | Scission et fusion suppriment toujours leurs sources, et le `SET_NULL` vidait donc la reference a chaque fois. Un champ qui ne peut jamais rien indiquer invite a s'y fier a tort. La filiation vit dans `ElementOperation.donnees` |
| `EtatAncrage` passe de trois etats a deux | `EXACTE` et `RETROUVEE` se comportaient exactement pareil : ni le regime d'edition, ni l'affichage, ni le calcul d'etat ne les distinguaient. Fusionnes en `ANCREE` |

### Bascule des pages existantes / Migrating existing pages
`manage.py basculer_vers_le_moteur_element` decoupe `text_readability` en
elements et tente de re-ancrer les extractions en cherchant leur texte, avec la
regle habituelle : plusieurs occurrences, on ne devine pas.

Resultat sur le dev (538 pages, 29 921 extractions) : **13 174 elements crees,
8 585 ancres recuperees (28,7 %)**. Aucune extraction ni commentaire supprime :
celles qu'on ne retrouve pas restent en base, detachees.

### On traduit les anciens offsets, on ne cherche pas le texte
Les anciennes extractions portent `start_char` et `end_char` : des positions
dans `text_readability`, ecrites par l'alignement de LangExtract au moment de
l'analyse. **Ces positions sont fiables** — verifie sur echantillon : aucune
hors bornes, 5 % seulement a 0-0 (jamais alignees).

Comme les elements sont decoupes dans CE MEME texte, il suffit de noter ou
commence chaque paragraphe pour traduire un ancien offset en portions. C'est un
calcul d'intersection, exactement celui que `services/ancrage.py` fait deja pour
le nouveau moteur.

Trois versions successives de la commande, et ce que chacune a appris :

| Methode | Re-ancrage | Extractions commentees |
|---|---|---|
| Chercher `extraction_text`, element par element | 39,7 % | 51/115 |
| + insensible a la casse et a la typographie, sur le texte colle | 48,6 % | 66/115 |
| **Traduire `start_char`/`end_char`** | **99,7 %** | **113/115** |

Chercher le texte etait a la fois inutile et moins bon :
- ca rejetait des ancres correctes au motif que le texte apparaissait ailleurs
  dans la page (« ambigu »), alors que l'offset, lui, savait laquelle etait la
  bonne ;
- ca echouait sur les alignements partiels de LangExtract, ou `extraction_text`
  est plus long que ce qui a reellement ete trouve dans le document ;
- ca echouait sur les differences d'ecriture entre le texte rendu et le
  document (un `\n` devenu espace, une apostrophe courbe).

**Note** : une analyse intermediaire avait conclu que 73 % des extractions
etaient des reformulations et non des citations. C'etait faux, et c'etait un
artefact de la methode de mesure — une recherche de texte trop litterale, pas
un fait sur les donnees. `extraction_text` porte bien la citation.

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0039` et
  `hypostasis_extractor.0033` (suppression du champ, fusion des etats, avec
  conversion des donnees existantes).
- La commande de bascule, elle, se lance a la demande, et accepte `--a-blanc`
  pour voir ce qui se passerait sans rien ecrire.

---

## 2026-08-05 — Ancrage par element, phase D : pipeline d'analyse + garde d'edition

**Quoi / What :** `services/analyse_par_element.py` (chunks -> LangExtract ->
ancres) et `services/garde_edition.py` (interdire l'edition pendant une analyse).

**Pourquoi / Why :** c'est la piece qui relie tout le reste. Le chunking (phase C)
decoupe sur les frontieres d'elements, le LLM analyse chaque chunk seul,
l'intersection (phase B) traduit les positions rendues en portions d'ancrage.
Verifie contre Gemini 2.5 Flash : sur une liste a puces de trois elements, le
modele rend un span qui les traverse tous les trois, et le pipeline produit trois
portions ordonnees pointant chacune le bon texte.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/analyse_par_element.py` | Pipeline d'analyse du moteur ELEMENT |
| `hypostasis_extractor/services/garde_edition.py` | Refus d'editer pendant une analyse |
| `hypostasis_extractor/tests/test_analyse_par_element.py` | 19 tests, LLM simule |
| `hypostasis_extractor/tests/test_analyse_llm_reel.py` | 3 tests d'integration, appels LLM reels |
| `hypostasis_extractor/tests/test_garde_edition.py` | 24 tests |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | `"updated_at"` ajoute aux `update_fields` des jobs (battement de coeur pour la garde d'edition) |
| `front/views.py` | `_refuser_si_une_analyse_tourne()` + garde sur `renommer_locuteur`, `editer_bloc`, `supprimer_bloc` |
| `services/reconciliation.py`, `moteur_structure.py`, `masquage.py`, `reingestion.py` | Appel de la garde en tete de chaque operation d'edition |

### Deux decisions du proprietaire / Two owner decisions
1. **Les gros elements partent entiers**, sans decoupage. `max_char_buffer` est
   calcule plus grand que le chunk pour que LangExtract le recoive tel quel.
   A noter : ca ne protege pas les positions (LangExtract les re-base de toute
   facon), ca garantit que le modele lit chaque element ENTIER, dans son
   contexte.
2. **L'edition est bloquee pendant une analyse.** Un delai de grace de 90 minutes
   empeche qu'un worker Celery interrompu condamne une page pour toujours — cas
   documente dans le CHANGELOG du 19 juin 2026.

### Defauts corriges apres relecture adverse / Fixed after adversarial review
| Defaut / Defect | Correction |
|---|---|
| `lx.extract` telecharge le texte s'il ressemble a une URL (`fetch_urls=True` par defaut) : un element qui est un lien nu aurait fait analyser la page distante, avec des ancres fausses et une requete sortante pilotee par le document ingere | `fetch_urls=False` |
| Une analyse dont TOUS les chunks echouent finissait `COMPLETED`, indiscernable d'une page sans rien a extraire | Passage en `ERROR`, et bilan persiste dans `raw_result` |
| Une extraction incoherente (span a l'envers) faisait tomber toute l'analyse | Attrapee par extraction, comptee dans `extractions_refusees` |
| Relancer un job dupliquait toutes ses extractions | Purge des entites du job avant analyse |
| Un JSON tronque par `max_output_tokens` perdait le chunk entier | `resolver_params={"suppress_parse_errors": True}` |
| `updated_at` n'etait jamais rafraichi : le delai de grace mesurait l'age depuis la creation, pas la vie du job | Battement de coeur dans `front/tasks.py`, et la garde regarde les deux dates |
| La garde ne protegeait que la couche elements, qu'aucun code n'appelle encore, alors que les vraies editions passent par `front/views.py` | Garde ajoutee sur les trois vues d'edition |

### Tests avec appels LLM reels / Real LLM tests
Ils coutent de l'argent et dependent de ce que le modele repond. Double verrou :
le tag `llm_reel` **et** la variable `TESTS_LLM_REELS`. Django n'excluant pas les
tags par defaut, le tag seul ne protegerait pas.

```bash
docker exec -e TESTS_LLM_REELS=1 hypostasia_dev_web \
    uv run python manage.py test hypostasis_extractor --tag=llm_reel
```

### Migration
- **Migration necessaire / Migration required :** Non.

### Ce qui reste avant utilisation / Remaining before use
Le pipeline n'est appele par aucune tache Celery ni vue. Il manque : la tache
Celery (avec `_check_ia_active`, notifications, progression), le bouton dans
l'interface, et le compteur de tokens que la spec section 4.2 declare necessaire.

---

## 2026-08-05 — Ancrage par element, phase G : masquage et re-ingestion

**Quoi / What :** `services/masquage.py` (masquer, demasquer) et
`services/reingestion.py` (reconcilier les elements par empreinte).

**Pourquoi / Why :** deux besoins distincts.
- **Masquer** : la transcription audio invente du contenu — un bruit de fond
  transcrit en mots, une phrase repetee. Ce n'est ni une coquille a corriger
  (il n'y a rien a corriger VERS) ni une note d'incertitude. L'element sort du
  contenu utile sans etre supprime, et l'operation est reversible.
- **Re-ingerer** : un pad de 200 comptes-rendus grossit d'un compte-rendu par
  semaine. Il faut re-analyser sans repayer 200 appels au LLM ni perdre les
  debats attaches aux 199 autres. Les elements sont reconnus par empreinte de
  contenu, jamais par position.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/masquage.py` | Masquer, demasquer, detacher les portions |
| `hypostasis_extractor/services/reingestion.py` | Reconciliation des elements par empreinte |
| `hypostasis_extractor/tests/test_masquage_et_reingestion.py` | 26 tests |

### Ecarts avec la spec, et pourquoi / Deviations from the spec
| Ou / Where | Ecart / Deviation | Raison / Reason |
|---|---|---|
| 5.4 | Le demasquage ne reutilise pas la reconciliation | Celle-ci repositionne apres un CHANGEMENT de texte et rend la main quand le texte est inchange — exactement le cas du demasquage. Elle exclut de plus les portions detachees, a raison |
| 5.4 | Le journal note un hash du texte BRUT, pas l'empreinte normalisee | L'empreinte ecrase les espaces et la casse. Corriger une double espace pendant un masquage decale tous les offsets qui suivent sans changer l'empreinte d'un iota : les portions seraient rattachees a des positions fausses |
| 5.4 | Le journal note les identifiants des portions detachees | Un element peut porter des portions detachees AVANT le masquage, par une correction anterieure. Les rattacher au demasquage les ferait pointer n'importe quoi. Seules celles que ce masquage a detachees reviennent |
| 5.3 | Les elements deja masques sont apparies, pas exclus | En les excluant, un element masque dont le texte reste dans la source serait recree en doublon a chaque re-ingestion, masque a son tour, exclu, recree... Un pad re-ingere cinquante fois accumulerait cinquante copies du meme bruit |
| 5.3 | Les empreintes en double sont signalees des DEUX cotes | Ne regarder que l'ancien document laisse passer le cas le plus probable : un intitule repete qui apparait une seconde fois dans le NOUVEAU contenu |
| 5.3 | Le masquage par re-ingestion passe par `masquer_un_element` | Un masquage ecrit a la main ne serait ni journalise ni recuperable : l'element ne pourrait jamais retrouver ses ancres, meme a texte strictement identique |
| 5.3 | Numerotation en deux temps (plage temporaire puis renumerotation) | Un element masque restant a l'ordre 0 entre en collision definitive avec un nouvel element cree a l'ordre 0. Ce conflit-la n'est pas transitoire, donc la contrainte differee le refuse a juste titre |
| 5.2 | La fusion refuse un element masque avec un visible | Le resultat ne pourrait etre ni l'un ni l'autre : visible, il renverrait au LLM le bruit qu'un humain avait retire ; masque, il ferait disparaitre du contenu utile |

### Migration
- **Migration necessaire / Migration required :** Non — aucun changement de schema.

---

## 2026-08-05 — Ancrage par element, phase F : moteur scission / fusion

**Quoi / What :** `services/moteur_structure.py` — couper un element en deux,
recoller deux elements adjacents, en redistribuant les portions d'ancrage.
Plus deux changements de schema que ces operations rendent necessaires.

**Pourquoi / Why :** une transcription audio colle deux tours de parole en un
seul element, ou attribue le mauvais locuteur au milieu d'un segment. Sans
scission ni fusion, la seule facon de corriger serait de tout re-analyser et de
perdre le debat attache. « Recoller un tour de parole scinde » est l'operation
numero un sur une vraie diarisation.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/moteur_structure.py` | Scission, fusion, coalescence, renumerotation |
| `hypostasis_extractor/tests/test_moteur_structure.py` | 41 tests |

### Changement de schema 1 : contraintes d'unicite DEFERRABLE
Les contraintes `unicite_ordre_dans_la_page` et `unicite_ordre_dans_l_extraction`
sont desormais verifiees au COMMIT, plus a chaque ligne ecrite.

**Raison :** le pseudo-code de la spec section 5.1 est incodable autrement. Il
cree le premier morceau avec l'`ordre` de l'element d'origine, qui existe encore
a cet instant — `IntegrityError` immediate, verifiee empiriquement. Meme
probleme pour le decalage des `ordre_dans_extraction` : decaler des numeros
de +1 fait forcement se telescoper deux lignes en chemin.

**Consequences a connaitre :**
- Une violation d'unicite sur ces deux tables ne se manifeste plus au `save()`
  mais au commit, donc hors de tout `try/except` place autour de l'ecriture.
- `bulk_create(ignore_conflicts=True)` et tout `ON CONFLICT` sont desormais
  refuses par PostgreSQL sur ces deux tables : une contrainte deferrable ne peut
  pas servir d'arbitre a un upsert.

### Changement de schema 2 : le journal des operations tient a la Page
`ElementOperation.element` passe de `CASCADE` a `SET_NULL`, et le modele gagne
`page` (FK obligatoire), `identifiant_stable_element` et `donnees`.

**Raison :** scission et fusion suppriment toujours leurs elements sources. Avec
une CASCADE sur l'element, chaque operation effacait l'historique de la
precedente — scinder puis refusionner ne laissait aucune trace de la scission.
Le journal etait decoratif, et l'invariant « rien ne disparait en silence » faux
la ou il compte le plus.

### Defauts de la spec corriges au passage / Spec defects fixed
| Section | Defaut / Defect |
|---|---|
| 5.1 | Le pseudo-code viole la contrainte d'unicite des la premiere ligne ; son `transaction.atomic()` arrive apres les `create` |
| 5.2 | La fusion promeut toutes les portions en `RETROUVEE`, y compris celles qui etaient `DETACHEE` — une portion detachee ressuscitait sur des offsets jamais valides |
| 5.2 | La coalescence recollait deux portions distantes de la longueur du separateur, ou qu'elles soient. Deux portions separees par deux caracteres de vrai texte etaient recollees en avalant ce texte. On ne recolle plus qu'a la couture |
| 5.2 | `_fusionner_les_provenances` : les boites PDF du second element heritaient du `page_no` du premier, donc auraient ete dessinees sur la mauvaise page. Chaque boite porte desormais sa page |

### Migration
- **Migration necessaire / Migration required :** Oui
- `core.0037` (contrainte deferrable), `hypostasis_extractor.0032` (idem),
  `core.0038` (journal rattache a la page, ecrite a la main car la table est
  vide et le champ `page` non-nullable).
- **Sans effet sur les donnees existantes** : les trois tables concernees ne
  sont alimentees par aucun pipeline a ce stade.

---

## 2026-08-05 — Ancrage par element, phases B, C et E : intersection, chunking, reconciliation

**Quoi / What :** les trois algorithmes du moteur ELEMENT qui ne dependent
d'aucune decision d'interface.
- **Phase B** — `services/ancrage.py` : transforme un span rendu par LangExtract
  (des offsets dans le texte d'un chunk) en portions d'ancrage, une par element
  traverse.
- **Phase C** — `services/chunking.py` : regroupe les elements en chunks sans
  jamais couper un element en deux.
- **Phase E** — `services/reconciliation.py` : repositionne les portions apres
  une correction de texte, et serialise les corrections concurrentes.

**Pourquoi / Why :** ce sont les trois endroits ou une ancre peut devenir fausse.
Un chunk qui coupe un element fait lire une demi-phrase au LLM ; un span mal
traduit ancre au mauvais endroit ; une correction de texte fait glisser toutes
les positions. Chacun des trois refuse de deviner : quand la position n'est pas
certaine, la portion est marquee `DETACHEE` plutot que placee au hasard.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/ancrage.py` | Decoupage d'un span en portions + table des offsets |
| `hypostasis_extractor/services/chunking.py` | Construction des chunks alignes sur les elements |
| `hypostasis_extractor/services/reconciliation.py` | Repositionnement des portions + verrou de concurrence |
| `hypostasis_extractor/tests/test_chunking_par_element.py` | 23 tests |
| `hypostasis_extractor/tests/test_reconciliation.py` | 23 tests |

### Fichiers deplaces / Moved files
| Avant / Before | Apres / After | Raison / Reason |
|---|---|---|
| `hypostasis_extractor/services.py` | `hypostasis_extractor/services/__init__.py` | La spec impose un paquet `services/`. Les imports existants restent valides ; les imports relatifs internes sont passes de `from .models` a `from ..models` |
| `hypostasis_extractor/tests.py` | `hypostasis_extractor/tests/test_modeles_extraction.py` | Un module et un paquet de meme nom empechaient `manage.py test` de decouvrir les tests |

### Ecarts avec la spec, et pourquoi / Deviations from the spec
| Ou / Where | Ecart / Deviation | Raison / Reason |
|---|---|---|
| section 2.3 | Parametre `decalages_dans_l_element` ajoute | La table d'offsets de la spec dit ou un morceau d'element est DANS LE CHUNK, jamais ou il est DANS L'ELEMENT. Sans cette information, une portion d'un element trop gros serait ancree a 0 |
| section 2.3 | Un element absent de la table leve une erreur au lieu d'etre saute | Un saut silencieux produit une ancre incomplete que rien en aval ne detecte : la portion du milieu disparait et la numerotation se resserre |
| section 4.1 | Taille calculee par somme des longueurs, pas par `position_debut/fin_dans_page` | Ces attributs n'existent pas sur `ElementDocument`. La somme mesure en plus exactement ce que le budget veut borner : le texte reellement envoye au LLM |
| section 4.1 | Cle `offsets` ajoutee a chaque chunk | La section 2.3 dit reutiliser « la meme table que celle utilisee pour construire le chunk » — table que le chunker de la spec ne produisait pas |
| section 4.1 | Un element plus gros que le budget part entier | La regle 1 est declaree obligatoire. Consequence : un chunk ne contient jamais une sous-chaine d'element, contrairement a ce que la section 2.3 envisage |
| section 6 | `reconcilier_les_portions_de_l_element` ecrit aussi le texte | La spec appelle `texte_de_la_portion_avant_edition()`, methode inexistante, tout en ayant retire `ancien_texte`. Les deux sont inconciliables |
| section 6 | Les portions des extractions masquees sont repositionnees | Les ignorer laisserait des offsets perimes qui ressortiraient faux au demasquage |
| section 6 | Les portions deja `DETACHEE` sont exclues | Leurs offsets ne veulent plus rien dire : les reutiliser pouvait faire repasser une portion `EXACTE` sur un passage sans rapport |

### Migration
- **Migration necessaire / Migration required :** Non — aucun changement de schema.

---

## 2026-08-05 — Ancrage par element, phase A : modeles et signal d'etat

**Quoi / What :** ajout du socle de donnees du moteur ELEMENT — `ElementDocument`,
`AncrageExtraction` (ancre multi-elements), `ElementOperation`, le champ
`SourceLink.ancrage_source`, et le signal `recalculer_etat_de_l_element`.
Implemente la phase A de `SPEC-ancrage-par-element-v2.md` (section 11).

**Pourquoi / Why :** l'ancrage actuel se fait par offsets de caracteres dans un
texte plat. Des qu'un texte est corrige, les positions glissent et le lien avec
le passage source est perdu. Le nouveau moteur ancre dans un element de document
identifie par un UUID stable, via une table de liaison ordonnee qui permet a une
extraction de couvrir plusieurs elements — mesure : une extraction d'une phrase
enjambe deja deux elements dans 7,5 % des cas, une extraction de deux phrases
dans 76 % des cas.

**Etat / Status :** socle de donnees uniquement. Aucun pipeline ne cree encore
d'element : le moteur d'intersection (phase B), le chunking (phase C) et
l'ingestion (phase D) restent a ecrire. Le nouveau moteur n'est donc lu par
aucun code existant.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | + `empreinte_du_texte()`, `EtatElement`, `ElementDocument`, `TypeOperationElement`, `ElementOperation` ; + champ `SourceLink.ancrage_source` ; imports `hashlib`, `re`, `uuid` |
| `hypostasis_extractor/models.py` | + `EtatAncrage`, `AncrageExtraction` (table de liaison M2M ordonnee) |
| `hypostasis_extractor/signals.py` | + `recalculer_etat_de_l_element()` et ses trois recepteurs (ancrage, commentaire, masquage d'extraction) |
| `hypostasis_extractor/tests/` | Nouveau package + `test_ancrage_m2m.py` (37 tests) |
| `core/migrations/0035_elementdocument_elementoperation.py` | Creation des modeles |
| `core/migrations/0036_sourcelink_ancrage_source_and_more.py` | FK croisees + contrainte d'unicite |
| `hypostasis_extractor/migrations/0031_ancrageextraction.py` | Creation de la table de liaison |

### Coexistence des deux moteurs / Both engines coexist
Conformement a la section 9 de la spec, **aucun ancien champ n'est retire ni
modifie**. `ExtractedEntity.start_char` / `end_char` et
`SourceLink.start_char_source` / `end_char_source` restent en place et
fonctionnent comme avant. Les trois migrations sont purement additives
(`CreateModel`, `AddField`, `AddConstraint`) — aucun `RemoveField`, aucun
`AlterField`, aucun `RunPython`. Trois tests de non-regression verifient
explicitement que les anciens champs existent toujours.

### Regle de calcul de l'etat / State computation rule
Une portion d'ancrage ne compte dans l'etat d'un element que si son extraction
n'est **pas masquee** et que son ancrage n'est **pas detache**. Consequence
voulue : un element dont toutes les portions sont detachees redevient `LIBRE`,
donc librement editable. Il n'y a pas d'etat `SCELLE` — le scellement a ete
abandonne (YAGNI).

### Migration
- **Migration necessaire / Migration required :** Oui
- `core.0035`, `hypostasis_extractor.0031`, `core.0036` — dans cet ordre, gere
  automatiquement par les dependances.
- Commande : `docker exec hypostasia_web uv run python manage.py migrate`
- **Sans effet sur les donnees existantes** : uniquement des tables nouvelles et
  une colonne nullable sur `SourceLink`.

---

## 2026-06-19 — Fix : taches en erreur bloquees en « En cours » (statut "error" vs "failed")

**Quoi / What :** correction d'une regression du widget « taches » : un job
d'analyse / synthese / transcription termine en erreur s'affichait indefiniment
« En cours… » (spinner) dans le dropdown et ne passait jamais le bouton en rouge.
Cause : le modele ecrit `status="error"` (`ExtractionJobStatus.ERROR`, coherent avec
`PageStatus` et `TranscriptionJobStatus`), mais `views_taches.py` et
`taches_dropdown.html` testaient `"failed"` — une valeur qui n'existe dans aucun enum.

**Pourquoi / Why :** introduit lors de la session A.8 (simplification des statuts).
Le vocabulaire du front a diverge de celui des modeles. `"failed"` n'etant jamais egal
a `"error"`, les jobs en erreur n'etaient ni comptes (badge non lu), ni detectes comme
erreur (etat rouge prioritaire), et tombaient dans le `else` du template → spinner
« En cours » permanent. Les erreurs ne remontaient donc jamais a l'utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views_taches.py` | Comparaisons de statut `"failed"` → `"error"` (compteurs non lues, etat erreur, marquer-toutes-lues) |
| `front/templates/front/includes/taches_dropdown.html` | `{% elif tache.status == "failed" %}` → `"error"` (icone + libelle Erreur) |
| `front/tasks.py` | Libelle WebSocket `notifier_tache_terminee(status="failed")` → `"error"` + docstring |
| `front/tests/test_phases.py` | `test_bouton_erreur_si_failed_non_lu` → `_si_error_non_lu`, `status="error"` |

### Migration
- **Migration necessaire / Migration required :** Non
- **Nettoyage des jobs deja bloques :** repasser en `"error"` les jobs orphelins restes
  `pending` / `processing` (worker interrompu) via `manage.py shell`
  (`ExtractionJob` + `TranscriptionJob`).

---

## 2026-05-02 — Session A.8 : Statuts binaires + drawer-only + FALC additionnel

**Quoi / What :** simplification massive de la couche debat — `ExtractedEntity.statut_debat`
passe de 6 valeurs (nouveau, discutable, discute, consensuel, controverse, non_pertinent)
a **2 valeurs binaires** (`nouveau`, `commente`) auto-derivees par signal Django depuis
l'existence de commentaires. Refonte UX en **drawer-only** : suppression de la carte
inline (fusion vers `_card_body.html` unique). Retrait additionnel FALC : edition
d'extraction, edition/suppression de commentaire, onglet "Tous les commentaires",
bouton "Replier la carte", tri "Statut de debat".

**Pourquoi / Why :** suite logique du brainstorming YAGNI 2026-05-01 et de la session
A.7. Les 6 statuts manuels (consensuel/controverse/etc.) demandaient un effort cognitif
non valide par l'usage : sur l'instance live, la majorite des entites restaient en
"nouveau" et la curation manuelle etait quasi-inexistante. La logique de gating
"synthese bloquee si <80% consensus" empechait de lancer des syntheses dont l'utilisateur
voulait quand meme tester la qualite. La carte inline + drawer = 2 templates a maintenir
pour le meme objet ; la fusion supprime la divergence. Les autres retraits FALC (edition
d'extraction, edition/suppression de commentaire, onglet doublon, replier) ciblent des
features a usage faible/nul.

### Changements principaux / Main changes

1. **Signal Django auto-update** : nouveau `hypostasis_extractor/signals.py`. Le statut
   `statut_debat` est auto-derive de l'existence de commentaires (post_save +
   post_delete sur `CommentaireExtraction`). Plus de set manuel.
2. **Enum reduit** : `StatutDebat` passe de 6 valeurs a 2 (`NOUVEAU`, `COMMENTE`).
   Migration data + AlterField.
3. **Fusion `non_pertinent` -> `masquee`** : le statut `non_pertinent` disparait, ses
   instances en DB sont fusionnees dans `masquee=True`. Le champ `masquee` devient
   independant du statut.
4. **Action `changer_statut` retiree** : 4 boutons UI supprimes de la carte.
5. **Refonte drawer-only** : suppression de `carte_inline.html` + JS de creation
   dynamique de carte sous les paragraphes. Clic pastille -> ouvre drawer + scroll
   vers la carte concernee. **Le drawer est l'unique endroit pour voir et commenter
   une extraction.**
6. **`_card_body.html` unique** : retrait du parametre `mode`, partial unique pour
   le drawer (et le bottom_sheet mobile). Le formulaire commenter cible
   `closest .extraction-content` avec swap `outerHTML` -> les commentaires apparaissent
   immediatement sans toast ni rechargement.
7. **Pastille triangle orange** : le statut `commente` s'affiche en triangle orange
   (clip-path CSS) au lieu d'un cercle vert. Plus distinctif visuellement et coherent
   avec le code couleur "discussion en cours".
8. **Layout commentaires Facebook-like** : pseudo en haut (gras), commentaire en
   dessous. Plus lisible que l'ancien layout horizontal avec typo Srisakdi.
9. **Dashboard consensus simplifie** : graphique 6 segments remplace par barre binaire
   `commentees / total`. Le bouton "Lancer la synthese" reste present (sans gate).
10. **`_calculer_consensus`** simplifie de ~30 a ~10 lignes.
11. **Action `vue_commentaires`** retiree + template + onglet "Tous les commentaires"
    (redondant avec le drawer).
12. **Actions `modifier_commentaire` + `supprimer_commentaire`** retirees + serializers.
13. **YAGNI edition d'extraction** : actions `editer` + `modifier`, helper
    `_peut_editer_extraction`, bouton "Modifier" et modale d'edition retires entierement.
14. **Tri "Statut de debat"** retire du selecteur du drawer (plus de sens binaire).
15. **Bouton "Replier la carte"** (▴) retire (drawer a son ✕).
16. **Bouton "tâches" (A.6)** : distingue maintenant `analyse` vs `synthese` dans le
    dropdown, lien "Voir le resultat" pointe vers la page V2/V3 creee pour les syntheses.
17. **CSS** : 6 paires de variables `--statut-*` reduites a 2.
18. **Marginalia.js** : matrice 6 statuts -> 2 (couleur orange `#E69F00` pour
    `commente`).
19. **Templates aide** (`aide_desktop`, `aide_mobile`, `onboarding_vide`) simplifies :
    section explicative des 6 statuts -> bloc binaire + mention "le statut est automatique".
20. **Fixtures** (`charger_fixtures_demo.py`) : valeurs riches `statut_debat` retirees
    -> `nouveau` (le signal complete a `commente` quand les commentaires sont crees).

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/0029_a8_recalcul_statuts_fusion_non_pertinent.py` :
  RunPython qui fusionne `non_pertinent` -> `masquee=True` puis recalcule tous les
  statuts depuis les commentaires (option A : recalcul pur).
- `hypostasis_extractor/migrations/0030_a8_alter_statut_debat_choices.py` : AlterField
  qui reduit l'enum a 2 valeurs.

### Solde net / Net balance

- 8 phases (1-8) + 4-bis : **~-2950 lignes nettes** sur cette session
- Cumul cleanup A.1 -> A.8 : ~15500 lignes net retirees en 8 sessions

### Verification anti-regression / Anti-regression check

- Snapshot tests pre-A.8 : 743 tests / 723 OK / 0 fail / 20 errors préexistantes
- Snapshot tests post-A.8 : **690 tests / 658 OK / 0 fail** / 20 errors préexistantes (mêmes E2E + test_analysis)
- 53 tests obsoletes retires/adaptes, **aucune regression introduite**
- Test UI Chrome : page lecture, drawer Analyses (avec hypostases visibles, commentaires
  inline, bouton commenter), creation/suppression commentaire (signal -> statut auto),
  dashboard consensus avec bouton synthese, mobile (bottom_sheet) — tous OK.

### Hors perimetre / Out of scope (conserve intact)

- Synthese deliberative + analyseurs synthetiseurs
- Versionning de pages (`parent_page`, `versions_enfants`)
- Bouton "Historique" + "Comparer V1↔V2" + tabs versions
- Suppression d'extraction (`btn-supprimer-extraction`) + masquer/restaurer
- Filtre contributeurs avec dimming
- Bouton "tâches" A.6 + signal WebSocket + dropdown + marquer-lue
- Systeme de commentaires (`CommentaireExtraction`)

### References / References

- Spec A.8 : `PLAN/A.8-statuts-binaires-fusion-templates-spec.md`
- Plan d'execution : `PLAN/A.8-statuts-binaires-fusion-templates-plan.md`
- Spec maître YAGNI : `PLAN/REVUE_YAGNI_2026-05-01.md`

---

## 2026-05-02 — Session A.7 : Retrait Reformulation IA + Restitution IA + Restitution manuelle

**Quoi / What :** retrait integral des fonctionnalites Reformulation IA, Restitution IA
et Restitution manuelle (code mort en pratique : 0/134 extractions utilisaient ces
champs en DB, sections invisibles dans l'UI). Conservation totale de la Synthese
(seul mecanisme IA reellement utilise) et du versionning de pages (utilise par la
Synthese).

**Pourquoi / Why :** suite logique du brainstorming YAGNI 2026-05-01 (cf.
`PLAN/REVUE_YAGNI_2026-05-01.md`) et de la refonte WebSocket A.6. Audit DB +
Chrome a confirme l'absence d'usage : aucune entite avec `texte_reformule`,
aucune avec `texte_restitution_ia`, aucune `restitution_page` non-null sur les
134 extractions de l'instance live. Aucun bouton Reformuler/Restituer/Pre-remplir-IA
visible dans l'UI courante (sidebar droite cachee + sections conditionnees a des
champs DB vides). Le code mort cumule represente une dette technique non
justifiee qui complique la refonte RAG a venir.

### Changements principaux / Main changes

1. **2 taches Celery supprimees / 2 Celery tasks removed** : `reformuler_entite_task`
   (~110 lignes), `restituer_debat_task` (~115 lignes) dans `front/tasks.py`.
2. **9 actions ViewSet retirees / 9 ViewSet actions removed** : 3 actions
   reformulation IA (`choisir_reformulateur`, `previsualiser_reformulation`,
   `reformuler`), 4 actions restitution IA (`choisir_restituteur`,
   `previsualiser_restitution`, `generer_restitution`, `restitution_ia_status`),
   1 action restitution manuelle (`creer_restitution`), 1 action `fil_discussion`
   + helper `_re_rendre_fil_discussion`.
3. **3 serializers retires / 3 serializers removed** : `RunReformulationSerializer`,
   `RunRestitutionSerializer`, `RestitutionDebatSerializer`.
4. **7 templates supprimes / 7 templates deleted** : `reformulation_en_cours.html`,
   `choisir_reformulateur.html`, `confirmation_reformulation.html`,
   `restitution_ia_en_cours.html`, `choisir_restituteur.html`,
   `confirmation_restitution.html`, `fil_discussion.html`.
5. **13 champs DB retires / 13 DB fields removed** via migration consolidee :
   - `ExtractedEntity` : `texte_reformule`, `reformule_par`, `reformulation_en_cours`,
     `reformulation_lancee_a`, `reformulation_erreur`, `restitution_page`,
     `restitution_texte`, `restitution_date`, `restitution_ia_en_cours`,
     `restitution_ia_lancee_a`, `restitution_ia_erreur`, `texte_restitution_ia`
   - `ExtractionJob` : `est_reformulation`
6. **Enum `TypeAnalyseur` reduit de 4 a 2 valeurs** : suppression de `REFORMULER`
   et `RESTITUER`. Reste `ANALYSER` + `SYNTHETISER`.
7. **Modele vestige `core.Reformulation` supprime** : zero usage en code et zero
   ligne en DB. Heritage d'une architecture TextBlock-based abandonnee.
8. **Related_name renomme** : `Page.parent_page.related_name` passe de `restitutions`
   a `versions_enfants` pour coherence semantique (la Synthese aussi cree des
   versions enfants).
9. **Templates branches nettoyes** : sections `{% if reformulation_* %}` /
   `{% if restitution_* %}` retirees de `vue_commentaires.html` ; bouton hover
   `btn-commenter-extraction` (qui pointait vers `fil_discussion`) retire de
   `extraction_results.html` et `bottom_sheet_extraction.html` ; logique de timeout
   reset des reformulations bloquees (~50 lignes) retiree de l'action
   `vue_commentaires` ; contexte `analyseurs_reformuler_existent` /
   `analyseurs_restituer_existent` retire des actions ViewSet.
10. **JS nettoye / JS cleaned** : handler clic `.restitution-ancre` retire de
    `hypostasia.js` (pastille violette inline orpheline) ; options select
    `<option value="reformuler">` et `<option value="restituer">` retirees du
    SwAlert d'edition d'analyseur.
11. **Templates de l'editeur d'analyseur mis a jour** : `analyseur_editor.html`
    (2 options `<option>` retirees), `analyseur_item.html` (couleur badge
    `bg-amber-400` pour reformuler retiree), `modale_prompt_readonly.html` (2
    branches `{% elif %}` retirees + ajout d'une branche `synthetiser` manquante).
12. **Vestige template** : `core/templates/core/includes/sidebar_items_partial.html`
    referencait `block.reformulations.all` (related_name du modele supprime). Aurait
    plante au prochain rendu de la sidebar — VIEW 3 (`reformulations`), VIEW 7
    (`edit_reformulations`) et bouton toolbar « Re-ecriture » retires (~75 lignes).
13. **3 fichiers fixtures JSON nettoyes** des 13 champs DB retires :
    `exemple_deliberation.json`, `demo_alignement_versions.json`, `demo_completes.json`.
14. **Fixture analyseur "FALC" (type reformuler) retiree** de `charger_fixtures_demo.py`.
15. **Tests morts retires** : 1 classe `Phase24IntegrationReformulationMockTest` +
    4 methodes individuelles dans test_phases.py + adaptation de 3 methodes de tests
    survivants (`Phase04ModifierCommentaireTest`, `Phase04SupprimerCommentaireTest`,
    `Phase24ResolveModelParamsAnthropicTest`) qui referençaient des chaines obsoletes.

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/0028_a7_retrait_reformulation_restitution_fields.py` :
  13 RemoveField + 1 AlterField (TypeAnalyseur).
- `core/migrations/0033_a7_retrait_modele_reformulation.py` : 1 DeleteModel.
- `core/migrations/0034_a7_renommer_related_name_versions_enfants.py` : 1 AlterField
  (related_name).

### Solde net / Net balance

- 28 fichiers modifies, 7 templates supprimes, 3 nouvelles migrations
- **+304 / −4794 = −4490 lignes nettes**
- Cumul cleanup A.1 → A.7 : ~12900 lignes net retirees en 7 sessions

### Verification anti-regression / Anti-regression check

- Snapshot tests pre-A.7 : 748 tests, 728 OK, 0 fail, 20 errors (preexistantes E2E
  playwright + script orphelin)
- Snapshot tests post-A.7 : **743 tests, 723 OK, 0 fail, 20 errors** (memes 20
  preexistantes — zero regression introduite)
- `manage.py check` : System check identified no issues (0 silenced)
- Test UI Chrome : page `/lire/4/` se charge proprement (33 cartes inline + 59
  pastilles + onglets V1/V2/V3/V4 + Synthese deliberative). Endpoint
  `/extractions/vue_commentaires/?page_id=4` rend 77 KB sans aucune ref obsolete.
  Aucun lien hx-get/hx-post avec URL obsolete dans le DOM.

### Hors perimetre / Out of scope (conserve intact)

- Tache Celery `synthetiser_page_task` et helper `_construire_prompt_synthese`
- Type analyseur `SYNTHETISER` + 3 analyseurs synthetiseurs en fixture
  (Charte, Mathemagique, Synthese deliberative)
- Versionning Page (`parent_page`, `version_number`, `version_label`)
- Carte inline `carte_inline.html` + bouton "Commenter" inline (pure JS local)
- Systeme de commentaires (`CommentaireExtraction`) + statuts de debat +
  action `changer_statut`
- Helper `core/llm_providers.py:appeler_llm` (utilise par la Synthese)

### References / References

- Plan d'execution : `PLAN/A.7-retrait-reformulation-restitution.md`
- Spec maitre : `PLAN/REVUE_YAGNI_2026-05-01.md`
- Sessions precedentes A.1-A.6 : retrait Explorer / Heatmap / Mode focus /
  Stripe / Bibliotheque analyseurs / refonte WebSocket

---

## 2026-04-29 — PHASE-29 : Synthese deliberative dans le drawer + bool est_par_defaut + fix WebSocket OOB + audit HTMX (alpha:0.3.1)

**Quoi / What:** Refonte UX complete de la synthese deliberative dans le drawer (miroir
du flow extraction), avec markdown server-side, sélecteur d'analyseurs en boutons,
notification cross-page via WebSocket, audit HTMX complet et nombreux fix adjacents.

**Pourquoi / Why:** Le modal de synthese etait construit en JS (anti-pattern djc) et
manquait l'estimation prix / le prompt complet / la gate Stripe. L'utilisateur voulait
le meme niveau d'information que pour l'extraction. Les bool `inclure_extractions` et
`inclure_texte_original` etaient sauvegardes mais ignores par la tache Celery.
Long audit HTMX en fin de session pour stabiliser les retours et ne plus avoir de
"bordel" dans les comportements selon la page.

### Changements principaux / Main changes

1. **Endpoint `previsualiser_synthese`** sur `PageViewSet` : calcule estimation tokens
   (50% output, sans chunking), consensus complet (compteurs + bloquantes), compteurs
   d'extractions/commentaires disponibles, gate Stripe, conditions de blocage.
2. **Drawer de confirmation** (`confirmation_synthese.html`) : selecteur d'analyseur,
   encart consensus, infos analyseur, estimation, bouton « Voir le prompt complet ».
3. **Polling drawer** : `synthese_en_cours_drawer.html` (spinner pendant la synthese,
   message d'erreur + retry sinon). Auto-fermeture du drawer + chargement V2 en zone-lecture
   via `HX-Trigger: fermerDrawer` + OOB sur `#zone-lecture`.
4. **Bool `est_par_defaut`** sur l'analyseur (un par type) : `save()` decoche
   automatiquement les autres du meme type. Toast info quand un autre est decoche.
5. **Bool `inclure_extractions` / `inclure_texte_original`** branches dans
   `_construire_prompt_synthese` : sections injectees selon les bool de l'analyseur.
   Validation « au moins l'un des deux » dans la vue.
6. **Helper `_calculer_consensus(page)`** extrait de la vue dashboard, reutilise par
   le drawer de confirmation.
7. **WebSocket synthese terminee** : la tache Celery envoie au groupe
   `notifications_user_{user.pk}` un message `synthese_terminee`. Le `NotificationConsumer`
   emet un toast OOB cliquable « Voir la version V{N} ». Notification cross-page : meme
   si l'utilisateur a navigue ailleurs, il est notifie.
8. **Tableau analyseurs** dans `/api/analyseurs/` : Nom / Type / Texte / Extractions /
   Actif / Defaut. La liste affiche TOUS les analyseurs (actifs et inactifs).
   Le filtre `is_active=True` ne s'applique qu'au selecteur du drawer.
9. **Markdown server-side pour la synthese** : ajout de la lib `markdown` Python.
   Le prompt impose explicitement le format markdown (titres, gras, citations,
   listes). Le rendu HTML passe par `html.escape()` puis `markdown.markdown(...)` :
   securite XSS preservee + structure HTML propre. Avant : split paragraphes nu.
10. **Selecteur d'analyseur en boutons** dans le drawer (vs select deroulant).
    Titre « Quel moteur utiliser ? » + sous-titre explicatif. Bouton actif en violet,
    etoile bleue pour le defaut. Au clic = recharge le drawer (estimation/prompt
    re-calcules pour le nouvel analyseur).
11. **Bouton « Voir le prompt complet »** deplace juste sous le selecteur d'analyseur
    pour comparer rapidement les prompts entre moteurs.
12. **Toggle `is_active` dans l'editeur d'analyseur** : permet de desactiver un
    analyseur sans le supprimer (il reste visible dans la liste mais exclu du
    selecteur du drawer).
13. **Bouton « Supprimer cette version »** dans `lecture_principale.html` (a cote
    de Historique) : visible uniquement si `parent_page` non-null ET utilisateur
    proprietaire du dossier. Action `LectureViewSet.destroy()` qui refuse :
    (a) la racine, (b) les versions avec commentaires (preserve le travail
    collaboratif), (c) les non-proprietaires. Apres suppression : `HX-Location`
    vers la racine.
14. **Empecher l'import sans connexion** : `data-user-authenticated` sur `<body>`
    + guard JS sur les 3 inputs d'import (toolbar, overlay, onboarding) qui
    dispatch `authRequise` -> SweetAlert connexion.
15. **URL push apres import** : header `X-Hypostasia-Page-Url` cote serveur +
    `history.pushState()` cote JS. L'URL change apres import (avant : restait
    sur l'ancien document).
16. **Titre de version = nom de l'analyseur** : `version_label = analyseur_synthese.name`
    (ex: « V2 - Mathemagique » au lieu de « V2 - Synthese deliberative »).
    Permet de distinguer les versions selon l'analyseur utilise.
17. **Audit HTMX en fin de session** : 3 agents Explore deployes en parallele
    pour cartographier les `hx-target`/`hx-swap-oob`, valider les fallbacks F5
    (15/15 vues OK), et tracer les flows analyse + synthese. Resultat : projet
    globalement sain, 3 vrais problemes corriges (voir ci-dessous).

### Ameliorations issues de l'audit HTMX (fin de session)

| # | Action | Resolution |
|---|---|---|
| P1 | Polling synthese qui continue apres navigation cross-page (fuite ~60 requetes inutiles sur 3 min) | Filtre conditionnel `every 3s [document.querySelector('#zone-lecture [data-page-id]')?.dataset.pageId === '{{ page.pk }}']` : HTMX evalue la condition a chaque tick, pas de requete si l'utilisateur a navigue ailleurs |
| P3 | OOB complexe `synthese_terminee_oob.html` (3 swaps + HX-Trigger) en fin de synthese | Remplace par `HX-Location` natif HTMX vers `/lire/V{N}/` + `HX-Trigger fermerDrawer`. URL pushed proprement, etat coherent, pas d'OOB fragile. Partial supprime |
| P5 | `comparer_hypostases` sans fallback F5 (URL partagee = page nue) | Si non-HTMX, redirige vers la vue parente `/lire/{pk}/comparer/?v2=...` qui affiche l'onglet correctement |
| Doublon | Toast `Synthese terminee` envoye deux fois (SweetAlert + WS) | Retire le SweetAlert de `synthese_status` completed, garde le toast WS qui est plus riche (lien cliquable) |
| Cohérence | Liste/api/analyseurs/ filtrait `is_active=True` (analyseurs disparaissaient) | Affiche TOUS les analyseurs, le filtre `is_active=True` ne s'applique qu'au selecteur du drawer |

### Bugs corriges / Bugs fixed

| Bug | Cause | Fix |
|---|---|---|
| Option « Synthetiser » absente du formulaire de creation | `hypostasia.js:273-277` n'avait que 3 options dans le SweetAlert | +1 option |
| Analyseur disparait apres save | `BooleanField(required=False)` de DRF rempli `validated_data` avec `False` quand le PATCH est en form-urlencoded sans le champ. Le `setattr` desactivait alors `is_active` | `partial_update` ne setter QUE les champs explicitement dans `request.data.keys()` |
| `analyseurId is not defined` dans le JS de l'editeur | La variable etait declaree dans le scope local d'un callback de click | Hisser au scope du IIFE global |
| Le toast WS HTMX ne s'affichait jamais | `htmx-ext-ws-2.0.4` ne gere pas la syntaxe courte `<div id="X" hx-swap-oob="beforeend">`. Bug touchait aussi `notification` standard du projet | Utiliser la syntaxe explicite `<div hx-swap-oob="beforeend:#X">` |
| Migration `synthetiser` manquante | Le model avait 4 types mais la migration 0011 n'en avait que 3 | Migration `0025_alter_analyseursyntaxique_type_analyseur.py` (ajoutee dans le merge precedent) |
| `analyseurId is not defined` dans le JS de l'editeur (callbacks externes au scope) | Variable declaree dans le scope local d'un callback de click | Hisser au scope du IIFE global |
| Selecteur d'analyseur de synthese : changement non pris en compte | `hx-vals` codait l'ID au render serveur (capture statique) | Switch vers `hx-include="#select-analyseur-synthese"` (lecture LIVE), puis remplace par boutons (rechargement complet du drawer a chaque clic) |
| `bg-violet-400` invisible (toggle, pastille) | Pas dans le subset Tailwind compile du projet | Switch vers `bg-violet-500` (present) |
| `peer-checked:bg-emerald-500` ne se colore pas | Variant non genere par Tailwind | Switch vers `peer-checked:bg-blue-500` (present) |
| Commentaires Django multi-lignes visibles dans le HTML | `{# ... #}` ne fonctionne QUE sur une ligne en Django (test reproduit) | Switch vers `{% comment %}...{% endcomment %}` (1 occurrence trouvee dans `synthese_en_cours_drawer.html`) |
| Lien navbar `/api/analyseurs/` bug HTMX (JS auto-save ne se re-bind pas correctement apres swap) | `hx-get` HTMX au lieu d'un GET classique | Retire les attributs HTMX → navigation classique avec full page reload |
| Toast info `est_par_defaut` decoche → ne s'affichait pas | `fetch().then()` ne propageait pas le HX-Trigger du serveur | Lecture du header HX-Trigger dans `.then()` + `dispatchEvent(new CustomEvent(name, {detail}))` |

### Fichiers crees / Created files

| Fichier / File | Description |
|---|---|
| `front/templates/front/includes/confirmation_synthese.html` | Partial confirmation drawer (estimation, consensus, prompt, selecteur boutons) |
| `front/templates/front/includes/synthese_en_cours_drawer.html` | Partial polling (spinner / erreur retry) avec filtre conditionnel anti-zombie |
| `front/templates/front/includes/ws_synthese_terminee.html` | Toast WS cross-page envoye par le `NotificationConsumer` |
| `front/tests/test_phase29_synthese_drawer.py` | 20 tests unitaires |
| `hypostasis_extractor/migrations/0026_analyseursyntaxique_est_par_defaut.py` | Migration auto |
| `docs/superpowers/specs/2026-04-29-synthese-drawer-confirmation-design.md` | Spec brainstorming |
| `docs/superpowers/plans/2026-04-29-synthese-drawer-confirmation.md` | Plan d'implementation 14 taches |

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | +champ `est_par_defaut` + override `save()` pour decocher les autres du meme type |
| `hypostasis_extractor/serializers.py` | +`est_par_defaut` dans `AnalyseurSyntaxiqueUpdateSerializer` |
| `hypostasis_extractor/views.py` | `partial_update` : ne setter que les champs envoyes (fix bug DRF) + toast info `est_par_defaut`. `list` affiche TOUS les analyseurs (plus de filtre `is_active=True`) |
| `hypostasis_extractor/templates/.../analyseur_editor.html` | +option `synthetiser`, +toggle est_par_defaut, label « extractions et leurs commentaires », hisser `analyseurId`, propagation HX-Trigger via fetch.then |
| `hypostasis_extractor/templates/.../configuration_llm.html` | Liste → tableau (Nom/Type/Actif/Defaut) |
| `hypostasis_extractor/templates/.../includes/analyseur_item.html` | Refait en `<tr>` avec colonnes |
| `front/views.py` | Helper `_calculer_consensus` extrait. Nouvelle action `previsualiser_synthese`. `synthetiser` (POST) renvoie partial drawer + `HX-Trigger: ouvrirDrawer`. `synthese_status` adapte (3 branches drawer + OOB completed + fermerDrawer) |
| `front/tasks.py` | `_construire_prompt_synthese(page, job, analyseur)` (3e arg). Sections conditionnees aux bool. Guard `dernier_job_analyse=None`. `synthetiser_page_task` envoie au groupe utilisateur `notifications_user_{pk}` un signal `synthese_terminee` |
| `front/consumers.py` | +handler `synthese_terminee` qui rend le toast WS |
| `front/templates/front/includes/ws_toast.html` | Syntaxe corrigee `hx-swap-oob="beforeend:#ws-toasts"` (resout aussi le bug global de tous les toasts WS du projet) |
| `front/templates/front/includes/dashboard_consensus.html` | Bouton synthese : `hx-get` direct vers `previsualiser_synthese` (suppression `onclick="ouvrirModaleSynthese"`) |
| `front/templates/front/includes/carte_analyseur.html` | +badge « Par defaut » et badge type `synthetiser` (etait manquant) |
| `front/templates/front/includes/detail_analyseur_readonly.html` | Idem |
| `front/static/front/js/hypostasia.js` | +option `synthetiser` au SweetAlert. +listener `fermerDrawer`. `ouvrirPanneauDroit` appelle `ouvrir(false)` pour ne pas ecraser le contenu pre-swap |
| `front/static/front/js/dashboard_consensus.js` | Suppression de `ouvrirModaleSynthese` et `fermerModaleSynthese` (anti-pattern JS-built HTML) |
| `front/static/front/js/drawer_vue_liste.js` | `ouvrirDrawer(rechargerLeContenu=true)` ne charge le contenu que si demande explicitement |
| `front/management/commands/charger_fixtures_demo.py` | `est_par_defaut=True` sur les 3 analyseurs demo |

### Fichiers supprimes / Deleted files

- `front/templates/front/includes/synthese_en_cours.html` (remplace par `synthese_en_cours_drawer.html`)
- `front/templates/front/includes/synthese_terminee_oob.html` (remplace par `HX-Location` natif HTMX en fin de session)

### Dependances ajoutees / New dependencies

- `markdown==3.10.2` (pyproject.toml) — parser markdown server-side pour le rendu de la synthese

### WebSocket — flux complet

Le WS pre-existant `NotificationConsumer` (route `/ws/notifications/`) est connecte sur
toutes les pages via `<div ws-connect="/ws/notifications/">` dans `base.html`, avec un
groupe par utilisateur (`notifications_user_{user.pk}`). Il reste connecte cross-page
tant que le navigateur ne ferme pas l'onglet. PHASE-29 reutilise ce mecanisme :

```
1. Utilisateur clique "Lancer la synthèse" dans le drawer.
2. POST /lire/{pk}/synthetiser/ → cree un ExtractionJob + Celery .delay()
3. Celery (synthetiser_page_task) :
   - construit le prompt selon les bool de l'analyseur
   - appelle le LLM
   - cree une Page enfant V2
   - emet : envoyer_progression_websocket(
         f"notifications_user_{owner.pk}",
         "synthese_terminee",
         {"page_synthese_id": ..., "version_number": ..., "titre_page": ...},
     )
4. NotificationConsumer.synthese_terminee() rend ws_synthese_terminee.html et
   envoie le HTML au client via WebSocket.
5. htmx-ext-ws receptionne, applique les OOB swaps :
   - <div hx-swap-oob="beforeend:#ws-toasts">...</div> → ajoute un toast cliquable
6. Le toast contient un lien hx-get vers la V2 → clic = chargement zone-lecture.
```

**Piege OOB important** : la syntaxe courte `<div id="ws-toasts" hx-swap-oob="beforeend">`
ne marche PAS avec `htmx-ext-ws-2.0.4`. Toujours utiliser la syntaxe explicite
`<div hx-swap-oob="beforeend:#ws-toasts">`.

### Tests / Tests

- 20 nouveaux tests unitaires (`test_phase29_synthese_drawer.py`)
- 38 tests `test_phase28_light` adaptes au nouveau flux drawer
- Total : 74 tests verts (`phase29` + `phase28_light` + `analyse_drawer_unifie`)
- Pas de tests E2E (projet en alpha)

### Decisions de design / Design decisions

- **Approche miroir extraction** plutot que generique unifie (YAGNI, djc privilegie le verbeux et lisible top-to-bottom).
- **Bool `est_par_defaut` par type** (vs default global) — chaque type a son contexte.
- **Polling drawer + WS** : le polling rafraichit en temps reel quand l'utilisateur reste sur la page ; le WS notifie cross-page. Les deux mecanismes coexistent comme dans le flux extraction. **MAIS** le polling est protege par un filtre conditionnel JS qui le pause si l'utilisateur a navigue ailleurs.
- **Pas de bouton Annuler explicite** dans la confirmation — la croix du drawer ou Escape suffisent.
- **Auto-fermeture du drawer en fin de synthese** + bascule auto sur la V2 via `HX-Location` natif HTMX (vs OOB complexes).
- **Ratio output 50%** comme l'extraction (a affiner apres mesure reelle).
- **Selecteur d'analyseur en boutons** plutot qu'en `<select>` : indique mieux le choix possible et permet d'afficher visuellement le defaut (etoile bleue).
- **Audit HTMX** : conserver le pattern `polling drawer + WS cross-page` plutot que tout migrer vers WS-only. Defense en profondeur, le WS peut tomber, le polling rattrape. Cout de la refonte > benefice marginal.

### Pieges documentes / Documented pitfalls

- **`htmx-ext-ws-2.0.4` syntaxe OOB** : la forme courte `<div id="X" hx-swap-oob="beforeend">` ne marche PAS, il faut la forme explicite `<div hx-swap-oob="beforeend:#X">`. Bug reproduit, fix dans `ws_toast.html` et `ws_synthese_terminee.html`.
- **DRF + form-urlencoded + `BooleanField(required=False)`** : DRF rempli `validated_data` avec `False` pour les BooleanField non envoyes, ce qui peut desactiver des champs accidentellement. Solution : `partial_update` ne setter que les champs explicitement dans `request.data.keys()`.
- **Django commentaires `{# #}`** : ne fonctionnent QUE sur une seule ligne. Multi-ligne = `{% comment %}...{% endcomment %}` obligatoire (sinon le commentaire apparait visible dans le HTML rendu).
- **Subset Tailwind** : seules certaines variantes de couleurs/peer-checked sont compilees. Verifier avec `grep` dans `tailwind.css` avant d'utiliser une classe rare.
- **Polling HTMX et navigation** : le polling continue dans le DOM masque apres swap de la zone-lecture. Solution : filtre conditionnel `every Ns [expr]` qui pause si conditions non remplies.

### Migration

- **Migration necessaire / Migration required:** Oui — `0026_analyseursyntaxique_est_par_defaut.py`
- `docker exec hypostasia_web uv run python manage.py migrate`

---

## 2026-03-17 — PHASE-26c : Refactoring statuts de debat (6 statuts + ownership)

**Quoi / What:** Refactoring du systeme de statuts de debat : passage de 4 a 6 statuts, ajout du controle d'ownership, suppression du double badge, integration de "masquer" dans le cycle deliberatif.

**Pourquoi / Why:** 3 problemes UX identifies : toutes les extractions demarraient en rouge (alarmant), n'importe quel user pouvait changer le statut, et "masquer" etait deconnecte du cycle deliberatif.

### Changements principaux / Main changes

1. **6 statuts** : nouveau (gris), discutable (orange), discute (ambre), consensuel (vert), controverse (rouge), non_pertinent (gris pale)
2. **Ownership** : seul le proprietaire du dossier peut changer statut, masquer, restaurer
3. **Non pertinent** remplace le boolean `masquee` (synchronise via `save()`)
4. **Double badge supprime** : le `_card_body.html` n'affiche plus le statut en doublon
5. **Auto-promotion** : commentaire sur nouveau/discutable → discute
6. **Dashboard 6 compteurs** : grille 3x2, non_pertinent exclu du calcul de consensus

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | +2 choices, default→nouveau, save() sync masquee |
| `hypostasis_extractor/migrations/0021_*.py` | AlterField + RunPython data migration |
| `front/views.py` | Helper _est_proprietaire_dossier, ownership checks, est_proprietaire contexte |
| `front/serializers.py` | +2 choices ChangerStatutSerializer |
| `front/static/front/css/hypostasia.css` | 6 couleurs statut, discutable rouge→orange |
| `front/static/front/js/marginalia.js` | +2 entrees COULEURS_STATUT |
| `front/static/front/js/keyboard.js` | Check ownership avant raccourci S |
| `front/templates/.../carte_inline.html` | Boutons owner-only, +discutable, +non_pertinent |
| `front/templates/.../_card_body.html` | Suppression double badge statut |
| `front/templates/.../drawer_vue_liste.html` | Masquer/restaurer owner-only, "Non pertinentes" |
| `front/templates/.../dashboard_consensus.html` | Grille 3x2, 6 compteurs |
| `front/templates/front/base.html` | data-est-proprietaire sur #zone-lecture |
| `hypostasis_extractor/templatetags/extractor_tags.py` | +2 icones statut |
| `front/tests/test_phases.py` | ~17 updates + 5 nouvelles classes test |
| `front/management/commands/charger_fixtures_demo.py` | Redistribution 6 statuts |

### Migration
- **Migration necessaire / Migration required:** Oui — `hypostasis_extractor/migrations/0021_refactoring_statuts_debat.py`
- `uv run python manage.py migrate`

---

## 2026-03-16 — PHASE-26a UX : 5 ameliorations filtre multi-contributeurs

**Quoi / What:** 5 ameliorations UX du filtre multi-contributeurs :
1. **Scroll-to-first** : le drawer scrolle en haut apres activation/desactivation d'un filtre
2. **Noms dans compteur** : "2 sur 78 (marie)" au lieu de "2 sur 78"
3. **Badge entites** : la pilule active affiche le nombre d'entites distinctes (pas de commentaires)
4. **Couleur HSL** : chaque contributeur a une couleur deterministe (hash MD5 du username)
5. **Mode Sauf** : bouton "Sauf" pour inverser le filtre (exclure au lieu d'inclure)

**Pourquoi / Why:** Le facilitateur utilise le filtre pour preparer ses reunions de consensus.
Ces ameliorations rendent l'outil plus lisible (couleurs distinctes, noms), plus precis
(entites vs commentaires), et plus flexible (mode exclure pour voir "tout sauf X").

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | Helper `_calculer_teinte_contributeur()`, enrichissement contributeurs (nombre_entites + couleur_hsl), mode `exclure` avec `.exclude()` |
| `front/templates/front/includes/drawer_vue_liste.html` | Compteur avec noms + sauf, pilule-exclue/pilule-active, bouton Sauf, badge entites, commentaires mode inversé |
| `front/static/front/js/drawer_vue_liste.js` | Scroll-to-first, variable `modeFiltre`, handler bouton Sauf, `getContributeursActuels` inclut pilule-exclue |
| `front/static/front/js/marginalia.js` | `appliquerFiltreContributeurs` supporte `modeFiltre` pour inverser le dimming pastilles |
| `front/static/front/css/hypostasia.css` | `.pilule-contributeur.pilule-active` HSL, `.pilule-exclue` hachures, `.pilule-toggle-mode` |
| `front/tests/test_phases.py` | 8 tests : compteur noms, entites count, couleur HSL (3), exclure, compteur sauf, HX-Trigger mode |

### Migration
- **Migration necessaire / Migration required:** Non

---

## 2026-03-16 — PHASE-26a-bis : Filtre multi-contributeurs (pilules toggle)

**Quoi / What:** Remplacement du `<select>` mono-sélection contributeur par des pilules toggle
réutilisant le pattern `.pilule-locuteur` existant (PHASE-15). Supporte la sélection multiple :
cliquer plusieurs pilules → union des commentaires. Le paramètre `?contributeur=` accepte
désormais une liste séparée par virgules (`?contributeur=1,2,3`), rétro-compatible avec le
format single (`?contributeur=42`).

**Pourquoi / Why:** Le facilitateur veut comparer 2+ contributeurs ("qu'est-ce que Marie ET
Thomas ont dit ?"). Les pilules toggle survivent au swap HTMX, zéro JS custom fragile,
mobile-friendly, FALC.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | `drawer_contenu()` : parsing multi-IDs virgule-séparée, `user_id__in`, HX-Trigger `contributeurs_ids` (plural). Renommage `_calculer_scores_temperature_par_contributeurs()`. `LectureViewSet.retrieve()` : parsing multi-IDs. |
| `front/templates/front/includes/drawer_vue_liste.html` | Select+chip → pilules `.pilule-locuteur` toggle + bouton "Tous ×". Conditions `contributeur_actif` → `contributeurs_actifs` (set). |
| `front/static/front/js/drawer_vue_liste.js` | `getContributeursActuels()` (lecture pilules actives), handler clic pilule toggle, suppression handler select/chip. |
| `front/static/front/js/marginalia.js` | `contributeursFiltresActuels = []`, `appliquerFiltreContributeurs()` (array), listener `contributeurs_ids`. |
| `front/static/front/css/hypostasia.css` | +`.pilule-reset-contributeurs`, suppression `.chip-contributeur-actif` et `.btn-retirer-filtre-contributeur`. |
| `front/tests/test_phases.py` | 4 tests existants adaptés + 5 nouveaux tests PHASE-26a-bis (multi-filtre, HX-Trigger multi, pilules, heatmap union, rétro-compat). |

---

## 2026-03-16 — PHASE-26a : Filtre contributeur sur les commentaires

**Quoi / What:** Filtre par contributeur dans le drawer vue liste des extractions.
Quand un contributeur est selectionne, seules les extractions qu'il a commentees
apparaissent, les commentaires des autres sont dimmes (opacite reduite), les pastilles
de marge non concernees sont desactivees, et la heat map se recalcule pour ne compter
que les commentaires de ce contributeur.

**Pourquoi / Why:** Le facilitateur a besoin de filtrer par contributeur pour preparer
les reunions de consensus ("qu'est-ce que Michel a dit ?"). Ce filtre se combine avec
la heat map pour visualiser la temperature du debat du point de vue d'un contributeur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | +helper `_calculer_scores_temperature_par_contributeur()`, modifier `drawer_contenu()` (param contributeur, liste contributeurs, HX-Trigger), modifier `retrieve()` (heat map par contributeur) |
| `front/templates/front/includes/drawer_vue_liste.html` | +dropdown contributeur, +classe dimming commentaires |
| `front/static/front/js/drawer_vue_liste.js` | +param contributeur sur `chargerContenu()`, event listener select, heatmap reload |
| `front/static/front/js/marginalia.js` | +listener `contributeurFiltreChange`, filtrage pastilles, API `getContributeurFiltre`/`resetContributeurFiltre` |
| `front/static/front/css/hypostasia.css` | +`.commentaire-hors-filtre`, +`.pastille-hors-filtre` |
| `front/tests/test_phases.py` | +13 tests unitaires PHASE-26a (7 base + 6 UX) |
| `front/tests/e2e/test_17_filtre_contributeur.py` | **NOUVEAU** — 6 tests E2E |
| `front/management/commands/charger_fixtures_demo.py` | +24 commentaires sur pages Wikipedia (Ostrom, Alexandre, Sadin) par 4 contributeurs, dossier "Petits textes" rendu public |

### Ameliorations UX (post-implementation)
1. Icone personne devant le select contributeur (differencie du select de tri)
2. Chip/badge actif "nom x" pour retirer le filtre en un clic
3. Compteur "N sur M" quand filtre actif (ex: "2 sur 78")
4. Highlight du nom du contributeur filtre dans les commentaires (fond bleu + gras)
5. Badge point bleu sur le bouton toolbar Extractions quand filtre actif

---

## 2026-03-15 — PHASE-25d UX : Ameliorations Explorer

**Quoi / What:** 7 ameliorations UX sur l'Explorer et le systeme d'invitation :
1. Description optionnelle sur les dossiers (champ `description` 200 chars)
2. Compteur de suivis affiche en ambre sur les cards ("3 suivis")
3. Bouton Explorer (globe) ajoute dans la toolbar principale desktop
4. Toasts de confirmation sur Suivre/Ne plus suivre/Inviter
5. Selecteur tri (Plus recents / Plus suivis / Alphabetique)
6. Preview des 3 premiers titres de pages en badges gris dans les cards
7. Fix bug dropdown auteur duplique (Meta.ordering polluait DISTINCT)

**Pourquoi / Why:** Les cards etaient trop minimales (nom + date), l'Explorer
pas assez decouvrable (cache dans le footer de l'arbre uniquement), et pas de
feedback apres les actions Suivre/Inviter.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +champ `description` sur Dossier |
| `core/migrations/0024_dossier_description.py` | Migration auto |
| `front/serializers.py` | +champ `tri` dans ExplorerFiltresSerializer |
| `front/views_explorer.py` | +annotate nombre_suivis, +tri (populaire/nom/recent), +preview pages, +toasts HX-Trigger, fix DISTINCT |
| `front/views.py` | +toast sur action inviter |
| `front/templates/front/includes/explorer_page.html` | +select tri, +listener toast SweetAlert |
| `front/templates/front/includes/explorer_card.html` | +description, +compteur suivis ambre, +preview pages badges |
| `front/templates/front/base.html` | +bouton globe Explorer dans toolbar |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0024_dossier_description.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25d : Invitation par email + Explorer + DossierSuivi

**Quoi / What:** Invitation par email pour dossiers et groupes (email connu = partage direct,
email inconnu = invitation avec token + email). Page Explorer pour decouvrir les dossiers publics
(recherche, filtre auteur, pagination). Suivi de dossiers publics (4e section "Suivis" dans l'arbre).
Inscription avec token d'invitation → auto-acceptation.

**Pourquoi / Why:** PHASE-25c imposait de connaitre le username exact pour partager. Pas de
decouverte de contenu public. Pas moyen d'inviter un non-inscrit.

### Fichiers crees / Created files
| Fichier / File | Description |
|---|---|
| `front/views_invitation.py` | InvitationViewSet + helpers (creer, accepter, envoyer email) |
| `front/views_explorer.py` | ExplorerViewSet (list, suivre, ne_plus_suivre) |
| `front/templates/front/includes/explorer_page.html` | Page Explorer complete |
| `front/templates/front/includes/explorer_resultats.html` | Resultats pagines |
| `front/templates/front/includes/explorer_card.html` | Card dossier individuelle |
| `front/templates/front/invitation_erreur.html` | Page erreur invitation |
| `front/templates/front/emails/invitation_dossier.txt` | Email invitation dossier (texte) |
| `front/templates/front/emails/invitation_dossier.html` | Email invitation dossier (HTML) |
| `front/templates/front/emails/invitation_groupe.txt` | Email invitation groupe (texte) |
| `front/templates/front/emails/invitation_groupe.html` | Email invitation groupe (HTML) |
| `front/tests/e2e/test_16_invitation_explorer.py` | 8 tests E2E |
| `core/migrations/0023_dossiersuivi_invitation.py` | Migration auto |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +Invitation, +DossierSuivi |
| `hypostasia/settings.py` | +config email (EMAIL_BACKEND, SITE_URL, etc.) |
| `front/serializers.py` | +InviterEmailSerializer, +ExplorerFiltresSerializer |
| `front/views.py` | +action inviter sur DossierViewSet, _render_arbre 4 sections (+ Suivis) |
| `front/views_auth.py` | Handle ?token= dans register |
| `front/views_groupes.py` | +action inviter sur GroupeViewSet |
| `front/urls.py` | +ExplorerViewSet, +InvitationViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | +section Suivis |
| `front/templates/front/includes/_dossier_node.html` | +bouton Ne plus suivre |
| `front/templates/front/includes/partage_dossier_form.html` | +section email + invitations en attente |
| `front/templates/front/register.html` | +hidden field token |
| `front/templates/front/base.html` | +lien Explorer dans footer arbre |
| `front/tests/test_phases.py` | +18 tests unitaires PHASE-25d |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0023_dossiersuivi_invitation.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25c : Visibilite 3 niveaux + groupes + arbre restructure

**Quoi / What:** Systeme de visibilite a 3 niveaux (prive/partage/public) sur les dossiers.
Groupes d'utilisateurs (CRUD) pour faciliter le partage. Arbre restructure en 3 sections
accordeon (Mes dossiers / Partages avec moi / Dossiers publics). Anonymes limites aux dossiers
publics. Controle d'acces lecture/ecriture sur LectureViewSet. Moderation : owner du dossier
peut supprimer les commentaires. Auto-classement des imports dans "Mes imports". Menu contextuel
avec sous-menu visibilite. OOB swaps corriges (centralises via _render_arbre).

**Pourquoi / Why:** Le modele de visibilite PHASE-25 etait binaire (tout ou rien). Pas de
distinction prive/partage/public, pas de groupes, les anonymes voyaient tout.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +VisibiliteDossier, +GroupeUtilisateurs, visibilite sur Dossier, DossierPartage avec groupe+constraints |
| `core/migrations/0022_*.py` | Migration auto |
| `front/views.py` | +3 helpers acces, _render_arbre 3 sections, +changer_visibilite, +quitter, acces LectureViewSet, auto-classify imports, OOB fixes, moderation, DossierViewSet.list filtre |
| `front/views_groupes.py` | **Nouveau** — GroupeViewSet CRUD |
| `front/serializers.py` | +ChangerVisibiliteSerializer, +GroupeCreateSerializer, +GroupeAjouterMembreSerializer |
| `front/urls.py` | +GroupeViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | Rewrite — 3 sections accordeon |
| `front/templates/front/includes/_dossier_node.html` | **Nouveau** — partial reutilisable |
| `front/templates/front/includes/partage_dossier_form.html` | +section groupes |
| `front/static/front/js/arbre_context_menu.js` | +sous-menu visibilite |
| `front/static/front/js/arbre_overlay.js` | +JS accordeon + bouton quitter |
| `front/templates/front/includes/groupe_detail.html` | **Nouveau** — partial template detail groupe |
| `front/tests/test_phases.py` | +23 tests PHASE-25c |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0022_alter_dossierpartage_unique_together_and_more.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25b : Auth extension navigateur

**Quoi / What:** Authentification par token API pour l'extension navigateur Chrome.
L'extension envoie le token dans les headers HTTP. POST /api/pages/ exige un token valide (401 sinon).
Page `/auth/token/` pour generer/regenerer le token. Apres recolte, boutons dossiers pour classer
la page. Dossier "A ranger" auto-cree par defaut. Dedup filtree par owner + partages.
Fix URL hardcodee dans sidebar.js.

**Pourquoi / Why:** L'extension fonctionnait sans authentification — impossible de tracer
qui envoie quoi, ni de classer les pages par utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasia/settings.py` | +rest_framework.authtoken dans INSTALLED_APPS, +CORS_ALLOW_HEADERS |
| `core/views.py` | TokenAuthentication, owner sur create, endpoints me/mes_dossiers/classer_depuis_extension, dedup filtree owner+partages |
| `front/views_auth.py` | +action mon_token (GET/POST) — generation et regeneration de token |
| `front/templates/front/mon_token.html` | **Nouveau** — page standalone token avec bouton copier/regenerer |
| `front/templates/front/base.html` | Lien "Mon token API" dans dropdown menu utilisateur |
| `extension/popup.js` | Token dans headers, feedback auth, boutons dossiers post-recolte |
| `extension/popup.html` | Zones #authStatus et #dossiersChoix |
| `extension/sidebar.js` | Fix URL hardcodee → lecture serverUrl depuis storage + token dans headers |
| `extension/options.html` | Renommer "Cle API" en "Token d'authentification" + help-text |
| `front/tests/test_phases.py` | +12 tests unitaires PHASE-25b |
| `front/tests/e2e/test_15_token.py` | **Nouveau** — 3 tests E2E page token |

---

## 2026-03-15 — PHASE-25 : Users et partage

**Quoi / What:** Authentification Django (login/register/logout), propriete des ressources
(owner sur Dossier/Page), remplacement de `prenom` par `user` FK obligatoire sur
CommentaireExtraction/Question/ReponseQuestion, partage binaire de dossiers (DossierPartage),
protection des ecritures (lectures restent publiques).

**Pourquoi / Why:** L'app fonctionnait en mono-utilisateur avec identification par prenom libre.
Cette phase ajoute une vraie authentification pour tracer les contributions et permettre
le partage de dossiers entre utilisateurs.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +owner sur Dossier/Page, +DossierPartage, user FK sur Question/ReponseQuestion |
| `hypostasis_extractor/models.py` | user FK remplace prenom sur CommentaireExtraction |
| `core/migrations/0021_*.py` | Migration PHASE-25 (owner, DossierPartage, user FK) |
| `hypostasis_extractor/migrations/0020_*.py` | Migration PHASE-25 (user FK commentaire) |
| `core/admin.py` | Adapte pour user FK |
| `front/views_auth.py` | **Nouveau** — AuthViewSet (login/register/logout) |
| `front/views.py` | +_exiger_authentification(), protection ~28 actions POST, request.user dans create, _render_arbre filtre owner |
| `front/serializers.py` | +LoginSerializer, +RegisterSerializer, +DossierPartageSerializer, -prenom sur 3 serializers |
| `front/urls.py` | Enregistrer AuthViewSet |
| `front/templates/front/login.html` | **Nouveau** — page de connexion |
| `front/templates/front/register.html` | **Nouveau** — page d'inscription |
| `front/templates/front/base.html` | Menu utilisateur dans navbar |
| `front/templates/front/includes/fil_discussion.html` | Supprimer prenom, user FK, layout SMS server-side |
| `front/templates/front/includes/vue_commentaires.html` | Idem |
| `front/templates/front/includes/vue_questionnaire.html` | Supprimer prenom, gater formulaires |
| `front/templates/front/includes/drawer_vue_liste.html` | Affichage user.username |
| `front/templates/front/includes/arbre_dossiers.html` | Bouton partager |
| `front/templates/front/includes/partage_dossier_form.html` | **Nouveau** — formulaire partage |
| `front/management/commands/charger_fixtures_demo.py` | Creer users demo, assigner ownership |
| `front/tests/test_phases.py` | +19 tests unitaires PHASE-25, adaptation tests existants |
| `front/tests/e2e/base.py` | Helpers creer_utilisateur_demo, se_connecter |
| `front/tests/e2e/test_13_auth.py` | **Nouveau** — 10 tests E2E auth |
| `front/tests/e2e/__init__.py` | Import test_13 |
| `hypostasia/settings.py` | LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL |

### Audit stack-ccc

Audit complet de conformite au skill stack-ccc realise. 10 non-conformites detectees et corrigees :
- LOCALISATION ajoutee dans toutes les docstrings (views, serializers, helpers)
- Imports deplaces en haut de fichier (plus d'import interne dans les methodes)
- `role="alert"` + `aria-live="assertive"` sur les zones d'erreurs (login, register)
- `aria-label` sur les formulaires d'authentification et le dropdown menu
- `data-testid` sur tous les elements interactifs du partage (input, boutons, lignes)
- `aria-hidden="true"` sur les SVG decoratifs du partage

### Tests — 712 tests verts (614 unitaires + 98 E2E)

| Suite | Nombre | Statut |
|---|---|---|
| Tests unitaires PHASE-25 | 19 | OK |
| Tests unitaires existants (adaptes) | 595 | OK |
| Tests E2E PHASE-25 (auth) | 10 | OK |
| Tests E2E existants (adaptes) | 88 | OK |

---

## 2026-03-15 — PHASE-24 : Providers IA unifies

**Quoi / What:** Couche d'abstraction unique `core/llm_providers.py` pour les appels LLM directs.
Ajout de 2 nouveaux providers : Ollama (local) et Anthropic (Claude).
Suppression du code mort `core/services.py`.

**Pourquoi / Why:** 3 chemins d'appel LLM disperses dans le code. Cette phase les unifie
en un seul point d'entree `appeler_llm()` et ajoute le support Ollama (gratuit, local)
et Anthropic Claude (reformulation/restitution uniquement).

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `pyproject.toml` | Ajout dependance `anthropic>=0.40` |
| `core/models.py` | Provider +2 (OLLAMA, ANTHROPIC), AIModelChoices +9 modeles, champ `base_url`, prefix_to_provider etendu, tarifs |
| `core/llm_providers.py` | **Nouveau** — fonction unique `appeler_llm()` dispatche vers 5 providers |
| `core/migrations/0020_*.py` | **Nouveau** — migration auto (base_url + choices) |
| `front/tasks.py` | Supprime `_appeler_llm_reformulation()`, remplace par `appeler_llm()` |
| `hypostasis_extractor/services.py` | Ajout Ollama (model_url) et Anthropic (ValueError) dans `resolve_model_params()` |
| `core/services.py` | **Supprime** — code mort (dispatch legacy) |
| `front/tests/test_phases.py` | +10 tests unitaires PHASE-24 |
| `PLAN/PHASES/INDEX.md` | PHASE-24 cochee |

### Migration
- **Migration necessaire / Migration required:** Oui
- `uv run python manage.py migrate` — ajoute `base_url` sur `AIModel`, etend les choices

---

## 2026-03-11 — Corrections post-audit phases 1-6

- Renommage du skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + dossier `skills/`)
  / Renamed skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + `skills/` directory)
- Ajout attributs `aria-*` et `data-testid` dans les templates
  / Added `aria-*` and `data-testid` attributes in templates
- Mise a jour INDEX.md (phases 01-06 marquees completees)
  / Updated INDEX.md (phases 01-06 marked as completed)
- Creation de ce CHANGELOG
  / Created this CHANGELOG

**Fichiers modifies / Modified files:**
- `CLAUDE.md`
- `PLAN/PHASES/INDEX.md`
- `front/templates/front/base.html`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/templates/front/includes/panneau_analyse.html`
- `front/templates/front/includes/extraction_results.html`
- `front/templates/front/includes/extraction_manuelle_form.html`
- `front/templates/front/includes/lecture_principale.html`
- `skills/django-htmx-readable/` → `skills/stack-ccc/`
- `CHANGELOG.md` (nouveau / new)

**Migration** : non / no

---

## 2026-03-11 — PHASE-06 : Modeles de donnees (statut_debat + masquee)

- Ajout des champs `statut_debat` et `masquee` sur `ExtractedEntity`
  / Added `statut_debat` and `masquee` fields on `ExtractedEntity`

**Fichiers modifies / Modified files:**
- `hypostasis_extractor/models.py`
- `hypostasis_extractor/migrations/0018_extractedentity_masquee_extractedentity_statut_debat.py`

**Migration** : oui / yes

---

## 2026-03-11 — PHASE-05 : Extension navigateur robustesse

- Amelioration de la robustesse de l'extension navigateur (gestion d'erreurs, retry)
  / Improved browser extension robustness (error handling, retry)

**Fichiers modifies / Modified files:**
- `core/views.py`

**Migration** : non / no

---

## 2026-03-11 — PHASE-04 : CRUD manquants

- Ajout des operations CRUD manquantes (renommer/supprimer dossiers, supprimer pages, deplacer pages)
  / Added missing CRUD operations (rename/delete folders, delete pages, move pages)

**Fichiers modifies / Modified files:**
- `front/views.py`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/static/front/js/hypostasia.js`

**Migration** : non / no

---

## 2026-03-10 — PHASE-03 : Nettoyage code extraction

- Nettoyage et refactorisation du code d'extraction
  / Cleanup and refactoring of extraction code

**Migration** : non / no

---

## 2026-03-11 — PHASE-02 : Assets locaux (polices, CDN, collectstatic)

- Localisation des assets : Tailwind CSS, HTMX, SweetAlert2 en fichiers statiques
  / Localized assets: Tailwind CSS, HTMX, SweetAlert2 as static files
- Ajout des polices Lora (via Google Fonts, sera localise plus tard)
  / Added Lora fonts (via Google Fonts, to be localized later)

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/tailwind.css`
- `front/static/front/css/hypostasia.css`
- `front/static/front/vendor/htmx-2.0.4.min.js`
- `front/static/front/vendor/sweetalert2-11.min.js`

**Migration** : non / no

---

## 2026-03-11 — PHASE-01 : Extraction CSS/JS depuis base.html

- Extraction du CSS inline vers `hypostasia.css` et du JS inline vers `hypostasia.js`
  / Extracted inline CSS to `hypostasia.css` and inline JS to `hypostasia.js`
- Mise en place de la structure `front/static/front/`
  / Set up `front/static/front/` structure

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/hypostasia.css` (nouveau / new)
- `front/static/front/js/hypostasia.js` (nouveau / new)

**Migration** : non / no
