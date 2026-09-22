# La marge de neutralité fait taire les deux meilleurs juges

> ## ⚖️ TRANCHÉ par le mainteneur le 30 août 2026 — VOIE A, UNE MARGE PAR JUGE
>
> **Chaque juge porte sa propre marge, calibrée sur sa distribution.** La voie B
> — une échelle commune — n'est pas retenue : elle demanderait de décider ce que
> « comparable » veut dire entre un juge à contradiction et un juge sans, ce qui
> est un problème plus dur que celui qu'on cherche à résoudre.
>
> **Le patron de code existe déjà, et il faut le suivre à l'identique** — c'est
> celui du SEUIL, qui a exactement le même problème et qui l'a résolu :
> `seuil_du_juge(nom)` lit `SEUILS_PAR_DEFAUT` (`core/services/juges_locaux.py:385`),
> réglable par variable d'environnement (`SEUIL_<JUGE>`), **et la valeur est
> FIGÉE sur l'avis au moment de l'écriture** (`AvisDeVerification.seuil`,
> `core/models.py:2202`). La marge doit être figée de la même façon, sur un champ
> de l'avis. **Sans ce gel, changer une marge réécrirait le verdict de tous les
> avis déjà en base** — et c'est précisément la faute que le gel du seuil existe
> pour empêcher.
>
> `MARGE_DE_NEUTRALITE = 2.5` (`core/models.py:2255`) devient donc
> `marge_du_juge(nom)` + `MARGES_PAR_DEFAUT` + un champ `marge` sur l'avis, lu par
> `tranche` (`core/models.py:2301`) à la place de la constante de classe.

### Les distributions par juge — MESURÉES le 30 août 2026

C'est ce que la section « ce qu'il faut avant de coder » réclamait. Mesure
**gratuite**, en lecture seule, sur les **859** avis en base (aucun modèle
appelé) :

| juge | n | médiane | Q1 | Q3 | seuil | < 1 pt | **< 2,5 pt (muet aujourd'hui)** | < 5 pt |
|---|---|---|---|---|---|---|---|---|
| CamemBERTa v2 | 859 | 50,5 | 49,8 | 58,0 | 49,7 | 38 % | **50 %** | 59 % |
| mDeBERTa v3 | 859 | 50,0 | **50,0** | 58,8 | 50,0 | **61 %** | **65 %** | 67 % |
| bge-m3 | 859 | 32,8 | 6,3 | 83,2 | 70,0 | 1 % | **2 %** | 4 % |
| distilCamemBERT | 859 | 54,0 | 45,9 | 82,5 | 63,7 | 1 % | **4 %** | 8 % |

**Un écart à lever avant de calibrer.** Cette note annonce **85 %** de mutisme
pour CamemBERTa v2 et mDeBERTa v3 (mesure du 20 août, 836 avis) ; la mesure du
30 août en rend **50 %** et **65 %** sur 859 avis. L'écart n'est pas expliqué —
il peut venir du corpus d'avis, qui a grossi, ou d'une définition différente du
mutisme. **Le sens du défaut ne change pas** (les deux juges à contradiction se
taisent bien plus que les deux autres), mais aucun seuil ne doit être choisi sur
un chiffre dont on ne sait pas d'où il vient.

### Ce que la mesure ajoute, et qui borne l'attente

**La voie A règle trois juges sur quatre, pas quatre.**

- **bge-m3** ne se tait que 2 % du temps : sa marge doit **augmenter**, pas
  baisser. Une marge par juge sert d'abord à le rendre **moins** péremptoire —
  c'est l'inverse de ce que le titre de cette note laisse attendre.
- **distilCamemBERT** (4 %) est dans le même cas.
- **CamemBERTa v2** est le vrai bénéficiaire : ses écarts au seuil ont une
  médiane de 2,58 point, juste au-dessus de la bande actuelle. Une marge de
  l'ordre de 0,6 point le ferait parler dans 70 % des cas.
- **mDeBERTa v3 est structurellement muet, et aucune marge ne l'en sort.** Son
  premier et son troisième quartile valent tous deux 50,0 : **la moitié de ses
  scores tombent exactement sur son seuil**, et la médiane de ses écarts vaut
  **0,18 point**. Le faire parler dans 70 % des cas demanderait une marge de
  **0,04 point**, c'est-à-dire trancher sur la deuxième décimale — exactement ce
  que la bande de neutralité existe pour interdire.

**Conséquence à assumer en codant** : après ce chantier, « l'accord des juges »
reposera sur trois voix au lieu d'une, pas sur quatre. Le silence de mDeBERTa
n'est pas un défaut de réglage, c'est ce que ce modèle répond sur ce matériau —
et l'écran doit continuer à le dire.

**Arbitrage en attente du mainteneur, exposé le 22 août 2026.**
Mesure du 20 août 2026, sur **836 avis réels**. **Rien n'est codé.**

## Ce que le code fait aujourd'hui

`AvisDeVerification.MARGE_DE_NEUTRALITE = 2.5` (`core/models.py:2255`) : un
juge dont le score tombe à moins de 2,5 points de son seuil est déclaré **sans
avis** (`tranche` rend False), et la fiche de preuve le dit au lieu de trancher.

**L'intention est juste, et il faut la garder.** Le commentaire du code la
défend bien : sans bande de neutralité, un « neutre » sincère bascule en
« confirme » ou « ne confirme pas » **sur la troisième décimale**. Afficher un
tirage au sort comme un verdict, dans un outil dont l'objet est la traçabilité,
est le pire défaut possible — il est invisible.

Le problème n'est pas la bande. C'est qu'**une seule bande sert quatre juges
dont les échelles n'ont rien à voir**.

## Le fait, mesuré

| juge | ce qu'il rend | forme de la distribution | muet |
|---|---|---|---|
| CamemBERTa v2 | `(P(ent) − P(contra) + 1)/2` | concentrée autour de 50 | **85 %** |
| mDeBERTa v3 | idem | concentrée autour de 50 | **85 %** |
| bge-m3 | `P(entailment)` brut | étalée, de 0,3 à 99,2 | **4 %** |

Les juges **à contradiction** rendent une différence de deux probabilités : par
construction, elle se serre autour de 0,5. Les 2,5 points de marge y avalent
l'essentiel de la distribution. `bge-m3`, qui rend une probabilité brute,
s'étale sur presque toute la plage et passe la bande sans effort.

## La conséquence, et c'est elle qui décide

**CamemBERTa v2 et mDeBERTa v3 sont les DEUX MEILLEURS juges par AUC appariée**
— et ils se taisent 85 % du temps.

Donc **l'accord affiché repose de fait sur `bge-m3` seul**, c'est-à-dire sur le
seul des quatre juges **qui n'a pas de classe contradiction**. Le signal que
tout le dossier défend — une source peut *contredire* l'affirmation, pas
seulement l'appuyer faiblement — est porté par le seul juge incapable de le
produire.

Ce n'est pas une panne : chaque pièce fait ce qu'on lui demande. C'est un défaut
de **composition**, et il est invisible à l'écran : la fiche montre trois juges
muets et un qui parle, ce qui ressemble à de la prudence.

## Les deux voies

### A. Une marge par juge

Chaque juge porte sa propre marge, calibrée sur sa distribution réelle.

- **Pour** : chaque score reste interprétable dans son échelle d'origine, rien
  n'est transformé, et les 836 avis déjà en base suffisent à calibrer.
- **Contre** : un réglage de plus par juge, à maintenir à chaque changement de
  modèle. Et une marge par juge est un chiffre qu'il faudra justifier — sinon
  c'est le même arbitraire, réparti en quatre.

### B. Une échelle commune

Normaliser les scores avant de comparer (rang, z-score sur la distribution
observée, ou recalage sur les quantiles).

- **Pour** : une seule marge, conceptuellement propre, et les juges deviennent
  comparables entre eux — ce que l'affichage prétend déjà faire.
- **Contre** : il faut choisir la transformation, et elle sera contestable ; un
  score normalisé n'est plus lisible seul (« 62 » ne veut plus rien dire
  cliniquement) ; et la normalisation dépend du corpus observé, donc elle
  bougera.

## Recommandation

**La voie A**, marge par juge. Moins élégante, mais chaque chiffre affiché reste
celui que le modèle a produit, et le réglage se lit directement sur la
distribution de chacun — qu'on a déjà. La voie B demande de décider ce que
« comparable » veut dire entre un juge à contradiction et un juge sans, ce qui
est un problème plus difficile que celui qu'on cherche à résoudre.

## Ce qu'il faut avant de coder

**Les distributions par juge, en tableau.** Elles ne sont pas dans ce document :
la mesure du 20 août donne les taux de mutisme et la forme, pas les quantiles.
Il faut, par juge : médiane, écart interquartile, et la part d'avis dans la
bande à 1, 2 et 3 points. Les 836 avis sont en base
(`AvisDeVerification`), le calcul ne coûte rien et n'appelle aucun modèle.

## Ce qui casse si on ne fait rien

Rien ne tombe. Mais la colonne « accord des juges » continue d'afficher un
accord qui n'en est pas un : trois silences et une voix, présentés comme un
consensus prudent. Et la tension entre juges — le signal posé le 20 août, celui
qui devait révéler les citations douteuses — reste **structurellement
inaccessible**, puisqu'il faut au moins deux juges qui parlent pour qu'il y ait
tension.
