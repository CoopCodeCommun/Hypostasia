# Ce que ces deux jours ont mesuré

**17–18 août 2026.** Compte rendu des mesures, des erreurs commises, et de ce
qui reste ouvert. Tous les chiffres cités ont été mesurés ; ceux qui ne l'ont
pas été sont signalés comme tels.

---

## 1. Le chantier livré

`Configuration.ai_model` portait **un seul** modèle pour tout. Une table de rôles
sépare désormais le **rédacteur d'article** du **juge de vérification**, avec un
repli : sans affectation, chaque rôle reprend le modèle de la Configuration, donc
rien ne change le jour du déploiement.

Toutes les plateformes exposant `POST {base_url}/chat/completions` — OpenRouter,
Mistral, Scaleway, orq.ai, un Ollama local — partagent **un seul chemin d'appel**,
paramétré par `base_url`. Une seule valeur d'enum, aucune ligne de code par
plateforme.

**2 007 tests verts**, 22 min 32 s (hors e2e). C'était 1 916 au matin du 17.

### Quatre choses étaient déclarées et ne servaient à rien

| | |
|---|---|
| `AIModel.temperature` | déclaré depuis l'origine, transmis à **aucun** appel |
| `tokens_input_reels`, `tokens_output_reels`, `cout_reel_euros` | **aucun écrivain** dans tout le dépôt ; un bloc d'affichage qui ne pouvait jamais apparaître |
| `bilan_de_verification` | écrit, **jamais lu** — un échec du juge était invisible à l'écran |
| Le fork LangExtract (`AnnotateurAvecProgression`) | **aucun appelant** — 497 lignes retirées, ses tests réimplémentaient sa logique |

Trois sont réparées. La capture des tokens reste ouverte : c'est le socle de la
facturation à l'utilisateur.

---

## 2. Ce que les mesures ont appris

### 2.1 Un verdict de juge n'est pas reproductible

Le juge de production, rejouant **ses propres** 145 paires, retrouve **77 %** de
ses verdicts — à température 0, à trois minutes d'écart. Le nombre de citations
« vérifiées » a varié de **105 à 133** sur cinq exécutions identiques.

**Mais cela dépend du modèle, pas du dispositif.** Les candidats atteignent
**95 %** avec le même prompt et le même jeton imprévisible. Le juge instable est
celui qui « réfléchit » : 150 s contre 8 s pour les mêmes huit appels.

### 2.2 Le désaccord entre juges venait de la QUESTION

Sur les mêmes quinze paires d'une même affirmation, avec le prompt de production,
cinq modèles rendent de **0 à 14** verdicts positifs. Écrire le seuil dans la
consigne fait tomber la dispersion :

| consigne | dispersion entre les 5 modèles |
|---|---|
| prompt de production | **14 points** |
| seuil **large** écrit | 5 points |
| seuil **strict** écrit | **1 point** |

Le mot « établir » n'est défini nulle part. Chaque modèle plaçait la barre à sa
façon — et deux relectures humaines (les miennes) l'ont placée à deux endroits
opposés à vingt-quatre heures d'intervalle.

### 2.3 Un score règle ce que le verdict binaire ne peut pas régler

Demander « à quel point » plutôt que « oui ou non » :

| Juge | meilleur seuil | accord |
|---|---|---|
| `gemini-2.5-flash` | 45/100 | **15/15** |
| `gemini-3.1-flash-lite` | 45/100 | 14/15 |
| `gpt-5-mini` | 45/100 | 14/15 |
| `mistral-small-latest` | — | 13/15 |

Le modèle le **moins** stable en verdict binaire devient le **meilleur** en score.

**Deux réserves.** Les modèles se collent aux repères donnés dans le prompt
(0 · 40 · 70 · 100) : c'est une échelle à quatre crans, pas un continuum. Et la
voie propre — lire les **logprobs** du token de verdict — est **fermée** sur les
deux API : Mistral répond « *Logprobs are not enabled for this model* », OpenAI
oppose un 403 sur ses modèles de raisonnement.

### 2.4 L'extraction est le maillon le moins réglé

Sur un même extrait de débat à trois voix, cinq modèles rendent de **5 à 18**
extractions. Ce qui compte n'est pas le nombre :

| Modèle | extraits | verbatim | médiane | couverture | voix |
|---|---|---|---|---|---|
| `gemini-2.5-flash` | 6 | 6/6 | **330 car.** | 98 % | 2·2·2 |
| `gemini-3.1-flash-lite` | 8 | 8/8 | 140 | 54 % | 3·3·2 |
| `gpt-5-mini` | 8 | 8/8 | 123 | 59 % | 4·3·**1** |
| `gpt-5-nano` | 6 | 6/6 | 118 | **37 %** | 4·**0**·2 |
| `mistral-small-latest` | 18 | 18/18 | 101 | 97 % | **6·6·6** |

- `gemini-2.5-flash` **recopie les tours de parole** (médiane = la taille d'une
  intervention) : l'ancre désigne tout, donc rien.
- `gpt-5-nano` **perd une voix** sur cette passe — les deux idées maîtresses du
  contradicteur disparaissent. Sur un outil de délibération, c'est un défaut de
  nature. *(Réserve : mesuré sur la passe 1 ; aux passes 2-3, une extraction
  d'Eric réapparaît.)*
- `gemini-3.1-flash-lite` **coupe des conditions** : il retient « une ressource
  qui peut être gouvernée comme un commun numérique » en s'arrêtant avant « à
  condition que les communautés participent ». L'extrait reste verbatim, donc
  **l'amputation de sens franchit toutes les défenses automatiques**.
- `mistral-small` est le plus équilibré sur cette passe. *(Réserve : aux passes
  2-3 il tombe à 6·5·4, et il réécrit un extrait — donc non verbatim, donc
  inancrable. Le « tous verbatim » n'est vrai que de la passe 1.)*

**La température n'est pas transmise à ce chemin** : le réglage que porte un
modèle ne vaut donc que pour la moitié de ses usages.

### 2.5 Le contrat de sortie tient

**Zéro marqueur de citation inventé** sur les quinze rédactions mesurées, chez
les cinq modèles. Le dispositif qui supprime les citations inventées n'a rien eu
à supprimer.

Et à température 0, deux modèles rendent **trois articles identiques octet pour
octet**. La rédaction est déterministe quand on la règle.

---

## 3. Ce que j'ai eu faux, et qui l'a rattrapé

Trois relectures adverses par un agent `fable` ont rattrapé, à chaque fois, des
conclusions que j'avais **publiées**.

| Ce que j'avais écrit | Ce que la mesure dit |
|---|---|
| L'écart wiki 97 % / synthèse 71 % s'explique par 36 % de sources en plus | **Faux.** À nombre de sources égal, l'écart persiste : wiki **100 %** contre synthèse **70 %**. `r = −0,25` |
| L'instabilité du juge est structurelle, causée par le jeton imprévisible | **Faux.** Les autres juges atteignent 95 % avec le même jeton. C'est le modèle |
| « 59 % des citations passeraient en faible » | **Faux.** 77/145 = **53 %**. Un chiffre non mesuré dans une décision |
| « Mistral avait raison sur les trois paires relues » | Prématuré : j'appliquais une lecture étroite sans l'avoir examinée |
| « Mistral se trompe sept fois, les permissifs ont raison » | **Réfuté par mon propre tableau** : le juge de référence s'accorde avec Mistral à **14/15**, et mon accord avec lui n'est que de 9/15 |
| « ShieldStral ne transfère pas à l'implication » | **Faux — corrigé le 18 août**, voir § 4 |

**La leçon de méthode**, et elle vaut plus que le chantier : *quand une mesure
semble contredire une lecture existante, la tester à conditions égales avant de
publier la nouvelle.* Deux de ces six erreurs sont des explications trouvées trop
vite, et deux sont des seuils appliqués sans les avoir écrits.

**Le conflit d'intérêt, nommé** : je suis un modèle de langage qui juge d'autres
modèles de langage, et ma conclusion validait commodément le juge que j'avais
moi-même affecté en production le matin. Les quinze verdicts restent publiés,
motif par motif, pour être contredits un par un.

---

## 4. ShieldStral — le cadrage fait tout

Modèle de **modération** de Mistral, poids **Apache 2.0**, 3,8 milliards de
paramètres, 7,7 Go. Il tourne ici **sur processeur, sans clé, sans réseau**.

Ce n'est pas un classifieur à catégories fixes : l'opérateur écrit sa **propre
question binaire**, le modèle rend **un seul token**, et on lit ses logits — donc
**un score continu, vraiment calibré**, là où les API refusent les logprobs.

**Deux cadrages, deux résultats opposés :**

| Cadrage | accord | AUC |
|---|---|---|
| affirmation **et** source dans le même `<Document>` | **4/15** | — |
| `<Document>` = la source seule, `<Query>` portant l'affirmation | **14/15** | **0,92** |

**Le premier résultat était le mien, pas celui du modèle.** En respectant la
structure `<Instruct>` / `<Query>` / `<Document>` que sa fiche décrit, il classe
correctement **24 couples sur 26**. Une conclusion négative écrite après le
premier essai aurait été fausse — et je l'avais écrite.

**Ce qui reste à éprouver** : le seuil optimal (0,05) est choisi *après coup* sur
quinze points, donc sur-ajusté ; le classement place quelques reprises quasi
littérales très bas. Il faut refaire la mesure sur plusieurs affirmations avant
d'en tirer un classement.

---

## 5. Souveraineté : où en est-on

Mesuré, pas supposé — la chaîne entière tourne chez Mistral :

| Besoin | Chez Mistral | État |
|---|---|---|
| Extraction | `mistral-small-latest` | ✅ le découpage le plus fin des cinq |
| Rédaction | `mistral-small-latest` | ✅ 0 marqueur inventé |
| Juge | `mistral-small-latest` | ✅ 13/15 en score, stabilité 95 % |
| Transcription | `voxtral-mini-latest` | ✅ **en production**, 14,8 s d'audio en 1,9 s, 2 locuteurs séparés |
| Juge binaire local | ShieldStral | ✅ poids ouverts, rien ne sort de la machine |
| **Embedding (RAG)** | `mistral-embed` | ⚠️ **le maillon faible** — décembre 2023, jamais renouvelé, aucune revendication multilingue |

Le RAG n'existe pas encore dans le code : le maillon faible n'est donc pas encore
un problème. `bge-m3` chez OVHcloud (0,01 €/M, MIT, 8 192 tokens) reste
l'alternative à mesurer le jour venu.

**Le verrou LangExtract est levé** : il routait par expression régulière sur le
nom du modèle (`^mistral` → Ollama), et `lx.extract` accepte un `config` qui
résout le provider par son **nom**. API publique, **aucun fork**.

---

## 6. Ce qui reste ouvert

1. **L'addendum de spec sur le seuil** — le geste qui manque depuis le début. Le
   mot « établir » doit être défini, ou remplacé par un score. Tant qu'il ne l'est
   pas, aucun classement de juges ne veut dire quoi que ce soit.
2. **Le passage au score** : `verifie` et `faible` cessent d'être deux états pour
   devenir deux côtés d'un curseur. `introuvable` reste déterministe, `contesté`
   reste humain, la provenance reste attachée.
3. **La capture des tokens réels** — préalable à toute facturation.
4. **Le risque du JSON nu** : une plateforme qui rend `[...]` au lieu de
   `{"extractions": [...]}` perd ses extractions **en silence**. Le fork censé
   s'en prémunir était mort ; rien ne le couvre.
5. **Le référentiel des modèles vieillit sans que rien ne le dise** :
   `gemini-2.5-flash-lite` y figure encore et répond 404 ; un tarif de mars avait
   augmenté sans surveillance.
6. **Refaire le jugement des juges sur dix affirmations**, une fois le seuil
   écrit, et par quelqu'un d'autre que le modèle qui a choisi le juge.

---

## 7. Les bancs, et comment les rejouer

| Banc | Ce qu'il mesure |
|---|---|
| `benchmarks/juge_de_verification/comparer_un_juge.py` | accord et **stabilité** d'un juge contre l'étalon gelé |
| `…/comparer_les_seuils.py` | l'effet d'écrire le seuil dans la consigne |
| `…/comparer_les_scores.py` | un juge qui rend un degré au lieu d'un verdict |
| `…/comparer_shieldstral.py` | un juge **local**, à score calibré |
| `benchmarks/chaine_complete/comparer_la_chaine.py` | les trois étages, N modèles, N passes |
| `…/rendre_le_rapport.py` | le rapport HTML, engendré depuis les mesures |

**Aucun n'écrit en base.** L'étalon des 145 paires est gelé dans
`benchmarks/juge_de_verification/etalon-du-juge.json` — mesuré intact après une
vingtaine d'exécutions.
