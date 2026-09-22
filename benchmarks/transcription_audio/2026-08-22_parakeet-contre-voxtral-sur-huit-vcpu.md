# Parakeet contre Voxtral sur huit vCPU — la première mesure du chantier

**22 août 2026.** Première mesure d'inférence de la transcription locale : la
spec était écrite depuis le 16 août, **aucun chiffre n'avait jamais été relevé**.

**Machine** — chaque chiffre de cette note vaut *pour cette machine*, et le
mainteneur rejouera les mêmes mesures sur le Framework Laptop 13 :

| | |
|---|---|
| processeur | `Intel Core Processor (Haswell, no TSX)` — VM QEMU/KVM |
| vCPU | **8** (`nproc`), 1 thread par cœur |
| VNNI / AMX | **aucun** — le drapeau le plus élevé est `avx2` |
| RAM | 22 Go, **14 Go disponibles** |
| état de la stack | Hypostasia en marche, workers Celery **résidents au repos** (5,4 Go + 2,3 Go), aucune tâche en cours, charge < 1,5 |
| conteneurs | `rust:1-trixie` (voie A) et `python:3.12-slim` (voie B), **sans bridage** — la machine *est* le gabarit VPS visé |

---

## Ce que cette journée a trouvé, en quatre points

1. **Le protocole de découpage écrit dans la spec détruit la transcription.**
   Parakeet TDT v3 nourri par blocs de 240 s (§ 6.2) rend **95,4 % de WER**, perd
   88 % du texte, et sort du franglais — **32,2 %** de ses mots sont des mots
   anglais courants, contre 0,1 % dans la transcription humaine. Le même modèle,
   sur le même audio, alimenté par segments de parole, rend **34,9 %**.
2. **Ce n'était ni la quantification, ni la crate Rust, ni notre audio.** Trois
   vérifications l'établissent, et elles comptent parce que chacune écarte une
   fausse piste coûteuse.
3. **Le plafond de 4 locuteurs existe, il est atteint, et l'échec est
   parfaitement silencieux.** Sur une tranche à **6 voix réelles**, Sortformer en
   rend **exactement 4**, `diarize` en rend **5** — et les deux affichent
   **0,0 %** d'`INCONNU`. Voxtral en rend **7** : il se trompe aussi, mais dans
   l'autre sens, et ses deux locuteurs de trop pèsent 10 et 41 mots — une erreur
   qu'un contrôle automatique peut voir.
4. **La diarisation n'est pas le goulot** — l'hypothèse 6 de la spec est infirmée
   sur ce matériel. Elle coûte **moins** que la transcription (82,8 s contre
   108,8 s pour la voie A), là où les sources publiques annonçaient un rapport de
   quatre pour un dans l'autre sens.

---

## Le matériau, et les quatre tranches mesurées

Deux émissions de « Libre à vous ! » (radio Cause Commune, licence libre), leurs
transcriptions humaines publiées sur librealire.org, figées en copie locale.

| tranche | source | durée | voix réelles | répartition |
|---|---|---|---|---|
| **T1** | n° 282 du 7 juillet, sujet Tactic, 0 → 900 s | 900 s | **4** | Célo 977, Laurent Costy 647, HgO 534, Étienne Gonnu 90 mots |
| **T2** | 16 juin, « Au café libre », 600 → 1500 s | 900 s | **4** | Étienne Gonnu 1450, Isabelle Carrère 545, Pierre Beyssac 449, Gee 183 |
| **T3** | 16 juin, « Au café libre », 2790 → 3690 s | 900 s | **4** | Pierre Beyssac 1420, Gee 919, Étienne Gonnu 880, Isabelle Carrère 212 |
| **T4** | 16 juin, **émission entière**, 4100 → 5000 s | 900 s | **6** | Benjamin Bellamy 709, Gee 677, Pierre Beyssac 550, Étienne Gonnu 516, Gaël 78, Isabelle Carrère 11 |

**T4 est le test du critère 1** : la tranche enjambe deux séquences — la fin du
plateau à quatre, puis une chronique dialoguée à deux voix nouvelles. Six
personnes distinctes dans un audio continu, sans montage.

Deux points de protocole tranchés au passage :

- **Le piège 1 du § 5.3 est levé** : l'audio de T1 commence bien au **tour 10**
  (« Nous allons poursuivre par notre sujet principal qui porte sur Tactic »), et
  non au tour 11. Vérifié contre la référence, comme le demandait le § 7.4.
- **La référence de T1 rend 131 tours**, exactement l'attendu du § 7.1 : la page
  n'a pas changé depuis que la spec l'a décrite.

---

## Les mesures de coût et de qualité — tranche T1

Une ligne par (moteur, quantification, découpage, machine). Toutes ont tourné sur
la machine de l'en-tête, **l'une après l'autre** — jamais deux inférences en même
temps.

| pile | quantif. | découpage ASR | diarisation | transcription | inférence | RTFx | par heure d'audio | pic RSS | locut. (4 réels) | WER | mots anglais |
|---|---|---|---|---|---|---|---|---|---|---|---|
| voie A — `parakeet-rs` + Sortformer v2 | int8 | **240 s** (§ 6.2) | 81,1 s | 208,1 s | 289,2 s | 3,1× | 19,3 min | 5,52 Go | 3 | **95,37 %** | **32,20 %** |
| voie A — `parakeet-rs` + Sortformer v2 | int8 | 20 s | 82,8 s | 108,8 s | 191,5 s | **4,7×** | **12,8 min** | **1,84 Go** | 3 | 39,09 % | 0,92 % |
| voie B — `onnx-asr` + `diarize` | int8 | VAD Silero | 136,4 s | 158,8 s | 295,2 s | 3,0× | 19,7 min | 3,89 Go | 3 | **34,95 %** | 0,36 % |
| voie B — `onnx-asr` + `diarize` | fp32 | VAD Silero | 134,1 s | **96,3 s** | 230,4 s | 3,9× | 15,4 min | 5,01 Go | 3 | 55,53 % | — |
| **Voxtral** (API Mistral) | — | — | *(un seul appel)* | | **11,0 s** | 82× | — | — | **4** | **26,90 %** | 0,12 % |

Le chargement des modèles est mesuré **hors inférence** : 4,5 à 7,2 s selon la
pile. Il ne se paie qu'une fois si le worker reste vivant.

L'appel Voxtral a coûté **0,045 $** pour ces 900 s.

La colonne « mots anglais » compte les occurrences de 40 mots anglais très
courants (*the, and, that, with, of, is, was…*) rapportées au nombre de mots.
C'est une **approximation**, pas une mesure de langue : elle donne un ordre de
grandeur au phénomène de bascule, et sa valeur de référence est le 0,10 % de la
transcription humaine.

### Ce que ces chiffres disent

**Le coût CPU tient dans une file Celery.** La meilleure configuration mesurée
demande **12,8 min de calcul par heure d'audio** (RTFx 4,7×), à 241 % de CPU —
soit 2,4 cœurs sur 8 — et 1,84 Go de pic. Une heure d'audio coûterait treize
minutes d'un worker déprioritisé. **Le critère § 8.3 est satisfait**, et
largement.

**Le WER de la meilleure pile locale reste 8 points au-dessus de Voxtral**
(34,95 % contre 26,90 %). Sur T4, l'écart est du même ordre (40,13 % contre
31,95 %). Les deux chiffres sortent du même `comparer.py`, sur le même extrait :
ce qui compte est l'écart, pas le niveau absolu — que les biais du § 5.4 tirent
vers le haut pour tout le monde.

**Le fp32 est plus rapide que l'int8, et nettement moins bon.** 96,3 s contre
158,8 s pour la même transcription — l'int8 est **1,6× plus lent**, ce qui
s'explique : sans VNNI ni AMX, il n'existe aucun chemin entier optimisé, et la
déquantification coûte plus que ce que l'arithmétique entière fait gagner. Mais
le fp32 rend **2 292 mots contre 2 674**, et son WER monte à **55,53 %** : il
saute du contenu. **Une seule passe, et aucune explication établie** — ce
pourrait être un défaut de l'export ONNX du fp32 (le seul à porter un fichier
`.data` externe de 2,3 Go) autant qu'un effet réel. À reprendre sur la seconde
machine avant d'en tirer quoi que ce soit.

**Conséquence pratique, pour cette machine seulement** : l'int8 est le bon choix
— meilleur texte pour 652 Mo au lieu de 2,4 Go — et son surcoût en temps est le
prix d'un processeur sans instructions entières dédiées. Sur un VPS récent, le
classement des vitesses s'inverserait probablement. C'est l'objet de la mesure
sur la seconde machine.

---

## Le critère 1 : le plafond des locuteurs

C'est le critère qui disqualifie. Voici ce que les quatre tranches donnent.

| tranche | voix réelles | voie A (Sortformer) | voie B (`diarize`, max 8) | Voxtral |
|---|---|---|---|---|
| T1 | 4 (une à 90 mots) | **3** | **3** | **4** ✓ |
| T2 | 4 | **4** ✓ | **4** ✓ | **4** ✓ |
| T3 | 4 | **4** ✓ | **4** ✓ | **5** |
| **T4** | **6** | **4** | **5** | **7** |

**Sur T1, les deux piles locales perdent le locuteur qui parle le moins** — 90
mots sur 2 248. Sur T2 et T3, où les quatre voix sont mieux réparties, elles
trouvent le bon compte. **Ce n'est donc pas le nombre de voix qui les met en
défaut, c'est le déséquilibre des temps de parole.** Dans une délibération, c'est
exactement le profil du président de séance — celui qui distribue la parole sans
la prendre.

**Sur T4, le plafond architectural se voit à l'œil nu** : Sortformer rend
**exactement 4** slots pour 6 personnes, ce que le § 4.5 annonçait comme
« limitation attendue de l'architecture, pas un bug ». `diarize`, qui n'a **aucun
plafond dur** et à qui on avait autorisé jusqu'à 8 locuteurs, en trouve 5 — il se
dégrade autrement, mais il se dégrade.

### L'erreur est silencieuse, et c'est mesuré

| tranche T4 | locuteurs rendus | taux d'`INCONNU` |
|---|---|---|
| voie A | 4 pour 6 | **0,3 %** (6 mots) |
| voie B | 5 pour 6 | **0,0 %** (0 mot) |

**L'avertissement du § 4.5 est vérifié par la mesure.** Le taux d'`INCONNU` ne
monte que si le diariseur n'attribue rien ; dans le cas d'absorption — celui qui
nous concerne — il reste au plancher pendant que la sortie est fausse. **Ce taux
ne peut pas servir de garde-fou**, et il n'existe dans les deux piles locales
aucun autre signal exploitable de dépassement.

**Voxtral se trompe aussi, mais son erreur est visible.** Sur T4 il rend 7
locuteurs pour 6, sur T3 il en rend 5 pour 4 : il **sur-segmente**. Or ses
locuteurs excédentaires portent 10 et 41 mots — un seuil sur le volume de parole
par locuteur les repérerait. Une sur-segmentation se détecte ; une absorption,
non. **Pour une chaîne de preuve, ce n'est pas la même erreur.**

### Lu à l'œil, sur T1

Le § 7.7 demandait de lire à la main quelques changements de tour, parce que le
WER ne dit rien de l'attribution. Les cinq premiers :

| temps | Voxtral | voie B | qui parle vraiment |
|---|---|---|---|
| 0 → 25 s | `speaker_1` | `SPEAKER_01` | Étienne Gonnu |
| 25 → 102 s | `speaker_2` | `SPEAKER_01` | Laurent Costy |
| 102 → 105 s | `speaker_3` | `SPEAKER_00` | Célo |
| 105 → 109 s | `speaker_2` | `SPEAKER_01` | Laurent Costy |
| 109 → 111 s | `speaker_4` | `SPEAKER_02` | HgO |

Voxtral sépare les quatre personnes. **La voie B fond l'animateur et l'invité
principal dans un seul slot** : `SPEAKER_01` porte à la fois Étienne Gonnu et
Laurent Costy.

---

## Le mode d'emploi que personne n'avait écrit

C'est le résultat d'ingénierie de la journée, et il ne figure dans la
documentation d'aucun des deux projets.

**Parakeet TDT v3 ONNX ne se nourrit pas de blocs de durée fixe.** Sur 120 s d'un
bloc, il rend 433 caractères de franglais pour deux minutes de parole dense ; sur
20 s isolées, il rend **du vide**. Le même modèle, découpé par un VAD sur les
frontières de parole, rend du français propre :

> **blocs de 240 s :** « Tactic, an association on but non lucratif, an ASBL that
> defends the logiciel libre, a sujet that's animated by the seul and unique
> Laurent Costi […] We are donc in Belgique already. »
>
> **VAD :** « Nous allons donc poursuivre par notre sujet principal qui portera
> sur tactique et non pas tic-tac […] Merci beaucoup Étienne, bonjour à toutes et
> à tous. Donc depuis 2002, tactique ASBL, ASBL pour associations sans but
> lucratif. »

Trois vérifications ont été nécessaires, et chacune écarte une fausse piste :

1. **Ce n'est pas la quantification** — le fp32 rend le même charabia que l'int8,
   au mot près.
2. **Ce n'est pas la crate Rust** — `onnx-asr`, implémentation Python
   indépendante, rend **le même texte** sur les mêmes fichiers ONNX. Deux
   décodeurs écrits séparément ne convergent pas sur un bug : c'est le modèle qui
   produit cela.
3. **Ce n'est pas notre audio** — `whisper-base`, sur le même WAV, rend du
   français correct. L'audio est propre : mono 16 kHz, −17,5 dB moyen.

**Le découpage court ne suffit pas tout à fait.** À 20 s de bloc, la voie A
descend à 0,92 % de mots anglais — neuf fois plus que la transcription humaine,
et près de trois fois plus que la voie B (0,36 %). Le VAD fait mieux parce qu'il
coupe **là où personne ne parle**, jamais au milieu d'un mot.

**Et il manque deux fichiers au `prepare.sh` de la spec** : `config.json` et
`nemo128.onnx`, le préprocesseur mel à **128 bandes**. Sans lui, `onnx-asr`
s'arrête sur `Got: 80 Expected: 128`. Le dépôt HuggingFace les publie ; l'annexe C
ne les télécharge pas.

---

## La forme de sortie : vérifiée, pas déduite

`construire_html_diarise()` (`front/services/transcription_audio.py:271`) attend
une liste de `{speaker, start, end, text}`. La voie B écrit cette forme sur
demande (`--forme-produit`), et elle a été **passée pour de vrai** dans la
fonction, dans le conteneur `web` : 26 segments en entrée → 32 996 caractères de
HTML diarisé valide, blocs colorés par locuteur compris.

La voie A rend des clefs françaises (`debut`, `fin`, `locuteur`, `texte`) : un
renommage suffit. **Aucune des deux piles n'est disqualifiée sur la forme.**

Une différence de fond, en revanche : la voie A attribue à la **phrase**, la voie
B au **mot** (biais 4 du § 5.4). Une phrase qui enjambe un changement de tour
part en bloc chez un seul locuteur côté voie A ; côté voie B, chaque mot est
attribué par son point milieu, puis les mots consécutifs de même locuteur sont
regroupés. **C'est l'avantage structurel de la voie B**, et il porte précisément
sur ce que le critère 1 mesure.

---

## Les biais, rappelés

Les quatre du § 5.4 valent pour tous les chiffres ci-dessus :

1. **Le WER est une borne inférieure**, jamais une estimation neutre :
   `comparer.py` retient le point de troncature qui le minimise.
2. **Aucune normalisation des nombres** — « 20 » contre « vingt » compte comme
   une erreur.
3. **Le découpage coupe le mot à cheval sur chaque frontière** — négligeable avec
   un VAD, réel avec des blocs fixes.
4. **La granularité d'attribution diffère entre les deux voies** (phrase contre
   mot) : leurs taux d'`INCONNU` ne sont pas comparables entre eux.

Quatre s'y ajoutent, propres à cette campagne :

5. **Une seule passe par ligne.** Aucune mesure de la dispersion. Les écarts
   inférieurs à ~5 % ne doivent pas être lus comme significatifs.
6. **Le tour de départ n'est vérifié contre l'audio que pour T1.** Pour T2 à T4,
   il vient d'un calage par débit moyen de parole : leurs WER portent une
   incertitude que T1 n'a pas. Leur **classement** reste cohérent avec T1, ce qui
   est le seul usage qu'on en fait ici.
7. **Les autres workers étaient résidents en mémoire** pendant les mesures. Ils
   ne consommaient pas de CPU, mais occupaient 7,7 Go : les pics RSS relevés sont
   ceux du banc seul, la RAM disponible autour ne l'était pas.
8. **Aucune pile ne sature la machine** — le CPU plafonne vers 360 % sur 8 vCPU.
   Les RTFx mesurés sont ceux du parallélisme interne d'ONNX Runtime tel qu'il
   vient, pas ceux d'un système poussé à fond.

---

## Ce qui n'est toujours pas mesurable

**Le DER reste incalculable** : la transcription de l'April n'a aucun horodatage,
et un DER exige un alignement temporel de référence. Ce que cette note établit
sur l'attribution — la fusion de deux locuteurs, le plafond à 4 — vient du
**comptage des locuteurs** et d'une **lecture à l'œil** des changements de tour.
C'est convaincant, et ce n'est pas une métrique.

---

## Ce que ça change pour les trois décisions en attente

Sans les trancher — ce n'est pas le rôle d'une mesure :

- **Combien de voix dans les enregistrements réels ?** La question devient plus
  aiguë, pas moins : au-delà de 4, **aucune des deux piles locales ne le dit**.
  À 5 ou 6 voix il faudrait Ultra-Sortformer, ou accepter une attribution fausse
  en silence. **Tant que ce chiffre n'est pas connu, aucune des deux voies ne
  peut être retenue pour de la délibération.**
- **Faut-il un DER ?** La mesure suggère que non, ou pas d'abord : ce qui a
  départagé les piles ici, c'est le **comptage des locuteurs** contre une
  référence humaine — qui ne coûte rien — et non la précision des frontières. Un
  DER coûterait quelques heures d'annotation pour affiner une décision que le
  comptage tranche déjà.
- **Où ranger le banc ?** Tranché par le mainteneur le 22 août, et fait : scripts
  dans `benchmarks/transcription_audio/banc/`, poids et résultats bruts hors
  dépôt, dossier de travail passé en argument.
