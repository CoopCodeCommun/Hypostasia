"""
Ce que la sauvegarde borg fait reellement, et ce qu'elle refuse de faire.
/ What the borg backup actually does, and what it refuses to do.

LOCALISATION : front/tests/test_sauvegarde_borg.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_sauvegarde_borg \\
        --settings=hypostasia.settings_test_opus

POURQUOI TESTER DES SCRIPTS DE SAUVEGARDE

Parce qu'une sauvegarde ne se signale JAMAIS quand elle se degrade. Un
`prune` sans filtre rogne les archives d'une autre stack, un dump ecrit
sans verrou produit une archive VIDE, une passphrase recopiee dans un
script part sur la forge au premier `git add -A` distrait. Aucun de ces
trois accidents ne leve d'erreur : ils se decouvrent le jour de la
restauration, c'est-a-dire trop tard.
/ A backup never reports its own decay: these accidents surface on the
day you restore, which is too late.

Ces tests ne lancent aucune sauvegarde — ils n'ont ni depot ni reseau.
Ils lisent les scripts et le Makefile, et tiennent les invariants que
personne ne peut voir a l'oeil nu.
/ They run no backup; they read the scripts and hold the invariants.

LES INVARIANTS TENUS ICI

1. Aucun secret dans un script versionne : tout vient du `.env`.
2. Le dump est pris sous verrou, en format restaurable, et une archive
   sans dump n'est jamais creee.
3. Le `prune` ne touche que les archives de CETTE stack.
4. La verification DEROULE le dump : un dump tronque doit echouer.
5. La restauration demande une confirmation, et n'ecrase jamais le
   `.env` courant — il porte la passphrase du depot en service.
6. Le Makefile APPELLE les scripts, il ne les recopie pas.
7. `make install` attend le socket du mode dans lequel il tourne.
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase

REPERTOIRE_DES_SCRIPTS = "bin"
SCRIPT_DE_SAUVEGARDE = f"{REPERTOIRE_DES_SCRIPTS}/backup.sh"
SCRIPT_DE_RESTAURATION = f"{REPERTOIRE_DES_SCRIPTS}/restore.sh"
SCRIPT_DE_VERIFICATION = f"{REPERTOIRE_DES_SCRIPTS}/check_backup.sh"
SCRIPT_D_INITIALISATION = f"{REPERTOIRE_DES_SCRIPTS}/init_backup.sh"
SCRIPT_DE_VERIFICATION_PROD = f"{REPERTOIRE_DES_SCRIPTS}/verifier_prod.sh"

TOUS_LES_SCRIPTS = (
    SCRIPT_DE_SAUVEGARDE,
    SCRIPT_DE_RESTAURATION,
    SCRIPT_DE_VERIFICATION,
    SCRIPT_D_INITIALISATION,
    SCRIPT_DE_VERIFICATION_PROD,
)


def _contenu(chemin_relatif):
    """Rend le texte integral d'un fichier du depot."""
    return (Path(settings.BASE_DIR) / chemin_relatif).read_text(encoding="utf-8")


def _lignes_utiles(chemin_relatif):
    """
    Rend les lignes d'un fichier, commentaires et vide exclus.
    / Returns a file's lines, comments and blanks excluded.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    Les commentaires sont ecartes : ils CITENT les commandes sans les
    lancer. Un test qui les lirait passerait au vert sur une simple
    mention — et c'est precisement ce que ces scripts font beaucoup,
    puisqu'ils documentent la restauration dans leur en-tete.
    / Comments name commands without running them, and these scripts
    quote a lot of commands in their headers.
    """
    lignes = []
    for ligne in _contenu(chemin_relatif).splitlines():
        nettoyee = ligne.strip()
        if not nettoyee or nettoyee.startswith("#"):
            continue
        lignes.append(nettoyee)
    return lignes


def _code_utile(chemin_relatif):
    """Rend le code d'un fichier en un seul bloc, commentaires exclus."""
    return "\n".join(_lignes_utiles(chemin_relatif))


def _rang_de(lignes, motif):
    """Rend l'index de la premiere ligne portant `motif`, ou None."""
    return next((i for i, ligne in enumerate(lignes) if motif in ligne), None)


def _commande_complete(chemin_relatif, debut_de_la_commande):
    """
    Rend UNE commande shell entiere, continuations recollees.
    / Returns one whole shell command, continuations joined.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    `borg create` tient sur cinq lignes, une par chemin archive. Un test
    qui chercherait « media » n'importe ou dans le fichier passerait au
    vert alors meme que media/ aurait ete retire de la commande : le nom
    survit dans la variable qui le porte. Recoller la commande est ce
    qui rend l'assertion vraie.
    / A test looking for "media" anywhere would stay green even after
    media/ was removed from the command: the name survives in its
    variable. Joining the continuations is what makes it real.
    """
    lignes = _lignes_utiles(chemin_relatif)
    for index, ligne in enumerate(lignes):
        if debut_de_la_commande not in ligne:
            continue
        morceaux = [ligne]
        while morceaux[-1].endswith("\\") and index + 1 < len(lignes):
            index += 1
            morceaux.append(lignes[index])
        return " ".join(morceau.rstrip("\\").strip() for morceau in morceaux)
    return ""


class LesScriptsDeSauvegardeExistentTest(TestCase):
    """
    LOCALISATION : front/tests/test_sauvegarde_borg.py
    """

    def test_les_cinq_scripts_sont_ranges_dans_bin(self):
        for chemin in TOUS_LES_SCRIPTS:
            with self.subTest(script=chemin):
                self.assertTrue(
                    (Path(settings.BASE_DIR) / chemin).is_file(),
                    f"{chemin} est absent.",
                )


class AucunSecretDansLesScriptsTest(TestCase):
    """
    Un script est fait pour etre versionne ; le `.env` ne l'est pas.
    / Scripts are versioned; the .env is not.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    Une passphrase ecrite dans un script finit poussee sur la forge, et
    la sauvegarde devient lisible par quiconque a le depot. C'est la
    regle centrale du kit borgwarehouse dont ces scripts sont issus.
    / A passphrase written into a script ends up pushed to the forge.
    """

    VARIABLES_SENSIBLES = (
        "BORG_PASSPHRASE",
        "POSTGRES_PASSWORD",
        "SECRET_KEY",
    )

    def test_aucun_script_n_affecte_une_valeur_a_un_secret(self):
        """
        LOCALISATION : front/tests/test_sauvegarde_borg.py

        La regle : une affectation a un secret ne vaut que si sa valeur
        VIENT D'AILLEURS — une expansion, une substitution de commande.
        Tout le reste est une valeur en dur.

        La version precedente de ce test acceptait aussi les valeurs
        entre quotes simples et sautait les lignes `export ` : mesure du
        16 aout 2026, `BORG_PASSPHRASE='hunter2'` et
        `export BORG_PASSPHRASE=hunter2` passaient tous deux au vert. Or
        la forme la plus naturelle d'un secret en dur en shell est
        precisement quotee.
        / Measured: both a single-quoted secret and an `export`ed one
        passed — and quoted is exactly how one writes a secret by hand.
        """
        for chemin in TOUS_LES_SCRIPTS:
            for variable in self.VARIABLES_SENSIBLES:
                for ligne in _lignes_utiles(chemin):
                    debut = f"{variable}="
                    if debut not in ligne:
                        continue
                    valeur = ligne.split(debut, 1)[1].lstrip()
                    # On ote UN niveau de quotes : c'est ce qui
                    # demasque `VAR='secret'` sans rejeter
                    # `VAR="$AUTRE"`.
                    # / Strip one quoting level: unmasks VAR='secret'
                    # without rejecting VAR="$OTHER".
                    for quote in ('"', "'"):
                        if valeur.startswith(quote):
                            valeur = valeur[1:]
                            break
                    with self.subTest(script=chemin, ligne=ligne):
                        self.assertTrue(
                            valeur == "" or valeur.startswith("$"),
                            f"{chemin} ecrit un secret en dur : {ligne}",
                        )

    def test_les_scripts_lisent_le_fichier_d_environnement(self):
        for chemin in (
            SCRIPT_DE_SAUVEGARDE,
            SCRIPT_DE_RESTAURATION,
            SCRIPT_DE_VERIFICATION,
        ):
            with self.subTest(script=chemin):
                self.assertIn(
                    ".env",
                    _code_utile(chemin),
                    f"{chemin} ne lit pas le .env : d'ou viendraient "
                    f"alors l'adresse du depot et sa passphrase ?",
                )


class LaSauvegardeEstPriseSousVerrouEtRestaurableTest(TestCase):
    """
    Les trois manieres silencieuses de rater une sauvegarde.
    / The three silent ways to fail a backup.

    LOCALISATION : front/tests/test_sauvegarde_borg.py
    """

    def test_un_verrou_empeche_deux_sauvegardes_simultanees(self):
        # Sans verrou, un lancement manuel tombant pendant le cron
        # partage le meme dossier de dump : le premier a finir le
        # supprime pendant que l'autre archive encore, et l'archive
        # arrive SANS DUMP, en silence.
        # / Without the lock, one run deletes the dump dir while the
        # other is still archiving: an archive with no dump.
        self.assertIn(
            "flock",
            _code_utile(SCRIPT_DE_SAUVEGARDE),
            "Aucun verrou : une sauvegarde manuelle lancee pendant le "
            "cron peut produire une archive vide, sans rien signaler.",
        )

    def test_le_dump_est_pris_au_format_restaurable(self):
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn("pg_dump", code, "Aucun dump PostgreSQL.")
        self.assertIn(
            "-Fc",
            code,
            "Le dump n'est pas au format custom : on perd pg_restore, "
            "donc la restauration selective et la verification qui "
            "deroule le fichier.",
        )

    def test_un_dump_vide_n_est_jamais_archive(self):
        # Un dump vide archive proprement donne une archive credible et
        # inutilisable. / An empty dump archives cleanly and restores
        # nothing.
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn(
            '[ ! -s "$FICHIER_DU_DUMP" ]', code,
            "Rien ne verifie que le dump est non vide avant d'archiver.",
        )

    def test_l_absence_de_media_arrete_la_sauvegarde(self):
        """
        media/ est la RAISON D'ETRE de cette sauvegarde.
        / media/ is why this backup exists.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        La base se reconstruit, les PDF et les audios non. Or `borg
        create` sur un chemin absent ne rend qu'un code 1 — mesure du
        16 aout 2026, borg 1.4.4 — que la tolerance aux avertissements
        laisse passer. Un volume non monte ou un dossier renomme donne
        alors des semaines d'archives « fraiches » sans un seul media,
        et on ne l'apprend qu'en restaurant.
        / borg create on a missing path returns 1, which the warning
        tolerance swallows: weeks of fresh-looking archives with no
        media at all.
        """
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn(
            '[ ! -d "$REPERTOIRE_DES_MEDIAS" ]',
            code,
            "Rien ne verifie que media/ existe avant d'archiver.",
        )

    def test_la_place_liberee_par_la_rotation_l_est_reellement(self):
        """
        `prune` delie les archives ; `compact` rend la place.
        / `prune` unlinks archives; `compact` frees the space.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Depuis borg 1.2, `prune` seul ne libere RIEN. Mesure du 16 aout
        2026, borg 1.4.4, depot local, 4 archives de 20 Mo aleatoires :
        77 Mo avant, **77 Mo apres un prune qui a pourtant supprime
        trois archives**, 20 Mo apres `compact`. Sans cet appel, la
        retention n'existe que sur le papier et le quota du depot se
        remplit jusqu'a ce que la sauvegarde echoue, des mois plus tard,
        pour une raison sans rapport apparent.
        / Measured: 77 MB before, 77 MB after a prune that deleted three
        archives, 20 MB after compact.
        """
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn(
            "borg compact",
            code,
            "La rotation ne libere aucune place : `prune` delie les "
            "archives, seul `compact` rend l'espace (borg >= 1.2).",
        )

    def test_les_avertissements_de_borg_ne_tuent_pas_la_sauvegarde(self):
        """
        Le code 1 de borg est un avertissement, pas une panne.
        / borg's exit code 1 is a warning, not a failure.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        borg rend 1 quand un fichier a bouge pendant sa lecture — ce qui
        arrive des qu'un import tourne pendant l'archivage de `media/`.
        Sous `set -e`, un `borg create` nu ferait echouer la sauvegarde
        a chaque fois, et le cron rendrait une erreur une nuit sur deux
        pour une archive parfaitement bonne.
        / borg returns 1 when a file moved while being read, which
        happens as soon as an import runs during the archiving.
        """
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn("borg_tolerant", code, "La tolerance a disparu.")
        for commande in ("borg create", "borg prune", "borg compact"):
            with self.subTest(commande=commande):
                self.assertIn(
                    f"borg_tolerant {commande}",
                    code,
                    f"`{commande}` est appele sans la tolerance : un "
                    f"simple avertissement tuerait la sauvegarde.",
                )

    def test_l_archive_porte_la_base_les_medias_et_l_environnement(self):
        # Le code est dans git ; ces trois-la ne le sont pas. Une
        # archive sans media/ perd les PDF et les audios ; sans .env,
        # la restauration redemande toutes les cles API.
        # / The code is in git; these three are not.
        creation = _commande_complete(SCRIPT_DE_SAUVEGARDE, "borg create")

        self.assertTrue(creation, "Aucune commande `borg create`.")
        self.assertIn(
            "$REPERTOIRE_DU_DUMP", creation, "Le dump n'est pas archive.",
        )
        self.assertIn(
            "$REPERTOIRE_DES_MEDIAS", creation,
            "media/ n'est pas dans la commande d'archivage : les PDF, "
            "audios et transcriptions ne seraient pas sauvegardes.",
        )
        self.assertIn(
            "$FICHIER_ENV", creation,
            "Le .env n'est pas dans la commande d'archivage : une "
            "restauration redemanderait toutes les cles.",
        )

    def test_deux_sauvegardes_a_la_suite_ne_se_marchent_pas_dessus(self):
        """
        borg refuse deux archives homonymes.
        / borg refuses two archives sharing a name.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Le nom d'archive porte l'horodatage. A la minute pres — la
        granularite du kit d'origine — deux `make backup` lances a la
        suite echouent sur « Archive ... already exists », rendu a
        l'utilisateur sous la forme d'un « code 2 » qui ne dit pas
        pourquoi (constate le 16 aout 2026, une sauvegarde prenant 4 s).
        Relancer une sauvegarde juste apres une autre est un geste
        normal.
        / At minute granularity, two consecutive backups fail with a
        "code 2" that does not say why. Measured: a backup takes 4 s.
        """
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn(
            "%H-%M-%S",
            code,
            "L'horodatage des archives s'arrete a la minute : deux "
            "sauvegardes lancees a la suite portent le meme nom, et la "
            "seconde echoue.",
        )

    def test_le_prune_ne_touche_que_les_archives_de_cette_stack(self):
        # Sans ce filtre, deux sauvegardes partageant un depot se
        # rognent mutuellement leur retention, en silence.
        # / Without this filter, two backups sharing a repository trim
        # each other's retention, silently.
        rotation = _commande_complete(SCRIPT_DE_SAUVEGARDE, "borg prune")

        self.assertTrue(rotation, "Aucune rotation : le depot grossit sans fin.")
        self.assertIn(
            '--glob-archives "$PREFIXE-*"',
            rotation,
            "Le prune n'est pas filtre sur le prefixe : il peut "
            "supprimer les archives d'une autre stack du meme depot.",
        )

    def test_les_traces_de_travail_sont_ignorees_par_git(self):
        """
        LOCALISATION : front/tests/test_sauvegarde_borg.py

        La cle privee donne acces au depot qu'elle protege. Le dossier
        de dump, lui, porte un dump PostgreSQL EN CLAIR : commite par
        distraction, il publie toute la base — verbatims nominatifs
        compris — sur la forge.
        / The private key grants access to the repository it protects;
        the dump directory holds a plaintext dump of the whole database.
        """
        gitignore = _contenu(".gitignore")

        for motif, ce_que_c_est in (
            ("/bin/.ssh/", "la cle privee du depot"),
            ("/.dump-pg-", "le dump PostgreSQL en clair"),
            ("/.backup-", "le verrou de sauvegarde"),
            ("/.restauration-", "le dossier d'extraction d'une restauration"),
        ):
            with self.subTest(ignore=ce_que_c_est):
                self.assertIn(
                    motif,
                    gitignore,
                    f"git ne l'ignore pas : {ce_que_c_est}.",
                )


class LesDeuxPiegesDeShellQuiN_ontFaitAucunBruitTest(TestCase):
    """
    Deux pannes trouvees en EXECUTANT les scripts, pas en les lisant.
    / Two failures found by RUNNING the scripts, not by reading them.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    Aucune des deux ne leve d'erreur visible, et toutes deux rendent la
    sauvegarde fausse. Elles sont tenues ici parce qu'elles se
    reproduiront au prochain script shell du projet.
    / Neither raises a visible error, and both make the backup wrong.
    """

    def test_le_fichier_d_environnement_n_est_pas_source_tel_quel(self):
        """
        `UID` est en LECTURE SEULE dans bash, et le .env le porte.
        / UID is read-only in bash, and the .env carries it.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Le .env du projet declare `UID=1000` et `GID=1000` pour docker
        compose. Un `. "$FICHIER_ENV"` brut echoue sur cette ligne, et
        avec `set -e` le script s'arrete LA. Mesure du 16 aout 2026 :
        `bash bin/backup.sh` sortait en 11 ms, sur une seule ligne
        d'erreur, sans avoir rien archive — et un cron ne lit pas les
        lignes d'erreur.
        / Measured: the backup exited in 11 ms having archived nothing,
        on one error line — and a cron does not read error lines.
        """
        for chemin in (
            SCRIPT_DE_SAUVEGARDE,
            SCRIPT_DE_RESTAURATION,
            SCRIPT_DE_VERIFICATION,
            SCRIPT_DE_VERIFICATION_PROD,
        ):
            with self.subTest(script=chemin):
                code = _code_utile(chemin)
                self.assertNotIn(
                    '. "$FICHIER_ENV"',
                    code,
                    "Le .env est source tel quel : `UID=1000` est une "
                    "affectation a une variable en lecture seule, et "
                    "sous `set -e` le script s'arrete a cette ligne "
                    "sans rien faire.",
                )
                self.assertIn(
                    "(UID|GID)=",
                    code,
                    "Rien n'ecarte UID et GID a la lecture du .env.",
                )

    def test_aucune_recherche_par_tube_dans_un_script_a_pipefail(self):
        """
        `printf | grep -q` ment sous `pipefail`.
        / `printf | grep -q` lies under `pipefail`.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        `grep -q` sort des la premiere correspondance ; l'ecrivain du
        tube prend alors un SIGPIPE et rend 141 ; `pipefail` fait de ce
        141 le statut du pipeline. Une correspondance TROUVEE est donc
        lue comme une ABSENCE — mais seulement quand l'entree depasse le
        tampon du tube, ce qui rend le defaut intermittent.

        Mesure du 16 aout 2026, sur la table des matieres reelle d'un
        dump (625 lignes) : avec `pipefail`, les QUATRE tables cherchees
        sont declarees absentes ; sans, aucune. Sur trois lignes, le
        meme code passe au vert — c'est pourquoi un essai jouet ne le
        montre pas.
        / Measured on a real 625-line dump TOC: with pipefail all four
        tables are reported missing; without, none. A three-line toy
        example stays green, which is why it hides.
        """
        import re

        for chemin in TOUS_LES_SCRIPTS:
            code = _code_utile(chemin)
            if "pipefail" not in code:
                continue
            for ligne in _lignes_utiles(chemin):
                if re.search(r"\|\s*grep\s+-[A-Za-z]*q", ligne):
                    with self.subTest(script=chemin, ligne=ligne):
                        self.fail(
                            "Recherche par tube dans un script a "
                            "pipefail : une correspondance trouvee "
                            "sera lue comme une absence des que "
                            f"l'entree depasse le tampon.  {ligne}"
                        )


class LaSauvegardeSeConfigureTouteSeuleTest(TestCase):
    """
    `make backup` sur une machine neuve doit sauvegarder, pas refuser.
    / `make backup` on a fresh machine must back up, not refuse.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    Un premier lancement qui rend « BORG_PREFIX absent du .env » met
    l'utilisateur devant une deuxieme commande a trouver. Le script sait
    parfaitement, lui, que rien n'est configure : c'est a lui d'enchainer.
    / A first run answering "BORG_PREFIX missing" puts the user in front
    of a second command to find. The script already knows.
    """

    def test_le_script_enchaine_sur_l_initialisation_quand_rien_n_est_configure(self):
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        self.assertIn(
            "init_backup.sh",
            code,
            "`bash bin/backup.sh` sur une machine neuve ne configure "
            "rien : il rend une erreur et laisse chercher la commande "
            "suivante.",
        )

    def test_l_absence_de_configuration_n_est_plus_une_erreur_fatale(self):
        """
        LOCALISATION : front/tests/test_sauvegarde_borg.py

        `${BORG_REPO:?...}` arrete le script AVANT toute chance de
        s'initialiser. Les trois variables du depot doivent donc etre
        lues sans cette forme-la.
        / `${VAR:?...}` aborts before any chance to self-configure.
        """
        code = _code_utile(SCRIPT_DE_SAUVEGARDE)

        for variable in ("BORG_PREFIX", "BORG_REPO", "BORG_PASSPHRASE"):
            with self.subTest(variable=variable):
                self.assertNotIn(
                    f"${{{variable}:?",
                    code,
                    f"`{variable}` est exigee avec `:?` : le script "
                    f"meurt avant d'avoir pu se configurer.",
                )

    def test_le_nom_des_archives_vient_de_la_machine_et_n_est_pas_demande(self):
        """
        Une archive doit dire d'ou elle vient.
        / An archive must say where it comes from.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Le prefixe nomme les archives ET la cle SSH du depot. Le tirer
        du nom de la machine repond aux deux besoins — reconnaitre la
        provenance d'une sauvegarde quand plusieurs machines partagent
        un serveur, et donner a la cle un nom unique sur la machine —
        et supprime une question a laquelle personne n'a de meilleure
        reponse que `hostname`.
        / Derived from the machine's name: it answers both needs and
        removes a question nobody answers better than `hostname` does.
        """
        lignes = _lignes_utiles(SCRIPT_D_INITIALISATION)
        code = "\n".join(lignes)

        self.assertIn(
            "hostname",
            code,
            "Le prefixe des archives ne vient pas du nom de la machine.",
        )
        for ligne in lignes:
            if "demander" in ligne and "refixe" in ligne:
                with self.subTest(ligne=ligne):
                    self.fail(
                        "Le prefixe est DEMANDE : c'est une question de "
                        "plus, a laquelle `hostname` repond mieux."
                    )

    def test_le_coffre_affiche_les_quatre_elements_en_entier(self):
        """
        Ce qui n'est pas affiche ne part pas au coffre.
        / What is not displayed does not reach the vault.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Le bloc du coffre est le SEUL moment ou ces quatre elements
        existent ensemble sous les yeux de quelqu'un. Trois ouvrent le
        chiffrement — adresse, passphrase, `borg key export` — et le
        quatrieme, la cle SSH privee, ouvre l'acces au depot.

        Afficher le CHEMIN de la cle ne suffit pas : on copie ce qu'on
        voit. Un chemin oblige a aller chercher le fichier, ce qu'on ne
        fait pas a 2 h du matin, et la cle reste sur la machine — la
        seule qui ne sera plus la le jour ou on en a besoin.
        / Displaying the key's PATH is not enough: people copy what they
        see, and the key stays on the very machine that will be gone.
        """
        code = _code_utile(SCRIPT_D_INITIALISATION)

        self.assertIn(
            'cat "$CLE_SSH"',
            code,
            "La cle SSH PRIVEE n'est pas affichee, seulement son "
            "chemin : elle ne partira pas au coffre, et sans elle le "
            "depot est inaccessible depuis une autre machine.",
        )
        self.assertIn(
            'borg key export "$BORG_REPO"',
            code,
            "La cle de chiffrement du depot n'est pas exportee.",
        )
        for element in ("$BORG_PASSPHRASE", "$BORG_REPO", "$BORG_PREFIX"):
            with self.subTest(element=element):
                self.assertIn(
                    element,
                    code,
                    f"{element} n'est pas affiche : sans lui, les trois "
                    f"autres elements ne servent a rien.",
                )

    def test_le_coffre_donne_le_nom_exact_du_fichier_de_cle(self):
        """
        La cle doit reprendre le nom que le script cherchera.
        / The key must carry the name the script will look for.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Les scripts cherchent `bin/.ssh/${BORG_PREFIX}_ed25519`. Sur la
        machine de secours, une cle reposee sous un autre nom n'est
        simplement pas vue : `BORG_RSH` n'est pas pose, ssh se rabat sur
        la configuration systeme, et borgwarehouse refuse la connexion —
        avec un message qui parle de permissions, jamais de nom de
        fichier.
        / A key restored under another name is simply not seen, and the
        refusal talks about permissions, never about the file name.
        """
        code = _code_utile(SCRIPT_D_INITIALISATION)

        self.assertIn(
            "_ed25519",
            code,
            "Le bloc du coffre ne donne pas le nom que le fichier de "
            "cle devra porter sur la machine de secours.",
        )
        """
        L'initialisation relance la sauvegarde ; l'inverse aussi.
        / Init runs the backup, and the backup runs init.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        `bin/init_backup.sh` finit par une premiere sauvegarde. Si
        `bin/backup.sh` rappelait l'initialisation sans que le .env ait
        ete complete entre-temps, les deux s'appelleraient sans fin. Le
        `exec` garantit qu'aucune pile ne s'empile, et l'ecriture du
        .env par l'initialisation garantit la sortie de boucle.
        / `exec` guarantees no stack builds up; the .env written by init
        guarantees the loop ends.
        """
        commande = _commande_complete(SCRIPT_DE_SAUVEGARDE, "init_backup.sh")

        self.assertIn(
            "exec ",
            commande,
            "L'initialisation est appelee sans `exec` : la sauvegarde "
            "qu'elle lance a son tour rappellerait ce script.",
        )


class LaVerificationDerouleLeDumpTest(TestCase):
    """
    Verifier qu'une archive existe ne dit rien de sa restaurabilite.
    / Checking that an archive exists says nothing about restorability.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    Un dump tronque — disque plein, conteneur tue en plein dump — a une
    taille credible, se trouve bien dans l'archive, et ne se restaure
    pas. Seule une lecture INTEGRALE le demasque : la table des
    matieres d'un dump custom est en tete du fichier, donc `pg_restore
    -l` reussit sur un fichier coupe en deux.
    / Only a full read unmasks a truncated dump: the TOC sits at the
    head of the file, so `pg_restore -l` succeeds on a halved one.
    """

    def test_la_fraicheur_de_la_derniere_archive_est_controlee(self):
        code = _code_utile(SCRIPT_DE_VERIFICATION)

        self.assertIn(
            '-le "$AGE_MAX_HEURES"',
            code,
            "L'age de la derniere archive n'est COMPARE a rien : un "
            "cron mort depuis trois semaines passerait au vert.",
        )

    def test_la_fraicheur_ne_regarde_que_les_archives_de_cette_stack(self):
        fraicheur = _commande_complete(SCRIPT_DE_VERIFICATION, "borg list --glob-archives")

        self.assertIn(
            '--glob-archives "$BORG_PREFIX-*"',
            fraicheur,
            "Sans filtre sur le prefixe, l'archive fraiche d'une AUTRE "
            "stack du meme depot suffirait a nous rassurer.",
        )

    def test_le_dump_est_deroule_entierement_et_pas_seulement_liste(self):
        """
        LOCALISATION : front/tests/test_sauvegarde_borg.py

        On cherche la commande EXACTE. Chercher « /dev/null » quelque
        part dans le fichier ne prouverait rien : le script en compte
        six, toutes des redirections de sortie — verifie le 16 aout
        2026 en retirant le deroulement, le test restait au vert.
        / Looking for "/dev/null" anywhere proves nothing: the script
        holds six, all output redirections. Measured.
        """
        code = _code_utile(SCRIPT_DE_VERIFICATION)

        self.assertIn(
            "pg_restore -f /dev/null",
            code,
            "Le dump n'est pas DEROULE. `pg_restore -l` reussit sur un "
            "dump ampute de ses 100 derniers octets (mesure du 16 aout "
            "2026, PostgreSQL 17) : seul `pg_restore -f /dev/null` le "
            "demasque.",
        )

    def test_la_verification_sort_en_code_non_nul_si_ca_cloche(self):
        # C'est ce qui la rend utilisable telle quelle en monitoring.
        # Le compteur doit etre INCREMENTE et RELU : chercher `exit 1`
        # n'importe ou laisserait debrancher le compteur sans rougir.
        # / The counter must be both incremented and read back.
        code = _code_utile(SCRIPT_DE_VERIFICATION)

        self.assertIn(
            "NOMBRE_D_ERREURS + 1",
            code,
            "Le compteur d'erreurs n'est jamais incremente.",
        )
        self.assertIn(
            '"$NOMBRE_D_ERREURS" -eq 0',
            code,
            "Le compteur d'erreurs n'est jamais relu : la verification "
            "sortirait en 0 quoi qu'elle ait trouve.",
        )
        self.assertIn("exit 1", code, "La verification ne signale jamais d'echec.")

    def test_la_verification_regarde_le_contenu_de_l_archive(self):
        # Une archive qui se deroule sans porter media/ ni le .env est
        # une archive inutile. / An archive that unrolls but carries
        # neither media/ nor the .env is a useless archive.
        code = _code_utile(SCRIPT_DE_VERIFICATION)

        for motif, manque in (
            ("hypostasia\\.dump", "le dump"),
            ("/media/", "media/"),
            ("\\.env", "le .env"),
        ):
            with self.subTest(cherche=manque):
                self.assertIn(
                    motif,
                    code,
                    f"La verification ne regarde pas si {manque} est "
                    f"dans l'archive.",
                )

    def test_la_verification_distingue_une_stack_arretee_d_un_dump_casse(self):
        """
        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Les deux epreuves du dump tournent DANS le conteneur postgres.
        S'il ne tourne pas, elles echouent toutes les deux et le verdict
        serait « dump TRONQUE » sur une archive parfaitement saine — un
        monitoring reveillerait quelqu'un la nuit pour une sauvegarde
        qui n'a rien.
        / With the stack down, a healthy archive would be declared
        truncated, waking someone up for nothing.
        """
        code = _code_utile(SCRIPT_DE_VERIFICATION)

        self.assertIn(
            "dans_postgres true",
            code,
            "Rien ne verifie que le conteneur postgres repond avant "
            "d'eprouver le dump dedans.",
        )


class LaRestaurationDemandeUneConfirmationTest(TestCase):
    """
    Restaurer ECRASE la base en service.
    / Restoring OVERWRITES the live database.

    LOCALISATION : front/tests/test_sauvegarde_borg.py
    """

    def test_la_restauration_exige_une_confirmation_explicite(self):
        # Un mot a taper, pas un « o/n » : la frappe doit etre trop
        # deliberee pour partir d'un reflexe.
        # / A word to type, not a y/n: too deliberate to be a reflex.
        code = _code_utile(SCRIPT_DE_RESTAURATION)

        self.assertIn(
            "read -r -p",
            code,
            "La restauration ecrase la base sans rien demander.",
        )
        self.assertIn(
            '= "RESTAURER"',
            code,
            "La reponse n'est comparee a rien : n'importe quelle "
            "touche declencherait l'ecrasement.",
        )

        # Et la confirmation PRECEDE la destruction. Une confirmation
        # posee apres l'arret du conteneur ou apres le `pg_restore` ne
        # protege plus rien. / And it comes BEFORE the destruction.
        lignes = _lignes_utiles(SCRIPT_DE_RESTAURATION)
        rang_confirmation = _rang_de(lignes, '= "RESTAURER"')
        rang_arret = _rang_de(lignes, "compose -f \"$FICHIER_COMPOSE\" stop web")
        rang_restauration = _rang_de(lignes, "pg_restore --clean")

        self.assertIsNotNone(rang_arret, "Le conteneur web n'est jamais arrete.")
        self.assertIsNotNone(rang_restauration, "Rien ne restaure la base.")
        self.assertLess(
            rang_confirmation, rang_arret,
            "Le conteneur web est arrete AVANT la confirmation : le "
            "site tombe meme quand on repond non.",
        )
        self.assertLess(
            rang_confirmation, rang_restauration,
            "La base est ecrasee AVANT la confirmation.",
        )

    def test_la_restauration_ecrase_bien_la_base(self):
        # `pg_restore` sans `--clean` empile les donnees sur celles
        # deja presentes et echoue sur chaque contrainte d'unicite : on
        # obtient une base a moitie ancienne, a moitie restauree.
        # / Without --clean, pg_restore stacks onto existing data.
        code = _code_utile(SCRIPT_DE_RESTAURATION)

        self.assertIn("pg_restore", code)
        self.assertIn(
            "--clean",
            code,
            "Sans --clean, la restauration s'empile sur les donnees "
            "existantes : base a moitie ancienne, a moitie restauree.",
        )

    def test_la_restauration_cherche_les_contenus_au_lieu_de_les_reconstruire(self):
        """
        Une machine de secours n'a pas le meme chemin que l'originale.
        / A recovery machine does not share the original's path.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        borg archive des chemins ABSOLUS. Reconstruire l'emplacement de
        `media/` en collant le repertoire du projet au dossier
        d'extraction revient a supposer que la machine qui restaure
        porte le projet au MEME chemin que celle qui a sauvegarde. C'est
        vrai a l'essai, sur la machine d'origine — et faux le jour du
        sinistre, quand on remonte ailleurs. Le dump se restaurerait, et
        `media/` serait declare absent : les 473 Mo de PDF, d'audios et
        de transcriptions resteraient dans l'archive.
        / True in rehearsal on the original machine, false on the day it
        matters: the dump restores and media/ is reported missing.
        """
        code = _code_utile(SCRIPT_DE_RESTAURATION)

        self.assertNotIn(
            "$DOSSIER_DE_RESTAURATION${REPERTOIRE_DU_PROJET}",
            code,
            "Les chemins de l'archive sont RECONSTRUITS a partir du "
            "chemin local : la restauration sur une autre machine ne "
            "retrouverait ni media/ ni le .env.",
        )
        for contenu in ("'hypostasia.dump'", "'media'", "'.env'"):
            with self.subTest(contenu=contenu):
                self.assertIn(
                    f"-name {contenu}",
                    code,
                    f"{contenu} n'est pas CHERCHE dans l'arborescence "
                    f"extraite.",
                )

    def test_la_restauration_n_ecrase_jamais_le_fichier_d_environnement(self):
        """
        Le `.env` de l'archive porte une passphrase peut-etre perimee.
        / The archived .env may carry a stale passphrase.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        L'ecraser avec celui d'une vieille archive remplacerait
        BORG_PASSPHRASE par une valeur qui n'ouvre plus le depot en
        service : la restauration suivante deviendrait impossible, et
        on ne s'en apercevrait qu'a ce moment-la.
        / Overwriting it would replace the passphrase of the live
        repository, and the next restore would be impossible.
        """
        lignes = _lignes_utiles(SCRIPT_DE_RESTAURATION)

        # On verifie le COMPORTEMENT, pas le message. La version
        # precedente cherchait le mot « PROTEGE » — qui vit dans un
        # `echo` du bandeau : on pouvait ajouter la copie ecrasante et
        # garder le message, et le test restait vert.
        # / Behaviour, not message: the previous version looked for a
        # word living in an echo, so the overwrite could be added
        # alongside it and stay green.
        for ligne in lignes:
            if ligne.lstrip().startswith("echo "):
                continue
            ecrit_dans_le_env = (
                '> "$FICHIER_ENV"' in ligne
                or '>> "$FICHIER_ENV"' in ligne
                or ('cp ' in ligne and '"$FICHIER_ENV"' in ligne)
                or ('mv ' in ligne and '"$FICHIER_ENV"' in ligne)
                or ('sed -i' in ligne and '"$FICHIER_ENV"' in ligne)
            )
            with self.subTest(ligne=ligne):
                self.assertFalse(
                    ecrit_dans_le_env,
                    "La restauration ECRIT dans le .env courant : il "
                    "porte la passphrase du depot en service, et celle "
                    "de l'archive peut etre perimee. Le depot "
                    "deviendrait inaccessible, et on ne s'en "
                    f"apercevrait qu'a la restauration suivante. {ligne}",
                )


class LaVerificationDeProductionTest(TestCase):
    """
    Ce qu'on ne decouvre qu'au moment ou on en a besoin.
    / What you only discover when you need it.

    LOCALISATION : front/tests/test_sauvegarde_borg.py
    """

    def test_elle_controle_le_depot_le_cron_et_les_secrets_par_defaut(self):
        code = _code_utile(SCRIPT_DE_VERIFICATION_PROD)

        self.assertIn("BORG_REPO", code, "Le depot n'est pas verifie.")
        self.assertIn("crontab", code, "Le cron n'est pas verifie.")
        self.assertIn(
            "CHANGEZ_MOI",
            code,
            "Rien ne verifie que les secrets d'exemple ont ete "
            "remplaces : une prod peut tourner avec la SECRET_KEY du "
            "fichier d'exemple sans que rien ne le dise.",
        )

    def test_elle_controle_que_debug_et_nginx_vont_ensemble(self):
        # La conf de prod avec DEBUG=true envoie `/` vers le port 8001,
        # ou personne n'ecoute : 502 sur tout le site.
        # / The production nginx config with DEBUG=true sends / to a
        # port nobody listens on.
        code = _code_utile(SCRIPT_DE_VERIFICATION_PROD)

        self.assertIn("NGINX_CONF", code)
        self.assertIn("DEBUG", code)

    def test_elle_sort_en_code_non_nul_quand_elle_est_lancee_seule(self):
        code = _code_utile(SCRIPT_DE_VERIFICATION_PROD)

        self.assertIn(
            "exit 1",
            code,
            "Elle ne signale jamais d'echec : inutilisable en "
            "monitoring.",
        )


class LeMakefileAppelleLesScriptsDeSauvegardeTest(TestCase):
    """
    Le Makefile est une facade cote hote.
    / The Makefile is a host-side facade.

    LOCALISATION : front/tests/test_sauvegarde_borg.py

    Deux definitions d'une meme sequence finissent toujours par
    diverger : c'est ce qui a produit les deux dernieres pannes du
    projet. Une commande `borg create` recopiee dans le Makefile
    divergerait de celle du script au premier ajustement d'exclusion.
    / Two definitions of one sequence always drift apart.
    """

    def _lignes_du_makefile(self):
        return _lignes_utiles("Makefile")

    def test_les_cibles_de_sauvegarde_existent(self):
        contenu = _contenu("Makefile")

        for cible in ("backup:", "restore:", "backup-check:", "verif-prod:"):
            with self.subTest(cible=cible):
                self.assertIn(
                    f"\n{cible}",
                    contenu,
                    f"La cible `{cible[:-1]}` est absente du Makefile.",
                )

    def test_il_n_y_a_pas_de_cible_d_initialisation_separee(self):
        """
        Une seule cible a retenir : `make backup`.
        / One target to remember: `make backup`.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        `make backup-init` a existe une demi-journee. Une cible qu'on ne
        tape QU'UNE FOIS dans la vie d'une machine est une cible qu'on
        ne retient pas : au moment de sauvegarder, on tape `make backup`,
        et c'est a lui de savoir s'il doit d'abord se configurer.
        / A target typed once in a machine's lifetime is a target nobody
        remembers; `make backup` must know whether to configure itself.
        """
        contenu = _contenu("Makefile")

        self.assertNotIn(
            "\nbackup-init:",
            contenu,
            "La cible `backup-init` est revenue : c'est une chose de "
            "plus a retenir pour un geste qu'on ne fait qu'une fois.",
        )

    def test_les_cibles_appellent_les_scripts_sans_reecrire_borg(self):
        """
        Aucune commande borg ne vit dans le Makefile.
        / No borg command lives in the Makefile.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        On cherche les SOUS-COMMANDES, pas le mot « borg » : le texte
        d'aide des cibles le prononce forcement, et un test qui
        s'arreterait la interdirait d'ecrire une aide comprehensible.
        / We look for subcommands, not the word "borg": the help text
        necessarily says it.
        """
        sous_commandes = ("borg create", "borg prune", "borg init", "borg extract")

        for ligne in self._lignes_du_makefile():
            for sous_commande in sous_commandes:
                if sous_commande in ligne:
                    with self.subTest(ligne=ligne):
                        self.fail(
                            f"Le Makefile reecrit une commande que les "
                            f"scripts de bin/ portent deja : {ligne}"
                        )

    def test_les_cibles_sont_declarees_phony(self):
        """
        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Une cible absente de `.PHONY` cesse de tourner le jour ou un
        fichier prend son nom — `make backup` ne ferait plus rien si un
        fichier `backup` apparaissait a la racine, sans un mot.
        / A target missing from .PHONY silently stops running the day a
        file takes its name.
        """
        lignes = _contenu("Makefile").splitlines()
        declarations = []
        dans_le_bloc = False
        for ligne in lignes:
            if ligne.startswith(".PHONY:"):
                dans_le_bloc = True
            elif dans_le_bloc and not declarations[-1].rstrip().endswith("\\"):
                break
            if dans_le_bloc:
                declarations.append(ligne)
        bloc = " ".join(declarations)

        for cible in ("backup", "restore", "backup-check", "verif-prod"):
            with self.subTest(cible=cible):
                self.assertIn(
                    f" {cible} ",
                    f"{bloc} ",
                    f"`{cible}` n'est pas declaree dans le bloc .PHONY.",
                )


class LInstallationVerifieLaProductionTest(TestCase):
    """
    LOCALISATION : front/tests/test_sauvegarde_borg.py
    """

    def _variables_du_makefile(self):
        """
        Rend les variables du Makefile, resolues une fois.
        / Returns the Makefile's variables, resolved once.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Sans cela, un test qui cherche `verifier_prod.sh` echouerait sur
        un Makefile qui l'appelle proprement par `$(SCRIPT_DE_...)` —
        c'est-a-dire qu'il PENALISERAIT le style attendu ici, ou chaque
        chemin de script est nomme une seule fois.
        / Otherwise the test would penalise the very style this project
        asks for: each script path named once, in a variable.
        """
        variables = {}
        for ligne in _contenu("Makefile").splitlines():
            if ligne.startswith(("\t", "#", " ")) or ":=" not in ligne:
                continue
            nom, _, valeur = ligne.partition(":=")
            variables[nom.strip()] = valeur.strip()
        return variables

    def _corps_de_la_cible(self, nom):
        """
        Rend les lignes du corps d'une cible, variables resolues.
        / Returns a target's body lines, variables resolved.
        """
        variables = self._variables_du_makefile()
        lignes = _contenu("Makefile").splitlines()
        corps = []
        dans_la_cible = False
        for ligne in lignes:
            if ligne.startswith(f"{nom}:"):
                dans_la_cible = True
                continue
            if dans_la_cible:
                # Le corps d'une cible est indente par une tabulation ;
                # la premiere ligne non indentee et non vide la ferme.
                # / A target's body is tab-indented.
                if ligne.startswith("\t"):
                    resolue = ligne.strip()
                    # Les commentaires de recette (`@#`) CITENT des
                    # commandes sans les lancer.
                    # / Recipe comments name commands without running them.
                    if resolue.startswith("@#") or resolue.startswith("#"):
                        continue
                    for cle, valeur in variables.items():
                        resolue = resolue.replace(f"$({cle})", valeur)
                    corps.append(resolue)
                elif ligne.strip():
                    break
        return corps

    def test_l_installation_appelle_la_verification_de_production(self):
        corps = "\n".join(self._corps_de_la_cible("install"))

        self.assertIn(
            "verifier_prod.sh",
            corps,
            "`make install` ne verifie ni le depot de sauvegarde, ni "
            "le cron, ni les secrets par defaut.",
        )

    def test_la_verification_ne_fait_jamais_echouer_l_installation(self):
        """
        Une prod pas encore sauvegardee doit pouvoir s'installer.
        / A not-yet-backed-up production must still install.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        Sinon on tient l'oeuf et la poule : le depot borg se cree
        depuis la machine installee, et l'installation refuserait de
        finir tant qu'il n'existe pas.
        / Otherwise: the repository is created from the installed
        machine, and the install would refuse to finish without it.
        """
        lignes = [
            ligne
            for ligne in self._corps_de_la_cible("install")
            if "verifier_prod.sh" in ligne
        ]
        self.assertTrue(lignes, "La verification n'est pas appelee.")

        for ligne in lignes:
            with self.subTest(ligne=ligne):
                self.assertTrue(
                    "|| true" in ligne or ligne.startswith("-"),
                    "L'echec de la verification arreterait l'installation "
                    "d'une machine dont le depot n'est pas encore cree.",
                )

    def test_l_installation_attend_le_socket_du_mode_ou_elle_tourne(self):
        """
        Le socket de prod n'est pas celui de dev.
        / The production socket is not the dev one.

        LOCALISATION : front/tests/test_sauvegarde_borg.py

        `supervisord-dev.conf` ouvre `/tmp/supervisor-dev.sock`,
        `supervisord.conf` ouvre `/tmp/supervisor.sock`. Une attente
        codee en dur sur le socket de dev boucle SANS FIN sur une
        machine de production — et rien dans la sortie ne dit pourquoi.
        / A hard-coded wait on the dev socket loops forever on a
        production machine, and nothing in the output says why.
        """
        corps = "\n".join(self._corps_de_la_cible("install"))

        # Le corps est lu VARIABLES RESOLUES : un `$(SOCKET_DEV)` code
        # en dur y apparait donc sous la forme du chemin lui-meme. Le
        # chercher sous son nom de variable ne prouverait rien — mesure
        # du 16 aout 2026 : la violation injectee passait au vert.
        # / The body is read with variables resolved, so a hard-coded
        # $(SOCKET_DEV) shows up as the path. Measured: looking for the
        # variable name caught nothing.
        self.assertNotIn(
            "/tmp/supervisor-dev.sock",
            corps,
            "L'installation attend le socket de DEV en dur : sur une "
            "machine de production, supervisord ouvre "
            "/tmp/supervisor.sock et cette boucle ne finit jamais.",
        )
        self.assertIn(
            "SOCKET_DU_MODE",
            corps,
            "L'installation ne choisit pas son socket selon le mode.",
        )

        # Et ce choix se fait bien sur DEBUG, la seule chose qui decide
        # lequel des deux supervisord tourne.
        # / And that choice reads DEBUG, which decides which supervisord
        # is running.
        definition = [
            ligne
            for ligne in _contenu("Makefile").splitlines()
            if ligne.startswith("SOCKET_DU_MODE")
        ]
        self.assertTrue(definition, "SOCKET_DU_MODE n'est pas defini.")
        self.assertIn("DEBUG", definition[0])
