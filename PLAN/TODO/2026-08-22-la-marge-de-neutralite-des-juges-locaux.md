# La marge de neutralité fait taire les deux meilleurs juges

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
