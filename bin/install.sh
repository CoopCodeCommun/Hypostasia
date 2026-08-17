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
    # C'est ce qui fait de l'installation un TEST DES CLES API : les
    # notes etalons sont analysees par le modele configure, pour de bon.
    # Si la cle manque ou si l'appel echoue, l'installation le dit.
    #
    # La commande n'analyse QUE ce qui ne l'est pas encore, et saute les
    # notes trop grosses (la Presentation V3 porte 549 elements a elle
    # seule, 73 % du corpus). Elle est donc sans effet aux demarrages
    # suivants : ce script est rejoue a CHAQUE lancement du conteneur, et
    # rien n'est refacture.
    #
    # Les analyses partent dans la file Celery : le demarrage n'attend
    # pas le modele, et l'administrateur suit leur avancement depuis le
    # menu des taches. Les workers demarrent juste apres ce script ; les
    # taches patientent dans Redis en attendant.
    # / A real API-key test, queued so startup does not wait, and
    # naturally idempotent so a restart does not re-bill.
    echo "Analyse des notes etalons par le vrai modele (test des cles API)..."
    python manage.py analyser_les_notes_etalons

    # Le wiki et la synthese dirigee du carnet etalon. Meme discipline
    # que l'analyse ci-dessus : appels FACTURES, mais la commande ne
    # produit que ce qui manque, donc un redemarrage ne refacture rien.
    #
    # Sans elle, une installation neuve montre deux onglets VIDES et
    # toute la couche synthese — sourcage [N], panneau de preuve,
    # ecartees, couverture, verification — reste invisible.
    #
    # Elle passe APRES l'analyse : un article ne peut citer que des
    # extractions qui existent. Au premier demarrage, les analyses sont
    # encore dans la file Celery, donc le carnet peut n'avoir que les
    # extractions de charger_extractions_demo — c'est suffisant, et le
    # demarrage suivant complete ce qui manque.
    # / Billed but idempotent; runs after analysis since an article can
    # only cite extractions that already exist.
    echo "Production du wiki et de la synthese etalons..."
    python manage.py produire_les_syntheses_etalons

    # LA VERIFICATION DES CITATIONS.
    #
    # Elle reste un GESTE EXPLICITE — jamais automatique a la production
    # (SPEC-synthese § 7, question n°3). L'installation la declenche donc
    # comme un utilisateur le ferait par le bouton « Verifier les
    # citations », avec le meme endpoint, la meme tache et le meme juge.
    #
    # Sans elle, une installation neuve montre des articles dont TOUS les
    # renvois sont « non verifie » : l'etage qui fait toute la valeur du
    # produit reste invisible, et le chiffre qui rend la demonstration
    # convaincante (~88 % de citations verifiees sur les donnees etalons)
    # n'apparait nulle part.
    #
    # Elle ne juge que les paires SANS verdict, donc un redemarrage ne
    # refacture rien. Et comme les articles partent dans la file Celery,
    # le premier demarrage n'a encore rien a verifier : c'est le
    # demarrage suivant qui les juge, sans qu'on ait rien a ordonner.
    # / Verification stays an explicit act; the install triggers it like
    # the button does. Only verdict-less pairs are judged.
    echo "Verification des citations des articles etalons..."
    python manage.py verifier_les_citations_etalons
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
