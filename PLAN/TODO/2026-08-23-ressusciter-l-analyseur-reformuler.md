# Ressusciter l'analyseur « reformuler » — du verbatim oral à l'énoncé auto-suffisant

**Intention du mainteneur, 23 août 2026. Rien n'est codé.**

Cette note s'appuie sur un **dossier de conception externe** (recherche du 23 août 2026,
GDN-CC, distorsion de certitude, stratégies de décodage) que le mainteneur a fourni.
**Elle ne le recopie pas** : elle dit ce qu'il devient une fois confronté au code
d'Hypostasia — ce qui est déjà là, ce qui manque, et ce que nos invariants imposent.
Le dossier a sa place dans `PLAN/Documents exterieurs/`.

---

## 1. Ce qui a été retiré, et pourquoi — ce n'est pas un rejet

`TypeAnalyseur` portait `REFORMULER` et `RESTITUER` (migrations 0011, 0025), et
`ExtractedEntity` douze champs : `texte_reformule`, `reformule_par`,
`reformulation_en_cours`, `reformulation_lancee_a`, `reformulation_erreur`, plus la
restitution. Tout a été retiré le **2 mai 2026** par le chantier A.7
(`PLAN/archive/A.7-retrait-reformulation-restitution.md`, migration
`0028_a7_retrait_reformulation_restitution_fields`), ~3 000 lignes.

**Le motif est écrit, et il compte** :

> DB live : 134 ExtractedEntity, **0 reformulations**, 0 restitutions […] aucun bouton
> Reformuler / Restituer visible — sections IA jamais déclenchées car les champs DB
> sont vides.

C'était du **code mort**, jamais branché à l'interface. Le retrait n'a rien tranché
sur le fond. **Ressusciter est donc légitime** — mais la leçon est qu'une fonction
sans point d'entrée à l'écran n'existe pas.

---

## 2. Le besoin, dans le vocabulaire du projet

Une extraction porte `extraction_text` : le **verbatim exact** du passage, et c'est
l'ancre qui fait la preuve. Sur une transcription, ce verbatim est de l'oral
spontané — reprises, hésitations, déictiques, style direct :

> « ben moi je pense qu'il faudrait peut-être qu'on revoie ça, enfin, ce truc-là »

Ce verbatim est **excellent comme preuve** et **mauvais comme matériau de rédaction** :
il n'est pas auto-suffisant hors de son contexte. Le rédacteur d'article le reçoit tel
quel (`_blocs_d_extractions_par_note`, `front/tasks.py:1048`, envoie
`Citation : "{extraction_text}"`), et c'est à lui de le transposer — c'est-à-dire à
l'étape où l'on contrôle le moins.

**Ce que « reformuler » produirait** : à côté du verbatim, un **énoncé auto-suffisant
en style indirect**, dérivé mécaniquement, contrôlé, et traçable.

C'est très exactement la tâche du corpus **GDN-CC** (ISIR/Sorbonne, ACL 2026) :
réécrire une *unité argumentative* du Grand Débat National en énoncé auto-suffisant.
Leur « unité argumentative » est notre **extraction**. La correspondance est directe.

---

## 3. Le risque n°1 — et il est pire ici qu'ailleurs

Le dossier externe établit que le vrai mode de défaillance n'est pas l'hallucination
mais la **distorsion de certitude** : le contenu propositionnel est préservé, le degré
d'engagement du locuteur ne l'est pas. Mesuré **30 à 49,5 %** en réécriture de phrase,
avec un biais **1,5 à 2×** vers l'inflation, **+40 % après cinq itérations**, et un
effet de la température **quasi nul**. Aucune métrique de similarité ne le voit :
BERTScore rend 0,95.

**Dans Hypostasia, cela ne trahit pas seulement le locuteur : cela CHANGE L'HYPOSTASE.**

C'est le point que le dossier externe ne pouvait pas connaître, et il commande toute
la conception. Les 30 hypostases sont classées par **dispositif de preuve** et **mode
de raisonnement** — six familles épistémiques. Le référentiel dit, mot pour mot :

- **conjecture** : « opinion ou proposition non vérifiée » — *non prouvé par déduction empirique*
- **hypothèse** : « explication ou possibilité d'un événement » — *non prouvé par induction empirique*
- **croyance** : « certitude ou conviction qui fait croire une chose vraie ou possible »
- **loi** : « corrélation » — *non prouvé par induction empirique*

« Je pense qu'il faudrait peut-être réformer ça » est une **conjecture**. Reformulé en
« il faut réformer cela », c'est un **principe**, voire une **loi**. Le degré de
certitude **est** l'axe de classement : le détruire ne dégrade pas le style, il
reclasse l'énoncé dans une autre famille épistémique.

Et l'effet se propage : le **statut de débat**, l'alignement cross-documents, la
géométrie du débat — tout repose sur ce typage. Une inflation de certitude à 30 % sur
un corpus fabriquerait un faux consensus, mécaniquement, et de façon invisible.

**Conséquence de conception** : le contrôle de modalité n'est pas une garde parmi
d'autres, c'est **la** condition d'existence de la fonction. Une reformulation qui ne
préserve pas le marqueur épistémique est **rejetée**, jamais publiée avec une réserve.

---

## 4. Ce qui est DÉJÀ en place — plus que le dossier ne le suppose

| Ce que le dossier recommande | Ce que le dépôt a déjà |
|---|---|
| Un vérificateur NLI **français**, bidirectionnel | **`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` est installé** (`core/services/juges_locaux.py:106`), avec **CamemBERTa v2** (`almanach/camembertav2-base-xnli`) et **bge-m3**. Ce sont exactement les briques du § 5 du dossier |
| Une infrastructure pour les faire tourner sans gêner le reste | Le worker **`celery_worker_juge_local`**, file `verification_locale`, **concurrence 1**, sous **`nice -n 19`** — conçu précisément pour des encodeurs résidents |
| Une API d'inférence distante | **`Provider.COMPATIBLE_OPENAI`** + `base_url` + `variable_de_cle_api` : brancher **OVH AI Endpoints** ne demande **aucune ligne de code**, seulement une ligne en base |
| Greedy plutôt que sampling | Le champ **`AIModel.temperature`** existe, et tous les bancs mesurent déjà à **0** |
| « Au plus un retry » | La culture est acquise : la nuit écrit un **tour d'échec** plutôt que de boucler |
| Une bibliothèque de prompts éditable | `AnalyseurSyntaxique` + `PromptPiece` + versions + banc d'essai, écran `/api/analyseurs/` |
| Un journal des éditions | `PageEdit`, `TypeEdit` |

**Le vérificateur du § 5 du dossier est donc à moitié construit, et il tourne déjà.**
Ce qui manque n'est pas l'infrastructure : c'est **l'implication bidirectionnelle**
(source → réécriture détecte l'ajout ; réécriture → source détecte la perte) et le
seuil.

⚠️ **Mais l'existant porte un défaut connu, et il frappe ici aussi** :
`2026-08-22-la-marge-de-neutralite-des-juges-locaux.md` mesure que **CamemBERTa v2 et
mDeBERTa v3 se taisent 85 % du temps**, parce qu'une marge unique de 2,5 points sert
quatre juges aux échelles incompatibles. **Un vérificateur de reformulation bâti
là-dessus hériterait du même mutisme.** Cette note-là est donc un **préalable**, pas
un voisin.

---

## 5. L'architecture

### 5.1 Sur quoi porte la reformulation — l'extraction, et rien d'autre

L'unité est l'**`ExtractedEntity`**, comme dans l'implémentation retirée, et comme
l'unité argumentative de GDN-CC. Pas l'`ElementDocument` : un tour de parole est trop
gros, et le toucher déplacerait les ancres.

### 5.2 Le résultat vit À CÔTÉ, jamais à la place

**Invariant non négociable** : `extraction_text` est le verbatim exact, et c'est lui
que l'ancre garantit. La reformulation est un champ distinct — ou une table liée si
l'on veut en garder plusieurs versions. **Aucun chemin ne doit pouvoir écraser le
verbatim.**

Corollaire à écrire dans le code, pas seulement ici : la vérification § 7 continue de
juger la paire (extraction, paragraphe) **contre le verbatim**, jamais contre la
reformulation. Sinon on vérifierait une réécriture contre une réécriture.

### 5.3 Qui la consomme

Trois consommateurs possibles, et ils ne posent pas le même risque :

| Consommateur | Effet | Risque |
|---|---|---|
| le **rédacteur d'article** (`_blocs_d_extractions_par_note`) | reçoit l'énoncé auto-suffisant au lieu du verbatim brut | **le plus utile, et le plus engageant** : c'est ce qui finit dans un article |
| l'**affichage** d'une carte d'extraction | montre la reformulation, le verbatim au clic | faible — le verbatim reste à un clic |
| l'**alignement cross-documents** | compare des énoncés normalisés | à instruire : la normalisation peut créer de faux alignements |

**Le premier jet ne devrait servir que l'affichage.** Donner la reformulation au
rédacteur avant d'avoir mesuré le taux de distorsion sur notre propre corpus reviendrait
à injecter le risque du § 3 directement dans les articles.

### 5.4 Le type d'analyseur revient

`reformuler` retourne dans `TypeAnalyseur` — 10 caractères, il tient dans le
`max_length=20`. **Mais il s'ajoute au typage en cours** :
`2026-08-23-typer-les-analyseurs-par-action.md` prévoit trois types ; ce serait le
quatrième. Les onze querysets `filter(type_analyseur=…)` en dur, les deux `<select>` et
la garde d'utilisabilité y sont recensés : **faire les deux dans le même chantier**,
pas l'un après l'autre.

---

## 6. Les quatre gardes, dont trois sont gratuites

Reprises du dossier externe, ordonnées par ce qu'elles coûtent :

1. **Greedy ou beam, jamais de sampling.** Trente points de FactCC sur CNN/DM
   (84,23 contre 54,05 en nucleus). Et surtout : **le greedy est reproductible** — on
   peut rejouer une reformulation et obtenir le même texte, ce que l'opposabilité
   exige. Coût : un champ déjà présent, mis à 0.
2. **Le contrôle de modalité** — lexique fermé de marqueurs épistémiques
   (*peut-être, je crois, il me semble, sans doute, probablement, devrait, faudrait,
   pourrait*) : présent en source, absent en sortie ⇒ **rejet**. C'est la garde du § 3,
   elle est déterministe, sans latence, **et explicable à un contradicteur**. Coût :
   une centaine de lignes de Python.
3. **L'inventaire et la polarité** — entités nommées, nombres, dates présents en source
   doivent l'être en sortie ; négations et antonymes contrôlés. Coût : idem.
4. **Le NLI bidirectionnel** — sur l'infrastructure des juges locaux (§ 4). Coût réel,
   mais l'essentiel est déjà installé.

**Les gardes 1 à 3 éliminent la majeure partie du risque sans un seul modèle
supplémentaire et sans un octet de données d'entraînement.** C'est par là qu'on
commence.

---

## 7. L'hébergement — la contrainte que le dossier ne connaît pas

**La cible de déploiement est un VPS CPU, sans GPU.** Et la machine porte déjà les
quatre encodeurs NLI : **5,13 Go de RSS pour 6,01 Go de pic** (mesure du 19 août), à
quoi s'ajoutent une conversion Docling (~2 Go) et PostgreSQL. `AGENTS.md` en tire déjà
la conclusion : **cela exclut un VPS de 4 ou 8 Go**.

Un Gemma 4 12B en Q4 pèse ~7 Go de plus, et sur CPU sa latence se compte en secondes
par extraction. **Le faire tourner à côté des juges est exclu sur la cible actuelle.**

Trois voies, à trancher :

| Voie | Ce que ça coûte | Ce que ça donne |
|---|---|---|
| **OVH AI Endpoints** (ou équivalent) via `COMPATIBLE_OPENAI` | facturé, dépendance réseau, **zéro ligne de code** | le chemin le plus court pour mesurer |
| **Un worker dédié** sur une machine à GPU | une machine de plus, une file de plus | l'auto-hébergement complet, plus tard |
| **Un petit modèle sur CPU** | latence à mesurer | à n'envisager qu'après avoir mesuré le besoin |

**Recommandation** : commencer par OVH pour **mesurer**, décider de l'auto-hébergement
ensuite sur des chiffres. Le projet a déjà un précédent : `bge-m3` chez OVHcloud à
0,01 €/M (banc du 18 août).

---

## 8. Le fine-tuning — le vrai gain, et il est chiffré

Le résultat central de GDN-CC : les LLM zero-shot commettent **72 % d'erreurs de
sur-analyse** — ajout d'une analyse ou d'une conclusion absente du texte — **« même
lorsqu'on leur demande explicitement de ne rien ajouter »**. Un simple SFT fait tomber
ce taux à **2 %**. Facteur 36, en français, sur une tâche quasi identique à la nôtre.

**La sur-analyse est, pour nous, exactement le même défaut que la distorsion de
certitude** : ajouter une conclusion, c'est produire une hypostase que personne n'a
prononcée.

Le dossier externe recommande de **refaire leur fine-tuning sur un modèle Apache 2.0**
plutôt que d'utiliser `LequeuISIR/AU-clarification_gemma-2-9b-it`, qui n'a **aucune
licence déclarée** et dérive d'un modèle sous Gemma Terms of Use. **C'est décisif
ici** : Jean Sallantin pose comme objectif qu'« Hypostasia doit devenir un commun
numérique libre » — un modèle non librement licencié au cœur du produit contredirait
la raison d'être du projet. Leur dataset (`LequeuISIR/GDN-CC`, 2 285 unités annotées à
la main) et leur code sont publics.

Budget de référence donné par le dossier : ~100 GPU-heures H100 pour l'ensemble de
leurs expériences, donc quelques heures pour un run — LoRA sur une L4, ou ~50 € de
location.

---

## 9. Le plan

**Étape 1 — le gratuit, et rien d'autre.** Greedy à 0, les trois contrôles symboliques
(§ 6.1 à 6.3), le prompt de GDN-CC avec sa clause « si le segment est déjà clair, tu le
recopies » — la meilleure garde anti-embellissement à coût nul — plus une consigne
explicite de préservation de la certitude. Sortie affichée **à côté** du verbatim,
consommée par **personne d'autre**.

**Étape 2 — mesurer sur NOTRE corpus.** Annoter 100 à 200 extractions de nos propres
transcriptions, et mesurer deux taux : sur-analyse, et distorsion de certitude. Le
dossier le dit lui-même : *« la distorsion de certitude n'a été mesurée qu'en anglais ;
son existence en français est une extrapolation raisonnable, non mesurée — c'est
probablement la mesure la plus rentable que tu puisses faire. »* **Pour nous, il y a
une troisième mesure, et c'est la nôtre : le taux de CHANGEMENT D'HYPOSTASE.** Faire
re-typer par l'analyseur d'extraction le verbatim puis la reformulation, et compter les
divergences. Elle se calcule avec ce qui existe déjà.

**Étape 3 — le vérificateur.** NLI bidirectionnel sur l'infrastructure des juges
locaux — **après** avoir réglé la marge de neutralité, sans quoi il se taira 85 % du
temps.

**Étape 4 — le fine-tuning**, si et seulement si l'étape 2 confirme les taux.

**Plus tard, si le besoin est là** : la sortie structurée sous grammaire et les règles
Grew (§ 3 du dossier externe). C'est ce qui rendrait le système réellement opposable —
chaque transformation traçable à une règle nommée — et c'est aussi ce qui coûte le
plus.

**Ne pas boucler** : au plus un retry, puis on renvoie le verbatim **inchangé**, marqué
« non reformulé ». Un bloc laissé en citation directe est un échec acceptable ; un bloc
réécrit trois fois jusqu'à passer le vérificateur est un risque.

---

## 10. Ce qu'il faut trancher

1. **Un champ ou une table ?** Un champ suffit pour une version ; une table permet de
   garder l'historique et le modèle qui a produit chaque version — cohérent avec la
   traçabilité que le projet réclame partout ailleurs.
2. **Le déclenchement** : à l'analyse (une reformulation par extraction produite,
   facturé au fil de l'eau), à la demande, ou la nuit ? Sur un carnet à 397 extractions,
   la première option est un coût qu'il faut avoir chiffré.
3. **Le rédacteur reçoit-il la reformulation ?** Pas au premier jet — voir § 5.3.
4. **Quel modèle, et où ?** § 7. À décider sur mesure, pas sur benchmark : le dossier
   rappelle qu'aucun classement français à jour n'existe, et que « la qualité de
   génération et les scores de benchmark divergent ».
5. **Que devient une reformulation quand le verbatim change** — correction de
   transcription, ré-ingestion ? La réponse cohérente avec le reste du projet est
   qu'elle est **invalidée**, comme une portion se détache. À écrire.

---

## 11. Ce qu'il faut mesurer

**Fixtures étalons à écrire** : 100 à 200 extractions de transcriptions réelles, avec
leur reformulation **annotée à la main** — c'est l'étalon, et il n'existe pas. Sur le
modèle de `benchmarks/juge_de_verification/etalon-du-juge.json`, gelé hors base.

**Un banc LLM réel** (`make test-llm`, tag `llm_reel`, **facturé**) : zero-shot contre
fine-tuné, sur les trois taux du § 9 étape 2. Métriques : **ROUGE-L, pas BERTScore** —
le dossier montre que BERTScore ne distingue pas (0,81 → 0,86 quand ROUGE-L fait
0,45 → 0,60), et que les métriques de similarité ne corrèlent avec l'humain que sur
des jeux trop faciles.

**Attention au bruit** : `PLAN/PASSATION.md` § 6 mesure **11 points d'amplitude
intra-modèle** sur ce type de taux. Répéter, et ne rien conclure d'un écart plus petit.

---

## 12. Ce qui casse si on ne fait rien

Rien. Les articles continuent d'être rédigés directement à partir du verbatim oral, et
c'est le modèle rédacteur qui fait la transposition — sans contrôle, sans trace, et à
l'étape où l'on mesure le moins. La reformulation ne répare pas une panne : elle
**déplace une transformation invisible vers un endroit où elle devient contrôlable**.

C'est aussi ce qui la rend intéressante : elle rend explicite, mesurable et rejetable
un geste que le système fait déjà, en silence, à chaque production d'article.
