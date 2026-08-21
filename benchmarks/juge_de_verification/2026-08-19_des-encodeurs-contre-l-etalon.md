# Sept encodeurs contre l'étalon — et deux bornes qui changent la lecture du dossier

**19 août 2026.** Mesure locale, sur processeur, sans clé et sans réseau une fois les
poids en cache. Rejouable : `benchmarks/juge_de_verification/comparer_un_encodeur.py`.

Le plafond, lui, a coûté quelques centimes :
`benchmarks/juge_de_verification/mesurer_le_plafond_de_l_etalon.py`.

> ## ⚠️ LE JEU ADVERSE FUIT PAR LA NÉGATION — relecture du 19 août au soir
>
> Ce rapport présente le jeu adverse comme « la seule mesure qui tranche », au
> motif que le recouvrement de mots y vaut **0,500 exactement**. C'est vrai, et
> c'est vérifié. **Mais un autre comptage de surface y réussit très bien.**
>
> Mesuré en rejouant le jeu (273 paires, aucun modèle chargé) :
>
> | prédicteur trivial | AUC globale | **AUC appariée** |
> |---|---|---|
> | **compteur de « ne / n' / pas / aucun / jamais / ni / non »** | **0,776** | **0,962** |
> | nombre de mots de l'affirmation | 0,545 | 0,904 |
> | recouvrement de mots source→affirmation | 0,500 | 0,500 |
> | *(rappel)* meilleur juge, `mdeberta` | 0,743 | 0,853 |
>
> **Un compteur de négations bat tous les juges mesurés.** La cause est dans la
> construction : **97 % des affirmations fausses portent une marque de négation,
> contre 42 % des vraies** — parce que toutes les paires perturbées sont fausses,
> toutes les vraies non perturbées, et que la perturbation dominante (114 paires
> sur 156) est une négation.
>
> **Ce qui tombe** : la preuve *positive* que ces quatre juges « vérifient ».
> Une AUC de 0,74 sur ce jeu est compatible avec le biais NLI bien documenté
> « marqueur de négation ⇒ contradiction », sans aucune compréhension de la
> source.
>
> **Ce qui tient** : la conclusion *négative*. Écarter les deux LettuceDetect
> français reste fondé — et l'est même davantage : ils échouent alors qu'un
> indice de surface exploitable était à leur portée.
>
> **Ce qu'il faudrait pour trancher** : des perturbations qui n'ajoutent aucun
> marqueur de négation (substitution d'entité vérifiée, inversion de relation,
> changement de portée), ou un jeu où les affirmations vraies en portent autant
> que les fausses.

---

## Ce que cette journée établit

**1. Les deux références du dossier sont lexicalement saturées.** Un simple recouvrement
de mots obtient **0,889** sur l'étalon gelé et **0,981** sur les quinze paires relues à la
main — au-dessus de ShieldStral (0,734 et 0,923) et de tous les encodeurs. Une AUC contre
elles **ne distingue pas un juge d'implication d'un `grep`**.

**2. L'étalon ne peut pas être prédit au-delà de 0,690.** C'est le score de
`gemini-2.5-flash`, qui l'a produit, contre ses propres verdicts. Le plafond est bas pour
une raison de **protocole** et non de difficulté : le juge texte ne rend que quatre crans,
et **120 paires sur 145 reçoivent exactement 70**.

**3. Un jeu adverse à recouvrement rigoureusement constant tranche — et il renverse le
classement.** Les deux modèles LettuceDetect français, dont le **candidat n°1 du récap**,
y sont **au niveau du hasard ou en dessous** : leurs bons scores sur l'étalon étaient du
comptage de mots. Trois modèles NLI y atteignent **0,73 à 0,74**, à condition de lire
P(contradiction) — le seul signal qu'un compteur de mots ne peut pas imiter.

### Le classement final, sur le jeu adverse corrigé

273 paires, 117 vraies et 156 fausses, **compteur de mots à 0,500 par construction**.
« appariée » compare les versions d'une **même** paire — c'est la métrique de ce jeu.

| candidat | meilleure combinaison | AUC | **appariée** | négation | quantif. |
|---|---|---|---|---|---|
| `mdeberta-v3-base-mnli-xnli` | `directe` / `moins_contradiction` | **0,743** | 0,840 | **0,764** | **0,695** |
| `bge-m3-zeroshot` | `directe` | 0,737 | 0,801 | 0,760 | 0,662 |
| `camembertav2-base-xnli` | `directe` / `moins_contradiction` | 0,728 | **0,853** | **0,788** | 0,548 |
| `distilcamembert-base-nli` | `directe` / `moins_contradiction` | 0,656 | 0,737 | 0,675 | 0,603 |
| `lettucedect-v2-mmbert-base` | `qa` / `meilleure_phrase` | 0,630 | 0,763 | — | — |
| `lettucedect-210m-eurobert-fr` | `resume` / `pire_token` | **0,516** | 0,667 | 0,516 | 0,517 |
| `lettucedect-610m-eurobert-fr` | `qa` / `couverture` | **0,481** | 0,308 | **0,492** | 0,459 |
| **recouvrement de mots** | — | **0,490** | **0,500** | 0,500 | 0,500 |

### Ce qu'on peut en retenir, et ce qu'on ne peut pas

**Une liste courte est justifiée** : `mdeberta-v3-base-mnli-xnli`, `bge-m3-zeroshot` et
`camembertav2-base-xnli`, tous en cadrage `directe`, deux d'entre eux avec le signal de
contradiction. Ils tournent en **145 à 160 ms par paire** en régime établi, contre
~24 000 ms pour ShieldStral. `distilcamembert` suit, à **42 ms**.

**Ils sont branchés depuis le 19 août** — voir
`CHANGELOG/2026-08-19-quatre-juges-locaux.md`. Ce qui le justifie n'est pas un score
élevé dans l'absolu, c'est qu'ils **dépassent le compteur de mots là où l'étalon gelé ne
permettait pas de le dire**, et qu'ils coûtent deux ordres de grandeur de moins.

**Ce que cela ne démontre toujours pas.** Le jeu adverse n'éprouve que **deux types
d'erreur** — négation et quantificateur. Il reste à faire ce que le dossier réclame
depuis le début : une référence humaine à grande échelle.

**Ce qui est en revanche acquis, et qui ne l'était pas ce matin :** on ne retiendra pas
les deux LettuceDetect français, et on sait pourquoi.

---

## Les deux bornes

| borne | valeur | ce qu'elle mesure |
|---|---|---|
| **plafond** | **0,690** | `gemini-2.5-flash` rejouant les 145 paires contre ses verdicts gelés |
| **baseline lexicale** | **0,889** | part des mots (> 3 caractères) de la source retrouvés dans l'affirmation |

**Le plafond est sous la baseline, et ce n'est pas une coquille.** Les deux se lisent
ensemble :

- **dépasser 0,690 ne prouve rien** — la référence elle-même n'y parvient pas ;
- **ne pas dépasser 0,889 est le vrai constat** — et personne n'y parvient.

### Pourquoi le plafond est si bas

Les degrés rendus par `gemini-2.5-flash` le 19 août, sur les 145 paires :

```
{40: 12, 70: 120, 90: 3, 100: 10}
```

**Quatre valeurs, et 83 % des paires sur une seule.** Un juge qui donne la même note à
120 paires ne peut pas les classer : l'AUC s'effondre sur les ex æquo, mécaniquement.
C'est la troisième fois que les quatre crans sont constatés — après les quinze paires du
18 août et les vingt-neuf de la campagne live — et c'est ici qu'on en mesure le coût.

**C'est une limite du protocole texte, pas de la tâche.** Et c'est l'argument le plus
direct qu'on ait pour un juge à score continu : un encodeur rend un flottant, pas un cran.

### Ce que la distribution des crans dit du SOUS-NOTAGE

Le constat posé le 19 août — *« le juge de production pose son cran 40 sur des
sources qui établissent pleinement une part du paragraphe, c'est-à-dire la
définition de son propre cran 70 ; systématique sur les paragraphes
multi-sources »* — trouve ici un élément **à charge du modèle, pas du prompt**.

| juge | corpus | crans rendus |
|---|---|---|
| `mistral-small` (production) | 29 citations live | `{0: 1, 40: 14, 70: 13, 100: 1}` — **48 % au cran 40** |
| `gemini-2.5-flash` | les 145 paires gelées | `{40: 12, 70: 120, 90: 3, 100: 10}` — **8 % au cran 40** |

**Les deux ont reçu le même prompt v3**, et l'étalon est précisément un corpus
multi-sources (2 à 15 sources par affirmation, 23 affirmations). Le prompt sait
donc parfaitement faire produire le cran 70 sur des paragraphes multi-sources :
`gemini` y met 83 % des paires. **Ce n'est pas la question qui pousse au cran 40,
c'est `mistral-small`.**

> **La réserve, et elle est réelle** : deux corpus différents, deux jours
> différents. Ce n'est pas une comparaison contrôlée — c'est un indice qui
> désigne le modèle plutôt que la consigne, et qui indique où chercher. Le
> trancher demanderait de faire juger **le même corpus** par les deux modèles.

Corollaire pour le seuil du second juge : ajuster le 38 de ShieldStral sur
`mistral-small` serait encore plus mal fondé qu'on ne le pensait, puisqu'on
calerait un juge continu sur un juge dont la **prédictibilité propre plafonne à
0,690** et dont la sévérité n'est pas celle de la consigne.

### Deux réserves sur le plafond

- Les degrés d'aujourd'hui viennent du protocole **v3** (« dans quelle mesure », 0 à 100) ;
  les verdicts gelés viennent du **v2** binaire, figé la veille de l'addendum qui a établi
  que la question v2 était ambiguë. Ce n'est donc pas exactement « la référence contre
  elle-même » : c'est la référence sous la question d'aujourd'hui contre ses verdicts
  d'hier.
- `Gemini 2.5 Flash` est à **température 0,7** dans le référentiel, et l'étalon a été
  produit à cette température. Une exécution est un tirage — le 17 août, cinq exécutions
  ont rendu de 105 à 133 verdicts positifs.

### Pourquoi la baseline lexicale n'est pas un artefact

Le paragraphe de synthèse a été **écrit à partir** des sources qui le soutiennent : il en
reprend le vocabulaire. Le recouvrement est donc informatif *par construction du corpus*,
et il le reste quel que soit le seuil de longueur des mots (0,869 à 0,889 pour des mots de
1 à 5 caractères minimum).

Elle est en outre **déterministe et gratuite** — ce qui prive au passage le déterminisme
des encodeurs de sa valeur d'argument : le compteur de mots est lui aussi reproductible à
100 %, et il score plus haut.

---

## Ce que le protocole a coûté à établir, avant toute mesure

Trois pièges, tous silencieux, tous rencontrés avant d'obtenir un seul chiffre.

### Le cadrage fait tout — troisième confirmation

Sur l'exemple publié par la carte de `lettucedect-210m-eurobert-fr-v1` :

| cadrage | ce que le modèle répond |
|---|---|
| `nu` — la source et l'affirmation, rien autour | il ne signale **rien** |
| `resume` — gabarit « Résume le texte suivant » | P = 0,571, spans bancals |
| `qa` — gabarit « Réponds brièvement à la question » | **P = 0,951, le span exact de la carte** |

Les trois cadrages restent dans le banc, comme les deux cadrages de ShieldStral y restent.

### Un tokeniseur mal déclaré, qui dégrade sans erreur

`almanach/camembertav2-base-xnli` — le « meilleur score français » du récap, XNLI-fr 85,6 —
annonce `RobertaTokenizer` dans son `tokenizer_config.json` alors que son `tokenizer.json`
porte un vocabulaire **WordPiece**. `AutoTokenizer` suit la déclaration, se retrouve sans
table de fusions, et découpe **caractère par caractère** : 109 tokens là où il en faut 11.
Aucune erreur, aucun avertissement. `PreTrainedTokenizerFast` lit le `tokenizer.json`
directement et rend le bon découpage.

### Le contrôle d'orientation, et pourquoi un signe ne suffit pas

Les deux modèles EuroBERT ne déclarent pas leurs étiquettes (`LABEL_0` / `LABEL_1`) : rien
dans leur config ne dit laquelle vaut « non soutenu ». Une étiquette inversée ne lève
aucune erreur — elle rendrait une AUC symétrique, 0,27 au lieu de 0,73, qui aurait l'air
d'un mauvais modèle plutôt que d'une erreur de lecture.

Le banc confronte donc chaque candidat à une paire dont la réponse est connue (source à
« 67 millions », affirmation à « 69 millions ») **et exige un écart minimal de 0,10**. Un
signe ne suffit pas : `lettucedect-610m-eurobert-fr` note la paire fausse **0,964** et la
vraie **0,994** — il les *ordonne* sans les *séparer*.

---

## Les candidats, sur les 145 paires gelées

Meilleure combinaison de chacun. Les tableaux complets — 9 combinaisons pour les
modèles à spans, 4 pour les NLI — sont dans la sortie du banc.

| candidat | meilleure combinaison | AUC | strat. | macro | orientation | ms/passe |
|---|---|---|---|---|---|---|
| `mdeberta-v3-base-mnli-xnli` | `par_phrase` / `moins_contradiction` | **0,758** | 0,688 | 0,762 | +0,607 | 216 |
| `lettucedect-610m-eurobert-fr` | `qa` / `couverture` | *0,738* | 0,758 | 0,825 | **refusé, +0,031** | 1102 |
| `distilcamembert-base-nli` (68 M) | `par_phrase` | 0,728 | 0,703 | 0,787 | +0,933 | **47** |
| `lettucedect-210m-eurobert-fr` | `qa` / `couverture` | 0,710 | 0,750 | 0,641 | +0,157 | 277 |
| `camembertav2-base-xnli` | `par_phrase` / `moins_contradiction` | 0,706 | 0,734 | 0,797 | +0,922 | 177 |
| `bge-m3-zeroshot` | `par_phrase` | 0,665 | 0,750 | 0,763 | +0,983 | 366 |
| `lettucedect-v2-mmbert-base` | `qa` / `meilleure_phrase` | 0,529 | **0,797** | **0,835** | +0,124 | 275 |
| — *ShieldStral 3B (18 août)* | *`separe` / large* | *0,734* | *—* | *—* | *—* | *~24 000* |
| — **recouvrement de mots** | — | **0,889** | **0,867** | 0,833 | — | ~0 |
| — *plafond de l'étalon* | — | *0,690* | *—* | *—* | *—* | — |

### Quatre choses que ce tableau dit

**Le signal de contradiction paie, et il était jeté.** Ne lire que P(entailment) revient à
ignorer la seule information qu'un compteur de mots ne peut pas produire : deux textes qui
se contredisent partagent leur vocabulaire. En soustrayant P(contradiction), `mdeberta`
passe de 0,723 à **0,758** et `camembertav2` de 0,692 à 0,706. Il ne coûte **aucune passe
avant supplémentaire** — les logits sont déjà là.

**Le meilleur score brut est refusé au contrôle d'orientation.** `lettucedect-610m`, le
candidat n°1 du récap, note la paire fausse 0,964 et la vraie 0,994. Il les *ordonne* sans
les *séparer*, et sur l'exemple publié par sa propre carte il ne signale **rien**. Ses
chiffres ne sont **pas concluants** : on ne peut pas départager « modèle peu sensible » de
« implémentation native divergente », parce que `trust_remote_code=True` échoue sous
`transformers` 5.14.1 (`KeyError: 'default'`). Le 210m, lui, reproduit l'exemple de sa
carte au span près.

**Une AUC globale basse peut cacher un défaut de CALIBRATION, pas de jugement.**
`lettucedect-v2-mmbert-base` a une AUC globale de 0,529 — la pire du tableau. Sa
stratifiée est de **0,797**, macro **0,835**, jamais sous 0,40 sur aucun groupe : il classe
correctement les sources **à l'intérieur** d'un paragraphe, mais ses scores ne sont pas
comparables **entre** paragraphes. C'est un défaut de **calibration**, et c'est exactement
ce que la métrique stratifiée existe pour distinguer.

> **L'entraînement français n'a pas décidé, et c'est l'inverse de ce qu'on attendait.** Les
> deux modèles entraînés *sur* RAGTruth-**FR** dominent ce tableau (0,738 et 0,710) et
> s'effondrent au hasard sur le jeu adverse ; le modèle **multilingue**, dernier ici,
> y atteint 0,661. Ce que le tableau ci-dessus classe, c'est l'aptitude à épouser une
> référence lexicalement saturée — pas l'aptitude à vérifier.

**Le rapport qualité/prix n'est pas où on l'attendait.** `distilcamembert-base-nli`, 68
millions de paramètres, atteint 0,728 à **47 ms la passe** — soit **500 fois moins cher**
que ShieldStral pour un score équivalent. Sur les 15 paires relues à la main, avec le
signal de contradiction, il atteint **0,923** : exactement le score de ShieldStral 3B.

### La réserve qui interdit de classer sur la stratifiée

L'AUC stratifiée repose sur **128 couples dans 11 affirmations**, et **56 de ces couples —
44 % — viennent d'un seul paragraphe**. Son étendue par groupe va de 0,00 à 1,00 chez
presque tous les candidats. **Un écart inférieur à 0,1 n'y est pas résolu**, et aucun
classement ne doit s'y appuyer. Elle sert à repérer un décalage franc entre global et
stratifié — comme celui de mmBERT — pas à départager deux candidats.

---

## Le jeu adverse — la seule mesure qui tranche

Aucune AUC contre les deux références ne démontre qu'un candidat *vérifie* : tant que le
compteur de mots les prédit à 0,889 et 0,981, un score élevé reste compatible avec un juge
qui ne fait que compter du vocabulaire commun.

Ce banc porte donc un **troisième jeu**, construit pour que le compteur de mots n'y puisse
rien. On prend chaque paire que la référence déclare « soutient », et on **nie
l'affirmation** — dans la phrase que la source établit, choisie par recouvrement lexical,
et non dans une phrase au hasard : nier une phrase sans rapport laisserait la paire
soutenue au sens large, et l'étiquette mentirait.

La négation **n'enlève aucun mot** et n'ajoute que « ne » / « n' » et « pas », tous sous
quatre caractères, donc invisibles pour le compteur. La vérité, elle, bascule.

**Vérifié : sur les 114 paires transformables, le recouvrement de mots rend un score
rigoureusement identique avant et après — donc une AUC de 0,500 exactement.**

| propriété du jeu adverse | valeur |
|---|---|
| paires | **228** (114 positives, 114 négatives) — **équilibré**, contrairement à l'étalon |
| positives de l'étalon transformables | 114 sur 118 |
| recouvrement identique avant/après | **114 / 114** |
| **AUC du compteur de mots** | **0,500** |

Tout ce qui dépasse 0,5 sur ce jeu est une détection qu'un `grep` ne peut pas produire.
C'est la seule affirmation de ce genre que le dossier puisse soutenir.

### Deux perturbations sur quatre étaient invalides, et la mesure les a trouvées

Le jeu a d'abord porté **quatre** perturbations. L'inspection des textes produits en a
écarté deux — et sans elle, deux conclusions fausses auraient été publiées.

| perturbation | verdict | ce que l'inspection a montré |
|---|---|---|
| **négation** | ✅ valide | 114 paires |
| **quantificateur** | ✅ valide | 40 paires — « permettent » → « empêchent » contredit bien la source |
| ~~entités~~ | ❌ **écartée** | elle échangeait « Open » et « Badges », deux morceaux du **même** nom composé : « Les Badges Open » est une coquille, pas une affirmation fausse. **Tous** les modèles y étaient au hasard, et ce hasard ne disait rien d'eux. Le fond n'est pas réglable : deux entités coordonnées s'échangent sans changer le sens, et en remplacer une ferait bouger le recouvrement — ce que ce jeu s'interdit. |
| ~~nombre~~ | ⚠️ **non mesurable** | elle changeait « 2010 » en « 2011 » sur une source disant « En 2011 » : elle **corrigeait** l'affirmation au lieu de la fausser. Corrigée — le nombre doit figurer dans la source et son remplaçant non, sous quatre caractères pour rester invisible au compteur — il ne reste que **2 cas sur 118**. Le corpus ne porte pas assez de nombres courts partagés. |

**L'invariant est maintenant vérifié paire par paire**, et les perturbations qui
déplacent le recouvrement sont écartées et comptées. Ce que le banc mesure repose donc
sur **deux types d'erreur indépendants**, pas quatre — et il le dit.

### Les trois renversements, et ils tiennent tous

#### 1. Les deux LettuceDetect français ne détectent rien

`lettucedect-610m-eurobert-fr` — le **candidat n°1 du récap**, celui qui « bat
GPT-4.1-mini de près de 11 points » — obtient **0,481**, donc **sous le hasard**, et
**0,308** en apparié. Le 210m obtient 0,516. Aucune de leurs neuf combinaisons ne
dépasse 0,52.

Or ils obtenaient 0,738 et 0,710 sur l'étalon gelé. **Ces scores-là étaient donc
compatibles avec du comptage de mots, et la mesure adverse montre qu'ils n'étaient rien
d'autre.** Sans le jeu adverse, on aurait retenu le 610m.

#### 2. Le cadrage gagnant s'inverse entre les deux jeux

| jeu | cadrage gagnant | pourquoi |
|---|---|---|
| étalon gelé | `par_phrase` — le maximum sur les phrases | la source n'établit qu'une part du paragraphe |
| **adverse** | **`directe` — le paragraphe entier** | prendre le maximum laisse une phrase **non perturbée** sauver la paire |

`mdeberta` fait **0,743** en `directe` contre **0,598** en `par_phrase` sur l'adverse,
et exactement l'inverse sur l'étalon. **L'agrégation qui épouse le mieux une référence
lexicalement saturée est la mauvaise pour vérifier.**

#### 3. La contradiction fait toute la différence, et elle était jetée

| candidat | `directe` seul | `directe` − P(contradiction) | gain |
|---|---|---|---|
| `mdeberta-v3-base-mnli-xnli` | 0,573 | **0,743** | **+0,170** |
| `camembertav2-base-xnli` | 0,585 | **0,728** | **+0,143** |
| `distilcamembert-base-nli` | 0,600 | 0,656 | +0,056 |

C'est la prédiction exacte de la relecture adverse : P(contradiction) est le **seul**
signal qu'un compteur de mots ne peut pas imiter, puisque deux textes qui se
contredisent partagent leur vocabulaire. Il ne coûte **aucune passe avant
supplémentaire** — les logits sont déjà là.

**Corollaire de structure** : les modèles à **spans** (LettuceDetect) n'ont pas de
classe « contradiction » — leur étiquetage « soutenu / non soutenu » confond l'*absence*
et la *négation*. C'est une limite d'architecture, pas de taille, et elle explique
vraisemblablement les deux échecs ci-dessus.

### La réserve, et elle est de taille

**Ce jeu n'éprouve que DEUX types d'erreur : la négation et le quantificateur.** Un
modèle peut les détecter et rester aveugle à un nombre changé ou à deux entités
permutées — et les deux perturbations qui devaient les couvrir se sont révélées
invalides. Les 0,743 et 0,728 ne disent pas « ce juge vérifie » : ils disent « ce juge
détecte une négation et une inversion de quantificateur là où un compteur de mots ne le
peut pas ». C'est beaucoup plus que ce que le dossier savait, et beaucoup moins qu'une
validation.

**Et le quantificateur est le plus fragile des deux** : 40 paires seulement, et
`camembertav2` y tombe à 0,548 alors qu'il est le meilleur sur la négation (0,788). Un
juge peut donc être excellent sur un type d'erreur et médiocre sur le suivant — c'est
exactement ce que la ventilation existe pour montrer, et exactement ce qu'un chiffre
unique aurait caché.

## Ce qui manque encore

1. **Une référence humaine à grande échelle.** Elle manque depuis le début du dossier. Les
   quinze paires relues portent sur **une seule** affirmation.
2. **Une référence produite à température 0**, pour que l'étalon cesse d'être un tirage.
3. **D'autres perturbations que la négation** — changer un nombre, permuter deux entités.
   La négation est la plus propre (recouvrement rigoureusement conservé) mais c'est **un
   seul** type d'erreur, et un modèle peut être bon sur elle et mauvais sur les autres.

---

## Ce que le récap proposait et que ce chantier n'a PAS fait

Le dossier de passation du 19 août suggérait six étapes. Trois ont été écartées,
et il vaut mieux dire pourquoi que laisser croire à un oubli.

| étape proposée | statut | pourquoi |
|---|---|---|
| Banc sur **PsiloQA** et **RAGTruth-FR** | **écartée** | ce sont des traductions automatiques de corpus anglais, et elles mesurent une *autre* tâche. Le budget est mieux placé dans le **jeu adverse à recouvrement constant** décrit plus haut, qui tranche la question que ce banc ne tranche pas. |
| Latence en **ONNX INT8** | **non faite** | la latence float32 mesurée (48 à 1063 ms/passe) est déjà largement sous la contrainte : le gain ×2 à ×4 annoncé n'ouvre aucune décision aujourd'hui. À reprendre le jour où un juge sera retenu. |
| **Calibrer le seuil** | **délibérément non faite** | tout ce dossier existe parce que le seuil était le problème. L'AUC s'en passe, et poser un seuil sur 145 paires dont la référence plafonne à 0,690 le sur-ajusterait. |
| Un **jeu de référence maison** de 100 à 200 paires annotées à la main | **manque toujours** | c'est le trou du dossier depuis le début, et les mesures d'aujourd'hui le rendent plus criant : la seule référence humaine porte sur **une** affirmation. |

## Rejouer

```bash
# les encodeurs — GRATUIT, hors réseau, rien en base
docker exec -w /app -e PYTHONPATH=/tmp/banc_deps hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_encodeur.py --tous --etalon \
    --sortie /app/benchmarks/juge_de_verification/encodeurs-etalon.json

# relire une campagne sans recharger un modèle
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_encodeur.py --etalon \
    --depuis /app/benchmarks/juge_de_verification/encodeurs-etalon.json

# le plafond — FACTURÉ (145 paires, 8 appels)
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/mesurer_le_plafond_de_l_etalon.py 2
```

`cmarkea/distilcamembert-base-nli` exige `sentencepiece`, absent de l'image ; il s'installe
à côté, sans toucher au conteneur :
`docker exec hypostasia_web pip install --target /tmp/banc_deps sentencepiece`.
