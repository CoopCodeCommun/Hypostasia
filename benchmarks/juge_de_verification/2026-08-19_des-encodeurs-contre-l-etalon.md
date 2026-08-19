# Sept encodeurs contre l'étalon — et deux bornes qui changent la lecture du dossier

**19 août 2026.** Mesure locale, sur processeur, sans clé et sans réseau une fois les
poids en cache. Rejouable : `benchmarks/juge_de_verification/comparer_un_encodeur.py`.

Le plafond, lui, a coûté quelques centimes :
`benchmarks/juge_de_verification/mesurer_le_plafond_de_l_etalon.py`.

---

## Ce que cette journée établit, en trois phrases

1. **L'étalon gelé ne peut pas être prédit au-delà de 0,690** — c'est le score de
   `gemini-2.5-flash`, qui l'a produit, contre ses propres verdicts. Et ce plafond est bas
   pour une raison de **protocole**, pas de difficulté : le juge texte ne rend que quatre
   crans, et **120 paires sur 145 reçoivent exactement 70**.
2. **Un recouvrement de mots obtient 0,889** sur ce même étalon, et **0,981** sur les
   quinze paires relues à la main. Les deux références sont lexicalement saturées : une
   AUC calculée contre elles ne distingue pas un juge d'implication d'un `grep`.
3. **Quatre juges dépassent le plafond, aucun ne dépasse le compteur de mots.** Le
   meilleur encodeur égale ShieldStral pour **vingt-trois fois moins cher**.

**Conclusion de gouvernance : ce banc ne permet de retenir aucun juge.** Il permet de
savoir ce qu'il faudrait mesurer pour pouvoir en retenir un, et c'est déjà davantage que
ce que le dossier savait ce matin.

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

## Les candidats

*(tableau complet ci-dessous, après la seconde campagne)*

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

*(résultats des candidats : voir la section suivante)*

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
