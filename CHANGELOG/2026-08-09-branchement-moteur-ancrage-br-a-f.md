# Branchement du moteur d'ancrage — phases BR-A à BR-F

**Date :** 2026-08-09 → 2026-08-10
**Migration :** Oui

## 2026-08-09 — Branchement du moteur d'ancrage, BR-A : le flag Page.moteur

**Quoi / What :** premiere phase du branchement (SPEC-ancrage v2 § 9,
cahier PLAN/branchement-moteur-ancrage-cahier-des-charges.md) :
- `Page.moteur` (ancien/element, defaut ancien, db_index) — un CHAMP
  explicite, decision D1 : le discriminant implicite elements.exists()
  prendrait une ingestion echouee pour une page ANCIEN.
- Migration core.0053 (appliquee sur dev) : schema + AUCUN estampillage
  — c'est un choix documente (§ 9.2) : tout l'existant reste ANCIEN,
  y compris les 537 pages/541 du dev decouvertes porteuses d'elements
  DORMANTS (phases de test du moteur). Les basculer serait changer le
  rendu du corpus entier d'un coup ; la reconversion est une decision
  explicite (§ 9.5), quasi gratuite le jour venu.
- Le flag ELEMENT est pose au point de passage unique de l'ingestion
  (creer_les_elements_d_une_page) — teste, y compris le cas D1 (page
  ELEMENT a zero element).
- Addendum date pose dans SPEC-ancrage-par-element-v2.md (D1-D2 +
  decouverte).

| Fichier | Changement |
|---|---|
| `core/models.py` | + MoteurDePage, + Page.moteur |
| `core/migrations/0053_page_moteur.py` | Schema + noop documente |
| `hypostasis_extractor/services/ingestion_docling.py` | Pose du flag |
| `core/tests/test_moteur_flag.py` | 5 tests |

Suite : BR-B (routage de l'import fichier vers l'ingestion Docling).

### Migration
- **Migration necessaire / Migration required :** Oui — core.0053
  (appliquee sur dev).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-B : l'import de fichier nourrit le moteur ELEMENT

**Quoi / What :** quand un fichier importe est d'un type que Docling
sait convertir (`.pdf`, `.docx`, `.md`, `.pptx`, `.xlsx`), la vue
d'import lance desormais `ingerer_un_fichier_avec_docling` en
arriere-plan, EN PLUS du pipeline synchrone existant. C'est la premiere
vraie bascule de flux du § 9 : les nouvelles pages couvertes deviennent
ELEMENT (le flag est pose par la tache, mecanique BR-A).
/ Covered file imports now ALSO launch Docling element ingestion in the
background — the first real flow switch of § 9.

**Decision de transition (double ecriture)** : le pipeline synchrone
continue de remplir `html_readability` — l'AFFICHAGE reste celui de
l'ancien moteur jusqu'a BR-D (`rendu_elements` n'a pas encore
d'appelant). Aucune regression visible ; les elements s'accumulent en
attendant leur ecran. Le `.txt` (sans structure) et le `.json` de
transcription restent entierement sur leurs pipelines d'origine, et le
toast le dit honnetement : « Fichier importé — découpage en éléments
lancé » seulement quand c'est vrai.

**Verifie en reel** : import d'un `.md` par la vraie vue, ingestion par
le vrai worker Celery (meme conteneur, chemin `source_file.path`
partage) — page 674, 4 elements, `moteur=element`, premiere page
ELEMENT nee du flux reel en dev. Pas de course delay/commit
(autocommit, pas d'ATOMIC_REQUESTS) ; les e2e (eager) n'uploadent que
du `.txt`, donc aucun Docling synchrone dans les suites.

**Relecture adverse (7 défauts, tous traités le soir même)** :
1. HAUTE — aucun garde-fou de ressources : conversion bornée
   (`max_num_pages=200`, `max_file_size=50 Mo` — un `.docx` est un zip,
   la limite d'upload porte sur la taille compressée) et **file Celery
   dédiée `ingestion_docling` à concurrence 1** (task_routes +
   programme supervisord `celery_worker_docling` ; redémarrage du
   conteneur requis pour l'activer) — jamais deux Docling en même temps
   sur l'hôte 8 Go partagé avec la prod.
2. Broker en panne : `.delay` encadré, l'import reste un succès (page
   ANCIEN lisible), toast sans fausse promesse.
3. Échec d'ingestion silencieux : assumé et consigné (pas de surface UI
   avant BR-D/E — fiche A TESTER + § 5 du cahier).
4. Fenêtre BR-B→BR-D (analyse ANCIEN payée sur page ELEMENT →
   extractions sans portions) : dette écrite au § 5 du cahier, à
   trancher à BR-C.
5. La vue ne passe plus que `page.pk` : la tâche résout le chemin
   depuis `source_file` (découplage du stockage).
6. Tests renforcés : `.docx` réel (binaire), conversion en échec →
   Docling jamais lancé, media de test nettoyé.
7. Toast double : timer paramétrable (`showToast.timer`), 4,5 s pour ce
   message (public FALC).

Tests : `front.tests.test_import_docling` (8) +
`hypostasis_extractor.tests.test_tasks_element` (3 nouveaux) +
`hypostasis_extractor.tests.test_ingestion_docling` (3 nouveaux), TDD
RED→GREEN — 46 verts au total sur le périmètre.
Fichiers : `hypostasis_extractor/services/ingestion_docling.py`,
`hypostasis_extractor/tasks_element.py`, `front/views.py`,
`hypostasia/celery.py`, `supervisord.conf`,
`front/static/front/js/hypostasia.js`.

Suite : BR-C (routage de l'analyse pour les pages ELEMENT).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-C : l'analyse route selon le moteur

**Quoi / What :** le bouton « analyser » lance desormais
`analyser_une_page_avec_le_moteur_element` (ancres par PORTIONS) quand
`page.moteur == element`, et `analyser_page_task` (offsets) sinon.
Meme ExtractionJob, meme toast : le moteur est un detail
d'implementation pour la personne qui lit.
/ The "analyse" button now routes by the page's engine flag.

**M6 tranché — coexistence des jobs** : la relance ne purge pas les
jobs precedents (meme semantique que l'ancien moteur) ; la promesse
§ 4.2 de SPEC-synthese est tenue par les gardes deja en place
(`nettoyer_ia` refuse AVANT purge et AVANT l'appel LLM ; le chemin
ELEMENT porte sa garde interne). Ecarts § 4.2 assumes par addendum
date (pas de compteur de tokens, boucle sequentielle — une vertu sur
8 Go —, `suppress_parse_errors`).

**Verifie en reel** : job 938 sur la page 674 (ELEMENT) —
`raw_result.moteur='element'`, 1 chunk, LLM reel, 2,9 s, zero erreur.
La fenetre « analyse ANCIEN sur page ELEMENT » (relecture BR-B, defaut
n°4) s'est refermee avant toute analyse reelle.

Tests : `front.tests.test_analyse_routage` (2, TDD RED→GREEN).
Fichiers : `front/views.py` (action `analyser`).

Suite : BR-D (affichage par elements dans lecture_principale).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-D : la lecture rend les elements

**Quoi / What :** une page ELEMENT est desormais AFFICHEE depuis ses
ElementDocument — titres, paragraphes, listes regroupees, chaque
portion d'extraction marquee `mark.portion.hl-extraction` sur SON
passage exact (`front/services/rendu_elements.py`, ecrit en phase G,
enfin branche). Une page ANCIEN, ou une page ELEMENT a zero element
(ingestion echouee), retombe sur `html_annote`/`html_readability`
comme avant — jamais de page blanche.
/ ELEMENT pages now render from their elements with per-portion marks;
OLD pages are untouched.

**Le branchement passe par un tag de template**
(`front/templatetags/rendu_moteur.py`), pas par les contextes de vue :
lecture_principale.html est rendu depuis PLUS DE SIX endroits, et
injecter `blocs_de_lecture` dans chacun garantissait l'oubli — le meme
piege que corpus_permissions avait resolu pour est_proprietaire. Les
elements MASQUES ne sont pas rendus (leur gestion arrive avec BR-E).

**Relecture BR-C appliquee dans la foulee (3 correctifs testes)** :
1. HAUTE — battement de coeur par chunk dans l'analyse ELEMENT
   (`analyse_par_element.py`) + le juge de blocage distingue un job
   PENDING en file (tolere 90 min, plafond de la garde d'edition) d'un
   PROCESSING fige (5 min sans battement = mort) : fini les faux
   « Timeout » qui relancaient des analyses en double.
2. MOYENNE — `analyser_page_task` revalide le moteur A L'EXECUTION et
   delegue au moteur ELEMENT si la page a bascule entre le clic et
   l'execution (course avec l'ingestion Docling) : jamais
   d'extractions a offsets sans portions sur une page ELEMENT.
3. Consignes au § 5 du cahier (pas de code) : ordre des cartes du
   panneau encore par start_char (entrelace pour ELEMENT — cosmetique),
   drawer d'estimation chunke encore a l'ancienne, anti-doublon sans
   verrou sur double-clic rapide (preexistant, attenue par la
   transition atomique de la tache ELEMENT).

**Collisions de tests entre sessions resolues** :
`hypostasia/settings_test_fable.py` donne a cette session sa base de
test dediee (`test_hypostasia_fable`) — les runs paralleles des deux
sessions ne se detruisent plus (« database test_hypostasia does not
exist », deadlocks : c'etait ca).

Tests : `front.tests.test_lecture_elements` (5) +
`front.tests.test_analyse_routage` (9 au total) + battement de coeur
(`test_analyse_par_element.BattementDeCoeurTest`) — TDD RED→GREEN ;
`front.tests.test_phases` : 543 verts (non-regression totale).
Fichiers : `front/templatetags/rendu_moteur.py` (nouveau),
`front/templates/front/includes/_blocs_elements.html` (nouveau),
`lecture_principale.html`, `front/views.py`, `front/tasks.py`,
`hypostasis_extractor/services/analyse_par_element.py`,
`hypostasia/settings_test_fable.py` (nouveau).

Suite : BR-E (ElementViewSet : corriger, scinder, fusionner, masquer —
avec le verrou ElementDocument).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-E : les operations sur un element ont leurs endpoints

**Quoi / What :** nouveau `ElementViewSet`
(`hypostasis_extractor/views_element.py`, routes `/elements/<pk>/...`) :
`corriger` (texte + reconciliation des portions + journal PageEdit),
`scinder`, `fusionner_avec_le_suivant`, `masquer`, `demasquer` — un
serializer par action (convention du depot). Les GARDES des services
(analyse en cours, synthese figee qui cite) remontent en **409 avec
leur message FALC** ; les entrees invalides en 400 ; un tiers sans
droit d'ecriture en 403 (meme regle que la lecture :
`_utilisateur_peut_ecrire_page`, import paresseux anti-cycle).
/ Element operation endpoints; service guards surface as 409 FALC.

**Le verrou § 7 est POSE** (defaut de concurrence consigne le 8 aout) :
chaque action ouvre une transaction et `select_for_update()` la ou les
lignes ElementDocument AVANT d'appeler le service — la fusion
verrouille les DEUX voisins. Reponses : 200 + HX-Trigger
{showToast, lectureReload} — le front recharge la lecture, qui re-rend
les blocs BR-D. Pas d'UI dediee encore (boutons a venir avec BR-F/G).

**Verification visuelle BR-D (agent maquette, Chromium reel)** — 2
defauts HAUTE decouverts et corriges dans la foulee : le passage
`span`→`mark` reveillait les DEFAUTS NAVIGATEUR de `<mark>` — texte
MarkText noir dur (1,28:1 en mode sombre) et fond jaune fluo pour tout
statut sans regle CSS, dont `non_pertinent` (4 182 extractions en
base). Correctif : reset `mark.hl-extraction` dans maquette.css,
specificite (0,1,1) calculee pour perdre contre les fonds par statut.
Conformes par ailleurs : structure des blocs, typographie identique a
la zone de lecture, 4 marques sur les bonnes portions a travers
h2/p/li/h3, zero regression sur l'ancien rendu (verifie sur 2 pages
temoins, clair et sombre), zero erreur console. Ecart de parti pris
consigne : surlignage permanent (choix T7) la ou l'etalon revele au
survol — a trancher plus tard.

Tests : `hypostasis_extractor.tests.test_views_element` (14) + verrou
CSS dans test_lecture_elements — TDD RED→GREEN, 40 verts sur le
perimetre BR. Fichiers : `hypostasis_extractor/views_element.py`
(nouveau), `hypostasis_extractor/serializers.py` (3 serializers),
`front/urls.py`, `front/static/front/css/maquette.css`.

Suite : BR-F (fixtures representatives + parcours e2e ELEMENT).

## 2026-08-10 — Branchement du moteur d'ancrage, BR-F : fixtures representatives et parcours e2e — LE BRANCHEMENT BR-A→F EST COMPLET

**Quoi / What :** fixtures § 9.4 versionnees
(`hypostasis_extractor/tests/fixtures/` : pad markdown structure,
texte brut temoin du repli) + tests de conversion REELLE par Docling
(pad → title/section_header/list_item/chemins de section ; docx avec
TABLEAU fabrique par python-docx → element `table` au contenu
ancrable). Opt-in : `TESTS_DOCLING=1` + `--tag=docling` — jamais dans
une suite ordinaire (8 Go). Et le parcours E2E complet au navigateur
(`front/tests/e2e/test_23_moteur_element.py`) : import d'un `.md` par
le bouton reel → ingestion eager → la note rouverte se lit par BLOCS
(h2/h3/p/ul-li, `data-testid="blocs-elements"`), 8,6 s.
/ Representative fixtures + real-Docling conversion tests (opt-in) +
the full browser journey.

**Decouverte consignee (le role meme des fixtures)** : le backend
markdown de Docling traite chaque LIGNE source comme un element — un
paragraphe a retours a la ligne durs se fragmente (« l'ete. » devient
un element), et une puce continuee sur deux lignes perd son label
`list_item`. Reel documente dans le test, pas corrige : les pads reels
s'ecrivent sans retour dur ; a reevaluer si la recette montre une gene.

**Relecture adverse BR-E appliquee (9 defauts, 5 corriges + tests)** :
1. HAUTE — deux scissions simultanees sur la MEME page se percutaient
   au commit (renumerotation page-entiere + contrainte d'ordre
   DEFERRED → IntegrityError → 500) : les operations de STRUCTURE
   (scinder, fusionner) posent desormais le verrou de PAGE avant tout ;
   corriger/masquer restent au verrou de ligne.
2. La justification > 500 caracteres etait AVALEE en silence
   (is_valid sans controle) : refusee en 400 desormais, partout.
3. La justification de scinder/fusionner passait en brut (un dict JSON
   → 500 psycopg) : serializers partout, convention respectee.
4. Les toasts 409 montraient les messages internes des exceptions
   (pk, « job(s) », moitie anglaise) : messages FALC dedies — celui de
   la synthese NOMME toujours la synthese bloquante (§ 5.3).
5. Corriger sans changement polluait PageEdit : no-op propre + toast
   « Aucun changement » ; le journal porte l'identifiant STABLE (l'ordre
   est renumerote par les scissions).
Consignes sans code (BASSE, § 5 du cahier) : verrou avant controle de
droit (oracle d'existence conforme au reste du depot), messages de
course fusion/scission perfectibles, error_messages morts des
serializers.

Tests : 18 verts sur test_views_element (5 nouveaux TDD RED→GREEN),
fixtures 4 + 2 docling reels, e2e 1.

**Le § 9 de la spec est tenu de bout en bout** : import → ingestion
Docling (file dediee, bornee) → flag ELEMENT → analyse par elements
(LLM reel verifie) → lecture par blocs marques par portion (verifiee
au navigateur, clair/sombre) → operations d'element sous verrou et
gardes. L'existant ANCIEN n'a pas bouge (543 test_phases verts).
Restent, hors perimetre du branchement : BR-G (visualiseur PDF,
curseur audio — a cadrer separement), la bascule de la capture web et
de l'audio (D2), la reconversion explicite § 9.5.

---

> **Mise à jour du 10 août (nuit) : le branchement BR-A→F est COMPLET.**
> Les sections BR-C à BR-F sont documentées à la fin de cette fiche.

> Écrit le 9 août 2026 (nuit). Réfère : SPEC-ancrage-par-element-v2.md § 9,
> PLAN/branchement-moteur-ancrage-cahier-des-charges.md, CHANGELOG du 9 août.

## Ce qui a été livré

### BR-A — le flag moteur (`Page.moteur`)

- Champ explicite `moteur` sur Page : `ancien` (défaut) ou `element`,
  migration `core/0053_page_moteur.py` **appliquée sur dev**.
- Décision § 9.2 confirmée après découverte : **537 des 541 pages du dev
  portent des éléments DORMANTS** (ingérés par les phases de test du
  moteur, jamais lus par le flux réel). Elles restent TOUTES `ancien` —
  la migration n'estampille rien, c'est un choix documenté dans son
  docstring. La bascule de l'existant sera une reconversion explicite
  (§ 9.5, décision D4, hors périmètre).
- Le flag `element` est posé au point de passage unique :
  `creer_les_elements_d_une_page` (ingestion_docling.py).

### BR-B — l'import de fichier nourrit le moteur ELEMENT

- Types couverts par Docling : `.pdf`, `.docx`, `.md`, `.pptx`, `.xlsx`
  (`fichier_couvert_par_docling`, ingestion_docling.py).
- Pour un type couvert, `_importer_fichier_document` (front/views.py)
  lance `ingerer_un_fichier_avec_docling` en arrière-plan **en plus** du
  pipeline synchrone : `html_readability` continue d'être rempli,
  l'affichage reste celui de l'ancien moteur jusqu'à BR-D (double
  écriture de transition). Toast honnête : « Fichier importé —
  découpage en éléments lancé ».
- `.txt` (pas de structure) et `.json` (pipeline transcription) :
  repli intégral sur l'ancien comportement, toast inchangé.

## À tester à la main

1. **Import d'un `.md` ou `.docx`** (connecté) : la note s'affiche
   immédiatement (pipeline synchrone), le toast mentionne le découpage.
   Quelques secondes plus tard (≈45 s au premier import après un
   redémarrage : chargement de Docling dans le worker), en admin ou en
   shell : `page.moteur == "element"` et `page.elements.count() > 0`.
2. **Import d'un `.txt`** : toast simple « Fichier importé », la page
   reste `moteur=ancien`, zéro élément.
3. **Vérifier l'affichage** : la note importée se lit normalement —
   rien ne doit changer visuellement avant BR-D.
4. **Analyse d'une page fraîchement importée** : elle passe encore par
   l'ancien moteur (le routage de l'analyse est BR-C) — vérifier que
   les extractions fonctionnent comme avant.

## Preuves déjà faites

- 10 tests unitaires verts : `core.tests.test_moteur_flag` (5) et
  `front.tests.test_import_docling` (5), TDD RED→GREEN.
- Recette réelle sur dev : import `.md` par la vraie vue, ingestion par
  le vrai worker — **page 674**, 4 éléments (title, text, 2 list_item),
  `moteur=element`. Première page ELEMENT née du flux réel.

## Correctifs de la relecture adverse (appliqués, testés)

- **Gardes-fous de ressources** : conversion bornée
  (`max_num_pages=200`, `max_file_size=50 Mo` passés à Docling) et
  **file Celery dédiée `ingestion_docling` à concurrence 1** (nouveau
  programme `celery_worker_docling` dans supervisord.conf — nécessite
  un redémarrage du conteneur) : jamais deux conversions en même temps
  sur l'hôte 8 Go partagé avec la prod.
- **Broker en panne** : `.delay` encadré — l'import reste un succès
  (page ANCIEN lisible), toast sans promesse de découpage, erreur au
  journal.
- **Découplage stockage** : la vue ne passe que `page.pk`, la tâche
  résout le chemin depuis `source_file` (et refuse proprement une page
  sans fichier ou un stockage sans chemin local).
- **Toast FALC** : le message double « Fichier importé — découpage en
  éléments lancé » s'affiche 4,5 s (timer paramétrable dans
  `showToast`).
- Tests ajoutés : `.docx` réel (binaire), broker en panne, conversion
  synchrone en échec (verrouille que Docling n'est jamais lancé sur un
  fichier rejeté), résolution du chemin, limites, route de queue.

## Points de vigilance

- L'ingestion qui ÉCHOUE laisse la page en `ancien`, lisible (le
  pipeline synchrone a rempli le HTML) — dégradation SILENCIEUSE :
  aucun objet de suivi, le bouton « tâches » ne liste que les jobs,
  et **aucune relance manuelle n'existe encore**. Surface UI et relance
  à livrer avec BR-D/BR-E ; en attendant, le journal Celery fait foi.
- **Fenêtre BR-B→BR-D** : analyser une page fraîchement importée passe
  encore par l'ancien moteur — extractions en offsets, sans portions,
  qui ne survivront pas à la bascule d'affichage BR-D (risque consigné
  au § 5 du cahier, à trancher à BR-C).
- La reconversion des 537 pages dormantes reste une décision explicite
  du propriétaire (§ 9.5) — carnet par carnet, quasi gratuite.
- Suite : BR-C (routage de l'analyse), BR-D (affichage rendu_elements).

---

# Phases BR-C à BR-F (nuit du 9 au 10 août)

## Ce qui a été livré

- **BR-C — analyse routée** : le bouton « analyser » lance le moteur
  ELEMENT pour une page ELEMENT (même job, même toast). La tâche
  ancienne REVALIDE le moteur à l'exécution (course avec l'ingestion).
  Battement de cœur par chunk ; un job PENDING en file n'est plus tué
  à 5 min (tolérance 90 min).
- **BR-D — lecture par blocs** : une page ELEMENT s'affiche depuis ses
  éléments (h2/h3/p/listes), chaque portion marquée
  `mark.portion.hl-extraction` sur son passage exact. Repli
  readability si zéro élément. Vérifiée AU NAVIGATEUR (clair + sombre,
  contrastes ≥ 13:1 après correctif `mark`).
- **BR-E — endpoints élément** : `/elements/<pk>/corriger|scinder|
  fusionner_avec_le_suivant|masquer|demasquer`. Verrou de PAGE pour
  les opérations de structure, verrou de ligne sinon ; gardes en 409
  FALC nommant la synthèse bloquante ; journal PageEdit avec
  identifiant stable. PAS ENCORE DE BOUTONS dans l'interface (BR-G).
- **BR-F — fixtures et e2e** : conversions réelles opt-in
  (`docker exec -e TESTS_DOCLING=1 … --tag=docling`) et parcours
  navigateur complet (`front.tests.e2e.test_23_moteur_element`).

## À tester à la main

1. Importer un `.md` structuré (titres, puces) : après quelques
   secondes, la note se lit en BLOCS (inspecter :
   `data-testid="blocs-elements"`). La relire, l'analyser : les
   surlignages tombent sur les passages exacts, y compris dans les
   titres et les puces.
2. Vérifier le MODE SOMBRE d'une note ELEMENT analysée : texte des
   surlignages lisible, pas de jaune fluo.
3. Tester les endpoints élément au curl/HTMX (pas encore de boutons) :
   corriger un texte → toast + la lecture se recharge ; scinder ;
   masquer/démasquer. Vérifier le 409 FALC pendant une analyse.
4. Vérifier qu'une note ANCIENNE (tout le corpus existant) se lit et
   s'analyse exactement comme avant.

## Dettes et limites consignées (§ 5 du cahier pour le détail)

- Échec d'ingestion silencieux (pas de surface UI ni relance — BR-G).
- Cartes du panneau triées par offsets de chunk pour ELEMENT
  (entrelacement cosmétique) ; estimation du drawer à l'ancienne.
- Docling md : paragraphes à retours durs fragmentés, puce sur deux
  lignes perd son label (documenté dans les fixtures).
- Boutons d'interface des opérations d'élément : à livrer avec BR-G,
  sur le design maquette.

