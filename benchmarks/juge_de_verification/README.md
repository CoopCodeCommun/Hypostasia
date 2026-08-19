# Banc d'essai — le juge de vérification

Comparer des juges d'implication (NLI) sur des paires **déjà jugées**, sans rien réécrire.

> **Ce dossier ne contient aucun test automatisé.** `comparer_un_juge.py` est un script
> `__main__` qui appelle un vrai modèle — **c'est facturé** — et le dossier `benchmarks/`
> n'est pas une app Django : `manage.py test` ne le collecte pas. Même précédent, mêmes
> raisons que `benchmarks/extraction_format/`.
>
> Ce qui EST couvert par la suite : `front/tests/test_gel_de_l_etalon_du_juge.py` (la
> commande de gel), `core/tests/test_verification.py` (la cascade, la non-dégradation et
> la dichotomie).

## Pourquoi un étalon gelé

Les verdicts vivent dans une colonne **qu'on réécrit**. Le bouton « Vérifier les
citations » rejuge tout l'article, `verifier_les_citations_etalons` en fait autant dès
qu'une seule paire a perdu son verdict, et `--forcer` rejuge sans condition. Une mesure
qui ne vit que dans une colonne réécrivable n'est pas une mesure : c'est un état.

`etalon-du-juge.json` est donc la seule trace stable de ce qu'un juge a répondu — **et de
la question exacte qu'on lui a posée**. Ce n'est pas une fixture : rien ne le charge en
base, et le banc le lit à chaque exécution.

## Ce que le banc mesure

**L'accord, pas la vérité.** Ni le juge de référence ni le candidat ne détiennent la bonne
réponse. Ce que produit ce banc, c'est une matrice de désaccords — et un désaccord entre
deux juges sur une citation est en lui-même une information : c'est ce qui rend l'état
*contestable* plutôt qu'asséné.

### Commencer TOUJOURS par le plancher de bruit

Un juge ne se reproduit pas lui-même. Mesuré le 17 août : le modèle de référence rejouant
ses propres 145 paires ne retrouve que **77 %** de ses verdicts, à température 0, à trois
minutes d'écart — et le nombre de citations « vérifiées » a varié de **105 à 133 sur cinq
exécutions**.

**Mais ce plancher dépend du MODÈLE, pas du dispositif.** Les candidats mesurés le même jour
atteignent **95 %**, avec le même prompt et le même jeton imprévisible. Le jeton — la défense
anti-injection, tirée à chaque appel — interdit le déterminisme parfait, et rien de plus :
l'écart de 18 points vient du modèle, pas de lui.

**Conséquence : un taux d'accord avec l'étalon ne veut rien dire tant qu'on n'a pas ce
plancher.** Un candidat à 82 % n'est pas « moins bon » qu'une référence dont la propre
reproductibilité est de 77 %.

```bash
# le plancher de bruit d'un modèle : deux exécutions, comparées entre elles
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id> --enregistrer /tmp/run_a.json
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id> --reference /tmp/run_a.json
```

C'est **la stabilité** qui décide, pas l'accord : un verdict opposable qui change à chaque
relance n'est pas opposable.

## Geler l'étalon

```bash
docker exec -w /app hypostasia_web python manage.py geler_l_etalon_du_juge
```

Lecture seule : aucun appel de modèle, aucune écriture en base. La commande **exclut** les
paires dont la question a dérivé depuis leur verdict (bornes périmées, verbatim devenu
introuvable) et les compte à part : les geler produirait une comparaison entre deux
questions différentes.

## Rejouer un juge candidat

```bash
# les modèles et leur identifiant
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --lister

# le banc — APPELS FACTURÉS
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id_du_modele>
```

Le prompt, le jeton imprévisible et l'analyse de la réponse sont importés de
`core/services/verification.py`, **sans copie** : deux copies du prompt finiraient par
poser deux questions différentes, et la comparaison ne voudrait plus rien dire.

## Les mesures

| Date | Juge | Paires | Stabilité | Accord | Durée | Rapport |
|---|---|---|---|---|---|---|
| 2026-08-17 | `gemini-2.5-flash` (référence) | 145 | **77 %** | 72–88 % | 136–154 s | [stabilité des juges Gemini](2026-08-17_stabilite-des-juges-gemini.md) |
| 2026-08-17 | `gemini-3.1-flash-lite` | 145 | **95 %** | 81 % | **8 s** | idem — **juge retenu** |
| 2026-08-17 | `gemini-3.5-flash-lite` | 145 | 94 % | 82 % | 8 s | idem |
| 2026-08-17 | `mistral-small-latest` | 145 | **95 %** | **57 %** | 9 s | idem — stable et **beaucoup plus sévère** |
| 2026-08-17 | `ministral-3b-latest` | 145 | 89 % | 79 % | 8 s | idem — laisse tomber 1 à 4 paires sans verdict |
| 2026-08-17 | `gemini-2.5-flash-lite` | — | — | — | — | **404 : plus servi aux nouveaux comptes** |

Ranger ici le compte rendu de chaque comparaison, et ajouter sa ligne au tableau.

## Un juge LOCAL, à score continu — et un piège de protocole

`comparer_shieldstral.py` ne se range pas dans le tableau ci-dessus : il ne
mesure ni stabilité ni accord avec l'étalon, mais **l'AUC** — la probabilité
qu'une paire vraie reçoive un score plus haut qu'une paire fausse. C'est le
chiffre à lire ici, parce qu'il **ne dépend d'aucun seuil**, et que le seuil est
exactement ce que tout ce dossier a montré manquant.

| Date | Juge | Paires | Référence | Cadrage | AUC | Rapport |
|---|---|---|---|---|---|---|
| 2026-08-18 | ShieldStral 1.0 3B, local | 15 | relecture humaine | `separe` (correct) | **0,923** | [le cadrage fait tout](2026-08-18_shieldstral-le-cadrage-fait-tout.md) |
| 2026-08-18 | idem | 15 | idem | `ensemble` (fautif) | **0,538** | idem — ne classe rien |
| 2026-08-18 | idem | **145** | l'étalon gelé | `separe` | **0,734** | idem — **le 0,923 ne généralise pas** |

⚠️ **Sur l'étalon, ne lisez PAS l'accord.** Il porte 118 « soutient » pour 27
« ne_soutient_pas » : *accepter tout* donne déjà 118/145, et le « meilleur
seuil » que rend le banc n'est alors qu'un artefact de métrique. Et la
« vérité » y est un juge dont la reproductibilité mesurée est de **77 %** : un
accord parfait avec lui serait suspect, pas rassurant.

**Le piège, et il a coûté une conclusion publiée.** La fiche du modèle décrit un
triplet `<Instruct>` / `<Query>` / `<Document>` : la question va dans `Query`, le
texte à évaluer va dans `Document`. Mettre l'affirmation ET la source dans
`<Document>` fait tomber l'AUC de 0,92 à 0,54 — le modèle ne sait plus lequel des
deux textes il juge. **Ce n'est pas un réglage de prompt, c'est une erreur de
protocole**, et rien ne la signale : le modèle répond, simplement de travers.

Le banc rejoue **les deux** cadrages, exprès. Retirer le fautif laisserait le bon
sans point de comparaison.

> Ce banc n'appelle **aucune API** et ne coûte rien : le modèle (7,7 Go, poids
> Apache 2.0) tourne sur processeur, depuis le cache local. Compter environ deux
> minutes de temps processeur par paire.

## Les DEUX BORNES — à lire avant tout chiffre de ce dossier

**Mesurées le 19 août 2026.** Elles encadrent toute AUC produite ici, et les
ignorer fait conclure l'inverse de la mesure.

| borne | valeur | ce qu'elle est | comment la rejouer |
|---|---|---|---|
| **plafond** | **0,690** | `gemini-2.5-flash`, **le modèle qui a produit l'étalon**, rejouant les 145 paires contre ses propres verdicts gelés | `mesurer_le_plafond_de_l_etalon.py 2` — **facturé** |
| **baseline lexicale** | **0,889** | la part des mots de la source retrouvés dans l'affirmation, sans aucun modèle | imprimée par `comparer_un_encodeur.py` |

**Le plafond est SOUS la baseline.** Il faut donc lire les deux ensemble :

1. **Dépasser 0,690 ne prouve pas grand-chose** — la référence elle-même n'y
   arrive pas. Et la raison est mécanique : le protocole texte ne rend que
   **quatre crans**, et sur ces 145 paires **120 reçoivent exactement 70**. Un
   juge qui donne la même note à 83 % des paires ne peut pas les classer ; son
   AUC s'effondre sur les ex æquo. C'est une limite du **protocole**, pas de la
   tâche — et c'est l'argument le plus direct pour un juge à score continu.
2. **Ne pas dépasser 0,889 est le vrai constat.** Les deux références sont
   lexicalement **saturées** : le paragraphe a été écrit *à partir* de ses
   sources et en reprend le vocabulaire. Une AUC calculée contre elles **ne
   distingue pas un juge d'implication d'un `grep`** — et le `grep` est lui aussi
   déterministe, ce qui prive au passage la reproductibilité de sa valeur
   d'argument.

> **Ce qu'il faudrait pour trancher, et qui n'existe pas encore** : un jeu adverse
> à **recouvrement lexical constant** — les affirmations positives réelles,
> perturbées mécaniquement (un nombre changé, une négation insérée, deux entités
> permutées). La vérité y est connue *sans juge*, et seul un modèle qui comprend
> l'implication peut réussir. C'est déterministe et gratuit.

## Des ENCODEURS comme juges — `comparer_un_encodeur.py`

Sept modèles de 68 à 608 millions de paramètres, entraînés **pour cette tâche**,
qui tournent sur processeur en moins d'une seconde par paire — contre ~24 s pour
ShieldStral.

| Date | Juge | Paires | Réf. | Meilleur cadrage | AUC | ms/passe |
|---|---|---|---|---|---|---|
| 2026-08-19 | `lettucedect-610m-eurobert-fr` | 145 | étalon gelé | `qa` / `couverture` | **0,738** | 1063 |
| 2026-08-19 | `distilcamembert-base-nli` (68 M) | 145 | idem | `par_phrase` | **0,728** | **48** |
| 2026-08-19 | `mdeberta-v3-base-mnli-xnli` | 145 | idem | `par_phrase` | 0,723 | 229 |
| 2026-08-19 | `lettucedect-210m-eurobert-fr` | 145 | idem | `qa` / `couverture` | 0,710 | 266 |
| 2026-08-19 | `camembertav2-base-xnli` | 145 | idem | `par_phrase` | 0,692 | 179 |
| 2026-08-19 | `bge-m3-zeroshot` | 145 | idem | `par_phrase` | 0,665 | 338 |
| 2026-08-19 | `lettucedect-v2-mmbert-base` | 145 | idem | `nu` / `meilleure_phrase` | **0,529** | 280 |

Compte rendu complet, réserves comprises :
[des encodeurs contre l'étalon](2026-08-19_des-encodeurs-contre-l-etalon.md).

**Trois choses que ce banc a apprises et qui valent au-delà de lui :**

- **Le français déclaré n'est pas le français entraîné.** `lettucedect-v2-mmbert-base`
  revendique `fr` dans ses métadonnées, passe le contrôle d'orientation
  proprement, et **classe au niveau du hasard** (0,529, six combinaisons sur neuf
  sous 0,5). Les deux EuroBERT entraînés *sur* RAGTruth-FR le battent nettement.
- **Un tokeniseur peut se dégrader sans lever d'erreur.**
  `almanach/camembertav2-base-xnli` déclare `RobertaTokenizer` pour un vocabulaire
  **WordPiece** : `AutoTokenizer` découpe alors **caractère par caractère**, 109
  tokens au lieu de 11. Correctif : `PreTrainedTokenizerFast`.
- **Un contrôle d'orientation exige une MARGE, pas un signe.** Le 610m note la
  paire fausse 0,964 et la vraie 0,994 : il les *ordonne* sans les *séparer*, et
  passait « ✓ » avec une simple comparaison.

> **Le plancher de bruit des encodeurs est 100 %**, au bit près, sur toutes les
> combinaisons (jusqu'à 1305 scores comparés). C'est acquis par construction —
> aucun échantillonnage, aucun jeton imprévisible — et **cela ne les rend pas
> meilleurs** : le compteur de mots l'est aussi. Le déterminisme supprime un mode
> de panne, il ne dit rien de la qualité.
