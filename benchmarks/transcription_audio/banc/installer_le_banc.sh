#!/usr/bin/env bash
# Copie les scripts versionnes du banc vers un dossier de travail hors depot.
# / Copies the versioned benchmark scripts into a work folder outside the repository.
#
# LOCALISATION : benchmarks/transcription_audio/banc/installer_le_banc.sh
#
# POURQUOI CE SCRIPT. Les scripts du banc sont versionnes ; les poids, l'audio et
# les resultats bruts ne le sont pas (3,8 Go). Le conteneur monte UN seul dossier
# de travail : il faut donc y deposer une copie des scripts. Le dossier de travail
# est un ARGUMENT, jamais un chemin en dur : le meme banc doit se rejouer a
# l'identique sur une autre machine.
# / The work folder is an argument, never a hardcoded path: the same benchmark must
# replay identically on another machine.
#
# Usage : bash installer_le_banc.sh /chemin/du/dossier/de/travail
set -euo pipefail

DOSSIER_DES_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOSSIER_DE_TRAVAIL="${1:?Usage: installer_le_banc.sh <dossier_de_travail>}"

mkdir -p "$DOSSIER_DE_TRAVAIL/src" "$DOSSIER_DE_TRAVAIL/audio"

# Les scripts sont recopies a chaque appel : le dossier de travail ne doit jamais
# porter une version plus ancienne que le depot.
# / Scripts are re-copied on every call: the work folder must never hold an older version.
for fichier_a_copier in Dockerfile Dockerfile.voie-b Dockerfile.diarisation \
                        Dockerfile.loudpage Dockerfile.pyannote4 Dockerfile.whisperx \
                        docker-compose.banc.yml Cargo.toml \
                        prepare.sh preparer_la_campagne.sh run_bench.sh \
                        preparer_ultra_sortformer.sh \
                        mesurer_une_pile.py mesurer_un_serveur_whisper.py mesurer_whisperx.py \
                        voxtral_de_reference.py \
                        lancer_la_campagne.sh agreger_la_campagne.py \
                        reference.py inspecter_reference.py comparer.py ; do
    cp "$DOSSIER_DES_SCRIPTS/$fichier_a_copier" "$DOSSIER_DE_TRAVAIL/$fichier_a_copier"
done
cp "$DOSSIER_DES_SCRIPTS/src/main.rs" "$DOSSIER_DE_TRAVAIL/src/main.rs"
chmod +x "$DOSSIER_DE_TRAVAIL/prepare.sh" "$DOSSIER_DE_TRAVAIL/run_bench.sh"

echo "Banc installe dans : $DOSSIER_DE_TRAVAIL"
ls -la "$DOSSIER_DE_TRAVAIL"
