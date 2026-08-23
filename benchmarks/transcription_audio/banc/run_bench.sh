#!/usr/bin/env bash
# Execute le banc d'essai et mesure le pic memoire reellement consomme
# / Runs the benchmark and measures actual peak memory
set -euo pipefail
cd /work

DUREE_EXTRAIT="${1:-900}"      # secondes d'audio a transcrire / seconds of audio
DEBUT_EXTRAIT="${2:-0}"        # decalage de depart / start offset
DOSSIER_MODELE="${3:-./tdt}"   # ./tdt (fp32) ou ./tdt-int8
ETIQUETTE="${4:-fp32}"
CHUNK_SECONDES="${5:-240}"
MODELE_SORTFORMER="${6:-diar_streaming_sortformer_4spk-v2.onnx}"
SOURCE_AUDIO="${7:-audio/complet.wav}"   # l'enregistrement d'ou l'extrait est tire
# Le binaire : celui a 4 slots par defaut, ou celui a 8 fabrique par
# preparer_ultra_sortformer.sh. Un modele a 8 sorties passe dans le binaire a 4
# fait PANIQUER le programme (broadcast [T,8] vers [T,4]) : l'incompatibilite
# est bruyante, elle ne se confond pas avec un mauvais resultat.
# / The binary: 4 slots by default, or the 8-slot one. Mismatches panic loudly.
BINAIRE="${8:-./target/release/bench}"

# Le debut ET la source font partie du nom. Sans le debut, un extrait different
# mais de meme duree reutiliserait silencieusement le fichier precedent ; sans la
# source, deux enregistrements differents produiraient le MEME nom de fichier —
# et le second banc mesurerait l'audio du premier sans que rien ne le dise.
# / Offset AND source belong in the name: otherwise two different recordings
# produce the same filename and the second run silently measures the first audio.
NOM_DE_LA_SOURCE="$(basename "$SOURCE_AUDIO" .wav)"
EXTRAIT="audio/extrait_${NOM_DE_LA_SOURCE}_${DEBUT_EXTRAIT}_${DUREE_EXTRAIT}s.wav"

if [ ! -f "$EXTRAIT" ]; then
    echo "--- extraction de ${DUREE_EXTRAIT}s a partir de ${DEBUT_EXTRAIT}s (source : $SOURCE_AUDIO) ---"
    ffmpeg -y -loglevel error -ss "$DEBUT_EXTRAIT" -t "$DUREE_EXTRAIT" \
        -i "$SOURCE_AUDIO" -ac 1 -ar 16000 -sample_fmt s16 "$EXTRAIT"
fi
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$EXTRAIT"

echo "============================================================"
echo "BANC D'ESSAI — variante : $ETIQUETTE"
echo "vCPU visibles dans le conteneur : $(nproc)"
echo "============================================================"

# /usr/bin/time -v donne le pic RSS, ce que `time` du shell ne sait pas faire
# / /usr/bin/time -v gives peak RSS, which the shell builtin cannot
/usr/bin/time -v "$BINAIRE" \
    "$EXTRAIT" "$DOSSIER_MODELE" "$CHUNK_SECONDES" "resultat_${ETIQUETTE}.json" \
    "$MODELE_SORTFORMER" \
    2> "mesures_${ETIQUETTE}.txt" | tee "sortie_${ETIQUETTE}.txt"

echo
echo "--- ressources (extrait de /usr/bin/time -v) ---"
grep -E "Maximum resident|Elapsed .wall|User time|System time|Percent of CPU" "mesures_${ETIQUETTE}.txt" || true
