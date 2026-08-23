#!/usr/bin/env bash
# La campagne entiere : toutes les piles, sur toutes les tranches, en SERIE.
# / The whole campaign: every stack, on every slice, run SERIALLY.
#
# LOCALISATION : benchmarks/transcription_audio/banc/lancer_la_campagne.sh
# S'EXECUTE SUR L'HOTE (il pilote les conteneurs par `docker exec`).
#
# EN SERIE, ET JAMAIS EN PARALLELE. Deux inferences simultanees se disputent les
# memes vCPU : les RTFx mesures seraient faux, et faux d'une quantite qui depend
# de l'ordre d'ordonnancement — donc irreproductible d'une machine a l'autre.
# / Serial, never parallel: concurrent inferences make RTFx meaningless.
#
# CE QUI EST MESURE, ET DANS QUEL CONTENEUR :
#
# | pile | conteneur | ce que ca teste |
# |---|---|---|
# | voie A, Sortformer v2 | banc Rust | le diariseur a plafond DUR de 4 |
# | voie A, Ultra-Sortformer 8spk | banc Rust (binaire patche) | le meme, sans le plafond |
# | pilote, `diarize` | image ONNX | clustering spectral, sans jeton |
# | pilote, `sherpa` | image ONNX | segmentation pyannote en ONNX, sans jeton |
# | pilote, `pyannote` 3.1 | image PyTorch figee | l'ancien pipeline, marque legacy en amont |
# | pilote, `community-1` | image PyTorch a jour | le pipeline COURANT, jeton + conditions |
# | WhisperX | image dediee | un AUTRE ASR (Whisper) + alignement wav2vec2 |
# | `achetronic/parakeet` | serveur Go | l'ASR seul, sans diarisation |
# | Voxtral | conteneur `web` | la base de comparaison, FACTUREE |
#
# Usage :
#   bash lancer_la_campagne.sh "etat de la stack pendant la mesure" [tranches...]
#
# Une tranche s'ecrit  source.wav:debut:duree:etiquette  — par exemple :
#   audio/complet.wav:0:900:T1
set -uo pipefail

ETAT_DE_LA_STACK="${1:?Usage: lancer_la_campagne.sh \"etat de la stack\" [tranches...]}"
shift || true

# Les tranches par defaut sont celles de la note du 22 aout : deux plateaux a
# quatre voix (l'un desequilibre, l'autre non) et une tranche a SIX voix, qui
# est le test du plafond.
# / Default slices: two four-voice panels and one six-voice slice.
if [ "$#" -gt 0 ]; then
    TRANCHES=("$@")
else
    TRANCHES=(
        "audio/complet.wav:0:900:T1"
        "audio/cafe_libre_complet.wav:600:900:T2"
        "audio/emission_complete.wav:4100:900:T4"
    )
fi

DOSSIER_DE_TRAVAIL="${DOSSIER_DE_TRAVAIL:-/home/ubuntu/banc-transcription-travail}"
CONTENEUR_RUST="${CONTENEUR_RUST:-bench-asr2}"
CONTENEUR_ONNX="${CONTENEUR_ONNX:-bench-python}"
CONTENEUR_PYTORCH="${CONTENEUR_PYTORCH:-bench-diar}"
CONTENEUR_PYANNOTE4="${CONTENEUR_PYANNOTE4:-bench-pya4}"
CONTENEUR_WHISPERX="${CONTENEUR_WHISPERX:-bench-whisperx}"
CONTENEUR_WEB="${CONTENEUR_WEB:-hypostasia_web}"
URL_ACHETRONIC="${URL_ACHETRONIC:-http://172.17.0.1:5092}"
CHARGE_MAXIMALE="${CHARGE_MAXIMALE:-2.0}"   # charge moyenne toleree avant de mesurer

attendre_une_machine_calme() {
    # UNE MESURE PRISE SUR UNE MACHINE OCCUPEE EST FAUSSE, ET FAUSSE EN SILENCE.
    # Constate le 23 aout 2026 : une diarisation mesuree pendant un `docker
    # build` a rendu 343 s la ou elle en prend 123 — presque le triple, sans
    # qu'aucune erreur ne le signale. On attend donc que la machine se calme,
    # et on ECRIT la charge relevee a cote de chaque mesure.
    # / A measurement taken on a busy machine is wrong, and wrong silently.
    local attentes=0
    while :; do
        local charge; charge="$(cut -d' ' -f1 /proc/loadavg)"
        if awk "BEGIN{exit !($charge <= $CHARGE_MAXIMALE)}"; then
            echo "    charge $charge — machine calme, on mesure"
            return 0
        fi
        if [ "$attentes" -ge 60 ]; then
            echo "    ATTENTION : charge $charge encore au-dessus de $CHARGE_MAXIMALE" \
                 "apres 30 min d'attente. On mesure quand meme, et ce chiffre est SUSPECT."
            return 1
        fi
        [ "$attentes" -eq 0 ] && echo "    charge $charge > $CHARGE_MAXIMALE — on attend que la machine se calme"
        attentes=$((attentes + 1))
        sleep 30
    done
}

echo "############################################################"
echo "# CAMPAGNE — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# etat de la stack : $ETAT_DE_LA_STACK"
echo "# tranches : ${TRANCHES[*]}"
echo "############################################################"

for tranche in "${TRANCHES[@]}"; do
    IFS=':' read -r SOURCE DEBUT DUREE NOM <<< "$tranche"
    NOM_DE_LA_SOURCE="$(basename "$SOURCE" .wav)"
    EXTRAIT="audio/extrait_${NOM_DE_LA_SOURCE}_${DEBUT}_${DUREE}s.wav"

    echo
    echo "════════════════════════════════════════════════════════════"
    echo "TRANCHE $NOM — $SOURCE de ${DEBUT}s a $((DEBUT + DUREE))s"
    echo "════════════════════════════════════════════════════════════"

    # --- 1. voie A, Sortformer v2 (plafond dur a 4) ---
    echo "--- [$NOM] voie A / Sortformer v2 ---"
    attendre_une_machine_calme
    docker exec "$CONTENEUR_RUST" bash -c \
        "cd /work && bash run_bench.sh $DUREE $DEBUT ./tdt-int8 ${NOM}-voieA-sortformer 20 \
         diar_streaming_sortformer_4spk-v2.onnx $SOURCE" 2>&1 | tail -12

    # --- 2. voie A, Ultra-Sortformer 8 locuteurs (binaire patche) ---
    echo "--- [$NOM] voie A / Ultra-Sortformer 8spk ---"
    attendre_une_machine_calme
    docker exec "$CONTENEUR_RUST" bash -c \
        "cd /work && bash run_bench.sh $DUREE $DEBUT ./tdt-int8 ${NOM}-voieA-ultra8 20 \
         ultra_sortformer_8spk.onnx $SOURCE ./banc-8spk/target/release/bench" 2>&1 | tail -12

    # --- 3, 4. pilote ONNX : diarize puis sherpa ---
    for diariseur in diarize sherpa; do
        echo "--- [$NOM] pilote / $diariseur ---"
        attendre_une_machine_calme
        docker exec "$CONTENEUR_ONNX" bash -c \
            "cd /work && /usr/bin/time -v python mesurer_une_pile.py --audio $EXTRAIT \
             --modeles ./hf-parakeet --diariseur $diariseur --max-locuteurs 8 \
             --etiquette ${NOM}-pilote-${diariseur} --etat-de-la-stack '$ETAT_DE_LA_STACK' \
             2> mesures_${NOM}-pilote-${diariseur}.txt | tail -10 ; \
             grep -E 'Maximum resident' mesures_${NOM}-pilote-${diariseur}.txt"
    done

    # --- 5. pilote PyTorch : pyannote 3.1 (le plus lent, ~1x le temps reel) ---
    echo "--- [$NOM] pilote / pyannote 3.1 (legacy) ---"
    attendre_une_machine_calme
    docker exec "$CONTENEUR_PYTORCH" bash -c \
        "cd /work && /usr/bin/time -v python mesurer_une_pile.py --audio $EXTRAIT \
         --modeles ./hf-parakeet --diariseur pyannote --max-locuteurs 8 \
         --etiquette ${NOM}-pilote-pyannote --etat-de-la-stack '$ETAT_DE_LA_STACK' \
         2> mesures_${NOM}-pilote-pyannote.txt | tail -10 ; \
         grep -E 'Maximum resident' mesures_${NOM}-pilote-pyannote.txt" 2>&1 | grep -viE 'warn|deprecat'

    # --- 5 bis. pyannote community-1, le pipeline COURANT (pyannote.audio 4.x) ---
    echo "--- [$NOM] pilote / pyannote community-1 (courant) ---"
    attendre_une_machine_calme
    docker exec "$CONTENEUR_PYANNOTE4" bash -c \
        "cd /work && /usr/bin/time -v python mesurer_une_pile.py --audio $EXTRAIT \
         --modeles ./hf-parakeet --diariseur pyannote-community --max-locuteurs 8 \
         --etiquette ${NOM}-pilote-community --etat-de-la-stack '$ETAT_DE_LA_STACK' \
         2> mesures_${NOM}-pilote-community.txt | tail -10 ; \
         grep -E 'Maximum resident' mesures_${NOM}-pilote-community.txt" 2>&1 | grep -viE 'warn|deprecat'

    # --- 5 ter. WhisperX : un AUTRE ASR (Whisper), alignement wav2vec2, pyannote ---
    echo "--- [$NOM] WhisperX (Whisper + wav2vec2 + community-1) ---"
    attendre_une_machine_calme
    docker exec "$CONTENEUR_WHISPERX" bash -c \
        "cd /work && /usr/bin/time -v python mesurer_whisperx.py --audio $EXTRAIT \
         --modele ${MODELE_WHISPER:-large-v3} --quantification int8 --langue fr \
         --max-locuteurs 8 --etiquette ${NOM}-whisperx --etat-de-la-stack '$ETAT_DE_LA_STACK' \
         2> mesures_${NOM}-whisperx.txt | tail -14 ; \
         grep -E 'Maximum resident' mesures_${NOM}-whisperx.txt" 2>&1 | grep -viE 'warn|deprecat'

    # --- 6. le serveur Go, sans diarisation ---
    echo "--- [$NOM] achetronic/parakeet (serveur Go) ---"
    attendre_une_machine_calme
    docker exec "$CONTENEUR_ONNX" bash -c \
        "cd /work && python mesurer_un_serveur_whisper.py --url $URL_ACHETRONIC \
         --audio $EXTRAIT --etiquette ${NOM}-achetronic \
         --nom-de-la-pile 'achetronic/parakeet (Go, ONNX)' \
         --etat-de-la-stack '$ETAT_DE_LA_STACK'" 2>&1 | tail -8

    # --- 7. Voxtral : FACTURE, et le script refuse de rappeler l'API ---
    # OPTIONNEL : Voxtral passe par le conteneur `web` du projet, qui n'existe
    # pas sur une machine ou seul le banc est installe. On saute proprement
    # plutot que d'echouer — la base de comparaison manquera, et le tableau le
    # dira, mais les huit autres piles auront ete mesurees.
    # / Optional: Voxtral needs the project's `web` container, absent on a
    # benchmark-only machine. We skip cleanly rather than fail.
    if ! docker inspect "$CONTENEUR_WEB" >/dev/null 2>&1; then
        echo "--- [$NOM] Voxtral : IGNORE (conteneur $CONTENEUR_WEB absent) ---"
        continue
    fi
    echo "--- [$NOM] Voxtral (API Mistral, facture) ---"
    docker cp "$DOSSIER_DE_TRAVAIL/voxtral_de_reference.py" "$CONTENEUR_WEB:/tmp/" >/dev/null
    docker cp "$DOSSIER_DE_TRAVAIL/$EXTRAIT" "$CONTENEUR_WEB:/tmp/$(basename "$EXTRAIT")" >/dev/null
    docker exec -w /app "$CONTENEUR_WEB" bash -c \
        "PYTHONPATH=/app python /tmp/voxtral_de_reference.py /tmp/$(basename "$EXTRAIT") \
         /tmp/resultat_${NOM}-voxtral.json" 2>&1 | grep -vE 'DEBUG|INFO' | tail -8
    docker cp "$CONTENEUR_WEB:/tmp/resultat_${NOM}-voxtral.json" \
        "$DOSSIER_DE_TRAVAIL/resultat_${NOM}-voxtral.json" >/dev/null 2>&1 || true
done

echo
echo "############################################################"
echo "# CAMPAGNE TERMINEE — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# Agreger avec : python3 agreger_la_campagne.py"
echo "############################################################"
