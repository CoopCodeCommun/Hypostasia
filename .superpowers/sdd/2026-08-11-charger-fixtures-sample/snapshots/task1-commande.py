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
