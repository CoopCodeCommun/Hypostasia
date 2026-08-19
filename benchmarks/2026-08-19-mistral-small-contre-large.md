# Mistral Small contre Mistral Large — la chaîne étage par étage

**18-19 août 2026.** Base reconstruite de zéro (`docker compose down -v`),
LangExtract 1.6.0, températures à 0, juge constant (`mistral-small-latest`,
seuil 45).

**Ce qui rend cette mesure lisible** : à chaque étage, un seul paramètre change.
La rédaction a été comparée **sur les mêmes 149 extractions** ; l'extraction a
été comparée **sur les mêmes 6 notes**.

---

## 1. L'EXTRACTION — la taille du modèle n'y change presque rien

| modèle | extractions | **verbatim exact** | non verbatim | ancrées |
|---|---|---|---|---|
| `gemini-2.5-flash` *(mesure du 18 août, avant bascule)* | 112 | **100 %** | 0 | 112 |
| `mistral-small-latest` | 137 | **85 %** | 21 | 137 |
| `mistral-large-latest` | 134 | **87 %** | 18 | 134 |

**Payer 3,3× plus cher achète deux points de verbatim.** C'est dans le bruit.

**Le vrai écart n'est pas Small/Large, c'est Mistral/Gemini** : les deux Mistral
reformulent ~14 % de ce qu'ils présentent comme une citation, là où Gemini n'en
reformulait aucune. C'est un trait de famille, pas une affaire de taille.

**Ce que ça coûte, concrètement** : une extraction non verbatim ne se retrouve
pas dans sa source. Le contrôle de vérification la marque `INTROUVABLE` — la
chaîne de preuve est cassée — et c'est ce qui explique les **14 % de citations
introuvables** mesurés sur les deux jeux d'articles, à l'identique.

**Un effet de bord à connaître** : les deux Mistral ont **100 % d'ancrage**
(134/134 et 137/137). Les non-verbatim sont donc ancrées par l'**aligneur
flou** — celui qui est passé de `difflib` à **LCS** dans LangExtract 1.6.0. Avec
Gemini, ce chemin de code n'était **jamais** emprunté ; il produit désormais
~14 % des ancres. Le risque signalé dans `CHANGELOG/DEFAUTS-DIFFERES.md` est
passé de théorique à actif.

## 2. LA RÉDACTION — l'écart est massif, et ce n'est pas le style

Mêmes 149 extractions, même température, même juge. Seule la plume change.

| | caractères | renvois simples | **renvois groupés** | **liens créés** |
|---|---|---|---|---|
| wiki — **Small** | 6 097 | 10 | **7** (57 extractions dedans) | **10** |
| wiki — **Large** | 8 540 | **55** | **0** | **55** |
| synthèse — **Small** | 8 141 | 25 | **21** (50 dedans) | **25** |
| synthèse — **Large** | 7 895 | **72** | **0** | **72** |

**127 citations exploitables contre 35 — 3,6×.** Zéro citation inventée chez
l'un comme chez l'autre (`marqueurs_retires: []`).

### La cause : l'obéissance au format, pas la qualité de la prose

Le prompt exige des marqueurs **consécutifs** et le dit avec un exemple :

> `[[ext:N]]` … Plusieurs sources = plusieurs marqueurs consécutifs
> (`[[ext:12]][[ext:15]]`)

**Large obéit à la lettre** : `[[ext:14]][[ext:15]][[ext:16]][[ext:17]][[ext:18]]`.
**Small désobéit** : `[[ext:14, ext:15, ext:16, ext:17, ext:18, ext:19]]`.

Et le motif de l'indexeur, `\[\[ext:(\d+)\]\]`, ne les voyait pas : **107
citations perdues sur 142 produites**, plus **huit marqueurs bruts affichés en
clair** dans le HTML du wiki. Rien ne le signalait — l'indexeur dénonce
bruyamment un marqueur *halluciné*, mais il était **aveugle** à celui-là.

> **Corrigé le 19 août** : `normaliser_les_marqueurs_groupes` réécrit
> `[[ext:1, ext:2]]` en `[[ext:1]][[ext:2]]` en amont de tout, et le bilan
> **compte** les groupes réécrits — réparer en silence excuserait la
> désobéissance et on ne saurait plus quel modèle la commet.
> Voir `CHANGELOG/2026-08-19-le-repli-sur-les-marqueurs-groupes.md`.

**À la lecture, les deux prosés se valent.** Structurés, fluides, chaque
affirmation porte son renvoi. Ce n'est pas le style qui départage : c'est qu'un
article produit 127 preuves cliquables et l'autre 35 plus du balisage cassé.

## 3. LA FORCE DES CITATIONS — Large cite plus, et plus lâchement

Juge constant : `mistral-small-latest`, seuil 45.

| | citations | vérifiées | faibles | introuvables | degrés rendus |
|---|---|---|---|---|---|
| **Small** | 35 | **14** | 15 | 5 (14 %) | 0:1 · 40:14 · 70:13 · 100:1 |
| **Large** | 127 | **28** | 69 | 18 (14 %) | 0:12 · 40:57 · 70:28 · **100:0** |

**Deux fois plus de citations vérifiées en valeur absolue** — 28 contre 14.
C'est le chiffre qui compte pour un outil de synthèse sourcée.

**Mais Large cite plus lâchement** : 57 citations au cran 40 (« appuie de loin,
sans rien établir ») et **aucune à 100**.

> ⚠️ **La comparaison « 48 % contre 29 % de vérifiées » n'est PAS honnête**, et
> il faut le dire : les 35 citations de Small sont celles qui ont survécu au bug
> de format — un sous-ensemble **non aléatoire**. Ses 107 citations groupées
> n'ont jamais été jugées. Seul le compte **absolu** de vérifiées se compare.

**Le taux d'introuvables est identique — 14 % — chez les deux.** C'est mécanique
et c'est un bon contrôle : les deux ont rédigé sur les **mêmes** extractions.
Ça confirme qu'`INTROUVABLE` est un défaut de l'**extracteur**, jamais du
rédacteur.

## 4. Les quatre crans, confirmés une troisième fois

Degrés rendus par le juge, sur données de production :

- articles de Small : `{0: 1, 40: 14, 70: 13, 100: 1}`
- articles de Large : `{0: 12, 40: 57, 70: 28, 100: 0}`

**Aucune valeur intermédiaire, nulle part.** Les quatre crans sont une propriété
du protocole texte, pas du sujet — mesurée d'abord sur quinze paires d'une seule
affirmation, puis sur 29 citations réelles, puis sur 97. C'est ce qui justifie
d'avoir stocké un **flottant** : le juge local à logits, lui, rend 8,5 · 37,8 ·
46,9 · 75,5 · 99,0.

## 5. Les tarifs, relevés le 18 août sur `mistral.ai/pricing/api/`

| modèle | input | output |
|---|---|---|
| Mistral Small 4 | 0,15 $ | 0,60 $ |
| **Mistral Large 3** | **0,50 $** | **1,50 $** |
| Mistral Medium 3.5 | 1,50 $ | 7,50 $ |
| Ministral 3 (3B) | 0,10 $ | 0,10 $ |
| *(rappel)* gemini-2.5-flash | 0,30 $ | 2,50 $ |

Large coûte **×3,3 en entrée, ×2,5 en sortie** par rapport à Small — et reste
**moins cher en sortie que le Gemini qu'on a quitté**.

---

## Ce que j'en conclus

### ⚠️ Le repli retourne la conclusion sur la rédaction

Le texte **déjà produit** par Small, repassé dans `normaliser_les_marqueurs_groupes`
— **sans un seul appel de modèle** :

| | avant | après repli | gain |
|---|---|---|---|
| wiki | 10 | **67** | +57 (7 groupes) |
| synthèse | 25 | **75** | +50 (21 groupes) |
| **total** | **35** | **142** | **+107** |

**Small produit 142 citations, Large 127.** Une fois le format réparé, **Small
en cite PLUS que Large** — et il coûte trois fois moins cher.

L'avantage de Large tenait **entièrement** à un défaut de notre indexeur, pas à
une infériorité de Small.

| étage | recommandation |
|---|---|
| **Extraction** | **rester sur Small.** Large n'achète que 2 points de verbatim pour 3,3× le prix. Le problème des 14 % non verbatim est un trait Mistral que la taille ne corrige pas — c'est le **prompt d'extraction** qu'il faudrait éprouver, ou Gemini qu'il faudrait reconsidérer |
| **Rédaction** | **rester sur Small, sous réserve.** Il cite désormais 142 contre 127, pour un tiers du prix. Ce qui n'est PAS mesuré : la FORCE de ces 142 citations. Les 107 récupérées n'ont jamais été jugées |
| **Juge** | **rester sur Small.** Son métier est d'être petit, rapide et bon marché — 145 paires en 9 s |

**Ce qui reste à éprouver**, et que cette mesure ne dit pas :

1. **La force des 142 citations de Small.** C'est la mesure qui manque, et la
   seule qui puisse trancher : produire à nouveau avec Small, repli actif, et
   faire juger. Elle écrasera les articles de Large — c'est un arbitrage.
2. **Le nombre de citations n'est pas la qualité du sourçage.** Large cite plus
   lâchement (57 crans à 40, aucun à 100) ; Small pourrait faire de même une
   fois ses groupes récupérés.
3. **Une seule passe par condition**, deux articles, un corpus.
4. Le juge est un Mistral qui juge du Mistral. Le second avis de ShieldStral,
   indépendant, est mesuré à part.

### La leçon de méthode

**J'ai failli recommander un modèle trois fois plus cher pour corriger un bug
de six lignes chez nous.** L'écart de 3,6× entre les deux plumes était réel et
mesuré — et il ne disait rien de la qualité des modèles. Avant d'attribuer un
écart à un modèle, vérifier qu'il ne vient pas de l'outil qui le mesure.
