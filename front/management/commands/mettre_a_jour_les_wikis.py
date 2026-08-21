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

CETTE COMMANDE EST LA PORTE MANUELLE. La nuit, c'est le PLANIFICATEUR
qui declenche la meme chose (`hypostasia/celery.py`, `beat_schedule` ->
`front.tasks.lancer_la_passe_de_nuit_task`). Les deux passent par la
MEME tache : une seconde implementation divergerait, et on ne saurait
plus laquelle a produit un article donne.
/ This command is the manual door; the scheduler uses the same task.

EN PARALLELE, PAS EN SUITE. Une tache par wiki part sur la file par
defaut : les appels au redacteur avancent a la concurrence du worker,
et chacun tient largement sous le plafond de 30 minutes.
/ One task per wiki on the default queue.

FLUX :
1. ouvre une `PasseDeNuit` et met un wiki par tache en file ;
2. chaque tache rend la main a la passe en finissant ;
3. la DERNIERE ferme la passe — c'est elle que le recapitulatif du
   matin interroge avant de partir (le mail suit TOUJOURS le run).
"""

from django.core.management.base import BaseCommand, CommandError

from core.models import Wiki
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

        if a_blanc:
            # DIRE CE QUI PARTIRAIT NE COUTE RIEN et n'ecrit rien : le
            # calcul est le meme que celui de l'ecran (« ce qui n'a pas
            # ete repris »), donc la nuit ne travaille jamais sur un
            # wiki que l'ecran dirait a jour.
            # / A dry run costs nothing and writes nothing.
            wikis_a_examiner = self._wikis_qui_ont_du_neuf()
            ecartes = 0
            if maximum and len(wikis_a_examiner) > maximum:
                ecartes = len(wikis_a_examiner) - maximum
                wikis_a_examiner = wikis_a_examiner[:maximum]
            self.stdout.write(
                f"À blanc : {len(wikis_a_examiner)} wiki(s) seraient mis "
                f"à jour, {ecartes} écarté(s) par --maximum."
            )
            for wiki in wikis_a_examiner:
                self.stdout.write(f"  - #{wiki.pk} « {wiki.sujet[:60]} »")
            return

        if not options.get("meme_si_une_passe_tourne"):
            deja_en_cours = passe_en_cours()
            if deja_en_cours is not None:
                raise CommandError(
                    f"Une passe lancée le "
                    f"{deja_en_cours.lancee_le:%d/%m/%Y à %H:%M} tourne "
                    f"encore : celle-ci ne démarre pas. Deux passes "
                    f"appelleraient le rédacteur sur les mêmes wikis. "
                    f"/ A pass is already running; this one will not start."
                )

        # LA MEME TACHE QUE LE PLANIFICATEUR, jamais une seconde
        # implementation. / The scheduler's task, never a second one.
        from front.tasks import lancer_la_passe_de_nuit_task

        tache_d_ouverture = lancer_la_passe_de_nuit_task.delay(
            maximum=maximum,
        )
        self.stdout.write(
            "Passe de nuit mise en file : une tâche par wiki, sur la "
            "file par défaut. Suivre son avancement :\n"
            "  make logs   (ou : docker compose logs -f web)\n"
            f"  tâche d'ouverture : {tache_d_ouverture}"
        )

    def _wikis_qui_ont_du_neuf(self):
        """
        Les wikis dont l'article n'a pas repris toute la matiere de son
        perimetre. / The wikis whose article left something out.
        """
        wikis_a_examiner = []
        for wiki in Wiki.objects.select_related("page", "dossier"):
            try:
                a_du_neuf = extractions_ecartees(wiki.page).exists()
            except Exception as erreur:
                self.stderr.write(
                    f"  wiki #{wiki.pk} : périmètre illisible ({erreur}) "
                    f"— laissé de côté."
                )
                continue
            if a_du_neuf:
                wikis_a_examiner.append(wiki)
        return wikis_a_examiner
