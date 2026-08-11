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

import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from core.models import Dossier, Page, TranscriptionConfig, VisibiliteDossier
from core.services.corpus import ranger_une_note_dans_un_carnet

User = get_user_model()

NOM_DU_CARNET = "Documents étalons"

REPERTOIRE_SAMPLE = Path(settings.BASE_DIR) / "sample"

FICHIER_DE_LA_CAPTURE = "capture-web-badgeons-la-normandie.html"
FICHIER_DU_MARKDOWN = "PRESENTATION-V3.md"

# L'article d'origine. Sans url, l'idempotence de la capture porterait
# sur un champ vide et deux captures se confondraient.
# / Without a url, the capture's idempotency key would be empty.
URL_DE_LA_CAPTURE = "https://badgeons-la-normandie.fr/"

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
        analyseur_d_arguments.add_argument(
            "--sans-mp3", action="store_true",
            help="Saute la transcription Voxtral du fichier audio.",
        )

    def handle(self, *args, **options):
        self.a_blanc = options["a_blanc"]
        self.sans_mp3 = options["sans_mp3"]

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
