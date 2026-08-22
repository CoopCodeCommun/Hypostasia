#!/bin/bash
# =============================================================================
# bin/paqueter_l_extension.sh — Fabrique le paquet de l'extension navigateur
# / Builds the browser extension package
#
# S'EXECUTE DEPUIS L'HOTE.   Lance par :  make extension-zip
#
# Il produit  dist/hypostasia-extension-<version>.zip,  pret a etre
# televerse sur addons.mozilla.org.
#
# LE MANIFEST DOIT ETRE A LA RACINE DE L'ARCHIVE, pas dans un dossier
# `extension/`. Un zip fabrique depuis la racine du depot avec
# `zip -r dist/x.zip extension/` produit une archive que Firefox refuse,
# avec un message qui parle de manifest introuvable et ne dit pas
# pourquoi. On entre donc dans `extension/` avant de zipper.
# / The manifest must sit at the archive root, not inside an `extension/`
# folder: Firefox rejects the archive with an unhelpful message.
#
# LA VERSION VIENT DU MANIFEST, JAMAIS DU FICHIER `VERSION` DE LA RACINE.
# Celui-ci porte `alpha:0.3.1` — une chaine que les stores refusent, ils
# n'acceptent que des nombres separes par des points. La version de
# l'extension avance a son propre rythme, independamment du serveur.
# / The version comes from the manifest, never from the root VERSION
# file, which holds a string the stores reject.
# =============================================================================

set -euo pipefail

RACINE_DU_DEPOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOSSIER_SOURCE="$RACINE_DU_DEPOT/extension"
DOSSIER_SORTIE="$RACINE_DU_DEPOT/dist"

if [ ! -f "$DOSSIER_SOURCE/manifest.json" ]; then
    echo "Pas de manifest dans $DOSSIER_SOURCE — rien a paqueter." >&2
    exit 1
fi

# La lecture par python valide le JSON au passage : un manifest casse
# arrete le script ici, pas apres la fabrication d'une archive inutile.
# / Reading through python validates the JSON along the way.
VERSION_DE_L_EXTENSION="$(python3 -c "
import json
print(json.load(open('$DOSSIER_SOURCE/manifest.json'))['version'])
")"

ARCHIVE="$DOSSIER_SORTIE/hypostasia-extension-$VERSION_DE_L_EXTENSION.zip"

mkdir -p "$DOSSIER_SORTIE"

# On repart d'une archive vide. `zip` AJOUTE a une archive existante au
# lieu de la remplacer : sans cette suppression, un fichier retire du
# dossier survivrait indefiniment dans le paquet livre.
# / zip appends to an existing archive instead of replacing it.
rm -f "$ARCHIVE"

# `screen/` EST EXCLU, ET IL DOIT LE RESTER. Il porte les captures de la
# fiche du store : 1,7 Mo, soit dix fois le poids de l'extension entiere.
# Livrees, elles ne serviraient a personne — le navigateur ne les ouvre
# jamais — et elles feraient d'un paquet de 68 Ko un paquet de 1,9 Mo.
# Elles vivent dans le depot parce que c'est la qu'on les retrouve au
# moment de remplir la fiche, pas parce qu'elles s'installent.
# / screen/ holds the store listing captures: 1.7 MB that the browser
# never opens. They live in the repo to be found at listing time.
cd "$DOSSIER_SOURCE"
zip --recurse-paths --filesync --quiet "$ARCHIVE" . \
    --exclude '.*' '*/.*' '*~' 'screen/*' 'screen'

echo "Paquet : $ARCHIVE"
echo "Taille : $(du -h "$ARCHIVE" | cut -f1)"
echo
echo "Contenu :"
unzip -l "$ARCHIVE" | sed 's/^/  /'
