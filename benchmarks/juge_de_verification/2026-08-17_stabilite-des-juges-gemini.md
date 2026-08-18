# Comparaison de juges — 17 août 2026

**Jeu de mesure** : `etalon-du-juge.json`, 145 paires (affirmation, source) gelées, jugées le
17 août par `verbatim+nli-lot v2 — Gemini 2.5 Flash`. 8 appels par exécution, lots de 20.
**Aucune écriture en base** — le banc rejoue, il ne re-juge pas.

> **Ce rapport mesure l'ACCORD et la STABILITÉ, jamais la justesse.** Pour savoir *qui a
> raison*, il a fallu juger les paires à la main : c'est fait dans
> `benchmarks/chaine_complete/rapport.html`, § « Étage 3 bis — qui a raison ? », et le
> résultat corrige deux conclusions de ce fichier-ci. Les corrections sont datées sur place.

---

## Le résultat qui compte : un verdict de juge n'est pas reproductible

Avant de comparer deux modèles, il faut savoir combien un modèle diffère **de lui-même**.
Sans ce plancher, un taux d'accord ne veut rien dire.

Le juge de référence a rejoué ses propres 145 paires **cinq fois**. Le nombre de citations
qu'il déclare « vérifiées » :

| Exécution | Température | « soutient » | « ne_soutient_pas » | Accord avec l'étalon |
|---|---|---|---|---|
| l'étalon (17 août, matin) | défaut | **118** | 27 | — |
| rejeu n°1 | défaut | **133** | 12 | 88 % |
| rejeu n°2 | 0 | **115** | 30 | 83 % |
| rejeu n°3 | 0 | **105** | 40 | 72 % |
| rejeu n°4 | 0 | **120** | 25 | — |

**De 105 à 133 sur cinq exécutions du même modèle sur les mêmes paires**, soit un taux de
citations vérifiées oscillant entre **72 % et 92 %**. Le chiffre affiché à l'utilisateur
dépend du tirage.

**Mesure directe de la reproductibilité** — rejeu n°4 comparé au rejeu n°3, même modèle,
même température 0, trois minutes d'écart : **77 % (112/145)**.

### Pourquoi la température 0 ne suffit pas — et ce qui est vraiment en cause

> **Correction du 17 août, après relecture adverse.** Une première version de ce rapport
> attribuait l'instabilité au **jeton imprévisible** du prompt, « donc structurelle, donc
> irréparable ». **La mesure le réfute** : les juges candidats atteignent **95 %** de
> stabilité avec exactement le même jeton, tiré de la même façon, dans le même prompt — le
> banc importe `_construire_le_prompt_du_juge` sans le recopier. Si le jeton était la cause
> dominante, ils seraient instables aussi.

Ce qui est vrai, et ce qui ne l'est pas :

1. **Le jeton interdit le déterminisme parfait, et rien de plus.** Le prompt du juge
   encadre chaque donnée d'un délimiteur à jeton imprévisible, tiré à chaque appel — la
   défense contre l'injection (relecture G, B2). Deux appels ne portent donc jamais le même
   prompt, et 100 % de reproductibilité est exclu par construction. **Mais l'écart entre
   77 % et 95 % ne vient pas de là** : il vient du modèle.
2. **C'est le modèle qui est incertain.** Le juge de référence met **150 s** là où les
   candidats en mettent **8** pour les mêmes huit appels : il « réfléchit » longuement, et
   cette réflexion n'est pas déterministe. Les candidats, qui ne réfléchissent guère,
   retrouvent 95 % de leurs verdicts.
3. **La preuve par l'étage voisin.** Sur le banc de chaîne complète, à température 0, la
   *rédaction* d'un article rend **trois textes identiques octet pour octet** chez deux
   modèles. Le prompt du rédacteur, lui, ne porte pas de jeton. Déterminisme d'un côté,
   95 % de l'autre : l'écart imputable au jeton est de l'ordre de quelques points, pas de
   vingt.

> **Ce qui reste vrai de la conclusion, et qui suffit** : un verdict n'est pas une propriété
> de la citation, c'est **un acte daté rendu par un juge nommé**. Relancer la vérification
> change le résultat — beaucoup avec un juge qui réfléchit, un peu avec un juge stable.
> Jamais rien.

> **Réserve de méthode** : chaque taux de stabilité ci-dessous est **une seule** comparaison
> de deux exécutions. L'écart de 18 points est probablement réel ; il est donné avec plus de
> précision qu'il n'en a.

---

## La comparaison des candidats

`gemini-2.5-flash-lite` **n'a pas pu être mesuré** : l'API répond `404 — This model is no
longer available to new users. Please update your code to use models/gemini-3.5-flash-lite`.
Le référentiel du dépôt le proposait encore.

| Juge | Entrée $/M | Sortie $/M | **Stabilité** (run B vs run A) | Accord avec l'étalon | Durée (145 paires) |
|---|---|---|---|---|---|
| `gemini-2.5-flash` (référence) | 0,30 | 2,50 | **77 %** | 72 – 88 % | **136 – 154 s** |
| `gemini-3.1-flash-lite` | **0,25** | **1,50** | **95 %** | 81 % | **8 – 9 s** |
| `gemini-3.5-flash-lite` | 0,30 | 2,50 | **94 %** | 82 % | **8 s** |

Tarifs relevés le 17 août 2026 sur `https://ai.google.dev/gemini-api/docs/pricing`.

**Les deux candidats sont indistinguables de la référence sur *ce qu'ils jugent*** — leurs
81 % et 82 % d'accord tombent à l'intérieur du plancher de bruit de la référence
(72 – 88 %). Ils la battent en revanche nettement sur ce qui décide :

- **la stabilité** : 95 % contre 77 %, soit **18 points** ;
- **le temps** : **17 fois plus rapide**, à nombre d'appels identique (8) ;
- **le prix** : −17 % en entrée et −40 % en sortie pour `gemini-3.1-flash-lite`.

**Les verdicts négatifs deviennent stables, eux aussi.** Chez la référence, 13 à 16 des
« ne_soutient_pas » se reproduisent ; chez `gemini-3.1-flash-lite`, **25 sur 28**. C'est le
verdict « faible » — celui qui accuse une attribution — qui gagne le plus à ce changement.

### Le coût, et ce qui n'est pas mesuré dedans

Entrée mesurée : **37 786 tokens** pour les 145 paires. Sortie visible : ~1 160 tokens
(8 tokens par paire).

| Juge | Coût des 145 paires | Hypothèse sur le « thinking » |
|---|---|---|
| `gemini-2.5-flash` | ~**0,026 $** | ×5 en sortie — l'estimation du dépôt, **non mesurée** |
| `gemini-3.1-flash-lite` | ~**0,011 $** | thinking supposé négligeable |
| `gemini-3.5-flash-lite` | ~**0,014 $** | idem |

**Le nombre de tokens de réflexion n'est mesuré chez aucun des trois** : `appeler_llm` ne
rend que du texte, et les trois champs de coût réel d'`ExtractionJob` n'ont aucun écrivain.
La **durée**, elle, est mesurée : 150 s contre 8 s pour huit appels identiques. C'est une
preuve indirecte forte que la référence réfléchit longuement et que les candidats non — et
comme le thinking est facturé **au tarif de sortie** (la page de tarifs l'écrit), l'écart de
coût réel est probablement plus grand que le tableau ne le montre.

---

## Les juges Mistral, et ce qu'ils révèlent

Mesurés après que la clé `MISTRAL_API_KEY` a été renseignée, dans les mêmes conditions —
température 0, mêmes 145 paires, deux exécutions chacun.

| Juge | Entrée $/M | Sortie $/M | **Stabilité** | Accord étalon | Durée | Sans réponse |
|---|---|---|---|---|---|---|
| `ministral-3b-latest` | 0,10 | 0,10 | 89 % | 79 % | 8 s | **1 à 4 paires** |
| `mistral-small-latest` | 0,15 | 0,60 | **95 %** | **57 %** | 9–10 s | 0 |

**`ministral-3b` laisse tomber des paires.** Une à quatre par exécution repartent sans
verdict — pour un juge, c'est un défaut : la paire garde son état précédent et l'échec se
compte au bilan, mais on paie un appel pour rien.

**`mistral-small` est aussi stable que le meilleur Gemini, et beaucoup plus SÉVÈRE.** Il
marque **77 paires** « ne soutient pas » là où la référence en marquait 27 — et il le
refait à 95 %. Ce n'est pas de l'instabilité : c'est une autre lecture du critère.

### Deux juges stables qui divergent sur 43 % des paires

C'est le résultat le plus instructif du banc. Quand deux juges qui se reproduisent chacun à
95 % ne sont d'accord que sur 57 % des paires, **le désaccord ne vient plus du hasard : il
vient de la question**.

Lecture à la main de trois paires en litige (Gemini « soutient », Mistral « ne soutient
pas ») — **Mistral a raison sur les trois** :

| Affirmation (extrait) | Source citée |
|---|---|
| « Les Open Badges représentent une démarche innovante… Ils ont été conçus pour combler un manque… constituant un point de départ historique. » | « UNE DÉMARCHE INNOVANTE POUR LA RECONNAISSANCE DES COMPÉTENCES INFORMELLES » |
| *(la même affirmation)* | « les badges comme outil de reconnaissance des apprentissages tout au long de la vie » |
| *(la même affirmation)* | « combler un manque dans les outils de reconnaissance des apprentissages informels » |

Chaque source établit **un fragment** de l'affirmation, et aucune ne l'établit entière. Le
prompt demande pourtant à chacune, seule, d'établir tout ce que l'affirmation avance.

### Ce que la structure des affirmations explique — et ce qu'elle n'explique pas

| | Affirmations | Paires | Sources par affirmation | Affirmation médiane |
|---|---|---|---|---|
| Wiki | 11 | 58 | 5,3 (de 2 à 8) | 713 caractères |
| Synthèse | 12 | 87 | 7,2 (de 2 à 15) | 921 caractères |

**L'unité jugée est un paragraphe entier**, auquel sont attachées de deux à quinze sources.
Sur les trois paires relues à la main, chaque source établissait un **fragment** de
l'affirmation, et le prompt demande à chacune, seule, d'établir tout ce que l'affirmation
avance.

> **Correction du 17 août, après relecture adverse.** Une première version affirmait que
> cela **expliquait** l'écart wiki 97 % / synthèse 71 %, les paragraphes de la synthèse
> portant 36 % de sources en plus. **Le recomptage réfute cette lecture** :
>
> | | Wiki | Synthèse |
> |---|---|---|
> | affirmations à **2–6 sources** | **100 %** (42 paires) | **70 %** (30 paires) |
> | affirmations à **7–15 sources** | 88 % (16 paires) | 72 % (57 paires) |
>
> **À nombre de sources comparable, l'écart persiste presque entier** — 30 points sur la
> tranche basse. Et la corrélation entre le nombre de sources et le taux de soutien est
> faible : **r = −0,25** sur 23 affirmations. L'écart est porté par **le document**, pas par
> le compte de sources. La lecture du matin — « le wiki cite serré, la synthèse ratisse
> large et étire ses sources » — explique ces mêmes données au moins aussi bien, et mieux à
> comptes appariés. Elle est donc rétablie.
>
> Ce que le multi-sources fait quand même : à l'intérieur du wiki, le taux passe de 100 % à
> 88 % quand le nombre de sources monte. Effet réel, dans le sens attendu, mais qui ne porte
> pas l'écart entre les deux documents.

**Ce qui reste démontré, et qui suffit : la question posée au juge est SOUS-SPÉCIFIÉE.**
Deux juges stables à 95 % qui divergent sur 43 % des paires ne peuvent pas diverger sur le
hasard : ils divergent sur le **seuil**. « Établir » veut-il dire établir *tout* ce que
l'affirmation avance, ou *la part que cette source revendique* ? Le prompt ne le dit pas, et
chaque modèle tranche à sa façon.

> **Trou de spec à instruire avant de changer de juge.** `SPEC-synthese § 7.2` a raison de
> juger **par paire** — c'est la seule façon de désigner *laquelle* des sources ne tient pas.
> Mais il faut alors **dire le seuil**. Tant qu'il n'est pas dit, changer de juge ne fait que
> changer de seuil en silence.
>
> **Cet addendum n'est pas écrit à ce jour.** Tant qu'il ne l'est pas, la décision ci-dessous
> n'est pas un arbitrage : c'est un statu quo, et il faut le lire comme tel.

---

## Décision

**Juge affecté : `gemini-3.1-flash-lite`**, température 0 :

```bash
manage.py affecter_un_modele_a_un_role \
    --role juge_de_verification --choix gemini-3.1-flash-lite --temperature 0
```

**Pourquoi lui et pas `mistral-small-latest`, qui est aussi stable, moins cher et
européen** : parce que le juge sévère **se trompe**.

> **Correction du 18 août — le sens de ce paragraphe est inversé.** Une première version
> disait que `mistral-small-latest` était « plus juste sur les trois paires relues », et que
> garder Gemini était un statu quo conservant le tableau flatteur. **Les quinze paires d'une
> affirmation ont depuis été jugées une à une**, sous une règle écrite AVANT de juger : une
> source soutient si elle établit au moins une assertion complète de l'affirmation. Sous
> cette règle, l'accord avec mes verdicts est de **8/15 pour `mistral-small-latest`**, contre
> 13/15 et 14/15 pour les juges permissifs. Ses sept écarts vont **tous** dans le sens de la
> sévérité, et trois portent sur des sources qui reprennent l'affirmation presque mot pour
> mot — dont « le créateur prend un abonnement sur la plateforme » face à « utilisées via des
> abonnements pour créer les badges ».
>
> **La lecture initiale appliquait sans le dire la lecture étroite** (« la source doit établir
> *tout* ce que l'affirmation avance »), sous laquelle les quinze paires échouent. C'est
> exactement le piège que ce rapport dénonce par ailleurs — et j'y suis tombé le premier.
>
> Détail, motifs paire par paire et comparaison : `benchmarks/chaine_complete/rapport.html`,
> § « Étage 3 bis — qui a raison ? ».

**L'erreur de Mistral est cohérente, et c'est ce qui la rend utile** : les six sources qu'il
accepte sont des propositions complètes sans matière étrangère ; les sept qu'il refuse sont
des fragments nominaux ou des phrases qui disent quelque chose *en plus*. Il répond donc à
« cette source est-elle l'énoncé exact de cette affirmation ? » — un contrôle
d'**attribution** — quand le prompt demande « cette source établit-elle ce que l'affirmation
avance ? », un contrôle de **soutien**. **À reprendre comme second juge, pas comme
remplaçant.**

> **Chiffre corrigé le 17 août** : une version antérieure annonçait 59 % de citations qui
> passeraient en « faible » avec le juge sévère. Le compte réel est **77/145 = 53 %**. Aucune
> combinaison des mesures ne donnait 59 % — c'était un chiffre non mesuré dans une décision,
> ce que ce dépôt s'interdit.

Le rédacteur d'article reste sur `gemini-2.5-flash` : ce banc ne mesure que le juge, et
`compar:IA` place la génération 2.5 Flash en tête des modèles testés en français (1090).

## Ce qui n'a pas pu être mesuré

- **OpenRouter, orq.ai** : clés absentes.
- **Les tokens de réflexion**, faute d'un chemin qui remonte l'`usage`.
- **La justesse, à l'échelle.** Ce banc mesure l'accord et la stabilité, **jamais la
  vérité**. Trois paires ont été relues à la main — c'est un indice, pas une mesure. Un
  échantillon annoté à la main serait le seul étalon de justesse, et il n'existe pas.
