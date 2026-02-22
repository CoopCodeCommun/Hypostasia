"""
Commande Django pour importer le debat fictif sur l'IA.
/ Django management command to import the fictional AI debate.

Usage :
    uv run python manage.py import_demo_debat
"""

import json
import hashlib
import os

from django.core.management.base import BaseCommand

from core.models import Page, Dossier
from front.services.transcription_audio import construire_html_diarise


class Command(BaseCommand):
    help = "Importe le débat fictif IA (Eric, Laurent, Elinor) comme donnée de démonstration."

    def handle(self, *args, **options):
        # Chemin vers le fichier JSON de transcription dans le dossier demo/
        # / Path to the transcription JSON file in the demo/ folder
        chemin_racine_projet = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
            )
        )
        chemin_json_transcription = os.path.join(
            chemin_racine_projet, "demo", "debat_ia_transcription.json"
        )

        # Charger les segments de transcription depuis le fichier JSON
        # / Load transcription segments from the JSON file
        with open(chemin_json_transcription, "r", encoding="utf-8") as fichier_json:
            donnees_transcription = json.load(fichier_json)

        # Le JSON est au format Voxtral : dict avec model, text, segments
        # / JSON is in Voxtral format: dict with model, text, segments
        segments_transcription = donnees_transcription.get("segments", donnees_transcription)
        self.stdout.write(f"Chargé {len(segments_transcription)} segments depuis le JSON.")

        # Construire le HTML coloré par locuteur et le texte brut
        # (construire_html_diarise accepte dict ou list)
        # / Build speaker-colored HTML and plain text
        # (construire_html_diarise accepts dict or list)
        html_diarise, texte_brut = construire_html_diarise(donnees_transcription)

        # Calculer le hash du contenu pour la deduplication
        # / Compute content hash for deduplication
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        # Creer ou recuperer le dossier de demonstration
        # / Create or retrieve the demo folder
        dossier_demo, dossier_cree = Dossier.objects.get_or_create(
            name="Démonstration",
        )
        if dossier_cree:
            self.stdout.write(self.style.SUCCESS(f"Dossier créé : {dossier_demo.name}"))
        else:
            self.stdout.write(f"Dossier existant : {dossier_demo.name}")

        # Verifier si la page existe deja (par son titre) pour l'idempotence
        # / Check if the page already exists (by title) for idempotency
        titre_page = "Débat IA — Eric, Laurent, Elinor"
        page_existante = Page.objects.filter(title=titre_page).first()

        if page_existante:
            self.stdout.write(f"Page déjà existante (id={page_existante.id}), mise à jour...")
            page_existante.transcription_raw = donnees_transcription
            page_existante.html_readability = html_diarise
            page_existante.text_readability = texte_brut
            page_existante.content_hash = hash_contenu
            page_existante.status = "completed"
            page_existante.save()
            page_importee = page_existante
        else:
            # Creer la page de type audio avec la transcription complete
            # / Create an audio-type page with the full transcription
            page_importee = Page.objects.create(
                title=titre_page,
                url="demo://debat-ia-fictif",
                source_type="audio",
                original_filename="debat_ia_demo.mp3",
                transcription_raw=donnees_transcription,
                html_readability=html_diarise,
                text_readability=texte_brut,
                content_hash=hash_contenu,
                status="completed",
                dossier=dossier_demo,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Page créée : « {page_importee.title} » (id={page_importee.id})"
            ))

        # Afficher le resume de l'import
        # / Display the import summary
        self.stdout.write(f"  - Type : {page_importee.source_type}")
        self.stdout.write(f"  - Segments : {len(segments_transcription)}")
        self.stdout.write(f"  - Dossier : {dossier_demo.name}")
        self.stdout.write(f"  - Status : {page_importee.status}")
        self.stdout.write(self.style.SUCCESS("Import terminé avec succès."))
