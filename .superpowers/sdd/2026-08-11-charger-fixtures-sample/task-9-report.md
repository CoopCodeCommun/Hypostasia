# Rapport — Tâche 9 : charger le PDF et créer la base de démonstration

## Ce qui a été fait

Suivi de la méthode TDD imposée : tests d'abord (échec confirmé), puis
implémentation, puis tests devenus faux repris.

### `front/management/commands/charger_fixtures_sample.py`

- `EXTENSIONS_REFUSEES` réduit à `{".docx"}` (commentaire réécrit :
  pourquoi le PDF en sort — mesure du 11 août, référence au benchmark —
  et pourquoi le docx y reste — le seul exemplaire du dépôt ne produit
  aucun élément).
- Message de `CommandError` réécrit pour ne parler que du docx.
- `FICHIER_DU_PDF = "Etude_Epistemologique_IA.pdf"` ajouté à
  `DOCUMENTS_ETALONS`, **en dernier** (le plus coûteux des cinq).
- `_charger_le_pdf(proprietaire, carnet_des_etalons)` : patron exact de
  `_charger_le_markdown`, avec `read_bytes()` (binaire),
  `text_readability=""`, et une ligne de bilan qui annonce le coût
  (~98 s, ~2 Gio) **avant** de lancer Docling.
- `NOM_DE_LA_BASE_DE_DEMONSTRATION = "Démonstration"` et
  `SLUG_DE_LA_BASE_DE_DEMONSTRATION = "demonstration"` (slug posé
  explicitement, jamais généré).
- `_creer_la_base_de_demonstration(proprietaire, carnet_des_etalons)` :
  `get_or_create` sur `nom` avec `slug` dans les `defaults`, puis
  `AppartenanceDossierBase.objects.get_or_create` — même patron que
  `front/views_corpus.py:1176`. Rien n'est créé en `--a-blanc`.
- `handle()` appelle `_creer_la_base_de_demonstration` après
  `_charger_les_documents`.
- Docstring de module et `help` de la commande mis à jour (cinq
  documents, docx seul refusé).

### `front/tests/test_charger_fixtures_sample.py`

- Ajout de `PdfEtBaseDeDemonstrationTest` (5 tests, du brief à la
  lettre) : chargement par défaut du PDF, refus persistant du docx,
  rattachement à la base « Démonstration », non-duplication de la base
  au second lancement, aucune base créée en `--a-blanc`.

### `hypostasis_extractor/tests/test_fixtures_representatives.py`

- Ajout de `PdfEtalonTest` (taggée `docling`,
  `@unittest.skipUnless(DOCLING_DEMANDE, ...)`), verrouillant : 11
  éléments, 2 `table`, 11/11 éléments avec `provenance["page_no"]` et
  `provenance["boites"]` non vide, pages 1 à 3.

### `docs/superpowers/specs/2026-08-11-fixtures-sample-design.md`

- Addendum n°2 ajouté en fin de document (le § 3.5 n'est **pas**
  réécrit) : renversement de la décision, tableau de mesure, ce qui a
  changé dans la commande, liste des tests repris.

## Tests existants devenus faux — repris, pas ajustés en silence

C'est un vrai changement de comportement, pas un détail :

- **`RefusDesFormatsLourdsTest.test_un_pdf_est_refuse_sans_conversion`**
  affirmait l'inverse de la nouvelle règle (le PDF y était refusé). Il
  devient **`test_un_docx_est_refuse_sans_conversion`** : même structure
  de test (mock de la tâche fichier, `assertRaises(CommandError)`,
  `assert_not_called()`), mais sur `présentation des open badges.docx`
  au lieu du PDF.
- Comptes de pages `--sans-mp3` passés de **3 à 4** partout où le mock
  `ingerer_un_fichier_avec_docling.apply` (partagé par le markdown ET,
  désormais, le PDF) est utilisé sans `--fichier` restrictif :
  - `DocumentsEcritsTest.test_les_deux_notes_sont_rangees_dans_le_carnet`
  - `DocumentsEcritsTest.test_relancer_ne_double_rien_et_ne_reconvertit_pas`
    (le compte d'appels du mock fichier passe aussi de 1 à 2 — un appel
    pour le markdown, un pour le PDF)
  - `EntreesAudioTest.test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge`
  - `RattrapageDesNotesSansElementTest.test_une_note_avec_ses_elements_est_bien_sautee`
  - `ReinitialisationTest.test_reset_supprime_les_notes_et_les_recharge`
    (deux assertions : nombre de pages avant reset, nombre après)
  - `BilanDeSortieTest.test_le_bilan_compte_les_notes_sautees` (« Notes
    sautées : 3 » → « Notes sautées : 4 » au second chargement)

Chaque bascule est commentée en français/anglais dans le test lui-même,
expliquant que le PDF partage le même mock que le markdown.

## Sortie des tests

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample \
    hypostasis_extractor.tests.test_fixtures_representatives \
    --noinput --settings=hypostasia.settings_test_opus

Ran 49 tests in 11.566s
OK (skipped=5)
```

Conversion Docling réelle (taggée `docling`, isolée, une seule
conversion à la fois, mémoire vérifiée avant — 18 Gio disponibles) :

```
docker exec -w /app -e TESTS_DOCLING=1 hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_fixtures_representatives.PdfEtalonTest \
    --noinput --settings=hypostasia.settings_test_opus --tag=docling

Ran 1 test in 90.149s
OK
```

Le compte mesuré par cette conversion réelle **correspond exactement**
à celui annoncé par le brief : 11 éléments, 2 `table`, 11 boîtes sur 11
éléments, pages {1, 2, 3}. Aucun ajustement n'a été nécessaire.

## Commande réelle (étape 8)

```
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --reset
```

Bilan obtenu :

```
Propriétaire        : jonas (réutilisé)
Réinitialisation    : 4 note(s) supprimée(s), carnet supprimé
Carnet              : Documents étalons — pk=2 (créé)
Transcription       : Voxtral Mini (réutilisée)
Capture web         : 28 élément(s) — section_header 4 · text 19 · list_item 5
Markdown            : 549 élément(s)
Transcription JSON  : 12 tour(s) de parole
Audio mp3 (Voxtral) : 9 tour(s) de parole
PDF                 : conversion Docling en cours (~98 s, ~2 Gio)…
PDF                 : 11 élément(s)
Notes sautées       : 0 (déjà présentes)
Base                : Démonstration — pk=1 (créée)
```

Vérification post-exécution :

```
Page.objects.count() == 5
  5 capture-web-badgeons-la-normandie.html web
  6 PRESENTATION-V3.md file
  7 fake_debat_ia_transcription.json audio
  8 audio-FR-2locuteur-palaiscesar-14s.mp3 audio
  9 Etude_Epistemologique_IA.pdf file
BaseDeConnaissances(nom="Démonstration").slug == "demonstration"
AppartenanceDossierBase(dossier=carnet, base=base).exists() == True
```

## Compte réel d'éléments avec `page_no` en base

```python
ElementDocument.objects.exclude(provenance__page_no=None).count()
```

**→ 11.**

C'est le chiffre que la passation notait à 0 (« aucun PDF n'a jamais été
ingéré par le moteur ELEMENT »). Les trois premiers éléments inspectés
portent bien une boîte chacun (`section_header` p.1, `section_header`
p.1, `text` p.1).

## Réserves

- La conversion réelle prend ~90-95 s pour 3 pages avec chargement des
  modèles Docling (OCR + layout) : conforme à la mesure du 11 août
  (98 s), légère variation normale d'un run à l'autre.
- `git status` n'a pas été touché : aucune opération git exécutée,
  aucun commit, aucun push.
