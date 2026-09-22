#!/usr/bin/env bash
# Prepare le banc d'essai : modeles ONNX + audio de test
# / Prepare the benchmark: ONNX models + test audio
set -euo pipefail
cd /work

HF_TDT="https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/resolve/main"
HF_SORT="https://huggingface.co/altunenes/parakeet-rs/resolve/main"
AUDIO_SRC="https://media.april.org/audio/radio-cause-commune/libre-a-vous/emissions/20260707/libre-a-vous-20260707-tactic-asbl.ogg"

mkdir -p tdt tdt-int8 audio

telecharger() {
    # $1 = url, $2 = destination. Reprend sans retelecharger si le fichier est la.
    # / $1 = url, $2 = destination. Skips if the file is already there.
    if [ -f "$2" ]; then
        echo "  deja present : $2 ($(du -h "$2" | cut -f1))"
        return
    fi
    echo "  telechargement : $2"
    # --fail : sans lui, une page d'erreur HTML serait ecrite dans le fichier modele
    # / --fail: without it, an HTML error page would be written into the model file
    curl -sSL --fail --retry 3 -o "$2.part" "$1"
    mv "$2.part" "$2"
    echo "    -> $(du -h "$2" | cut -f1)"
}

echo "=== 1/4 Modele Parakeet TDT v3 (fp32) ==="
telecharger "$HF_TDT/encoder-model.onnx"        tdt/encoder-model.onnx
telecharger "$HF_TDT/encoder-model.onnx.data"   tdt/encoder-model.onnx.data
telecharger "$HF_TDT/decoder_joint-model.onnx"  tdt/decoder_joint-model.onnx
telecharger "$HF_TDT/vocab.txt"                 tdt/vocab.txt

echo "=== 2/4 Modele Parakeet TDT v3 (int8) ==="
# Le loader attend les noms sans suffixe : on renomme a la copie, encodeur ET decodeur
# / The loader expects unsuffixed names: rename on copy, both encoder AND decoder
telecharger "$HF_TDT/encoder-model.int8.onnx"       tdt-int8/encoder-model.onnx
telecharger "$HF_TDT/decoder_joint-model.int8.onnx" tdt-int8/decoder_joint-model.onnx
cp -n tdt/vocab.txt tdt-int8/vocab.txt

echo "=== 3/4 Modele Sortformer v2 (diarisation) ==="
telecharger "$HF_SORT/diar_streaming_sortformer_4spk-v2.onnx" diar_streaming_sortformer_4spk-v2.onnx

echo "=== 4/4 Audio de test (Libre a vous ! #282, licence libre) ==="
telecharger "$AUDIO_SRC" audio/source.ogg

echo "--- duree du fichier source ---"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 audio/source.ogg

echo "--- conversion en WAV 16 kHz mono 16 bits ---"
# Sortformer et Parakeet exigent 16 kHz mono / both models require 16 kHz mono
ffmpeg -y -loglevel error -i audio/source.ogg -ac 1 -ar 16000 -sample_fmt s16 audio/complet.wav
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 audio/complet.wav

echo
echo "=== Inventaire ==="
du -sh tdt tdt-int8 diar_streaming_sortformer_4spk-v2.onnx audio/* 2>/dev/null

echo
echo "Etape suivante : python3 reference.py  (transcription humaine de reference)"
