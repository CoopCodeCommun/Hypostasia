## Tâche 2 : les deux documents écrits — capture web et markdown

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : `_proprietaire()`, `_creer_le_carnet()` de la tâche 1.
- Produit : `_charger_la_capture_web(proprietaire, carnet)`,
  `_charger_le_markdown(proprietaire, carnet)`, et
  `_note_deja_presente(carnet, nom_du_fichier)` — que les tâches 3 et 5
  réutilisent telles quelles.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class DocumentsEcritsTest(TestCase):
    """La capture web et le markdown, avec Docling mocké."""

    def setUp(self):
        self.chemin_du_module = (
            "front.management.commands.charger_fixtures_sample"
        )

    def test_la_capture_web_devient_une_page(self):
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_de_la_capture = Page.objects.get(source_type="web")
        self.assertTrue(page_de_la_capture.html_original)
        self.assertEqual(
            page_de_la_capture.original_filename,
            "capture-web-badgeons-la-normandie.html",
        )

    def test_le_markdown_devient_une_page_avec_son_fichier(self):
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_du_markdown = Page.objects.get(
            original_filename="PRESENTATION-V3.md",
        )
        self.assertEqual(page_du_markdown.source_type, "file")
        # La tache resout le chemin depuis source_file : sans lui, elle
        # rendrait {"erreur": "page sans fichier source"}.
        # / The task resolves the path from source_file.
        self.assertTrue(page_du_markdown.source_file)

    def test_les_deux_notes_sont_rangees_dans_le_carnet(self):
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        carnet = Dossier.objects.get(name="Documents étalons")
        self.assertEqual(
            Page.objects.filter(
                appartenances_dossiers__dossier=carnet,
            ).distinct().count(),
            2,
        )

    def test_relancer_ne_double_rien_et_ne_reconvertit_pas(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, \
                patch(cible_fichier) as fichier_mocke:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

            # LE POINT DE CE TEST : la seconde execution ne doit PAS
            # reconvertir. Le garde-fou du service arrive apres la
            # conversion — s'y fier ferait payer Docling pour rien.
            # / The second run must not re-convert.
            self.assertEqual(capture_mockee.call_count, 1)
            self.assertEqual(fichier_mocke.call_count, 1)

        self.assertEqual(Page.objects.count(), 2)

    def test_les_taches_sont_appelees_en_synchrone_avec_la_cle_primaire(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_de_la_capture = Page.objects.get(source_type="web")
        capture_mockee.assert_called_once_with(
            args=[page_de_la_capture.pk],
        )
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.DocumentsEcritsTest --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : échec sur `--sans-mp3` inconnu, puis sur `Page.DoesNotExist`.

- [ ] **Étape 3 : écrire le chargement des documents écrits**

Ajouter l'option, les constantes, et remplacer `_charger_les_documents`.

```python
# En tete du fichier, apres les imports existants
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

from core.models import Page
from core.services.corpus import ranger_une_note_dans_un_carnet

REPERTOIRE_SAMPLE = Path(settings.BASE_DIR) / "sample"

FICHIER_DE_LA_CAPTURE = "capture-web-badgeons-la-normandie.html"
FICHIER_DU_MARKDOWN = "PRESENTATION-V3.md"

# L'article d'origine. Sans url, l'idempotence de la capture porterait
# sur un champ vide et deux captures se confondraient.
# / Without a url, the capture's idempotency key would be empty.
URL_DE_LA_CAPTURE = "https://badgeons-la-normandie.fr/"
```

```python
    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true",
            help="Affiche ce qui serait fait, sans rien ecrire.",
        )
        analyseur_d_arguments.add_argument(
            "--sans-mp3", action="store_true",
            help="Saute la transcription Voxtral du fichier audio.",
        )
```

Dans `handle`, après la lecture de `--a-blanc` :

```python
        self.sans_mp3 = options["sans_mp3"]
```

Puis les méthodes :

```python
    def _note_deja_presente(self, carnet_des_etalons, nom_du_fichier):
        """
        Dit si une note issue de ce fichier est deja dans le carnet.
        / Says whether a note from this file is already in the notebook.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        On regarde AVANT de convertir. Le service porte bien un garde-fou
        — `creer_les_elements_d_une_page` leve si la page a deja des
        elements — mais il arrive APRES la conversion Docling. S'y fier
        ferait payer 98 s pour un PDF de 3 pages, et rien produire.
        / The service's guard comes after conversion; this one comes before.
        """
        if carnet_des_etalons is None:
            return False
        return Page.objects.filter(
            appartenances_dossiers__dossier=carnet_des_etalons,
            original_filename=nom_du_fichier,
        ).exists()

    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
        """
        Charge les documents etalons, un par forme d'entree.
        / Loads the reference documents, one per input form.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py
        """
        self._charger_la_capture_web(proprietaire, carnet_des_etalons)
        self._charger_le_markdown(proprietaire, carnet_des_etalons)

    def _charger_la_capture_web(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue de la capture web, et l'ingere.
        / Creates the note from the web capture, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        C'est la SEULE fixture qui eprouve les labels de structure d'un
        HTML reel : section_header, list_item, text. Les pages « Wikipedia »
        de charger_fixtures_demo n'ont que des <p> et sortent toutes en
        `text`. / The only fixture exercising real HTML structure labels.
        """
        if self._note_deja_presente(carnet_des_etalons, FICHIER_DE_LA_CAPTURE):
            self.stdout.write("Capture web         : déjà présente — sautée")
            return None

        if self.a_blanc:
            self.stdout.write("Capture web         : serait chargée")
            return None

        html_capture = (REPERTOIRE_SAMPLE / FICHIER_DE_LA_CAPTURE).read_text(
            encoding="utf-8",
        )

        page_de_la_capture = Page.objects.create(
            source_type="web",
            original_filename=FICHIER_DE_LA_CAPTURE,
            url=URL_DE_LA_CAPTURE,
            title="Badgeons la Normandie",
            html_original=html_capture,
            html_readability=html_capture,
            text_readability="",
            content_hash=hashlib.sha256(
                html_capture.encode("utf-8"),
            ).hexdigest(),
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
        )
        ranger_une_note_dans_un_carnet(
            page_de_la_capture, carnet_des_etalons, proprietaire,
        )

        nombre_d_elements = self._ingerer_la_capture(page_de_la_capture)
        self.stdout.write(
            f"Capture web         : {nombre_d_elements} élément(s)",
        )
        return page_de_la_capture

    def _ingerer_la_capture(self, page_de_la_capture):
        """
        Lance l'ingestion de la capture, en synchrone.
        / Runs the capture's ingestion, synchronously.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        ON PASSE PAR LA TACHE, PAS PAR LE SERVICE.

        Le service nu cree les elements et s'arrete la. C'est la tache qui
        ecrit `Page.ingestion_etat` (en_cours -> reussie/echouee) et qui
        attrape l'echec avec un message lisible. L'ecran de lecture affiche
        cet etat : une page ingeree par le service nu ment sur son statut.
        `.apply()` l'execute ici meme, sans worker.
        / The task writes ingestion_etat; the bare service does not.
        """
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        resultat = ingerer_une_capture_web_avec_docling.apply(
            args=[page_de_la_capture.pk],
        )
        return self._elements_du_resultat(resultat)

    def _elements_du_resultat(self, resultat_de_la_tache):
        """
        Lit le nombre d'elements d'un resultat de tache, sans mentir.
        / Reads a task result's element count, without lying.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Les taches rendent {"elements": N} ou {"erreur": "..."} — jamais
        une exception pour un cas normal. Un mock de test rend un Mock :
        on ne compte alors rien plutot que d'inventer un chiffre.
        / Never invent a count: a mocked task has none to give.
        """
        valeur = getattr(resultat_de_la_tache, "result", None)
        if not isinstance(valeur, dict):
            return "?"
        if "erreur" in valeur:
            self.stdout.write(self.style.WARNING(
                f"    ingestion en échec : {valeur['erreur']}",
            ))
            return 0
        return valeur.get("elements", 0)

    def _charger_le_markdown(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue du markdown, et l'ingere.
        / Creates the note from the markdown file, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Le markdown passe bien par Docling, mais sans OCR ni modele de
        layout : ceux-la ne se chargent que pour les PDF et les images.
        C'est pourquoi cette fixture-ci est sure, la ou le PDF ne l'est pas.
        / Markdown goes through Docling without OCR or layout models.
        """
        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MARKDOWN):
            self.stdout.write("Markdown            : déjà présent — sauté")
            return None

        if self.a_blanc:
            self.stdout.write("Markdown            : serait chargé")
            return None

        chemin_du_markdown = REPERTOIRE_SAMPLE / FICHIER_DU_MARKDOWN
        contenu_du_markdown = chemin_du_markdown.read_text(encoding="utf-8")

        page_du_markdown = Page.objects.create(
            source_type="file",
            original_filename=FICHIER_DU_MARKDOWN,
            url=None,
            title="Présentation Hypostasia V3",
            html_original="",
            html_readability="",
            text_readability=contenu_du_markdown,
            content_hash=hashlib.sha256(
                contenu_du_markdown.encode("utf-8"),
            ).hexdigest(),
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(
                contenu_du_markdown.encode("utf-8"),
                name=FICHIER_DU_MARKDOWN,
            ),
        )
        ranger_une_note_dans_un_carnet(
            page_du_markdown, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_un_fichier_avec_docling,
        )

        # On ne passe QUE la cle primaire : la tache resout le chemin
        # depuis page.source_file, comme le fait la vue d'import.
        # / Only the pk: the task resolves the path from source_file.
        resultat = ingerer_un_fichier_avec_docling.apply(
            args=[page_du_markdown.pk],
        )
        self.stdout.write(
            f"Markdown            : {self._elements_du_resultat(resultat)} élément(s)",
        )
        return page_du_markdown
```

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 12 tests.

- [ ] **Étape 5 : lancer la commande pour de vrai, Docling compris**

```bash
free -h | head -2
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --sans-mp3
```

Ceci lance deux vraies conversions Docling. Vérifier `free -h` avant :
il faut plusieurs Gio disponibles. Attendu : deux comptes d'éléments
non nuls, et **28 pour la capture web**.

**Si la capture web ne rend pas 28** : ne pas corriger le chiffre dans
le test. S'arrêter, relever le compte obtenu et sa ventilation par label,
et le signaler — un écart ici veut dire que l'extraction a bougé.

- [ ] **Étape 6 : point d'arrêt**

Ne rien commiter. Rapporter les comptes réels obtenus, la RAM au pic
observée, et la durée.

---

## Tâche 3 : les deux entrées audio — transcription JSON et mp3
## Contraintes globales

Elles valent pour **toutes** les tâches.

- **Aucune opération git.** Ni `add`, ni `commit`, ni `checkout --`, ni
  `stash`, ni `restore`. Le dépôt appartient au mainteneur. Chaque tâche
  se termine par un point d'arrêt, pas par un commit.
- **Aucun `ruff format` ni `ruff check --fix`** sur un fichier existant.
- **Une seule suite de tests à la fois.** Jamais `--parallel`. Deux runs
  simultanés se détruisent la base.
- **Commentaires bilingues** français puis anglais, sur chaque bloc de
  logique. C'est la convention du dépôt, sans exception.
- **Noms de variables verbeux** en français : `carnet_des_etalons`, pas
  `carnet`. `nombre_d_elements_crees`, pas `n`.
- **Chaque fichier créé porte un en-tête** avec une ligne
  `LOCALISATION : <chemin>`, comme tous les modules du dépôt.
- **Jamais Docling sur un `.pdf` ou un `.docx`** depuis cette commande.
- **Ne jamais inventer un chiffre.** Un compte annoncé est un compte mesuré.

### Commandes de référence

```bash
# Lancer un test
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus

# Lancer la commande
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --a-blanc
```

`uv run` est obligatoire : `python manage.py` seul échoue dans ce
conteneur (`ImportError: Couldn't import Django`).

---

## Structure des fichiers
## Faits établis — ne pas les redécouvrir

Mesurés le 11 août 2026 sur cette machine. Ils dispensent de vérifier.

| Fait | Valeur |
|---|---|
| Champ d'état d'ingestion sur `Page` | **`ingestion_etat`** (pas `etat_ingestion`), plus `ingestion_detail` et `ingestion_maj_le` |
| Sans `TranscriptionConfig` active | la transcription est **mockée en silence** (`front/tasks.py:633`) |
| `sample/fake_debat_ia_transcription.json` | 12 segments, 3 locuteurs (Laurent, Elinor, Eric), clés racine `model` / `text` / `segments` |
| `sample/capture-web-badgeons-la-normandie.html` | 8 523 octets, déjà extrait |
| Conversion Docling d'un PDF de 3 pages | 2 031 Mio, 98 s dont ~89 s de chargement des modèles |
| L'import d'un JSON de transcription par la vue | **ne crée aucun élément** — la commande doit appeler l'ingestion elle-même |

### Signatures dont le code a besoin

```python
# core/services/corpus.py
ranger_une_note_dans_un_carnet(page, dossier, utilisateur=None)  # -> appartenance

# hypostasis_extractor/tasks_element.py
ingerer_un_fichier_avec_docling(identifiant_de_la_page, chemin_du_fichier=None)
ingerer_une_capture_web_avec_docling(identifiant_de_la_page)
ingerer_une_transcription_diarisee_en_elements(identifiant_de_la_page)
# -> {"elements": int} ou {"erreur": str}

# front/tasks.py
transcrire_audio_task(job_id, chemin_fichier_audio, max_locuteurs=5, langue="")

# front/services/transcription_audio.py
construire_html_diarise(donnees)  # -> (html_diarise, texte_brut)
```

Appel synchrone d'une tâche : `ingerer_un_fichier_avec_docling.apply(args=[page.pk])`.

---

## Tâche 1 : le squelette — propriétaire, carnet, config, `--a-blanc`
