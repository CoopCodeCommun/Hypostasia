# Rapport — second PDF ajouté aux étalons

> 11 août 2026. Aucune opération git effectuée (interdiction respectée) :
> `sample/présentation des open badges.pdf` était déjà `git add`-é par le
> propriétaire au démarrage de la tâche (`git status` le montrait en `A`).

## Ce qui a été fait

### 1. TDD — tests d'abord, échec constaté, puis implémentation

- Modifié `front/tests/test_charger_fixtures_sample.py` : comptes de
  pages `4 → 5` partout où `--sans-mp3` charge désormais cinq documents
  au lieu de quatre (le second PDF partage le mock d'`ingerer_un_fichier_
  avec_docling` avec le markdown et le premier PDF). Ajouté trois tests
  dans `PdfEtBaseDeDemonstrationTest` : chargement par défaut du second
  PDF (avec vérification que `original_filename` garde le nom exact et
  que le titre distingue les deux PDF), et `--fichier` avec le nom à
  espace et accent.
- Lancé `docker exec -w /app hypostasia_web uv run python manage.py test
  front.tests.test_charger_fixtures_sample` **avant** de toucher la
  commande : 6 échecs + 2 erreurs, conformes à l'attendu (comptes encore
  à 4, second PDF absent de `DOCUMENTS_ETALONS`).
- Implémenté ensuite `front/management/commands/charger_fixtures_sample.py`.
  Suite relancée : 44/44 verts.
- Ajouté `PdfDesOpenBadgesEtalonTest` (taggée `docling`, gardée par
  `TESTS_DOCLING=1`) dans `hypostasis_extractor/tests/test_fixtures_representatives.py`,
  jumelle de `PdfEtalonTest`.

### 2. Implémentation

- `FICHIER_DU_PDF` renommé `FICHIER_DU_PDF_ETUDE` ; nouvelle constante
  `FICHIER_DU_PDF_OPEN_BADGES = "présentation des open badges.pdf"`.
- `DOCUMENTS_ETALONS` passe à six entrées ; le second PDF est en tout
  dernier (le plus coûteux des six : ~3 365 Mio de RSS au pic contre
  ~2 031 pour l'étude).
- Nouvelle méthode `_charger_le_pdf_des_open_badges`, calquée
  exactement sur `_charger_le_pdf` (même patron : `read_bytes()`,
  `text_readability` vide, `ingerer_un_fichier_avec_docling.apply()`).
  Titre `"Présentation des Open Badges"` et libellé de bilan
  `"PDF open badges"`, distincts de `"Étude épistémologique de l'IA"` /
  `"PDF étude"` (l'ancien libellé `"PDF"` a été renommé `"PDF étude"`
  pour la symétrie — aucun test ne dépendait de l'ancien libellé).
- `_charger_les_documents` appelle les deux méthodes PDF dans l'ordre
  (étude puis open badges).
- Commentaires bilingues, docstrings `LOCALISATION`, messages d'erreur
  (`_resoudre_les_fichiers_demandes`) et textes d'aide (`--fichier`,
  `help`) mis à jour pour refléter six documents / deux PDF.
- Docstring de tête du module et commentaire au-dessus de
  `EXTENSIONS_REFUSEES` mis à jour (mesures des deux PDF).

### 3. Le nom à espace et accent — vérifié à chaque maillon

- **Lecture depuis `sample/`** : `Path.read_bytes()` — aucun problème,
  chemin filesystem.
- **`ContentFile(..., name=...)` → `media/`** : `original_filename` sur
  `Page` garde le nom **exact**, espace et accent compris — vérifié par
  `Page.objects.get(original_filename="présentation des open badges.pdf")`,
  qui réussit en test et sur la base réelle. Le nom du fichier **stocké**,
  lui, passe par le sanitizing standard de Django
  (`FileSystemStorage.get_valid_filename`) : l'espace devient un
  underscore, l'accent est conservé — comportement normal de la couche
  de stockage pour n'importe quel nom, pas une perte de donnée. Constaté
  en base réelle : `sources/présentation_des_open_badges_SFbu5Uy.pdf`.
- **Résolution du chemin par la tâche Celery** : `.apply()` a résolu et
  lu `/app/media/sources/présentation_des_open_badges_qJ30fkK.pdf` sans
  erreur, en test comme en exécution réelle.
- **`--fichier` en ligne de commande** : `docker exec -w /app
  hypostasia_web uv run python manage.py charger_fixtures_sample
  --fichier "présentation des open badges.pdf"` — testé au niveau shell
  réel (pas seulement `call_command` en Python), fonctionne.

Aucun maillon n'a achoppé. Le fichier n'a pas été renommé.

### 4. Exécution réelle (Docling, machine `hypostasia_web`)

- `free -h` vérifié avant chaque lancement : toujours ≥ 18 Gio
  disponibles (jamais sous le seuil de 5 Gio).
- Aucune suite de tests en cours vérifiée avant chaque lancement
  (`ps -eo cmd | grep "[m]anage.py test"`, vide à chaque fois).
- Une seule conversion Docling à la fois, jamais en parallèle.
- `PdfDesOpenBadgesEtalonTest` (conversion isolée, test taggé
  `docling`) : **86,99 s**, 61 éléments.
- `PdfEtalonTest` (premier PDF, non-régression) : **80,47 s**, 11
  éléments — inchangé.
- `charger_fixtures_sample --sans-mp3` en exécution réelle sur la base
  de développement (celle du serveur `runserver` en cours, non
  redémarré) : le second PDF a été chargé (les cinq autres, déjà
  présents, ont été sautés par idempotence), log applicatif « Docling :
  61 element(s) retenu(s) sur le document ».
- Relancée une seconde fois : les six documents sont sautés
  (« déjà présent — sauté »), aucune reconversion, aucun rechargement
  de modèle Docling observé dans les logs.

### 5. Comptes réels obtenus — second PDF

| Mesure | Valeur obtenue |
|---|---|
| Éléments | **61** |
| Ventilation | `list_item` 28 · `section_header` 12 · `text` 21 |
| Éléments avec `page_no` | 61/61 |
| Éléments avec `provenance.boites` | 61/61 |
| Pages Docling rencontrées | {1, 2, 3, 4} |
| Table | 0 |

Identique au benchmark (`tmp/benchmark-docling-2026-08-11.md` § 2), à
la mesure demandée par le mainteneur (61 éléments, 61/61). **Aucun
ajustement n'a été nécessaire.**

### 6. Total en base après chargement des six étalons

Carnet « Documents étalons » (base de développement) :

| Fichier | Éléments | Avec boîtes |
|---|---|---|
| capture-web-badgeons-la-normandie.html | 28 | 0 |
| PRESENTATION-V3.md | 549 | 0 |
| fake_debat_ia_transcription.json | 12 | 0 |
| audio-FR-2locuteur-palaiscesar-14s.mp3 | 9 | 0 |
| Etude_Epistemologique_IA.pdf | 11 | 11 |
| présentation des open badges.pdf | 61 | 61 |

**Total éléments avec coordonnées en base : 72** (11 + 61 — seuls les
deux PDF portent une géométrie de page).

### 7. Spec complétée, pas réécrite

Ajouté un **Addendum n°3** en fin de
`docs/superpowers/specs/2026-08-11-fixtures-sample-design.md`, à la
suite de l'addendum n°2 (qui anticipait déjà ce pas : « le second PDF
n'est pas versionné (…) à versionner d'abord si on le veut »). Le corps
de la spec et les addendums n°1/n°2 n'ont pas été modifiés.

## Tests — résultat final

- `front.tests.test_charger_fixtures_sample` : **44/44 verts** (Docling
  et Voxtral mockés, ~12 s).
- `hypostasis_extractor.tests.test_fixtures_representatives` (suite
  ordinaire, tags `docling` sautés) : **8/8**, `skipped=6`.
- `hypostasis_extractor.tests.test_fixtures_representatives.PdfEtalonTest`
  (réel, `TESTS_DOCLING=1 --tag=docling`) : **1/1 vert**, 80,47 s.
- `hypostasis_extractor.tests.test_fixtures_representatives.PdfDesOpenBadgesEtalonTest`
  (réel, `TESTS_DOCLING=1 --tag=docling`) : **1/1 vert**, 86,99 s.
- `manage.py check` : aucun problème.

## Réserves

- Le libellé de bilan `"PDF"` (premier document) a été renommé
  `"PDF étude"` pour distinguer les deux lignes du bilan à l'œil.
  Aucun test ne dépendait de l'ancien libellé, mais c'est un changement
  de sortie visible que le mainteneur n'avait pas explicitement demandé
  — signalé plutôt que fait en silence.
- Le fichier `sample/présentation des open badges.pdf` était déjà en
  `git add` (état `A`) avant le début de la tâche ; je ne l'ai ni ajouté
  ni committé, conformément à l'interdiction absolue sur `git`.
- `--sans-mp3` a été utilisé pour toutes les exécutions réelles (pas de
  `MISTRAL_API_KEY` nécessaire ni de coût réseau) : le chemin mp3 n'a
  pas été retesté dans ce lot, mais il est inchangé par cette tâche.
