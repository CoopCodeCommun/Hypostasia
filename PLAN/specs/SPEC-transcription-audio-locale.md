# SPEC — La transcription audio en local

**Projet** : Hypostasia V3
**Version** : 1.0 — 16 août 2026
**Périmètre** : remplacer l'appel à l'API Mistral Voxtral par une chaîne exécutée
sur nos machines, sans perte de qualité sur du français à plusieurs voix.
**Statut** : **SPÉCIFIÉE, MESURE NON FAITE.** L'état de l'art est établi et
sourcé (§ 3 et § 4), le banc d'essai est écrit et compile (§ 6), mais **aucun
chiffre n'a encore été mesuré sur notre matériel** : la session s'est arrêtée
pendant le téléchargement des poids. Tout § 4 vient de sources publiques, pas de
nos mesures — et § 4.4 explique pourquoi ces sources ne suffisent pas.
**Conventions** : skill `djc`

> **Ce document n'est pas un état d'avancement.** Les trois seuls qui en tiennent
> un restent `CHANGELOG/`, `PLAN/PASSATION.md` et la mémoire. Ce qui suit décrit
> un **état cible** et le **protocole** qui permettra d'y trancher. Le § 7 liste
> ce qui reste à faire *avant de pouvoir décider*, pas un reste-à-coder.

> **Ce n'est pas une cinquième spec canonique.** Les quatre de `README.md`
> décrivent des couches du produit. Celle-ci décrit une brique d'infrastructure
> et un protocole de mesure. Elle n'a pas de maquette pour étalon : son étalon
> est une transcription humaine (§ 5.3).

---

## 0. Ce que cette spec décide

| # | Décision | § |
|---|---|---|
| 1 | Le sujet n'est pas « remplacer Whisper » mais **reconstruire deux étages** : ASR *et* diarisation | 2 |
| 2 | **Aucun modèle ASR à poids ouverts ne diarise** — ni Whisper, ni Parakeet, ni les Voxtral ouverts | 3.1 |
| 3 | Le modèle Voxtral qui diarise est **API seule** : la bascule n'est pas un changement d'hébergement | 3.2 |
| 4 | Sur du français, **Parakeet TDT v3 vaut Whisper large-v3** pour trois fois moins de paramètres | 4.1 |
| 5 | Un **GPU n'apporte presque rien** à cette chaîne : ×1,6 sans TensorRT | 4.3 |
| 6 | Le goulot d'étranglement est **la diarisation**, pas la transcription | 4.2 |
| 7 | Sortformer a un **plafond dur à 4 locuteurs**, inscrit dans la forme du tenseur de sortie | 4.5 |
| 8 | Le motif de la bascule est la **souveraineté**, pas le coût : le point mort est à ~150-200 h/mois | 4.6 |
| 9 | La mesure se fait **en conteneur**, sur du français conversationnel réel, contre une **transcription humaine** | 5 |
| 10 | Le **DER n'est pas calculable** avec notre référence : elle n'a pas d'horodatage | 5.4 |

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

`core/models.py:1085-1091` porte `diarization_enabled` et `max_speakers`
(**défaut : 5**). `core/models.py:1141` porte le tarif : `0,003 $/min`.

**Ce que ça implique** : nous ne consommons pas un modèle de transcription, nous
consommons un **service** qui rend en un appel le texte, les horodatages *et*
l'attribution des locuteurs. C'est cette dernière qui n'a pas d'équivalent local
prêt à l'emploi.

---

## 3. Le point dur : la diarisation

### 3.1 Aucun ASR ouvert ne diarise

Whisper, Parakeet, Canary, Granite, et les Voxtral à poids ouverts produisent du
texte et des horodatages. Aucun ne dit *qui* parle. Il faut un second étage, et
c'est lui qui coûte cher (§ 4.2).

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

### 4.1 Qualité

| Modèle | Taille | WER français (FLEURS) | WER moyen | Licence |
|---|---|---|---|---|
| Voxtral Mini Transcribe 2 (notre API) | — | n/d | 5,90 % FLEURS | propriétaire |
| **Parakeet TDT 0.6B v3** (NVIDIA) | 0,6 B | **5,15 %** | 6,32 % (Open ASR Leaderboard) | CC-BY-4.0 |
| Whisper large-v3 | 1,55 B | **5,03 %** | 7,40 % | MIT |
| Whisper large-v3 turbo | 809 M | n/d | 7,75 % | MIT |
| Canary-Qwen 2.5B | 2,5 B | anglais seul | 5,63 % | NVIDIA |
| Granite Speech 3.3 8B | 8 B | n/d | 5,85 % | Apache 2.0 |

**Parakeet v3 fait jeu égal avec Whisper large-v3 en français pour trois fois
moins de paramètres.** Sur nos langues, rien ne justifie de payer le prix CPU du
large-v3.

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

### 4.2 Coût CPU, et où se trouve vraiment le goulot

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
| **Diarize** (FoxNoseTech) | **~7 min 30** (RTF 0,12) | 10,8 % annoncé sur le Show HN, **4,8 %** sur le dépôt — écart non expliqué | pas de parole superposée, dégradation au-delà de 7 locuteurs |
| Sortformer v2 (NVIDIA) | n/d | 14,76 % DIHARD3-Eval ; 5,85 % CALLHOME 2 loc. | **4 locuteurs maximum**, gère la parole superposée |

**Le résultat structurant** : à ~1 min 40 pour l'ASR contre ~7 min 30 pour la
diarisation, **l'étage locuteurs coûte plus de quatre fois l'étage texte**.
Toute optimisation portée sur l'ASR est une optimisation portée au mauvais
endroit.

### 4.3 Pourquoi un GPU ne résout pas ce problème

Sur Parakeet, un T4 via ONNX Runtime CUDA donne **×1,6** par rapport au CPU. Il
faut TensorRT — donc NVIDIA, plus une compilation propre à la carte — pour le ×9.
Économiser 40 secondes par heure d'audio ne justifie aucun achat.

Et le GPU n'aide pas davantage la diarisation : chez Diarize, seuls les
embeddings WeSpeaker sont neuronaux ; le VAD Silero mis à part, le reste
(GMM+BIC, clustering spectral) est du scikit-learn, CPU par nature.

**Corollaire** : si un GPU entre un jour dans l'infrastructure, ce sera pour le
LLM d'extraction (le fork LangExtract), pas pour l'audio. Arbitrage distinct,
critères distincts — la VRAM avant tout.

Repères de marché, août 2026 (marché dégradé par la crise mémoire) : RTX 5060 Ti
16 Go à ~805 $ neuve (+88 % sur son MSRP) et ~460 $ d'occasion ; RTX 3060 12 Go à
250-275 $ d'occasion, 339 $ neuve rééditée.

Sur le **Framework Laptop 13 Core Ultra Series 1** (Meteor Lake) : l'iGPU Arc
Xe-LPG **n'a pas d'unités XMX** — l'accélération passe par DP4a, ~16 TOPS INT8 ;
le NPU AI Boost fait ~11 TOPS. Ce sont les XMX de Lunar Lake (Series 2, 67 TOPS)
qui font le saut. La pile Linux existe (`intel_vpu`, `intel/linux-npu-driver`,
plugin NPU d'OpenVINO, noyau ≥ 6.6) et `FluidInference/parakeet-tdt-0.6b-v3-ov`
fournit le modèle converti — mais leur propre mesure annonce **1,3× sur PyTorch
en iGPU**, soit un gain d'autonomie, pas de vitesse. **Non prioritaire.**

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
et plausible**, sans aucun signal d'erreur. Sur un corpus où l'on construit
ensuite un « qui a dit quoi », une attribution fausse et silencieuse vaut moins
qu'une erreur visible.

Un clustering se dégrade autrement : pyannote et Diarize *estiment* le nombre de
locuteurs et peuvent sortir n'importe quel entier. Leur erreur est continue et
symétrique — sur- ou sous-segmentation — donc **détectable**.

**Notre `max_speakers` par défaut est 5.** Exactement une de trop.

Trois sorties si 4 ne suffit pas :

- **`mago-research/Ultra-Sortformer`** (Apache 2.0) élargit la tête de sortie par
  initialisation orthogonale SVD, avec deux taux d'apprentissage (1e-5 sur les
  poids d'origine, 1e-4 sur les nouvelles lignes). **Checkpoints publiés pour 5
  et 8 locuteurs.** Réserve annoncée par le projet : plus de slots décale le
  comptage sur les extraits courts. Compatibilité avec `parakeet-rs`
  **non vérifiée** — dépend du figeage de la dimension de sortie côté Rust.
- Le contournement du ticket #14546 : Sortformer pour la segmentation, puis MFCC
  + k-means en ligne pour ré-attribuer au-delà de 4.
- Diarize, sans plafond dur, au prix de la parole superposée.

### 4.6 Le calcul économique

0,003 $/min = **0,18 $/h d'audio**. Un VPS 8 vCPU / 16 Go coûte 25-40 €/mois.
Point mort ≈ **150-200 h d'audio par mois**. En dessous, le local coûte plus cher.

**Le motif de la bascule n'est donc pas l'argent, c'est la souveraineté sur des
délibérations** — ce qui cadre avec ce que porte le projet par ailleurs.

---

## 5. Le protocole de mesure

### 5.1 Matériel de référence

Framework Laptop 13, **Intel Core Ultra 7 155H**, 22 threads, 30 Go de RAM
(≈20 Go disponibles), Docker 29.6.2. **CPU uniquement.**

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

Trois pièges de ce matériau, déjà traités dans les scripts :

1. La page de transcription couvre **toute l'émission**, chroniques comprises. Le
   sujet Tactic commence au **tour 10** (`reference.json`). Les chroniques
   (Benjamin Bellamy, Isabelle Carrère) sont hors du fichier audio.
2. **« Célo » est orthographié de deux façons** dans la page — « Célo » (22 tours)
   et « Celo » (5 tours). Sans fusion, on compte 5 locuteurs au lieu de 4.
3. Le sujet principal dépasse largement 20 min ; on en extrait une tranche
   (900 s par défaut) et on aligne sur le début.

### 5.4 Ce qu'on mesure — et ce qu'on ne peut pas mesurer

| Grandeur | Comment | Statut |
|---|---|---|
| RTFx de la diarisation | chrono autour de `sortformer.diarize()` | mesurable |
| RTFx de la transcription | chrono cumulé sur les morceaux | mesurable |
| Temps de chargement des modèles | chronométré **à part** de l'inférence | mesurable |
| Pic mémoire réel | `/usr/bin/time -v`, ligne *Maximum resident set size* | mesurable |
| WER | alignement semi-global mot à mot contre la référence humaine | mesurable |
| Nombre de locuteurs détectés | sortie de Sortformer contre les 4 réels | mesurable |
| Répartition du temps de parole | par locuteur, contre le compte de mots de la référence | approché |
| **DER** | — | **NON calculable** |

**Pourquoi pas de DER** : la transcription de l'April **n'a aucun horodatage**.
Un DER exige un alignement temporel de référence. Un vrai DER supposerait
d'annoter à la main les frontières de tours — travail à décider séparément.

Le WER utilise un alignement **semi-global** : la fin de la référence peut être
tronquée sans pénalité, puisqu'on ne transcrit qu'un extrait du début.
Normalisation : minuscules, ponctuation retirée, apostrophes coupées, **accents
conservés**. Les nombres écrits en chiffres contre en lettres resteront comptés
comme des erreurs — biais connu, à signaler dans les résultats.

---

## 6. Le banc monté, et les trois obstacles rencontrés

Le banc est écrit et **compile**. Les fichiers sont en annexe : ils vivent
aujourd'hui dans un scratchpad temporaire, d'où leur recopie ici.

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
4-5 minutes**, et recommande de faire tourner Sortformer sur l'audio entier puis
de **découper pour TDT et de remapper**. L'exemple ne fait pas ce que le README
prescrit.

Notre `bench.rs` le fait : Sortformer sur l'intégralité (il est nativement en
streaming), TDT par morceaux de 240 s, **avec report du décalage sur les
horodatages** de chaque morceau — sans quoi l'attribution est fausse dès le
deuxième morceau.

### 6.3 Ce que le loader attend exactement

`ParakeetTDT::from_pretrained(dossier)` cherche, dans un même dossier :
`encoder-model.onnx`, `encoder-model.onnx.data`, `decoder_joint-model.onnx`,
`vocab.txt`. Sortformer prend un **chemin de fichier**, pas un dossier.

La variante int8 de `istupakov/parakeet-tdt-0.6b-v3-onnx` s'appelle
`encoder-model.int8.onnx` : il faut la **renommer** dans un dossier séparé.
**Non vérifié** : que le loader accepte un encodeur int8 sans fichier `.data`
associé — le fp32 en a un, l'int8 devrait être autonome. **À confirmer au premier
essai.**

Volumétrie : encodeur fp32 ≈ 2,4 Go (`.onnx.data`) + 42 Mo, encodeur int8
≈ 652 Mo, Sortformer v2 quelques dizaines de Mo. C'est le téléchargement du fp32
qui a arrêté la session.

---

## 7. Ce qui reste à faire

**Avant de pouvoir décider** — dans l'ordre :

1. **Finir le téléchargement des poids** (`prepare.sh`), puis lancer le banc en
   **fp32** : `bash run_bench.sh 900 0 ./tdt fp32 240`.
2. **Vérifier que la variante int8 charge** (§ 6.3). Si oui, la mesurer :
   `bash run_bench.sh 900 0 ./tdt-int8 int8 240`. C'est **elle** qui décide pour
   un serveur CPU, pas le fp32.
3. **Contrôler le point de départ de l'audio** : le fichier commence-t-il au tour
   10 (annonce d'Étienne Gonnu) ou au tour 11 (Laurent Costy) ? Ajuster le
   troisième argument de `comparer.py`. Un décalage d'un tour fausse le WER.
4. **Lancer `comparer.py`** et consigner : WER, nombre de locuteurs détectés,
   répartition de la parole, pic RSS.
5. **Lire à la main 3 ou 4 changements de tour** dans `resultat_*.json`. Le WER
   ne dit rien de la qualité d'attribution ; l'œil, si.
6. **Éprouver le plafond des 4** : refaire tourner sur un extrait où les quatre
   parlent, puis chercher un enregistrement à 5 ou 6 voix et vérifier que la
   sortie reste plausible alors qu'elle est fausse (§ 4.5). C'est le test qui
   compte le plus pour nous.

**Ensuite, les autres solutions à comparer** :

- **`istupakov/onnx-asr` + `FoxNoseTech/diarize`** en Python — la voie la plus
  proche de notre pile. Le collage manque (alignement RTTM ↔ horodatages), il
  est de l'ordre de la centaine de lignes, et `construire_html_diarise()` attend
  déjà cette forme de données.
- **`loudpage/parakeet-v3-diarized`** — Parakeet v3 + pyannote derrière une API
  compatible Whisper, sorties VTT. Le prêt-à-l'emploi : à mesurer pour la
  qualité de bout en bout, en acceptant la lenteur de pyannote et le token HF.
- **`achetronic/parakeet`** — serveur Go, API compatible Whisper, sortie VTT,
  Docker fourni. Pas de diarisation, mais **la sortie VTT entre directement dans
  le backend WebVTT de Docling** que nous utilisons déjà.
- **Ultra-Sortformer 5 ou 8 locuteurs** si le plafond de 4 se révèle bloquant.

**Décisions qui attendent le mainteneur** :

- **Combien de voix dans les enregistrements réels ?** Toute l'architecture en
  dépend. `max_speakers` vaut 5 par défaut, ce qui suggère plus de 4.
- **Faut-il un DER ?** S'il le faut, il faut annoter à la main les frontières de
  tours sur un extrait. À arbitrer avant de s'engager.
- **Où ranger le banc d'essai** — il est aujourd'hui dans un scratchpad
  temporaire (annexes ci-dessous pour ne rien perdre).

**Non fait, et volontairement** : la voie OpenVINO/NPU sur Meteor Lake (§ 4.3).
Le gain est en watts, pas en secondes.

---

## 8. Les critères de la décision

Dans cet ordre, le premier qui échoue disqualifie :

1. **L'attribution des locuteurs est-elle juste** sur un extrait à 4 voix, et
   **échoue-t-elle visiblement** au-delà ? Une erreur silencieuse est
   disqualifiante — c'est ce qui contamine la suite de la chaîne.
2. **Le WER français** tient-il la comparaison avec ce que rend Voxtral
   aujourd'hui, sur le même extrait ?
3. **Le coût CPU** tient-il dans une file Celery aux côtés du reste ?
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
FROM rust:1-trixie

# ffmpeg pour la conversion audio, time pour mesurer la RAM reellement consommee
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl time python3 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENV CARGO_TERM_COLOR=never
```

Mise en route :

```bash
docker build -t bench-asr:2 .
docker run -d --name bench-asr2 -v "$PWD":/work -w /work bench-asr:2 sleep infinity
docker exec bench-asr2 bash -c 'cd /work && cargo build --release'
```

## Annexe B — `Cargo.toml`

```toml
[package]
name = "bench"
version = "0.1.0"
edition = "2021"

[dependencies]
# La feature sortformer n'est pas activee par defaut / sortformer feature is off by default
parakeet-rs = { version = "0.3", features = ["sortformer"] }
hound = "3.5"

[profile.release]
opt-level = 3
```

## Annexe C — `prepare.sh` (l'essentiel)

```bash
HF_TDT="https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/resolve/main"
HF_SORT="https://huggingface.co/altunenes/parakeet-rs/resolve/main"
AUDIO="https://media.april.org/audio/radio-cause-commune/libre-a-vous/emissions/20260707/libre-a-vous-20260707-tactic-asbl.ogg"

# fp32 — les quatre fichiers doivent etre dans le meme dossier
curl -sSL -o tdt/encoder-model.onnx        "$HF_TDT/encoder-model.onnx"
curl -sSL -o tdt/encoder-model.onnx.data   "$HF_TDT/encoder-model.onnx.data"   # ~2,4 Go
curl -sSL -o tdt/decoder_joint-model.onnx  "$HF_TDT/decoder_joint-model.onnx"
curl -sSL -o tdt/vocab.txt                 "$HF_TDT/vocab.txt"

# int8 — renommage obligatoire : le loader ne connait pas le suffixe .int8
curl -sSL -o tdt-int8/encoder-model.onnx        "$HF_TDT/encoder-model.int8.onnx"
curl -sSL -o tdt-int8/decoder_joint-model.onnx  "$HF_TDT/decoder_joint-model.int8.onnx"
cp tdt/vocab.txt tdt-int8/vocab.txt

curl -sSL -o diar_streaming_sortformer_4spk-v2.onnx "$HF_SORT/diar_streaming_sortformer_4spk-v2.onnx"
curl -sSL -o audio/source.ogg "$AUDIO"

# Sortformer comme Parakeet exigent 16 kHz mono
ffmpeg -y -i audio/source.ogg -ac 1 -ar 16000 -sample_fmt s16 audio/complet.wav
```

## Annexe D — `run_bench.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /work
DUREE="${1:-900}"; DEBUT="${2:-0}"; MODELE="${3:-./tdt}"
ETIQUETTE="${4:-fp32}"; CHUNK="${5:-240}"
EXTRAIT="audio/extrait_${DUREE}s.wav"

[ -f "$EXTRAIT" ] || ffmpeg -y -loglevel error -ss "$DEBUT" -t "$DUREE" \
    -i audio/complet.wav -ac 1 -ar 16000 -sample_fmt s16 "$EXTRAIT"

# /usr/bin/time -v donne le pic RSS, ce que le `time` du shell ne sait pas faire
/usr/bin/time -v ./target/release/bench \
    "$EXTRAIT" "$MODELE" "$CHUNK" "resultat_${ETIQUETTE}.json" \
    2> "mesures_${ETIQUETTE}.txt" | tee "sortie_${ETIQUETTE}.txt"

grep -E "Maximum resident|Elapsed .wall|User time|Percent of CPU" "mesures_${ETIQUETTE}.txt"
```

## Annexe E — `src/main.rs`, les points qui comptent

Trois passages portent tout le sens et sont signalés dans le code :
Sortformer tourne sur l'audio **entier** (il est nativement en streaming), TDT est
**découpé** avec **report du décalage** sur les horodatages — c'est le correctif que
l'exemple officiel du dépôt n'a pas — et l'attribution se fait par **recouvrement
temporel maximal**.

Deux pièges à ne pas re-découvrir : `segment.start` et `segment.end` de Sortformer
sont en **échantillons**, pas en secondes ; et sans le report du décalage,
l'attribution est fausse dès le deuxième morceau.

```rust
/*
Banc d'essai : Parakeet TDT v3 (transcription) + Sortformer v2 (diarisation), CPU uniquement.
/ Benchmark: Parakeet TDT v3 (transcription) + Sortformer v2 (diarization), CPU only.

Difference avec examples/diarization.rs du depot : cet exemple DECOUPE l'audio pour TDT.
Le README previent que TDT plafonne autour de 4-5 minutes ; l'exemple officiel ne gere pas
ce cas et echoue donc silencieusement sur un fichier long. Sortformer, lui, tourne sur
l'integralite de l'audio d'un seul tenant puisqu'il est nativement en streaming.
/ Difference with the repo's examples/diarization.rs: this one CHUNKS the audio for TDT.
The README warns TDT caps around 4-5 minutes; the official example does not handle it.
Sortformer runs on the whole audio at once since it is natively streaming.

Usage: bench <audio.wav> <dossier_tdt> <secondes_par_chunk> <sortie.json>
*/

use parakeet_rs::sortformer::{DiarizationConfig, Sortformer};
use parakeet_rs::{ParakeetTDT, TimestampMode, Transcriber};
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
    let chemin_audio = arguments.get(1).expect("usage: bench <audio.wav> <dossier_tdt> <sec_par_chunk> <sortie.json>");
    let dossier_tdt = arguments.get(2).expect("dossier du modele TDT manquant");
    let secondes_par_chunk: f32 = arguments.get(3).map(|s| s.parse().unwrap()).unwrap_or(240.0);
    let chemin_sortie = arguments.get(4).map(|s| s.as_str()).unwrap_or("resultat.json");

    // ---------- Lecture de l'audio / Read the audio ----------
    let mut lecteur = hound::WavReader::open(chemin_audio)?;
    let specification = lecteur.spec();
    let echantillons: Vec<f32> = match specification.sample_format {
        hound::SampleFormat::Float => lecteur.samples::<f32>().collect::<Result<Vec<_>, _>>()?,
        hound::SampleFormat::Int => lecteur
            .samples::<i16>()
            .map(|s| s.map(|s| s as f32 / 32768.0))
            .collect::<Result<Vec<_>, _>>()?,
    };
    let duree_audio_secondes =
        echantillons.len() as f32 / specification.sample_rate as f32 / specification.channels as f32;

    println!("### AUDIO");
    println!("fichier            : {}", chemin_audio);
    println!("echantillons       : {}", echantillons.len());
    println!("frequence          : {} Hz", specification.sample_rate);
    println!("canaux             : {}", specification.channels);
    println!("duree              : {:.1} s ({:.1} min)", duree_audio_secondes, duree_audio_secondes / 60.0);
    println!("modele TDT         : {}", dossier_tdt);
    println!("decoupage TDT      : {:.0} s par morceau", secondes_par_chunk);
    println!();

    // ---------- Etape 1 : diarisation sur l'audio complet ----------
    println!("### ETAPE 1 — DIARISATION (Sortformer v2, audio entier)");
    let chrono_chargement_sortformer = Instant::now();
    let mut sortformer = Sortformer::with_config(
        "diar_streaming_sortformer_4spk-v2.onnx",
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
                println!(
                    "  morceau {}/{} ({:.0} s d'audio) : {:.2} s -> {:.1}x, {} phrases",
                    indice + 1, nombre_de_chunks, duree_morceau,
                    chrono_morceau.elapsed().as_secs_f32(),
                    duree_morceau / chrono_morceau.elapsed().as_secs_f32(),
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

    // ---------- Etape 3 : attribution par recouvrement maximal ----------
    println!("### ETAPE 3 — ATTRIBUTION (recouvrement temporel maximal)");
    let mut segments_attribues: Vec<SegmentAttribue> = Vec::new();
    let mut phrases_sans_locuteur = 0usize;

    for (debut, fin, texte) in &phrases_horodatees {
        let locuteur = segments_locuteurs
            .iter()
            .filter_map(|segment| {
                let segment_debut = segment.start as f32 / TAUX_ECHANTILLONNAGE as f32;
                let segment_fin = segment.end as f32 / TAUX_ECHANTILLONNAGE as f32;
                let recouvrement = (fin.min(segment_fin) - debut.max(segment_debut)).max(0.0);
                if recouvrement > 0.0 { Some((segment.speaker_id, recouvrement)) } else { None }
            })
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap())
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
    println!("=> pour 1 h d'audio    : {:.1} min de calcul", 3600.0 / (duree_audio_secondes / temps_total_inference) / 60.0);

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

Le taux de phrases `INCONNU` est un indicateur en soi : il monte quand Sortformer
ne détecte pas de locuteur actif, donc **quand il y a plus de voix qu'il ne peut
en représenter**.

Sorties : `resultat_<etiquette>.json` (métriques + segments attribués + texte
brut) et `mesures_<etiquette>.txt` (`/usr/bin/time -v`).

## Annexe F — `reference.py`

Récupère la transcription humaine avec `html.parser` de la bibliothèque standard
— aucune dépendance à installer. Les tours de parole sont marqués par un **nom en
gras suivi de deux-points** ; un candidat est retenu s'il fait 40 caractères ou
moins, ce qui écarte les phrases en gras. Sorties : `reference.json` et
`reference.txt`.

Sortie observée sur l'émission n° 282 : **131 tours**, dont Laurent Costy (43),
HgO (32), Célo (22), Étienne Gonnu (17) pour le sujet Tactic — plus « Celo » (5),
qui est le même intervenant mal orthographié, et les chroniqueurs hors sujet.

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
    """Reconstruit le flux texte en marquant ce qui etait en gras."""

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
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bench-asr)"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        brut = reponse.read()
    for encodage in ("utf-8", "latin-1"):
        try:
            return brut.decode(encodage)
        except UnicodeDecodeError:
            continue
    return brut.decode("utf-8", errors="replace")


def construire_les_tours(morceaux):
    """Un tour commence a chaque nom en gras termine par ':'."""
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

    print(f"  tours de parole detectes : {len(tours)}")
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
"""Affiche l'ordre des tours de parole pour reperer les frontieres des segments."""
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
transcrit qu'un extrait du début. Troisième argument : le **tour de départ**
(10 par défaut, § 5.3). L'alias `Celo` → `Célo` est fusionné.

Il affiche substitutions, omissions et insertions **séparément** : leur répartition
en dit plus que le WER global. Beaucoup d'omissions signalent des passages non
transcrits ; beaucoup d'insertions, des hallucinations.

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
"""
import json
import re
import sys
import unicodedata

CHEMIN_HYPOTHESE = sys.argv[1] if len(sys.argv) > 1 else "resultat.json"
CHEMIN_REFERENCE = sys.argv[2] if len(sys.argv) > 2 else "reference.json"
# La page de reference couvre toute l'emission (chroniques comprises) ; le fichier
# audio ne couvre que le sujet principal. On demarre donc la reference a ce tour-la.
# / The reference page covers the whole show; the audio file only covers the main
# topic, so we start the reference at that turn.
TOUR_DE_DEPART = int(sys.argv[3]) if len(sys.argv) > 3 else 10

# Le meme intervenant est ecrit de deux facons dans la page / same person, two spellings
ALIAS_LOCUTEURS = {"Celo": "Célo"}


def normaliser(texte):
    """Minuscules, ponctuation retiree, espaces normalises. Les accents sont GARDES."""
    texte = texte.lower()
    # Les apostrophes typographiques deviennent des apostrophes simples
    texte = texte.replace("’", "'").replace("‘", "'")
    # On coupe sur l'apostrophe : "l'April" -> "l" "april", des deux cotes pareil
    texte = texte.replace("'", " ")
    texte = "".join(
        caractere for caractere in texte
        if not unicodedata.category(caractere).startswith("P") or caractere == " "
    )
    return re.sub(r"\s+", " ", texte).strip()


def mots(texte):
    return normaliser(texte).split()


def wer_semi_global(hypothese, reference):
    """
    Distance d'edition au niveau des mots, fin de reference libre.
    Retourne (wer, erreurs, longueur_reference_utilisee, S, D, I).
    """
    n, m = len(hypothese), len(reference)
    if n == 0:
        return 1.0, m, m, 0, m, 0

    # d[j] pour la ligne courante ; on garde aussi le decompte des operations
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

    # Fin de reference libre : on prend le j qui minimise le WER, pas la distance brute
    meilleur_wer, meilleur_j = 2.0, m
    for j in range(max(1, n // 2), m + 1):
        wer_ici = precedente[j] / j
        if wer_ici < meilleur_wer:
            meilleur_wer, meilleur_j = wer_ici, j

    s, d, ins = ops_precedente[meilleur_j]
    return meilleur_wer, precedente[meilleur_j], meilleur_j, s, d, ins


def main():
    with open(CHEMIN_HYPOTHESE, encoding="utf-8") as fichier:
        resultat = json.load(fichier)
    with open(CHEMIN_REFERENCE, encoding="utf-8") as fichier:
        reference = json.load(fichier)

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
    print(f"  >>> WER = {100.0 * wer:.2f} %")
    print()

    print("-" * 78)
    print("LOCUTEURS")
    print("-" * 78)
    locuteurs_reference = {}
    for tour in reference:
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
- discussion `ggml-org/whisper.cpp#3752` — quantification q4_0 contre q5/q2_k
- Mistral — *Voxtral Transcribe 2*, tarif et diarisation
- TechPowerUp — deep dives Meteor Lake (Xe-LPG sans XMX) et Lunar Lake (XMX)

Une synthèse plus large de cette veille est dans la mémoire persistante :
atom *« Transcription audio locale sur CPU en 2026 »* (`66e79a48`).
