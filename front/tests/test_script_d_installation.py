"""
Ce que les scripts de demarrage lancent reellement.
/ What the startup scripts actually launch.

LOCALISATION : front/tests/test_script_d_installation.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_script_d_installation \\
        --settings=hypostasia.settings_test_opus

POURQUOI TESTER DES SCRIPTS SHELL ET UN MAKEFILE

Parce que c'est la qu'ont eu lieu les deux dernieres derives, et que
rien ne pouvait les voir.

`install.sh` chargeait `charger_fixtures_demo` — un jeu de notes
FICTIVES, sans aucune base de connaissances — au lieu des documents
etalons de `sample/`. Sur une installation neuve, l'ecran « Bases de
connaissances » arrivait VIDE (constate le 15 aout 2026).

Avant cela, le lancement de dev tirait les deux files Celery depuis un
worker unique, quand la production en declare deux. Meme cause : une
commande ecrite dans un document qu'on lit, pas qu'on execute.
/ Both recent drifts lived in shell scripts, where no test was looking.

LES QUATRE INVARIANTS TENUS ICI

1. L'installation charge les documents etalons, puis leurs extractions,
   puis une analyse par le vrai modele — dans cet ordre.
2. Les deux scripts de demarrage passent par l'installation, et lancent
   chacun SON supervisord : runserver en dev, gunicorn+daphne en prod.
3. Le Makefile n'ecrit aucune commande que les scripts portent deja :
   il les APPELLE. Deux definitions d'une meme sequence finissent
   toujours par diverger.
4. `DEBUG` et `NGINX_CONF` vont ensemble : nginx doit viser les ports
   ou quelqu'un ecoute vraiment.
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase

REPERTOIRE_DES_SCRIPTS = "bin"
SCRIPT_D_INSTALLATION = f"{REPERTOIRE_DES_SCRIPTS}/install.sh"
SCRIPT_DE_DEMARRAGE_DEV = f"{REPERTOIRE_DES_SCRIPTS}/start-dev.sh"
SCRIPT_DE_DEMARRAGE_PROD = f"{REPERTOIRE_DES_SCRIPTS}/start-prod.sh"

COMMANDE_DES_DOCUMENTS = "charger_fixtures_sample"
COMMANDE_DES_EXTRACTIONS = "charger_extractions_demo"
COMMANDE_DU_LLM = "analyser_les_notes_etalons"


def _lignes_utiles(chemin_relatif):
    """
    Rend les lignes d'un fichier, commentaires et vide exclus.
    / Returns a file's lines, comments and blanks excluded.

    LOCALISATION : front/tests/test_script_d_installation.py

    Les commentaires sont ecartes : ils CITENT les commandes sans les
    lancer, et un test qui les lirait passerait au vert sur une simple
    mention. / Comments name commands without running them.
    """
    chemin = Path(settings.BASE_DIR) / chemin_relatif
    lignes = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        nettoyee = ligne.strip()
        if not nettoyee or nettoyee.startswith("#") or nettoyee.startswith(";"):
            continue
        lignes.append(nettoyee)
    return lignes


def _rang_de(lignes, motif):
    """Rend l'index de la premiere ligne portant `motif`, ou None."""
    return next((i for i, ligne in enumerate(lignes) if motif in ligne), None)


class LInstallationChargeLeBonJeuDeDonneesTest(TestCase):
    """
    LOCALISATION : front/tests/test_script_d_installation.py
    """

    def test_les_scripts_sont_ranges_dans_un_repertoire_dedie(self):
        for chemin in (
            SCRIPT_D_INSTALLATION,
            SCRIPT_DE_DEMARRAGE_DEV,
            SCRIPT_DE_DEMARRAGE_PROD,
        ):
            with self.subTest(script=chemin):
                self.assertTrue(
                    (Path(settings.BASE_DIR) / chemin).is_file(),
                    f"{chemin} est absent.",
                )

    def test_l_installation_charge_les_documents_etalons(self):
        # Sans cette commande, aucune BaseDeConnaissances n'est creee et
        # l'ecran « Bases » reste vide sur une installation neuve.
        # / Without it, the knowledge-base screen stays empty.
        lignes = _lignes_utiles(SCRIPT_D_INSTALLATION)

        self.assertIsNotNone(
            _rang_de(lignes, COMMANDE_DES_DOCUMENTS),
            f"L'installation n'appelle pas `{COMMANDE_DES_DOCUMENTS}` : "
            f"ni les documents de sample/, ni base de connaissances.",
        )

    def test_l_installation_pose_les_extractions_puis_analyse_pour_de_vrai(self):
        lignes = _lignes_utiles(SCRIPT_D_INSTALLATION)

        self.assertIsNotNone(
            _rang_de(lignes, COMMANDE_DES_EXTRACTIONS),
            "Les notes seraient chargees sans aucune extraction.",
        )
        self.assertIsNotNone(
            _rang_de(lignes, COMMANDE_DU_LLM),
            "L'installation ne teste plus les cles API : c'est pourtant "
            "ce qu'apporte une analyse par le vrai modele.",
        )

    def test_l_analyse_est_lancee_sans_option_de_garde(self):
        """
        L'idempotence n'est plus une option, c'est le comportement.
        / Idempotency is no longer an option but the behaviour.

        LOCALISATION : front/tests/test_script_d_installation.py

        L'ancienne commande, `charger_fixtures_llm_reel`, rejouait de
        vrais appels payants a chaque execution : il fallait lui passer
        `--si-absent` et `--asynchrone` pour la rendre supportable dans
        un script que le conteneur relance a chaque demarrage.

        `analyser_les_notes_etalons` n'analyse par construction que ce
        qui ne l'est pas encore, et envoie toujours dans la file. Une
        option de garde ici signalerait un retour en arriere.
        / The previous command replayed billed calls on every run and
        needed guard flags; this one is guarded by construction.
        """
        lignes = _lignes_utiles(SCRIPT_D_INSTALLATION)
        ligne_du_llm = lignes[_rang_de(lignes, COMMANDE_DU_LLM)]

        self.assertNotIn("--si-absent", ligne_du_llm)
        self.assertNotIn("--forcer", ligne_du_llm)

    def test_l_ordre_des_etapes_est_tenu(self):
        # Les extractions s'ancrent sur des elements que la premiere
        # commande vient de creer ; et migrer vient avant toute donnee.
        # / Extractions anchor onto elements just created.
        lignes = _lignes_utiles(SCRIPT_D_INSTALLATION)

        rang_migrations = _rang_de(lignes, "migrate")
        rang_documents = _rang_de(lignes, COMMANDE_DES_DOCUMENTS)
        rang_extractions = _rang_de(lignes, COMMANDE_DES_EXTRACTIONS)

        self.assertLess(rang_migrations, rang_documents)
        self.assertLess(rang_documents, rang_extractions)


class LesDeuxDemarragesSontDistinctsTest(TestCase):
    """
    Dev et prod ne lancent pas les memes serveurs.
    / Dev and production do not launch the same servers.

    LOCALISATION : front/tests/test_script_d_installation.py
    """

    def test_les_deux_demarrages_passent_par_l_installation(self):
        # C'est ce qui garantit « les fixtures chargees a chaque
        # installation, prod comme dev ».
        # / This is what guarantees fixtures on every install.
        for script in (SCRIPT_DE_DEMARRAGE_DEV, SCRIPT_DE_DEMARRAGE_PROD):
            with self.subTest(script=script):
                lignes = _lignes_utiles(script)
                self.assertIsNotNone(
                    _rang_de(lignes, "install.sh"),
                    f"{script} ne lance pas l'installation.",
                )

    def test_le_dev_lance_runserver_et_la_prod_gunicorn_et_daphne(self):
        lignes_dev = _lignes_utiles(SCRIPT_DE_DEMARRAGE_DEV)
        lignes_prod = _lignes_utiles(SCRIPT_DE_DEMARRAGE_PROD)

        self.assertIsNotNone(
            _rang_de(lignes_dev, "supervisord-dev.conf"),
            "Le demarrage de dev doit lancer supervisord-dev.conf "
            "(runserver, avec rechargement automatique).",
        )
        rang_prod = _rang_de(lignes_prod, "supervisord.conf")
        self.assertIsNotNone(
            rang_prod,
            "Le demarrage de prod doit lancer supervisord.conf "
            "(gunicorn + daphne).",
        )
        self.assertIsNone(
            _rang_de(lignes_prod, "supervisord-dev.conf"),
            "Le demarrage de prod lance la configuration de DEV.",
        )

    def test_la_prod_attend_postgresql_avant_de_migrer(self):
        # Le conteneur peut demarrer avant sa base : migrer trop tot
        # echoue. / The container may start before its database.
        lignes = _lignes_utiles(SCRIPT_DE_DEMARRAGE_PROD)

        self.assertIsNotNone(_rang_de(lignes, "pg_isready"))


class LeMakefileNeReecritPasLesScriptsTest(TestCase):
    """
    Le Makefile APPELLE les scripts, il ne les recopie pas.
    / The Makefile CALLS the scripts, it does not duplicate them.

    LOCALISATION : front/tests/test_script_d_installation.py

    Deux definitions d'une meme sequence finissent toujours par
    diverger : c'est exactement ce qui a produit les deux dernieres
    pannes. Le Makefile est une facade cote hote ; la sequence
    d'installation n'existe qu'a un seul endroit.
    / Two definitions of one sequence always drift apart.
    """

    def _lignes_du_makefile(self):
        return _lignes_utiles("Makefile")

    def test_la_cible_des_fixtures_appelle_le_script(self):
        lignes = self._lignes_du_makefile()
        cibles_qui_reecrivent = [
            ligne for ligne in lignes
            if COMMANDE_DES_DOCUMENTS in ligne or COMMANDE_DES_EXTRACTIONS in ligne
        ]

        for ligne in cibles_qui_reecrivent:
            with self.subTest(ligne=ligne):
                self.assertIn(
                    "install.sh", ligne,
                    "Le Makefile reecrit une commande que l'installation "
                    "porte deja : les deux sequences vont diverger. Il "
                    "doit appeler le script.",
                )

    def test_le_makefile_refuse_de_tourner_sans_docker(self):
        # Le Makefile pilote Docker, il ne l'installe pas : son absence
        # doit donner un message clair, pas une erreur brute de shell.
        # / The Makefile drives Docker; it does not install it.
        contenu = "\n".join(self._lignes_du_makefile())

        self.assertIn(
            "command -v docker", contenu,
            "Aucun garde-fou : sans Docker, chaque cible echouerait sur "
            "un « command not found » sans dire quoi faire.",
        )


class DebugEtNginxVontEnsembleTest(TestCase):
    """
    nginx doit viser les ports ou quelqu'un ecoute.
    / nginx must target ports where something is listening.

    LOCALISATION : front/tests/test_script_d_installation.py

    En prod, gunicorn sert le HTTP sur 8001 et daphne le WebSocket sur
    8000. En dev, runserver sert LES DEUX sur 8000. Les deux
    configurations nginx different donc, et se choisissent par
    `NGINX_CONF` — un reglage couple a `DEBUG` que rien ne tenait
    ensemble : `DEBUG=true` avec la conf de prod envoie `/` sur 8001, ou
    personne n'ecoute, et tout le site rend 502.
    / A coupling nothing enforced: dev with the production nginx config
    sends everything to a port nobody listens on.
    """

    def _proxys_de(self, nom_du_fichier):
        chemin = Path(settings.BASE_DIR) / "nginx" / nom_du_fichier
        return [
            ligne.strip()
            for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if "proxy_pass" in ligne and not ligne.strip().startswith("#")
        ]

    def test_la_conf_de_dev_ne_vise_que_le_port_du_runserver(self):
        for ligne in self._proxys_de("dev.conf"):
            with self.subTest(ligne=ligne):
                self.assertNotIn(
                    "8001", ligne,
                    "La conf de dev vise le port de gunicorn, qui ne "
                    "tourne pas en dev : le site rendrait 502.",
                )

    def test_la_conf_de_prod_separe_le_http_et_le_websocket(self):
        proxys = self._proxys_de("default.conf")

        self.assertTrue(
            any("8001" in ligne for ligne in proxys),
            "La conf de prod ne vise pas gunicorn (8001).",
        )
        self.assertTrue(
            any("8000" in ligne for ligne in proxys),
            "La conf de prod ne vise pas daphne (8000) pour le WebSocket.",
        )
