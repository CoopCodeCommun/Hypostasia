# Banc d'essai — transcription et diarisation audio en local

Ce dossier porte les **mesures** ; `banc/` porte le **code** qui les produit, et
il est fait pour se rejouer à l'identique sur une autre machine.

| Ce que tu cherches | Où |
|---|---|
| l'état cible, le protocole, les annexes intégrales | `PLAN/specs/SPEC-transcription-audio-locale.md` |
| le code du banc | `banc/` |
| les mesures datées | les fichiers `AAAA-MM-JJ_*.md` de ce dossier |

## Les sept piles que le banc mesure

Ce qui sépare les candidats, c'est la **diarisation** — pas la transcription.
Le pilote `mesurer_une_pile.py` garde donc le même ASR, le même alignement mot à
mot et le même regroupement pour tous, et ne fait varier que le diariseur : sans
cela, on comparerait des chaînes entières sans jamais savoir d'où vient l'écart.

| pile | diariseur | plafond de locuteurs | jeton HuggingFace |
|---|---|---|---|
| voie A — `parakeet-rs` (Rust) | Sortformer v2 | **4, en dur** | non |
| voie A — binaire **patché** | Ultra-Sortformer 8spk | 8 | non |
| pilote — `onnx-asr` | `diarize` (WeSpeaker + spectral) | aucun | non |
| pilote — `onnx-asr` | `sherpa-onnx` (segmentation pyannote en ONNX) | aucun | **non** |
| pilote — `onnx-asr` | `pyannote` 3.1 (PyTorch) | aucun | **oui** |
| `achetronic/parakeet` | *aucun* | — | non |
| `loudpage/parakeet-v3-diarized` | pyannote (NeMo) | aucun | **oui** |
| Voxtral (API Mistral) | intégrée | — | — (clé Mistral) |

`sherpa` et `pyannote` exécutent **le même modèle de segmentation** : le premier
en ONNX sans rien demander, le second via PyTorch avec un jeton et l'acceptation
de conditions sur un site tiers. Les deux sont là pour que le critère 4 de la
spec — « installable sans friction » — soit mesuré, pas supposé.

## Rejouer la campagne entière, sur n'importe quelle machine

Les scripts sont versionnés ; les poids (~4,5 Go), l'audio et les résultats
bruts ne le sont pas. **Le dossier de travail est un argument, jamais un chemin
en dur** : c'est ce qui permet de comparer deux machines.

```bash
# 1. deposer les scripts dans un dossier de travail hors depot
bash banc/installer_le_banc.sh ~/banc-transcription-travail
export DOSSIER_DE_TRAVAIL=~/banc-transcription-travail

# 2. monter les quatre conteneurs du banc (compose separe de celui du projet)
docker compose -f banc/docker-compose.banc.yml up -d

# 3. poids, audio, conversion 16 kHz mono, puis la transcription humaine
docker exec bench-asr2 bash -c 'cd /work && bash prepare.sh && python3 reference.py'

# 4. le binaire a huit locuteurs (une constante de la crate, voir le script)
docker exec bench-asr2 bash -c 'cd /work && cargo build --release'
docker exec bench-asr2 bash -c 'cd /work && bash preparer_ultra_sortformer.sh'

# 5. la campagne : toutes les piles, toutes les tranches, EN SERIE
bash banc/lancer_la_campagne.sh "decrire ce que faisait la machine"

# 6. le tableau comparatif, une ligne par (pile, tranche, machine)
docker exec bench-python bash -c 'cd /work && python agreger_la_campagne.py'
```

Compter environ **deux heures** de calcul pour trois tranches de 900 s, dont la
moitié pour `pyannote` seul.

## Les frictions d'installation, mesurées

Elles ne sont pas des anecdotes : le critère 4 les compte.

| pile | ce qu'il a fallu |
|---|---|
| voie A (Rust) | Debian **13** obligatoire — ONNX Runtime réclame glibc ≥ 2.38 |
| voie A à 8 locuteurs | **recopier la crate et changer une constante** (`NUM_SPEAKERS`) |
| `onnx-asr` | ajouter `config.json` et `nemo128.onnx`, que `prepare.sh` ne télécharge pas |
| `sherpa-onnx` | rien — `pip install`, deux modèles, aucun jeton |
| `pyannote` | **quatre** blocages successifs : `torchaudio ≥ 2.9` a retiré `AudioMetaData` ; la 4.x redirige vers un dépôt **restreint** (403 malgré un jeton valide) ; `huggingface_hub ≥ 1.0` a retiré `use_auth_token` ; `matplotlib` manquant |
| `loudpage` | aucun Dockerfile fourni ; `nemo_toolkit`, `lhotse`, `webdataset`, et `cuda-python` sur une machine sans GPU |
| `achetronic` | rien — une image, un port |

## Deux choses que `prepare.sh` ne fait pas

- **Il ne télécharge ni `config.json` ni `nemo128.onnx`** — le préprocesseur mel
  à 128 bandes dont `onnx-asr` a besoin. Sans lui : `Got: 80 Expected: 128`.
- **Il télécharge le fp32 (2,4 Go) avant l'int8.** Sur une liaison lente, c'est
  ce qui a arrêté la toute première session du chantier.

## Ce que ces mesures ne peuvent pas dire

Le **DER n'est pas calculable** : la transcription humaine de référence n'a aucun
horodatage. Le **WER est une borne inférieure**, jamais une estimation neutre —
`comparer.py` retient le point de troncature qui le minimise. Les biais connus
sont au § 5.4 de la spec, et chaque note de mesure les rappelle.
