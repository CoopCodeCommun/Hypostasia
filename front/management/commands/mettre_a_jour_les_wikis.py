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

import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Wiki
from core.services.passe_de_nuit import passe_en_cours


# Combien de temps laisser a la tache d'ouverture pour creer la passe,
# et a quel rythme regarder. La tache peut patienter derriere d'autres
# dans la file : deux minutes sont larges sans etre une eternite.
# / How long the opening task gets to create the pass.
DELAI_D_OUVERTURE = timedelta(minutes=2)
SECONDES_ENTRE_DEUX_REGARDS = 3


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
            "--attendre", action="store_true",
            help="Ne rend la main que lorsque la passe est fermee. "
                 "INDISPENSABLE quand un recapitulatif suit dans le "
                 "meme script : sans cela il partirait avant que la "
                 "passe n'existe.",
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

        if options.get("attendre"):
            self._attendre_la_fermeture()

    def _attendre_la_fermeture(self):
        """
        Ne rend la main qu'une fois la passe fermee.
        / Returns only once the pass is closed.

        LOCALISATION :
        front/management/commands/mettre_a_jour_les_wikis.py

        POURQUOI CETTE OPTION EXISTE. La commande ne fait plus que
        METTRE EN FILE : elle rend la main en quelques millisecondes,
        avant meme que la tache d'ouverture n'ait cree la
        `PasseDeNuit`. Un script qui enchaine le recapitulatif derriere
        elle — `bin/nuit.sh tout` — trouvait donc « aucune passe en
        cours » et envoyait le mail AVANT le travail qu'il annonce.
        C'est la promesse centrale du chantier, cassee par sa propre
        porte manuelle.
        / The command only queues: a script chaining the recap behind it
        found no running pass and mailed before the work it announces.
        """
        from core.models import PasseDeNuit
        from core.services.passe_de_nuit import passe_en_cours

        # D'abord attendre que la passe EXISTE : la tache d'ouverture
        # peut patienter derriere d'autres dans la file.
        # / First wait for the pass to exist.
        debut = timezone.now()
        while passe_en_cours() is None:
            if timezone.now() - debut > DELAI_D_OUVERTURE:
                derniere = PasseDeNuit.objects.first()
                if derniere is not None and not derniere.tourne_encore:
                    # Elle a ouvert ET ferme pendant qu'on regardait :
                    # rien a attendre. / It opened and closed already.
                    break
                raise CommandError(
                    "La passe n'a pas démarré : le worker Celery "
                    "répond-il ? (make status) "
                    "/ The pass never started; is the worker alive?"
                )
            time.sleep(SECONDES_ENTRE_DEUX_REGARDS)

        # Puis attendre qu'elle finisse.
        # / Then wait for it to finish.
        while passe_en_cours() is not None:
            time.sleep(SECONDES_ENTRE_DEUX_REGARDS)

        passe = PasseDeNuit.objects.first()
        if passe is not None:
            self.stdout.write(
                f"Passe terminée : {passe.wikis_examines} examiné(s), "
                f"{passe.wikis_modifies} modifié(s), "
                f"{passe.wikis_en_erreur} en erreur."
            )

    def _wikis_qui_ont_du_neuf(self):
        """
        Les wikis qui ont une raison d'etre repris cette nuit.
        / The wikis with a reason to be re-run tonight.

        LE MEME CRITERE QUE LA TACHE, jamais un second : il exige que
        quelque chose soit APPARU depuis le dernier tour, et pas
        seulement qu'il reste des extractions ecartees — un wiki en
        porte en permanence.
        / The task's criterion, never a second one.
        """
        from front.tasks import _le_wiki_a_une_raison_d_etre_repris

        return [
            wiki for wiki in Wiki.objects.select_related("page", "dossier")
            if _le_wiki_a_une_raison_d_etre_repris(wiki)
        ]
