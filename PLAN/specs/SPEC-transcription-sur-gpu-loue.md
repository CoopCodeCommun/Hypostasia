# SPEC — La transcription sur GPU loué à la minute

**Projet** : Hypostasia V3
**Version** : 1.0 — 23 août 2026
**Périmètre** : exécuter **notre** conteneur de transcription sur un GPU loué à
la minute (OVHcloud AI Training), et savoir si cela coûte moins cher que l'API
Mistral tout en gardant la donnée sous notre contrôle.
**Statut** : **PROTOCOLE ÉCRIT, RIEN DE MESURÉ SUR GPU.** Tous les chiffres de
performance cités ici viennent du banc CPU (§ 2) ou des tarifs publics d'OVHcloud
(§ 4). Aucune inférence n'a jamais tourné sur GPU dans ce projet.
**Conventions** : skill `djc`. Les annexes suivent les commentaires bilingues
FR/EN comme le reste du projet.

> **Cette spec est faite pour être lue sans contexte.** Elle reprend les chiffres
> dont elle a besoin plutôt que d'y renvoyer, et ses annexes sont intégrales :
> une session qui l'ouvre à froid doit pouvoir dérouler le test de bout en bout.
>
> Elle **complète** `SPEC-transcription-audio-locale.md`, qui décide *quels
> modèles*. Celle-ci décide *où ils tournent*. Les deux se lisent ensemble, et
> la seconde ne rouvre aucune des questions tranchées par la première.

---

## 1. Le motif : la donnée, pas la juridiction

Le projet transcrit des **comptes rendus de délibération confidentiels**. Envoyés
à l'API Mistral, ils **nourrissent l'entraînement du fournisseur** — ce que ses
conditions autorisent. C'est le seul motif de ce chantier, et il ne se négocie
pas contre quelques points de WER.

**La nationalité du fournisseur n'est pas le sujet** : Mistral est une entreprise
française. Ce qui change avec un GPU loué, c'est que **la donnée ne quitte pas
notre chaîne** — elle transite par un Object Storage que nous contrôlons, elle
est traitée par des poids que nous avons figés, et personne ne la réutilise.

S'y ajoute un défaut mesuré de l'API : **elle n'est pas déterministe.** Deux
appels sur le même extrait ont rendu **26,90 %** puis **27,07 %** de WER. Pour
une chaîne de preuve, deux transcriptions différentes du même enregistrement sont
un problème en soi.

---

## 2. Ce que le banc CPU a déjà établi

Campagne des 22-23 août 2026, 36 mesures, 12 piles, 3 tranches de 900 s de
français radiophonique, contre transcription humaine
(`benchmarks/transcription_audio/`). Ce qu'il faut en retenir ici :

| | WER moyen | coût CPU | pic RSS |
|---|---|---|---|
| **WhisperX large-v3 + pyannote** | **30,5 %** | **101-112 min/h d'audio** | **8,3 Go** |
| WhisperX `large-v3-turbo` (ASR seul) | 31,5 % | 41 min/h | 3,66 Go |
| WhisperX `small` (ASR seul) | 36,0 % | 17 min/h | 3,15 Go |
| Voxtral (API) | 31,9 % | — | — |
| Parakeet + VAD | 47,7 % | ~10 min/h | 3,90 Go |

**Trois acquis qui commandent ce test :**

1. **L'ASR est tranché : Whisper.** Parakeet est éliminé — il bascule en anglais
   selon le contenu (jusqu'à 38 % de mots anglais contre 0,10 % chez l'humain),
   dans ses trois implémentations.
2. **Le diariseur est tranché : pyannote**, seul juste sur les trois tranches (y
   compris à six voix) et seul sans paramètre à deviner.
3. **La configuration retenue ne tient pas sur notre VPS** : 8,3 Go à côté des
   5,13 Go des juges NLI et des 2 Go de Docling. **C'est ce qui motive le GPU
   loué**, pas la vitesse.

**Le poste qui domine n'est pas celui qu'on croit** : sur CPU, la diarisation
pèse ~55 min/h contre ~60 pour l'ASR. Le GPU accélère beaucoup Whisper
(float16 + batch) et **bien moins pyannote**. C'est donc **pyannote qui décidera
de la facture**, et c'est la première chose à mesurer.

---

## 3. Ce que ce test doit établir

Dans cet ordre — le premier peut clore la question :

1. **Le RTFx réel sur GPU, séparément pour l'ASR et pour la diarisation.** Sans
   ces deux chiffres, le § 4 n'est qu'une équation.
2. **Le coût fixe d'un job** : pull de l'image, montage du volume, chargement des
   poids. Il décide de la **taille de lot** — s'il vaut trois minutes, il faut
   traiter les enregistrements par paquets et non un par un.
3. **Le WER sur les trois mêmes tranches**, pour vérifier que `float16` sur GPU
   rend le même texte que `int8` sur CPU. Le banc sait déjà le faire :
   `comparer.py` et les références humaines ne bougent pas.
4. **Le coût réel d'une heure d'audio**, facture à l'appui, à comparer aux
   0,17 € de Voxtral.

---

## 4. Le calcul du point mort

Voxtral coûte **0,003 $/min**, soit **0,18 $/h d'audio ≈ 0,17 €**. Un GPU loué
doit donc traiter une heure d'audio en moins de :

| GPU | prix horaire annoncé | budget de calcul par heure d'audio |
|---|---|---|
| **L4** | 0,75 €/h | **13,6 min** |
| L40S | 1,40 €/h | 7,3 min |
| H100 PCIe | 2,80 €/h (3,10 € en offre AI managée) | 3,6 min |

Notre mesure CPU donne 101 à 112 min/h. **Atteindre le point mort sur un L4
demande un facteur ×7,4.** Plausible pour l'ASR, incertain pour pyannote.

> **Tarifs relevés le 23 août 2026 sur les pages publiques d'OVHcloud. À
> revérifier avant toute décision** : ils changent, et la facturation à la minute
> n'est explicitement annoncée que sur l'offre AI managée.

**Le point mort n'est pas le seul critère.** Même à coût égal, le GPU loué gagne
sur le motif du § 1. Il faudrait qu'il soit *nettement* plus cher pour être
écarté.

---

## 5. Le protocole, de A à Z

### 5.1 Ce qu'il faut avant de commencer

- Un compte OVHcloud avec un **projet Public Cloud** et les **AI Tools** activés.
- Un **utilisateur AI** (identifiant + mot de passe), créé depuis l'espace client.
- Le jeton `HF_TOKEN_DIARIZATION` du `.env` du projet, **et les conditions
  acceptées** sur `pyannote/speaker-diarization-community-1` avec le compte qui
  porte ce jeton.
- Le banc installé localement : `benchmarks/transcription_audio/banc/`.

> **L'accès HuggingFace se vérifie sur un FICHIER, jamais sur le dépôt.** L'API
> des métadonnées répond `200` alors même que les poids sont refusés en `403`.
> Contrôle qui ne ment pas :
> ```bash
> curl -sSL -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $HF_TOKEN_DIARIZATION" \
>   https://huggingface.co/pyannote/speaker-diarization-community-1/resolve/main/config.yaml
> ```

### 5.2 Installer et connecter la CLI

```bash
# installation (une ligne, voir la doc CLI d'OVHcloud pour la variante manuelle)
ovhai login          # identifiants de l'utilisateur AI
ovhai config list    # verifier la region active
```

### 5.3 Préparer l'Object Storage

La donnée ne doit **jamais** être embarquée dans l'image : elle vit dans un
conteneur d'objets, monté au lancement du job.

```bash
# pousser l'audio de test (les trois tranches du banc CPU, pour comparer)
ovhai bucket object upload transcription@GRA audio/extrait_complet_0_900s.wav
ovhai bucket object upload transcription@GRA audio/extrait_cafe_libre_complet_600_900s.wav
ovhai bucket object upload transcription@GRA audio/extrait_emission_complete_4100_900s.wav

# pousser les references humaines, pour calculer le WER sur place
ovhai bucket object upload transcription@GRA reference.json
ovhai bucket object upload transcription@GRA reference_cafe_libre.json

ovhai bucket object list transcription@GRA
```

**Les poids vont aussi sur l'Object Storage**, dans un second conteneur — les
retélécharger depuis HuggingFace à chaque job serait payé en minutes de GPU :

```bash
# depuis une machine ou le cache existe deja (celui du banc)
ovhai bucket object upload poids@GRA .cache_huggingface/hub --recursive
```

### 5.4 Construire l'image GPU

**Trois contraintes d'AI Training, et aucune n'est optionnelle** (annexe A) :

| contrainte | ce qu'il faut écrire |
|---|---|
| l'image ne tourne **pas en root**, mais sous l'UID **42420** | `RUN chown -R 42420:42420 /workspace` |
| `HOME` doit valoir `/workspace` | `ENV HOME=/workspace` |
| tout dossier créé dynamiquement doit appartenir à 42420 | `RUN chown -R 42420:42420 /logs /runs` |

```bash
docker buildx build --platform linux/amd64 -f Dockerfile.gpu -t banc-gpu:1 .

# LE test qui evite la mauvaise surprise a distance : rejouer les droits reels
docker run --rm -it --user=42420:42420 banc-gpu:1 python -c "print('ok')"
```

### 5.5 Pousser l'image sur un registre

```bash
docker login -u <utilisateur> -p <mot-de-passe> <adresse-du-registre>
docker tag banc-gpu:1 <adresse-du-registre>/banc-gpu:1
docker push <adresse-du-registre>/banc-gpu:1
```
Le registre privé se déclare ensuite auprès d'AI Training (espace client ou
`ovhai registry add`), avec les identifiants du registre.

### 5.6 Lancer le job

```bash
ovhai job run <adresse-du-registre>/banc-gpu:1 \
    --gpu 1 \
    --volume transcription@GRA:/data:rw \
    --volume poids@GRA:/poids:ro \
    --env HF_TOKEN_DIARIZATION=<jamais en clair : voir l'encart ci-dessous> \
    -- bash /workspace/mesurer_sur_gpu.sh
```

> **Le jeton ne s'écrit ni dans l'image, ni dans un script versionné, ni dans une
> ligne de commande que `ps` peut lire.** Le poser dans les variables du job
> depuis l'espace client, ou passer par un fichier de secrets. Un secret écrit
> dans un script finit poussé sur la forge au premier `git add -A` distrait.

Suivi et récupération :

```bash
ovhai job logs <job-id> --follow
ovhai job get <job-id>          # etat, duree, ressources
ovhai bucket object download transcription@GRA --prefix resultat_
```

### 5.7 Mesurer

Le script embarqué (annexe B) chronomètre **séparément** le chargement, l'ASR et
la diarisation, exactement comme le banc CPU — sans quoi on ne saura pas lequel
des deux étages coûte.

Puis, en local, la comparaison se fait avec le code déjà écrit :

```bash
python3 benchmarks/transcription_audio/banc/comparer.py \
    resultat_gpu-T1.json reference.json 10
python3 benchmarks/transcription_audio/banc/agreger_la_campagne.py
```

**Le coût réel se lit sur la facture**, pas sur une estimation : relever la durée
facturée du job (`ovhai job get`) et la comparer au temps d'inférence mesuré. **La
différence est le coût fixe**, et c'est le chiffre du § 3.2.

---

## 6. Les pièges connus, et ce qu'ils coûtent

| piège | conséquence | parade |
|---|---|---|
| **l'image pèse 14,3 Go** (celle du banc CPU) | si le pull est facturé, un job de 5 min coûte le double | image **mince** : CUDA + WhisperX, **sans les poids** |
| **les poids dans l'image ou sur le hub** | 2,9 Go retéléchargés à chaque job, payés en minutes de GPU | Object Storage monté en lecture seule |
| **écrire hors de `/workspace` ou de `/data`** | permission refusée sous l'UID 42420, le job meurt au premier `open()` | `chown -R 42420:42420` sur tout dossier écrit |
| **`--platform linux/amd64` oublié** | image ARM construite sur un Mac, illisible à distance | toujours `docker buildx build --platform linux/amd64` |
| **mesurer sans séparer les étages** | on saura que « c'est plus rapide », pas **où** | trois chronos, comme le banc CPU |
| **une seule passe** | l'écart entre deux passes du même job n'est pas connu | au moins deux passes avant de conclure |

**Et le piège de méthode, qui a déjà coûté une campagne** : une mesure prise
pendant qu'autre chose tourne est fausse **en silence**. Sur le banc CPU, une
diarisation chronométrée pendant un `docker build` a rendu 343 s au lieu de 123.
Sur un GPU dédié le risque est moindre, mais **ne jamais lancer deux jobs
simultanés sur le même GPU**.

---

## 7. Les critères de la décision

Dans cet ordre, le premier qui échoue disqualifie :

1. **La donnée reste-t-elle sous notre contrôle ?** Nos poids, notre conteneur,
   notre Object Storage, aucune réutilisation par le fournisseur. C'est le motif
   du chantier ; s'il n'est pas tenu, le reste ne compte pas.
2. **Le WER `float16`/GPU vaut-il celui d'`int8`/CPU** sur les trois tranches ?
   Un écart de plus de deux points invaliderait la bascule.
3. **Le coût par heure d'audio** tient-il la comparaison avec les 0,17 € de
   Voxtral, coût fixe du job compris ?
4. **L'exploitation est-elle tenable** : un job se lance depuis une tâche Celery,
   échoue proprement, et se reprend sans intervention ?

---

## 8. Ce que ce test ne dit pas

- **Rien sur la qualité des modèles** : elle est tranchée par le banc CPU, et le
  GPU ne la change pas — sauf par la quantification, ce que le critère 2 vérifie.
- **Rien sur le nombre de voix des enregistrements réels**, qui reste la question
  ouverte du § 6 de `PLAN/PASSATION.md` et qui commande le choix du diariseur.
- **Rien sur la latence** : le besoin est du traitement par lots, personne
  n'attend devant l'écran.

---

## Annexe A — `Dockerfile.gpu`

```dockerfile
# Le banc de transcription, en CUDA, pour AI Training.
# / The transcription benchmark, CUDA build, for AI Training.
#
# TROIS CONTRAINTES D'AI TRAINING, et aucune n'est optionnelle :
#   1. l'image ne tourne PAS en root, mais sous l'UID 42420 ;
#   2. HOME doit valoir /workspace ;
#   3. tout dossier ou l'on ecrit doit appartenir a 42420.
# Un `open()` hors de ces dossiers echoue, et le job meurt a la premiere ligne.
# / Three AI Training constraints: UID 42420, HOME=/workspace, chown everything written.
#
# L'IMAGE NE PORTE AUCUN POIDS. Ils vivent sur l'Object Storage, monte en
# lecture seule : les embarquer ajouterait 3 Go a chaque pull, et le pull est
# du temps facture.
# / No weights in the image: they live on Object Storage, mounted read-only.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# torch CUDA, et non la variante CPU du banc local.
# / CUDA torch, not the CPU wheel used by the local bench.
RUN pip3 install --no-cache-dir torch torchaudio \
        --index-url https://download.pytorch.org/whl/cu124
RUN pip3 install --no-cache-dir whisperx

WORKDIR /workspace
ENV HOME=/workspace

# Le cache des bibliotheques pointe vers le volume monte : sans cela, elles
# retelechargeraient les poids a chaque job.
# / Caches point at the mounted volume, or the weights would be re-downloaded.
ENV HF_HOME=/poids
ENV TORCH_HOME=/poids/torch

COPY mesurer_whisperx.py comparer.py mesurer_sur_gpu.sh /workspace/

# LE chown : sans lui, rien n'est ecrivable sous l'UID 42420.
# / THE chown: without it, nothing is writable as UID 42420.
RUN chown -R 42420:42420 /workspace

# Verification locale, qui rejoue les droits reels d'AI Training :
#   docker run --rm -it --user=42420:42420 banc-gpu:1 python3 -c "import whisperx"
```

## Annexe B — `mesurer_sur_gpu.sh`

```bash
#!/usr/bin/env bash
# Le point d'entree du job : mesure les trois tranches, ecrit dans /data.
# / The job entrypoint: measures the three slices, writes to /data.
#
# POURQUOI TROIS TRANCHES ET PAS UNE. Le banc CPU a montre que la qualite de
# transcription varie fortement d'un enregistrement a l'autre — un modele peut
# rendre 26 % de WER sur l'un et 39 % sur l'autre. Une seule tranche ne dirait
# rien de comparable aux mesures deja faites.
# / One slice would not compare with the CPU campaign: quality varies a lot.
set -uo pipefail

ETAT="GPU loue OVHcloud AI Training, job dedie, aucune autre charge"
cd /data

for tranche in \
    "extrait_complet_0_900s:T1" \
    "extrait_cafe_libre_complet_600_900s:T2" \
    "extrait_emission_complete_4100_900s:T4" ; do

    IFS=':' read -r fichier nom <<< "$tranche"
    echo "########## $nom ##########"

    # float16 et non int8 : sur GPU c'est la quantification utile, l'int8 y
    # perd son interet (il n'existe pas de chemin entier optimise sur ces
    # cartes pour CTranslate2).
    # / float16, not int8: on GPU that is the useful precision.
    python3 /workspace/mesurer_whisperx.py \
        --audio "$fichier.wav" \
        --peripherique cuda \
        --modele "${MODELE_WHISPER:-large-v3-turbo}" \
        --quantification float16 \
        --langue fr \
        --max-locuteurs 8 \
        --etiquette "gpu-$nom" \
        --etat-de-la-stack "$ETAT" \
        --forme-produit
done

echo "########## JOB TERMINE ##########"
ls -la /data/resultat_gpu-*.json
```

## Annexe C — la boucle complète, en une page

```bash
# 1. preparer (une fois)
ovhai login
ovhai bucket object upload transcription@GRA audio/extrait_complet_0_900s.wav
ovhai bucket object upload poids@GRA .cache_huggingface/hub --recursive

# 2. construire et pousser l'image
docker buildx build --platform linux/amd64 -f Dockerfile.gpu -t banc-gpu:1 .
docker run --rm --user=42420:42420 banc-gpu:1 python3 -c "import whisperx; print('ok')"
docker tag banc-gpu:1 <registre>/banc-gpu:1 && docker push <registre>/banc-gpu:1

# 3. lancer
ovhai job run <registre>/banc-gpu:1 --gpu 1 \
    --volume transcription@GRA:/data:rw --volume poids@GRA:/poids:ro \
    -- bash /workspace/mesurer_sur_gpu.sh

# 4. suivre, puis rapatrier
ovhai job logs <job-id> --follow
ovhai job get <job-id>        # <- la DUREE FACTUREE se lit ici
ovhai bucket object download transcription@GRA --prefix resultat_gpu-

# 5. comparer, en local, avec le code du banc CPU
python3 benchmarks/transcription_audio/banc/comparer.py resultat_gpu-T1.json reference.json 10
```

---

## 9. Sources

- Tarifs GPU OVHcloud (relevés le 23 août 2026) :
  [L4](https://www.ovhcloud.com/en/public-cloud/gpu/l4/) ·
  [L40S](https://www.ovhcloud.com/en/public-cloud/gpu/l40s/) ·
  [H100](https://www.ovhcloud.com/en/public-cloud/gpu/h100/)
- [AI Training — construire et utiliser une image Docker personnalisée](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-training-build-use-custom-image)
  (UID 42420, `HOME=/workspace`, `chown`)
- [CLI `ovhai` — référence des commandes](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-cli-overview)
  (`job run`, `bucket object`, `--volume`)
- [CLI — installation](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-cli-install-client)
- [Registres — utiliser et gérer ses registres](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-manage-registries)
- [AI Deploy — déployer Whisper](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-deploy-openai-whisper)
  (tutoriel officiel, utile comme point de comparaison)
- Les mesures CPU du projet : `benchmarks/transcription_audio/`
