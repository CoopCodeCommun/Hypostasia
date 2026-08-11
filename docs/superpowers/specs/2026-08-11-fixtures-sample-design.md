# `charger_fixtures_sample` — redonner un corpus étalon à une base vide

> Spécification, 11 août 2026.
> Objectif 1 de `PLAN/PASSATION-machine-docling.md`.
> Les objectifs 2 à 4 (mesure Docling, fixtures PDF, spec du visualiseur)
> ne sont **pas** couverts ici : ils dépendent d'une mesure qui n'a pas
> encore été faite.

---

## 1. Le problème

La machine de développement démarre avec une base à zéro. Il n'y a ni
utilisateur, ni carnet, ni note — rien à regarder, donc rien à
développer. `sample/` porte cinq documents versionnés choisis pour
couvrir les formes d'entrée du produit ; il manque la commande qui les
transforme en base utilisable.

Les deux commandes existantes ne conviennent pas :

- **`charger_fixtures_demo`** écrit ses pages « Wikipedia » en dur dans
  le code. Elles ne portent que des `<p>` : tous leurs éléments sortent
  en `text`, elles n'éprouvent aucun label de structure.
- **`charger_fixtures_llm_reel`** appelle les services d'ingestion nus,
  et son `_proprietaire()` lève `CommandError` quand la base n'a aucun
  utilisateur — c'est-à-dire exactement notre cas.

---

## 2. Ce que la commande produit

`front/management/commands/charger_fixtures_sample.py` — même famille
que les autres `charger_fixtures_*`.

Un propriétaire, une configuration de transcription, un carnet, quatre
notes :

| Fichier de `sample/` | Page | Ingestion |
|---|---|---|
| `capture-web-badgeons-la-normandie.html` | `source_type="web"`, `html_original` | `ingerer_une_capture_web_avec_docling` |
| `PRESENTATION-V3.md` | `source_type="file"`, `source_file` | `ingerer_un_fichier_avec_docling` |
| `fake_debat_ia_transcription.json` | `source_type="audio"`, `transcription_raw` | `ingerer_une_transcription_diarisee_en_elements` |
| `audio-FR-2locuteur-palaiscesar-14s.mp3` | `source_type="audio"` + `TranscriptionJob` | `transcrire_audio_task`, qui enchaîne l'ingestion |

Après elle, et sans rien installer de plus, on doit pouvoir voir : une
gouttière de document écrit avec des labels réels, une gouttière audio
avec locuteurs et minutages, le panneau intégré, le surlignage au
survol.

---

## 3. Décisions de conception

### 3.1 Passer par les tâches Celery, en synchrone

La commande appelle `ingerer_un_fichier_avec_docling.apply(args=[pk])`,
et non `ingestion_docling.ingerer_un_fichier(page, chemin)`.

**Pourquoi.** Les services nus créent les éléments et s'arrêtent là. Ce
sont les tâches qui écrivent `Page.ingestion_etat` (`EN_COURS` →
`REUSSIE` / `ECHOUEE`) et qui attrapent l'échec avec un message lisible
par l'utilisateur. Or l'écran de lecture affiche cet état (U2). Une
page ingérée par le service nu reste à l'état vide : elle ment sur son
propre statut. C'est ce que produit `charger_fixtures_llm_reel`
aujourd'hui.

`.apply()` exécute la tâche dans le processus de la commande : aucun
worker n'est requis, et le bilan chiffré final est vrai parce que tout
est terminé quand il s'affiche. `.delay()` rendrait ce bilan mensonger.

### 3.2 Créer la `TranscriptionConfig` Voxtral

`front/tasks.py:633` choisit le fournisseur ainsi :

```python
if config_transcription and config_transcription.provider == "voxtral":
    segments_transcrits = transcrire_audio_via_voxtral(...)
else:
    segments_transcrits = transcrire_audio_mock(...)
```

Sur une base neuve il n'existe aucune `TranscriptionConfig` : le mp3
serait **mocké en silence** et produirait un faux verbatim. La commande
crée donc la config `Voxtral Mini` (`model_choice="voxtral-mini-latest"`,
`is_active=True`, `diarization_enabled=True`), sur le patron déjà écrit
dans `charger_fixtures_demo.py:1144`.

La clé vient de l'environnement : `front/services/transcription_audio.py:86`
lit `os.environ["MISTRAL_API_KEY"]`. **Clé absente → la commande saute
le mp3 et le dit**, plutôt que de créer une config qui échouera ou, pire,
de laisser passer un mock déguisé en transcription.

### 3.3 Idempotence par nom de fichier dans le carnet

Une relance ne doit rien doubler et ne doit pas relancer Docling.

La clé est `Page.original_filename` (ou `Page.url` pour la capture web)
parmi les notes rangées dans le carnet étalon. Une note déjà présente
est sautée **avant** toute conversion.

Le service porte bien un garde-fou — `creer_les_elements_d_une_page`
lève si la page a déjà des éléments — mais il arrive **après** la
conversion Docling. S'y fier ferait payer le coût sans rien produire.

### 3.4 `--reset` pour rejouer, et son garde-fou

L'appel Voxtral doit servir de test à chaque lancement. L'idempotence
du § 3.3 s'y oppose : une relance saute le mp3 déjà transcrit. `--reset`
tranche — il supprime le carnet étalon et les notes qui n'appartiennent
qu'à lui, puis tout se refait, appel Voxtral compris.

> **Le mécanisme de déduplication par empreinte** décidé le 11 août
> (chantier voisin, spec `2026-08-11-dedup-import-design.md`) **ne
> remplace pas `--reset`** : il va dans le sens inverse. Une empreinte
> rendrait le saut du mp3 encore plus systématique, alors qu'on veut
> précisément pouvoir le rejouer. Les deux mécanismes coexistent sans
> se contredire — l'un évite les doublons subis, l'autre permet la
> reprise voulue.

**Garde-fou obligatoire.** `AncrageExtraction.element` est en `PROTECT` :
supprimer une page qui porte des ancres lève `ProtectedError`. Si une
note étalon a été analysée entre-temps, `--reset` doit **refuser
explicitement**, nommer la note et son nombre d'ancres, et ne rien
supprimer du tout — jamais une suppression partielle qui laisse le
carnet à moitié vide.

### 3.5 Le PDF et le docx sont refusés, pas oubliés

Ils ne sont pas simplement absents de la liste : si on passe un `.pdf`
ou un `.docx` à `--fichier`, la commande le refuse en nommant l'objectif
2 de la passation. Docling n'a pas encore été éprouvé sur eux ici, et
une commande de fixtures appelant Docling en masse est exactement ce qui
a fait tomber le serveur le 10 août.

Le `.docx` de `sample/` n'est de toute façon pas versionné.

### 3.6 Le propriétaire

Le premier superuser par `pk` s'il en existe un ; sinon la commande crée
`jonas` / `admin1234` (`is_staff=True`), mêmes identifiants que
`charger_fixtures_demo`, pour qu'un seul mot de passe suffise quel que
soit l'ordre des deux commandes.

---

## 4. Interface

```
python manage.py charger_fixtures_sample [--a-blanc] [--reset] [--sans-mp3]
                                         [--fichier CHEMIN]
```

| Option | Effet |
|---|---|
| `--a-blanc` | Affiche ce qui serait fait. N'écrit rien, n'appelle ni Docling ni Voxtral. |
| `--reset` | Supprime le carnet étalon et ses notes propres avant de recharger (§ 3.4). |
| `--sans-mp3` | Saute la transcription Voxtral. Automatique et signalé si `MISTRAL_API_KEY` manque. |
| `--fichier CHEMIN` | Ne charge que ce fichier au lieu des quatre de `sample/`. Répétable. C'est par cette porte qu'arrive un `.pdf` ou un `.docx` — et c'est elle qui les refuse (§ 3.5). |

Le carnet s'appelle **« Documents étalons »**, en `VisibiliteDossier.PUBLIC`.

### Bilan de sortie

Forme attendue. Seuls les comptes de la capture web sont connus
d'avance (§ 5.2) ; les autres se mesureront à la première exécution et
ne sont donc pas prédits ici.

```
Propriétaire        : jonas (réutilisé)
Carnet              : Documents étalons — pk=<N>
Capture web         : 28 élément(s) — section_header 4 · list_item 5 · text 19
Markdown            : <N> élément(s)
Transcription JSON  : <N> tour(s) de parole
Audio mp3 (Voxtral) : <N> tour(s) de parole — <N> s
Notes sautées       : <N> (déjà présentes)
```

Le détail par label n'est imprimé que pour la capture web : c'est elle
qui porte le contrôle de non-régression du § 5.

---

## 5. Tests (TDD)

Le test s'écrit d'abord, on le regarde échouer, puis vient le code.
Deux vitesses, sur le patron déjà en place dans
`hypostasis_extractor/tests/test_fixtures_representatives.py`.

### 5.1 Rapides — Docling et Voxtral mockés

Dans `front/tests/test_charger_fixtures_sample.py` :

1. Base sans utilisateur → la commande crée `jonas` et ne lève pas.
2. Un superuser existe → il est réutilisé, aucun compte créé.
3. Deux exécutations de suite → même nombre de pages, et les tâches
   d'ingestion ne sont appelées qu'une fois (assertion sur le mock).
4. `--a-blanc` → aucune `Page`, aucun `Dossier`, aucune tâche appelée.
5. `--fichier` sur un `.pdf` → refus explicite, aucune conversion.
6. `MISTRAL_API_KEY` absente → mp3 sauté, message écrit, les trois
   autres notes chargées quand même.
7. Aucune `TranscriptionConfig` avec la clé présente → la config Voxtral
   est créée, `is_active=True`, `provider="voxtral"`.
8. `--reset` sur une note portant une ancre → refus, `ProtectedError`
   jamais atteinte, rien de supprimé.
9. Les quatre pages finissent en `ingestion_etat=REUSSIE`.

### 5.2 Lent — conversion Docling réelle

Taggé `docling`, sauté sauf `TESTS_DOCLING=1`, comme l'existant :

10. La capture web réelle rend **28 éléments — `section_header` 4 ·
    `list_item` 5 · `text` 19**.

Ce compte est le contrôle de non-régression des deux correctifs du
11 août (légende d'image, recollage des groupes `inline`). **54
éléments dont un `picture`** signalerait un retour à la version
antérieure aux correctifs ; **une cinquantaine de blocs tous en `text`**
signalerait le retour du découpage maison par paragraphes.

---

## 6. Hors périmètre

- Le PDF, sa mesure, ses fixtures étalons, le visualiseur (objectifs 2
  à 4). Ils feront l'objet d'une spec séparée, **après** la mesure —
  notamment celle qui dira si `provenance.boites` se remplit vraiment.
- Le `.docx`, non versionné.
- Toute analyse LLM des notes chargées : la commande produit des
  documents et leurs éléments, pas des extractions.
- Tout commit. Le dépôt reste à la main de son propriétaire.

---

## 7. Risques connus

| Risque | Parade |
|---|---|
| Docling sur `PRESENTATION-V3.md` (60 Kio) coûte plus que les 784 Mio mesurés sur `pad-markdown.md` (1 Kio) | Mesurer la RAM au pic à la première exécution et le noter. Le markdown ne charge ni OCR ni modèle de layout : le pic devrait rester loin des 21 Gio disponibles. **Mesure du 11 août sur cette machine, pour comparaison** : un PDF de 3 pages, lui, charge OCR *et* layout — 2 031 Mio et 98 s, dont ~89 s de seul chargement des modèles. C'est la borne haute ; le markdown doit rester très en dessous. Si la commande approche ce chiffre sur un `.md`, quelque chose charge des modèles qui n'ont rien à y faire. |
| L'appel Voxtral échoue (réseau, quota) | La tâche attrape déjà l'erreur et passe le `TranscriptionJob` en échec. La commande le rapporte dans son bilan et n'échoue pas pour autant : les trois autres notes restent chargées. |
| `.apply()` masque un bug qui n'apparaîtrait qu'avec un vrai worker (sérialisation des arguments) | Les tâches ne reçoivent qu'une clé primaire entière — rien à sérialiser qui puisse diverger. |
| La capture web n'a pas de `url`, l'idempotence porterait sur un champ vide | Poser explicitement l'`url` d'origine de l'article à la création de la page. |

---

# Addendum n°2 du 11 août 2026 — le PDF entre dans les étalons

> Demande du propriétaire du dépôt, en cours de session. **Renverse une
> décision de la spec** (§ 3.5) : le PDF n'est plus refusé, il est chargé
> par défaut. Le § 3.5 n'est **pas** réécrit : ce qui suit s'ajoute à la
> trace, sans l'effacer.

## Ce qui change, et pourquoi c'est légitime maintenant

Le § 3.5 faisait refuser les `.pdf` parce que Docling n'avait **pas été
éprouvé** sur cette machine, et qu'une commande de fixtures convertissant des
PDF en masse avait fait tomber le serveur le 10 août. Ce motif est levé : la
mesure existe.

| PDF | Pages | Éléments | `provenance.boites` | Durée | RSS pic |
|---|---|---|---|---|---|
| `Etude_Epistemologique_IA.pdf` | 3 | 11, dont **2 `table`** | **11/11** | 98 s | 2 031 Mio |

Ce compte a été reconfirmé lors de l'implémentation de la tâche 9 : la
conversion Docling réelle (`PdfEtalonTest`, taggée `docling`) et la
commande `charger_fixtures_sample --reset` rendent toutes deux **11
éléments, dont 2 `table`, et 11 boîtes sur 11 éléments**, pages 1 à 3.

**Le gain dépasse la fixture.** La passation notait que la base portait
« 0 élément avec `page_no` » — aucun PDF n'avait jamais été ingéré par le
moteur ELEMENT, ce qui rendait le visualiseur PDF impossible à développer
faute de la moindre boîte de coordonnées. Charger ce PDF **remplit enfin ce
trou** : 11 éléments avec `page_no` et boîtes, et le bouton « voir la source »
de la gouttière, déjà codé, a de quoi s'afficher.

**Le docx reste refusé.** Le seul du dépôt (`présentation des open badges.docx`)
est fait de diapositives exportées en images : Docling en extrait
**zéro élément**. Une fixture qui ne produit rien n'éprouve rien.

**Le second PDF n'est pas versionné.** `présentation des open badges.pdf`
n'apparaît pas dans `git ls-files sample/` : une fixture non versionnée
n'existe pas pour les autres machines. À versionner d'abord si on le veut.

## Ce qui a changé dans la commande

- `EXTENSIONS_REFUSEES` ne garde plus que `{".docx"}`.
- `FICHIER_DU_PDF` rejoint `DOCUMENTS_ETALONS`, **en dernier** : c'est le
  document le plus coûteux, les quatre autres sont en base avant lui.
- `_charger_le_pdf` suit le patron de `_charger_le_markdown`, avec deux
  différences : lecture en `read_bytes()` (un PDF est binaire) et
  `text_readability` laissé vide (ce sont les `ElementDocument`, pas la
  `Page`, qui portent le texte une fois ingérés). Son bilan annonce le
  coût **avant** de lancer Docling : la commande va bloquer ~98 s sinon
  sans rien dire.
- Une base de connaissances **« Démonstration »** (`slug="demonstration"`,
  posé explicitement) range désormais le carnet des étalons, via
  `_creer_la_base_de_demonstration` — même patron que
  `AppartenanceDossierBase.objects.get_or_create` dans
  `front/views_corpus.py:1176`.

## Tests devenus faux, repris

`test_un_pdf_est_refuse_sans_conversion` (`RefusDesFormatsLourdsTest`)
affirmait l'inverse de la nouvelle règle : il devient
`test_un_docx_est_refuse_sans_conversion`. Les comptes de pages attendus
avec `--sans-mp3` passent de 3 à 4 dans plusieurs tests (le PDF partage
le mock d'`ingerer_un_fichier_avec_docling` avec le markdown, donc se
charge dans les mêmes conditions) : `test_les_deux_notes_sont_rangees_
dans_le_carnet`, `test_relancer_ne_double_rien_et_ne_reconvertit_pas`,
`test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge`,
`test_une_note_avec_ses_elements_est_bien_sautee`,
`test_reset_supprime_les_notes_et_les_recharge`, et le compte de notes
sautées du bilan (3 → 4).

---

# Addendum n°3 du 11 août 2026 — un second PDF, versionné, ajouté aux étalons

> Suite directe de l'addendum n°2, qui notait : « Le second PDF n'est pas
> versionné (…) À versionner d'abord si on le veut. » C'est fait : le
> propriétaire du dépôt a versionné `sample/présentation des open
> badges.pdf` (`git status` le montre en `A`, prêt à committer). Ce qui
> suit s'ajoute à la trace, sans réécrire ce qui précède.

## Motif

Éprouver le moteur d'ingestion sur un PDF réel plus lourd que l'étalon
existant (212 Kio contre 8,7 Kio, 4 pages contre 3, 61 éléments contre
11 — mesure complète dans `tmp/benchmark-docling-2026-08-11.md` § 2).

## Ce qui a changé dans la commande

- `FICHIER_DU_PDF` est renommé `FICHIER_DU_PDF_ETUDE` : avec un second
  PDF, un nom qui ne dit pas lequel est lequel devient ambigu. Le nouveau
  s'appelle `FICHIER_DU_PDF_OPEN_BADGES`.
- `DOCUMENTS_ETALONS` en compte désormais **six** ; `FICHIER_DU_PDF_OPEN_
  BADGES` est en tout dernier, après `FICHIER_DU_PDF_ETUDE` : c'est le
  plus coûteux des six (~3 365 Mio de RSS au pic, contre ~2 031 Mio pour
  l'étude).
- `_charger_le_pdf_des_open_badges` suit exactement le patron de
  `_charger_le_pdf` (même lecture en `read_bytes()`, même
  `text_readability` vide, même passage par
  `ingerer_un_fichier_avec_docling.apply()`). Son titre —
  « Présentation des Open Badges » — et son libellé de bilan — « PDF
  open badges » — le distinguent de l'étude d'un coup d'œil dans
  l'interface comme dans les logs.
- `EXTENSIONS_REFUSEES` ne change pas : le docx reste le seul format
  refusé.

## Le nom de fichier à espace et accent

`présentation des open badges.pdf` a été vérifié à chaque maillon :

- lecture depuis `sample/` via `Path.read_bytes()` : aucun problème,
  c'est un chemin filesystem, pas une chaîne interprétée ;
- `ContentFile(octets, name=FICHIER_DU_PDF_OPEN_BADGES)` écrit bien un
  fichier dans `media/sources/` ; **`original_filename` sur `Page`**
  porte le nom exact, espace et accent compris — c'est lui que
  l'interface affiche ;
- le nom du fichier **stocké**, lui, passe par le sanitizing standard de
  Django (`FileSystemStorage.get_valid_filename`) : l'espace devient un
  underscore (`présentation_des_open_badges_<suffixe>.pdf`), l'accent
  est conservé tel quel. C'est un comportement normal de la couche de
  stockage pour n'importe quel nom de fichier — pas une perte de
  donnée, et pas quelque chose que cette commande a besoin de corriger ;
- la tâche Celery résout le chemin depuis `page.source_file` exactement
  comme pour l'étude, et l'a fait sans erreur lors de l'exécution réelle
  (`/app/media/sources/présentation_des_open_badges_qJ30fkK.pdf`) ;
- `--fichier "présentation des open badges.pdf"` en ligne de commande
  fonctionne, exécution réelle comprise (`docker exec ... manage.py
  charger_fixtures_sample`, sans guillemets shell cassés).

Le fichier n'a pas été renommé. Un nom avec espace est un cas d'usage
légitime.

## Comptes réels obtenus (exécution réelle, 11 août 2026)

Conversion Docling réelle, machine `hypostasia_web` :

| Mesure | Valeur obtenue |
|---|---|
| Éléments | **61** |
| Ventilation | `list_item` 28 · `section_header` 12 · `text` 21 |
| Éléments avec `page_no` | 61/61 |
| Éléments avec `provenance.boites` | 61/61 |
| Pages Docling rencontrées | {1, 2, 3, 4} |
| Table | 0 (aucune — contrairement à l'étude, qui en a 2) |

Ce compte est identique à celui du benchmark (§ 2 de
`tmp/benchmark-docling-2026-08-11.md`) et confirmé deux fois : une fois
par `PdfDesOpenBadgesEtalonTest` (taggée `docling`, conversion isolée,
86,99 s), une fois par l'exécution réelle de `charger_fixtures_sample`
sur la base de développement (conversion + écriture, log applicatif :
« Docling : 61 element(s) retenu(s) »).

Après cette exécution, le carnet « Documents étalons » porte six notes
et **72 éléments avec coordonnées** en base (11 de l'étude + 61 de la
présentation open badges) — la capture web, le markdown, la transcription
JSON et le mp3 n'en portent aucun, faute de géométrie de page.

## Tests devenus faux, repris

Les comptes de pages attendus avec `--sans-mp3` passent de **4 à 5**
dans les mêmes tests que l'addendum n°2 avait déjà fait passer de 3 à 4
(le second PDF partage, comme le premier, le mock d'`ingerer_un_fichier_
avec_docling`) : `test_les_deux_notes_sont_rangees_dans_le_carnet`,
`test_relancer_ne_double_rien_et_ne_reconvertit_pas` (le compte d'appels
du mock partagé passe de 2 à 3), `test_sans_cle_mistral_le_mp3_est_
saute_et_le_reste_charge`, `test_une_note_avec_ses_elements_est_bien_
sautee`, `test_reset_supprime_les_notes_et_les_recharge`, et le compte
de notes sautées du bilan (4 → 5).

`hypostasis_extractor/tests/test_fixtures_representatives.py` gagne
`PdfDesOpenBadgesEtalonTest`, jumelle de `PdfEtalonTest` : mêmes
décorateurs `@tag("docling")` et `@unittest.skipUnless(DOCLING_DEMANDE,
RAISON_DU_SKIP)`, même structure, verrouillant les 61 éléments plutôt
que les 11 de l'étude.
