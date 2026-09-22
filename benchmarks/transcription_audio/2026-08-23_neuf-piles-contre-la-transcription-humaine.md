# Neuf piles contre la transcription humaine — la campagne complète

**23 août 2026.** Neuf piles, trois tranches, vingt-sept mesures, toutes prises
l'une après l'autre sur la même machine. La note du 22 août comparait deux piles
et Voxtral ; celle-ci ajoute Ultra-Sortformer, sherpa-onnx, les **deux** versions
de pyannote, WhisperX et un serveur Go.

**Machine** — chaque chiffre vaut *pour cette machine*, et le mainteneur rejouera
la campagne sur un Framework Laptop 13 (Core Ultra 7 155H) :

| | |
|---|---|
| processeur | `Intel Core Processor (Haswell, no TSX)` — VM QEMU/KVM |
| vCPU | **8**, 1 thread par cœur |
| VNNI / AMX | **aucun** — le drapeau le plus élevé est `avx2` |
| RAM | 22 Go, ~14 Go disponibles |
| état de la stack | Hypostasia en marche, workers Celery résidents au repos, aucune tâche en cours |
| garde-fou | chaque mesure attend que la charge repasse **sous 2,0** — voir « ce qui a failli fausser la campagne » |

---

## Ce que la campagne établit, en quatre points

1. **pyannote est le seul diariseur juste sur les trois tranches**, y compris à
   six voix. Les deux versions — 3.1 *legacy* et `community-1` courant — trouvent
   le compte exact partout. Aucune autre pile n'y parvient.
2. **WhisperX bat Voxtral sur la qualité du texte, sur les trois tranches.**
   C'est la seule pile locale qui passe devant l'API — 25,05 % contre 27,07 % de
   WER sur T1, et l'écart tient ailleurs.
3. **Parakeet TDT v3 bascule en anglais, et de façon imprévisible.** Sur une
   tranche il rend 0,36 % de mots anglais, sur une autre **11 à 38 %**. Whisper
   ne le fait pas : 0,00 à 0,12 %. C'est ce qui disqualifie Parakeet pour du
   français conversationnel, bien plus que son WER.
4. **Le montage compte autant que les modèles.** `community-1` trouve 6 voix sur
   6 dans notre pilote, et 5 sur 6 à l'intérieur de WhisperX — même pipeline de
   diarisation, même audio, assignation différente.

---

> **Une pile n'est pas dans les chiffres : `loudpage/parakeet-v3-diarized`.**
> Son image se construit (12 Go), mais elle n'a pas encore tourné — un build
> pendant une mesure la fausserait, et la campagne occupait la machine. Ce qui
> est déjà mesuré la concernant est son **coût d'installation**, qui est le plus
> élevé du banc. Et ce qu'elle apporterait est limité : c'est Parakeet (l'ASR
> que cette campagne disqualifie) servi par NeMo au lieu d'ONNX.

## Les trois tranches

| tranche | source | voix réelles | ce qu'elle éprouve |
|---|---|---|---|
| **T1** | n° 282 du 7 juillet, sujet Tactic, 0 → 900 s | **4**, dont une à 90 mots | le locuteur minoritaire |
| **T2** | 16 juin, « Au café libre », 600 → 1500 s | **4**, équilibrées | le cas favorable |
| **T4** | 16 juin, émission entière, 4100 → 5000 s | **6** | le plafond |

---

## Critère 1 — le comptage des locuteurs

C'est le critère qui disqualifie. Nombre de locuteurs rendus / nombre réel :

| pile | T1 (4, déséquilibrées) | T2 (4, équilibrées) | T4 (**6**) |
|---|---|---|---|
| voie A — Sortformer v2 | 3 | **4** ✓ | **4** — son plafond dur |
| voie A — Ultra-Sortformer 8spk | 3 | **4** ✓ | 8 |
| pilote — `diarize` | 3 | **4** ✓ | 5 |
| pilote — `sherpa-onnx` | **15** | **24** | **16** |
| pilote — **pyannote 3.1** | **4** ✓ | **4** ✓ | **6** ✓ |
| pilote — **`community-1`** | **4** ✓ | **4** ✓ | **6** ✓ |
| WhisperX | **4** ✓ | **4** ✓ | 5 |
| Voxtral (API) | **4** ✓ | **4** ✓ | 7 |
| achetronic | 1 | 1 | 1 — *ne diarise pas* |

**pyannote est le seul à ne jamais se tromper.** Et l'écart entre ses deux
versions est nul sur ce critère.

**Le plafond de Sortformer se voit à l'œil nu** : exactement 4 slots pour 6
personnes, ce que le § 4.5 de la spec annonçait comme « limitation attendue de
l'architecture ». Le binaire patché à 8 slots lève bien le plafond — il rend 8 —
mais il sur-segmente au lieu de compter juste.

**sherpa-onnx est hors-jeu, et c'est probablement notre faute.** 15, 24 et 16
locuteurs : le seuil de clustering que le banc lui passe (`threshold=0.5`,
`num_clusters=-1`) est manifestement mauvais pour du français radiophonique.
**Ce chiffre mesure notre paramétrage, pas la pile** — il faudrait balayer le
seuil avant d'en conclure quoi que ce soit. En l'état, la seule chose établie est
qu'elle ne marche pas *par défaut*.

**Voxtral sur-segmente à 6 voix** (7 pour 6), comme le 22 août. Son erreur reste
détectable — ses locuteurs excédentaires portent une poignée de mots.

### La nuance qui compte pour l'architecture

`community-1` rend **6 voix sur 6** dans notre pilote et **5 sur 6** dans
WhisperX, sur le même audio, avec les mêmes bornes `min/max_speakers`. La
différence n'est pas dans le modèle : elle est dans l'**assignation**. Notre
pilote attribue chaque mot au tour qui recouvre son point milieu, puis compte les
locuteurs présents ; WhisperX assigne par segment Whisper, et un locuteur qui ne
parle que dans un segment absorbé disparaît du compte.

**Autrement dit : à modèles égaux, le collage décide.** C'est un argument pour
garder notre pilote plutôt que d'adopter une pile intégrée — mais c'est une
observation sur une tranche, pas une loi.

---

## Critère 2 — la qualité du texte

WER contre la transcription humaine (borne inférieure, cf. les biais), et part de
mots anglais courants — la référence humaine est à **0,10 %** :

| pile | WER T1 | WER T2 | WER T4 | anglais T1 | anglais T2 | anglais T4 |
|---|---|---|---|---|---|---|
| **WhisperX** (Whisper large-v3) | **25,05 %** | **36,41 %** | **29,92 %** | 0,12 % | **0,03 %** | **0,00 %** |
| Voxtral (API) | 27,07 % | 36,78 % | 31,95 % | 0,12 % | 0,03 % | 0,00 % |
| pilote (Parakeet + VAD) | 34,95 % | 67,92 % | 40,13 % | 0,36 % | **11,41 %** | 1,36 % |
| voie A (Parakeet, blocs 20 s) | 39,09 % | 75,43 % | 63,69 % | 0,92 % | **16,91 %** | 8,83 % |
| achetronic (Parakeet, serveur Go) | 60,66 % | **97,67 %** | 60,63 % | 0,15 % | **38,26 %** | 1,59 % |

**Le WER de T2 n'est pas un défaut de calage — c'est un effondrement réel.** Je
l'ai cru un moment : 75 % de WER sur une tranche dont le tour de départ n'est pas
vérifié contre l'audio, c'est le premier soupçon. La colonne « anglais » tranche :
**16,91 %** de mots anglais contre 0,36 % sur T1. Parakeet part en anglais sur
cette tranche, et Whisper n'y bouge pas (0,03 %). Sur le même extrait, avec la
même référence et le même calage.

**achetronic s'effondre complètement sur T2** : 311 mots produits pour 900 s
d'audio, 38 % d'anglais, 97,67 % de WER. Le serveur découpe pourtant en fenêtres
glissantes avec VAD — cela n'y change rien.

**Ce que ça dit de Parakeet TDT v3** : ce n'est pas un modèle un peu moins bon en
français, c'est un modèle **instable** en français. Sa qualité dépend du contenu
d'une façon qu'aucun réglage du banc n'a corrigée — ni le VAD, ni la taille des
blocs, ni la quantification, ni l'implémentation (Rust, Python, Go : les trois
basculent).

---

## Les quatre tailles de Whisper — la mesure qui déplace tout

Le WER du tableau précédent est déterminé par l'**ASR**, jamais par le diariseur :
les quatre lignes « pilote » partagent le même texte au caractère près. La vraie
question était donc : *quelle taille de Whisper faut-il payer ?* Mesuré sur les
trois tranches, ASR seul (`--sans-diarisation`) :

| modèle | WER T1 | WER T2 | WER T4 | **moyenne** | min/h | pic RSS |
|---|---|---|---|---|---|---|
| **large-v3** | 25,05 % | 36,41 % | 29,92 % | **30,5 %** | ~60 | 8,27 Go |
| **large-v3-turbo** | 26,35 % | 36,82 % | 31,36 % | **31,5 %** | 41 | **3,66 Go** |
| medium | 26,85 % | 39,49 % | 34,46 % | 33,6 % | 37 | 5,43 Go |
| small | 30,88 % | 41,74 % | 35,50 % | 36,0 % | **17** | **3,15 Go** |
| *Parakeet + VAD, pour comparaison* | 34,95 % | 67,92 % | 40,13 % | 47,7 % | ~10 | 3,90 Go |

**Trois conclusions, et la première clôt le débat sur l'ASR :**

1. **Whisper `small` bat Parakeet sur tous les tableaux** — 36,0 % contre 47,7 %
   de WER, 0,03 % contre 4,38 % de mots anglais, pour un coût du même ordre
   (17 contre ~10 min/h) et **moins de mémoire** (3,15 contre 3,90 Go). À partir
   de là, **Parakeet n'a plus aucun argument** : il n'est ni meilleur, ni moins
   cher, ni plus léger, et il est le seul à basculer en anglais.
2. **`turbo` domine `medium`** : meilleur WER (31,5 contre 33,6 %) **et** 1,8 Go
   de moins. `medium` sort du jeu. Il ne domine pas `medium` en vitesse
   (41 contre 37 min/h), et la raison mérite d'être connue : **turbo garde
   l'encodeur complet de large-v3 et ne réduit que le décodeur** (4 couches au
   lieu de 32). Sur GPU, où le décodage domine, cela donne les ×8 annoncés en
   amont ; **sur CPU et sur de l'audio long, c'est l'encodeur qui coûte**, et il
   est intact. Le gain se réduit à ~30 % contre large-v3.
3. **La dégradation est douce** — 30,5 → 31,5 → 33,6 → 36,0 % quand on descend
   en taille, pendant que le coût est divisé par quatre. Aucun décrochage : le
   choix est un curseur, pas une falaise.

**Aucune taille ne bascule en anglais** : 0,00 à 0,12 %, contre 0,10 % chez
l'humain. L'instabilité était bien propre à Parakeet, pas au découpage.

---

## sherpa-onnx : le seuil n'est pas réglable une fois pour toutes

Le premier tableau donnait 15, 24 et 16 locuteurs pour 4, 4 et 6 réels — un
chiffre qui mesurait notre paramétrage, pas la pile. Balayage complet :

| seuil (CAM++) | T1 (4) | T2 (4) | T4 (6) |
|---|---|---|---|
| 0,5 | 15 | 24 | 16 |
| 0,7 | 9 | 12 | 11 |
| 0,9 | 6 | 9 | 7 |
| 0,95 | 5 | — | **6 ✓** |
| **1,0** | **4 ✓** | — | 4 |
| 1,1 | 3 | — | 3 |

**Aucun seuil ne convient aux trois tranches.** À 1,0 le compte est exact sur T1
et retombe à 4 sur T4 ; à 0,95 c'est l'inverse.

Essai avec **l'extracteur d'empreintes de pyannote lui-même**
(`wespeaker_en_voxceleb_resnet34_LM`), dans l'idée de reproduire le pipeline
officiel en ONNX et sans jeton : il **sous-segmente** au contraire — 3, 5, 2 à
seuil 0,5, et 1, 2, 1 à seuil 0,8. Sa plage utile est ailleurs. Mettre le modèle
de pyannote dans sherpa ne suffit pas : le clustering n'est pas le même.

**On s'arrête là, et c'est une conclusion, pas un abandon.** Continuer à affiner
reviendrait à régler un paramètre sur trois extraits pour qu'il tombe juste sur
ces trois extraits — un seuil calibré ainsi n'aurait aucune valeur prédictive, et
le banc produirait un chiffre flatteur qui mentirait au déploiement. Le résultat
honnête est celui-ci : **sherpa exige un seuil qui dépend de l'enregistrement ;
pyannote trouve juste sans aucun réglage.** C'est précisément ce qu'on paie dans
ses 65 min/h.

---

## loudpage : mort en OOM, et abandonné

La pile n'a jamais rendu un chiffre de qualité. Ce qu'elle a coûté avant d'y
renoncer, au titre du critère 4 :

| ce qu'il a fallu | détail |
|---|---|
| écrire son Dockerfile | le dépôt n'en fournit **aucun** |
| retirer `cuda-python` | dans ses dépendances, sur une machine sans GPU |
| **rétrograder NeMo 3.0.0 → 2.3.1** | la 3.0.0 importe `nv_one_logger`, **absent de PyPI** (404) et de l'index NVIDIA public. Le serveur annonçait pourtant `Application startup complete` — **sans modèle chargé** |
| renommer le jeton | il attend `HUGGINGFACE_ACCESS_TOKEN`, pas `HF_TOKEN_DIARIZATION` |
| 12 Go d'image | contre 4,3 à 4,8 Go pour les autres |

Et au bout : **tué par l'OOM killer sur une tranche de 900 s**,
`OOMKilled=true`, exit 137, **11,6 Go de RSS** relevés par le noyau alors qu'il
n'avait traité que le premier de ses deux morceaux de 450 s. Sur une machine de
22 Go dont 14 disponibles.

**Abandonné en accord avec le mainteneur.** Ce qu'il apporte est de toute façon
Parakeet servi par NeMo au lieu d'ONNX — l'ASR que cette campagne disqualifie.

---

## Critère 3 — le coût

Minutes de calcul par heure d'audio, et pic mémoire du processus :

| pile | T1 | T2 | T4 | pic RSS |
|---|---|---|---|---|
| voie A — Sortformer v2 | **13,2** | **12,9** | **12,7** | **1,83-1,85 Go** |
| voie A — Ultra-Sortformer 8spk | 13,6 | 13,6 | 13,5 | 2,28 Go |
| achetronic | 14,2 | 13,9 | 13,9 | — |
| pilote — `diarize` | 20,9 | 20,3 | **16,1** | 3,87-3,93 Go |
| pilote — `sherpa-onnx` | 27,5 | 28,1 | 23,1 | 3,42-3,46 Go |
| pilote — **pyannote 3.1** | 65,2 | 64,2 | 62,8 | 3,78-3,79 Go |
| pilote — **`community-1`** | 65,4 | 66,9 | 65,1 | 3,77-3,82 Go |
| **WhisperX** | **101,5** | **112,3** | **100,6** | **7,76-8,49 Go** |
| Voxtral (API) | 0,7 | 0,8 | 0,9 | — |

**Le critère 3 est satisfait par tout le monde sauf WhisperX**, qui demande
presque **deux fois le temps réel** et 8 Go. Une heure d'audio lui coûterait
1 h 40 de calcul — tenable pour un lot de nuit, pas pour une file qui doit
avancer.

**Les deux versions de pyannote coûtent la même chose** : 62,8 à 66,9 min/h, et
3,8 Go. L'écart entre elles est dans le bruit.

### pyannote 3.1 contre `community-1`, diariseur seul

Le pic RSS du tableau porte sur le processus entier, ASR compris — il ne permet
pas de comparer deux diariseurs entre eux. Mesure refaite avec `--sans-asr`, qui
ne charge rien de Parakeet, sur la tranche T1 (900 s) :

| | pic RSS du **diariseur seul** | diarisation | locuteurs |
|---|---|---|---|
| pyannote **3.1** (legacy) | **2,28 Go** | 882,8 s | 4 / 4 |
| **`community-1`** (courant) | **2,29 Go** | 852,4 s | 4 / 4 |

**18 Mo d'écart, soit 0,8 %** — et `community-1` est même 3,4 % plus rapide.
**Aucune régression mémoire n'est visible sur CPU**, y compris en isolant le
diariseur. L'ASR pesait 1,5 Go dans les chiffres du tableau.

Deux réserves : la régression signalée en amont porte sur la **VRAM**, qui n'a
pas d'objet ici — aucune image du banc n'est CUDA. Et l'écart de temps entre ces
882,8 s et les 818,9 s relevés dans la campagne (8 %) dépasse le seuil de bruit
que cette note se donne : **une seule passe par ligne**, donc ce 3,4 % d'avance
de `community-1` ne veut rien dire non plus.

**La diarisation redevient le goulot dès qu'on quitte Sortformer.** Chez
pyannote, elle pèse 818 à 859 s contre 125 à 160 s pour la transcription — cinq
à sept fois plus. L'hypothèse 6 de la spec, infirmée le 22 août avec Sortformer,
est donc **vraie pour pyannote** : tout dépend du diariseur qu'on choisit.

---

## Ce qui a failli fausser la campagne, et le garde-fou qui en est né

**Une mesure prise sur une machine occupée est fausse, et fausse en silence.**
Le 23 août, une diarisation `community-1` mesurée pendant un `docker build` a
rendu **343 s** là où elle en prend **123** — presque le triple, sans qu'aucune
erreur ne le signale. La charge était à 10,3 sur 8 vCPU.

`lancer_la_campagne.sh` attend désormais que la charge repasse **sous 2,0** avant
chaque mesure, et écrit la valeur relevée à côté de chaque ligne. Si elle ne
redescend pas en trente minutes, il mesure quand même **et écrit que le chiffre
est suspect**. Les vingt-sept mesures de cette note ont toutes été prises sous
ce garde-fou ; le journal montre plusieurs attentes réelles.

Deux autres incidents, consignés parce qu'ils coûteraient une demi-journée à qui
les redécouvrirait :

- **Le serveur `achetronic` rejette tout fichier de plus de 400 s** sans
  l'option `-long-audio` (« audio exceeds the single-pass model limit »). Nos
  tranches font 900 s. L'option est dans `docker-compose.banc.yml`.
- **Écraser un script pendant que `bash` l'exécute peut le faire dérailler** —
  bash relit le fichier au fil de l'exécution. Une campagne a dû être relancée
  pour cette raison.

---

## Les frictions d'installation — le critère 4, mesuré

| pile | ce qu'il a fallu |
|---|---|
| voie A (Rust) | Debian **13** — ONNX Runtime réclame glibc ≥ 2.38 |
| voie A à 8 locuteurs | **recopier la crate et changer une constante** (`NUM_SPEAKERS`) |
| `onnx-asr` | ajouter `config.json` et `nemo128.onnx`, absents de `prepare.sh` |
| `sherpa-onnx` | **rien** — `pip install`, deux modèles, aucun jeton |
| `achetronic` | **rien** — une image, un port, une option |
| **pyannote** | **quatre** blocages : `torchaudio ≥ 2.9` a retiré `AudioMetaData` ; la 4.x redirige vers un dépôt **restreint** (403 malgré un jeton valide, jusqu'à acceptation des conditions) ; `huggingface_hub ≥ 1.0` a retiré `use_auth_token` ; `matplotlib` manquant |
| WhisperX | jeton et conditions de `community-1`, comme pyannote |
| `loudpage` | **aucun Dockerfile fourni** — écrit pour le banc ; `cuda-python` retiré de ses dépendances (inutile sans GPU) ; image de **12 Go sur disque**, contre 4,3 à 4,8 Go pour les autres |
| Voxtral | une clé d'API, facturé |

**Un détail qui compte pour rejouer ailleurs** : pyannote 3.1 range son modèle
d'empreintes dans `/root/.cache/torch/pyannote/`, **pas** dans `HF_HOME`. Monter
un seul cache ne suffit donc pas à tout mutualiser.

---

## Les biais

Les quatre du § 5.4 de la spec valent pour tous les chiffres ci-dessus (WER en
borne inférieure, nombres non normalisés, mots coupés aux frontières,
granularité d'attribution). Quatre s'y ajoutent :

1. **Une seule passe par ligne.** Aucune dispersion mesurée. Les écarts sous ~5 %
   ne sont pas significatifs. L'API Voxtral, appelée deux fois sur T1 à un jour
   d'écart, a rendu 26,90 % puis 27,07 % : **elle n'est pas déterministe.**
2. **Le tour de départ n'est vérifié contre l'audio que pour T1.** Pour T2 et T4
   il vient d'un calage par débit moyen. Le **classement** des piles reste
   cohérent entre les trois tranches, ce qui est le seul usage qu'on en fait.
3. **Le taux de mots anglais est un indicateur, pas une mesure de langue** — 40
   mots courants comptés. Sa valeur de référence est le 0,10 % de la
   transcription humaine.
4. **Le pic RSS porte sur le processus entier**, ASR compris. Il ne permet pas de
   comparer la mémoire de deux diariseurs entre eux — c'est l'objet d'une mesure
   séparée (`--sans-asr`).

---

## Ce que ça change pour la décision

**Aucune pile ne gagne sur tous les critères, et c'est le résultat.**

- **Le meilleur texte** est celui de WhisperX, qui bat l'API — mais il coûte
  deux fois le temps réel et 8 Go, et il rate le comptage à six voix.
- **Le meilleur comptage** est celui de pyannote, seul juste partout — mais il
  coûte 65 min/h, exige un jeton et l'acceptation de conditions sur un site
  tiers, et son installation a demandé quatre correctifs de version.
- **Le meilleur coût** est celui de Sortformer — mais son plafond de 4 est
  atteint, et silencieux.
- **Parakeet TDT v3 est le point commun de toutes les piles locales bon marché,
  et c'est lui qui les plombe** : instable en français, il bascule en anglais
  selon le contenu, dans les trois implémentations testées.

### Ce que la campagne recommande, une fois tout mesuré

**L'ASR est tranché : Whisper, quelle que soit la taille.** Même `small` bat
Parakeet sur la qualité, la stabilité et la mémoire, pour un coût comparable.
Les sept piles bâties sur Parakeet tombent d'un bloc.

**Le diariseur est tranché aussi : pyannote**, seul juste sur les trois tranches,
et le seul qui n'exige aucun paramètre à deviner. Ses deux versions se valent —
retenir `community-1`, qui est le pipeline courant.

**Reste un curseur, et c'est au mainteneur de le poser** : `large-v3-turbo`
(31,5 % de WER, 41 min/h, 3,66 Go) ou `small` (36,0 %, 17 min/h, 3,15 Go). Avec
la diarisation pyannote par-dessus, compter **+65 min/h** dans les deux cas —
c'est elle qui domine le coût, pas l'ASR.

**La combinaison qui n'a toujours pas été mesurée, et qui devrait l'être** :
Whisper pour l'ASR, pyannote pour la diarisation, **notre pilote pour le
collage** — c'est-à-dire WhisperX démonté, avec l'assignation au point milieu à
la place de la sienne. C'est la seule façon connue d'avoir à la fois le texte de
Whisper et le 6/6 de pyannote, que WhisperX manque (5/6) par son assignation. Les
trois briques existent déjà dans le banc.
