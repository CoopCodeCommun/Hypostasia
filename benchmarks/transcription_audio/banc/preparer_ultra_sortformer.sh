#!/usr/bin/env bash
# Fabrique un SECOND binaire du banc, capable de huit locuteurs.
# / Builds a SECOND benchmark binary, able to handle eight speakers.
#
# LOCALISATION : benchmarks/transcription_audio/banc/preparer_ultra_sortformer.sh
# S'EXECUTE DANS LE CONTENEUR DU BANC (celui de l'annexe A), depuis /work.
#
# POURQUOI CE SCRIPT EXISTE. `parakeet-rs` 0.3.7 refuse Ultra-Sortformer 8
# locuteurs, et le message le dit exactement :
#
#     ndarray: could not broadcast array from shape: [680, 8] to: [680, 4]
#
# Le plafond n'est PAS dans le format du modele — les deux ONNX ont la meme
# interface, seule la derniere dimension de sortie change (4 contre 8). Il est
# dans UNE CONSTANTE de la crate : `pub const NUM_SPEAKERS: usize = 4;`,
# utilisee 25 fois, sans aucun `4` en dur a cote. La config de streaming
# (chunk_len, fifo_len, spkcache_len), elle, est lue dans les metadonnees du
# modele : elle s'adapte deja toute seule.
# / The ceiling is not in the model format but in ONE crate constant.
#
# On recopie donc la crate, on change la constante, et on construit un second
# binaire. C'est un patch d'une ligne sur du code dont la logique est deja
# eprouvee — l'alternative (reecrire la boucle de streaming Sortformer en
# Python) ferait courir le risque d'une erreur silencieuse, c'est-a-dire
# exactement ce que ce banc existe pour detecter.
#
# Usage : bash preparer_ultra_sortformer.sh
set -euo pipefail
cd /work

CRATE_D_ORIGINE="$(find /usr/local/cargo/registry/src -maxdepth 2 -type d -name 'parakeet-rs-0.3.7' | head -1)"
if [ -z "$CRATE_D_ORIGINE" ]; then
    echo "Crate parakeet-rs-0.3.7 introuvable : lancer d'abord 'cargo build --release'." >&2
    exit 1
fi

echo "--- copie de la crate depuis $CRATE_D_ORIGINE ---"
rm -rf vendor/parakeet-rs-8spk banc-8spk
mkdir -p vendor
cp -r "$CRATE_D_ORIGINE" vendor/parakeet-rs-8spk
chmod -R u+w vendor/parakeet-rs-8spk

# Le checksum du registre rendrait la copie invalide des qu'on y touche.
# / The registry checksum would invalidate the copy as soon as we edit it.
rm -f vendor/parakeet-rs-8spk/.cargo-checksum.json

echo "--- LE patch : une constante ---"
sed -i 's/^pub const NUM_SPEAKERS: usize = 4;/pub const NUM_SPEAKERS: usize = 8;/' \
    vendor/parakeet-rs-8spk/src/sortformer.rs

# Verification explicite : un sed muet qui n'a rien remplace produirait un
# binaire identique au premier, et un resultat faussement rassurant.
# / Explicit check: a silent no-op sed would yield a binary identical to the first.
if ! grep -q '^pub const NUM_SPEAKERS: usize = 8;' vendor/parakeet-rs-8spk/src/sortformer.rs; then
    echo "ECHEC : la constante NUM_SPEAKERS n'a pas ete remplacee." >&2
    exit 1
fi
echo "    NUM_SPEAKERS = 8 confirme"

echo "--- second projet, meme main.rs ---"
mkdir -p banc-8spk/src
cp src/main.rs banc-8spk/src/main.rs
cat > banc-8spk/Cargo.toml <<'FIN_DU_CARGO'
[package]
name = "bench"
version = "0.1.0"
edition = "2021"

[dependencies]
# La copie patchee, et non la version du registre / the patched copy
parakeet-rs = { path = "../vendor/parakeet-rs-8spk", features = ["sortformer"] }
hound = "3.5"

[profile.release]
opt-level = 3
FIN_DU_CARGO

echo "--- compilation ---"
cd banc-8spk && cargo build --release
echo
echo "Binaire a huit locuteurs : /work/banc-8spk/target/release/bench"
echo "Usage : run_bench_8spk.sh, ou directement avec le modele Ultra-Sortformer."
