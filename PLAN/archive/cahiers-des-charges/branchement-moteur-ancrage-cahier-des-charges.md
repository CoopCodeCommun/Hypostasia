# Branchement du moteur d'ancrage par élément — cahier des charges

**Préparé le 9 août 2026 (nuit)** pour la session qui suivra la fin de
la bascule CSS. Chantier BACK (Fable : des décisions vont surgir).
Sources : SPEC-ancrage-par-element-v2.md (§ 9, § 11, § 12),
mémoire `etat-moteur-ancrage-verifie` (vérification exhaustive du
8 août), CHANGELOG des 8-9 août (couche synthèse A-I).

## 1. Objet

Faire du moteur ÉLÉMENT (phases A-G, écrites et testées) le moteur
RÉEL des nouvelles pages : aujourd'hui aucune tâche n'est appelée hors
tests, tout le flux passe par l'ancien moteur (`analyser_page_task`,
offsets plats), et `front/services/rendu_elements.py` (écrit, 20
tests) n'a aucun appelant. Le § 9 de la spec impose la stratégie :
**double moteur, données vierges** — les pages existantes restent
ANCIEN et continuent de fonctionner ; toute NOUVELLE page passe par
ÉLÉMENT ; jamais de migration de données de force.

## 2. Ce qui s'active tout seul au branchement (déjà livré)

- **Le gel § 5 de la couche synthèse devient EFFECTIF** : les cinq
  gardes de la phase E (réconciliation, masquage, scission, fusion,
  réingestion) ne protègent aujourd'hui que des chemins sans appelant.
  Décision du propriétaire (question n°5 de SPEC-synthese) : le gel
  est livré AVEC le branchement. C'est l'enjeu de gouvernance n°1.
- La **couverture § 9** devient riche (elle est déjà exacte sur les
  pages à éléments) et le **verbatim § 7** dérive moins (ancres
  réconciliées au lieu d'offsets périmés — les 6/8 « faibles » de la
  démo viennent en partie de là).
- Le **panneau de preuve** peut pointer la portion exacte
  (`ancrage_source` est déjà rempli par l'indexation quand il existe).

## 3. Décisions à trancher AVANT de coder (avec le propriétaire)

| # | Décision | Options / recommandation |
|---|---|---|
| D1 | **Flag moteur explicite ou discriminant implicite** (`page.elements.exists()` actuel) | Recommandé : champ `Page.moteur` (choices ANCIEN/ELEMENT, défaut ANCIEN, migration une-ligne) — la spec § 9.2 le prévoit ; l'implicite casse sur une page ÉLÉMENT à 0 élément (ingestion échouée) |
| D2 | **Quels flux basculent, dans quel ordre** | Recommandé : 1) import FICHIER (docling est fait pour ça) ; 2) capture web/extension (HTML → éléments) ; 3) AUDIO en dernier (dépend de Q1 spec : frontière préférentielle non mesurée sur vraie transcription diarisée) |
| D3 | **La question n°1 de la spec** (frontière audio) | À mesurer sur une vraie transcription de la base dev avant la bascule audio — livrable : une mesure, pas une opinion |
| D4 | **`reconvertir_avec_docling`** (pages ANCIEN → ÉLÉMENT à la demande, § 9.5) | Hors périmètre du branchement initial — consigner, ne pas coder |
| D5 | **RGPD/purge réelle** (question n°3 spec) | Décision produit séparée — ne pas bloquer |

## 4. Phases proposées

| Phase | Contenu | Notes |
|---|---|---|
| BR-A | **FAITE (9 août, nuit)** : `Page.moteur` (migration 0053, appliquée), existant TOUT ANCIEN (§ 9.2 — décision confirmée après découverte de 537/541 pages aux éléments DORMANTS en dev), flag posé par `creer_les_elements_d_une_page`. 5 tests. | La reconversion des 537 sera quasi gratuite (§ 9.5) mais explicite |
| BR-B | **FAITE (9 août, nuit)** : types couverts (`.pdf .docx .md .pptx .xlsx`) → `ingerer_un_fichier_avec_docling` lancée en arrière-plan EN PLUS du pipeline synchrone (double écriture : l'affichage reste ANCIEN jusqu'à BR-D) ; `.txt` = repli ANCIEN, toast honnête. 5 tests (`front.tests.test_import_docling`) + recette réelle (page 674, 4 éléments, `moteur=element`) | Hypothèses vérifiées : worker Celery dans le même conteneur, pas d'ATOMIC_REQUESTS (pas de course delay/commit), e2e eager sains (.txt seulement) |
| BR-C | **FAITE (9 août, nuit)** : `analyser` route selon `page.moteur` (même job, même toast). M6 tranché : coexistence des jobs, promesse § 4.2 tenue par les gardes existantes (nettoyer_ia AVANT purge et AVANT LLM ; garde interne du chemin ELEMENT). Écarts § 4.2 assumés par addendum (tokens, séquentiel = vertu 8 Go, suppress_parse_errors). 2 tests + recette réelle (job 938, LLM réel, `raw_result.moteur='element'`) | La fenêtre BR-B→BR-C s'est refermée avant toute analyse réelle : aucun job d'offsets sur page ELEMENT |
| BR-D | **FAITE (9 août, nuit)** : templatetag `blocs_de_lecture_de` (rendu_moteur.py) appelé DANS lecture_principale.html (6+ contextes de rendu couverts d'un coup, pattern corpus_permissions) → partial `_blocs_elements.html` (balises par label, listes regroupées, `mark.portion.hl-extraction` par portion, masqués non rendus). Zéro bloc → repli html_annote/readability. 5 tests + 543 test_phases verts | Éléments masqués : gestion UI à BR-E. Ordre des cartes du panneau et estimation : voir § 5 |
| BR-E | **FAITE (10 août, nuit)** : `ElementViewSet` (`hypostasis_extractor/views_element.py`, routes `/elements/<pk>/…`) — corriger (réconciliation + PageEdit), scinder, fusionner_avec_le_suivant, masquer, demasquer ; un serializer par action ; gardes en 409 FALC, verrou `select_for_update` posé partout (fusion : les DEUX lignes). 14 tests. Réponses 200 + lectureReload (le front recharge les blocs BR-D) | UI (boutons) à livrer avec BR-F/G ; vérif visuelle BR-D faite (2 défauts HAUTE `<mark>` corrigés : MarkText noir, fond Mark fluo sur non_pertinent) |
| BR-F | **FAITE (10 août, nuit)** : fixtures versionnées (`hypostasis_extractor/tests/fixtures/` : pad markdown, texte brut) + conversions RÉELLES Docling opt-in (`TESTS_DOCLING=1 --tag=docling` : pad structuré, docx à tableau fabriqué par python-docx) + parcours e2e navigateur complet (`e2e/test_23_moteur_element.py`, import → blocs, 8,6 s). Découverte consignée : le backend md de Docling fragmente les paragraphes à retour dur (puce sur 2 lignes perd list_item) | PDF à tableaux → BR-G ; verbatim diarisé → bascule audio (D2). Relecture BR-E appliquée (verrou de page pour la structure + 4 correctifs) |
| BR-G | Phases I/J spec (visualiseur PDF PDF.js, curseur audio) | GROS morceau UI — à cadrer séparément après BR-A→F, sur le design maquette |

**M6 à solder en BR-C** : la promesse § 4.2 synthèse (« une note citée
par une dirigée ne se ré-analyse pas ») — décider si la relance
d'analyse ELEMENT purge l'ancien job (alors la garde § 4.2 refuse
proprement AVANT l'appel LLM) ou coexiste (alors documenter que la
promesse ne vaut que pour le moteur ELEMENT).

## 5. Risques connus (consignés les 8-9 août)

- **Fenêtre transitionnelle BR-B→BR-D (relecture BR-B, défaut n°4)** :
  une page importée aujourd'hui devient ELEMENT, mais le bouton
  « analyser » route encore vers l'ancien moteur (BR-C) et l'affichage
  vers `html_readability` (BR-D). Une analyse payée dans cette fenêtre
  produit des extractions en offsets, SANS portions : à la bascule
  d'affichage BR-D, elles ne seront pas rendues par
  `construire_les_blocs_de_lecture`, et BR-C relancera une analyse
  ELEMENT payante en doublon. À trancher à BR-C : fenêtre assumée et
  documentée, ou réconciliation des anciens jobs à la bascule.
- **Restes cosmétiques ELEMENT (relecture BR-C, défauts n°3-5, consignés le 9 août)** :
  les cartes du panneau d'analyse sont encore triées par `start_char`
  (offsets de chunk pour ELEMENT → entrelacement entre chunks ; le
  scroll-vers-la-marque, lui, marche par `data-extraction-id`) ; le
  drawer d'estimation chunke `text_readability` à l'ancienne (coût du
  bon ordre de grandeur, nombre de chunks approximatif pour ELEMENT) ;
  l'anti-doublon de la vue ne survit pas à un double-clic plus rapide
  que la création du job (préexistant, atténué par la transition
  atomique PENDING→PROCESSING de la tâche ELEMENT). À solder avec
  BR-E/BR-F.
- **Échec d'ingestion silencieux (relecture BR-B, défaut n°3)** : si
  Docling échoue, la page reste ANCIEN et lisible, mais rien ne le dit
  à l'utilisateur (pas d'objet de suivi, le bouton « tâches » ne liste
  que les jobs) et aucune relance manuelle n'existe. Surface UI et
  relance à livrer avec BR-D/BR-E ; en attendant, le journal Celery
  fait foi.

- Verrou de concurrence scission/fusion : les portions sont
  verrouillées, pas la ligne ElementDocument — la vue DOIT poser le
  verrou (mémoire du 8 août).
- `rendu_elements.py` : jamais vu la production — le brancher est un
  vrai test ; prévoir la comparaison au rendu ancien sur les mêmes
  contenus.
- Les e2e existants et `front/utils.py` (pont texte↔HTML 504 lignes,
  double moteur § 9 spec) restent INTOUCHÉS : l'ANCIEN doit continuer
  de fonctionner à l'identique — c'est le contrat du double moteur.
- 8 Go : ingestion docling + LLM = lourd ; un seul run à la fois.

## 6. Méthode

TDD strict (RED d'abord), relecture adverse par agent à chaque phase,
messages FALC, agents maquette pour BR-D/BR-G (un navigateur à la
fois), CHANGELOG + fiche « A TESTER » par phase, addendum daté de la
spec ancrage pour tout écart tranché, jamais de commit. Migrations
appliquées sur dev au fil de l'eau.
