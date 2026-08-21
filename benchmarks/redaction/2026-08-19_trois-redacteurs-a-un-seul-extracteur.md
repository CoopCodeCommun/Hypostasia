# Trois rédacteurs, à un seul extracteur

**19 août 2026.** Corpus de démonstration, LangExtract 1.6.0, températures à 0,
juge constant : `mistral-small-latest`, seuil 45.

**C'est la campagne que celle du matin aurait dû être.** Les trois défauts
qu'elle portait sont fermés, et chacun par un mécanisme, pas par une consigne :

| le défaut du matin | ce qui le ferme ici |
|---|---|
| un job échoué sur un 503, invisible parce qu'un job en `error` satisfait « plus rien en attente » | une **garde** qui exige que le dernier job de production de chaque article soit `completed` **et du modèle attendu** |
| trois extracteurs sur les mêmes notes, donc chaque fait en ~3 exemplaires | **un seul extracteur** : 275 extractions masquées, périmètre de **137**, toutes de `mistral-small` |
| `--forcer` re-fige un périmètre neuf | **aucune extraction entre les passes** — vérifié : **0 citation hors périmètre** chez les trois |

> ## ⚠️ LE « % VÉRIFIÉES » NE DISCRIMINE RIEN — lire ceci avant les tableaux
>
> **Neuf passes répétées (3 modèles × 3 répétitions × 4 articles) ont mesuré le
> bruit que toutes les campagnes précédentes, celle-ci comprise, avaient supposé
> négligeable. Il ne l'est pas.**
>
> À température 0, même prompt, même périmètre, même juge, **`mistral-large`
> rend 29,4 %, 40,6 % puis 31,1 % de citations vérifiées** — onze points
> d'amplitude avec lui-même. Medium va de 172 à 267 citations selon la passe.
>
> | mesure | meilleur → pire (médianes) | écart | bruit | verdict |
> |---|---|---|---|---|
> | **% vérifiées** | Large 31,1 → Medium 38,9 | 7,8 | **11,2** | **DANS LE BRUIT** |
> | vérifiées (absolu) | Medium 63 → Small 85 | 22 | **38** | **DANS LE BRUIT** |
> | introuvables | Large 16 → Small 23 | 7 | **10** | **DANS LE BRUIT** |
> | citations | Medium 173 → Small 279 | 106 | 54 | **tranche** |
> | caractères | Medium 19 009 → Small 32 482 | 13 473 | 7 109 | **tranche** |
> | extractions distinctes | Medium 171 → Small 249 | 78 | 51 | **tranche** |
> | % prose sans marqueur | Medium 10,0 → Large 26,2 | 16,2 | 14,8 | **tranche, de justesse** |
>
> **Tout classement de ce rapport fondé sur le « % vérifiées » tombe** — y
> compris « Medium 41 % contre Small 36 % », qui a servi de recommandation au
> § 6. Un écart de cinq points est plus petit que la variation d'un modèle avec
> lui-même.
>
> Ce qui survit : Small **cite plus** et écrit plus long, Medium est **le plus
> sobre et le mieux sourcé**, Large reste **le plus bavard et le moins sourcé**.
> Détail et méthode : § 9, `analyser_les_passes.py`, `passes_repetees.json`.

> ## COMMENT LIRE CE RAPPORT — il porte DEUX campagnes
>
> Une seule chose les sépare : la **consigne de sourçage** du prompt de
> synthèse, réécrite entre les deux.
>
> - **§ 1 à 6 — la campagne AVANT.** Le prompt conditionnait le marqueur à
>   l'origine de la phrase ; Large écrivait une phrase sur deux sans source.
> - **§ 7 — la campagne APRÈS**, à périmètre et juge identiques. C'est elle qui
>   fait foi pour choisir un rédacteur.
>
> Les tableaux des § 1 à 6 ne sont **pas** périmés pour autant : ils mesurent ce
> que les modèles font quand le prompt laisse la porte ouverte, et c'est
> précisément ce qui a permis de trouver la porte.

Données brutes : `passe_small.json`, `passe_medium.json`, `passe_large.json`
(avant) et `passe_*_prompt_corrige.json` (après).
Périmètre : `perimetre_du_banc.json`. Mesure rejouable :
`mesurer_les_redacteurs.py`.

---

## 1. LE TABLEAU

| | citations | **vérifiées** | faibles | introuvables | non jugées | **% vérifiées** | caractères | distinctes |
|---|---|---|---|---|---|---|---|---|
| **Small** | 140 | 35 | 89 | 12 (9 %) | 4 | 28 % | 14 103 | 136 |
| **Medium** | 116 | 28 | 74 | 14 (12 %) | 0 | 27 % | 10 326 | 115 |
| **Large** | 140 | **41** | 76 | 13 (9 %) | **10** | **35 %** | 16 054 | 136 |

*(« % vérifiées » = vérifiées / (vérifiées + faibles). Les « non jugées » sont
des paires dont le juge n'a rendu aucun verdict : une perte du juge, pas du
rédacteur.)*

**L'avance de Large survit au pire cas**, ce qui n'était pas vrai le matin : si
ses 10 non jugées étaient toutes « faibles », il tomberait à **32 %** — encore
devant Small (28 %) et Medium (27 %).

### Les degrés rendus par le juge

| | 0 | 40 | 70 | 100 |
|---|---|---|---|---|
| Small | 16 | 73 | 35 | 0 |
| Medium | 15 | 59 | 28 | 0 |
| Large | **5** | 71 | **41** | 0 |

Toujours quatre crans, jamais de valeur intermédiaire — quatrième confirmation.
**Large échoue franchement trois fois moins souvent** (5 crans à 0 contre 16).

## 2. LA MESURE QUI DÉPARTAGE — la prose qui ne cite rien

> **Nuance apportée par les neuf passes (§ 9)** : cette mesure départage
> effectivement Medium de Large (16,2 points d'écart pour 14,8 de bruit), mais
> **de justesse**, et elle dépend fortement du SUJET — Small va de 4,5 % à
> 35,2 % selon l'article. Le titre de cette section disait « vraiment » ; c'est
> une de moins que ce que je croyais.

C'est ce que la campagne du matin annonçait sans définition, et qu'aucune
définition n'avait su reproduire. **La définition voyage désormais avec le
chiffre** : une phrase est « sans marqueur » quand elle ne porte aucun
`[[ext:N]]`. Les titres sont exclus — un titre ne cite jamais, et le compter
punirait le modèle qui structure le mieux.

| | phrases | sans marqueur | **part** | paragraphes entiers sans source |
|---|---|---|---|---|
| **Medium** | 41 | **0** | **0 %** | 0 / 18 |
| **Small** | 73 | 9 | 12 % | 0 / 13 |
| **Large** | 92 | **46** | **50 %** | 1 / 20 |

**Une phrase sur deux, chez Large, n'appuie sur rien.** Et ce ne sont pas des
transitions : ce sont des affirmations.

> « Les open badges émergent en 2011 comme une réponse à l'absence d'outils
> pour reconnaître les apprentissages informels. »
> « Cette situation limite leur déploiement à grande échelle et renforce les
> inégalités d'accès. »

**Medium ne fait jamais cela : ses 41 phrases portent toutes leur source.**

### C'est la contradiction du 19 août au matin, et elle est résolue

Le rapport du matin butait là-dessus : *« Large écrit plus fluide, mais sa
fluidité vient en partie de matière conjonctive non sourcée — ce qui devrait
produire des crans bas. Or il a la meilleure précision. Cette contradiction
n'est pas résolue. »*

Elle ne l'était pas parce que rien ne mesurait la prose nue. Les deux faits
sont vrais et compatibles : **Large cite moins souvent, et mieux quand il
cite.** Le juge ne note que ce qui porte un marqueur — la moitié de sa prose
échappe donc au contrôle. Son « 35 % de vérifiées » se lit sur la moitié de son
texte ; le « 27 % » de Medium se lit sur la totalité du sien.

## 3. LA COUVERTURE DU PÉRIMÈTRE

| | wiki | synthèse |
|---|---|---|
| Small | 47 / 137 = 34 % | **89 / 137 = 65 %** |
| Medium | 43 / 137 = 31 % | 72 / 137 = 53 % |
| Large | 57 / 137 = 42 % | 79 / 137 = 58 % |

**Aucun ne dépasse les deux tiers du périmètre**, et le wiki en laisse toujours
plus des trois cinquièmes de côté. Le sujet du wiki est volontairement étroit —
une partie de l'écart est donc voulue, et c'est ce que l'écran des « écartées »
donne à voir.

## 4. L'EFFET DE LA TOLÉRANCE AU VERBATIM

Le contrôle verbatim tolère depuis aujourd'hui trois retouches de forme (point
final, majuscule d'amorce, espace de ponctuation).

**Sur le périmètre de 137 extractions : 116 verbatim au sens strict, 9
rattrapées par la tolérance, 12 hors d'atteinte.**

Le taux d'introuvables des articles tombe à **9-12 %**, contre 17-19 % dans la
première exécution de cette même campagne, avec le contrôle strict.

## 5. CE QUE CETTE MESURE NE DIT PAS

- **La campagne a été exécutée DEUX FOIS, et seule la seconde compte.** La
  première tournait avec une tolérance au verbatim qui ne rattrapait qu'**une**
  extraction sur 21, là où le banc en annonçait neuf : elle forçait la première
  lettre en minuscule (ce qui casse toute citation commençant par un nom propre)
  et refusait un point que la source portait déjà, simplement détaché. Les deux
  sont corrigés et verrouillés par des tests. **Le classement du % vérifiées
  s'est inversé entre les deux exécutions** (Medium était devant à 39 %) : ce
  chiffre est donc plus fragile que l'écart sur la prose nue, qui, lui, est
  massif et stable.
- **Une seule passe par modèle**, deux articles, un corpus, un seul juge.
- **Le juge sous-note** — 9 cas relus sur 12 le 19 août. Les « % vérifiées »
  sont des planchers. Le biais frappe les trois de la même façon.
- **Le juge est un Mistral qui juge du Mistral.**
- **Les 10 paires non jugées de Large** ne sont pas un tirage aléatoire, et
  leur exclusion l'avantage — comme le matin.
- **La qualité de la prose n'est pas mesurée.** « Sans marqueur » ne veut pas
  dire « faux » : une phrase de transition légitime compte comme prose nue.
  L'inverse est plus inquiétant — les exemples relevés chez Large sont des
  affirmations factuelles, pas des transitions.
- **Le périmètre est celui d'un seul extracteur, mais d'un corpus de
  démonstration** : 6 notes, dont 5 analysées.

## 6. CE QUE J'EN CONCLUS

> Ces recommandations ont été écrites AVANT la correction du prompt. Elles
> sont conservées telles quelles, et **la correction ne les renverse pas** :
> Medium reste devant, et son avance s'élargit (41 % de vérifiées, 2 % de prose
> nue). Ce qui change, c'est l'argument : ce n'est plus « malgré » son taux,
> c'est **avec** le meilleur taux de la campagne.

> ⚠️ **Recommandations écrites avant les neuf passes du § 9.** Celles-ci
> retirent leur fondement principal : le « % vérifiées » ne discrimine pas.
> **La recommandation corrigée est au § 9.5.**

| étage | recommandation |
|---|---|
| **Rédaction** | **Medium**, qui a désormais le meilleur taux de la campagne. C'est le seul dont chaque phrase porte sa source, et le plus sobre (10 326 caractères). Pour un outil dont la promesse est la traçabilité, une prose intégralement sourcée vaut mieux qu'un meilleur taux sur la moitié d'un texte. **Réserve de coût : Medium est à 7,50 $ en sortie contre 1,50 $ pour Large et 0,60 $ pour Small** — c'est un arbitrage produit, pas une évidence technique. |
| **Si le coût prime** | **Small.** 12 % de prose nue, 140 citations, 0,60 $ en sortie. Il n'est derrière Large que de 7 points sur un critère qui ne regarde que la moitié du texte de Large. |
| **Large** | **à écarter, et le tarif le confirme** (§ 7 ter) : Small le bat sur les deux axes — 3,6× moins cher par citation vérifiée, meilleur taux, deux fois moins de prose nue. C'est le milieu de gamme qui ne gagne rien. |

## 7. LA PORTE DU PROMPT — ouverte, puis fermée, puis remesurée

### Ce que le prompt autorisait

La consigne de sourçage disait :

> « Chaque affirmation **tirée d'une hypostase** se termine par le marqueur de
> sa source »

**Elle conditionnait le marqueur au fait que la phrase soit « tirée d'une
hypostase ».** Une phrase de synthèse générale — « Les open badges émergent en
2011 comme une réponse à l'absence d'outils » — n'est, du point de vue du
modèle, tirée d'aucune extraction *en particulier*. Elle échappait donc à la
consigne sans la violer.

Rien ne disait **« toute affirmation doit porter un marqueur »**. La pièce de
pondération approchait sans y toucher : « chaque affirmation vient d'une
extraction fournie, et d'aucune autre » — elle parle de PROVENANCE, jamais de
MARQUEUR.

### La consigne réécrite

`front/tasks.py`, constante `CONSIGNE_DE_SOURCAGE` : « TOUTE AFFIRMATION que
porte ton article se termine par le marqueur de sa source… Si une phrase que tu
voulais écrire ne peut porter aucun marqueur, c'est qu'elle n'a pas sa place
dans l'article : supprime-la. Cela vaut aussi pour les phrases d'ouverture, de
contexte et de conclusion. » Deux exceptions, et deux seulement : les titres, et
les phrases de liaison purement structurelles.

### LA MESURE — même périmètre, même juge, seule la consigne change

| | prose nue AVANT | **APRÈS** | % vérifiées AVANT | **APRÈS** | citations |
|---|---|---|---|---|---|
| **Small** | 12 % | **9 %** | 28 % | **36 %** | 140 → 154 |
| **Medium** | 0 % | **2 %** | 27 % | **41 %** | 116 → 112 |
| **Large** | **50 %** | **19 %** | 35 % | **30 %** | 140 → 151 |

**La consigne était bien la cause.** Large passe de 46 phrases nues sur 92 à
19 sur 99 — **il en supprime les deux tiers** sans qu'on ait changé de modèle.

### Et Large n'y gagne pas pour autant — c'est le résultat qui compte

**Son taux de vérifiées BAISSE : 35 % → 30 %.** Ce n'est pas une régression,
c'est une révélation. Il source désormais les phrases qu'il laissait nues, et
**le juge note ces sources-là faibles**. Son « 35 % » d'avant se lisait sur la
moitié de son texte ; son « 30 % » se lit sur les quatre cinquièmes.

Small et Medium, eux, progressent sur **les deux** critères — ils avaient peu à
supprimer, et la consigne les a resserrés.

**Medium ressort nettement en tête : 41 % de citations vérifiées et 2 % de
prose nue.** C'est le meilleur taux de toute la campagne, sur le texte le plus
intégralement sourcé.

> ⚠️ **Une seule passe par condition.** Un écart de quelques points — Small
> 28 → 36 % — n'est pas distinguable du bruit. Le 50 % → 19 % de Large, lui,
> est massif et ne s'explique par rien d'autre : c'est le seul paramètre qui a
> changé.

## 7 bis. Ce que le prompt corrigé ne répare pas

- **Large garde 19 % de phrases nues.** La consigne réduit des deux tiers, elle
  n'annule pas. Medium est à 2 % sur la même consigne : l'écart restant est
  bien un trait de modèle, cette fois sans porte ouverte pour l'expliquer.
- **Les `INTROUVABLE` ne bougent pas dans le bon sens** — Small 12 → 21,
  Large 13 → 16. C'est attendu : le prompt de synthèse ne touche pas à
  l'extraction, et un rédacteur qui cite PLUS cite aussi plus d'extractions non
  verbatim. La chaîne de preuve se répare à l'étage de l'extraction, pas ici.
- **Le nombre de citations monte, la couverture non** : Large passe de 136 à
  139 extractions distinctes sur 137 — il cite plus souvent les mêmes.
- **Les « non jugées » restent** : 10 chez Large et Small, 4 chez Medium. Ce
  sont des paires que le juge n'a pas rendues, et leur exclusion avantage
  mécaniquement qui en a le plus.

## 7 ter. LE RAPPORT TARIF / EFFICACITÉ — Large est dominé

Tarifs relevés le 18 août 2026 sur `mistral.ai/pricing/api/`, en dollars par
million de tokens. **Le prompt d'entrée est identique pour les trois** —
15 365 caractères mesurés pour les deux articles, même périmètre de 137
extractions. Seule la longueur de sortie diffère, et elle est mesurée.

| | in $/M | out $/M | caractères produits | **coût de la campagne** | vérifiées | **coût / 100 vérifiées** |
|---|---|---|---|---|---|---|
| **Small** | 0,15 | 0,60 | 15 326 | **0,0029 $** | 44 | **0,0065 $** |
| **Large** | 0,50 | 1,50 | **18 033** | 0,0087 $ | 37 | 0,0235 $ |
| **Medium** | 1,50 | 7,50 | 11 053 | 0,0265 $ | 39 | 0,0679 $ |

> ⚠️ **Les neuf passes (§ 9) retirent une des deux jambes de ce raisonnement.**
> « 36 % contre 30 % de vérifiées » est **dans le bruit** : Large seul oscille
> de 29,4 à 40,6 %. Ce qui reste vrai de ce tableau, c'est le **coût** — il est
> calculé sur des caractères mesurés, pas sur un verdict de juge — et le fait
> que Large soit **le plus bavard**, ce que les neuf passes confirment.

**Large n'a aucun argument, et c'est le résultat le plus net de la campagne :**

- **Small le bat sur les DEUX axes** — 3,6× moins cher par citation vérifiée,
  36 % de vérifiées contre 30 %, et 9 % de prose nue contre 19 % ;
- **Medium le bat sur la qualité** — 41 % de vérifiées, 2 % de prose nue — au
  prix de 2,9× son coût.

Large est donc le **milieu de gamme qui ne gagne rien** : trop cher pour
concurrencer Small, trop faible pour justifier son surcoût. Et son défaut
s'auto-aggrave : **c'est le plus verbeux des trois** (18 033 caractères contre
11 053 pour Medium), donc il paie pour écrire davantage — et ce qu'il écrit en
plus est précisément la part la moins bien sourcée.

> **Ce que ce tableau suppose, et qu'il faut savoir.** Les coûts réels ne sont
> **pas** enregistrés en base — les trois champs prévus pour ça n'ont aucun
> écrivain. Les montants ci-dessus sont donc calculés depuis les **caractères
> mesurés**, avec une conversion de 4 caractères par token. Cette conversion
> est une hypothèse ; **le classement n'en dépend pas** (elle s'applique aux
> trois de la même façon), seuls les montants absolus bougeraient.

## 8. CE QUE CETTE MESURE NE SURVIT PAS À UN `down -v`

**`mistral-large-latest` et `mistral-medium-latest` n'existent dans AUCUNE
fixture.** Ils ont été créés à la main pour ce banc (`is_active=False`), et
`MODELES_IA_PAR_CLE_D_ENVIRONNEMENT` ne porte que Small, Gemini, GPT-4o Mini et
Claude Sonnet. Un `docker compose down -v && make install` les efface :
**cette campagne n'est pas rejouable en l'état après une réinstallation.**

Ce que la réinstallation rétablit correctement, en revanche — vérifié ligne à
ligne :

| | après `down -v && make install` |
|---|---|
| modèle d'**extraction** (`Configuration.ai_model`) | `mistral-small-latest`, **température 0** — il est en tête de la liste, et `MISTRAL_API_KEY` est présente |
| rôle **rédacteur** | `mistral-small-latest` |
| rôle **juge** | `mistral-small-latest` |
| les 4 pièces du prompt d'extraction, les 3 de synthèse, les 30 exemples | reposés par les fixtures |
| la consigne de sourçage `[[ext:N]]` | elle vit dans le **code** (`front/tasks.py`), elle ne dépend pas de la base |

> **Un rôle posé à la main SURVIT au redémarrage** — `get_or_create`, pas
> `update_or_create` (`fixtures_analyseurs.py:407`). C'est voulu, et c'est aussi
> ce qui fait qu'après ce banc le rôle rédacteur était resté sur **Large** : il
> a fallu le remettre à Small explicitement. Un banc qui déplace un rôle doit le
> reposer en partant.

### Et la réinstallation devrait FAIRE BAISSER le taux d'introuvables

Le recollage de la ponctuation vit dans l'ingestion. Les éléments **déjà en
base** gardent leur texte — les corriger décalerait les ancres — mais un
`down -v && make install` réingère tout, **avec le recollage**. Les sources
seront alors propres à la source, et les 20 liens `INTROUVABLE` dus à un espace
de ponctuation ne devraient plus apparaître du tout.

**C'est une prédiction, pas une mesure.** Elle se vérifie en relançant ce banc
après une réinstallation.

**Ce qui reste à éprouver** : ce que donnerait une consigne de sourçage qui
ferme la porte du § 7 — c'est peut-être là, et non dans le choix du modèle, que
se joue la prose nue de Large.

## 9. NEUF PASSES — ce que le bruit autorise à dire

**3 modèles × 3 répétitions × 4 articles**, dont deux sujets de wiki neufs
(« Les limites de l'explicabilité des systèmes d'IA », « La gouvernance
collective des outils numériques ») choisis pour toucher d'autres parties du
corpus. Températures à 0, périmètre figé à 137 extractions, juge constant.
Aucune passe écartée. Rejouable : `lancer_les_passes.py`, analysé par
`analyser_les_passes.py`.

### 9.1 Le bruit, mesuré au lieu d'être supposé

| | passe 1 | passe 2 | passe 3 | médiane | **étendue** |
|---|---|---|---|---|---|
| **% vérifiées** — Small | 36,0 | 33,9 | 34,8 | 34,8 | 2,1 |
| **% vérifiées** — Medium | 37,4 | 41,4 | 38,9 | 38,9 | 4,1 |
| **% vérifiées** — Large | 29,4 | 40,6 | 31,1 | 31,1 | **11,2** |
| **citations** — Large | 250 | 279 | 225 | 250 | **54** |
| **prose nue** — Large | 38,8 | 26,2 | 24,0 | 26,2 | **14,8** |

C'est **l'étendue**, pas l'écart-type : trois points ne méritent pas mieux.

**Large est de très loin le plus instable** — sur les trois mesures. Un modèle
qui varie de onze points sur son propre taux de vérifiées ne peut pas être
départagé d'un autre à sept points d'écart.

### 9.2 L'effet du SUJET est aussi grand que celui du modèle

% de prose sans marqueur, par article, médiane sur trois passes :

| article | Small | Medium | Large |
|---|---|---|---|
| Wiki — open badges | **4,5** | **0,0** | 20,9 |
| Wiki — explicabilité de l'IA | 13,3 | 10,0 | **39,2** |
| Wiki — gouvernance collective | **35,2** | 13,8 | 20,4 |
| Synthèse — état des lieux | 11,5 | 14,7 | 21,1 |

**Small passe de 4,5 % à 35,2 % de prose nue selon le sujet** — un facteur
huit, sur le même modèle et la même consigne. Le sujet « gouvernance
collective » est celui sur lequel le corpus a le moins de matière : le modèle
comble le vide avec de la prose non sourcée, exactement là où il devrait se
taire.

**C'est le résultat le plus utile de cette campagne pour le produit** : un
article sur un sujet mal couvert par le carnet se dégrade en prose non
sourcée, et ce n'est pas le modèle qu'il faut alors changer.

### 9.3 Ce qu'on peut affirmer, et rien de plus

| affirmation | tient ? |
|---|---|
| Small cite plus que Medium (279 contre 173) | **oui** — écart 106, bruit 54 |
| Medium écrit deux fois plus court (19 k contre 32 k caractères) | **oui** — écart 13 473, bruit 7 109 |
| Medium laisse moins de prose non sourcée que Large (10 % contre 26 %) | **oui, de justesse** — écart 16,2, bruit 14,8 |
| Medium a un meilleur % de citations vérifiées que Small | **NON** — 7,8 points d'écart pour 11,2 de bruit |
| Large est plus mauvais que Small sur le % vérifiées | **NON** — dans le bruit |
| Le taux d'introuvables distingue les rédacteurs | **NON** — et c'est attendu : il dépend de l'extracteur, pas du rédacteur |

### 9.4 Ce que cette campagne ne dit toujours pas

- **Trois répétitions, c'est peu.** L'étendue sur trois points sous-estime la
  vraie dispersion : les verdicts « tranche » les plus serrés — la prose nue
  Medium/Large, 16,2 contre 14,8 — sont à prendre comme des indices, pas comme
  des preuves.
- **Le juge est le même Mistral Small à chaque passe**, et il a lui aussi sa
  part de variation, qui n'est pas isolée ici : une partie du « bruit » attribué
  au rédacteur lui appartient peut-être.
- **Quatre articles, un corpus, un carnet de démonstration.**
- **Le coût n'a pas été remesuré sur ces neuf passes** : le § 7 ter reste
  calculé sur la campagne à deux articles.

### 9.5 LA RECOMMANDATION, corrigée par le bruit

Le « % vérifiées » ne départage pas les trois modèles. **Le choix se fait donc
sur ce qui tranche**, et ces critères ne désignent pas le même gagnant :

| si l'on veut… | alors | parce que |
|---|---|---|
| **le plus de preuves cliquables** | **Small** | 279 citations contre 173, et 249 extractions distinctes contre 171 — écarts hors bruit |
| **l'article le plus intégralement sourcé** | **Medium** | 10 % de prose nue contre 18,8 (Small) et 26,2 (Large) |
| **le moins cher** | **Small** | 10× moins que Medium par citation vérifiée (§ 7 ter) |

**Large n'est premier sur aucun critère, et il est le plus instable des trois**
— onze points d'amplitude sur son propre taux de vérifiées, 54 citations
d'écart entre deux passes. C'est le seul verdict que cette campagne rend sans
réserve.

**Entre Small et Medium, la mesure ne tranche pas** : elle dit qu'ils font des
articles *différents* — Small abondant et long, Medium sobre et mieux sourcé —
sans que l'un soit meilleur. **C'est un arbitrage produit, pas un résultat
technique**, et il se joue sur le prix : Small coûte dix fois moins.
