"""
Flush la base de donnees et recharge les fixtures de demonstration.
Utilise pour preparer un environnement propre avant les tests E2E.
/ Flush the database and reload demo fixtures.
/ Used to prepare a clean environment before E2E tests.

LOCALISATION : front/management/commands/reset_demo.py

Usage :
    uv run python manage.py reset_demo
    uv run python manage.py reset_demo --no-input   (pas de confirmation)
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Flush la base et recharge les fixtures de démonstration "
        "(front/fixtures/demo_completes.json)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Pas de confirmation interactive.",
        )

    def handle(self, *args, **options):
        mode_sans_confirmation = options.get("no_input", False)

        # Etape 1 : confirmation manuelle sauf si --no-input
        # / Step 1: manual confirmation unless --no-input
        if not mode_sans_confirmation:
            reponse = input(
                "⚠ Ceci va SUPPRIMER TOUTES les données et recharger les fixtures.\n"
                "Continuer ? [y/N] "
            )
            if reponse.lower() not in ("y", "yes", "o", "oui"):
                self.stdout.write("Annulé.")
                return

        # Etape 2 : flush complet de la base
        # / Step 2: full database flush
        self.stdout.write("1/3 — Flush de la base de données...")
        call_command("flush", "--no-input", verbosity=0)
        self.stdout.write(self.style.SUCCESS("     Base vidée."))

        # Etape 3 : chargement des fixtures de demonstration
        # / Step 3: load demo fixtures
        self.stdout.write("2/3 — Chargement des fixtures...")
        chemin_fixture = "front/fixtures/demo_completes.json"
        call_command("loaddata", chemin_fixture, verbosity=1)
        self.stdout.write(self.style.SUCCESS("     Fixtures chargées."))

        # Etape 4 : verification rapide
        # / Step 4: quick verification
        self.stdout.write("3/3 — Vérification...")
        from core.models import Dossier, Page
        from hypostasis_extractor.models import (
            ExtractedEntity,
            ExtractionJob,
            CommentaireExtraction,
        )

        nombre_dossiers = Dossier.objects.count()
        nombre_pages = Page.objects.count()
        nombre_jobs = ExtractionJob.objects.filter(status="completed").count()
        nombre_entites = ExtractedEntity.objects.filter(masquee=False).count()
        nombre_commentaires = CommentaireExtraction.objects.count()

        self.stdout.write(
            f"     {nombre_dossiers} dossiers | {nombre_pages} pages | "
            f"{nombre_jobs} jobs | {nombre_entites} entités | "
            f"{nombre_commentaires} commentaires"
        )
        self.stdout.write(self.style.SUCCESS("\nReset terminé. Prêt pour les tests E2E."))
