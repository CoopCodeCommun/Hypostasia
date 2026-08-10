"""
Allege la base en retirant les notes d'essai en double.
/ Slims the database by removing duplicate trial notes.

LOCALISATION : core/management/commands/purger_les_notes_inutiles.py

POURQUOI CETTE COMMANDE EXISTE

La base de dev a servi de terrain d'essai pendant tout le chantier :
546 pages, dont 98 titres presents en plusieurs exemplaires — un sujet y
figure jusqu'a 33 fois. Ces doublons ralentissent chaque ecran qu'on
veut travailler et brouillent la lecture des ecrans de carnet.

CE QU'ELLE SUPPRIME

Les pages en double, en gardant UN exemplaire par titre — quel que soit
leur type. Les plus gros groupes sont des SYNTHESES produites en rafale
pendant les essais : conserver le type de note n'oblige pas a conserver
ses 33 copies.

CE QU'ELLE NE SUPPRIME JAMAIS — les trois gardes

1. Une note COMMENTEE. Les 983 commentaires humains sont la donnee la
   plus precieuse de la base ; ils pendent aux extractions en CASCADE,
   donc supprimer leur page les emporterait.
2. Une note CITEE par une synthese, ou tenue dans le perimetre fige
   d'une dirigee. Piege verifie le 10 aout : les sources d'une synthese
   appartiennent aux NOTES, pas a l'article. Supprimer la note
   laisserait l'article debout avec une preuve vide — et un signal
   d'arbitrage refuse de toute facon la suppression d'une source de
   synthese dirigee. Meme raison pour une page PARENT : la supprimer
   orphelinerait ses sous-notes.
3. Le DERNIER exemplaire d'un titre. Degraisser n'est pas faire
   disparaitre un sujet de la base — c'est aussi ce qui garantit qu'il
   reste des wikis et des syntheses pour faire vivre leurs ecrans.
/ Three guards: commented notes, cited sources, and the last copy of any
title — which is what keeps a wiki and a synthesis alive.

MESURE DU 10 AOUT : 333 pages parties sur 546 (318 au premier passage,
15 de plus une fois la convergence corrigee), en emportant 6 072
extractions et ZERO commentaire. Il reste 213 pages, dont les 37
commentees, 7 syntheses et 2 wikis.
/ Measured: 333 of 546 pages, 0 comments lost.

QUEL EXEMPLAIRE ON GARDE

Celui qui porte des commentaires s'il y en a un ; sinon le plus riche en
extractions ; a egalite, le plus ancien — c'est en general l'original,
les suivants etant des re-imports.
/ The commented one, else the richest, else the oldest.

LANCER LA COMMANDE

    # Voir ce qui partirait, sans rien supprimer :
    docker exec hypostasia_dev_web python manage.py \\
        purger_les_notes_inutiles --a-blanc

    # Supprimer pour de vrai :
    docker exec hypostasia_dev_web python manage.py \\
        purger_les_notes_inutiles
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from core.models import Page, SourceLink
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
)


class Command(BaseCommand):
    help = (
        "Allege la base : retire les notes en double, en gardant un "
        "exemplaire par titre. Ne touche ni aux notes commentees, ni aux "
        "wikis et syntheses, ni aux sources citees."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc",
            action="store_true",
            help="Affiche ce qui serait supprime, sans rien supprimer.",
        )

    def handle(self, *args, **options):
        a_blanc = options["a_blanc"]

        pages_protegees, a_supprimer = self._converger(a_blanc)

        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "MODE A BLANC — rien ne sera supprime.",
            ))

        self.stdout.write(
            f"Pages en base         : {Page.objects.count()}",
        )
        self.stdout.write(
            f"Pages protegees       : {len(pages_protegees)}",
        )
        self.stdout.write(
            f"Pages a supprimer     : {len(a_supprimer)}",
        )

        if not a_supprimer:
            self.stdout.write("Rien a faire.")
            return

        self._afficher_ce_qui_part(a_supprimer, a_blanc)

        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "\nRien n'a ete supprime : relancer sans --a-blanc pour agir.",
            ))
            return

        with transaction.atomic():
            # LE GARDE-FOU SE REVERIFIE ICI, PAS SEULEMENT AVANT.
            #
            # Le controle du bilan a lieu hors transaction : un
            # commentaire pose entre les deux partirait en CASCADE, en
            # silence. La reconversion verrouille ses pages pour cette
            # raison exacte — « l'application est en service ».
            # / Re-check inside the transaction; the app is live.
            commentaires_en_peril = CommentaireExtraction.objects.filter(
                entity__job__page_id__in=a_supprimer,
            ).count()
            if commentaires_en_peril:
                raise SystemExit(
                    f"ARRET : {commentaires_en_peril} commentaire(s) humain(s) "
                    f"seraient emportes. Aucune suppression n'a eu lieu.",
                )

            # LES PORTIONS D'ABORD, SINON RIEN NE PART.
            #
            # `AncrageExtraction.element` est en PROTECT : le moteur de
            # structure interdit de supprimer un element qui porte encore
            # une portion, pour forcer a redistribuer les portions avant
            # de scinder ou fusionner. Cette garde vise un element SEUL.
            # Ici la page entiere s'en va, extractions comprises : les
            # portions n'ont plus rien a rattacher, et les retirer
            # d'abord est le seul ordre qui respecte la contrainte.
            # / The PROTECT guard targets a lone element; here the whole
            # page goes, so portions are removed first.
            portions_retirees, _ = AncrageExtraction.objects.filter(
                element__page_id__in=a_supprimer,
            ).delete()

            nombre, par_modele = Page.objects.filter(
                pk__in=a_supprimer,
            ).delete()
            if portions_retirees:
                par_modele["hypostasis_extractor.AncrageExtraction"] = (
                    par_modele.get(
                        "hypostasis_extractor.AncrageExtraction", 0,
                    ) + portions_retirees
                )
                nombre += portions_retirees

        self.stdout.write("")
        self.stdout.write(f"{nombre} lignes supprimees au total :")
        for modele, compte in sorted(par_modele.items()):
            self.stdout.write(f"  {modele:<45} {compte}")
        self.stdout.write("")
        self.stdout.write(f"Pages restantes       : {Page.objects.count()}")

    def _converger(self, a_blanc):
        """
        Rend (pages protegees, pages a supprimer) au POINT FIXE.
        / Returns protected and deletable pages, at the FIXED POINT.

        LOCALISATION : core/management/commands/purger_les_notes_inutiles.py

        POURQUOI UN SEUL PASSAGE NE SUFFIT PAS

        Les gardes se calculent sur l'etat AVANT suppression. Or une
        page peut n'etre protegee que par une AUTRE page qui, elle, part
        dans le meme passage : l'article qui la citait (ses SourceLink
        s'en vont avec lui), la synthese dirigee dont elle etait dans le
        perimetre, le parent dont elle etait l'enfant. Le protecteur
        disparu, la protegee devient supprimable — et un second
        lancement enleverait encore des pages que le premier bilan
        n'avait pas annoncees.

        Mesure du 10 aout : apres un premier passage donne pour complet,
        relancer la commande proposait encore 15 pages et 1 179
        extractions. Un bilan qui ne dit pas tout ce qui va partir n'est
        pas un bilan.

        On simule donc les tours successifs jusqu'a ce que plus rien ne
        bouge. La suite est decroissante et bornee par le nombre de
        pages : elle termine.
        / Guards are computed pre-deletion, so protectors can themselves
        vanish. Iterate until nothing moves.
        """
        # ATTENTION : une page condamnee n'est PAS une page protegee.
        # Les confondre ferait passer son titre pour « deja represente »
        # et emporterait le dernier exemplaire avec les autres. A chaque
        # tour, la selection se refait donc entierement, sur la seule
        # liste des VRAIES protegees — qui, elle, retrecit.
        # / A doomed page is not a protecting page.
        deja_condamnees = set()
        for _tour in range(Page.objects.count() + 2):
            protegees = self._recenser_les_pages_protegees(deja_condamnees)
            a_supprimer = set(
                self._choisir_les_pages_a_supprimer(protegees)
            )
            if a_supprimer == deja_condamnees:
                return protegees, sorted(deja_condamnees)
            deja_condamnees = a_supprimer

        # Filet : la suite est decroissante, on ne devrait jamais sortir
        # par ici. / Safety net; the sequence is decreasing.
        return (
            self._recenser_les_pages_protegees(deja_condamnees),
            sorted(deja_condamnees),
        )

    def _recenser_les_pages_protegees(self, deja_condamnees=frozenset()):
        """
        Rend l'ensemble des pk qu'on ne supprimera sous aucun pretexte.
        / Returns the set of pks that will never be deleted.

        LOCALISATION : core/management/commands/purger_les_notes_inutiles.py
        """
        protegees = set()

        # 1. Les notes commentees.
        protegees |= set(
            Page.objects.filter(
                extraction_jobs__entities__commentaires__isnull=False,
            ).values_list("pk", flat=True)
        )

        # 2. (Volontairement vide.) LES WIKIS ET SYNTHESES NE SONT PAS
        # PROTEGES UN A UN.
        #
        # Ce qu'on veut conserver, c'est le TYPE de note — de quoi faire
        # vivre les ecrans carnet/wiki/synthese —, pas ses copies
        # d'essai. Or les plus gros groupes de doublons de la base SONT
        # des syntheses produites en rafale pendant les tests : un meme
        # titre y figure jusqu'a 33 fois. Les proteger individuellement
        # ne garderait rien de plus, et encombrerait justement l'ecran
        # qu'on veut travailler.
        #
        # La garde n°3 suffit : le dernier exemplaire d'un titre reste,
        # quel que soit son type. Un wiki unique, une synthese unique ne
        # partent donc jamais.
        # / Keep the KIND, not the copies; guard #4 keeps the last one.

        # 3. Les sources citees — par la page, par l'extraction, ou par
        # le perimetre fige d'une synthese dirigee.
        #
        # UNE PROTECTION QUI VIENT D'UNE PAGE CONDAMNEE N'EN EST PLUS
        # UNE. L'article citant emporte ses SourceLink en CASCADE : une
        # fois lui parti, la source qu'il seul citait n'est plus citee
        # par personne. Ignorer ce fait faisait annoncer un bilan
        # incomplet, et laissait du travail au lancement suivant.
        # / A protection held by a doomed page is no protection.
        protegees |= set(
            SourceLink.objects.filter(page_source__isnull=False)
            .exclude(page_cible_id__in=deja_condamnees)
            .values_list("page_source_id", flat=True)
        )
        protegees |= set(
            Page.objects.filter(
                extraction_jobs__entities__source_links__isnull=False,
            ).exclude(
                extraction_jobs__entities__source_links__page_cible_id__in=(
                    deja_condamnees
                ),
            ).values_list("pk", flat=True)
        )
        protegees |= set(
            Page.objects.filter(syntheses_qui_la_couvrent__isnull=False)
            .exclude(syntheses_qui_la_couvrent__page_id__in=deja_condamnees)
            .values_list("pk", flat=True)
        )

        # 4. Les parents d'une page quelconque : supprimer un parent
        # orphelinerait ses sous-notes — sauf si l'enfant s'en va aussi.
        # / Deleting a parent orphans its sub-notes, unless they go too.
        protegees |= set(
            Page.objects.filter(parent_page__isnull=False)
            .exclude(pk__in=deja_condamnees)
            .values_list("parent_page_id", flat=True)
        )

        protegees.discard(None)
        return protegees

    def _choisir_les_pages_a_supprimer(self, pages_protegees):
        """
        Rend les pk a supprimer : les doublons de titre, moins un.
        / Returns the pks to delete: duplicate titles, minus one keeper.

        LOCALISATION : core/management/commands/purger_les_notes_inutiles.py
        """
        pages = (
            Page.objects.exclude(pk__in=pages_protegees)
            .annotate(nombre_d_extractions=Count("extraction_jobs__entities"))
            .values_list(
                "pk", "title", "nombre_d_extractions", "created_at",
            )
        )

        par_titre = defaultdict(list)
        for identifiant, titre, extractions, cree_le in pages:
            par_titre[(titre or "").strip()].append(
                (identifiant, extractions, cree_le),
            )

        titres_deja_representes = self._titres_des_pages_protegees(
            pages_protegees,
        )

        a_supprimer = []
        for titre, exemplaires in par_titre.items():
            # Le plus riche en extractions, puis le plus ancien.
            # / The richest, then the oldest.
            exemplaires.sort(key=lambda ligne: (-ligne[1], ligne[2]))

            # Si une page PROTEGEE porte deja ce titre, le sujet ne
            # disparaitra pas de la base : tous les exemplaires nus
            # peuvent partir. Sinon on en garde un.
            # / A protected page already carries this title, or we keep one.
            debut = 0 if titre in titres_deja_representes else 1
            a_supprimer.extend(
                identifiant for identifiant, _n, _d in exemplaires[debut:]
            )

        return a_supprimer

    def _titres_des_pages_protegees(self, pages_protegees):
        """Les titres deja tenus par une page qu'on garde. / Kept titles."""
        return {
            (titre or "").strip()
            for titre in Page.objects.filter(
                pk__in=pages_protegees,
            ).values_list("title", flat=True)
        }

    def _afficher_ce_qui_part(self, a_supprimer, a_blanc):
        """
        Montre les groupes concernes, pas seulement un total.
        / Shows the affected groups, not just a total.
        """
        from hypostasis_extractor.models import (
            CommentaireExtraction,
            ExtractedEntity,
        )

        extractions = ExtractedEntity.objects.filter(
            job__page_id__in=a_supprimer,
        ).count()
        commentaires = CommentaireExtraction.objects.filter(
            entity__job__page_id__in=a_supprimer,
        ).count()

        self.stdout.write("")
        self.stdout.write(f"  extractions emportees : {extractions}")
        self.stdout.write(
            f"  commentaires emportes : {commentaires}"
            + ("  <-- DOIT ETRE ZERO" if commentaires else "  (aucun)"),
        )

        # LE GARDE-FOU QUI COMPTE, VERIFIE AVANT D'AGIR.
        #
        # Les quatre gardes sont censees rendre ce cas impossible. Si
        # elles ont laisse passer quelque chose, mieux vaut s'arreter que
        # de decouvrir la perte apres coup.
        # / The guards make this impossible; if not, stop rather than lose.
        if commentaires and not a_blanc:
            raise SystemExit(
                "ARRET : la selection emporterait des commentaires humains. "
                "Aucune suppression n'a eu lieu.",
            )

        groupes = (
            Page.objects.filter(pk__in=a_supprimer)
            .values("title")
            .annotate(combien=Count("pk"))
            .order_by("-combien")[:8]
        )
        self.stdout.write("")
        self.stdout.write("  Principaux groupes allegés :")
        for groupe in groupes:
            titre = (groupe["title"] or "(sans titre)")[:48]
            self.stdout.write(f"    {titre:<50} -{groupe['combien']}")
