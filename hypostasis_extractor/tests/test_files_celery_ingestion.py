"""
Tests de la topologie des files Celery pour l'ingestion Docling.
/ Tests of the Celery queue topology for Docling ingestion.

LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        hypostasis_extractor.tests.test_files_celery_ingestion \\
        --settings=hypostasia.settings_test_opus

POURQUOI TESTER UN FICHIER DE CONFIGURATION

Parce que c'est precisement la qu'a eu lieu la derive, sans que rien ne
la signale. `supervisord.conf` declarait bien un worker dedie a
concurrence 1 ; le lancement de dev, lui, tirait les deux files a
concurrence 2 depuis un seul worker. Deux conversions Docling
simultanees etaient donc possibles en dev — deux chargements de modeles
(~80 s et ~2 Go chacun, mesure du 14 aout 2026) sur une machine qui n'en
supporte qu'un. Aucun test ne pouvait le voir : la topologie des files
ne vit dans aucun code Python.
/ The drift happened in configuration, where no test was looking.

CE QUE CES TESTS VERROUILLENT

1. Toute tache routee vers la file dediee trouve un worker qui l'ecoute
   (sans quoi elle attend indefiniment, en silence).
2. Aucun worker ne tire la file dediee EN MEME TEMPS qu'une autre : un
   PDF ne doit jamais pouvoir occuper les slots reserves aux analyses,
   ni l'inverse.
3. La file dediee reste servie a concurrence 1 : une seule conversion a
   la fois sur l'hote 8 Go partage.
4. Supervisord surveille les vrais process, pas un wrapper.
"""

import configparser
from pathlib import Path

from django.conf import settings
from django.test import TestCase

# Les deux topologies doivent porter les MEMES garanties. C'est tout
# l'objet du chantier : ce qui tourne en dev doit se comporter comme ce
# qui tourne en prod. / Both topologies carry the same guarantees.
FICHIERS_SUPERVISORD = ("supervisord.conf", "supervisord-dev.conf")

FILE_DEDIEE_A_DOCLING = "ingestion_docling"

# La file par defaut de Celery, celle qu'un worker consomme quand sa
# commande ne porte aucun `-Q`. / Celery's default queue.
FILE_PAR_DEFAUT = "celery"


def _programmes_supervisord(nom_du_fichier):
    """
    Rend les programmes declares dans un fichier supervisord.
    / Returns the programs declared in a supervisord file.

    LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py

    `interpolation=None` est indispensable : les commandes contiennent
    des `%%h` (echappement supervisord d'un `%h`), que l'interpolation
    par defaut de configparser refuserait de lire.
    / interpolation=None: the commands contain supervisord's %%h.

    :param nom_du_fichier: nom du fichier a la racine du depot
    :return: dict {nom_du_programme: ligne_de_commande}
    """
    chemin_du_fichier = Path(settings.BASE_DIR) / nom_du_fichier
    lecteur = configparser.ConfigParser(interpolation=None)
    lecteur.read(chemin_du_fichier, encoding="utf-8")

    programmes = {}
    for nom_de_section in lecteur.sections():
        if not nom_de_section.startswith("program:"):
            continue
        nom_du_programme = nom_de_section.split(":", 1)[1]
        programmes[nom_du_programme] = lecteur[nom_de_section].get("command", "")
    return programmes


def _files_consommees_par(ligne_de_commande):
    """
    Rend les files Celery que consomme une ligne de commande worker.
    / Returns the Celery queues a worker command line consumes.

    LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py

    Un worker sans `-Q` consomme la file par defaut, et elle seule.
    / A worker with no -Q consumes the default queue, and only it.

    QUATRE ECRITURES, UN SEUL SENS

    Celery accepte `-Q file`, `-Qfile`, `--queues file` et
    `--queues=file`. Ne reconnaitre que la premiere rendait ce test
    complaisant : `-Qcelery,ingestion_docling` etait lu comme « la file
    par defaut », et un worker qui melange les deux files passait au
    vert (relecture adverse du 14 aout 2026).
    / Celery accepts four spellings; reading only one made this test
    complacent.

    :param ligne_de_commande: la commande du programme supervisord
    :return: set des noms de files, ou set() si ce n'est pas un worker
    """
    valeur = _valeur_de_l_option(ligne_de_commande, ("-Q", "--queues"))
    if valeur is None:
        # Pas un worker du tout : ni file, ni file par defaut.
        # / Not a worker at all.
        if "worker" not in ligne_de_commande.split():
            return set()
        return {FILE_PAR_DEFAUT}
    return set(valeur.split(","))


def _valeur_de_l_option(ligne_de_commande, noms_de_l_option):
    """
    Rend la valeur d'une option, quelle que soit son ecriture.
    / Returns an option's value, whatever its spelling.

    LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py

    Couvre les quatre formes qu'accepte Celery : `-o valeur`,
    `-ovaleur`, `--option valeur` et `--option=valeur`.
    / Covers the four spellings Celery accepts.

    :param noms_de_l_option: les noms equivalents, court puis long
    :return: la valeur en chaine, ou None si l'option est absente
    """
    morceaux = ligne_de_commande.split()
    if "worker" not in morceaux:
        return None

    for position, morceau in enumerate(morceaux):
        for nom_de_l_option in noms_de_l_option:
            if morceau == nom_de_l_option:
                if position + 1 < len(morceaux):
                    return morceaux[position + 1]
                return None
            if morceau.startswith(f"{nom_de_l_option}="):
                return morceau.split("=", 1)[1]
            # Forme collee (`-Qfile`, `-c1`), reservee aux options
            # courtes : `--queuesfile` n'existe pas.
            # / Glued form, short options only.
            if (
                not nom_de_l_option.startswith("--")
                and morceau.startswith(nom_de_l_option)
                and len(morceau) > len(nom_de_l_option)
            ):
                return morceau[len(nom_de_l_option):]
    return None


def _concurrence_de(ligne_de_commande):
    """
    Rend la concurrence declaree par une ligne de commande worker.
    / Returns the concurrency declared by a worker command line.

    LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py

    Memes quatre ecritures que pour les files : `-c 1`, `-c1`,
    `--concurrency 1`, `--concurrency=1`.
    / Same four spellings as for queues.

    :return: l'entier declare, ou None si la commande n'en fixe aucune
        (Celery prend alors le nombre de coeurs — jamais 1 sur cet hote)
    """
    valeur = _valeur_de_l_option(ligne_de_commande, ("-c", "--concurrency"))
    if valeur is None:
        return None
    try:
        return int(valeur)
    except ValueError:
        return None


class LectureDesLignesDeCommandeCeleryTest(TestCase):
    """
    Le lecteur de lignes de commande comprend-il ce que Celery comprend ?
    / Does the command-line reader understand what Celery understands?

    LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py

    POURQUOI CES TESTS EXISTENT

    Un test de configuration ne vaut que ce que vaut sa lecture de la
    configuration. La premiere version de ce fichier ne reconnaissait
    que `-Q file` (espace) et `--concurrency=N` (egal). La relecture
    adverse du 14 aout 2026 a montre qu'elle laissait passer la derive
    exacte qu'elle devait empecher : `-Qcelery,ingestion_docling`
    (colle, forme parfaitement valide pour Celery) etait lu comme « la
    file par defaut », le programme etait donc ignore par le test des
    melanges, et la suite restait VERTE avec un worker qui tire les deux
    files.
    / A config test is only as good as its reading of the config; the
    first version let the very drift it guards against pass green.
    """

    def test_la_file_collee_a_l_option_est_reconnue(self):
        # `-Qa,b` sans espace : Celery l'accepte, le test doit le voir.
        self.assertEqual(
            _files_consommees_par("celery -A x worker -Qcelery,ingestion_docling"),
            {"celery", "ingestion_docling"},
        )

    def test_les_quatre_ecritures_de_la_file_sont_equivalentes(self):
        for ecriture in (
            "-Q ingestion_docling",
            "-Qingestion_docling",
            "--queues ingestion_docling",
            "--queues=ingestion_docling",
        ):
            with self.subTest(ecriture=ecriture):
                self.assertEqual(
                    _files_consommees_par(f"celery -A x worker {ecriture}"),
                    {"ingestion_docling"},
                )

    def test_les_quatre_ecritures_de_la_concurrence_sont_equivalentes(self):
        for ecriture in ("-c 1", "-c1", "--concurrency 1", "--concurrency=1"):
            with self.subTest(ecriture=ecriture):
                self.assertEqual(
                    _concurrence_de(f"celery -A x worker {ecriture}"), 1,
                )

    def test_une_commande_sans_file_consomme_la_file_par_defaut(self):
        self.assertEqual(
            _files_consommees_par("celery -A x worker --concurrency=2"),
            {"celery"},
        )

    def test_ce_qui_n_est_pas_un_worker_ne_consomme_aucune_file(self):
        self.assertEqual(_files_consommees_par("python manage.py runserver"), set())


class TopologieDesFilesCeleryTest(TestCase):
    """
    La file d'ingestion Docling est servie seule, a concurrence 1,
    en dev comme en prod.
    / The Docling queue is served alone, at concurrency 1, everywhere.

    LOCALISATION : hypostasis_extractor/tests/test_files_celery_ingestion.py
    """

    def test_les_deux_fichiers_supervisord_existent(self):
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            chemin_du_fichier = Path(settings.BASE_DIR) / nom_du_fichier
            self.assertTrue(
                chemin_du_fichier.is_file(),
                f"{nom_du_fichier} est absent : la topologie des files "
                f"n'est plus decrite nulle part pour cet environnement.",
            )

    def test_un_worker_sert_la_file_docling_dans_chaque_environnement(self):
        # Une tache routee vers une file que personne n'ecoute attend
        # pour toujours, sans erreur ni trace : c'est le pire des echecs
        # possibles. / A queue nobody listens to fails in total silence.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            with self.subTest(fichier=nom_du_fichier):
                files_servies = set()
                for ligne_de_commande in _programmes_supervisord(nom_du_fichier).values():
                    files_servies |= _files_consommees_par(ligne_de_commande)

                self.assertIn(
                    FILE_DEDIEE_A_DOCLING, files_servies,
                    f"{nom_du_fichier} : aucun worker n'ecoute la file "
                    f"{FILE_DEDIEE_A_DOCLING}. Les ingestions y "
                    f"attendraient indefiniment.",
                )

    def test_aucun_worker_ne_melange_la_file_docling_avec_une_autre(self):
        # C'est l'invariant qui avait derive en dev : un seul worker
        # tirait `celery,ingestion_docling`. Une conversion Docling
        # pouvait alors occuper les slots des analyses, et deux
        # conversions tourner de front.
        # / The invariant that had drifted: one worker pulling both.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            for nom_du_programme, ligne_de_commande in _programmes_supervisord(
                nom_du_fichier,
            ).items():
                files_du_worker = _files_consommees_par(ligne_de_commande)
                if FILE_DEDIEE_A_DOCLING not in files_du_worker:
                    continue
                with self.subTest(fichier=nom_du_fichier, programme=nom_du_programme):
                    self.assertEqual(
                        files_du_worker, {FILE_DEDIEE_A_DOCLING},
                        f"{nom_du_fichier} / {nom_du_programme} tire "
                        f"{sorted(files_du_worker)} : la file dediee doit "
                        f"etre servie SEULE.",
                    )

    def test_le_worker_docling_reste_a_concurrence_1(self):
        # Deux conversions simultanees, c'est deux chargements de
        # modeles (~80 s et ~2 Go chacun) sur un hote 8 Go partage avec
        # la production. / Two conversions at once would not fit.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            for nom_du_programme, ligne_de_commande in _programmes_supervisord(
                nom_du_fichier,
            ).items():
                if FILE_DEDIEE_A_DOCLING not in _files_consommees_par(ligne_de_commande):
                    continue
                with self.subTest(fichier=nom_du_fichier, programme=nom_du_programme):
                    self.assertEqual(
                        _concurrence_de(ligne_de_commande), 1,
                        f"{nom_du_fichier} / {nom_du_programme} : la file "
                        f"{FILE_DEDIEE_A_DOCLING} doit etre servie a "
                        f"concurrence 1, une conversion a la fois.",
                    )

    def test_les_taches_docling_sont_routees_vers_la_file_dediee(self):
        # Le routage et les workers sont deux moities de la meme
        # decision : les tester separement laisserait passer le cas ou
        # l'un des deux bouge sans l'autre.
        # / Routing and workers are two halves of one decision.
        from hypostasia.celery import celery_app

        taches_routees = {
            nom_de_la_tache
            for nom_de_la_tache, route in celery_app.conf.task_routes.items()
            if route.get("queue") == FILE_DEDIEE_A_DOCLING
        }

        self.assertEqual(
            taches_routees,
            {
                "hypostasis_extractor.tasks_element.ingerer_un_fichier_avec_docling",
                "hypostasis_extractor.tasks_element.ingerer_une_capture_web_avec_docling",
            },
            "Les deux taches qui appellent Docling (fichier et capture "
            "web) doivent partir sur la file dediee, et elles seules.",
        )

    def test_aucun_worker_docling_n_est_mis_sous_autoscale(self):
        # `--autoscale=4,1` ecrase silencieusement `--concurrency=1` :
        # le test de concurrence resterait vert avec un worker qui monte
        # a 4 conversions simultanees (relecture adverse du 14 aout).
        # / --autoscale silently overrides --concurrency.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            for nom_du_programme, ligne_de_commande in _programmes_supervisord(
                nom_du_fichier,
            ).items():
                if FILE_DEDIEE_A_DOCLING not in _files_consommees_par(ligne_de_commande):
                    continue
                with self.subTest(fichier=nom_du_fichier, programme=nom_du_programme):
                    self.assertNotIn(
                        "autoscale", ligne_de_commande,
                        f"{nom_du_fichier} / {nom_du_programme} : "
                        f"--autoscale rendrait la concurrence declaree "
                        f"sans effet.",
                    )

    def test_les_workers_laissent_finir_leur_tache_avant_de_mourir(self):
        # Un worker Celery s'arrete TIEDE : SIGTERM au seul parent, qui
        # orchestre la fin de ses enfants. `stopasgroup` casserait ca en
        # signalant tout le monde d'un coup. `killasgroup`, lui, ne joue
        # qu'en dernier recours (SIGKILL) et evite d'abandonner des
        # enfants prefork orphelins avec leur memoire — asymetrie
        # relevee par la relecture adverse du 14 aout 2026 : le dev
        # l'avait, la prod non.
        # / Celery stops warm: SIGTERM to the parent alone. stopasgroup
        # would break that; killasgroup only applies as a last resort.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            lecteur = configparser.ConfigParser(interpolation=None)
            lecteur.read(Path(settings.BASE_DIR) / nom_du_fichier, encoding="utf-8")
            for nom_de_section in lecteur.sections():
                if not nom_de_section.startswith("program:"):
                    continue
                reglages = lecteur[nom_de_section]
                if not _files_consommees_par(reglages.get("command", "")):
                    continue
                with self.subTest(fichier=nom_du_fichier, programme=nom_de_section):
                    self.assertEqual(
                        reglages.get("stopasgroup", "false").lower(), "false",
                        "stopasgroup enverrait le SIGTERM d'arret a tout "
                        "le groupe : les enfants prefork seraient coupes "
                        "au lieu d'etre arretes par leur parent.",
                    )
                    self.assertEqual(
                        reglages.get("killasgroup", "false").lower(), "true",
                        "killasgroup manquant : un SIGKILL de dernier "
                        "recours laisserait des enfants prefork "
                        "orphelins avec leur memoire.",
                    )
                    self.assertGreaterEqual(
                        int(reglages.get("stopwaitsecs", 0)), 60,
                        "Trop peu de temps laisse au worker pour finir "
                        "sa tache en cours avant le SIGKILL.",
                    )

    def test_supervisord_surveille_les_vrais_process_et_pas_un_wrapper(self):
        # `uv run` laisse un process intermediaire vivant : supervisord
        # surveillerait le wrapper, et son SIGTERM d'arret irait a lui
        # plutot qu'au worker. Or l'arret gracieux d'un worker Celery
        # (stopwaitsecs) est ce qui laisse une conversion en cours se
        # terminer. Le PATH de l'image contient deja /app/.venv/bin
        # (Dockerfile), le wrapper n'apporte rien.
        # / uv run leaves a wrapper process between supervisord and the
        # real one, and SIGTERM would go to the wrapper.
        for nom_du_fichier in FICHIERS_SUPERVISORD:
            for nom_du_programme, ligne_de_commande in _programmes_supervisord(
                nom_du_fichier,
            ).items():
                with self.subTest(fichier=nom_du_fichier, programme=nom_du_programme):
                    self.assertNotIn(
                        "uv run", ligne_de_commande,
                        f"{nom_du_fichier} / {nom_du_programme} passe par "
                        f"`uv run` : supervisord surveillerait le wrapper "
                        f"et non le process reel.",
                    )
