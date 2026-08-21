"""
Redecoupe les notes avec la recette d'ingestion courante.
/ Re-cuts notes with the current ingestion recipe.

LOCALISATION : hypostasis_extractor/management/commands/reingerer_les_notes.py

POURQUOI CETTE COMMANDE EXISTE. Les elements d'une note sont figes a
l'ingestion : ameliorer la recette ne touche pas ce qui est deja en base.
Une capture ingeree avant le 21 aout 2026 repartait de la page BRUTE —
menus, sommaire, bandeaux compris — et un `.txt` importe n'avait AUCUN
element. Les uns comme les autres le resteront tant que personne ne les
redecoupe.
/ Elements are frozen at ingestion: improving the recipe does not touch
what is already stored.

ELLE DETRUIT LES ELEMENTS ET LES REFAIT. C'est le seul moyen : un element
est identifie par un UUID stable, et rien ne sait « rejouer » un
decoupage en place. Une note dont les elements portent des ANCRES
d'extraction est donc SAUTEE, pas forcee : `AncrageExtraction.element`
est en PROTECT, et passer outre effacerait des preuves.
/ It destroys and rebuilds the elements; notes carrying extraction
anchors are SKIPPED, never forced — that would erase evidence.

ELLE TOURNE ICI, PAS DANS LA FILE. Une commande qu'on lance a la main
doit montrer son resultat ; l'envoyer dans `ingestion_docling` rendrait
la main aussitot sans rien dire. Le prix : les conversions s'enchainent
en serie, une a la fois — ce qui est exactement ce que la file dediee
garantit de son cote.
/ It runs here, not in the queue: a hand-run command must show its
result. Conversions therefore run one at a time, as the queue guarantees.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import EtatIngestion, Page, SourceType, TypeDeNote


class Command(BaseCommand):
    help = (
        "Redecoupe les notes (captures web et fichiers importes) avec la "
        "recette d'ingestion courante."
    )

    def add_arguments(self, parseur):
        parseur.add_argument(
            "--page",
            type=int,
            default=None,
            help="Ne traiter qu'une seule note, par son identifiant.",
        )
        parseur.add_argument(
            "--a-blanc",
            action="store_true",
            help="Montrer ce qui serait fait, sans rien ecrire.",
        )

    def handle(self, *args, **options):
        from hypostasis_extractor.models import AncrageExtraction
        from hypostasis_extractor.services.ingestion_docling import (
            fichier_couvert_par_docling,
            ingerer_un_fichier,
            ingerer_une_capture_web,
            source_html_d_une_capture,
        )
        from hypostasis_extractor.tasks_element import (
            _noter_l_etat_d_ingestion,
        )

        a_blanc = options["a_blanc"]

        # Les notes ORDINAIRES seulement. Un wiki ou une synthese portent
        # aussi source_type='web' sans avoir jamais ete captures, et
        # leur texte est produit par un modele, pas par un decoupage.
        # / Ordinary notes only: wikis and syntheses also carry
        # source_type='web' without ever having been captured.
        notes = Page.objects.filter(
            type_de_note=TypeDeNote.NOTE,
            source_type__in=(SourceType.WEB, SourceType.FILE),
        ).order_by("pk")
        if options["page"]:
            notes = notes.filter(pk=options["page"])

        redecoupees = 0
        sautees = 0

        for note in notes:
            elements_avant = note.elements.count()
            ancres = AncrageExtraction.objects.filter(element__page=note).count()
            etiquette = note.url or note.original_filename or "(sans source)"
            entete = f"  note {note.pk} — {etiquette[:58]}"

            # Ce qu'on saurait redecouper, et d'ou.
            # / What we could re-cut, and from where.
            if note.source_type == SourceType.WEB:
                if not note.url:
                    continue  # ni capture ni import : rien a redecouper
                _html, origine = source_html_d_une_capture(note)
                refus = "aucun HTML a decouper" if origine == "aucune" else ""
            else:
                origine = "le fichier importe"
                if not note.source_file:
                    refus = "aucun fichier source"
                elif not fichier_couvert_par_docling(note.original_filename or ""):
                    refus = f"type non couvert ({note.original_filename})"
                else:
                    refus = ""

            if ancres:
                refus = (
                    f"{ancres} ancre(s) d'extraction. "
                    f"Redecouper effacerait des preuves."
                )

            if refus:
                self.stdout.write(self.style.WARNING(
                    f"{entete}\n     SAUTEE : {refus}"
                ))
                sautees += 1
                continue

            if a_blanc:
                self.stdout.write(
                    f"{entete}\n     {elements_avant} element(s) -> "
                    f"redecoupage depuis {origine}"
                )
                continue

            with transaction.atomic():
                note.elements.all().delete()

            try:
                if note.source_type == SourceType.WEB:
                    elements = ingerer_une_capture_web(note)
                else:
                    elements = ingerer_un_fichier(note, note.source_file.path)
            except Exception as erreur:
                self.stdout.write(self.style.ERROR(
                    f"{entete}\n     ECHEC : {erreur}"
                ))
                sautees += 1
                continue

            # LE HELPER DE LA TACHE, PAS UN `update()` A LA MAIN. Il ne
            # pose pas que l'etat : il reecrit AUSSI `text_readability`,
            # la projection du texte des elements. Un update() direct
            # laissait ce champ sur la projection des ANCIENS elements.
            # / The task's helper, not a hand-written update(): it also
            # rewrites text_readability, the elements' text projection.
            _noter_l_etat_d_ingestion(note.pk, EtatIngestion.REUSSIE)
            self.stdout.write(self.style.SUCCESS(
                f"{entete}\n     {elements_avant} -> {len(elements)} element(s), "
                f"depuis {origine}"
            ))
            redecoupees += 1

        self.stdout.write("")
        if a_blanc:
            self.stdout.write("A blanc : rien n'a ete ecrit.")
        else:
            self.stdout.write(
                f"{redecoupees} note(s) redecoupee(s), {sautees} sautee(s)."
            )
