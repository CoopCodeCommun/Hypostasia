"""
Donne aux elements audio existants leur locuteur et leur minutage.
/ Gives existing audio elements their speaker and timing.

LOCALISATION : core/management/commands/enrichir_la_provenance_audio.py

POURQUOI CETTE COMMANDE PLUTOT QU'UNE RE-INGESTION

Les pages audio deja en base ont des elements — mais decoupes par la
RECONVERSION, sur les paragraphes du texte a plat, pas sur les tours de
parole. Ils n'ont donc aucune provenance, et leur gouttiere reste muette
la ou l'etalon affiche « Jean S. 00:01 ».

Re-ingerer les reparerait, mais detruirait tout : sur la seule page 40,
466 ancres et 479 extractions pendent a ces elements. On ne casse pas
une preuve pour gagner une etiquette.

On APPARIE donc les elements existants aux segments de la
transcription, sans toucher ni a leur texte ni a leurs ancres : seule
`provenance` est remplie. C'est le meme principe que la reconversion —
retrouver ce qui est deja la plutot que refaire.
/ Matching beats re-ingesting: 466 anchors hang from those elements.

COMMENT L'APPARIEMENT MARCHE

Les elements ont ete decoupes DANS le texte que les segments ont
produit : leurs textes se suivent donc dans le meme ordre. On avance en
parallele, en consommant les segments dont le texte se retrouve dans
l'element courant. Le premier segment consomme donne le locuteur et le
debut, le dernier donne la fin.

Un element auquel aucun segment ne correspond garde une provenance vide
— on ne lui invente pas un locuteur.
/ Both follow the same order; consume segments into the current element.

LANCER LA COMMANDE

    docker exec hypostasia_dev_web python manage.py \\
        enrichir_la_provenance_audio --a-blanc
    docker exec hypostasia_dev_web python manage.py \\
        enrichir_la_provenance_audio
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Page


class Command(BaseCommand):
    help = (
        "Remplit la provenance (locuteur, debut, fin) des elements des "
        "pages audio, depuis leur transcription diarisee, sans toucher "
        "aux ancres existantes."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true",
            help="Affiche ce qui serait fait, sans rien ecrire.",
        )
        analyseur_d_arguments.add_argument(
            "--page", type=int, default=None,
            help="Ne traiter qu'une page, par son identifiant.",
        )

    def handle(self, *args, **options):
        a_blanc = options["a_blanc"]

        pages = Page.objects.filter(
            source_type="audio", elements__isnull=False,
        ).distinct().order_by("pk")
        if options["page"] is not None:
            pages = pages.filter(pk=options["page"])

        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "MODE A BLANC — rien ne sera ecrit.",
            ))

        total_enrichis = total_orphelins = pages_traitees = 0
        for page in pages:
            enrichis, orphelins = self._enrichir_une_page(page, a_blanc)
            if enrichis or orphelins:
                pages_traitees += 1
                self.stdout.write(
                    f"  page {page.pk} : {enrichis} element(s) enrichi(s), "
                    f"{orphelins} sans segment",
                )
            total_enrichis += enrichis
            total_orphelins += orphelins

        self.stdout.write("")
        self.stdout.write(f"Pages audio traitees   : {pages_traitees}")
        self.stdout.write(f"Elements enrichis      : {total_enrichis}")
        self.stdout.write(
            f"Elements sans segment  : {total_orphelins} "
            f"(provenance laissee vide, aucun locuteur invente)",
        )
        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
            ))

    def _enrichir_une_page(self, page, a_blanc):
        """
        Apparie les elements d'une page a ses segments.
        / Matches a page's elements to its segments.

        LOCALISATION : core/management/commands/enrichir_la_provenance_audio.py

        :return: (nombre enrichi, nombre sans segment)
        """
        transcription = page.transcription_raw
        if not isinstance(transcription, dict):
            return 0, 0

        segments = [
            segment for segment in (transcription.get("segments") or [])
            if isinstance(segment, dict) and (segment.get("text") or "").strip()
        ]
        if not segments:
            return 0, 0

        elements = list(page.elements.order_by("ordre"))

        # UNE PAGE DEJA INGEREE PAR TOURS DE PAROLE N'A RIEN A GAGNER.
        #
        # Ses elements portent deja leur locuteur et leur minutage, poses
        # a l'ingestion. Les reapparier n'ajouterait rien et pourrait
        # abimer ce qui est juste : l'appariement est une reparation
        # pour l'existant, pas une seconde source de verite.
        # Constate en essayant : sur une page fraichement ingeree,
        # l'appariement rendait « 1 enrichi, 11 sans segment ».
        # / Already-ingested pages have nothing to gain and much to lose.
        if any((element.provenance or {}).get("locuteur") for element in elements):
            return 0, 0

        rang = 0
        a_ecrire = []
        orphelins = 0
        rang_bloque_depuis = 0

        for element in elements:
            rang_avant = rang
            consommes, rang = self._segments_de_l_element(
                element.texte, segments, rang,
            )
            if not consommes:
                orphelins += 1
                # UN CURSEUR QUI NE BOUGE PLUS EMPOISONNE TOUTE LA SUITE.
                #
                # Si un segment chevauche une frontiere d'element, il ne
                # se retrouve dans aucun des deux : `rang` cale, et TOUS
                # les elements suivants deviennent orphelins. Sans cette
                # alerte, la commande rendrait « 200 sans segment » sans
                # dire que c'est UN desalignement, pas 200 accidents.
                # / A stuck cursor orphans everything after it: say so.
                rang_bloque_depuis += 1
                if rang_bloque_depuis == 3:
                    self.stdout.write(self.style.WARNING(
                        f"    page {page.pk} : l'appariement cale au "
                        f"segment {rang} — les elements suivants seront "
                        f"laisses sans provenance plutot que mal attribues.",
                    ))
                continue
            rang_bloque_depuis = 0
            a_ecrire.append((element, {
                "locuteur": consommes[0].get("speaker") or None,
                "debut": consommes[0].get("start"),
                "fin": consommes[-1].get("end"),
            }))

        if a_blanc:
            return len(a_ecrire), orphelins

        with transaction.atomic():
            for element, provenance in a_ecrire:
                element.provenance = provenance
                element.save(update_fields=["provenance"])

        return len(a_ecrire), orphelins

    def _segments_de_l_element(self, texte_de_l_element, segments, rang):
        """
        Consomme les segments qui composent cet element.
        / Consumes the segments making up this element.

        LOCALISATION : core/management/commands/enrichir_la_provenance_audio.py

        On avance TANT QUE le texte du segment se retrouve dans
        l'element, en partant de la ou le precedent s'est arrete. Le
        premier segment qui ne s'y retrouve pas appartient a l'element
        suivant : on s'arrete sans le consommer.
        / Stop at the first segment that does not fit: it belongs to the
        next element.
        """
        consommes = []
        curseur = 0
        while rang < len(segments):
            texte_du_segment = (segments[rang].get("text") or "").strip()
            position = texte_de_l_element.find(texte_du_segment, curseur)
            if position == -1:
                break
            consommes.append(segments[rang])
            curseur = position + len(texte_du_segment)
            rang += 1
        return consommes, rang
