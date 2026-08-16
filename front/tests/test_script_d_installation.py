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
SCRIPT_DE_CONFIGURATION = f"{REPERTOIRE_DES_SCRIPTS}/configurer_env.sh"

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


def _contenu_du_makefile():
    """Rend le Makefile tel quel, indentation comprise."""
    return (Path(settings.BASE_DIR) / "Makefile").read_text(encoding="utf-8")


def _est_absent_d_un_clone_frais(nom_du_dossier):
    """
    Ce dossier est-il exclu du depot, donc absent d'un clone frais ?
    / Is this directory excluded from the repo, hence missing on a
    fresh clone?

    LOCALISATION : front/tests/test_script_d_installation.py

    On lit `.gitignore`, et NON le systeme de fichiers : sur une
    machine de developpement, `media/` est plein depuis des semaines —
    l'y trouver ne dit rien de ce qu'un clone neuf recevra. C'est
    justement l'ecart entre les deux qui a produit la panne de
    production du 16 aout 2026.
    / We read .gitignore, NOT the filesystem: on a dev machine media/
    has been full for weeks, which says nothing about a fresh clone.

    On lit le fichier plutot que d'appeler git : les tests tournent
    dans le conteneur, ou git n'a pas a etre installe.
    """
    gitignore = (Path(settings.BASE_DIR) / ".gitignore").read_text(encoding="utf-8")
    for ligne in gitignore.splitlines():
        motif = ligne.strip()
        if not motif or motif.startswith(("#", "!")):
            continue
        # `/media/`, `./staticfiles/*`, `/tmp/*` designent tous le meme
        # dossier a la racine. / All three name the same top directory.
        nom = motif.removeprefix("./").removeprefix("/")
        nom = nom.removesuffix("/*").removesuffix("/")
        if nom == nom_du_dossier:
            return True
    return False


def _corps_de_la_cible(nom):
    """
    Rend les lignes du corps d'une cible, variables du Makefile resolues.
    / Returns a target's body lines, Makefile variables resolved.

    LOCALISATION : front/tests/test_script_d_installation.py

    Sans la resolution, un test qui cherche `configurer_env.sh`
    echouerait sur un Makefile qui l'appelle proprement par
    `$(SCRIPT_DE_CONFIGURATION)` — il PENALISERAIT le style attendu ici,
    ou chaque chemin de script est nomme une seule fois.
    / Without it, the test would penalise the very style this project
    asks for: each script path named once, in a variable.
    """
    variables = {}
    for ligne in _contenu_du_makefile().splitlines():
        if ligne.startswith(("\t", "#", " ")) or ":=" not in ligne:
            continue
        cle, _, valeur = ligne.partition(":=")
        variables[cle.strip()] = valeur.strip()

    corps = []
    dans_la_cible = False
    for ligne in _contenu_du_makefile().splitlines():
        if ligne.startswith(f"{nom}:"):
            dans_la_cible = True
            continue
        if dans_la_cible:
            if ligne.startswith("\t"):
                resolue = ligne.strip()
                # Les commentaires de recette (`@#`) CITENT des
                # commandes sans les lancer : les garder ferait passer
                # un test au vert sur une simple mention.
                # / Recipe comments name commands without running them.
                if resolue.startswith("@#") or resolue.startswith("#"):
                    continue
                for cle, valeur in variables.items():
                    resolue = resolue.replace(f"$({cle})", valeur)
                corps.append(resolue)
            elif ligne.strip():
                break
    return corps


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


class LInstallationFabriqueSonFichierDEnvironnementTest(TestCase):
    """
    Une machine neuve n'a pas de `.env`, et sans lui rien ne demarre.
    / A fresh machine has no .env, and nothing starts without it.

    LOCALISATION : front/tests/test_script_d_installation.py

    `docker compose up -d` lit le `.env` : sans lui, `POSTGRES_PASSWORD`
    est vide et PostgreSQL refuse de s'initialiser. L'installation
    commencait donc par une etape non ecrite — « copier .env.example et
    le remplir » — dont le README seul portait la trace, et dont
    l'oubli le plus courant est de laisser `CHANGEZ_MOI_EN_PROD` comme
    SECRET_KEY en production.
    / The install began with an unwritten step that only the README
    carried, whose most common outcome is a production SECRET_KEY still
    reading CHANGEZ_MOI_EN_PROD.
    """

    def _lignes_du_makefile(self):
        return _lignes_utiles("Makefile")

    def test_le_script_de_configuration_existe(self):
        self.assertTrue(
            (Path(settings.BASE_DIR) / SCRIPT_DE_CONFIGURATION).is_file(),
            f"{SCRIPT_DE_CONFIGURATION} est absent.",
        )

    def test_l_installation_configure_avant_de_demarrer_les_conteneurs(self):
        """
        L'ordre n'est pas negociable : compose LIT le `.env`.
        / The order is not negotiable: compose READS the .env.
        """
        corps = _corps_de_la_cible("install")

        rang_configuration = _rang_de(corps, "configurer_env.sh")
        rang_demarrage = _rang_de(corps, "docker compose up")

        self.assertIsNotNone(
            rang_configuration,
            "`make install` ne fabrique aucun .env : sur une machine "
            "neuve, PostgreSQL demarre sans mot de passe et echoue.",
        )
        self.assertIsNotNone(rang_demarrage, "`make install` ne demarre rien.")
        self.assertLess(
            rang_configuration,
            rang_demarrage,
            "Le .env est fabrique APRES le demarrage des conteneurs : "
            "compose l'a deja lu, vide.",
        )

    def test_les_secrets_sont_tires_au_hasard_jamais_demandes(self):
        # Une SECRET_KEY saisie a la main est une SECRET_KEY faible, ou
        # recopiee d'un autre projet. / A hand-typed SECRET_KEY is a
        # weak one, or one copied from another project.
        code = "\n".join(_lignes_utiles(SCRIPT_DE_CONFIGURATION))

        self.assertIn(
            "openssl rand",
            code,
            "Les secrets ne sont pas tires au hasard.",
        )
        for secret in ("SECRET_KEY", "POSTGRES_PASSWORD"):
            with self.subTest(secret=secret):
                self.assertNotIn(
                    f'demander "{secret}',
                    code,
                    f"{secret} est DEMANDEE a l'utilisateur au lieu "
                    f"d'etre tiree au hasard.",
                )

    def test_le_fichier_existant_n_est_jamais_ecrase(self):
        """
        Relancer `make install` ne doit pas effacer les cles API.
        / Re-running `make install` must not wipe the API keys.

        LOCALISATION : front/tests/test_script_d_installation.py

        `make install` est rejoue a CHAQUE demarrage de conteneur.
        Regenerer le .env y perdrait les cles API, le mot de passe de la
        base — donc l'acces aux donnees — et la passphrase du depot de
        sauvegarde, ce qui rendrait toutes les archives illisibles.
        / Regenerating it would lose the API keys, the database password
        and the backup passphrase, making every archive unreadable.
        """
        lignes = _lignes_utiles(SCRIPT_DE_CONFIGURATION)
        code = "\n".join(lignes)

        # On vise le garde-fou EXACT. Chercher `-f ` n'importe ou
        # suffisait : mesure du 16 aout 2026, le bloc d'idempotence
        # supprime, le test restait vert grace au `[ -f "$FICHIER_MODELE" ]`
        # qui vient juste apres.
        # / Measured: with the idempotence block removed, looking for
        # `-f ` anywhere stayed green thanks to an unrelated check.
        self.assertIn(
            '[ -f "$FICHIER_ENV" ]',
            code,
            "Rien ne verifie si un .env existe deja avant d'en ecrire "
            "un : une relance de make install effacerait les cles API "
            "et la passphrase du depot de sauvegarde.",
        )

        # Et ce garde-fou SORT, il ne se contente pas de prevenir.
        # / And that guard exits; it does not merely warn.
        rang_du_garde = _rang_de(lignes, '[ -f "$FICHIER_ENV" ]')
        rang_de_l_ecriture = _rang_de(lignes, 'cp "$FICHIER_MODELE" "$FICHIER_ENV"')
        sortie_avant_ecriture = any(
            "exit 0" in ligne
            for ligne in lignes[rang_du_garde:rang_de_l_ecriture]
        )
        self.assertTrue(
            sortie_avant_ecriture,
            "Le garde-fou constate qu'un .env existe mais n'arrete pas "
            "le script : le fichier est ecrase quand meme.",
        )

    def test_debug_et_nginx_sont_ecrits_ensemble(self):
        """
        Un seul choix pour deux variables couplees.
        / One choice for two coupled variables.

        LOCALISATION : front/tests/test_script_d_installation.py

        `DEBUG` et `NGINX_CONF` doivent bouger ENSEMBLE : la conf de
        prod avec `DEBUG=true` envoie `/` vers le port 8001, ou personne
        n'ecoute, et tout le site rend 502. Les demander separement,
        c'est offrir a l'utilisateur la possibilite de se tromper — le
        script ne pose donc qu'UNE question, « dev ou prod », et ecrit
        les deux lignes.
        / Asking for them separately offers the user a chance to get it
        wrong; one question writes both lines.
        """
        lignes = _lignes_utiles(SCRIPT_DE_CONFIGURATION)
        code = "\n".join(lignes)

        for variable in ("DEBUG", "NGINX_CONF"):
            with self.subTest(variable=variable):
                self.assertIn(
                    f"remplacer_la_ligne {variable}",
                    code,
                    f"{variable} n'est jamais ecrite dans le .env.",
                )
        self.assertIn(
            "dev.conf",
            code,
            "La configuration nginx de dev n'est jamais ecrite : un "
            "poste de dev recevrait celle de production, et tout le "
            "site rendrait 502.",
        )

        # Et surtout : NGINX_CONF ne fait l'objet d'AUCUNE question.
        # C'est ce qui rend le couple indeformable — on ne peut pas
        # repondre « dev » puis « default.conf ».
        # / And above all: NGINX_CONF is never asked about, which is
        # what makes the pair impossible to get out of step.
        for ligne in lignes:
            if "demander" in ligne and "NGINX" in ligne:
                with self.subTest(ligne=ligne):
                    self.fail(
                        "NGINX_CONF est DEMANDEE separement de DEBUG : "
                        "on peut donc les mettre en desaccord, et le "
                        "site rend 502 sur toutes ses pages."
                    )

    def test_les_dossiers_montes_sont_crees_avant_les_conteneurs(self):
        """
        Docker cree un point de montage absent en ROOT.
        / Docker creates a missing bind-mount source as ROOT.

        LOCALISATION : front/tests/test_script_d_installation.py

        `docker-compose.yml` monte `./staticfiles` et `./media` dans
        nginx. Ni l'un ni l'autre n'est suivi par git : un clone frais ne
        les contient pas. Au premier `docker compose up -d`, c'est le
        DEMON Docker — donc root — qui les cree, en `root:root` 755. Le
        conteneur web, lui, tourne en uid 1000 (`USER hypostasia`,
        Dockerfile) : `collectstatic` ne peut plus creer
        `staticfiles/admin`, `bin/install.sh` s'arrete sous `set -e`, et
        la politique `restart: unless-stopped` relance le conteneur en
        boucle.

        Mesure du 16 aout 2026, `docker run -v <chemin absent>:/x` :
        le dossier apparait en `0 0` (root:root), et un `mkdir` par
        l'uid 1000 rend « Permission denied ». Panne constatee en
        production le meme jour, sur un clone neuf.

        Le `mkdir -p` de `bin/install.sh` ne rattrape RIEN : il tourne
        dans le conteneur, apres coup, et `mkdir -p` reussit sur un
        dossier existant quel qu'en soit le proprietaire. Les dossiers
        doivent donc etre crees SUR L'HOTE, avant que Docker n'y pense.
        / install.sh's mkdir -p catches nothing: it runs inside the
        container, too late, and mkdir -p succeeds on an existing
        directory whoever owns it.
        """
        corps = _corps_de_la_cible("install")

        rang_des_dossiers = _rang_de(corps, "mkdir -p")
        rang_du_demarrage = _rang_de(corps, "docker compose up")

        self.assertIsNotNone(
            rang_des_dossiers,
            "`make install` ne cree aucun dossier sur l'hote : Docker "
            "creera staticfiles/ et media/ en root, et le conteneur web "
            "bouclera sur une PermissionError.",
        )
        self.assertLess(
            rang_des_dossiers,
            rang_du_demarrage,
            "Les dossiers sont crees APRES le demarrage des conteneurs : "
            "Docker les a deja crees, en root.",
        )

        ligne = corps[rang_des_dossiers]
        for dossier in ("staticfiles", "media"):
            with self.subTest(dossier=dossier):
                self.assertIn(
                    dossier,
                    ligne,
                    f"{dossier}/ est monte par nginx et absent d'un "
                    f"clone frais : Docker le creera en root.",
                )

    def test_aucun_montage_hote_n_echappe_a_cette_precaution(self):
        """
        Un montage ajoute demain retombera dans le meme piege.
        / A mount added tomorrow falls into the same trap.

        LOCALISATION : front/tests/test_script_d_installation.py

        Ce test relit `docker-compose.yml` : tout chemin hote monte doit
        soit exister dans le depot (donc arriver avec le clone), soit
        etre cree par `make install` avant le demarrage. Sans lui, la
        panne de production du 16 aout 2026 se rejouerait a la premiere
        ligne de volume ajoutee.
        / Every host path mounted must either ship with the clone or be
        created by make install before startup.
        """
        import re

        compose = (Path(settings.BASE_DIR) / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        chemins_montes = set()
        for ligne in compose.splitlines():
            trouve = re.match(r"\s*-\s+\./([A-Za-z0-9_-]+)[/:]", ligne)
            if trouve:
                chemins_montes.add(trouve.group(1))

        self.assertTrue(chemins_montes, "Aucun montage hote trouve : test creux.")

        corps_de_l_install = "\n".join(_corps_de_la_cible("install"))
        montages_absents_du_clone = [
            chemin for chemin in sorted(chemins_montes)
            if _est_absent_d_un_clone_frais(chemin)
        ]

        self.assertIn(
            "media",
            montages_absents_du_clone,
            "media/ n'est plus ignore par git : ce test ne verifie plus "
            "rien. Le relire avant de le croire.",
        )

        for chemin in montages_absents_du_clone:
            with self.subTest(montage=chemin):
                self.assertIn(
                    chemin,
                    corps_de_l_install,
                    f"`./{chemin}` est monte par docker-compose et "
                    f"absent d'un clone frais, mais `make install` ne le "
                    f"cree pas : Docker le creera en root, et le "
                    f"conteneur web ne pourra pas y ecrire.",
                )

    def test_l_absence_de_terminal_ne_bloque_pas_l_installation(self):
        # Le script tourne aussi quand `make install` est appele depuis
        # un autre script. Sans terminal, il doit prendre ses valeurs
        # par defaut, pas attendre une reponse qui ne viendra jamais.
        # / Without a terminal it must fall back to defaults, not wait
        # for an answer that will never come.
        code = "\n".join(_lignes_utiles(SCRIPT_DE_CONFIGURATION))

        self.assertIn(
            "-t 0",
            code,
            "Rien ne detecte l'absence de terminal : `make install` "
            "lance depuis un script resterait bloque sur une question.",
        )


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
