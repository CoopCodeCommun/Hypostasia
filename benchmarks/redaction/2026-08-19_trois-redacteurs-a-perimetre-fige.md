# Trois rédacteurs Mistral, à périmètre figé

**19 août 2026.** Corpus de démonstration, LangExtract 1.6.0, températures à 0,
juge constant : `mistral-small-latest`, seuil 45.

> ## ⚠️ LE PÉRIMÈTRE N'ÉTAIT PAS FIGÉ — lire ceci avant le reste
>
> Le titre annonçait « même périmètre pour les trois ». **C'est faux pour un
> article sur six.** La re-production du wiki de Small a **échoué sur un 503 de
> l'API Mistral** (job 37 en `error`) : son texte est resté celui d'une passe
> antérieure, écrite sur **283** extractions, quand les cinq autres articles ont
> été écrits sur **412**. Preuve indépendante dans les textes : le wiki de Small
> ne porte aucun identifiant ≥ 284, là où les cinq autres citent des triplets
> `[[ext:13]][[ext:150]][[ext:284]]` — le même fait extrait par les trois
> extracteurs.
>
> **La seule comparaison réellement propre est celle des trois synthèses**,
> toutes trois sur 412 :
>
> | | citations | vérifiées | faibles | **% vérifiées** |
> |---|---|---|---|---|
> | Small | 147 | 40 | 80 | **33 %** |
> | Medium | 171 | 64 | 74 | **46 %** |
> | Large | 126 | 53 | 49 | **52 %** |
>
> Le classement survit. **C'est ce tableau-là qui aurait dû être le principal.**
>
> Et « figé » n'est pas une propriété du modèle de données : `--forcer` **re-fige
> un périmètre neuf** (`front/tasks.py:1432`). C'est une propriété du
> **protocole d'exécution** — ne pas lancer d'extraction entre les passes —, et
> c'est précisément ce qui a manqué.

Données brutes : `redacteur_small.json`, `redacteur_medium.json`,
`redacteur_large.json`. Mesure rejouable : `mesurer_les_redacteurs.py`.

---

> ## ⚠️ LE VERBATIM A ÉTÉ MESURÉ DEPUIS — cette section se trompe de cause
>
> Ce texte conclut que les ~14 % non verbatim sont « un trait Mistral » à
> corriger par **le prompt d'extraction**. Le typage des écarts, fait le
> 19 août, dit autre chose :
>
> - la concaténation soupçonnée fait **3 cas sur 21** chez Small ;
> - sur les 60 citations `INTROUVABLE` des articles, **11 seulement (18 %)**
>   sont un vrai saut de passage ;
> - la cause dominante est **notre ingestion** : la page 1 porte littéralement
>   `territoire .`, un point détaché de son mot, que les trois Mistral
>   recollent et que notre comparaison leur refuse.
>
> Le levier « durcir le prompt » vaut **8 liens sur 60**, pas la majorité.
> Détail et méthode :
> `benchmarks/extraction_format/2026-08-19_le-mode-d-echec-du-verbatim.md`.

## 1. L'EXTRACTION — la taille du modèle n'y change RIEN

| modèle | notes | extraits | **verbatim** | médiane | tarif |
|---|---|---|---|---|---|
| `mistral-large` | 5 | 134 | **87 %** | 108 car. | 0,50/1,50 |
| `mistral-medium` | 4 | 129 | **83 %** | 105 car. | 1,50/7,50 |
| `mistral-small` | 5 | 137 | **85 %** | 107 car. | 0,15/0,60 |
| *(rappel)* `gemini-2.5-flash` | 5 | 112 | **100 %** | — | 0,30/2,50 |

**Les trois sont équivalents à l'intérieur du bruit** (83-87 %), et Medium — dix
fois le prix de Small — est le **plus mauvais**. La granularité est identique
partout (médiane 105-108 caractères).

**Le seul écart qui compte est Mistral / Gemini**, pas Small / Large. Une
extraction non verbatim casse la chaîne de preuve : la vérification la marque
`INTROUVABLE`, et aucun rédacteur ne rattrape ça. C'est un trait de famille que
la taille ne corrige pas — c'est le **prompt d'extraction** qu'il faut éprouver.

## 2. LA RÉDACTION — Large est le plus précis, Medium le plus abondant

| | citations | **vérifiées** | faibles | introuvables | **% vérifiées** | crans 100 | caractères |
|---|---|---|---|---|---|---|---|
| **Small** | 240 | 68 | 122 | 45 | **36 %** | 1 | 13 529 |
| **Medium** | **280** | **96** | 122 | 62 | 44 % | 8 | 13 276 |
| **Large** | 265 | 94 | 91 | 60 | **51 %** | 7 | 14 691 |

*(« % vérifiées » = vérifiées / (vérifiées + faibles). Les `non_verifie` — 5 chez
Small, 20 chez Large — sont des paires dont le juge n'a rendu aucun verdict :
une perte du juge, pas du rédacteur.)*

**Zéro marqueur groupé restant chez les trois.** Le repli du 19 août tourne, et
les workers avaient été redémarrés — sans quoi il ne s'applique pas.

### Le rapport qualité-prix — TABLEAU CORRIGÉ

La première version de ce tableau annonçait Small « le plus mauvais » sur une
colonne « vérifiées par $ de sortie » où il est **le meilleur**. Erreur
d'arithmétique, corrigée :

| | vérifiées (absolu) | prix output | **vérifiées par $ de sortie** |
|---|---|---|---|
| Small | 68 | 0,60 | **113** |
| Medium | 96 | 7,50 | **13** |
| Large | 94 | 1,50 | **63** |

**Small est le meilleur rendement par dollar, d'un facteur presque deux face à
Large.** Medium est disqualifié : cinq fois le prix de Large pour deux citations
vérifiées de plus.

Le choix entre Small et Large n'est donc **pas** un arbitrage de coût — c'est un
arbitrage entre **volume à bas prix** et **précision**. Et voir la réserve
ci-dessous : l'avance de précision de Large n'est pas robuste.

## 3. La correction que cette mesure impose

**Une mesure publiée le 18 août était biaisée, et sa conclusion était fausse.**

Elle donnait Small gagnant (223 citations, 44 % de précision) contre Large
(127 citations, 29 %). Mais **Small avait écrit sur 283 extractions et Large sur
149** : un test d'extraction lancé entre les deux passes avait doublé le
périmètre sans qu'on en tienne compte.

À périmètre égal, **Small est dernier sur les deux critères**.

La leçon, et c'est la deuxième fois de la semaine qu'elle se présente : *avant
d'attribuer un écart à un modèle, vérifier qu'il ne vient pas du dispositif de
mesure.* La première fois, l'écart venait d'un bug de format dans notre
indexeur ; celle-ci, d'un périmètre qui avait bougé entre deux passes.

## 4. Ce que cette mesure ne dit PAS

- **L'avance de précision de Large n'est PAS robuste.** Ses 20 `non_verifie`
  ne sont pas un tirage aléatoire : c'est **un paquet contigu perdu sur un 503**
  pendant une instabilité de l'API qui a traversé toute la campagne. Selon leur
  sort, Large va de **45,9 %** (toutes faibles) à 55,6 % (toutes vérifiées),
  contre 44 % pour Medium — au pire cas, l'écart tombe de 7 points à 2. Au
  total, **30 % des citations de Large n'entrent pas dans son chiffre-titre**
  (60 introuvables + 20 perdues) contre 21 % pour Small : les deux exclusions
  l'avantagent.
- **Le juge sous-note, sur 9 cas relus sur 12.** Il pose son cran 40 (« appuie
  de loin, SANS RIEN ÉTABLIR ») sur des sources qui établissent pleinement une
  part du paragraphe — la définition de son propre cran 70. Ce n'est pas
  *systématique* mais majoritaire, et « sur les paragraphes multi-sources » ne
  discrimine rien : ils le sont quasiment tous (médiane 3 à 6 marqueurs par
  affirmation). Les taux de « % vérifiées » sont des **planchers**, et le biais
  frappant les trois de la même façon, le classement devrait tenir.
- **Le nombre d'extractions DISTINCTES citées resserre tout** : Small **192**,
  Medium **205**, Large **210**. L'écart de 40 citations du tableau fond à 18
  une fois les doublons retirés — et « Medium le plus abondant » ne survit pas.
- **Le pool de 412 est artificiel** : trois extracteurs sur les mêmes cinq
  notes, donc chaque fait existe en ~3 exemplaires. Les rédacteurs citent en
  rafales de doublons. Un carnet réel n'a jamais cette structure : la validité
  externe de ces comptes est faible.
- **Zéro marqueur halluciné** (`marqueurs_retires: []`) sur les six productions
  — un résultat favorable aux trois modèles.
- **Une seule passe par modèle**, deux articles, un corpus.
- **La qualité de la prose n'est pas mesurée ici.** Lecture d'extraits
  seulement : Large écrit plus fluide, mais sa fluidité vient en partie de
  matière conjonctive non sourcée — ce qui devrait produire des crans bas. Or il
  a la meilleure précision. Cette contradiction n'est pas résolue.
- **« Le taux d'introuvables monte avec le nombre de citations » était faux** :
  Small 240 → 18,8 %, **Medium 280 → 22,1 %**, Large 265 → 22,6 %. Non
  monotone. Deux points choisis sur trois.
- **Medium n'a rien extrait de « Palais César »** : job `completed`, un chunk,
  **zéro extraction, zéro erreur** — là où Small en trouve 5 et Large 3. C'est
  indiscernable du défaut silencieux documenté dans `AGENTS.md` (une plateforme
  qui rend `[…]` → `suppress_parse_errors` → liste vide → job `completed`). Le
  tableau imprimait « 4 notes » sans un mot.
- **La ligne de rappel Gemini est invérifiable** : la base a été détruite
  (`down -v`) et `gemini-2.5-flash` est à température **0,7**, sous un en-tête
  qui annonce « températures à 0 ».
- **« Équivalents à l'intérieur du bruit » : le bruit n'a pas été mesuré**, une
  seule passe par modèle. Un calcul binomial sur n≈130 donne ±6 points à 95 % —
  l'équivalence est *plausible*, pas établie. Et on ne peut pas à la fois
  aplatir 83-87 % dans le bruit et y classer Medium « le plus mauvais ».
