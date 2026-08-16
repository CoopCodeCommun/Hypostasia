# `charger_fixtures_sample` — plan d'implémentation

> **Pour les agents :** SOUS-SKILL REQUIS — `superpowers:subagent-driven-development`
> (recommandé) ou `superpowers:executing-plans`, tâche par tâche. Les étapes
> utilisent des cases à cocher (`- [ ]`).

**But :** donner à une base vide un corpus étalon de quatre documents,
issus de `sample/`, couvrant les quatre formes d'entrée du produit.

**Architecture :** une commande Django unique qui crée un propriétaire, une
configuration de transcription Voxtral, un carnet, puis quatre notes. Chaque
note est ingérée en appelant la **tâche Celery** correspondante en synchrone
(`.apply()`), et non le service nu — c'est la tâche qui écrit
`Page.ingestion_etat` et qui attrape les erreurs proprement.

**Pile :** Django 5 · DRF · Celery · Docling 2.118.0 · PostgreSQL · `uv`.

**Spécification :** `docs/superpowers/specs/2026-08-11-fixtures-sample-design.md`.

---

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

| Fichier | Responsabilité |
|---|---|
| `front/management/commands/charger_fixtures_sample.py` (créer) | La commande entière : propriétaire, carnet, config Voxtral, les quatre chargements, le bilan. |
| `front/tests/test_charger_fixtures_sample.py` (créer) | Les tests rapides, Docling et Voxtral mockés. |
| `hypostasis_extractor/tests/test_fixtures_representatives.py` (modifier) | Y ajouter le seul test lourd, taggé `docling` — le fichier porte déjà ce patron. |

Un seul module de commande : elle fait une chose, et `front/views.py` (3 269
lignes) montre assez ce que coûte l'éparpillement inverse.

---

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

**Fichiers :**
- Créer : `front/management/commands/charger_fixtures_sample.py`
- Créer : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : `core.models.Dossier`, `VisibiliteDossier`, `TranscriptionConfig`.
- Produit : `Command._proprietaire()`, `Command._creer_le_carnet(proprietaire)`,
  `Command._creer_la_config_de_transcription()`, la constante
  `NOM_DU_CARNET = "Documents étalons"`. Les tâches 2 à 5 s'appuient dessus.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Tests de la commande charger_fixtures_sample.
/ Tests for the charger_fixtures_sample command.

LOCALISATION : front/tests/test_charger_fixtures_sample.py
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import Dossier, Page, TranscriptionConfig

User = get_user_model()


class ProprietaireEtCarnetTest(TestCase):
    """Le socle : qui possède les notes étalons, et où elles sont rangées."""

    def test_a_blanc_ne_cree_aucun_utilisateur(self):
        # Une base neuve n'a personne, et le mode a blanc n'y change
        # rien : il annonce ce qu'il ferait, sans l'ecrire.
        # / A dry run announces without writing, users included.
        self.assertEqual(User.objects.count(), 0)

        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        self.assertEqual(User.objects.count(), 0)

    def test_le_superuser_existant_est_reutilise(self):
        superuser_existant = User.objects.create_superuser(
            username="deja_la", email="deja@example.org", password="x",
        )

        sortie = StringIO()
        with patch.object(
            __import__(
                "front.management.commands.charger_fixtures_sample",
                fromlist=["Command"],
            ).Command,
            "_charger_les_documents",
            return_value=None,
        ):
            call_command("charger_fixtures_sample", stdout=sortie)

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.first().pk, superuser_existant.pk)
        self.assertIn("réutilisé", sortie.getvalue())

    def test_sans_utilisateur_la_commande_cree_jonas(self):
        sortie = StringIO()
        with patch.object(
            __import__(
                "front.management.commands.charger_fixtures_sample",
                fromlist=["Command"],
            ).Command,
            "_charger_les_documents",
            return_value=None,
        ):
            call_command("charger_fixtures_sample", stdout=sortie)

        utilisateur_cree = User.objects.get(username="jonas")
        self.assertTrue(utilisateur_cree.is_staff)
        self.assertTrue(utilisateur_cree.check_password("admin1234"))

    def test_le_carnet_est_cree_une_seule_fois(self):
        sortie = StringIO()
        with patch.object(
            __import__(
                "front.management.commands.charger_fixtures_sample",
                fromlist=["Command"],
            ).Command,
            "_charger_les_documents",
            return_value=None,
        ):
            call_command("charger_fixtures_sample", stdout=sortie)
            call_command("charger_fixtures_sample", stdout=sortie)

        self.assertEqual(
            Dossier.objects.filter(name="Documents étalons").count(), 1,
        )

    def test_la_config_voxtral_est_creee_si_la_cle_est_la(self):
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with patch.object(
                __import__(
                    "front.management.commands.charger_fixtures_sample",
                    fromlist=["Command"],
                ).Command,
                "_charger_les_documents",
                return_value=None,
            ):
                call_command("charger_fixtures_sample", stdout=StringIO())

        config = TranscriptionConfig.objects.get(name="Voxtral Mini")
        self.assertTrue(config.is_active)
        self.assertEqual(config.provider, "voxtral")

    def test_sans_cle_mistral_aucune_config_n_est_creee(self):
        # Creer une config qui echouera au premier appel serait pire que
        # ne pas en creer : la transcription retomberait sur le mock, en
        # silence. / A config that will fail is worse than no config.
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("MISTRAL_API_KEY", None)
            with patch.object(
                __import__(
                    "front.management.commands.charger_fixtures_sample",
                    fromlist=["Command"],
                ).Command,
                "_charger_les_documents",
                return_value=None,
            ):
                call_command("charger_fixtures_sample", stdout=StringIO())

        self.assertEqual(TranscriptionConfig.objects.count(), 0)

    def test_a_blanc_n_ecrit_rien(self):
        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        self.assertEqual(Page.objects.count(), 0)
        self.assertEqual(Dossier.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(TranscriptionConfig.objects.count(), 0)
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `CommandError: Unknown command: 'charger_fixtures_sample'`.
C'est le bon échec. Un `AssertionError` à ce stade voudrait dire que la
commande existe déjà — s'arrêter et regarder pourquoi.

- [ ] **Étape 3 : écrire la commande**

```python
"""
Charge les documents etalons de sample/ dans une base vide.
/ Loads the reference documents from sample/ into an empty database.

LOCALISATION : front/management/commands/charger_fixtures_sample.py

POURQUOI CETTE COMMANDE

Une base neuve n'a ni utilisateur, ni carnet, ni note : il n'y a rien a
regarder, donc rien a developper. `sample/` porte les documents etalons
choisis pour couvrir les quatre formes d'entree du produit — capture
web, fichier ecrit, transcription deja faite, audio brut. Cette commande
les transforme en base utilisable.

CE QU'ELLE NE FAIT PAS

Elle n'appelle JAMAIS Docling sur un PDF ni sur un docx. Une commande de
fixtures qui convertit des PDF en masse a fait tomber le serveur le
10 aout 2026. Le PDF a son propre chemin, mesure, une conversion a la
fois.
/ It never runs Docling on a PDF: mass conversion took the server down.

LANCER LA COMMANDE

    docker exec -w /app hypostasia_web uv run python manage.py \\
        charger_fixtures_sample --a-blanc
    docker exec -w /app hypostasia_web uv run python manage.py \\
        charger_fixtures_sample
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Dossier, TranscriptionConfig, VisibiliteDossier

User = get_user_model()

NOM_DU_CARNET = "Documents étalons"

# Memes identifiants que charger_fixtures_demo : un seul mot de passe a
# retenir, quel que soit l'ordre dans lequel les deux commandes tournent.
# / Same credentials as charger_fixtures_demo: one password to remember.
UTILISATEUR_PAR_DEFAUT = {
    "username": "jonas",
    "email": "jonas@demo.hypostasia.org",
    "password": "admin1234",
}


class Command(BaseCommand):
    help = (
        "Charge les documents etalons de sample/ (capture web, markdown, "
        "transcription JSON, audio) dans un carnet de demonstration. "
        "N'appelle jamais Docling sur un PDF ou un docx."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true",
            help="Affiche ce qui serait fait, sans rien ecrire.",
        )

    def handle(self, *args, **options):
        self.a_blanc = options["a_blanc"]

        if self.a_blanc:
            self.stdout.write(self.style.WARNING(
                "MODE A BLANC — rien ne sera ecrit.",
            ))

        proprietaire = self._proprietaire()
        carnet_des_etalons = self._creer_le_carnet(proprietaire)
        self._creer_la_config_de_transcription()

        self._charger_les_documents(proprietaire, carnet_des_etalons)

        if self.a_blanc:
            self.stdout.write(self.style.WARNING(
                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
            ))

    def _proprietaire(self):
        """
        Rend le proprietaire des notes etalons, en le creant s'il le faut.
        / Returns the reference notes' owner, creating one if needed.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Une base neuve n'a AUCUN utilisateur. `charger_fixtures_llm_reel`
        leve une CommandError dans ce cas — c'est precisement le cas que
        cette commande doit savoir traiter.
        / A fresh database has no user at all; this must not be fatal.
        """
        proprietaire_existant = User.objects.filter(
            is_superuser=True,
        ).order_by("pk").first()
        if proprietaire_existant is None:
            proprietaire_existant = User.objects.order_by("pk").first()

        if proprietaire_existant is not None:
            self.stdout.write(
                f"Propriétaire        : {proprietaire_existant.username} (réutilisé)",
            )
            return proprietaire_existant

        self.stdout.write(
            f"Propriétaire        : {UTILISATEUR_PAR_DEFAUT['username']} (créé)",
        )
        if self.a_blanc:
            return None

        proprietaire_cree = User.objects.create_user(
            username=UTILISATEUR_PAR_DEFAUT["username"],
            email=UTILISATEUR_PAR_DEFAUT["email"],
            is_staff=True,
        )
        proprietaire_cree.set_password(UTILISATEUR_PAR_DEFAUT["password"])
        proprietaire_cree.save()
        return proprietaire_cree

    def _creer_le_carnet(self, proprietaire):
        """
        Rend le carnet des documents etalons, en le creant s'il le faut.
        / Returns the reference notebook, creating it if needed.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py
        """
        if self.a_blanc:
            self.stdout.write(f"Carnet              : {NOM_DU_CARNET} (serait créé)")
            return None

        carnet, a_ete_cree = Dossier.objects.get_or_create(
            name=NOM_DU_CARNET, owner=proprietaire,
            defaults={"visibilite": VisibiliteDossier.PUBLIC},
        )
        self.stdout.write(
            f"Carnet              : {NOM_DU_CARNET} — pk={carnet.pk} "
            f"({'créé' if a_ete_cree else 'réutilisé'})",
        )
        return carnet

    def _creer_la_config_de_transcription(self):
        """
        Cree la configuration Voxtral, si la cle API est presente.
        / Creates the Voxtral configuration, if the API key is present.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        SANS CETTE CONFIG, LA TRANSCRIPTION EST MOCKEE EN SILENCE.

        front/tasks.py:633 teste `config.provider == "voxtral"` et retombe
        sinon sur `transcrire_audio_mock`. Sur une base neuve il n'existe
        aucune config : le mp3 produirait un faux verbatim que rien ne
        distinguerait d'une vraie transcription.
        / Without this config the transcription is silently mocked.

        Cle absente : on ne cree RIEN. Une config qui echouera au premier
        appel est pire que pas de config — elle donne l'illusion que la
        chaine est branchee. / An about-to-fail config is worse than none.
        """
        if not os.environ.get("MISTRAL_API_KEY"):
            self.stdout.write(
                "Transcription       : pas de MISTRAL_API_KEY — config non créée",
            )
            return None

        if self.a_blanc:
            self.stdout.write("Transcription       : Voxtral Mini (serait créée)")
            return None

        config, a_ete_creee = TranscriptionConfig.objects.get_or_create(
            name="Voxtral Mini",
            defaults={
                "model_choice": "voxtral-mini-latest",
                "is_active": True,
                "diarization_enabled": True,
                "language": "",
            },
        )
        self.stdout.write(
            f"Transcription       : {config.name} "
            f"({'créée' if a_ete_creee else 'réutilisée'})",
        )
        return config

    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
        """
        Charge les quatre documents etalons. Rempli aux taches 2 et 3.
        / Loads the four reference documents. Filled in by tasks 2 and 3.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py
        """
        return None
```

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 7 tests.

- [ ] **Étape 5 : lancer la commande à blanc, pour de vrai**

```bash
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --a-blanc
```

Attendu : les quatre lignes de bilan, l'avertissement en tête et en pied,
et `Page.objects.count()` toujours à 0.

- [ ] **Étape 6 : point d'arrêt**

Ne rien commiter. Résumer au mainteneur : fichiers créés, tests passés
avec leur nombre, sortie de la commande à blanc.

---

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

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : `_note_deja_presente()`, `_elements_du_resultat()` de la tâche 2.
- Produit : `_charger_la_transcription_json(proprietaire, carnet)`,
  `_charger_le_mp3(proprietaire, carnet)`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class EntreesAudioTest(TestCase):
    """La transcription déjà faite, et la chaîne mp3 complète."""

    def _mocks_docling(self):
        """Les deux tâches Docling, neutralisées ensemble."""
        return (
            patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_capture_web_avec_docling.apply",
            ),
            patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_un_fichier_avec_docling.apply",
            ),
        )

    def test_le_json_devient_une_page_audio_avec_ses_elements(self):
        capture_mockee, fichier_mocke = self._mocks_docling()
        cible_ingestion = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply"
        )
        with capture_mockee, fichier_mocke, patch(cible_ingestion) as ingestion:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_du_json = Page.objects.get(
            original_filename="fake_debat_ia_transcription.json",
        )
        self.assertEqual(page_du_json.source_type, "audio")
        # 12 segments, 3 locuteurs — mesure du fichier versionne.
        # / 12 segments, 3 speakers, measured from the versioned file.
        self.assertEqual(len(page_du_json.transcription_raw["segments"]), 12)
        # LE POINT : la vue d'import, elle, N'appelle PAS cette ingestion
        # (front/views.py:5326). Une note importee par cette porte reste
        # sans element. La commande, elle, doit l'appeler.
        # / The import view never calls this; the command must.
        ingestion.assert_called_once_with(args=[page_du_json.pk])

    def test_sans_mp3_la_transcription_voxtral_n_est_pas_lancee(self):
        capture_mockee, fichier_mocke = self._mocks_docling()
        cible_voxtral = "front.tasks.transcrire_audio_task.apply"
        with capture_mockee, fichier_mocke, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ), patch(cible_voxtral) as voxtral_mocke:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        voxtral_mocke.assert_not_called()
        self.assertFalse(
            Page.objects.filter(
                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
            ).exists(),
        )

    def test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge(self):
        import os

        capture_mockee, fichier_mocke = self._mocks_docling()
        sortie = StringIO()
        cle_sauvegardee = os.environ.pop("MISTRAL_API_KEY", None)
        try:
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
                call_command("charger_fixtures_sample", stdout=sortie)
        finally:
            if cle_sauvegardee is not None:
                os.environ["MISTRAL_API_KEY"] = cle_sauvegardee

        voxtral.assert_not_called()
        self.assertIn("MISTRAL_API_KEY", sortie.getvalue())
        # Les trois autres notes sont chargees malgre tout.
        # / The other three notes are loaded regardless.
        self.assertEqual(Page.objects.count(), 3)

    def test_avec_la_cle_le_mp3_cree_une_page_et_un_job(self):
        import os

        capture_mockee, fichier_mocke = self._mocks_docling()
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
                call_command("charger_fixtures_sample", stdout=StringIO())

        from core.models import TranscriptionJob

        page_du_mp3 = Page.objects.get(
            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
        )
        job = TranscriptionJob.objects.get(page=page_du_mp3)
        self.assertEqual(job.transcription_config.provider, "voxtral")
        voxtral.assert_called_once()
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.EntreesAudioTest --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `Page.DoesNotExist` sur le JSON.

- [ ] **Étape 3 : écrire le chargement des entrées audio**

```python
# Constantes, en tete de fichier
FICHIER_DE_LA_TRANSCRIPTION = "fake_debat_ia_transcription.json"
FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
```

Étendre `_charger_les_documents` :

```python
    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
        self._charger_la_capture_web(proprietaire, carnet_des_etalons)
        self._charger_le_markdown(proprietaire, carnet_des_etalons)
        self._charger_la_transcription_json(proprietaire, carnet_des_etalons)
        self._charger_le_mp3(proprietaire, carnet_des_etalons)
```

```python
    def _charger_la_transcription_json(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue de la transcription deja faite, et l'ingere.
        / Creates the note from the ready-made transcript, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        DOCLING N'INTERVIENT PAS : une transcription diarisee est deja
        structuree. `ingerer_une_transcription_diarisee` la decoupe en
        tours de parole sans charger le moindre modele.
        / Docling plays no part: a diarised transcript is already structured.

        ATTENTION — la vue d'import, elle, N'appelle PAS cette ingestion
        (front/views.py:5326) : une note importee par cette porte reste
        sans element, donc sans gouttiere et sans ancrage possible. C'est
        un trou de l'application, releve le 11 aout 2026. La commande
        appelle l'ingestion explicitement.
        / The import view never triggers this ingestion; we do it here.
        """
        import json

        if self._note_deja_presente(
            carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
        ):
            self.stdout.write("Transcription JSON  : déjà présente — sautée")
            return None

        if self.a_blanc:
            self.stdout.write("Transcription JSON  : serait chargée")
            return None

        from front.services.transcription_audio import construire_html_diarise

        chemin_du_json = REPERTOIRE_SAMPLE / FICHIER_DE_LA_TRANSCRIPTION
        contenu_brut = chemin_du_json.read_text(encoding="utf-8")
        donnees_de_la_transcription = json.loads(contenu_brut)

        html_diarise, texte_brut = construire_html_diarise(
            donnees_de_la_transcription,
        )

        page_du_json = Page.objects.create(
            source_type="audio",
            original_filename=FICHIER_DE_LA_TRANSCRIPTION,
            url=None,
            title="Débat IA — transcription",
            html_original="",
            html_readability=html_diarise,
            text_readability=texte_brut,
            content_hash=hashlib.sha256(
                texte_brut.encode("utf-8"),
            ).hexdigest(),
            transcription_raw=donnees_de_la_transcription,
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(
                contenu_brut.encode("utf-8"),
                name=FICHIER_DE_LA_TRANSCRIPTION,
            ),
        )
        ranger_une_note_dans_un_carnet(
            page_du_json, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_une_transcription_diarisee_en_elements,
        )

        resultat = ingerer_une_transcription_diarisee_en_elements.apply(
            args=[page_du_json.pk],
        )
        self.stdout.write(
            f"Transcription JSON  : {self._elements_du_resultat(resultat)} "
            f"tour(s) de parole",
        )
        return page_du_json

    def _charger_le_mp3(self, proprietaire, carnet_des_etalons):
        """
        Cree la note audio et lance la vraie transcription Voxtral.
        / Creates the audio note and runs the real Voxtral transcription.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        C'est la seule fixture qui eprouve la chaine COMPLETE : mp3 ->
        Voxtral -> tours de parole -> elements. Un appel reseau reel, donc
        aussi un test de bout en bout a chaque chargement.
        / The only fixture exercising the full chain, network call included.

        La tache enchaine elle-meme l'ingestion en elements, mais par
        `.delay()` : sans worker, elle partirait dans le broker et ne se
        ferait jamais. On la rejoue donc ici, en synchrone, si la page
        n'a pas d'element. / The task chains via .delay(); we redo it sync.
        """
        if self.sans_mp3:
            self.stdout.write("Audio mp3           : sauté (--sans-mp3)")
            return None

        if not os.environ.get("MISTRAL_API_KEY"):
            self.stdout.write(self.style.WARNING(
                "Audio mp3           : sauté — pas de MISTRAL_API_KEY. "
                "La transcription serait mockée, pas réelle.",
            ))
            return None

        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MP3):
            self.stdout.write("Audio mp3           : déjà présent — sauté")
            return None

        if self.a_blanc:
            self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
            return None

        from core.models import TranscriptionConfig, TranscriptionJob

        chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
        octets_du_mp3 = chemin_du_mp3.read_bytes()

        page_du_mp3 = Page.objects.create(
            source_type="audio",
            original_filename=FICHIER_DU_MP3,
            url=None,
            title="Palais César — deux locuteurs",
            html_original="",
            html_readability="",
            text_readability="",
            content_hash="",
            status="processing",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(octets_du_mp3, name=FICHIER_DU_MP3),
        )
        ranger_une_note_dans_un_carnet(
            page_du_mp3, carnet_des_etalons, proprietaire,
        )

        config_active = TranscriptionConfig.objects.filter(
            is_active=True,
        ).first()
        job_de_transcription = TranscriptionJob.objects.create(
            page=page_du_mp3,
            transcription_config=config_active,
            audio_filename=FICHIER_DU_MP3,
            status="pending",
        )

        from front.tasks import transcrire_audio_task

        transcrire_audio_task.apply(args=[
            job_de_transcription.pk,
            page_du_mp3.source_file.path,
            config_active.max_speakers if config_active else 5,
            config_active.language if config_active else "fr",
        ])

        page_du_mp3.refresh_from_db()

        # La tache enchaine l'ingestion par `.delay()`. Sans worker, elle
        # n'a pas eu lieu : on la rejoue ici, en synchrone.
        # / The task chained via .delay(); without a worker, redo it here.
        if not page_du_mp3.elements.exists() and page_du_mp3.transcription_raw:
            from hypostasis_extractor.tasks_element import (
                ingerer_une_transcription_diarisee_en_elements,
            )

            ingerer_une_transcription_diarisee_en_elements.apply(
                args=[page_du_mp3.pk],
            )

        self.stdout.write(
            f"Audio mp3 (Voxtral) : {page_du_mp3.elements.count()} "
            f"tour(s) de parole",
        )
        return page_du_mp3
```

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 16 tests.

- [ ] **Étape 5 : lancer la commande complète, appel Voxtral réel compris**

```bash
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample
```

Attendu : quatre lignes chiffrées, dont la capture web à 28 éléments.
Vérifier ensuite en base que la note du mp3 porte bien des locuteurs :

```bash
docker exec -w /app hypostasia_web uv run python manage.py shell -c "
from core.models import Page
for page in Page.objects.filter(source_type='audio'):
    locuteurs = {(e.provenance or {}).get('locuteur') for e in page.elements.all()}
    print(page.original_filename, '|', page.elements.count(), 'éléments |', locuteurs)
"
```

Attendu : des locuteurs nommés, pas `{None}`. `{None}` signifierait que la
provenance n'a pas été posée à l'ingestion.

- [ ] **Étape 6 : point d'arrêt**

Ne rien commiter. Rapporter les quatre comptes et les locuteurs trouvés.

---

## Tâche 4 : `--fichier`, et le refus du PDF et du docx

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : tout ce qui précède.
- Produit : l'option `--fichier`, répétable, et
  `EXTENSIONS_REFUSEES = {".pdf", ".docx"}`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class RefusDesFormatsLourdsTest(TestCase):
    """Le PDF et le docx ne passent pas par cette porte."""

    def test_un_pdf_est_refuse_sans_conversion(self):
        from django.core.management.base import CommandError

        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_fichier) as fichier_mocke:
            with self.assertRaises(CommandError) as contexte:
                call_command(
                    "charger_fixtures_sample",
                    "--fichier", "sample/Etude_Epistemologique_IA.pdf",
                    stdout=StringIO(),
                )

        # Le message doit ORIENTER, pas seulement refuser.
        # / The message must point somewhere, not merely refuse.
        self.assertIn(".pdf", str(contexte.exception))
        fichier_mocke.assert_not_called()

    def test_un_docx_est_refuse_aussi(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "sample/quelque-chose.docx",
                stdout=StringIO(),
            )

    def test_fichier_restreint_le_chargement_a_ce_seul_document(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(cible_fichier):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "PRESENTATION-V3.md",
                stdout=StringIO(),
            )

        self.assertEqual(Page.objects.count(), 1)
        self.assertEqual(
            Page.objects.first().original_filename, "PRESENTATION-V3.md",
        )
        capture_mockee.assert_not_called()

    def test_un_fichier_inconnu_est_refuse_clairement(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as contexte:
            call_command(
                "charger_fixtures_sample",
                "--fichier", "n-existe-pas.md",
                stdout=StringIO(),
            )

        self.assertIn("n-existe-pas.md", str(contexte.exception))
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.RefusDesFormatsLourdsTest \
    --noinput --settings=hypostasia.settings_test_opus
```

Attendu : erreur sur `--fichier` inconnu.

- [ ] **Étape 3 : écrire l'option et le refus**

```python
# En tete de fichier
EXTENSIONS_REFUSEES = {".pdf", ".docx"}

# Les quatre documents etalons, par nom de fichier, dans l'ordre de
# chargement. `--fichier` restreint a un sous-ensemble de cette table.
# / The four reference documents, in loading order.
DOCUMENTS_ETALONS = [
    FICHIER_DE_LA_CAPTURE,
    FICHIER_DU_MARKDOWN,
    FICHIER_DE_LA_TRANSCRIPTION,
    FICHIER_DU_MP3,
]
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
        analyseur_d_arguments.add_argument(
            "--fichier", action="append", default=None, dest="fichiers",
            help=(
                "Ne charger que ce fichier de sample/, au lieu des quatre. "
                "Repetable."
            ),
        )
```

Dans `handle`, avant toute écriture :

```python
        self.fichiers_demandes = self._resoudre_les_fichiers_demandes(
            options["fichiers"],
        )
```

```python
    def _resoudre_les_fichiers_demandes(self, fichiers_de_l_option):
        """
        Rend la liste des fichiers a charger, en refusant les formats lourds.
        / Returns the files to load, refusing the heavy formats.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI REFUSER PLUTOT QU'IGNORER

        Le PDF et le docx n'ont pas ete eprouves par Docling sur cette
        machine. Une commande de fixtures qui convertit des PDF en masse a
        fait tomber le serveur le 10 aout 2026 : 2 031 Mio et 98 s pour
        trois pages. Les laisser passer en silence rejouerait l'incident ;
        les refuser en le disant oriente vers le chemin prevu pour eux.
        / Refusing loudly beats ignoring silently: mass PDF conversion
        took the server down.
        """
        from django.core.management.base import CommandError

        if not fichiers_de_l_option:
            return list(DOCUMENTS_ETALONS)

        fichiers_retenus = []
        for chemin_demande in fichiers_de_l_option:
            nom_du_fichier = os.path.basename(chemin_demande)
            extension = os.path.splitext(nom_du_fichier)[1].lower()

            if extension in EXTENSIONS_REFUSEES:
                raise CommandError(
                    f"« {nom_du_fichier} » est un {extension} : cette "
                    f"commande ne lance jamais Docling sur ce format. Une "
                    f"conversion de PDF coûte 2 031 Mio et 98 s (mesure du "
                    f"11 août 2026) ; une commande de fixtures qui en "
                    f"enchaîne a fait tomber le serveur le 10 août. Passer "
                    f"par `charger_fixtures_pdf`, qui rejoue des fixtures "
                    f"déjà converties, sans Docling.",
                )

            if nom_du_fichier not in DOCUMENTS_ETALONS:
                raise CommandError(
                    f"« {nom_du_fichier} » n'est pas un document étalon. "
                    f"Attendus : {', '.join(DOCUMENTS_ETALONS)}.",
                )

            fichiers_retenus.append(nom_du_fichier)

        return fichiers_retenus
```

Chaque `_charger_*` commence désormais par une garde :

```python
        if FICHIER_DE_LA_CAPTURE not in self.fichiers_demandes:
            return None
```

(et l'équivalent avec `FICHIER_DU_MARKDOWN`, `FICHIER_DE_LA_TRANSCRIPTION`,
`FICHIER_DU_MP3` dans les trois autres méthodes.)

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 20 tests.

- [ ] **Étape 5 : vérifier le refus en vrai**

```bash
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --fichier sample/Etude_Epistemologique_IA.pdf
```

Attendu : le message de refus, et **aucune conversion** — la commande
rend la main immédiatement, pas au bout de 98 s.

- [ ] **Étape 6 : point d'arrêt**

---

## Tâche 5 : `--reset` et son garde-fou

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : `NOM_DU_CARNET`, `_proprietaire()`.
- Produit : l'option `--reset` et `_reinitialiser(proprietaire)`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class ReinitialisationTest(TestCase):
    """--reset rejoue tout, sauf s'il y a des preuves à perdre."""

    def _charger_une_fois(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        cible_audio = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply"
        )
        with patch(cible_capture), patch(cible_fichier), patch(cible_audio):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

    def test_reset_supprime_les_notes_et_les_recharge(self):
        self._charger_une_fois()
        pks_de_depart = set(Page.objects.values_list("pk", flat=True))
        self.assertEqual(len(pks_de_depart), 3)

        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )
            # Le point du reset : on RECONVERTIT, la ou l'idempotence
            # aurait saute. / The point of --reset: convert again.
            self.assertEqual(capture_mockee.call_count, 1)

        self.assertEqual(Page.objects.count(), 3)
        self.assertFalse(
            set(Page.objects.values_list("pk", flat=True)) & pks_de_depart,
        )

    def test_reset_refuse_si_une_note_porte_une_ancre(self):
        from django.core.management.base import CommandError

        # Ces trois modeles vivent dans hypostasis_extractor, PAS dans
        # core.models. / These three live in hypostasis_extractor.
        from hypostasis_extractor.models import (
            AncrageExtraction, ExtractedEntity, ExtractionJob,
        )

        self._charger_une_fois()
        page_avec_ancre = Page.objects.filter(source_type="web").first()
        element = page_avec_ancre.elements.create(
            ordre=0, label="text", texte="un passage", empreinte_contenu="x",
        )
        job = ExtractionJob.objects.create(
            page=page_avec_ancre, name="job de test",
            prompt_description="peu importe", status="completed",
        )
        entite = ExtractedEntity.objects.create(
            job=job, extraction_class="PHENOMENE", extraction_text="une idée",
            start_char=0, end_char=10,
        )
        # Les champs sont debut_dans_element / fin_dans_element — des
        # positions DANS l'element, jamais dans le texte global de la
        # page. / Positions within the element, never page-global.
        AncrageExtraction.objects.create(
            extraction=entite, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=0, fin_dans_element=10,
        )

        nombre_de_pages_avant = Page.objects.count()
        with self.assertRaises(CommandError) as contexte:
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )

        # RIEN ne doit avoir ete supprime — pas de suppression partielle
        # qui laisserait le carnet a moitie vide.
        # / Nothing deleted: no half-emptied notebook.
        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
        self.assertIn(page_avec_ancre.title, str(contexte.exception))

    def test_reset_ne_touche_pas_une_note_rangee_ailleurs(self):
        from core.models import Dossier as CarnetModele
        from core.services.corpus import ranger_une_note_dans_un_carnet

        self._charger_une_fois()
        page_partagee = Page.objects.filter(source_type="web").first()
        proprietaire = page_partagee.owner
        autre_carnet = CarnetModele.objects.create(
            name="Un autre carnet", owner=proprietaire,
        )
        ranger_une_note_dans_un_carnet(page_partagee, autre_carnet, proprietaire)

        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )

        # Elle vit ailleurs : on ne l'emporte pas.
        # / It lives elsewhere: not ours to delete.
        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.ReinitialisationTest --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : erreur sur `--reset` inconnu.

**Note :** si `AncrageExtraction` ou `ExtractedEntity` n'ont pas ces
champs exacts, lire `core/models.py:1670` et suivants et **corriger le
test**, pas le modèle. Le test doit refléter le schéma réel.

- [ ] **Étape 3 : écrire la réinitialisation**

```python
    def add_arguments(self, analyseur_d_arguments):
        # ... les trois options precedentes ...
        analyseur_d_arguments.add_argument(
            "--reset", action="store_true",
            help=(
                "Supprime le carnet etalon et ses notes propres avant de "
                "recharger. Refuse si une note porte des ancres."
            ),
        )
```

Dans `handle`, juste après `proprietaire = self._proprietaire()` :

```python
        if options["reset"]:
            self._reinitialiser(proprietaire)
```

```python
    def _reinitialiser(self, proprietaire):
        """
        Supprime le carnet etalon et les notes qui n'appartiennent qu'a lui.
        / Deletes the reference notebook and the notes filed only in it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI CETTE OPTION EXISTE

        L'idempotence saute ce qui est deja la — y compris l'appel Voxtral,
        qu'on veut precisement pouvoir rejouer a chaque chargement. `--reset`
        est la seule facon de tout refaire.
        / Idempotency skips the Voxtral call we want to replay.

        LE GARDE-FOU N'EST PAS FACULTATIF

        `AncrageExtraction.element` est en PROTECT : supprimer une page qui
        porte des ancres leve ProtectedError. On ne se contente pas de
        laisser l'exception sortir — on VERIFIE D'ABORD, et on refuse tout
        en bloc. Une suppression partielle laisserait le carnet a moitie
        vide, dans un etat que personne n'a voulu.
        / Check first and refuse wholesale: a partial delete is worse.
        """
        from django.core.management.base import CommandError

        from hypostasis_extractor.models import AncrageExtraction

        carnet_existant = Dossier.objects.filter(
            name=NOM_DU_CARNET, owner=proprietaire,
        ).first()
        if carnet_existant is None:
            self.stdout.write("Réinitialisation    : aucun carnet à supprimer")
            return None

        # Les notes rangees UNIQUEMENT dans ce carnet sont a nous. Une note
        # rangee ailleurs aussi appartient a ce quelqu'un d'autre.
        # / Only notes filed solely here are ours to remove.
        notes_a_supprimer = []
        for page in Page.objects.filter(
            appartenances_dossiers__dossier=carnet_existant,
        ).distinct():
            rangee_ailleurs = page.appartenances_dossiers.exclude(
                dossier=carnet_existant,
            ).exists()
            if not rangee_ailleurs:
                notes_a_supprimer.append(page)

        # VERIFIER AVANT DE SUPPRIMER.
        notes_avec_ancres = []
        for page in notes_a_supprimer:
            nombre_d_ancres = AncrageExtraction.objects.filter(
                element__page=page,
            ).count()
            if nombre_d_ancres:
                notes_avec_ancres.append((page, nombre_d_ancres))

        if notes_avec_ancres:
            detail = " ; ".join(
                f"« {page.title} » ({nombre} ancre(s))"
                for page, nombre in notes_avec_ancres
            )
            raise CommandError(
                f"--reset refusé : {detail}. Ces notes portent des "
                f"extractions ancrées, et une ancre est une preuve. Rien "
                f"n'a été supprimé. Retirer les portions d'abord, ou "
                f"recharger dans une base neuve.",
            )

        if self.a_blanc:
            self.stdout.write(
                f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
                f"seraient supprimées",
            )
            return None

        for page in notes_a_supprimer:
            page.delete()
        carnet_existant.delete()

        self.stdout.write(
            f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
            f"supprimée(s), carnet supprimé",
        )
        return None
```

- [ ] **Étape 4 : lancer toute la suite, vérifier qu'elle passe**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 24 tests.

- [ ] **Étape 5 : point d'arrêt**

---

## Tâche 6 : le contrôle réel — 28 éléments sur la capture web

**Fichiers :**
- Modifier : `hypostasis_extractor/tests/test_fixtures_representatives.py`

Ce fichier porte déjà le patron : `DOCLING_DEMANDE = os.environ.get("TESTS_DOCLING") == "1"`,
`@tag("docling")`, et son en-tête explique pourquoi ces tests ne tournent
jamais dans une suite ordinaire.

**Interfaces :**
- Consomme : la commande complète des tâches 1 à 5.

- [ ] **Étape 1 : écrire le test qui échoue**

```python
@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class CaptureWebEtalonTest(TestCase):
    """
    Le contrôle de non-régression de l'extraction HTML.
    / The HTML extraction's non-regression control.

    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py

    Ce compte VERROUILLE les deux correctifs du 11 août 2026 :

    - une image n'est pas un tableau : sans légende elle ne produit
      aucun bloc, au lieu du message « Image not available… » destiné au
      développeur ;
    - un gras ne coupe pas une phrase : les fragments d'un même groupe
      inline se recollent, au lieu de produire deux blocs là où l'auteur
      a écrit une phrase.

    54 éléments dont un `picture` = retour à la version d'avant les
    correctifs. Une cinquantaine de blocs tous en `text` = retour du
    découpage maison par paragraphes.
    / This count locks in the two 11 August fixes.
    """

    def test_la_capture_web_rend_vingt_huit_elements(self):
        from io import StringIO

        from django.core.management import call_command

        from core.models import ElementDocument, Page

        call_command(
            "charger_fixtures_sample",
            "--fichier", "capture-web-badgeons-la-normandie.html",
            stdout=StringIO(),
        )

        page_de_la_capture = Page.objects.get(source_type="web")
        elements = ElementDocument.objects.filter(page=page_de_la_capture)

        self.assertEqual(elements.count(), 28)

        comptes_par_label = {}
        for element in elements:
            comptes_par_label[element.label] = (
                comptes_par_label.get(element.label, 0) + 1
            )

        self.assertEqual(
            comptes_par_label,
            {"section_header": 4, "list_item": 5, "text": 19},
        )

    def test_la_page_ingeree_porte_l_etat_reussie(self):
        """
        L'état d'ingestion ne peut se tester qu'ici.
        / The ingestion state can only be tested here.

        Avec Docling mocké, la tâche ne tourne pas, donc n'écrit pas
        `ingestion_etat` : un test rapide qui l'affirmerait ne
        vérifierait que son propre mock. C'est justement l'écart que
        `charger_fixtures_llm_reel` a laissé passer — ses pages
        gardent un état vide alors que l'écran de lecture l'affiche.
        / A mocked task writes no state; asserting it would test the mock.
        """
        from io import StringIO

        from django.core.management import call_command

        from core.models import EtatIngestion, Page

        call_command(
            "charger_fixtures_sample",
            "--fichier", "capture-web-badgeons-la-normandie.html",
            stdout=StringIO(),
        )

        page_de_la_capture = Page.objects.get(source_type="web")
        self.assertEqual(
            page_de_la_capture.ingestion_etat, EtatIngestion.REUSSIE,
        )
```

- [ ] **Étape 2 : lancer le test SANS le drapeau, vérifier qu'il est sauté**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_fixtures_representatives --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK (skipped=…)`. Aucun modèle Docling ne doit être chargé —
la commande doit rendre la main en quelques secondes, pas en 98 s.

- [ ] **Étape 3 : lancer le test AVEC le drapeau**

```bash
free -h | head -2
docker exec -w /app -e TESTS_DOCLING=1 hypostasia_web uv run python \
    manage.py test hypostasis_extractor.tests.test_fixtures_representatives \
    --noinput --settings=hypostasia.settings_test_opus --tag=docling
```

Attendu : `OK`. Une vraie conversion Docling, quelques dizaines de
secondes.

**Si le compte diffère de 28 :** ne pas ajuster le test au résultat.
S'arrêter, relever le compte obtenu et sa ventilation complète par label,
et le signaler. Un écart signifie que `extraire_les_elements_bruts` a
changé de comportement — c'est exactement ce que ce test existe pour
détecter, et le corriger en silence détruirait sa seule raison d'être.

- [ ] **Étape 4 : point d'arrêt**

Rapporter le compte obtenu et la ventilation par label.

---

## Vérification finale

- [ ] Toute la suite de la commande passe, avec son nombre de tests.
- [ ] La suite ordinaire ne charge aucun modèle Docling (contrôle : durée).
- [ ] Le contrôle taggé `docling` passe, à 28 éléments.
- [ ] La commande tourne de bout en bout sur une base vide, appel Voxtral
      compris, et rend un bilan entièrement chiffré.
- [ ] Relancée juste après, elle ne double rien et ne reconvertit rien.
- [ ] `--a-blanc` sur une base vide n'écrit strictement rien.
- [ ] L'écran de lecture montre une gouttière avec des labels réels sur le
      markdown, et des locuteurs avec minutages sur les deux notes audio.
- [ ] un fichier `CHANGELOG/AAAA-MM-JJ-slug.md` est rédigé (résumé, `---`, comment tester).
- [ ] Aucune opération git n'a été faite.

---

# Addendum du 11 août 2026 — brancher l'ingestion aux notifications

> Demande du propriétaire du dépôt, en cours de session. Ne fait pas partie
> de la spec `2026-08-11-fixtures-sample-design.md` : ces deux tâches
> touchent l'application, pas les fixtures.

## Le constat

Le moteur de notification existe et fonctionne :

```
tâche Celery → notifier_tache_terminee(user_pk, tache_id, tache_type, status)
             → group_send "user_<pk>" → NotificationConsumer.tache_terminee
             → JS : refetch /taches/bouton/
```

**Trois tâches n'y sont pas branchées**, toutes dans
`hypostasis_extractor/tasks_element.py` :

| Tâche | Ligne | Notifie ? |
|---|---|---|
| `ingerer_un_fichier_avec_docling` | 256 | non |
| `ingerer_une_capture_web_avec_docling` | 361 | non |
| `ingerer_une_transcription_diarisee_en_elements` | 427 | non |

Conséquence : importer un PDF déclenche 80 à 164 s de travail (mesure du
11 août) sans que rien ne prévienne l'utilisateur à la fin.

**Second défaut, découvert au même endroit.**
`_destinataires_de_notification(page)` (`front/tasks.py:50`) rend « l'owner
plus les propriétaires des carnets contenant la note ». Son commentaire dit
qu'elle existe parce qu'« avant la phase D, le second carnet d'une note
n'apprenait jamais qu'une synthèse avait tourné ». Or seules la **synthèse**
(`front/tasks.py:1383`, `1414`) et l'**article** (`1615`) l'utilisent :
l'**analyse** (`tasks_element.py:213`) et la **transcription**
(`front/tasks.py:704`, `735`) notifient encore `page.owner` seul. La
correction de la phase D n'a été appliquée qu'à moitié.

## Décision

Pas de nouveau modèle. `Page.ingestion_etat` porte déjà l'état
(`en_attente` / `en_cours` / `reussie` / `echouee`) et fait foi ; un modèle
`JobIngestion` parallèle dupliquerait la vérité et finirait par en diverger.
Il manque seulement un marqueur « lu », symétrique du `notification_lue`
que portent `ExtractionJob` et `TranscriptionJob`.

Le JS n'inspecte pas `tache_type` — il refetch le bouton à chaque message.
Aucun fichier statique à toucher : **ni `collectstatic`, ni bump de `?v=`**.

---

## Tâche 7 : notifier depuis les trois tâches d'ingestion

**Fichiers :**
- Modifier : `hypostasis_extractor/tasks_element.py`
- Modifier : `front/tasks.py` (destinataires de la transcription)
- Test : `hypostasis_extractor/tests/test_notifications_ingestion.py` (créer)

**Interfaces :**
- Consomme : `front.tasks.notifier_tache_terminee`,
  `front.tasks._destinataires_de_notification`.
- Produit : `_prevenir_de_l_ingestion(page, statut)` dans `tasks_element.py`,
  appelée par les trois tâches d'ingestion. `tache_type="ingestion"`,
  `tache_id` = **la clé primaire de la Page** (une ingestion n'a pas de job).

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Les taches d'ingestion previennent-elles l'utilisateur ?
/ Do ingestion tasks notify the user?

LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page
from core.services.corpus import ranger_une_note_dans_un_carnet

User = get_user_model()


class NotificationDeLIngestionTest(TestCase):
    """Une ingestion qui se termine doit se faire connaitre."""

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio")
        self.page = Page.objects.create(
            title="Une note", source_type="web",
            html_original="<p>du texte</p>", html_readability="<p>du texte</p>",
            text_readability="du texte", content_hash="x",
            owner=self.proprietaire,
        )

    def test_une_capture_ingeree_previent_son_proprietaire(self):
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1, 2, 3],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        notification.assert_called_once_with(
            user_pk=self.proprietaire.pk,
            tache_id=self.page.pk,
            tache_type="ingestion",
            status="completed",
        )

    def test_une_ingestion_en_echec_previent_aussi(self):
        # Un echec silencieux est pire qu'un echec : l'utilisateur
        # attendrait indefiniment. / A silent failure is worse.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", side_effect=ValueError("conversion HS"),
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        self.assertEqual(
            notification.call_args.kwargs["status"], "error",
        )

    def test_le_proprietaire_d_un_carnet_est_prevenu_aussi(self):
        # C'est la correction de la phase D, restee a moitie faite :
        # une note rangee dans le carnet d'un collegue doit le prevenir.
        # / The phase D fix, left half-done.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        collegue = User.objects.create_user(username="collegue")
        carnet_du_collegue = Dossier.objects.create(
            name="Le carnet du collègue", owner=collegue,
        )
        ranger_une_note_dans_un_carnet(
            self.page, carnet_du_collegue, self.proprietaire,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {self.proprietaire.pk, collegue.pk})

    def test_une_notification_qui_echoue_ne_casse_pas_l_ingestion(self):
        # Une ingestion reussie ne doit pas devenir un echec parce que
        # le canal de notification est tombe.
        # / A dead channel must not fail a successful ingestion.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch(
            "front.tasks.notifier_tache_terminee",
            side_effect=RuntimeError("channel layer HS"),
        ):
            resultat = ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk],
            )

        self.assertEqual(resultat.result, {"elements": 1})


class DestinatairesDeLAnalyseEtDeLaTranscriptionTest(TestCase):
    """
    La correction de la phase D, appliquee aux deux chemins oublies.
    / The phase D fix, applied to the two forgotten paths.
    """

    def test_l_analyse_previent_les_proprietaires_de_carnets(self):
        from hypostasis_extractor.models import ExtractionJob
        from hypostasis_extractor.tasks_element import _prevenir_l_utilisateur

        proprietaire = User.objects.create_user(username="proprio2")
        collegue = User.objects.create_user(username="collegue2")
        page = Page.objects.create(
            title="Note analysée", source_type="web", html_original="",
            html_readability="", text_readability="", content_hash="y",
            owner=proprietaire,
        )
        carnet = Dossier.objects.create(name="Carnet", owner=collegue)
        ranger_une_note_dans_un_carnet(page, carnet, proprietaire)

        job = ExtractionJob.objects.create(
            page=page, name="j", prompt_description="p", status="completed",
        )

        with patch("front.tasks.notifier_tache_terminee") as notification:
            _prevenir_l_utilisateur(job, "completed")

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {proprietaire.pk, collegue.pk})
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_notifications_ingestion --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `AssertionError: Expected 'notifier_tache_terminee' to be called
once. Called 0 times.` C'est le bon échec — la notification n'existe pas.

- [ ] **Étape 3 : écrire la fonction de notification**

Dans `hypostasis_extractor/tasks_element.py`, à côté de
`_prevenir_l_utilisateur` :

```python
def _prevenir_de_l_ingestion(page, statut):
    """
    Previent les interesses qu'un decoupage en elements s'est termine.
    / Tells the concerned parties an element ingestion has finished.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    POURQUOI CETTE FONCTION

    Une ingestion de PDF prend 80 a 164 s (mesure du 11 aout 2026). Sans
    notification, l'utilisateur qui vient d'importer un document n'a
    aucun moyen de savoir quand son document est pret : il rafraichit au
    jugé. Les trois taches d'ingestion etaient les seules du projet a ne
    rien dire.
    / An ingestion takes up to 164 s; without this, nobody knows when.

    UNE INGESTION N'A PAS DE JOB

    Les analyses ont un ExtractionJob, les transcriptions un
    TranscriptionJob. Une ingestion n'a que sa Page, dont
    `ingestion_etat` porte l'etat. On passe donc la cle primaire de la
    PAGE comme `tache_id` — la vue des taches le sait et cherche au bon
    endroit. / An ingestion has no job: the page's pk is the task id.

    :param page: la Page ingeree
    :param statut: "completed" ou "error"
    """
    from front.tasks import (
        _destinataires_de_notification, notifier_tache_terminee,
    )

    for pk_destinataire in _destinataires_de_notification(page):
        if pk_destinataire is None:
            continue
        try:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=page.pk,
                tache_type="ingestion",
                status=statut,
            )
        except Exception as erreur:
            # Une notification qui echoue ne doit pas faire echouer une
            # ingestion qui, elle, a reussi. Meme principe que partout
            # ailleurs dans ce fichier.
            # / A failed notification must not fail a successful ingestion.
            logger.warning(
                "Page %s : notification d'ingestion non transmise (%s).",
                page.pk, erreur,
            )
```

- [ ] **Étape 4 : appeler la fonction depuis les trois tâches**

Dans chacune des trois — `ingerer_un_fichier_avec_docling`,
`ingerer_une_capture_web_avec_docling`,
`ingerer_une_transcription_diarisee_en_elements` — appeler
`_prevenir_de_l_ingestion(page, "completed")` juste après
`_noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)`, et
`_prevenir_de_l_ingestion(page, "error")` juste après **chaque**
`_noter_l_etat_d_ingestion(..., EtatIngestion.ECHOUEE, ...)`.

Attention : il y a **plusieurs** chemins d'échec par tâche (page sans
fichier source, stockage sans chemin local, exception de conversion). Ils
doivent tous prévenir — un échec silencieux laisse l'utilisateur attendre
indéfiniment. **Ne pas prévenir** sur le retour anticipé « page déjà
ingérée » : rien ne s'est passé, il n'y a rien à annoncer.

- [ ] **Étape 5 : corriger les destinataires des deux chemins oubliés**

Dans `hypostasis_extractor/tasks_element.py`, `_prevenir_l_utilisateur`
prend aujourd'hui `page.owner` seul. Le faire passer par
`_destinataires_de_notification(job_extraction.page)`, en gardant la même
tolérance aux erreurs.

Dans `front/tasks.py`, `transcrire_audio_task` notifie
`page_associee.owner.pk` à deux endroits (succès ~704, erreur ~735). Les
faire passer par `_destinataires_de_notification(page_associee)` — la
fonction est définie dans le même fichier, ligne 50.

- [ ] **Étape 6 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_notifications_ingestion --noinput \
    --settings=hypostasia.settings_test_opus
```

Puis, **séparément**, les suites qui touchent aux notifications, pour
vérifier qu'on n'a rien cassé :

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_corpus_phase_d hypostasis_extractor.tests \
    --noinput --settings=hypostasia.settings_test_opus
```

- [ ] **Étape 7 : point d'arrêt**

Ne rien commiter. Rapporter le nombre de tests et tout test préexistant
qui aurait changé de comportement.

---

## Tâche 8 : afficher les ingestions dans le bouton et le dropdown

**Fichiers :**
- Modifier : `core/models.py` (un champ sur `Page`)
- Créer : une migration de schéma **et** une migration de données
- Modifier : `front/views_taches.py`
- Modifier : `front/templates/front/includes/taches_dropdown.html`
- Test : `front/tests/test_taches_ingestion.py` (créer)

**Interfaces :**
- Consomme : `Page.ingestion_etat`, `Page.ingestion_detail`,
  `Page.ingestion_maj_le`, et le `tache_type="ingestion"` de la tâche 7.
- Produit : `Page.ingestion_notification_lue`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Les ingestions apparaissent-elles dans le bouton et le dropdown ?
/ Do ingestions show up in the tasks button and dropdown?

LOCALISATION : front/tests/test_taches_ingestion.py
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import EtatIngestion, Page

User = get_user_model()


class IngestionDansLesTachesTest(TestCase):

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprio", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_page(self, etat, lue=False):
        return Page.objects.create(
            title="Un document", source_type="file",
            original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.proprietaire,
            ingestion_etat=etat, ingestion_notification_lue=lue,
        )

    def test_une_ingestion_en_cours_compte_dans_le_bouton(self):
        self._creer_page(EtatIngestion.EN_COURS)

        reponse = self.client.get("/taches/bouton/")

        self.assertContains(reponse, "1")
        self.assertEqual(reponse.context["nombre_en_cours"], 1)

    def test_une_ingestion_reussie_non_lue_compte_comme_non_lue(self):
        self._creer_page(EtatIngestion.REUSSIE, lue=False)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 1)

    def test_une_ingestion_deja_lue_ne_compte_plus(self):
        self._creer_page(EtatIngestion.REUSSIE, lue=True)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 0)

    def test_une_page_sans_ingestion_ne_compte_jamais(self):
        # Une page nee avant le moteur ELEMENT, ou un .txt : son
        # ingestion_etat est vide, elle n'est pas une tache.
        # / A page that never requested an ingestion is not a task.
        self._creer_page("")

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 0)
        self.assertEqual(reponse.context["nombre_en_cours"], 0)

    def test_l_ingestion_apparait_dans_le_dropdown(self):
        page = self._creer_page(EtatIngestion.REUSSIE)

        reponse = self.client.get("/taches/dropdown/")

        libelles = [t.libelle_de_tache for t in reponse.context["taches"]]
        self.assertIn("Découpage", libelles)
        self.assertEqual(reponse.context["taches"][0].page_resultat_id, page.pk)

    def test_marquer_lue_une_ingestion(self):
        page = self._creer_page(EtatIngestion.REUSSIE, lue=False)

        self.client.post(
            f"/taches/{page.pk}/marquer-lue/", {"type": "ingestion"},
        )

        page.refresh_from_db()
        self.assertTrue(page.ingestion_notification_lue)

    def test_on_ne_marque_pas_lue_la_page_d_un_autre(self):
        # Doctrine du projet : 404, jamais 403.
        # / Project doctrine: 404, never 403.
        autre = User.objects.create_user(username="autre")
        page_d_autrui = Page.objects.create(
            title="Pas la mienne", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=autre,
            ingestion_etat=EtatIngestion.REUSSIE,
        )

        reponse = self.client.post(
            f"/taches/{page_d_autrui.pk}/marquer-lue/", {"type": "ingestion"},
        )

        self.assertEqual(reponse.status_code, 404)
        page_d_autrui.refresh_from_db()
        self.assertFalse(page_d_autrui.ingestion_notification_lue)
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

Attendu : `TypeError` sur `ingestion_notification_lue`, champ inexistant.

- [ ] **Étape 3 : ajouter le champ et ses deux migrations**

Dans `core/models.py`, sur `Page`, à côté de `ingestion_maj_le` :

```python
    ingestion_notification_lue = models.BooleanField(
        default=False,
        help_text="La fin du decoupage en elements a-t-elle ete vue ? "
                  "Symetrique du notification_lue des jobs d'analyse et "
                  "de transcription (addendum du 11 aout 2026).",
    )
```

Puis :

```bash
docker exec -w /app hypostasia_web uv run python manage.py makemigrations core
```

**Et une migration de données, obligatoire.** Le champ vaut `False` par
défaut : sans elle, **toutes** les pages déjà ingérées apparaîtraient d'un
coup comme des notifications non lues. Le dépôt a déjà ce patron — voir
`core/migrations/0042`, `0047` et `0050`, qui estampillent l'existant et
impriment leur bilan. Écrire une migration qui pose
`ingestion_notification_lue=True` sur toutes les pages existantes dont
`ingestion_etat` n'est pas vide, et qui écrit combien de pages elle a
touchées.

- [ ] **Étape 4 : compter les ingestions dans le bouton**

Dans `_calculer_etat_bouton` (`front/views_taches.py:19`), ajouter aux
trois comptages existants — en cours, non lues, erreurs non lues — leur
équivalent sur `Page` :

```python
    # Les ingestions n'ont pas de job : leur etat vit sur la Page.
    # `ingestion_etat` vide = aucune ingestion demandee (un .txt, une page
    # nee avant le moteur ELEMENT) : ce n'est pas une tache.
    # / Ingestions have no job; an empty state means no task at all.
    nombre_ingestions_en_cours = Page.objects.filter(
        owner=user,
        ingestion_etat__in=[EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS],
    ).count()
    nombre_ingestions_non_lues = Page.objects.filter(
        owner=user,
        ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
        ingestion_notification_lue=False,
    ).count()
```

et les ajouter aux totaux. Pour les erreurs non lues, ajouter au `or`
existant un `Page.objects.filter(owner=user,
ingestion_etat=EtatIngestion.ECHOUEE,
ingestion_notification_lue=False).exists()`.

- [ ] **Étape 5 : lister les ingestions dans le dropdown**

Dans `dropdown()`, les objets passés au template portent quatre attributs
annotés : `type_tache`, `page_resultat_id`, `libelle_de_tache`, plus
`created_at` et `status` lus directement. Une `Page` a bien `created_at`,
mais son `status` est celui de la page, pas de l'ingestion — il faut donc
annoter explicitement :

```python
    # Les ingestions recentes de l'utilisateur. On annote les memes
    # attributs que les jobs pour que le template ne connaisse qu'une
    # seule forme. `status` est traduit depuis ingestion_etat : le
    # `status` propre de la Page parle d'autre chose.
    # / Same annotations as jobs, so the template knows one shape only.
    ingestions_recentes = list(Page.objects.filter(
        owner=request.user,
    ).exclude(ingestion_etat="").order_by("-ingestion_maj_le")[:30])

    for page_ingeree in ingestions_recentes:
        page_ingeree.type_tache = "ingestion"
        page_ingeree.page_resultat_id = page_ingeree.pk
        page_ingeree.libelle_de_tache = "Découpage"
        page_ingeree.notification_lue = page_ingeree.ingestion_notification_lue
        if page_ingeree.ingestion_etat == EtatIngestion.ECHOUEE:
            page_ingeree.status = "error"
        elif page_ingeree.ingestion_etat == EtatIngestion.REUSSIE:
            page_ingeree.status = "completed"
        else:
            page_ingeree.status = "processing"
```

**Attention au tri.** La fusion existante trie sur `created_at`. Pour une
ingestion, c'est la date de création de la **note**, qui peut être bien
antérieure au découpage. Trier les ingestions sur `ingestion_maj_le`, et
donner à chaque objet fusionné une clé de tri commune plutôt que de mélanger
deux sens du temps dans le même `sorted()`. Écrire ce choix en commentaire :
c'est le genre de détail qu'on « corrige » à tort six mois plus tard.

- [ ] **Étape 6 : traiter le cas « ingestion » dans `marquer_lue`**

`marquer_lue` (`front/views_taches.py:174`) aiguille aujourd'hui sur deux
cas. Ajouter le troisième : `tache_type == "ingestion"` →
`get_object_or_404(Page, pk=pk, owner=request.user)` puis
`ingestion_notification_lue = True`. Le `get_object_or_404` filtré sur
`owner` donne bien un **404** pour la page d'autrui, conformément à la
doctrine du projet — jamais un 403.

Faire de même dans `marquer_toutes_lues` (`:197`).

- [ ] **Étape 7 : le template**

Dans `front/templates/front/includes/taches_dropdown.html`, vérifier ce que
le gabarit fait de `type_tache` : s'il choisit une icône ou une couleur par
type, ajouter le cas `ingestion`. **Lire le template avant d'écrire** — s'il
n'utilise que `libelle_de_tache` et `status`, il n'y a rien à changer, et
c'est le résultat le plus probable.

Aucun fichier JS ni CSS n'est touché : **ni `collectstatic`, ni bump `?v=`**.
Un template modifié demande en revanche, si `DEBUG=False` :
`docker exec hypostasia_web supervisorctl restart daphne gunicorn`.

- [ ] **Étape 8 : lancer les tests**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_taches_ingestion --noinput \
    --settings=hypostasia.settings_test_opus
```

Puis, séparément, la suite des tâches existantes pour vérifier qu'aucun
compteur n'a changé de sens.

- [ ] **Étape 9 : vérifier au navigateur**

Importer un document réel, et regarder le bouton passer en « en cours »
puis en « terminé » **sans rafraîchir la page**. C'est la seule preuve qui
compte : les tests vérifient les comptages, pas le fait que le message
traverse vraiment le WebSocket.

- [ ] **Étape 10 : point d'arrêt**

---

# Addendum n°2 du 11 août 2026 — le PDF entre dans les étalons

> Demande du propriétaire du dépôt, en cours de session. **Renverse une
> décision de la spec** (§ 3.5) : le PDF n'est plus refusé, il est chargé
> par défaut.

## Ce qui change, et pourquoi c'est légitime maintenant

Le § 3.5 faisait refuser les `.pdf` parce que Docling n'avait **pas été
éprouvé** sur cette machine, et qu'une commande de fixtures convertissant des
PDF en masse avait fait tomber le serveur le 10 août. Ce motif est levé : la
mesure existe.

| PDF | Pages | Éléments | `provenance.boites` | Durée | RSS pic |
|---|---|---|---|---|---|
| `Etude_Epistemologique_IA.pdf` | 3 | 11, dont **2 `table`** | **11/11** | 98 s | 2 031 Mio |

**Le gain dépasse la fixture.** La passation notait que la base portait
« 0 élément avec `page_no` » — aucun PDF n'avait jamais été ingéré par le
moteur ELEMENT, ce qui rendait le visualiseur PDF impossible à développer
faute de la moindre boîte de coordonnées. Charger ce PDF **remplit enfin ce
trou** : 11 éléments avec `page_no` et boîtes, et le bouton « voir la source »
de la gouttière, déjà codé, a de quoi s'afficher.

**Le docx reste refusé.** Le seul du dépôt (`présentation des open badges.docx`)
est fait de huit diapositives exportées en images : Docling en extrait
**zéro élément**. Une fixture qui ne produit rien n'éprouve rien.

**Le second PDF n'est pas versionné.** `présentation des open badges.pdf`
n'apparaît pas dans `git ls-files sample/` : une fixture non versionnée
n'existe pas pour les autres machines. À versionner d'abord si on le veut.

## Tâche 9 : charger le PDF et créer la base de démonstration

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`
- Modifier : `hypostasis_extractor/tests/test_fixtures_representatives.py`
- Modifier : `docs/superpowers/specs/2026-08-11-fixtures-sample-design.md`
  (le § 3.5 ne dit plus la vérité — l'amender en addendum daté, ne pas le
  réécrire en silence)

**Interfaces :**
- Consomme : `AppartenanceDossierBase`, `BaseDeConnaissances`,
  `_note_deja_presente`, `_elements_du_resultat`.
- Produit : `FICHIER_DU_PDF`, `_charger_le_pdf(proprietaire, carnet)`,
  `_creer_la_base_de_demonstration(proprietaire, carnet)`.

### Le rattachement à la base de connaissances

Le patron exact est dans `front/views_corpus.py:1176` :

```python
AppartenanceDossierBase.objects.get_or_create(
    dossier=carnet, base=base, defaults={"integre_par": utilisateur},
)
```

`BaseDeConnaissances` porte `nom`, `slug`, `description`, `owner`,
`visibilite`. Le `slug` est un `SlugField` **unique** : le poser
explicitement (`demonstration`) plutôt que de le laisser se générer.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class PdfEtBaseDeDemonstrationTest(TestCase):
    """Le PDF entre dans les étalons, et le carnet dans une base."""

    def _mocks_sans_docling(self):
        """Les quatre tâches d'ingestion, neutralisées ensemble."""
        return [
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_une_capture_web_avec_docling.apply"),
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_un_fichier_avec_docling.apply"),
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_une_transcription_diarisee_en_elements.apply"),
        ]

    def test_le_pdf_est_charge_par_defaut(self):
        from contextlib import ExitStack

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        page_du_pdf = Page.objects.get(
            original_filename="Etude_Epistemologique_IA.pdf",
        )
        self.assertEqual(page_du_pdf.source_type, "file")
        # La tâche résout le chemin depuis source_file : sans lui, elle
        # rendrait {"erreur": "page sans fichier source"}.
        # / The task resolves the path from source_file.
        self.assertTrue(page_du_pdf.source_file)

    def test_le_docx_reste_refuse(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as contexte:
            call_command("charger_fixtures_sample",
                         "--fichier", "quelque-chose.docx", stdout=StringIO())

        self.assertIn(".docx", str(contexte.exception))

    def test_le_carnet_est_range_dans_la_base_demonstration(self):
        from contextlib import ExitStack

        from core.models import AppartenanceDossierBase, BaseDeConnaissances

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        base = BaseDeConnaissances.objects.get(nom="Démonstration")
        carnet = Dossier.objects.get(name="Documents étalons")
        self.assertTrue(
            AppartenanceDossierBase.objects.filter(
                dossier=carnet, base=base,
            ).exists(),
        )

    def test_relancer_ne_cree_pas_deux_bases(self):
        from contextlib import ExitStack

        from core.models import BaseDeConnaissances

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        self.assertEqual(
            BaseDeConnaissances.objects.filter(nom="Démonstration").count(), 1,
        )

    def test_a_blanc_ne_cree_pas_la_base(self):
        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        from core.models import BaseDeConnaissances

        self.assertEqual(BaseDeConnaissances.objects.count(), 0)
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.PdfEtBaseDeDemonstrationTest \
    --noinput --settings=hypostasia.settings_test_opus
```

- [ ] **Étape 3 : retirer le PDF des extensions refusées**

`EXTENSIONS_REFUSEES` ne garde que `{".docx"}`. Le commentaire qui la
surplombe doit dire **pourquoi le PDF en est sorti** — mesure du 11 août,
référence à `tmp/benchmark-docling-2026-08-11.md` — et pourquoi le docx y
reste : le seul du dépôt ne produit aucun élément.

Le message de `CommandError` parle encore du PDF : le réécrire pour le seul
docx.

- [ ] **Étape 4 : écrire `_charger_le_pdf`**

Sur le patron **exact** de `_charger_le_markdown` : lecture des octets,
`Page` en `source_type="file"` avec `source_file=ContentFile(...)`,
`ranger_une_note_dans_un_carnet`, puis
`ingerer_un_fichier_avec_docling.apply(args=[page.pk])`.

Une différence à respecter : un PDF est **binaire**. `read_bytes()`, pas
`read_text()`. Et `text_readability` ne peut pas recevoir son contenu — le
laisser vide, les éléments porteront le texte.

Ajouter `FICHIER_DU_PDF` à `DOCUMENTS_ETALONS`, **en dernier** : c'est le
document le plus coûteux, les trois autres doivent être chargés avant lui.

Sa ligne de bilan doit annoncer le coût **avant** de commencer, puisqu'elle
va bloquer une minute et demie :

```
PDF                 : conversion Docling en cours (~98 s, ~2 Gio)…
```

- [ ] **Étape 5 : écrire `_creer_la_base_de_demonstration`**

```python
    def _creer_la_base_de_demonstration(self, proprietaire, carnet_des_etalons):
        """
        Range le carnet des étalons dans une base de connaissances.
        / Files the reference notebook into a knowledge base.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Une base de connaissances est le niveau au-dessus du carnet : elle
        rassemble des carnets pour une communauté. Sans elle, l'écran des
        bases reste vide et rien ne s'y travaille.
        / A knowledge base groups notebooks; without one, its screen is empty.
        """
```

`get_or_create` sur le `nom`, avec `slug="demonstration"` explicite dans les
`defaults` — le `SlugField` est unique, deux exécutions ne doivent pas se
heurter. Puis le `get_or_create` d'`AppartenanceDossierBase`.

Rien ne doit être créé en `--a-blanc`.

- [ ] **Étape 6 : reprendre les tests devenus faux**

Le test `test_un_pdf_est_refuse_sans_conversion` de `RefusDesFormatsLourdsTest`
affirme l'inverse de la nouvelle règle. **Le reprendre, ne pas le supprimer** :
il devient le test du docx. Vérifier aussi les comptes de pages attendus dans
les autres classes — ils passent de 3 à 4 avec `--sans-mp3`.

Ce genre de test qui bascule est le signe d'un vrai changement de
comportement : le dire dans le rapport, ne pas l'ajuster en silence.

- [ ] **Étape 7 : l'étalon PDF, taggé `docling`**

Dans `hypostasis_extractor/tests/test_fixtures_representatives.py`, à côté de
`CaptureWebEtalonTest`, une classe pour le PDF — mêmes décorateurs
`@tag("docling")` et `@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)`.

Elle verrouille ce qu'aucun test ne couvre aujourd'hui :

- **11 éléments**, dont **2 de label `table`** ;
- **11 éléments sur 11** portent `provenance["page_no"]` **et**
  `provenance["boites"]` non vide ;
- les pages vont de 1 à 3.

C'est le premier test du dépôt qui prouve que l'ancrage par coordonnées
fonctionne de bout en bout. **Si un compte diffère, ne pas l'ajuster** :
relever le compte obtenu et le signaler.

- [ ] **Étape 8 : lancer la commande pour de vrai**

```bash
free -h | head -2
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --reset
```

Attendu : cinq documents, dont le PDF à 11 éléments. Vérifier ensuite que la
base porte enfin des coordonnées :

```bash
docker exec -w /app hypostasia_web uv run python manage.py shell -c "
from core.models import ElementDocument
avec_page = ElementDocument.objects.exclude(provenance__page_no=None)
print('elements avec page_no :', avec_page.count())
for e in avec_page[:3]:
    print(' ', e.label, '| page', e.provenance.get('page_no'), '|', len(e.provenance.get('boites') or []), 'boite(s)')
"
```

Attendu : un compte **non nul**. La passation notait « 0 élément avec
`page_no` » — c'est ce chiffre qu'on vient corriger.

- [ ] **Étape 9 : amender la spec**

`docs/superpowers/specs/2026-08-11-fixtures-sample-design.md` § 3.5 dit que
le PDF est refusé. Ce n'est plus vrai. Ajouter un **addendum daté** en fin de
document qui explique le renversement et son motif — la mesure. Ne pas
réécrire le § 3.5 en place : la trace de la décision initiale et de son
renversement a plus de valeur qu'un texte lisse.

- [ ] **Étape 10 : point d'arrêt**
