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
