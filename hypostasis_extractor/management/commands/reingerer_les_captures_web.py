"""
Redecoupe les captures web avec la recette courante.
/ Re-cuts web captures with the current recipe.

LOCALISATION : hypostasis_extractor/management/commands/reingerer_les_captures_web.py

POURQUOI CETTE COMMANDE EXISTE. Les elements d'une note sont figes a
l'ingestion : ameliorer la recette ne touche pas ce qui est deja en
base. Une capture ingeree avant le 21 aout 2026 repartait de la page
BRUTE — menus, sommaire, bandeaux compris — et le restera tant que
personne ne la redecoupe.
/ Elements are frozen at ingestion: improving the recipe does not touch
what is already stored.

ELLE DETRUIT LES ELEMENTS ET LES REFAIT. C'est le seul moyen : un
element est identifie par un UUID stable, et rien ne sait « rejouer »
un decoupage en place. Une note dont les elements portent des ANCRES
d'extraction est donc SAUTEE, pas forcee : `AncrageExtraction.element`
est en PROTECT, et passer outre effacerait des preuves.
/ It destroys and rebuilds the elements; notes carrying extraction
anchors are SKIPPED, never forced — that would erase evidence.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import EtatIngestion, Page, SourceType, TypeDeNote


class Command(BaseCommand):
    help = (
        "Redecoupe les captures web avec la recette courante "
        "(article Readability quand il est credible, page brute sinon)."
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
            ingerer_une_capture_web,
            source_html_d_une_capture,
        )
        from hypostasis_extractor.tasks_element import (
            _noter_l_etat_d_ingestion,
        )

        a_blanc = options["a_blanc"]

        # Les vraies captures web : une note ordinaire, capturee par
        # l'extension. Un wiki ou une synthese portent aussi
        # source_type='web' sans avoir jamais ete captures.
        # / Real web captures only: wikis and syntheses also carry
        # source_type='web' without ever having been captured.
        captures = Page.objects.filter(
            source_type=SourceType.WEB,
            type_de_note=TypeDeNote.NOTE,
            url__isnull=False,
        ).order_by("pk")
        if options["page"]:
            captures = captures.filter(pk=options["page"])

        if not captures.exists():
            self.stdout.write("Aucune capture web a redecouper.")
            return

        redecoupees = 0
        sautees = 0

        for capture in captures:
            elements_avant = capture.elements.count()
            ancres = AncrageExtraction.objects.filter(
                element__page=capture,
            ).count()
            _html, origine = source_html_d_une_capture(capture)

            entete = f"  note {capture.pk} — {(capture.url or '')[:58]}"

            if ancres:
                self.stdout.write(self.style.WARNING(
                    f"{entete}\n     SAUTEE : {ancres} ancre(s) d'extraction. "
                    f"Redecouper effacerait des preuves."
                ))
                sautees += 1
                continue

            if origine == "aucune":
                self.stdout.write(self.style.WARNING(
                    f"{entete}\n     SAUTEE : aucun HTML a decouper."
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
                capture.elements.all().delete()

            try:
                elements = ingerer_une_capture_web(capture)
            except Exception as erreur:
                self.stdout.write(self.style.ERROR(
                    f"{entete}\n     ECHEC : {erreur}"
                ))
                sautees += 1
                continue

            # LE HELPER DE LA TACHE, PAS UN `update()` A LA MAIN. Il ne
            # pose pas que l'etat : il reecrit AUSSI `text_readability`,
            # la projection du texte des elements. Un update() direct
            # laissait ce champ sur la projection des ANCIENS elements —
            # la note affichait 111 elements propres et gardait, en
            # dessous, le texte des 245 elements bruites.
            # / The task's helper, not a hand-written update(): it also
            # rewrites text_readability, the elements' text projection.
            _noter_l_etat_d_ingestion(capture.pk, EtatIngestion.REUSSIE)
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
