"""
La passe de nuit : le moteur met les wikis a jour tout seul.
/ The nightly pass: the engine updates the wikis on its own.

LOCALISATION : front/management/commands/mettre_a_jour_les_wikis.py

CE QU'ELLE FAIT. Pour chaque wiki dont le perimetre offre des
extractions que l'article n'a PAS reprises, elle demande au redacteur
des operations de section, et les applique. Elle passe par le meme
applieur que l'ecran, donc par les memes controles (§ 6.2/6.3) : un
titre halluciné, une affirmation sans preuve, une source hors
perimetre sont rejetes ici comme ailleurs, et le rejet s'ecrit dans
l'historique.

CE QU'ELLE NE FAIT JAMAIS. Regenerer un article. Elle n'a aucun chemin
vers `produire_un_wiki_task` — un wiki se suit, il ne se refait pas.

ELLE APPELLE UN VRAI MODELE, DONC ELLE EST FACTUREE : un appel au
redacteur par wiki examine. `--maximum` borne la nuit, et ce qui est
ecarte par cette borne est COMPTE — une troncature muette se lirait
comme une couverture complete.

SEQUENTIELLE, ET NON MISE EN FILE. Un appel a la fois : le cout reste
previsible, et la file des juges (concurrence 1, `nice -n 19`) ne se
remplit pas d'un coup. La contrepartie est assumee : la commande dure
ce que durent ses appels.
/ Billed, sequential, bounded, and never regenerating.

FLUX :
1. ouvre une `PasseDeNuit` — c'est elle que le recapitulatif du matin
   interroge avant de partir (le mail suit TOUJOURS le run) ;
2. liste les wikis a examiner (ceux qui ont des extractions ecartees) ;
3. met chacun a jour, une erreur n'arretant jamais les suivants ;
4. ferme la passe, avec ses comptes.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import PasseDeNuit, RoleDeModele, Wiki
from core.services.modeles_par_role import modele_du_role
from core.services.passe_de_nuit import passe_en_cours
from core.services.synthese import extractions_ecartees


class Command(BaseCommand):
    help = (
        "Met a jour les wikis dont le perimetre a du neuf. "
        "Appelle un vrai modele : c'est facture."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--maximum", type=int, default=0,
            help="Nombre maximum de wikis a mettre a jour (0 = tous). "
                 "Ce qui est ecarte par cette borne est compte et dit.",
        )
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true", dest="a_blanc",
            help="N'appelle aucun modele et n'ecrit rien : dit "
                 "seulement quels wikis seraient mis a jour.",
        )
        analyseur_d_arguments.add_argument(
            "--meme-si-une-passe-tourne", action="store_true",
            dest="meme_si_une_passe_tourne",
            help="Demarre meme si une autre passe est en cours. La "
                 "facture double, et deux tours se disputent le meme "
                 "article : a n'utiliser qu'en connaissance de cause.",
        )

    def handle(self, *arguments, **options):
        maximum = options.get("maximum") or 0
        a_blanc = options.get("a_blanc", False)

        # DEUX PASSES EN MEME TEMPS DOUBLERAIENT LA FACTURE, et deux
        # tours concurrents se disputeraient le meme article. Le cas
        # arrive tout seul : une nuit plus longue que prevu, et le cron
        # suivant repart. / Concurrent passes double the bill.
        if not a_blanc and not options.get("meme_si_une_passe_tourne"):
            deja_en_cours = passe_en_cours()
            if deja_en_cours is not None:
                raise CommandError(
                    f"Une passe lancée le "
                    f"{deja_en_cours.lancee_le:%d/%m/%Y à %H:%M} tourne "
                    f"encore : celle-ci ne démarre pas. Deux passes "
                    f"appelleraient le rédacteur sur les mêmes wikis. "
                    f"/ A pass is already running; this one will not start."
                )

        # LES WIKIS A EXAMINER : ceux dont l'article n'a pas repris
        # toute la matiere de son perimetre. Le calcul est le meme que
        # celui de l'ecran (« ce qui n'a pas ete repris »), donc la
        # nuit ne travaille jamais sur un wiki que l'ecran dirait a
        # jour. / Same "left out" computation as the screen.
        wikis_a_examiner = []
        for wiki in Wiki.objects.select_related("page", "dossier"):
            try:
                a_du_neuf = extractions_ecartees(wiki.page).exists()
            except Exception as erreur:
                # Un perimetre inconnu (article historique) n'est pas
                # une raison d'arreter la nuit. / An unknown scope does
                # not stop the night.
                self.stderr.write(
                    f"  wiki #{wiki.pk} : périmètre illisible ({erreur}) "
                    f"— laissé de côté."
                )
                continue
            if a_du_neuf:
                wikis_a_examiner.append(wiki)

        ecartes_par_le_maximum = 0
        if maximum and len(wikis_a_examiner) > maximum:
            ecartes_par_le_maximum = len(wikis_a_examiner) - maximum
            wikis_a_examiner = wikis_a_examiner[:maximum]

        if a_blanc:
            self.stdout.write(
                f"À blanc : {len(wikis_a_examiner)} wiki(s) seraient mis "
                f"à jour, {ecartes_par_le_maximum} écarté(s) par --maximum."
            )
            for wiki in wikis_a_examiner:
                self.stdout.write(f"  - #{wiki.pk} « {wiki.sujet[:60]} »")
            return

        modele_redacteur = modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE)
        passe = PasseDeNuit.objects.create(
            wikis_ecartes_par_le_maximum=ecartes_par_le_maximum,
        )

        from front.tasks import mettre_a_jour_un_wiki_la_nuit

        wikis_modifies = 0
        wikis_en_erreur = 0
        for wiki in wikis_a_examiner:
            try:
                tour = mettre_a_jour_un_wiki_la_nuit(wiki, modele_redacteur)
            except Exception as erreur:
                # UNE ERREUR NE FAIT PAS TOMBER LA NUIT. Un modele
                # injoignable sur un wiki laisserait tous les suivants
                # sans mise a jour, et personne ne saurait pourquoi.
                # / One failure never stops the whole pass.
                wikis_en_erreur += 1
                self.stderr.write(
                    f"  wiki #{wiki.pk} « {wiki.sujet[:40]} » : {erreur}"
                )
                continue
            if tour is not None and tour.a_change_l_article:
                wikis_modifies += 1
                self.stdout.write(
                    f"  wiki #{wiki.pk} « {wiki.sujet[:40]} » : "
                    f"{tour.operations.filter(appliquee=True).count()} "
                    f"opération(s) appliquée(s), "
                    f"{tour.operations.filter(appliquee=False).count()} "
                    f"rejetée(s)."
                )
            else:
                self.stdout.write(
                    f"  wiki #{wiki.pk} « {wiki.sujet[:40]} » : rien "
                    f"d'applicable — article inchangé."
                )

        passe.wikis_examines = len(wikis_a_examiner)
        passe.wikis_modifies = wikis_modifies
        passe.wikis_en_erreur = wikis_en_erreur
        passe.terminee_le = timezone.now()
        passe.save(update_fields=[
            "wikis_examines", "wikis_modifies", "wikis_en_erreur",
            "terminee_le",
        ])

        self.stdout.write(
            f"Passe de nuit terminée : {passe.wikis_examines} examiné(s), "
            f"{wikis_modifies} modifié(s), {wikis_en_erreur} en erreur, "
            f"{ecartes_par_le_maximum} écarté(s) par --maximum."
        )
