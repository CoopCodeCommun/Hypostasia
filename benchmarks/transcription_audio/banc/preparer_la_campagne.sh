#!/usr/bin/env bash
# Telecharge TOUT ce que la campagne exige, et rien de plus.
# / Downloads EVERYTHING the campaign needs, and nothing more.
#
# LOCALISATION : benchmarks/transcription_audio/banc/preparer_la_campagne.sh
# S'EXECUTE DANS LE CONTENEUR DU BANC (celui de l'annexe A), depuis /work.
#
# POURQUOI CE SCRIPT EXISTE A COTE DE `prepare.sh`. L'annexe C ne connait que la
# voie A : les poids Parakeet, le Sortformer a 4 locuteurs et un seul
# enregistrement. La campagne, elle, compare NEUF piles sur TROIS tranches — il
# lui faut en plus le preprocesseur mel, Ultra-Sortformer, les modeles
# sherpa-onnx, deux enregistrements de plus et leurs transcriptions humaines.
# Sans ce script, la preparation est une dizaine de gestes manuels, et un geste
# oublie ne se voit qu'au milieu de la campagne.
# / prepare.sh only knows path A; the campaign needs eight more things.
#
# TOUT EST IDEMPOTENT : ce qui est deja la n'est pas retelecharge.
# / Everything is idempotent.
#
# Volume : environ 5 Go de poids et d'audio. Compter 10 a 30 min selon la ligne.
#
# Usage : bash preparer_la_campagne.sh
set -euo pipefail
cd /work

HF_TDT="https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/resolve/main"
HF_ULTRA="https://huggingface.co/investguy/ultra_diar_streaming_sortformer_8spk_v1_onnx/resolve/main"
SHERPA="https://github.com/k2-fsa/sherpa-onnx/releases/download"
MEDIA_APRIL="https://media.april.org/audio/radio-cause-commune/libre-a-vous/emissions"
LIBREALIRE="https://www.librealire.org"

telecharger() {
    # $1 = url, $2 = destination. Ne retelecharge jamais ce qui est deja la.
    # / $1 = url, $2 = destination. Never re-downloads what is already there.
    if [ -f "$2" ]; then
        echo "  deja present : $2 ($(du -h "$2" | cut -f1))"
        return
    fi
    echo "  telechargement : $2"
    # --fail : sans lui, une page d'erreur HTML serait ecrite dans le fichier
    # modele, et l'echec surgirait bien plus tard sous une forme incomprehensible.
    # / --fail: otherwise an HTML error page lands inside the model file.
    curl -sSL --fail --retry 3 -o "$2.part" "$1"
    mv "$2.part" "$2"
    echo "    -> $(du -h "$2" | cut -f1)"
}

convertir_en_wav() {
    # $1 = source, $2 = destination. Sortformer et Parakeet exigent 16 kHz mono.
    # / Both models require 16 kHz mono.
    [ -f "$2" ] && { echo "  deja converti : $2"; return; }
    echo "  conversion : $2"
    ffmpeg -y -loglevel error -i "$1" -ac 1 -ar 16000 -sample_fmt s16 "$2"
}

echo "=== 1/7 Parakeet TDT v3 (int8 et fp32) ==="
bash prepare.sh > /dev/null
echo "  fait (voir prepare.sh pour le detail)"

echo "=== 2/7 Le dossier que onnx-asr sait lire ==="
# onnx-asr attend les noms d'ORIGINE du depot, et deux fichiers que prepare.sh
# ne telecharge pas : `config.json` et `nemo128.onnx`, le preprocesseur mel a
# 128 bandes. Sans lui : « Got: 80 Expected: 128 », et rien ne dit lequel
# manque. Les liens durs evitent de dupliquer 3 Go sur le disque.
# / onnx-asr needs the ORIGINAL names plus two files prepare.sh never fetches.
mkdir -p hf-parakeet
ln -f tdt-int8/encoder-model.onnx        hf-parakeet/encoder-model.int8.onnx       2>/dev/null || true
ln -f tdt-int8/decoder_joint-model.onnx  hf-parakeet/decoder_joint-model.int8.onnx 2>/dev/null || true
ln -f tdt/encoder-model.onnx             hf-parakeet/encoder-model.onnx            2>/dev/null || true
ln -f tdt/encoder-model.onnx.data        hf-parakeet/encoder-model.onnx.data       2>/dev/null || true
ln -f tdt/decoder_joint-model.onnx       hf-parakeet/decoder_joint-model.onnx      2>/dev/null || true
ln -f tdt/vocab.txt                      hf-parakeet/vocab.txt                     2>/dev/null || true
telecharger "$HF_TDT/config.json"   hf-parakeet/config.json
telecharger "$HF_TDT/nemo128.onnx"  hf-parakeet/nemo128.onnx

echo "=== 3/7 Ultra-Sortformer, 8 locuteurs ==="
telecharger "$HF_ULTRA/ultra_diar_streaming_sortformer_8spk_v1.onnx" ultra_sortformer_8spk.onnx

echo "=== 4/7 Les modeles de diarisation de sherpa-onnx (aucun jeton) ==="
mkdir -p modeles_sherpa
if [ ! -d modeles_sherpa/sherpa-onnx-pyannote-segmentation-3-0 ]; then
    telecharger "$SHERPA/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2" \
        modeles_sherpa/segmentation.tar.bz2
    # `tar xjf` exige bzip2, absent de l'image : Python le fait sans dependance.
    # / `tar xjf` needs bzip2, absent from the image; Python does it dependency-free.
    python3 - <<'FIN_PYTHON'
import bz2, io, tarfile
with bz2.open("modeles_sherpa/segmentation.tar.bz2") as archive:
    tarfile.open(fileobj=io.BytesIO(archive.read())).extractall("modeles_sherpa")
FIN_PYTHON
    rm -f modeles_sherpa/segmentation.tar.bz2
fi
# Le tag de la release porte une faute de frappe en amont (« recongition ») :
# la corriger ici donnerait un 404. / The upstream tag is misspelled; keep it.
telecharger "$SHERPA/speaker-recongition-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx" \
    modeles_sherpa/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx

echo "=== 5/7 Les deux enregistrements supplementaires ==="
# Le sujet Tactic (deja pris par prepare.sh) ne porte que quatre voix. Il faut
# le plateau du 16 juin pour un second point a quatre voix, et l'emission
# ENTIERE du meme jour pour la tranche a SIX voix — celle qui teste le plafond.
# / Tactic has four voices; the whole 16 June show is what carries six.
telecharger "$MEDIA_APRIL/20260616/libre-a-vous-20260616-au-cafe-libre.ogg" audio/cafe_libre_source.ogg
telecharger "$MEDIA_APRIL/20260616/libre-a-vous-20260616.ogg"              audio/emission_complete_source.ogg
convertir_en_wav audio/cafe_libre_source.ogg        audio/cafe_libre_complet.wav
convertir_en_wav audio/emission_complete_source.ogg audio/emission_complete.wav

echo "=== 6/7 Les transcriptions humaines de reference ==="
# Elles sont figees en copie locale : une page qui change en amont ferait
# glisser tous les WER sans que rien ne le signale.
# / Frozen locally: an upstream edit would silently shift every WER.
if [ ! -f reference.json ]; then
    python3 reference.py \
        "$LIBREALIRE/emission-libre-a-vous-diffusee-mardi-7-juillet-2026-sur-radio-cause-commune" \
        reference
fi
if [ ! -f reference_cafe_libre.json ]; then
    python3 reference.py \
        "$LIBREALIRE/emission-libre-a-vous-diffusee-mardi-16-juin-2026-sur-radio-cause-commune" \
        reference_cafe_libre
fi

echo "=== 7/7 Inventaire ==="
du -sh tdt tdt-int8 hf-parakeet modeles_sherpa ultra_sortformer_8spk.onnx \
       diar_streaming_sortformer_4spk-v2.onnx audio 2>/dev/null
echo
echo "Attendu : reference.json = 131 tours, reference_cafe_libre.json = 200 tours."
echo "Un compte different signale que la page a change en amont."
python3 - <<'FIN_PYTHON'
import json
for nom in ("reference.json", "reference_cafe_libre.json"):
    try:
        with open(nom, encoding="utf-8") as fichier:
            print(f"  {nom} : {len(json.load(fichier))} tours")
    except FileNotFoundError:
        print(f"  {nom} : ABSENT")
FIN_PYTHON
echo
echo "Etape suivante, dans le conteneur du banc :"
echo "  cargo build --release && bash preparer_ultra_sortformer.sh"
echo "Puis, sur l'hote :"
echo "  bash lancer_la_campagne.sh \"etat de la stack\""
