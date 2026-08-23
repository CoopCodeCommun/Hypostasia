# Le banc d'essai de transcription locale a tourné / The local transcription benchmark ran

**Date :** 2026-08-22
**Migration :** Non

## Résumé / Summary

**Quoi / What :** première mesure d'inférence du chantier de transcription audio
locale, sur les deux piles candidates (Rust `parakeet-rs` + Sortformer v2 ;
Python `onnx-asr` + `diarize`), avec Voxtral comme base de comparaison sur le
même extrait. Le banc d'essai, qui n'existait que dans les annexes de sa spec,
est désormais versionné dans `benchmarks/transcription_audio/banc/`, et le
collage Python de la voie B — qui n'existait nulle part — est écrit.
/ First inference measurements of the local transcription effort, on both
candidate stacks, with Voxtral as the baseline on the same extract. The
benchmark code is now versioned, and the missing Python glue is written.

**Pourquoi / Why :** la spec était écrite depuis le 16 août et **aucun chiffre
d'inférence n'avait été relevé** — la première session s'était arrêtée pendant le
téléchargement des poids. Les trois décisions en attente du mainteneur
(`PLAN/PASSATION.md § 6`) ne pouvaient pas être éclairées sans ces mesures.
/ The spec was written but no inference number had ever been measured.

**Les résultats détaillés sont dans deux notes**, servies en HTML par
`/benchmarks/voir/`. Ce fichier-ci ne les recopie pas :

- [`2026-08-22_parakeet-contre-voxtral-sur-huit-vcpu.md`](../benchmarks/transcription_audio/2026-08-22_parakeet-contre-voxtral-sur-huit-vcpu.md)
  — les deux premières piles, et la découverte du mode d'emploi de Parakeet ;
- [`2026-08-23_neuf-piles-contre-la-transcription-humaine.md`](../benchmarks/transcription_audio/2026-08-23_neuf-piles-contre-la-transcription-humaine.md)
  — la campagne complète : **neuf piles, trois tranches, vingt-sept mesures**.

## Le 23 août — la campagne complète / The full campaign

**Quoi / What :** les cinq candidats restants du § 7 de la spec sont montés et
mesurés — Ultra-Sortformer 8 locuteurs, `sherpa-onnx`, pyannote dans ses **deux**
versions (3.1 *legacy* et `community-1` courant), WhisperX, et le serveur Go
`achetronic`. Le banc a un **pilote unique** dont le diariseur est
interchangeable, une **campagne scriptée**, un **agrégateur** et un **compose à
sept services**.
/ The five remaining candidates are built and measured; the benchmark now has one
driver with a swappable diarizer, a scripted campaign, an aggregator and a compose.

**Pourquoi / Why :** mesurer deux piles ne permet pas de choisir. Et deux
questions du mainteneur ont montré que le banc mesurait à côté : il faisait
tourner le pipeline pyannote **legacy** en le présentant comme l'état de l'art,
et il ne mesurait pas la qualité de transcription autrement que par le WER.
/ Two of the maintainer's questions showed the benchmark was measuring the wrong thing.

### Ce que la campagne établit

- **pyannote est le seul diariseur juste sur les trois tranches**, y compris à
  six voix. Ses deux versions sont équivalentes en compte, en temps et en mémoire.
- **WhisperX bat Voxtral sur le WER**, sur les trois tranches — la seule pile
  locale à passer devant l'API.
- **Parakeet TDT v3 bascule en anglais** selon le contenu : de 0,36 % à 38 % de
  mots anglais suivant la tranche et l'implémentation, contre 0,10 % chez
  l'humain. C'est ce qui le disqualifie, plus encore que son WER.
- **Aucune pile ne gagne sur tous les critères** : le meilleur texte coûte deux
  fois le temps réel, le meilleur comptage coûte 65 min/h et un jeton, le
  meilleur coût plafonne à quatre locuteurs en silence.

### Ce qui a été ajouté au banc, et pourquoi

| ajout | ce qu'il empêche |
|---|---|
| **garde-fou de charge** dans la campagne | une diarisation mesurée pendant un `docker build` a rendu **343 s** au lieu de 123 — faux, et faux en silence |
| **taux de mots anglais** dans l'agrégateur | sans lui, l'effondrement de Parakeet sur T2 passait pour une erreur de calage de la référence |
| **`--sans-asr`** dans le pilote | le pic RSS porte sur le processus entier : sans cette option, on ne peut pas comparer la mémoire de deux diariseurs |
| **`-long-audio`** pour `achetronic` | le serveur **rejette** tout fichier de plus de 400 s, et nos tranches en font 900 |
| **machine de repli** dans l'agrégateur | les lignes Rust et Voxtral affichaient `None vCPU` dans la colonne qui sert à comparer deux machines |

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `PLAN/specs/SPEC-transcription-audio-locale.md` | deux addenda datés du 22 août : l'emplacement du banc (décision tranchée), le contrat de la voie B, la comparaison à deux machines, et la correction du poids de Sortformer |
| `benchmarks/transcription_audio/README.md` | comment rejouer le banc ailleurs, et les deux pièges de `prepare.sh` |
| `benchmarks/transcription_audio/2026-08-22_*.md` | la note de mesure |
| `benchmarks/transcription_audio/banc/` | le banc extrait des annexes A à G, désormais versionné |
| `benchmarks/transcription_audio/banc/mesurer_une_pile.py` | **neuf** (ex-`voie_b.py`) — le pilote : ASR fixe, **diariseur interchangeable** (`diarize`, `sherpa`, `pyannote`, `pyannote-community`), plus `--sans-asr` |
| `benchmarks/transcription_audio/banc/mesurer_whisperx.py` | **neuf** — WhisperX, seule pile du banc à changer d'ASR |
| `benchmarks/transcription_audio/banc/mesurer_un_serveur_whisper.py` | **neuf** — les serveurs à API compatible Whisper (`achetronic`, `loudpage`) |
| `benchmarks/transcription_audio/banc/lancer_la_campagne.sh` | **neuf** — toutes les piles, toutes les tranches, en série, avec garde-fou de charge |
| `benchmarks/transcription_audio/banc/agreger_la_campagne.py` | **neuf** — une ligne par (pile, tranche, **machine**), WER et taux d'anglais compris |
| `benchmarks/transcription_audio/banc/preparer_la_campagne.sh` | **neuf** — télécharge TOUT en une commande, idempotent |
| `benchmarks/transcription_audio/banc/preparer_ultra_sortformer.sh` | **neuf** — recopie la crate et change `NUM_SPEAKERS` pour lever le plafond de 4 |
| `benchmarks/transcription_audio/banc/docker-compose.banc.yml` | **neuf** — sept services, séparé du compose du projet |
| `benchmarks/transcription_audio/banc/Dockerfile.{diarisation,pyannote4,whisperx,loudpage}` | **neufs** — une image par pile, parce que leurs dépendances sont **incompatibles entre elles** |
| `benchmarks/transcription_audio/banc/voxtral_de_reference.py` | **neuf** — produit la base de comparaison Voxtral, appel facturé et non répétable par accident |
| `benchmarks/transcription_audio/banc/installer_le_banc.sh` | **neuf** — dépose les scripts dans un dossier de travail passé en argument |
| `benchmarks/transcription_audio/banc/Dockerfile.voie-b` | **neuf** — l'image Python de la voie B |
| `benchmarks/transcription_audio/banc/run_bench.sh` | la source audio devient un argument, et elle entre dans le nom de l'extrait |

**Rien n'a été modifié dans le code de production.** Le worker Celery dédié
n'est pas ajouté : la spec demande de mesurer d'abord, proposer ensuite.

---

## Comment refaire la mesure / Manual test

Les scripts sont versionnés ; les poids (~5 Go), l'audio et les résultats bruts
vivent **hors du dépôt**, dans un dossier de travail passé en argument. Compter
~15 Go d'images, ~5 Go de téléchargement, et **plusieurs heures** de calcul pour
la campagne complète.

### Prérequis

- Docker et compose. Rien d'autre sur l'hôte : ni Python, ni `cargo`, ni `ffmpeg`.
- ~25 Go de disque, 8 Go de RAM libre.
- Un `.env` portant `HF_TOKEN_DIARIZATION` et, pour la base de comparaison,
  `MISTRAL_API_KEY`.
- **Les conditions acceptées** avec le compte du jeton sur
  `pyannote/speaker-diarization-3.1` **et** `pyannote/speaker-diarization-community-1`.
  L'accès se vérifie sur un **fichier**, jamais sur le dépôt : l'API des
  métadonnées répond 200 alors même que les poids sont refusés en 403.

### La campagne, en six commandes

```bash
bash benchmarks/transcription_audio/banc/installer_le_banc.sh ~/banc-transcription-travail
export DOSSIER_DE_TRAVAIL=~/banc-transcription-travail
export FICHIER_ENV=$PWD/.env

docker compose -f benchmarks/transcription_audio/banc/docker-compose.banc.yml up -d
docker exec bench-asr2 bash -c 'cd /work && bash preparer_la_campagne.sh'
docker exec bench-asr2 bash -c 'cd /work && cargo build --release && bash preparer_ultra_sortformer.sh'
bash benchmarks/transcription_audio/banc/lancer_la_campagne.sh "decrire ce que faisait la machine"
docker exec bench-python bash -c 'cd /work && python agreger_la_campagne.py'
```

`preparer_la_campagne.sh` contrôle que les références humaines rendent bien
**131** et **200** tours : un compte différent signale que la page a changé en
amont, ce qui décalerait tous les WER en silence.

### Mesurer une seule pile

```bash
# un diariseur au choix, ASR commun
docker exec bench-python bash -c 'cd /work && python mesurer_une_pile.py \
    --audio audio/extrait_complet_0_900s.wav --modeles ./hf-parakeet \
    --diariseur sherpa --max-locuteurs 8 --etiquette essai \
    --etat-de-la-stack "au repos"'

# la memoire du diariseur SEUL, sans l'ASR dans le pic
docker exec bench-pya4 bash -c 'cd /work && python mesurer_une_pile.py \
    --audio audio/extrait_complet_0_900s.wav --modeles ./hf-parakeet \
    --diariseur pyannote-community --sans-asr --etiquette memoire \
    --etat-de-la-stack "au repos"'
```

### Vérifier que la sortie entre dans le produit

```bash
docker cp ~/banc-transcription-travail/forme_produit_essai.json hypostasia_web:/tmp/
docker exec -w /app hypostasia_web bash -c 'PYTHONPATH=/app python -c "
import json, django, os
os.environ.setdefault(\"DJANGO_SETTINGS_MODULE\",\"hypostasia.settings\"); django.setup()
from front.services.transcription_audio import construire_html_diarise
html, texte = construire_html_diarise(json.load(open(\"/tmp/forme_produit_essai.json\")))
print(len(html), \"caracteres de HTML\")"'
```
