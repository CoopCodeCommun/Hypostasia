# SPEC — La transcription audio en local

**Projet** : Hypostasia V3
**Version** : 1.1 — 16 août 2026
**Périmètre** : remplacer l'appel à l'API Mistral Voxtral par une chaîne exécutée
sur nos machines, sans perte de qualité sur du français à plusieurs voix.
**Statut** : **SPÉCIFIÉE, MESURE NON FAITE.** L'état de l'art est établi et sourcé
(§ 3 et § 4), le banc d'essai est écrit et compile (§ 6), mais **aucun chiffre de
performance d'inférence n'a été relevé sur notre matériel**. Tout § 4 vient de
sources publiques — et § 4.4 explique pourquoi elles ne suffisent pas.
**Conventions** : skill `djc`. Le code de banc d'essai des annexes suit les
commentaires bilingues FR/EN comme le reste du projet.

> **Ce document n'est pas un état d'avancement.** Les trois seuls qui en tiennent
> un restent `CHANGELOG/`, `PLAN/PASSATION.md` et la mémoire. Ce qui suit décrit
> un **état cible** et le **protocole** qui permettra d'y trancher. Le § 7 liste
> ce qui reste à faire *avant de pouvoir décider*, pas un reste-à-coder.
> Le chantier lui-même est suivi dans `PLAN/PASSATION.md § 5.4`.

> **Ce n'est pas une cinquième spec canonique.** Les quatre de `README.md`
> décrivent des couches du produit. Celle-ci décrit une brique d'infrastructure
> et un protocole de mesure. Elle n'a pas de maquette pour étalon : son étalon
> est une transcription humaine (§ 5.3).

---

## 0. Ce que cette spec décide

La colonne **fermeté** distingue ce qui est acquis de ce qui reste à confirmer par
la mesure. Le § 4.4 explique pourquoi aucune source publique ne peut clore les
lignes marquées « à confirmer ».

| # | Décision | Fermeté | § |
|---|---|---|---|
| 1 | Le sujet n'est pas « remplacer Whisper » mais **reconstruire deux étages** : ASR *et* diarisation | **acquis** | 2 |
| 2 | **Aucun modèle ASR à poids ouverts ne diarise** — ni Whisper, ni Parakeet, ni les Voxtral ouverts | **acquis** | 3.1 |
| 3 | Le modèle Voxtral qui diarise est **API seule** : la bascule n'est pas un changement d'hébergement | **acquis** | 3.2 |
| 4 | Sur du français, **Parakeet TDT v3 vaut Whisper large-v3** pour ~2,6 fois moins de paramètres | à confirmer | 4.1 |
| 5 | Un **GPU n'apporte presque rien** à cette chaîne : ×1,6 sans TensorRT | à confirmer | 4.3 |
| 6 | Le goulot d'étranglement serait **la diarisation**, pas la transcription | **hypothèse** | 4.2 |
| 7 | Sortformer a un **plafond dur à 4 locuteurs**, inscrit dans la forme du tenseur de sortie | **acquis** | 4.5 |
| 8 | Le motif de la bascule est la **souveraineté**, pas le coût : le point mort est à ~140-240 h/mois | **acquis** | 4.6 |
| 9 | La mesure se fait **en conteneur bridé à 8 vCPU**, sur du français conversationnel réel, contre une **transcription humaine** | **acquis** | 5 |
| 10 | Le **DER n'est pas calculable** avec notre référence : elle n'a pas d'horodatage | **acquis** | 5.4 |

---

## 1. Le problème

Hypostasia transcrit aujourd'hui l'audio importé via l'API Mistral. Le besoin est
du **traitement par lots** : personne n'attend devant l'écran, la latence n'est
pas un critère. La qualité, elle, en est un — une transcription fausse contamine
tout ce qu'on empile dessus, jusqu'à la géométrie du débat.

La question posée est : que coûterait la même chose en local, sur un serveur sans
carte graphique ?

Elle a une réponse simple sur l'ASR et une réponse difficile sur le reste.

---

## 2. L'état actuel, dans le code

`front/services/transcription_audio.py:107` construit l'appel :

```python
parametres_transcription = {
    "model": config_transcription.model_name,   # voxtral-mini-latest
    "diarize": diarisation_activee,             # True
}
```

Deux contraintes de l'API sont déjà encodées dans nos commentaires
(`transcription_audio.py:98-106`) :

- `diarize=True` **exige** `timestamp_granularities=["segment"]` ;
- `language` et `timestamp_granularities` sont **incompatibles** — quand on
  diarise, on ne peut donc pas forcer la langue.

`core/models.py:1085-1092` porte `diarization_enabled` et `max_speakers`
(**défaut : 5**). `core/models.py:1141` porte le tarif : `0,003 $/min`.

**Piège à connaître sur `max_speakers`.** Il traverse `front/tasks.py:623` puis
`transcription_audio.py:52` sous le nom `max_locuteurs`, et **n'est jamais envoyé
à l'API** : il finit uniquement dans un `logger.info` (`transcription_audio.py:80-82`).
Il ne renseigne donc pas sur le comportement actuel de la transcription, mais sur
**l'intention** — on s'attend à des enregistrements allant jusqu'à 5 voix. C'est
à ce titre seulement qu'il pèse sur le § 4.5, et la question posée au mainteneur
(§ 7) reste entière.

**Ce que tout cela implique** : nous ne consommons pas un modèle de transcription,
nous consommons un **service** qui rend en un appel le texte, les horodatages *et*
l'attribution des locuteurs. C'est cette dernière qui n'a pas d'équivalent local
prêt à l'emploi.

---

## 3. Le point dur : la diarisation

### 3.1 Aucun ASR ouvert ne diarise

Whisper, Parakeet, Canary, Granite, et les Voxtral à poids ouverts produisent du
texte et des horodatages. Aucun ne dit *qui* parle. Il faut un second étage, et
c'est probablement lui qui coûtera cher (§ 4.2).

### 3.2 Ce qui est ouvert chez Voxtral, et ce qui ne l'est pas

| Modèle | Diarise ? | Poids | Note |
|---|---|---|---|
| **Voxtral Mini Transcribe 2** — celui que nous appelons | **oui** | **non, API seule** | biais de contexte (100 termes), horodatage au mot, 3 h/requête, 13 langues |
| Voxtral Realtime (`Voxtral-Mini-4B-Realtime-2602`) | **non** | oui, Apache 2.0, 8,87 Go | ~3,4 B LM + 0,6 B encodeur, délai réglable 80 ms → 2,4 s, runtime vLLM |
| Voxtral Mini 3B 2507 | **non** | oui, GGUF Q4_K_M 2,47 Go | mel et tokenizer Tekken embarqués dans le GGUF, zéro Python à l'inférence |

**Conséquence de conception** : « passer Voxtral en local » n'existe pas. Le
modèle qui rend le service que nous utilisons n'a pas de poids publics. Toute
bascule est un **changement d'architecture**, pas un changement d'hébergement.

Et sur CPU les Voxtral cumulent deux handicaps : ce sont des LLM audio
**autorégressifs** — décodage token par token, ce qu'un processeur fait mal — et
ils ne diarisent pas. **Écartés** pour ce besoin.

---

## 4. Les candidats, et ce que disent les sources publiques

> Tous les chiffres de cette section sont **publics, pas mesurés par nous**.
> Le § 4.4 dit pourquoi il faut quand même mesurer.

**Deux unités à ne pas confondre**, employées telles quelles par leurs sources
respectives :

- **RTFx** = durée de l'audio ÷ temps de calcul. **Plus grand = plus rapide.**
  RTFx 36 signifie 36 fois plus vite que le temps réel.
- **RTF** = temps de calcul ÷ durée de l'audio. **Plus petit = plus rapide.**
  RTF 0,12 signifie 12 % du temps réel, soit RTFx 8,3.

### 4.1 Qualité

La colonne « WER français » est la seule comparable verticalement : elle porte
sur un corpus unique (FLEURS FR). La colonne « WER moyen » agrège des corpus
différents, indiqués entre parenthèses — **ne pas la lire comme un classement**.

| Modèle | Taille | WER français (FLEURS) | WER moyen (corpus) | Licence |
|---|---|---|---|---|
| Voxtral Mini Transcribe 2 (notre API) | — | n/d | 5,90 % (FLEURS multilingue) | propriétaire |
| **Parakeet TDT 0.6B v3** (NVIDIA) | 0,6 B | **5,15 %** | 6,32 % (Open ASR Leaderboard) | CC-BY-4.0 |
| Whisper large-v3 | 1,55 B | **5,03 %** | 7,40 % (FLEURS multilingue) | MIT |
| Whisper large-v3 turbo | 809 M | n/d | 7,75 % (FLEURS multilingue) | MIT |
| Canary-Qwen 2.5B | 2,5 B | — (anglais seul) | 5,63 % (Open ASR Leaderboard, EN) | NVIDIA |
| Granite Speech 3.3 8B | 8 B | n/d | 5,85 % (Open ASR Leaderboard) | Apache 2.0 |

**Parakeet v3 fait jeu égal avec Whisper large-v3 en français pour ~2,6 fois moins
de paramètres** (0,6 B contre 1,55 B). Sur nos langues, rien ne justifie de payer
le prix CPU du large-v3.

Deux propriétés de Parakeet comptent pour nous au-delà du WER :

- son décodeur est un **transducteur** qui émet en une passe — d'où l'écart de
  vitesse sur CPU face aux modèles autorégressifs ;
- il peut émettre un symbole *blank* : **le silence donne du vide, pas du texte
  halluciné**. Whisper, lui, boucle sur des phrases fantômes dans les longs
  blancs — défaut coûteux sur un enregistrement de délibération.

Ses limites : 25 langues européennes seulement (contre 99 pour Whisper), et une
longueur d'audio bornée (§ 6.3).

À garder en réserve pour le français : `bofenghuang/whisper-large-v3-french`,
affiné sur plus de 2 500 h.

### 4.2 Coût CPU, et où se trouverait le goulot

Mesures publiées par le dépôt `onnx-asr` pour Parakeet v3 :

| Exécution | RTFx | 1 h d'audio |
|---|---|---|
| **CPU** | **36** | ~1 min 40 |
| GPU T4, ONNX Runtime CUDA | 57 | ~1 min |
| GPU + TensorRT | 320 | ~11 s |

Diarisation, sur les mêmes ordres de grandeur :

| Outil | 1 h d'audio | DER | Limites |
|---|---|---|---|
| pyannote 3.1 (CPU) | ~52 min (RTF 0,86) | ~11,2 % | token HuggingFace obligatoire, conditions à accepter |
| **Diarize** (FoxNoseTech) | **~7 min 12** (RTF 0,12) | 10,8 % annoncé sur le Show HN, **4,8 %** sur le dépôt — écart non expliqué | pas de parole superposée, dégradation au-delà de 7 locuteurs |
| Sortformer v2 (NVIDIA) | **n/d** | 14,76 % DIHARD3-Eval ; 5,85 % CALLHOME 2 loc. | **4 locuteurs maximum**, gère la parole superposée |

**L'hypothèse structurante, et ses deux faiblesses.** À ~1 min 40 pour l'ASR
contre ~7 min 12 pour Diarize, l'étage locuteurs coûterait **plus de quatre fois**
l'étage texte. Mais :

1. le numérateur et le dénominateur viennent de **deux dépôts différents, mesurés
   sur deux machines inconnues** — le CPU du « 36 » n'est même pas précisé (§ 4.4) ;
2. surtout, **la ligne Sortformer est vide**, et c'est Sortformer que le banc
   utilise. Rien n'exclut qu'il soit plus rapide que l'ASR et que le rapport
   s'inverse sur la pile réellement choisie.

C'est donc une hypothèse de travail, pas un résultat. Le banc doit la trancher —
c'est l'un des premiers enseignements qu'on en attend.

### 4.3 Pourquoi un GPU ne résoudrait pas ce problème

Sur Parakeet, un T4 via ONNX Runtime CUDA donne **×1,6** par rapport au CPU. Il
faut TensorRT — donc NVIDIA, plus une compilation propre à la carte — pour le ×9.
Économiser ~40 secondes par heure d'audio ne justifie aucun achat.

Et le GPU n'aiderait pas davantage la diarisation : chez Diarize, seuls le VAD
Silero et les embeddings WeSpeaker sont neuronaux ; le reste (GMM+BIC, clustering
spectral) est du scikit-learn, CPU par nature.

**Corollaire** : si un GPU entre un jour dans l'infrastructure, ce sera pour le
LLM d'extraction (le fork LangExtract), pas pour l'audio. Arbitrage distinct,
critères distincts — la VRAM avant tout.

Ordres de grandeur relevés en août 2026, marché dégradé par la crise mémoire
(sources § 9, à revérifier avant toute décision d'achat) : RTX 5060 Ti 16 Go à
~805 $ neuve (+88 % sur son MSRP) et ~460 $ d'occasion ; RTX 3060 12 Go à
250-275 $ d'occasion, 339 $ neuve rééditée.

Sur le **Framework Laptop 13 Core Ultra Series 1** (Meteor Lake) : l'iGPU Arc
Xe-LPG **n'a pas d'unités XMX** — l'accélération passe par DP4a, ~16 TOPS INT8 ;
le NPU AI Boost fait ~11 TOPS. Ce sont les XMX de Lunar Lake (Series 2, 67 TOPS)
qui font le saut. La pile Linux existe (`intel_vpu`, `intel/linux-npu-driver`,
plugin NPU d'OpenVINO, noyau ≥ 6.6) et `FluidInference/parakeet-tdt-0.6b-v3-ov`
fournit le modèle converti — mais leur propre mesure annonce **1,3× sur PyTorch
en iGPU**. C'est un gain réel de 30 %, simplement trop faible pour justifier
d'installer et de maintenir toute une pile ; l'intérêt véritable de cette voie est
la consommation électrique. **Non prioritaire.**

### 4.4 Pourquoi ces chiffres ne suffisent pas

Trois raisons de tout remesurer :

1. **Aucune source publique ne mesure du français conversationnel à plusieurs
   voix.** Tout est benché sur du LibriSpeech anglais lu, ou sur FLEURS — de la
   parole lue elle aussi. Nos enregistrements sont des délibérations : hésitations,
   chevauchements, prises de parole courtes.
2. Le « 36 RTFx CPU » d'`onnx-asr` **ne précise pas le processeur**.
3. Le domaine est saturé de sites générés qui se recopient (gigagpu.com,
   vram.run, hardwarepedia.com, bestgpuforai.com). Signal d'alarme rencontré :
   l'un annonce « 2 093 tok/s sur RTX 4090 » pour Parakeet — un transducteur n'a
   pas de débit en tokens par seconde. **Ne rien reprendre de ces sources.**

### 4.5 Le plafond de Sortformer est architectural

Sortformer : encodeur NEST/FastConformer 18 couches, Transformer 18 couches
(hidden 192), puis deux couches feedforward à **4 sorties sigmoïdes par frame**.
La sortie est une matrice **T × S avec S = 4, en dur**. Le « Sort » vient du tri
des locuteurs par ordre d'arrivée, appris par une *Sort Loss* combinée à la perte
invariante par permutation.

Une sigmoïde par locuteur — et non un softmax — permet à plusieurs d'être actifs
sur la même frame : **c'est ce qui lui donne la parole superposée**, que Diarize
n'a pas.

Au-delà de 4, il n'y a pas de cinquième sortie. Test rapporté sur 6 locuteurs :
seuls `spk0`–`spk3` sortent. NVIDIA a confirmé dans le ticket NeMo #14546 que
c'est « une limitation attendue de l'architecture, pas un bug ».

**Le mode de panne, et pourquoi il est le pire pour nous** : les voix
surnuméraires ne disparaissent pas du texte — l'ASR est un étage indépendant et
transcrit tout. C'est l'**attribution** qui se perd : les paroles sont absorbées
dans l'un des quatre slots, ou tombent sans étiquette. La sortie reste **propre
et plausible**, sans signal d'erreur exploitable. Sur un corpus où l'on construit
ensuite un « qui a dit quoi », une attribution fausse et silencieuse vaut moins
qu'une erreur visible.

> **Conséquence pour le banc** : le taux de phrases `INCONNU` que produit
> l'annexe E **ne détecte pas** ce dépassement. Il ne monte que dans le cas où
> Sortformer n'attribue aucun locuteur ; dans le cas d'absorption — celui que ce
> paragraphe décrit — il reste bas alors que la sortie est fausse. C'est un
> indicateur **partiel et aveugle au cas qui compte** : ne pas s'y fier, et
> vérifier à l'œil (§ 7.5).

Un clustering se dégrade autrement : pyannote et Diarize *estiment* le nombre de
locuteurs et peuvent sortir n'importe quel entier. Leur erreur est continue et
symétrique — sur- ou sous-segmentation. On peut donc espérer la repérer en
comparant le compte annoncé au compte réel, mais **cette détectabilité reste une
hypothèse : le protocole ci-dessous ne la met pas à l'épreuve.**

**Notre `max_speakers` par défaut est 5** — soit une voix de plus que le plafond,
avec la réserve du § 2 sur ce que ce champ signifie réellement.

Trois sorties si 4 ne suffit pas :

- **`mago-research/Ultra-Sortformer`** (Apache 2.0) élargit la tête de sortie par
  initialisation orthogonale SVD, avec deux taux d'apprentissage (1e-5 sur les
  poids d'origine, 1e-4 sur les nouvelles lignes). **Checkpoints publiés pour 5
  et 8 locuteurs.** Réserve annoncée par le projet : plus de slots décale le
  comptage sur les extraits courts. Compatibilité avec `parakeet-rs`
  **non vérifiée** — dépend du figeage de la dimension de sortie côté Rust.
  L'annexe E prend le chemin du modèle en argument pour permettre l'essai.
- Le contournement du ticket #14546 : Sortformer pour la segmentation, puis MFCC
  + k-means en ligne pour ré-attribuer au-delà de 4.
- Diarize, sans plafond dur, au prix de la parole superposée.

### 4.6 Le calcul économique

0,003 $/min = **0,18 $/h d'audio**. Un VPS 8 vCPU / 16 Go coûte 25-40 €/mois, soit
environ **27-43 $** au change d'août 2026 (~1,08 $/€). Point mort :
27 / 0,18 ≈ **150 h** dans l'hypothèse basse, 43 / 0,18 ≈ **240 h** dans la haute.
Sans conversion, la fourchette serait 139-222 h. Retenir **~140-240 h d'audio par
mois** : en dessous, le local coûte plus cher que l'API.

**Le motif de la bascule n'est donc pas l'argent, c'est la souveraineté sur des
délibérations** — ce qui cadre avec ce que porte le projet par ailleurs.

---

## 5. Le protocole de mesure

### 5.1 Matériel de référence, et son bridage

Framework Laptop 13, **Intel Core Ultra 7 155H**, 22 threads, 30 Go de RAM
(≈20 Go disponibles), Docker 29.6.2. **CPU uniquement.**

**Le conteneur doit être bridé à 8 vCPU** (`--cpus=8`). Sans cela, le RTFx mesuré
sur 22 threads ne répondrait pas à la question posée : le § 4.6 raisonne sur un
VPS 8 vCPU, et c'est ce gabarit-là que le critère § 8.3 doit trancher. Mesurer
aussi sans bridage est utile — mais comme un second point, pas comme le principal.

### 5.2 Contrainte d'exécution

**Tout se passe en conteneur, rien sur l'hôte.** Le dossier de travail est monté
en volume ; l'hôte ne sert qu'à porter les fichiers.

### 5.3 Le matériau et son étalon

**« Libre à vous ! » n° 282 du 7 juillet 2026**, radio Cause Commune, sujet
principal « Tactic, une ASBL Tip Top ».

Pourquoi celui-là :

- **licence libre** — Art Libre 1.3+, CC BY-SA 2.0+ ou GFDL 1.3+ ;
- du **français conversationnel réel**, pas de la parole lue ;
- **exactement 4 intervenants** — Étienne Gonnu, Laurent Costy, Célo, HgO — donc
  pile au plafond de Sortformer, ce qui teste la limite sans la franchir ;
- surtout : **une transcription humaine publiée**, qui sert de vérité terrain
  pour le texte *et* pour l'attribution.

```
audio : https://media.april.org/audio/radio-cause-commune/libre-a-vous/
        emissions/20260707/libre-a-vous-20260707-tactic-asbl.ogg
texte : https://www.librealire.org/
        emission-libre-a-vous-diffusee-mardi-7-juillet-2026-sur-radio-cause-commune
```

Trois pièges de ce matériau, traités dans les scripts :

1. La page de transcription couvre **toute l'émission**, chroniques comprises. Le
   sujet Tactic commence au **tour 10** de `reference.json` — établi en lisant la
   page, **pas encore vérifié contre l'audio** : le fichier `tactic-asbl.ogg`
   peut commencer à l'annonce du sujet (tour 10) ou directement à la prise de
   parole de Laurent Costy (tour 11). C'est l'objet du § 7.3, et un décalage d'un
   tour fausse le WER.
2. **« Célo » est orthographié de deux façons** dans la page — « Célo » (22 tours)
   et « Celo » (5 tours). Sans fusion, on compte 5 locuteurs au lieu de 4.
3. Le sujet principal dépasse largement 20 min ; on en extrait une tranche
   (900 s par défaut) et on aligne sur le début.

### 5.4 Ce qu'on mesure, ce qu'on ne peut pas mesurer, et les biais connus

| Grandeur | Comment | Statut |
|---|---|---|
| RTFx de la diarisation | chrono autour de `sortformer.diarize()` | mesurable |
| RTFx de la transcription | chrono cumulé sur les morceaux | mesurable |
| Temps de chargement des modèles | chronométré **à part** de l'inférence | mesurable |
| Pic mémoire réel | `/usr/bin/time -v`, ligne *Maximum resident set size* | mesurable |
| WER | alignement semi-global mot à mot contre la référence humaine | mesurable, **biaisé optimiste** |
| Nombre de locuteurs détectés | sortie de Sortformer contre les 4 réels | mesurable |
| Répartition du temps de parole | par locuteur, sur la portion de référence réellement alignée | approché |
| **DER** | — | **NON calculable** |

**Pourquoi pas de DER** : la transcription de l'April **n'a aucun horodatage**.
Un DER exige un alignement temporel de référence. Un vrai DER supposerait
d'annoter à la main les frontières de tours — travail à décider séparément (§ 7).

**Quatre biais connus**, à rappeler en présentant les résultats :

1. **Le WER semi-global est optimiste.** On retient le point de troncature de la
   référence *qui minimise le WER* : c'est une borne inférieure, pas une
   estimation neutre. Le vrai WER est au moins celui-là.
2. **Les nombres.** « 20 » contre « vingt » compte comme une erreur. Aucune
   normalisation numérique n'est faite.
3. **Le découpage à 240 s coupe le mot qui chevauche chaque frontière** : il est
   transcrit en deux moitiés fausses, recousues par une espace. Sur 900 s, cela
   fait 3 frontières, donc au plus 3 mots abîmés — négligeable devant le total,
   mais réel.
4. **La granularité d'attribution est la phrase**, pas le mot. Une phrase qui
   enjambe un changement de tour est attribuée en bloc à un seul locuteur. C'est
   un choix : `TimestampMode::Sentences` donne des unités lisibles, alignées sur
   ce que la référence humaine découpe. `TimestampMode::Words` existe dans la
   crate et donnerait une attribution plus fine — à essayer en second passage si
   le critère § 8.1 se joue sur les changements de tour.

---

## 6. Le banc monté, et les trois obstacles rencontrés

Le banc est écrit et **compile sans avertissement** — vérifié le 16 août 2026 en
extrayant les annexes B et E de ce fichier même, puis `cargo build --release` dans
l'image de l'annexe A : 45 s sur la machine du § 5.1, dépendances comprises. C'est
une mesure de compilation, pas d'inférence.

Les fichiers sont en annexe : ils vivaient dans un scratchpad temporaire, qui a
été purgé une première fois. D'où leur recopie **intégrale** ici — ce document
doit suffire à tout reconstruire.

### 6.0 L'arborescence attendue

Tout est relatif à `/work` dans le conteneur, monté depuis le dossier de travail
de l'hôte :

```
/work
├── Dockerfile                                  annexe A
├── Cargo.toml                                  annexe B
├── src/main.rs                                 annexe E
├── prepare.sh                                  annexe C
├── run_bench.sh                                annexe D
├── reference.py                                annexe F
├── inspecter_reference.py                      annexe F
├── comparer.py                                 annexe G
├── diar_streaming_sortformer_4spk-v2.onnx      (telecharge)
├── tdt/                                        (telecharge, fp32)
│   ├── encoder-model.onnx
│   ├── encoder-model.onnx.data
│   ├── decoder_joint-model.onnx
│   └── vocab.txt
├── tdt-int8/                                   (telecharge, renomme)
│   ├── encoder-model.onnx
│   ├── decoder_joint-model.onnx
│   └── vocab.txt
├── audio/
│   ├── source.ogg
│   ├── complet.wav                             16 kHz mono 16 bits
│   └── extrait_0_900s.wav                      produit par run_bench.sh
├── reference.json / reference.txt              produits par reference.py
├── resultat_<etiquette>.json                   produits par le bench
├── sortie_<etiquette>.txt
└── mesures_<etiquette>.txt                     /usr/bin/time -v
```

### 6.1 Debian 12 ne peut pas lier ONNX Runtime

Premier essai sur `rust:1-bookworm` : échec d'édition de liens, symboles
indéfinis `__isoc23_strtoull` (glibc ≥ 2.38) et
`std::__cxx11::basic_string<...>::_M_replace_cold` (libstdc++ ≥ 13).

Les binaires ONNX Runtime que la crate `ort` télécharge sont compilés contre une
base plus récente que Debian 12 (glibc 2.36).

**Correctif : `rust:1-trixie`** (Debian 13, glibc 2.41). Compilation en 1 min 27
après `cargo clean`. À ne pas re-découvrir : c'est une heure perdue.

### 6.2 L'exemple officiel du dépôt ne tient pas sur un fichier long

`examples/diarization.rs` de `parakeet-rs` charge tout l'audio et le passe d'un
bloc à TDT. Or le README du même dépôt prévient que **CTC et TDT plafonnent vers
4-5 minutes** et invite à « découper en morceaux ». L'exemple ne suit pas cet
avertissement.

Notre `src/main.rs` en tire la conséquence : Sortformer sur l'intégralité (il est
nativement en streaming), TDT par morceaux de 240 s, **avec report du décalage sur
les horodatages** de chaque morceau — sans quoi l'attribution est fausse dès le
deuxième morceau. Cette répartition des rôles est notre déduction, pas une
prescription littérale du README.

### 6.3 Ce que le loader attend exactement

`ParakeetTDT::from_pretrained(dossier)` cherche, dans un même dossier :
`encoder-model.onnx`, `encoder-model.onnx.data`, `decoder_joint-model.onnx`,
`vocab.txt`. Sortformer prend un **chemin de fichier**, pas un dossier.

Les variantes int8 de `istupakov/parakeet-tdt-0.6b-v3-onnx` s'appellent
`encoder-model.int8.onnx` et `decoder_joint-model.int8.onnx` : **les deux** sont à
renommer dans un dossier séparé, ce que fait `prepare.sh`.
**Non vérifié** : que le loader accepte un encodeur int8 sans fichier `.data`
associé — le fp32 en a un, l'int8 devrait être autonome. **À confirmer au premier
essai.**

Volumétrie : encodeur fp32 ≈ 2,4 Go (`.onnx.data`) + 42 Mo, encodeur int8
≈ 652 Mo, Sortformer v2 quelques dizaines de Mo. C'est le téléchargement du fp32
qui a arrêté la première session.

---

## 7. Ce qui reste à faire

**Avant de pouvoir décider** — dans l'ordre :

1. **Télécharger les poids et le matériau** : `bash prepare.sh`. Puis
   **extraire la référence humaine** : `python3 reference.py`, qui produit
   `reference.json`. Attendu : **131 tours**, dont Laurent Costy (43), HgO (32),
   Célo (22), Étienne Gonnu (17) pour le sujet Tactic — plus « Celo » (5), le même
   intervenant mal orthographié, et les chroniqueurs hors sujet. **Un compte
   différent signale que la page a changé** : la figer par une copie locale.
2. **Lancer le banc en fp32, bridé à 8 vCPU** :
   `bash run_bench.sh 900 0 ./tdt fp32 240`.
3. **Vérifier que la variante int8 charge** (§ 6.3). Si oui, la mesurer :
   `bash run_bench.sh 900 0 ./tdt-int8 int8 240`. C'est **elle** qui décide pour
   un serveur CPU, pas le fp32.
4. **Contrôler le point de départ de l'audio** (§ 5.3, piège 1) : le fichier
   commence-t-il au tour 10 ou au tour 11 ? Comparer les premières phrases de
   `sortie_fp32.txt` à `reference.txt`, puis ajuster le troisième argument de
   `comparer.py`.
5. **Comparer** : `python3 comparer.py resultat_int8.json reference.json 10`.
   Consigner WER, nombre de locuteurs détectés, répartition de la parole et pic
   RSS **dans un fichier `CHANGELOG/AAAA-MM-JJ-transcription-locale.md`** — c'est
   le seul endroit prévu pour un résultat daté.
6. **Produire la base de comparaison Voxtral.** Le critère § 8.2 exige le WER de
   l'API *sur le même extrait*, et rien ne le fournit aujourd'hui. Il faut
   transcrire `audio/extrait_0_900s.wav` via `transcrire_audio_via_voxtral()`,
   convertir sa sortie au format de `resultat_*.json` (`texte_brut` et `segments`
   suffisent) et la passer dans le même `comparer.py`. **Sans cette étape, le
   critère 2 est indécidable** — et l'appel est facturé, donc à faire une fois.
7. **Lire à la main 3 ou 4 changements de tour** dans `resultat_*.json`. Le WER ne
   dit rien de la qualité d'attribution ; l'œil, si. Et le taux d'`INCONNU` est
   aveugle au cas qui compte (§ 4.5).
8. **Éprouver le plafond des 4** : chercher un enregistrement à 5 ou 6 voix et
   vérifier que la sortie reste plausible alors qu'elle est fausse. C'est le test
   qui compte le plus pour nous.

**Ensuite, les autres solutions à comparer** :

- **`istupakov/onnx-asr` + `FoxNoseTech/diarize`** en Python — la voie la plus
  proche de notre pile. Le collage manque (alignement RTTM ↔ horodatages), il
  est de l'ordre de la centaine de lignes, et `construire_html_diarise()`
  (`transcription_audio.py:271`) attend déjà cette forme de données :
  une liste de `{speaker, start, end, text}`.
- **`loudpage/parakeet-v3-diarized`** — Parakeet v3 + pyannote derrière une API
  compatible Whisper, sorties VTT. Le prêt-à-l'emploi : à mesurer pour la
  qualité de bout en bout, en acceptant la lenteur de pyannote et le token HF.
- **`achetronic/parakeet`** — serveur Go, API compatible Whisper, sortie VTT,
  Docker fourni. Pas de diarisation, mais sa sortie VTT entrerait dans le backend
  WebVTT de Docling — **que le projet embarque sans l'exploiter aujourd'hui** :
  aucun chemin de code n'ingère de VTT (vérifié), la seule trace est l'essai
  ponctuel mentionné dans `SPEC-ancrage-par-element-v2.md:682`.
- **Ultra-Sortformer 5 ou 8 locuteurs** si le plafond de 4 se révèle bloquant.

**Décisions qui attendent le mainteneur** — reprises dans `PLAN/PASSATION.md § 6` :

- **Combien de voix dans les enregistrements réels ?** Toute l'architecture en
  dépend, et c'est la seule question qui commande les autres.
- **Faut-il un DER ?** S'il le faut, il faut annoter à la main les frontières de
  tours sur un extrait. À arbitrer avant de s'engager.
- **Où ranger le banc d'essai** — il n'existe aujourd'hui que dans ces annexes.

**Non fait, et volontairement** : la voie OpenVINO/NPU sur Meteor Lake (§ 4.3).

---

## 8. Les critères de la décision

Dans cet ordre, le premier qui échoue disqualifie :

1. **L'attribution des locuteurs est-elle juste** sur un extrait à 4 voix, et
   **échoue-t-elle visiblement** au-delà ? Une erreur silencieuse est
   disqualifiante — c'est ce qui contamine la suite de la chaîne.
2. **Le WER français** tient-il la comparaison avec ce que rend Voxtral
   aujourd'hui, sur le même extrait ? (base à produire, § 7.6)
3. **Le coût CPU sur 8 vCPU** tient-il dans une file Celery aux côtés du reste ?
4. **La pile est-elle installable sans friction** : pas de token HuggingFace, pas
   de compilation exotique, une image Docker qui se reconstruit.

Le point 4 n'est pas cosmétique : `bin/install.sh` doit rester idempotent, et un
token à accepter à la main sur un site tiers casse cette propriété.

---

## Annexe A — `Dockerfile`

```dockerfile
# Banc d'essai ASR local : Parakeet TDT v3 (ONNX) + Sortformer v2, CPU uniquement
# / Local ASR benchmark: Parakeet TDT v3 (ONNX) + Sortformer v2, CPU only

# Debian 13 (trixie) et pas 12 : les binaires ONNX Runtime telecharges par la crate `ort`
# reclament glibc >= 2.38 (__isoc23_strtoull) et libstdc++ >= 13 (_M_replace_cold).
# Sur bookworm, l'edition de liens echoue avec des symboles indefinis.
# / Debian 13 (trixie), not 12: the ONNX Runtime binaries fetched by the `ort` crate
# require glibc >= 2.38 and libstdc++ >= 13. On bookworm, linking fails.
FROM rust:1-trixie

# ffmpeg pour la conversion audio, time pour mesurer la RAM reellement consommee
# / ffmpeg for audio conversion, time to measure actual peak RAM
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl time python3 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENV CARGO_TERM_COLOR=never
```

Mise en route. **Le `--cpus=8` n'est pas optionnel** : c'est le gabarit sur lequel
porte la décision (§ 5.1).

```bash
docker build -t bench-asr:2 .
docker run -d --name bench-asr2 --cpus=8 -v "$PWD":/work -w /work \
    bench-asr:2 sleep infinity
docker exec bench-asr2 bash -c 'cd /work && cargo build --release'
```

## Annexe B — `Cargo.toml`

Les versions sont **épinglées** : `rust:1-trixie` et `parakeet-rs = "0.3"` sont des
étiquettes mobiles, et « le banc compile » doit rester vrai dans trois mois.
Conserver le `Cargo.lock` produit au premier build.

```toml
[package]
name = "bench"
version = "0.1.0"
edition = "2021"

[dependencies]
# La feature sortformer n'est pas activee par defaut / sortformer feature is off by default
# Version figee : 0.3.7 est celle qui a compile / pinned: 0.3.7 is the version that compiled
parakeet-rs = { version = "=0.3.7", features = ["sortformer"] }
hound = "3.5"

[profile.release]
opt-level = 3
```

## Annexe C — `prepare.sh`

`curl -f` est **indispensable** : sans lui, un 404 HuggingFace écrit la page
d'erreur HTML dans `encoder-model.onnx`, et l'échec surgit des minutes plus tard
sous la forme d'un message incompréhensible du loader ONNX.

```bash
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
```

## Annexe D — `run_bench.sh`

Le nom de l'extrait encode **le début et la durée** : sinon, relancer avec un autre
point de départ et la même durée réutiliserait silencieusement l'extrait précédent
(cas de l'étape § 7.8).

```bash
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

# Le debut fait partie du nom : sans lui, un extrait different mais de meme duree
# reutiliserait silencieusement le fichier precedent
# / The offset is part of the name: without it, a different extract of the same
# length would silently reuse the previous file
EXTRAIT="audio/extrait_${DEBUT_EXTRAIT}_${DUREE_EXTRAIT}s.wav"

if [ ! -f "$EXTRAIT" ]; then
    echo "--- extraction de ${DUREE_EXTRAIT}s a partir de ${DEBUT_EXTRAIT}s ---"
    ffmpeg -y -loglevel error -ss "$DEBUT_EXTRAIT" -t "$DUREE_EXTRAIT" \
        -i audio/complet.wav -ac 1 -ar 16000 -sample_fmt s16 "$EXTRAIT"
fi
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$EXTRAIT"

echo "============================================================"
echo "BANC D'ESSAI — variante : $ETIQUETTE"
echo "vCPU visibles dans le conteneur : $(nproc)"
echo "============================================================"

# /usr/bin/time -v donne le pic RSS, ce que `time` du shell ne sait pas faire
# / /usr/bin/time -v gives peak RSS, which the shell builtin cannot
/usr/bin/time -v ./target/release/bench \
    "$EXTRAIT" "$DOSSIER_MODELE" "$CHUNK_SECONDES" "resultat_${ETIQUETTE}.json" \
    "$MODELE_SORTFORMER" \
    2> "mesures_${ETIQUETTE}.txt" | tee "sortie_${ETIQUETTE}.txt"

echo
echo "--- ressources (extrait de /usr/bin/time -v) ---"
grep -E "Maximum resident|Elapsed .wall|User time|System time|Percent of CPU" "mesures_${ETIQUETTE}.txt" || true
```

## Annexe E — `src/main.rs`

Trois passages portent le sens : Sortformer tourne sur l'audio **entier** (il est
nativement en streaming), TDT est **découpé** avec **report du décalage** sur les
horodatages, et l'attribution se fait par recouvrement temporel **cumulé par
locuteur**.

Trois pièges à ne pas re-découvrir :

1. `segment.start` et `segment.end` de Sortformer sont en **échantillons**, pas en
   secondes.
2. Sans report du décalage, l'attribution est fausse dès le deuxième morceau.
3. **Le recouvrement doit être cumulé par locuteur, pas comparé segment par
   segment.** Sortformer hache la parole en segments courts : prendre le maximum
   unitaire donnerait une phrase au locuteur d'un seul long segment plutôt qu'à
   celui de quatre courts qui totalisent davantage. C'est le défaut que porte
   l'exemple officiel du dépôt.

```rust
/*
Banc d'essai : Parakeet TDT v3 (transcription) + Sortformer v2 (diarisation), CPU uniquement.
/ Benchmark: Parakeet TDT v3 (transcription) + Sortformer v2 (diarization), CPU only.

Difference avec examples/diarization.rs du depot :
  1. cet exemple DECOUPE l'audio pour TDT (le README previent que TDT plafonne
     autour de 4-5 minutes ; l'exemple officiel ne gere pas ce cas) ;
  2. l'attribution cumule le recouvrement PAR LOCUTEUR au lieu de comparer
     segment par segment.
Sortformer, lui, tourne sur l'integralite de l'audio d'un seul tenant puisqu'il
est nativement en streaming.
/ Differences with the repo's examples/diarization.rs: (1) this one CHUNKS the audio
for TDT; (2) attribution sums overlap PER SPEAKER instead of comparing segment by
segment. Sortformer runs on the whole audio at once since it is natively streaming.

Usage: bench <audio.wav> <dossier_tdt> <secondes_par_chunk> <sortie.json> [modele_sortformer]
*/

use parakeet_rs::sortformer::{DiarizationConfig, Sortformer};
use parakeet_rs::{ParakeetTDT, TimestampMode, Transcriber};
use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::Write;
use std::time::Instant;

const TAUX_ECHANTILLONNAGE: u32 = 16_000;

/// Un morceau de transcription attribue a un locuteur
/// / A transcript chunk attributed to a speaker
struct SegmentAttribue {
    debut: f32,
    fin: f32,
    locuteur: String,
    texte: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let arguments: Vec<String> = env::args().collect();
    let chemin_audio = arguments.get(1)
        .expect("usage: bench <audio.wav> <dossier_tdt> <sec_par_chunk> <sortie.json> [sortformer.onnx]");
    let dossier_tdt = arguments.get(2).expect("dossier du modele TDT manquant");
    let secondes_par_chunk: f32 = arguments
        .get(3)
        .map(|valeur| valeur.parse().expect("le 3e argument doit etre un nombre de secondes"))
        .unwrap_or(240.0);
    let chemin_sortie = arguments.get(4).map(|s| s.as_str()).unwrap_or("resultat.json");
    // Passe en argument pour permettre d'essayer Ultra-Sortformer 5 ou 8 locuteurs
    // / Passed as an argument so Ultra-Sortformer 5/8-speaker can be tried
    let modele_sortformer = arguments
        .get(5)
        .map(|s| s.as_str())
        .unwrap_or("diar_streaming_sortformer_4spk-v2.onnx");

    // ---------- Lecture de l'audio / Read the audio ----------
    let mut lecteur = hound::WavReader::open(chemin_audio)?;
    let specification = lecteur.spec();

    // Le reste du programme suppose 16 kHz mono : le decoupage, le decalage et la
    // conversion des bornes de Sortformer utilisent la constante, pas l'en-tete du
    // fichier. Un WAV 44,1 kHz ou stereo donnerait des horodatages faux EN SILENCE.
    // / The rest assumes 16 kHz mono: chunking, offsets and Sortformer bounds use the
    // constant, not the file header. Another rate or channel count would be silently wrong.
    assert_eq!(
        specification.sample_rate, TAUX_ECHANTILLONNAGE,
        "audio attendu en 16 kHz — convertir avec ffmpeg -ar 16000"
    );
    assert_eq!(
        specification.channels, 1,
        "audio attendu en mono — convertir avec ffmpeg -ac 1"
    );

    let echantillons: Vec<f32> = match specification.sample_format {
        hound::SampleFormat::Float => lecteur.samples::<f32>().collect::<Result<Vec<_>, _>>()?,
        hound::SampleFormat::Int => lecteur
            .samples::<i16>()
            .map(|s| s.map(|s| s as f32 / 32768.0))
            .collect::<Result<Vec<_>, _>>()?,
    };
    assert!(!echantillons.is_empty(), "le fichier audio est vide");
    let duree_audio_secondes = echantillons.len() as f32 / TAUX_ECHANTILLONNAGE as f32;

    println!("### AUDIO");
    println!("fichier            : {}", chemin_audio);
    println!("echantillons       : {}", echantillons.len());
    println!("duree              : {:.1} s ({:.1} min)", duree_audio_secondes, duree_audio_secondes / 60.0);
    println!("modele TDT         : {}", dossier_tdt);
    println!("modele diarisation : {}", modele_sortformer);
    println!("decoupage TDT      : {:.0} s par morceau", secondes_par_chunk);
    println!();

    // ---------- Etape 1 : diarisation sur l'audio complet ----------
    println!("### ETAPE 1 — DIARISATION (Sortformer v2, audio entier)");
    let chrono_chargement_sortformer = Instant::now();
    // Prereglage callhome : c'est celui de l'exemple officiel. La crate offre aussi
    // dihard3(). CALLHOME est un corpus telephonique a deux voix, notre materiau est
    // une table ronde a quatre : essayer les deux si les resultats decoivent.
    // / callhome preset: the one from the official example. dihard3() also exists.
    let mut sortformer = Sortformer::with_config(
        modele_sortformer,
        None,
        DiarizationConfig::callhome(),
    )?;
    let temps_chargement_sortformer = chrono_chargement_sortformer.elapsed().as_secs_f32();
    println!("chargement modele  : {:.2} s", temps_chargement_sortformer);
    println!(
        "config             : chunk_len={} fifo_len={} spkcache_len={} right_context={} (latence {:.2} s)",
        sortformer.chunk_len, sortformer.fifo_len, sortformer.spkcache_len,
        sortformer.right_context, sortformer.latency()
    );

    let chrono_diarisation = Instant::now();
    let segments_locuteurs = sortformer.diarize(
        echantillons.clone(),
        specification.sample_rate,
        specification.channels,
    )?;
    let temps_diarisation = chrono_diarisation.elapsed().as_secs_f32();

    // Compte des locuteurs distincts et du temps de parole de chacun
    // / Count distinct speakers and each one's speaking time
    let mut identifiants_locuteurs: Vec<usize> = segments_locuteurs.iter().map(|s| s.speaker_id).collect();
    identifiants_locuteurs.sort_unstable();
    identifiants_locuteurs.dedup();

    println!("inference          : {:.2} s", temps_diarisation);
    println!("RTFx               : {:.1}x le temps reel", duree_audio_secondes / temps_diarisation);
    println!("segments trouves   : {}", segments_locuteurs.len());
    println!("locuteurs distincts: {} -> {:?}", identifiants_locuteurs.len(), identifiants_locuteurs);

    for identifiant in &identifiants_locuteurs {
        let temps_de_parole: f64 = segments_locuteurs
            .iter()
            .filter(|s| s.speaker_id == *identifiant)
            .map(|s| (s.end - s.start) as f64 / TAUX_ECHANTILLONNAGE as f64)
            .sum();
        let nombre_de_tours = segments_locuteurs.iter().filter(|s| s.speaker_id == *identifiant).count();
        println!(
            "  locuteur {} : {:.1} s de parole ({:.1} %), {} tours",
            identifiant, temps_de_parole,
            100.0 * temps_de_parole / duree_audio_secondes as f64,
            nombre_de_tours
        );
    }
    println!();

    // ---------- Etape 2 : transcription par morceaux ----------
    println!("### ETAPE 2 — TRANSCRIPTION (Parakeet TDT v3, par morceaux)");
    let chrono_chargement_tdt = Instant::now();
    let mut parakeet = ParakeetTDT::from_pretrained(dossier_tdt, None)?;
    let temps_chargement_tdt = chrono_chargement_tdt.elapsed().as_secs_f32();
    println!("chargement modele  : {:.2} s", temps_chargement_tdt);

    let echantillons_par_chunk = (secondes_par_chunk * TAUX_ECHANTILLONNAGE as f32) as usize;
    let nombre_de_chunks = echantillons.len().div_ceil(echantillons_par_chunk);
    println!("morceaux a traiter : {}", nombre_de_chunks);

    let chrono_transcription = Instant::now();
    let mut phrases_horodatees: Vec<(f32, f32, String)> = Vec::new();
    let mut texte_complet = String::new();

    for (indice, morceau) in echantillons.chunks(echantillons_par_chunk).enumerate() {
        // Decalage a rajouter aux horodatages, qui sont relatifs au morceau
        // / Offset to add to timestamps, which are relative to the chunk
        let decalage_secondes = (indice * echantillons_par_chunk) as f32 / TAUX_ECHANTILLONNAGE as f32;
        let chrono_morceau = Instant::now();

        match parakeet.transcribe_samples(
            morceau.to_vec(),
            specification.sample_rate,
            specification.channels,
            Some(TimestampMode::Sentences),
        ) {
            Ok(resultat) => {
                let duree_morceau = morceau.len() as f32 / TAUX_ECHANTILLONNAGE as f32;
                let temps_morceau = chrono_morceau.elapsed().as_secs_f32();
                println!(
                    "  morceau {}/{} ({:.0} s d'audio) : {:.2} s -> {:.1}x, {} phrases",
                    indice + 1, nombre_de_chunks, duree_morceau,
                    temps_morceau, duree_morceau / temps_morceau,
                    resultat.tokens.len()
                );
                if !texte_complet.is_empty() {
                    texte_complet.push(' ');
                }
                texte_complet.push_str(resultat.text.trim());
                for phrase in resultat.tokens {
                    phrases_horodatees.push((
                        phrase.start + decalage_secondes,
                        phrase.end + decalage_secondes,
                        phrase.text,
                    ));
                }
            }
            Err(erreur) => {
                println!("  morceau {}/{} : ECHEC — {}", indice + 1, nombre_de_chunks, erreur);
            }
        }
    }
    let temps_transcription = chrono_transcription.elapsed().as_secs_f32();
    println!("inference totale   : {:.2} s", temps_transcription);
    println!("RTFx               : {:.1}x le temps reel", duree_audio_secondes / temps_transcription);
    println!("phrases obtenues   : {}", phrases_horodatees.len());
    println!("caracteres         : {}", texte_complet.len());
    println!();

    // ---------- Etape 3 : attribution par recouvrement cumule ----------
    println!("### ETAPE 3 — ATTRIBUTION (recouvrement temporel cumule par locuteur)");
    let mut segments_attribues: Vec<SegmentAttribue> = Vec::new();
    let mut phrases_sans_locuteur = 0usize;

    for (debut, fin, texte) in &phrases_horodatees {
        // On SOMME le recouvrement par locuteur au lieu de prendre le meilleur segment :
        // Sortformer hache la parole, et quatre segments courts d'un meme locuteur
        // doivent l'emporter sur un seul long segment d'un autre.
        // / We SUM overlap per speaker instead of taking the single best segment.
        let mut recouvrement_par_locuteur: HashMap<usize, f32> = HashMap::new();
        for segment in &segments_locuteurs {
            let segment_debut = segment.start as f32 / TAUX_ECHANTILLONNAGE as f32;
            let segment_fin = segment.end as f32 / TAUX_ECHANTILLONNAGE as f32;
            let recouvrement = (fin.min(segment_fin) - debut.max(segment_debut)).max(0.0);
            if recouvrement > 0.0 {
                *recouvrement_par_locuteur.entry(segment.speaker_id).or_insert(0.0) += recouvrement;
            }
        }

        // En cas d'egalite parfaite, on prend le plus petit identifiant pour rester
        // deterministe d'une execution a l'autre (l'ordre d'un HashMap ne l'est pas).
        // / On an exact tie, take the lowest id to stay deterministic across runs.
        let locuteur = recouvrement_par_locuteur
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap().then(b.0.cmp(a.0)))
            .map(|(identifiant, _)| format!("locuteur_{}", identifiant));

        if locuteur.is_none() {
            phrases_sans_locuteur += 1;
        }
        segments_attribues.push(SegmentAttribue {
            debut: *debut,
            fin: *fin,
            locuteur: locuteur.unwrap_or_else(|| "INCONNU".to_string()),
            texte: texte.clone(),
        });
    }

    println!("phrases attribuees : {}", segments_attribues.len() - phrases_sans_locuteur);
    println!("phrases INCONNU    : {} ({:.1} %)",
        phrases_sans_locuteur,
        100.0 * phrases_sans_locuteur as f32 / segments_attribues.len().max(1) as f32);
    println!("  ATTENTION : ce taux ne detecte PAS le depassement des 4 locuteurs.");
    println!("  Les voix surnumeraires sont ABSORBEES dans les slots existants (cf. spec 4.5).");
    println!();

    // ---------- Bilan ----------
    let temps_total_inference = temps_diarisation + temps_transcription;
    println!("### BILAN");
    println!("duree audio            : {:.1} s", duree_audio_secondes);
    println!("chargement des modeles : {:.2} s (hors mesure d'inference)", temps_chargement_sortformer + temps_chargement_tdt);
    println!("diarisation            : {:.2} s", temps_diarisation);
    println!("transcription          : {:.2} s", temps_transcription);
    println!("inference totale       : {:.2} s", temps_total_inference);
    println!("RTFx global            : {:.1}x le temps reel", duree_audio_secondes / temps_total_inference);
    println!("=> pour 1 h d'audio    : {:.1} min de calcul", temps_total_inference / duree_audio_secondes * 60.0);

    // ---------- Ecriture du resultat ----------
    let mut fichier = File::create(chemin_sortie)?;
    writeln!(fichier, "{{")?;
    writeln!(fichier, "  \"duree_audio_s\": {:.2},", duree_audio_secondes)?;
    writeln!(fichier, "  \"chargement_sortformer_s\": {:.2},", temps_chargement_sortformer)?;
    writeln!(fichier, "  \"chargement_tdt_s\": {:.2},", temps_chargement_tdt)?;
    writeln!(fichier, "  \"diarisation_s\": {:.2},", temps_diarisation)?;
    writeln!(fichier, "  \"transcription_s\": {:.2},", temps_transcription)?;
    writeln!(fichier, "  \"locuteurs_detectes\": {},", identifiants_locuteurs.len())?;
    writeln!(fichier, "  \"phrases_inconnu\": {},", phrases_sans_locuteur)?;
    writeln!(fichier, "  \"texte_brut\": {},", echapper_json(&texte_complet))?;
    writeln!(fichier, "  \"segments\": [")?;
    for (indice, segment) in segments_attribues.iter().enumerate() {
        writeln!(
            fichier,
            "    {{\"debut\": {:.2}, \"fin\": {:.2}, \"locuteur\": \"{}\", \"texte\": {}}}{}",
            segment.debut, segment.fin, segment.locuteur,
            echapper_json(&segment.texte),
            if indice + 1 == segments_attribues.len() { "" } else { "," }
        )?;
    }
    writeln!(fichier, "  ]")?;
    writeln!(fichier, "}}")?;
    println!("\nresultat ecrit dans {}", chemin_sortie);

    Ok(())
}

/// Echappe une chaine pour l'inserer telle quelle dans du JSON
/// / Escapes a string so it can be inserted as-is into JSON
fn echapper_json(chaine: &str) -> String {
    let mut sortie = String::with_capacity(chaine.len() + 2);
    sortie.push('"');
    for caractere in chaine.chars() {
        match caractere {
            '"' => sortie.push_str("\\\""),
            '\\' => sortie.push_str("\\\\"),
            '\n' => sortie.push_str("\\n"),
            '\r' => sortie.push_str("\\r"),
            '\t' => sortie.push_str("\\t"),
            c if (c as u32) < 0x20 => sortie.push_str(&format!("\\u{:04x}", c as u32)),
            c => sortie.push(c),
        }
    }
    sortie.push('"');
    sortie
}
```

## Annexe F — `reference.py`

Récupère la transcription humaine avec `html.parser` de la bibliothèque standard
— aucune dépendance à installer. Les tours de parole sont marqués par un **nom en
gras suivi de deux-points** ; un candidat est retenu s'il fait 40 caractères ou
moins, ce qui écarte les phrases en gras. Sorties : `reference.json` et
`reference.txt`.

**Fragilité assumée** : le deux-points doit être *à l'intérieur* du gras
(`<strong>Nom :</strong>`), ce qui est le balisage actuel de librealire. Si la
page change, le script rendra zéro tour — d'où le compte attendu au § 7.1, qui
sert de détecteur.

```python
#!/usr/bin/env python3
"""
Extrait la transcription humaine de reference depuis librealire.org.
/ Extracts the human reference transcript from librealire.org.

Les tours de parole y sont marques par un nom en gras suivi de deux-points.
/ Speaker turns are marked there by a bold name followed by a colon.
"""
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser

URL = sys.argv[1] if len(sys.argv) > 1 else (
    "https://www.librealire.org/"
    "emission-libre-a-vous-diffusee-mardi-7-juillet-2026-sur-radio-cause-commune"
)
SORTIE = sys.argv[2] if len(sys.argv) > 2 else "reference"

IGNORER = {"script", "style", "head", "nav", "footer"}


class ExtracteurDeTours(HTMLParser):
    """
    Reconstruit le flux texte en marquant ce qui etait en gras.
    / Rebuilds the text stream, flagging what was bold.
    """

    def __init__(self):
        super().__init__()
        self.morceaux = []          # liste de (en_gras, texte)
        self.profondeur_gras = 0
        self.balise_ignoree = 0

    def handle_starttag(self, tag, attrs):
        if tag in IGNORER:
            self.balise_ignoree += 1
        elif tag in ("strong", "b"):
            self.profondeur_gras += 1
        elif tag in ("p", "div", "br", "li"):
            self.morceaux.append((False, "\n"))

    def handle_endtag(self, tag):
        if tag in IGNORER:
            self.balise_ignoree = max(0, self.balise_ignoree - 1)
        elif tag in ("strong", "b"):
            self.profondeur_gras = max(0, self.profondeur_gras - 1)

    def handle_data(self, data):
        if self.balise_ignoree:
            return
        self.morceaux.append((self.profondeur_gras > 0, data))


def recuperer(url):
    """
    Telecharge la page et la decode. / Downloads the page and decodes it.
    """
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bench-asr)"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        brut = reponse.read()
    try:
        return brut.decode("utf-8")
    except UnicodeDecodeError:
        # Repli si la page n'est pas en UTF-8 / fallback if the page is not UTF-8
        return brut.decode("latin-1")


def construire_les_tours(morceaux):
    """
    Un tour commence a chaque nom en gras termine par ':'.
    / A turn starts at each bold name ending with ':'.
    """
    tours = []
    locuteur_courant = None
    tampon = []

    for en_gras, texte in morceaux:
        propre = texte.replace("\xa0", " ")
        # Un nom de locuteur : en gras, court, et suivi de deux-points
        # / A speaker name: bold, short, and followed by a colon
        candidat = propre.strip()
        if en_gras and candidat.endswith(":") and 0 < len(candidat) <= 40:
            if locuteur_courant is not None:
                tours.append((locuteur_courant, " ".join(tampon)))
            locuteur_courant = candidat.rstrip(":").strip()
            tampon = []
        elif locuteur_courant is not None:
            tampon.append(propre)

    if locuteur_courant is not None:
        tours.append((locuteur_courant, " ".join(tampon)))

    nettoyes = []
    for locuteur, corps in tours:
        corps = re.sub(r"\s+", " ", corps).strip()
        if corps:
            nettoyes.append({"locuteur": locuteur, "texte": corps})
    return nettoyes


def main():
    print(f"recuperation : {URL}")
    html = recuperer(URL)
    print(f"  page recue : {len(html)} caracteres")

    extracteur = ExtracteurDeTours()
    extracteur.feed(html)
    tours = construire_les_tours(extracteur.morceaux)

    if not tours:
        print("  AUCUN TOUR DETECTE — le balisage de la page a probablement change.")
        print("  Verifier que les noms sont bien dans un <strong> avec le ':' a l'interieur.")
        sys.exit(1)

    print(f"  tours de parole detectes : {len(tours)}  (attendu : 131)")
    compteur = {}
    for tour in tours:
        compteur[tour["locuteur"]] = compteur.get(tour["locuteur"], 0) + 1
    print("  locuteurs :")
    for nom, nombre in sorted(compteur.items(), key=lambda x: -x[1]):
        mots = sum(len(t["texte"].split()) for t in tours if t["locuteur"] == nom)
        print(f"    {nom!r} : {nombre} tours, {mots} mots")

    with open(f"{SORTIE}.json", "w", encoding="utf-8") as fichier:
        json.dump(tours, fichier, ensure_ascii=False, indent=1)
    with open(f"{SORTIE}.txt", "w", encoding="utf-8") as fichier:
        for tour in tours:
            fichier.write(f"{tour['locuteur']} : {tour['texte']}\n\n")

    print(f"  ecrit : {SORTIE}.json et {SORTIE}.txt")


if __name__ == "__main__":
    main()
```

Un utilitaire d'appoint, `inspecter_reference.py`, affiche les tours numérotés pour
repérer où commence le sujet principal — c'est ainsi qu'on a établi le tour 10 :

```python
#!/usr/bin/env python3
"""
Affiche l'ordre des tours de parole pour reperer les frontieres des segments.
/ Prints turns in order, to locate segment boundaries.
"""
import json

tours = json.load(open("reference.json", encoding="utf-8"))
print(f"{len(tours)} tours au total\n")
print("idx | locuteur               | mots | debut du texte")
print("-" * 100)
for indice, tour in enumerate(tours):
    locuteur = tour["locuteur"][:22]
    nombre_mots = len(tour["texte"].split())
    debut = tour["texte"][:60].replace("\n", " ")
    print(f"{indice:3d} | {locuteur:22s} | {nombre_mots:4d} | {debut}")
```

## Annexe G — `comparer.py`

Calcule le WER par **alignement semi-global** : programmation dynamique classique,
puis minimum du rapport `distance / j` sur la **dernière ligne** au lieu de la
seule dernière cellule — ce qui laisse la fin de la référence libre, puisqu'on ne
transcrit qu'un extrait du début. Le biais optimiste que cela introduit est
documenté au § 5.4.

Il affiche substitutions, omissions et insertions **séparément** : leur répartition
en dit plus que le WER global. Beaucoup d'omissions signalent des passages non
transcrits ; beaucoup d'insertions, des hallucinations.

Deux points de méthode qui changent le résultat :

- **La ponctuation est remplacée par une espace, pas supprimée.** Sinon
  « peut-être » deviendrait `peutêtre`, et l'ASR qui écrit « peut être » se verrait
  compter deux erreurs là où il n'y en a aucune. Le français conversationnel est
  plein de traits d'union : le biais serait plus lourd que celui des nombres.
- **La section LOCUTEURS ne compte que la portion de référence réellement
  alignée.** Sans cette troncature, on comparerait 900 s de machine à tout ce qui
  suit dans la page — le compte de locuteurs et la répartition seraient faux par
  construction.

```python
#!/usr/bin/env python3
"""
Compare la sortie machine a la transcription humaine de reference.
/ Compares machine output against the human reference transcript.

Calcule un WER par alignement semi-global : la reference peut etre tronquee
a la fin sans penalite, puisqu'on ne transcrit qu'un extrait du debut du segment.
/ Computes WER via semi-global alignment: the reference may be truncated at the
end without penalty, since we only transcribe an extract from the segment start.

ATTENTION : la reference n'a PAS d'horodatage, donc aucun DER n'est calculable.
On ne compare que le nombre de locuteurs et la repartition de la parole.
/ NOTE: the reference has NO timestamps, so no DER can be computed.

Usage: comparer.py [resultat_*.json] [reference.json] [tour_de_depart]
"""
import json
import re
import sys
import unicodedata

CHEMIN_HYPOTHESE = sys.argv[1] if len(sys.argv) > 1 else "resultat_fp32.json"
CHEMIN_REFERENCE = sys.argv[2] if len(sys.argv) > 2 else "reference.json"
# La page de reference couvre toute l'emission (chroniques comprises) ; le fichier
# audio ne couvre que le sujet principal. On demarre donc la reference a ce tour-la.
# / The reference page covers the whole show; the audio file only covers the main
# topic, so we start the reference at that turn.
TOUR_DE_DEPART = int(sys.argv[3]) if len(sys.argv) > 3 else 10

# Le meme intervenant est ecrit de deux facons dans la page / same person, two spellings
ALIAS_LOCUTEURS = {"Celo": "Célo"}


def normaliser(texte):
    """
    Minuscules, ponctuation remplacee par une espace, espaces normalises.
    Les accents sont GARDES : c'est du francais, ils portent du sens.
    / Lowercase, punctuation replaced by a space, whitespace normalised.
    Accents are KEPT.
    """
    texte = texte.lower()
    # Les apostrophes typographiques deviennent des apostrophes simples
    # / Typographic apostrophes become plain ones
    texte = texte.replace("’", "'").replace("‘", "'")
    # La ponctuation est REMPLACEE par une espace, jamais supprimee : sinon
    # "peut-etre" deviendrait "peutetre" et ne s'alignerait plus sur "peut etre".
    # / Punctuation is REPLACED by a space, never removed.
    texte = "".join(
        " " if unicodedata.category(caractere).startswith("P") else caractere
        for caractere in texte
    )
    return re.sub(r"\s+", " ", texte).strip()


def mots(texte):
    return normaliser(texte).split()


def wer_semi_global(hypothese, reference):
    """
    Distance d'edition au niveau des mots, fin de reference libre.
    / Word-level edit distance, reference end free.
    Retourne (wer, erreurs, longueur_reference_utilisee, S, D, I).
    """
    n, m = len(hypothese), len(reference)
    if n == 0:
        return 1.0, m, m, 0, m, 0
    if m == 0:
        return 1.0, n, 0, 0, 0, n

    # d[j] pour la ligne courante ; on garde aussi le decompte des operations
    # / d[j] for the current row, plus the per-operation tally
    precedente = list(range(m + 1))
    ops_precedente = [(0, j, 0) for j in range(m + 1)]  # (subs, del, ins)

    for i in range(1, n + 1):
        courante = [i] + [0] * m
        ops_courante = [(0, 0, i)] + [(0, 0, 0)] * m
        for j in range(1, m + 1):
            cout_substitution = 0 if hypothese[i - 1] == reference[j - 1] else 1
            candidat_diag = precedente[j - 1] + cout_substitution
            candidat_suppr = courante[j - 1] + 1      # mot de reference non produit
            candidat_inser = precedente[j] + 1        # mot en trop dans l'hypothese
            meilleur = min(candidat_diag, candidat_suppr, candidat_inser)
            courante[j] = meilleur
            if meilleur == candidat_diag:
                s, d, ins = ops_precedente[j - 1]
                ops_courante[j] = (s + cout_substitution, d, ins)
            elif meilleur == candidat_suppr:
                s, d, ins = ops_courante[j - 1]
                ops_courante[j] = (s, d + 1, ins)
            else:
                s, d, ins = ops_precedente[j]
                ops_courante[j] = (s, d, ins + 1)
        precedente, ops_precedente = courante, ops_courante

    # Fin de reference libre : on prend le j qui minimise le WER, pas la distance brute.
    # La borne basse a n//2 evite de retenir une troncature absurdement courte ; si
    # l'hypothese fait plus du double de la reference, on balaie tout l'intervalle.
    # / Free reference end: pick the j minimising WER. The n//2 floor avoids absurdly
    # short truncations; if the hypothesis is more than twice the reference, scan all.
    borne_basse = min(max(1, n // 2), m)
    meilleur_wer, meilleur_j = None, m
    for j in range(borne_basse, m + 1):
        wer_ici = precedente[j] / j
        if meilleur_wer is None or wer_ici < meilleur_wer:
            meilleur_wer, meilleur_j = wer_ici, j

    s, d, ins = ops_precedente[meilleur_j]
    return meilleur_wer, precedente[meilleur_j], meilleur_j, s, d, ins


def tronquer_les_tours(tours, nombre_de_mots_voulu):
    """
    Ne garde que les tours couvrant les N premiers mots normalises.
    Sans cela, on comparerait 15 min de machine a tout le reste de la page.
    / Keeps only the turns covering the first N normalised words.
    """
    retenus = []
    cumul = 0
    for tour in tours:
        compte = len(mots(tour["texte"]))
        if cumul >= nombre_de_mots_voulu:
            break
        retenus.append(tour)
        cumul += compte
    return retenus


def main():
    with open(CHEMIN_HYPOTHESE, encoding="utf-8") as fichier:
        resultat = json.load(fichier)
    with open(CHEMIN_REFERENCE, encoding="utf-8") as fichier:
        reference = json.load(fichier)

    if TOUR_DE_DEPART >= len(reference):
        print(f"ERREUR : tour de depart {TOUR_DE_DEPART} au-dela des {len(reference)} tours.")
        sys.exit(1)

    reference = reference[TOUR_DE_DEPART:]
    for tour in reference:
        tour["locuteur"] = ALIAS_LOCUTEURS.get(tour["locuteur"], tour["locuteur"])
    print(f"reference demarree au tour {TOUR_DE_DEPART} "
          f"({len(reference)} tours retenus, premier locuteur : {reference[0]['locuteur']})")

    texte_hypothese = resultat["texte_brut"]
    texte_reference = " ".join(tour["texte"] for tour in reference)

    hypothese_mots = mots(texte_hypothese)
    reference_mots = mots(texte_reference)

    print("=" * 78)
    print("COMPARAISON A LA TRANSCRIPTION HUMAINE")
    print("=" * 78)
    print(f"mots produits par la machine : {len(hypothese_mots)}")
    print(f"mots dans la reference       : {len(reference_mots)}")
    print()

    wer, erreurs, longueur_utilisee, subs, dels, inserts = wer_semi_global(
        hypothese_mots, reference_mots
    )
    print(f"reference alignee sur        : {longueur_utilisee} mots "
          f"({100.0 * longueur_utilisee / max(1, len(reference_mots)):.0f} % du total)")
    print(f"erreurs                      : {erreurs}")
    print(f"  substitutions              : {subs}")
    print(f"  omissions                  : {dels}")
    print(f"  insertions                 : {inserts}")
    print()
    print(f"  >>> WER = {100.0 * wer:.2f} %   (borne INFERIEURE, cf. spec 5.4)")
    print()

    print("-" * 78)
    print("LOCUTEURS")
    print("-" * 78)
    # On ne compte que la portion de reference reellement alignee, sinon on
    # comparerait l'extrait transcrit a tout ce qui suit dans la page.
    # / Only count the reference portion actually aligned.
    reference_alignee = tronquer_les_tours(reference, longueur_utilisee)
    print(f"(portion alignee : {len(reference_alignee)} tours sur {len(reference)})")

    locuteurs_reference = {}
    for tour in reference_alignee:
        locuteurs_reference.setdefault(tour["locuteur"], 0)
        locuteurs_reference[tour["locuteur"]] += len(tour["texte"].split())
    print(f"reference : {len(locuteurs_reference)} locuteurs")
    for nom, nombre in sorted(locuteurs_reference.items(), key=lambda x: -x[1]):
        print(f"  {nom} : {nombre} mots")

    compte_machine = {}
    for segment in resultat["segments"]:
        compte_machine.setdefault(segment["locuteur"], 0)
        compte_machine[segment["locuteur"]] += len(segment["texte"].split())
    print(f"\nmachine   : {resultat['locuteurs_detectes']} locuteurs detectes par Sortformer")
    for nom, nombre in sorted(compte_machine.items(), key=lambda x: -x[1]):
        print(f"  {nom} : {nombre} mots")

    print()
    print("NOTE : la reference n'ayant aucun horodatage, le DER n'est pas calculable.")
    print("       Seuls le nombre de locuteurs et la repartition de parole sont comparables.")
    print("       Le taux d'INCONNU ne detecte pas le depassement des 4 locuteurs (spec 4.5).")


if __name__ == "__main__":
    main()
```

---

## 9. Sources

Model cards et dépôts (les seules sources retenues, § 4.4) :

- `nvidia/parakeet-tdt-0.6b-v3` — WER FR 5,15 % sur FLEURS, CC-BY-4.0
- `nvidia/diar_streaming_sortformer_4spk-v2`, `diar_sortformer_4spk-v1`
- *Streaming Sortformer* — arXiv 2507.18446
- ticket NeMo `NVIDIA-NeMo/Speech#14546` — le plafond de 4 est architectural
- `mago-research/Ultra-Sortformer` — checkpoints 5 et 8 locuteurs, Apache 2.0
- `altunenes/parakeet-rs` — MIT OR Apache-2.0, v0.3.7
- `istupakov/onnx-asr` — MIT, tableau RTFx CPU/CUDA/TensorRT
- `istupakov/parakeet-tdt-0.6b-v3-onnx` — poids ONNX, CC-BY-4.0
- `FoxNoseTech/diarize` — Apache 2.0, sans token HF
- `achetronic/parakeet` — serveur Go, API compatible Whisper
- `loudpage/parakeet-v3-diarized` — Parakeet v3 + pyannote
- `FluidInference/parakeet-tdt-0.6b-v3-ov` et `FluidInference/eddy-audio` — la
  voie OpenVINO/NPU et sa mesure « 1,3× sur PyTorch en iGPU »
- Mistral — *Voxtral Transcribe 2*, tarif et diarisation
- TechPowerUp — deep dives Meteor Lake (Xe-LPG sans XMX) et Lunar Lake (XMX)
- BuySellRam, *rapport prix GPU NVIDIA d'août 2026*, et WCCFTech pour la médiane
  de la RTX 5060 Ti 16 Go — ordres de grandeur du § 4.3, à revérifier avant achat

Une synthèse plus large de cette veille est dans la mémoire persistante :
atom *« Transcription audio locale sur CPU en 2026 »* (`66e79a48`).
