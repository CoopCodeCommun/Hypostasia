# Ce qui reste du verbatim introuvable — la question a changé de forme

> ## ✅ CODÉ le 30 août 2026 — la comparaison par les mots est en place
>
> `CHANGELOG/2026-08-30-le-verbatim-se-compare-par-les-mots.md`. Le contrôle
> verbatim a une **troisième passe** qui compare la suite des mots ; **42 des 45
> citations au fond intact** redeviennent vérifiables, **0 des 74 dont le fond
> avait bougé** n'est blanchie, et la non-régression est intacte (399/400).
>
> **La ponctuation structurante a été éprouvée avant de coder, et elle a changé le
> design.** Une première version ignorait toute la ponctuation : mesurée, elle
> blanchissait **17 parenthèses d'incise retirées sur 19** et **18 guillemets sur
> 64**. Les signes qui changent le sens sont donc **exigés**, à la classe près.
> Le banc les éprouve désormais à chaque exécution — **0 blanchie sur 225
> falsifications**.
>
> **Ce que cette note garde**, et qui n'est toujours pas fait : le **rejugement**
> des liens déjà `INTROUVABLE` (§ 3 ci-dessous — sans lui, les 42 le restent), et
> la **réingestion** des documents dont la donnée est fautive (§ 2, qui compte
> maintenant **cinq** défauts mesurés). Les règles T, G et L n'ont plus d'objet :
> la comparaison par les mots les englobe.

**Mesuré le 30 août 2026 sur la base de dev. Rien n'est codé, et la décision
appartient au mainteneur.** Mesure **gratuite** : aucun modèle appelé, aucune
écriture en base.

> ## ⚠️ D'abord : la question posée dans `PLAN/PASSATION.md` § 6 est PÉRIMÉE
>
> Elle demande « faut-il assouplir la comparaison du verbatim ? » et annonce que
> **34 des 60 `INTROUVABLE` (57 %)** ne tiennent qu'à une retouche de forme.
>
> **C'est fait depuis le 21 août 2026** (commit `08965de`, chantier
> `CHANGELOG/2026-08-20-la-preuve-dans-son-contexte.md`). Le contrôle verbatim a
> **deux passes** : la stricte, puis une seconde qui tolère trois retouches de
> forme — l'espace de ponctuation, le point final, la majuscule d'amorce
> (`_le_verbatim_est_present`, `core/services/verification.py:343`), avec 15
> tests dont les « ne doit JAMAIS » (`core/tests/test_verbatim_tolerant_a_la_forme.py`).
>
> La question qui reste est donc **plus étroite, et elle porte sur autre chose**.

## Ce que le code fait aujourd'hui

Le contrôle s'applique entre **l'extraction et sa note source**, jamais entre
l'article et la note : c'est `extraction.extraction_text` qu'on cherche dans le
texte des `ElementDocument` de la note (`core/services/verification.py:927`).

**Conséquence qu'il faut avoir en tête pour lire les chiffres** : un
`INTROUVABLE` n'accuse **ni le rédacteur ni le juge** — il accuse l'extraction,
ou l'ingestion qui l'a précédée. Et comme un article cite plusieurs fois la même
extraction, **une extraction fautive fait tomber tous ses liens** : les 119
liens ci-dessous viennent de **75 extractions distinctes**.

## L'état mesuré le 30 août 2026

| état des `SourceLink` | liens |
|---|---|
| `non_verifie` | 489 |
| `faible` | 470 |
| `verifie` | 387 |
| **`introuvable`** | **119** |
| **total** | **1 465** |

**119 sur 1 465, soit 8,1 % de tous les liens — et 12,2 % de ceux qui ont été
jugés.** Ils se concentrent : un seul article (« Wiki — les recherches sur la
logique… ») en porte 61, un autre 26.

**Les 119 ont été relus avec la règle d'aujourd'hui : aucun ne passe.** Ni
strictement, ni par les trois tolérances. Les 34 récupérables de la mesure du
19 août ont bien été récupérés ; ce qui reste est d'une autre nature.

## Le typage des 119 — ce qui les sépare de leur source

Typage par `benchmarks/extraction_format/typer_les_non_verbatim.py`, relancé le
30 août :

| catégorie | liens | extractions distinctes |
|---|---|---|
| **ponctuation** — tous les mots, dans l'ordre, d'un seul tenant | **45** | 29 |
| **saut** — un passage a été élidé sans le dire | 37 | 23 |
| **reformulation** — au moins un mot absent de la source | 37 | 23 |

Les 45 « ponctuation » sont ceux qui posent la question : **le fond est intact**,
et pourtant la chaîne de preuve est déclarée cassée. Voici ce qui les sépare de
leur source, caractère par caractère :

| écart | occurrences |
|---|---|
| un point ajouté, **jamais seul** (toujours combiné à un autre écart) | 18 |
| `-` de la source rendu `—` (tiret cadratin) | **17** |
| `"` de la source rendu `'` | **11** |
| un espace de la source en moins | 3 |
| un tiret de la source en moins | 3 |
| une parenthèse fermante ajoutée | 2 |

### La cause dominante est ENCORE notre ingestion — mais sur un autre caractère

Le correctif du 22 août (`_recoller`,
`hypostasis_extractor/services/ingestion_docling.py:512`) colle la ponctuation
basse au mot qui précède : `.,)]}»…`. **Le tiret n'y est pas.** Résultat, en
base :

```
source :   « des connaissances, un savoir -faire ou un savoir -être »
citation : « des connaissances, un savoir-faire ou un savoir-être »
```

Le modèle recolle le trait d'union, comme n'importe quel lecteur. Notre texte ne
le recolle pas, et la citation est déclarée introuvable. Idem pour
`peut -être`, `micro -certifications`.

**Ce que la base porte encore, mesuré le 30 août sur 1 413 éléments** — les
espaces avant `;` `:` `!` `?`, légitimes en typographie française, ne sont pas
comptées :

| famille | éléments | notes |
|---|---|---|
| espace avant un point (« territoire . ») | 22 | 4 |
| espace avant une virgule (« mot , ») | 47 | 5 |
| espace avant une parenthèse fermante | 106 | 6 |
| espace avant un tiret (« savoir -faire »), hors URL | 8 | 2 |

Le correctif du 22 août vit dans le **moteur** : il ne répare pas ce qui est
déjà en base. Ces éléments-là resteront tels quels tant qu'on ne réingère pas.

## Ce que chaque règle candidate récupérerait — simulé le 30 août

Chaque règle est appliquée **en plus** de la normalisation actuelle, aux 119
liens, sans rien écrire :

| règle candidate | récupère, seule |
|---|---|
| **T** — tous les tirets deviennent le même, et l'espace autour ne compte pas | **21** |
| **G** — le guillemet droit `"` et l'apostrophe droite `'` se valent | **11** |
| **L** — ligatures et accents ignorés (`œ`→`oe`, `î`→`i`) | 15 |
| V — une virgule finale ne compte pas | **0** |
| P — une parenthèse fermante finale ne compte pas | **0** |

| cumul | récupère | part des 119 |
|---|---|---|
| T + G | **32** | 27 % |
| T + G + V + P | 32 | 27 % |
| T + G + **L** | 47 | **39 %** |

**V et P rendent zéro, et c'est instructif** : la virgule et la parenthèse
n'apparaissent jamais **seules** dans un écart. L'intuition « il suffit
d'ignorer la ponctuation finale » est fausse ici — ces cas portent toujours un
second écart, qui reste.

**Il reste 72 liens (61 %) qu'aucune règle de forme ne rattrape** : ce sont les
sauts et les reformulations. Le fond a bougé, et le verdict `INTROUVABLE` est
juste.

## Un score de similarité réglerait-il tout ? — mesuré, et NON

**Question du mainteneur le 30 août 2026** : plutôt que des règles de forme une
par une, un algorithme de proximité de textes qui dirait « 99 % identique, c'est
bon ». L'idée est juste dans son intention, et **la mesure la réfute dans sa
forme** — mais elle mène à autre chose, qui marche.

### Ce qui a été mesuré

**Le banc est versionné** :
`benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py`, une
commande, aucun appel de modèle, aucune écriture en base :

```bash
docker exec -w /app hypostasia_web python \
    benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py
```

Score de similarité `difflib.SequenceMatcher` (bibliothèque standard) entre la
citation et la **meilleure fenêtre** de sa source. Ni `rapidfuzz` ni
`python-Levenshtein` ne sont installés — les adopter serait une dépendance de
plus, et ils changeraient la vitesse, pas la conclusion.

**Le jeu adverse a été fabriqué pour l'occasion** — mécanique, déterministe,
gratuit, exactement ce que `benchmarks/juge_de_verification/README.md` appelle
de ses vœux : 150 citations aujourd'hui **verbatim**, perturbées par une
négation insérée, un quantifieur inversé (« tous » → « aucun ») et **un chiffre
changé** (2011 → 2012).

| ce qu'on mesure | n | ratio min | médiane | **max** |
|---|---|---|---|---|
| **à récupérer** — les 45 « ponctuation », fond intact | 45 | **0,9577** | 0,9888 | 0,9960 |
| à rejeter — les sauts | 37 | — | 0,9546 | 0,9970 |
| à rejeter — les reformulations | 37 | — | 0,9892 | 0,9946 |
| à rejeter — **un chiffre changé** | 23 | — | 0,9806 | **0,9961** |
| à rejeter — une négation insérée | 58 | — | 0,9773 | 0,9910 |

**Les deux nuages se chevauchent, et aucun seuil ne les sépare** : la citation
honnête la plus abîmée vaut **0,9577**, la citation falsifiée la mieux notée vaut
**0,9970**.

| seuil | récupère | **blanchit** |
|---|---|---|
| 0,99 | 14 / 45 | 35 citations fausses |
| 0,98 | 39 / 45 | 68 |
| 0,95 | 45 / 45 | **122 sur 166** |

**Le cas qui tue l'idée est le plus petit de tous : un chiffre changé.**
`2011` → `2012`, c'est **un caractère sur cent cinquante** — ratio 0,9961, plus
haut que 24 des 45 citations honnêtes. Un seuil qui récupère la typographie
laisse donc passer une date falsifiée. Ce n'est pas un défaut de réglage :
**une similarité est unidimensionnelle**, elle additionne « trois signes de
ponctuation » et « une négation » dans le même nombre, alors que ces deux
écarts n'ont rien de comparable.

### Ce qui marche : comparer la SUITE DES MOTS, pas les caractères

L'intuition du mainteneur était bonne, mais l'unité de mesure ne l'était pas.
La règle qui sépare proprement est :

> **Les mots de la citation, dans l'ordre et sans trou, doivent se lire tels
> quels dans la source. Tout ce qui n'est pas un mot — espaces, points, tirets,
> guillemets, parenthèses — ne compte pas.**

Ce n'est pas un assouplissement flou : c'est un contrôle **plus strict sur ce
qui porte le sens** (les mots) et **indifférent à ce qui n'en porte pas** (la
typographie). Mesuré le 30 août :

| | résultat |
|---|---|
| les 45 « ponctuation » (fond intact) | **45 / 45 récupérées** |
| les 37 sauts | **0 / 37** blanchis |
| les 37 reformulations | **0 / 37** blanchis |
| 58 négations insérées | **0 / 58** blanchies |
| 11 quantifieurs inversés | **0 / 11** blanchies |
| 23 chiffres changés | **0 / 23** blanchis |
| coût | **3 ms** par citation (contre 0,6 ms aujourd'hui) — négligeable devant un juge |

Elle **remplace** les règles T, G et L de la section précédente, et elle fait
mieux : 45 récupérations au lieu de 32, sans la règle L qui blanchissait des mots
différents. Les tirets, les guillemets, les ligatures et les points deviennent
sans objet — ils ne sont pas des mots.

### Les trois choses à traiter avant d'y aller, et aucune n'est un obstacle

> ✅ **Les trois sont traitées** (30 août 2026). La garde de fin est **réutilisée
> telle quelle** au lieu d'être réécrite ; la garde des chiffres est portée par
> les signes structurants et **verrouillée par un test**, faute de cas en base ;
> les 8 citations refusées venaient des signes de **bord**, qui ne comptent plus.
> Non-régression finale : **399/400, identique à l'ancienne règle**.

**1. La garde de la marque de fin doit être portée explicitement.** C'est le seul
endroit où la comparaison par mots est **moins** sûre que le contrôle actuel :
`?` remplacé par `.` ne change aucun mot. Le code d'aujourd'hui a déjà cette
garde (`MARQUES_DE_FIN_DE_PHRASE`, `_l_occurrence_ne_coupe_pas_une_marque_de_fin`)
et son commentaire dit pourquoi. Le prototype du 30 août n'en attrape que 2 sur 5
— c'est un travail de finition, pas une inconnue.

**2. La garde des chiffres reste nécessaire, et elle n'a pas pu être éprouvée.**
`_ecraser_l_espace_de_ponctuation` protège « les niveaux 3, 5 et 8 » de se lire
« 3,5 ». Une comparaison par mots découpe `3,5` en deux mots `3` et `5` et
recréerait le défaut. **Aucune citation de la base ne porte ce cas** : la mesure
est donc vide, pas rassurante. Un test l'attend.

**3. Le prototype refuse encore 8 citations valides sur 400** (391 contre 399
aujourd'hui). Elles viennent du même endroit que la garde 1. À régler avant de
brancher quoi que ce soit — et à verrouiller par un test de non-régression sur
l'ensemble des liens déjà `verifie` ou `faible`.

### Ce que cette mesure a découvert au passage : un TROISIÈME défaut d'ingestion

En cherchant pourquoi la comparaison par mots refusait des citations valides, on
tombe sur des mots **soudés** dans la source :

```
source :   « comités constituants et participation citoyenneAucun parlementaire »
citation : « … et participation citoyenne »
```

**83 éléments sur 1 413, dans 13 notes.** Deux blocs recollés sans séparateur.
Le contrôle actuel ne le voit pas — un test de sous-chaîne accepte une citation
qui s'arrête **au milieu d'un mot** de la source. La comparaison par mots, elle,
le refuse, et c'est ce refus qui a révélé le défaut.

La parade retenue dans le prototype : **tolérer que le premier et le dernier mot
soient un suffixe / un préfixe de leur voisin dans la source, jamais un mot du
milieu.** Aux extrémités, une citation honnête peut légitimement s'arrêter dans
un mot soudé ; au milieu, accepter un mot partiel serait accepter un autre mot.
Avec cette tolérance, la non-régression passe de 346 à 391 sur 400.

**Mais la vraie réparation est en amont** — c'est le troisième défaut d'ingestion
de ce dossier, après l'espace avant ponctuation (corrigé le 22 août) et le tiret
détaché (non corrigé). Il rejoint la question 4 : faut-il réingérer ?

## Ce qu'il faut trancher, et ce que chaque option déplace

> Les règles T, G et L de la section « ce que chaque règle candidate
> récupérerait » **restent mesurées, mais elles ne sont plus la voie
> recommandée** : la comparaison par la suite des mots les englobe toutes les
> trois, récupère 45 liens au lieu de 32, et n'a pas le défaut de L. Elles gardent
> leur intérêt comme **repli minimal** si la voie par les mots est jugée trop
> lourde.

**1. Par les mots, ou deux règles de plus ?** ⚖️ **TRANCHÉ ET CODÉ le 30 août
2026 : par les mots.** Le tableau comparatif qui vivait ici a été remplacé par la
mesure réelle — voir l'encart de tête et le CHANGELOG. Les règles T, G et L
n'ont plus d'objet.

**Ce que le chantier a établi et qui n'était pas prévu** : le risque que cette
note signalait comme *non mesuré* — la ponctuation structurante — **était réel et
sérieux**. Ignorer toute la ponctuation blanchissait 17 parenthèses d'incise
retirées sur 19. Les signes qui portent le sens sont donc comparés, à la classe
près. **Le risque a été mesuré avant de coder, et c'est ce qui a fait le design.**

**2. Faut-il réingérer les documents déjà en base ?** Le dossier compte
maintenant **trois** défauts d'ingestion, tous mesurés le 30 août :

| défaut | éléments | notes | corrigé dans le moteur ? |
|---|---|---|---|
| espace avant un point (« territoire . ») | 22 | 4 | ✅ 22 août |
| espace avant une virgule (« mot , ») | 47 | 5 | ✅ 22 août |
| espace avant une parenthèse fermante | 106 | 6 | ✅ 22 août |
| **tiret détaché** (« savoir -faire »), hors URL | 8 | 2 | ❌ |
| **mots soudés** (« citoyenneAucun ») | **83** | **13** | ❌ |

Les deux derniers ont été **découverts par le chantier du 30 août**, et la
comparaison par les mots les **absorbe** — elle ne les répare pas. La donnée
reste fausse en base.

Les trois premiers sont réparés **pour les ingestions futures** et pas pour la
base. Les deux derniers ne le sont nulle part. La réingestion répare à la bonne
place, mais elle **détache les portions d'ancrage** et `AncrageExtraction.element`
est en `PROTECT` : c'est un chantier de migration, pas une commande.

**Ce qui a changé depuis ce matin** : la comparaison par mots absorbe le tiret
détaché **et** les mots soudés (par la tolérance aux extrémités) sans rien
réingérer. La réingestion redevient donc un chantier de propreté de la donnée,
pas un préalable à la chaîne de preuve.

**3. Faut-il rejuger ?** Inchangé, et c'est peut-être le plus rentable des trois.
Les 119 liens ont été jugés avec les règles de leur époque, et **rien ne repasse
sur les `INTROUVABLE`** après un changement de règle. Toute règle adoptée ici sera
sans effet sur le passé tant qu'une commande ne les relit pas. Le contrôle
verbatim n'appelle **aucun modèle** : c'est gratuit, seule l'écriture des verdicts
est à faire.

## Ce qui reste après le chantier du 30 août — et ce qui a été démenti

Trois points étaient annoncés comme ouverts à la fin du chantier. **La mesure en
a supprimé un.**

### 1. Rejuger les liens `INTROUVABLE` — la seule action immédiate, et elle est gratuite

**42 des 119 liens redeviennent vérifiables**, mais **rien ne les relit**. Ils
resteront `INTROUVABLE` à l'écran tant qu'une commande ne repassera pas dessus.

Ce que ça demande : une management command qui, pour chaque `SourceLink` en
`introuvable`, rejoue `_le_verbatim_est_present` et remet le lien en
`NON_VERIFIE` quand il passe — **jamais directement en `verifie`** : le verbatim
retrouvé rend la citation *jugeable*, il ne dit pas que la source l'établit.
C'est le juge qui le dit, et lui est facturé.

**Le contrôle verbatim n'appelle aucun modèle** : le passage en revue coûte zéro.
Seul le rejugement par le juge, si on l'enchaîne, serait facturé — et il ne doit
donc pas l'être par la même commande.

### 2. Réparer la donnée — deux défauts d'ingestion que la passe ABSORBE sans les corriger

Le tableau du § 2 les porte : le **trait d'union détaché** (8 éléments, 2 notes)
et les **mots soudés** (83 éléments, 13 notes). La comparaison par les mots les
absorbe, donc plus aucune citation n'échoue à cause d'eux — **et c'est
exactement ce qui rend leur correction moins urgente et plus facile à oublier.**

Ce qu'ils coûtent encore, maintenant que la chaîne de preuve ne trébuche plus
dessus : le texte affiché au lecteur porte « savoir -faire » et « participation
citoyenneAucun parlementaire ». C'est un défaut de **lecture**, plus un défaut de
preuve.

### 3. Une citation à cheval sur deux éléments — ❌ CE N'EST PAS UN DÉFAUT

**Annoncé comme ouvert le 30 août, démenti le jour même par la mesure.** Le
chantier avait relevé que 60 citations fabriquées à cheval sur deux éléments
passaient le contrôle — avec l'ancienne règle comme avec la nouvelle — et l'avait
noté comme un défaut préexistant à instruire.

**Vérification sur les données réelles : 4 extractions sur 1 174 ne se lisent
dans aucun élément isolé. Les quatre sont correctement ancrées**, en 2 à 4
portions, sur des éléments **contigus** :

| extraction | portions | ce qu'elle enjambe |
|---|---|---|
| 101 | 2 | « une image numérique » + « qui renferme des informations sur… » — une phrase coupée par l'ingestion |
| 820 | 2 | un chiffre et sa source, coupés au milieu de la parenthèse |
| 8 | 2 | deux `list_item` d'une même liste |
| 333 | 4 | une phrase d'annonce + les **trois** items qu'elle introduit |

`AncrageExtraction.ordre_dans_extraction` existe précisément pour cela : **une
extraction est une suite de portions, pas une portion unique.** Recoller les
éléments à la vérification est donc *cohérent* avec ce que le moteur d'ancrage
fait déjà — ce n'est pas une faille, c'est le même modèle de données lu des deux
côtés.

**Le seul cas qui mérite un regard** est l'extraction 8 : elle colle la fin d'un
item de liste au début du suivant et produit une lecture — « …démontre/indique
preuves : … » — que ni l'un ni l'autre item ne porte. Un cas sur 1 174, et il
reste **traçable** : ses deux portions sont ancrées, donc le lecteur voit
exactement d'où vient chaque morceau. **Aucune action n'est proposée** : borner le
recollement aux éléments de même label casserait le cas 333, qui est légitime et
plus fréquent.

## Ce qui casse si on ne fait rien

Rien ne tombe. Mais **8,1 % des liens affichent une chaîne de preuve cassée, et
un tiers de ces cas-là n'ont aucun défaut de fond** — un tiret cadratin, un
guillemet droit. Dans un outil dont l'affirmation la plus forte est « cette
citation vient bien de là », un faux « introuvable » coûte plus qu'un faux
« faible » : il accuse la source d'une faute qu'elle n'a pas commise.

**Depuis le 30 août, le contrôle sait les reconnaître — et l'écran ment
toujours.** Les 42 liens récupérables restent affichés `INTROUVABLE` tant que
personne ne les relit. Tout ce qui précède reste donc vrai à l'écran, et la seule
chose qui l'y rende faux est la commande de rejugement du § 1 ci-dessus. Elle est
gratuite.

## Coût de mise en œuvre

**La comparaison par les mots** : une fonction d'une vingtaine de lignes dans
`core/services/verification.py`, les deux gardes (marque de fin, chiffres), et
les tests « ne doit JAMAIS » sur le modèle des quinze existants — plus un test de
non-régression sur tous les liens déjà `verifie` ou `faible`. **Une journée** : la
fonction est déjà écrite et éprouvée dans
`benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py`, il reste à
la porter et à finir la garde de la marque de fin (son `TODO` la nomme).

**Le repli T + G** : une dizaine de lignes, une demi-journée.

**La commande de rejugement des `INTROUVABLE`** : quelques heures, **sans
facture** — le contrôle verbatim n'appelle aucun modèle.

**La réingestion** : un chantier à part entière, à ne pas mêler à celui-ci.
