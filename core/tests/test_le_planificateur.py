"""
Le planificateur : ce qui part tout seul, et qui l'execute.
/ The scheduler: what fires on its own, and who runs it.

LOCALISATION : core/tests/test_le_planificateur.py

POURQUOI TESTER UN FICHIER DE CONFIGURATION. Pour la meme raison que
`test_files_celery_ingestion.py` : la topologie ne vit dans aucun code
Python, et c'est precisement la qu'ont eu lieu les derives. Une entree
de `beat_schedule` qui nomme une tache inexistante ne leve rien au
demarrage — elle echoue chaque nuit, dans les journaux d'un worker que
personne ne lit.
/ A beat entry naming a missing task fails every night, in logs nobody
reads.

CE QUE CES TESTS VERROUILLENT

1. Chaque tache planifiee EXISTE et est enregistree dans Celery.
2. Le planificateur est declare dans les DEUX topologies supervisord.
3. Il ne consomme AUCUNE file — sinon il prendrait un slot
   d'execution, et la topologie des trois workers ne serait plus vraie.
4. Il n'y en a qu'UN : deux beats enverraient chaque tache en double,
   donc deux passes de nuit sur les memes wikis, donc la facture du
   redacteur doublee.
"""

import configparser
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from hypostasia.celery import celery_app

FICHIERS_SUPERVISORD = ("supervisord.conf", "supervisord-dev.conf")


def _programmes_de(nom_du_fichier):
    """Les sections [program:*] d'un fichier supervisord.
    / The [program:*] sections of a supervisord file."""
    lecteur = configparser.ConfigParser(interpolation=None)
    lecteur.read(Path(settings.BASE_DIR) / nom_du_fichier, encoding="utf-8")
    return {
        nom_de_section[len("program:"):]: lecteur[nom_de_section]
        for nom_de_section in lecteur.sections()
        if nom_de_section.startswith("program:")
    }


class LesTachesPlanifieesExistentTest(TestCase):
    """
    Une entree qui nomme une tache absente echoue chaque nuit, en
    silence. / An entry naming a missing task fails silently, nightly.
    """

    def test_les_deux_rendez_vous_sont_declares(self):
        noms = set(celery_app.conf.beat_schedule)

        self.assertIn("la-passe-de-nuit-des-wikis", noms)
        self.assertIn("le-recapitulatif-du-matin", noms)

    def test_chaque_tache_planifiee_est_enregistree(self):
        # `autodiscover_tasks` doit les avoir trouvees : sinon le beat
        # envoie un message que personne ne sait executer.
        # / Otherwise beat sends a message nobody can run.
        import front.tasks  # noqa: F401  (enregistre les taches)

        for nom_du_rendez_vous, entree in celery_app.conf.beat_schedule.items():
            with self.subTest(rendez_vous=nom_du_rendez_vous):
                self.assertIn(
                    entree["task"], celery_app.tasks,
                    f"« {entree['task']} » n'est pas une tâche enregistrée : "
                    f"le planificateur l'appellerait dans le vide.",
                )

    def test_le_recapitulatif_passe_apres_la_passe_de_nuit(self):
        # L'ecart d'horaire n'est qu'un confort — la garantie est dans
        # la tache, qui attend la fin de la passe. Mais un horaire
        # inverse ferait attendre le mail une journee entiere.
        # / The gap is comfort; an inverted one would cost a whole day.
        heure_de_la_passe = min(
            celery_app.conf.beat_schedule[
                "la-passe-de-nuit-des-wikis"
            ]["schedule"].hour
        )
        heure_du_mail = min(
            celery_app.conf.beat_schedule[
                "le-recapitulatif-du-matin"
            ]["schedule"].hour
        )

        self.assertLess(heure_de_la_passe, heure_du_mail)


class LePlanificateurTourneQuelquePartTest(TestCase):
    """
    Un `beat_schedule` sans process pour le lire ne declenche RIEN, et
    ne le dit pas. / A schedule with no process fires nothing, silently.
    """

    def test_le_planificateur_est_declare_dans_les_deux_topologies(self):
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            with self.subTest(fichier=nom_du_fichier):
                programmes = _programmes_de(nom_du_fichier)
                self.assertIn(
                    "celery_beat", programmes,
                    f"{nom_du_fichier} ne lance aucun planificateur : "
                    f"la passe de nuit ne partirait jamais.",
                )
                self.assertIn(
                    "beat", programmes["celery_beat"]["command"],
                )

    def test_il_n_y_a_qu_un_seul_planificateur_par_topologie(self):
        # Deux beats enverraient chaque tache en double : deux passes
        # sur les memes wikis, donc la facture doublee.
        # / Two beats double every task, and the bill with it.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            with self.subTest(fichier=nom_du_fichier):
                programmes = _programmes_de(nom_du_fichier)
                planificateurs = [
                    nom for nom, reglages in programmes.items()
                    if " beat" in reglages.get("command", "")
                ]
                self.assertEqual(planificateurs, ["celery_beat"])

    def test_le_planificateur_ne_consomme_aucune_file(self):
        # S'il en consommait une, il prendrait un slot d'execution et
        # la topologie des trois workers cesserait d'etre vraie.
        # / A queue-consuming beat would take an execution slot.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            with self.subTest(fichier=nom_du_fichier):
                commande = _programmes_de(nom_du_fichier)["celery_beat"][
                    "command"
                ]
                self.assertNotIn("-Q", commande)
                self.assertNotIn("--queues", commande)
                self.assertNotIn("worker", commande)

    def test_il_demarre_dans_les_deux_topologies(self):
        # MEME TOPOLOGIE DES DEUX COTES, comme les trois workers : ce
        # qui tourne en dev doit se comporter comme ce qui tourne en
        # prod. Un beat qui ne demarre pas est une nuit qui ne passe
        # jamais — en silence.
        # / Same topology on both sides: a beat that does not start is
        # a night that silently never happens.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            with self.subTest(fichier=nom_du_fichier):
                self.assertEqual(
                    _programmes_de(nom_du_fichier)["celery_beat"].get(
                        "autostart", "false",
                    ).lower(),
                    "true",
                )

    def test_le_planificateur_ne_passe_pas_par_uv_run(self):
        # Le wrapper s'interposerait entre supervisord et le process
        # reel : le SIGTERM d'arret irait au wrapper.
        # / The wrapper would swallow the stop signal.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            with self.subTest(fichier=nom_du_fichier):
                commande = _programmes_de(nom_du_fichier)["celery_beat"][
                    "command"
                ]
                self.assertNotIn("uv run", commande)
