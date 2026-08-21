# Le mode d'échec du verbatim — ce n'est pas ce qu'on croyait

**19 août 2026.** Mesure **gratuite** : aucun appel de modèle, aucune écriture
en base. Elle relit les 400 extractions déjà produites par les trois Mistral,
et les 60 citations `INTROUVABLE` des articles en base.

Tout ce qui suit sort d'une seule commande :
```bash
docker compose exec -T web python \
    benchmarks/extraction_format/typer_les_non_verbatim.py
```
Verrouillée par `hypostasis_extractor/tests/test_typage_des_non_verbatim.py`
(22 tests).

---

## 1. LE TYPAGE — la concaténation n'est PAS le mode d'échec

L'hypothèse de départ était : « sur pièces, Mistral concatène — il colle une
phrase d'amorce à la liste qui suit ». **La mesure la réfute.**

| modèle | verbatim | ponctuation | ellipse | saut | reformulation | hors source |
|---|---|---|---|---|---|---|
| `mistral-large` | 116 | 11 | 0 | **5** | 2 | 0 |
| `mistral-medium` | 107 | 17 | 0 | **4** | 1 | 0 |
| `mistral-small` | 116 | 16 | 0 | **3** | 2 | 0 |

Le saut — la concaténation soupçonnée — fait **3 cas sur 21** chez Small.
**Zéro ellipse** : aucun modèle n'annonce son élision.

Le mode dominant est la catégorie `ponctuation` : **tous les mots, dans
l'ordre, d'un seul tenant** — seuls des caractères non-mots diffèrent.

## 2. CE QUI DIFFÈRE, caractère par caractère

Sur les 61 extractions non verbatim, alignées contre la fenêtre source exacte :

| ce que l'extrait porte en plus (ou en moins) | occurrences |
|---|---|
| un point `.` | 31 |
| un espace de la source en moins | 23 |
| `"` de la source rendu `'` | 10 |
| une parenthèse `)` ou `).` | 12 |
| un tiret de la source en moins | 5 |
| une majuscule d'amorce | 4 |

> ⚠️ **Ce tableau est DESCRIPTIF, jamais explicatif.** Il dit ce que l'extrait
> porte et que la fenêtre source ne porte pas — **il ne dit pas qui l'a mis
> là**. Un point que la source portait déjà, simplement détaché par un espace
> d'ingestion (« territoire . Soutenu »), s'y lit exactement comme un point
> ajouté par le modèle. C'est le tableau du § 3 qui tranche, et il tranche
> autrement.

## 3. CE QUE ÇA COÛTE — les 60 `INTROUVABLE`, forme ou fond ?

Le contrôle verbatim (`core/services/verification.py:141`) est un test de
sous-chaîne après NFKC, apostrophes, guillemets et espaces écrasés. Un point
final ajouté le fait échouer, et le lien part en `INTROUVABLE` — la chaîne de
preuve est déclarée cassée.

| cause | liens | part |
|---|---|---|
| **espace de ponctuation de la source** | **20** | 33 % |
| point réellement ajouté | 8 | 13 % |
| majuscule d'amorce | 6 | 10 % |
| **récupérable par les trois règles** | **34** | **57 %** |
| autre retouche de forme *(tiret, `;`, `)`, guillemet, point parasite)* | 13 | 22 % |
| **vrai saut de passage** | **11** | **18 %** |
| variante orthographique *(`réglementation` / `règlementation`)* | 2 | 3 % |

**11 des 60 (18 %) sont un vrai défaut sémantique.** Les 49 autres sont des
retouches de forme — dont 34 que trois règles simples récupéreraient.

### La cause dominante est NOTRE ingestion, pas le prompt

C'est le résultat qui décide où porter l'effort. La page 1 porte littéralement
`territoire .` — un point détaché de son mot par un espace. Le modèle le
recolle, et notre comparaison le lui refuse.

```
source  : « d'un territoire . Soutenu »       extrait : « d'un territoire. »
source  : « par IMS Global , un consortium »  extrait : « par IMS Global, un »
source  : « des 1/3 Lieux(La Bobine »         extrait : « des 1/3 Lieux (La »
source  : « Le créateur/ la créatrice »       extrait : « Le créateur/la »
```

**Les trois modèles font la même correction au même endroit** — extractions
34, 167 et 301 sont un seul et même passage vu par trois modèles.

> **Cette répartition a d'abord été publiée à l'envers** (21 points ajoutés,
> 7 espaces), par un défaut de l'outil : sa garde ne refusait que les
> ponctuations *fortes* (`?`, `!`) après le passage, jamais un `.` que la
> source portait déjà. Treize cas changeaient donc de colonne — et avec eux, la
> conclusion : ce n'était pas le modèle qui met en phrase, c'était nous qui
> détachons les points. Verrouillé depuis par
> `test_un_point_deja_dans_la_source_n_est_pas_un_point_AJOUTE`.

## 4. CE QUE CETTE MESURE NE DIT PAS

- **Les 60 `INTROUVABLE` sont ceux des articles de `mistral-large` SEUL.**
  Ce sont les derniers rédigés (jobs 45 et 46) ; les articles de Small et de
  Medium ont été écrasés. Le typage des 400 extractions va dans le même sens
  pour les trois, mais la table du § 3 ne porte que sur un rédacteur.
- **60 liens ne sont pas 60 citations : il y a 43 extractions distinctes.**
  Les deux articles citent souvent la même. Pour décider d'un assouplissement,
  le lien est la bonne unité — c'est lui qui s'affiche cassé. Pour
  caractériser le mode d'échec d'un *extracteur*, le double comptage déforme
  les poids : les « 11 vrais sauts » ne sont que **8 extractions**, et les
  « 2 variantes orthographiques » **une seule**.
- **Le typage a un angle mort borné.** La source est le `join("\n")` des
  éléments : un collage de deux éléments **adjacents** — l'hypothèse exacte du
  brief — y est invisible. Mesuré : **1 extraction par modèle** enjambe une
  frontière d'élément, et c'est le même passage trois fois. L'angle mort
  existe, il ne peut pas porter la conclusion.
- **La catégorie `ponctuation` n'est pas une garantie de sens.** « Tous les
  mots, dans l'ordre » n'exclut pas qu'un `?` devenu `.` change ce que la
  source dit. Les 13 cas de ce corpus ont été relus un par un et sont bénins ;
  la règle générale ne l'est pas — c'est pourquoi `reparation_qui_suffit`
  refuse explicitement ce cas.
- **Le taux de verbatim de `gemini-2.5-flash` (100 %) reste invérifiable** :
  la base a été détruite, et il tournait à température 0,7.
- **Une seule passe par modèle**, 6 notes dont **5 analysées** (la note
  « Présentation Hypostasia V3 » n'a aucun job d'extraction), un corpus.
- **Rien ici ne mesure ce qu'un prompt corrigé donnerait.** C'est une passe
  facturée, non lancée.

## 5. OÙ PORTER L'EFFORT

Par modèle, sur les non-verbatim :

| modèle | non verbatim | récupérables par les 3 règles | reste |
|---|---|---|---|
| `mistral-small` | 21 | 9 | 12 |
| `mistral-large` | 18 | 9 | 9 |
| `mistral-medium` | 22 | 11 | 11 |

`PIECE_D_INSTRUCTIONS_DE_L_EXTRACTION` dit déjà « Extrais la citation EXACTE
du texte. Ne reformule jamais. » — et les modèles **obéissent sur le fond** :
2 reformulations de mots sur 137 chez Small.

Ce que la consigne ne dit pas, c'est que la **forme** compte aussi. Et les 30
exemples few-shot enseignent le contraire de ce qu'on veut : **29 sur 30** sont
des phrases complètes terminées par un point. Mais le § 3 borne ce que ça
coûte : **8 liens sur 60**, pas 21.

| levier | ce qu'il récupère | coût |
|---|---|---|
| **assouplir la comparaison** (3 règles) | 34 liens sur 60 | gratuit, déterministe |
| **réparer l'ingestion** (espaces détachés) | ~20 liens, à la source | réingestion |
| **durcir le prompt** (consigne + exemples de fragments) | 8 liens au plus | une passe facturée |
