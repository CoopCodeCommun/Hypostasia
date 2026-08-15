"""
Vide la base de donnees et recharge la demonstration.
Utilise pour preparer un environnement propre avant les tests E2E.
/ Empties the database and reloads the demonstration.

LOCALISATION : front/management/commands/reset_demo.py

Usage :
    python manage.py reset_demo
    python manage.py reset_demo --no-input   (pas de confirmation)

ELLE VIDAIT LA BASE ET NE LA RECHARGEAIT PLUS (corrige le 15 aout 2026)

Cette commande faisait `flush` puis `loaddata demo_completes.json`. Or
cette fixture ne se chargeait plus depuis le 21 mars 2026 — cinq mois —
a cause de deux migrations qui ont change le schema sous elle
(`updated_at` sur ExtractedEntity, puis le remplacement de `prenom` par
une cle etrangere sur CommentaireExtraction). La commande DETRUISAIT
donc tout et echouait a recharger : qui la lancait perdait la base sans
rien recuperer.

Ironie de l'affaire : la migration 0020 porte le commentaire « App pas
en production — reset_demo les recree proprement ». Le filet de securite
invoque etait lui-meme rompu, et personne ne pouvait le savoir.
/ It flushed then failed to reload, for five months. The migration that
relied on this safety net had been broken all along.

Elle recharge desormais par le MEME chemin que `install.sh` : les
documents etalons de sample/, puis les extractions de demonstration.
C'est en divergeant de ce chemin qu'elle etait morte sans temoin — un
chemin que personne n'emprunte est un chemin que personne ne teste.
/ It now reloads through the same path as install.sh: a path nobody
walks is a path nobody tests.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Vide la base et recharge la démonstration par le même chemin "
        "que install.sh (documents étalons de sample/ + extractions)."
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
        self.stdout.write("1/4 — Flush de la base de données...")
        call_command("flush", "--no-input", verbosity=0)
        self.stdout.write(self.style.SUCCESS("     Base vidée."))

        # Etape 3 : les documents etalons de sample/, comme install.sh.
        # Le premier chargement apres un flush reconvertit les deux PDF
        # avec Docling : comptez ~3 minutes.
        # / The reference documents, as install.sh does. The first load
        # after a flush reconverts both PDFs (~3 min).
        self.stdout.write("2/4 — Documents étalons (~3 min, conversions PDF)...")
        call_command("charger_fixtures_sample")
        self.stdout.write(self.style.SUCCESS("     Documents chargés."))

        # Etape 4 : les extractions posees dessus, sans appel LLM.
        # / The extractions anchored onto them, with no LLM call.
        self.stdout.write("3/4 — Extractions de démonstration...")
        call_command("charger_extractions_demo")
        self.stdout.write(self.style.SUCCESS("     Extractions posées."))

        # Etape 5 : verification rapide
        # / Step 5: quick verification
        self.stdout.write("4/4 — Vérification...")
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
