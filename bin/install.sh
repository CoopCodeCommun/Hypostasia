#!/bin/bash
# =============================================================================
# bin/install.sh — Installation / mise a jour Hypostasia
# / bin/install.sh — Hypostasia install / update
#
# S'EXECUTE DANS LE CONTENEUR, jamais depuis l'hote : il appelle
# `manage.py` directement. C'est ce qui lui permet de tourner au
# demarrage du conteneur, quand aucun hote n'est au bout du fil — au
# boot de la machine, apres un redeploiement, quand la restart policy
# relance le service. Le Makefile, lui, vit sur l'hote et ne fait que
# l'APPELER : la sequence d'installation n'existe qu'ici.
# / Runs INSIDE the container, so it can run at container startup when
# no host is around. The Makefile only calls it; the sequence lives here.
#
# USAGE
#   bash bin/install.sh            tout, dans l'ordre
#   bash bin/install.sh fixtures   les documents et leurs extractions
#   bash bin/install.sh statiques  collectstatic seul
#   bash bin/install.sh llm        l'analyse par le vrai modele
#
# IDEMPOTENT, ET C'EST CE QUI COMPTE
#
# Chaque etape saute ce qui est deja present. Le premier passage
# convertit deux PDF avec Docling (~3 min) ; les suivants prennent 10 s
# (mesure du 15 aout 2026). C'est ce qui permet aux deux scripts de
# demarrage de rappeler ce fichier a CHAQUE lancement du conteneur sans
# rien recouter — ni en temps, ni en appels LLM factures.
#
# Le garde-fou est POSE PAR CHAQUE COMMANDE, pas en tete de script. Un
# garde global « si la base est peuplee, ne rien faire » serait un
# recul : il empecherait de rattraper une installation partielle — une
# analyse LLM qui a echoue faute de cle doit pouvoir repartir au
# demarrage suivant, alors meme que la base est pleine.
# / The guard belongs to each command, not to the script: a global
# "database not empty, skip everything" would prevent recovering from a
# partial install.
#
# `uv run` a ete retire des appels Django : le PATH de l'image contient
# deja /app/.venv/bin (Dockerfile), et le wrapper n'ajoutait qu'un
# process et une reverification du lock a chaque commande.
# / No `uv run`: the venv is already on PATH.
# =============================================================================
set -e

cd "$(dirname "$0")/.."

ETAPE="${1:-tout}"

# ---------------------------------------------------------------------------
# Les etapes, une fonction chacune. Le Makefile les appelle par leur nom
# plutot que de reecrire les commandes : deux definitions d'une meme
# sequence finissent toujours par diverger.
# / One function per step, called by name from the Makefile.
# ---------------------------------------------------------------------------

installer_les_dependances() {
    echo "[1/6] uv sync..."
    uv sync
    echo "[2/6] Repertoires..."
    mkdir -p logs tmp/audio staticfiles
}

appliquer_les_migrations() {
    echo "[3/6] Migrations..."
    python manage.py migrate
}

collecter_les_statiques() {
    echo "[4/6] Collectstatic..."
    python manage.py collectstatic --noinput
}

charger_les_fixtures() {
    # Les documents etalons de sample/ : capture web, fichier ecrit,
    # transcription deja faite, audio brut, deux PDF. Cree aussi la base
    # de connaissances, le carnet et les analyseurs. La transcription de
    # l'audio se saute d'elle-meme sans MISTRAL_API_KEY.
    # / The reference documents, the knowledge base, the notebook.
    echo "[5/6] Documents etalons (premier passage : ~3 min, conversions PDF)..."
    python manage.py charger_fixtures_sample

    # Les extractions et commentaires, ecrits a la main : ils couvrent
    # expres des cas limites qu'un modele ne produit pas a coup sur —
    # marques imbriquees, ancre sur un tableau, cartes a 0/1/2
    # commentaires. Sans eux, les notes arrivent nues.
    # / Hand-written on purpose: they cover edge cases.
    echo "[6/6] Extractions de demonstration..."
    python manage.py charger_extractions_demo
}

analyser_avec_le_vrai_modele() {
    # C'est ce qui fait de l'installation un TEST DES CLES API : deux
    # notes sont analysees par le modele configure, pour de bon. Si la
    # cle manque ou si l'appel echoue, l'installation le dit.
    #
    # `--asynchrone` envoie les analyses dans la file Celery : le
    # demarrage n'attend pas le modele, et l'administrateur suit leur
    # avancement depuis le menu des taches. Les workers demarrent juste
    # apres ; les taches patientent dans Redis.
    #
    # `--si-absent` empeche la facture de se repeter : ce script est
    # rejoue a CHAQUE demarrage du conteneur. Une analyse deja en file
    # compte comme faite. Pour tout rejouer : `make fixtures-llm`.
    # / A real API-key test, queued so startup does not wait, and guarded
    # so a restart does not re-bill.
    echo "Analyse par le vrai LLM, en file Celery (test des cles API)..."
    python manage.py charger_fixtures_llm_reel --si-absent --asynchrone
}

case "$ETAPE" in
    tout)
        echo "=== Hypostasia install ==="
        installer_les_dependances
        appliquer_les_migrations
        collecter_les_statiques
        charger_les_fixtures
        analyser_avec_le_vrai_modele
        echo "=== Installation terminee ==="
        ;;
    fixtures)   charger_les_fixtures ;;
    statiques)  collecter_les_statiques ;;
    llm)        analyser_avec_le_vrai_modele ;;
    *)
        echo "Etape inconnue : $ETAPE" >&2
        echo "Attendu : tout | fixtures | statiques | llm" >&2
        exit 1
        ;;
esac
