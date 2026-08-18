# Un modèle par rôle, et un seul chemin d'appel / One model per role, one call path

**Date :** 2026-08-17
**Migration :** Oui — `core.0065_modeleparrole` et `core.0066_aimodel_variable_de_cle_api_alter_aimodel_base_url_and_more`
```bash
docker exec -w /app hypostasia_web python manage.py migrate core
```

## Résumé / Summary

**Quoi / What :** `Configuration.ai_model` portait UN SEUL modèle pour tout. Une table de
rôles sépare désormais le **rédacteur d'article** du **juge de vérification**, et toutes
les plateformes exposant `POST {base_url}/chat/completions` — OpenRouter, Mistral,
Scaleway, un Ollama local — passent par **un seul chemin d'appel**, avec timeout et
tentatives explicites.
*/ A role table separates the article writer from the verification judge, and every
OpenAI-compatible platform now shares one call path with explicit timeouts and retries.*

**Pourquoi / Why :** rédiger un article et répondre « soutient / ne_soutient_pas » sur un
lot de vingt paires sont deux métiers opposés — l'un doit être bon, l'autre petit et peu
cher. Tant qu'un seul champ les portait, un juge spécialisé était impossible, et donc
aussi la mesure qui permettrait de le choisir.
*/ Writing and judging are opposite jobs; a single field made a specialized judge — and
the measurement needed to choose one — impossible.*

---

## ⚠️ CE QUI A CHANGÉ DANS LA VÉRIFICATION, ET QU'IL FAUT SAVOIR

L'encart de `CHANGELOG/2026-08-17-la-verification-des-citations-a-l-installation.md` reste
valable **en entier**. Trois précisions s'y ajoutent.

### 1. Un échec du juge ne dégrade plus RIEN — et il le dit

Le CHANGELOG du 17 août affirmait déjà « le juge ne dégrade jamais rien quand il échoue ».
**C'était vrai de l'exception, pas de la réponse rejetée** : un lot rejeté ou un verdict
manquant écrivait `NON_VERIFIE` par-dessus le verdict précédent, estampillait la provenance
du juge qui venait d'échouer, et **vidait `commentaires_source`** au passage — la provenance
« sourcée par le débat » devenait fausse.

Désormais, quand le juge n'a rien dit d'une paire : **on ne touche à rien.** Ni l'état, ni
la provenance, ni la date, ni le lien vers le commentaire porteur. Une paire jamais jugée
reste « non vérifié » — le défaut restrictif tient tout seul, sans qu'on ait besoin de
l'écrire.

**Conséquence obligatoire, et c'est la seconde moitié du changement** : une vérification
entièrement ratée rendrait sinon un écran **rigoureusement identique** à celui d'avant le
clic, avec une tâche « terminée ». L'écran d'article porte donc un bandeau qui nomme le
nombre de citations non jugées et le motif rapporté. `bilan_de_verification` n'avait
**aucun lecteur** dans tout le dépôt : il en a un.

### 2. Un lot inexploitable est recoupé en deux — mais jamais sur une exception

Un juge qui cale sur vingt paires en juge parfois cinq. Un paquet dont la réponse revient
inexploitable est donc **recoupé en deux**, jusqu'à deux niveaux : « vingt paires perdues »
devient « cinq perdues », pour sept appels au pire au lieu de trente-neuf qu'aurait coûté
une dichotomie complète.

**Une exception ne déclenche aucun recoupage.** Une exception, c'est le service qui refuse
— quota, délai, panne : redécouper multiplierait les appels d'un fournisseur qui dit déjà
non, et la facture avec.

### 3. L'étalon des 145 paires est GELÉ, et il l'a fallu

Les verdicts vivent dans une colonne **qu'on réécrit**. Le bouton « Vérifier les
citations » rejuge tout l'article ; `verifier_les_citations_etalons` en fait autant dès
qu'une **seule** paire a perdu son verdict — sa docstring disait « seules les paires sans
verdict partent au juge », c'est faux, le saut est au grain de l'ARTICLE ; et `--forcer`
rejuge sans condition. Une mesure qui ne vit que dans une colonne réécrivable n'est pas
une mesure : c'est un état.

`benchmarks/juge_de_verification/etalon-du-juge.json` porte donc les **145 paires**, leur
question exacte et la réponse du juge de référence. **Mesuré le 17 août 2026 : 118
`verifie`, 27 `faible`, zéro dérive, une seule provenance — `verbatim+nli-lot v2 — Gemini
2.5 Flash`.**

Ce n'est PAS une fixture : rien ne le charge en base, et le banc le lit à chaque exécution.

---

## Ce qui a changé

### La table de rôles

| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | **Nouveau** — `RoleDeModele` (rédacteur d'article, juge de vérification) et `ModeleParRole` (rôle unique, FK en PROTECT) |
| `core/services/modeles_par_role.py` | **Nouveau** — `modele_du_role()` : la ligne du rôle, sinon **repli** sur `Configuration.ai_model` ; **lève** sur un rôle inconnu |
| `front/management/commands/affecter_un_modele_a_un_role.py` | **Nouveau** — le seul levier pour choisir un juge (l'admin Django est désactivé) |

**La table peut rester vide, et elle l'est au déploiement** : sans affectation, chaque rôle
retombe sur `Configuration.ai_model` et rien ne change. C'est la seule façon de livrer ça
sans rien casser le jour même.

**Un modèle créé pour un rôle naît `is_active=False`.** L'écran de configuration IA propose
au clic **tout modèle actif** et le pose dans `Configuration.ai_model` — qui est le modèle
d'**extraction**. Or LangExtract ne sait piloter que Google, OpenAI et Ollama : un modèle
de plateforme laissé actif éteindrait l'extraction d'un seul clic. `modele_du_role` ne
filtre volontairement pas sur `is_active` : « inactif » veut dire « pas proposable au
choix », pas « inutilisable ».

### Le branchement des rôles

Le rôle se résout **à la création du job**, jamais à l'appel : c'est `ExtractionJob.ai_model`
qui porte la provenance de ce qui a été produit.

| Fichier / File | Changement / Change |
|---|---|
| `front/views_synthese.py` | production de wiki, proposition de mise à jour, synthèse de carnet → **rédacteur** ; les deux endpoints de vérification → **juge** |
| `front/views.py` | synthèse par note et son écran de confirmation → **rédacteur** |
| `core/services/verification.py` | le juge par défaut est celui du rôle |
| `front/management/commands/produire_les_syntheses_etalons.py` | rédacteur |
| `front/management/commands/verifier_les_citations_etalons.py` | juge |

**Défaut corrigé au passage** : `synthetiser_page_task` relisait `Configuration.ai_model`
au moment de son exécution et **ignorait `job.ai_model`**. Le job estampillait un modèle et
la tâche en utilisait un autre : dès que le modèle configuré changeait pendant que le job
attendait dans la file, la provenance enregistrée était fausse.

### Le chemin d'appel partagé

| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | `Provider.COMPATIBLE_OPENAI`, champ `variable_de_cle_api`, règle `vendor/modele`, provider explicite prioritaire sur la table de préfixes |
| `core/llm_providers.py` | `_appeler_le_chemin_compatible()` partagé par OpenAI, Ollama et les plateformes ; timeout et tentatives explicites sur **les quatre** providers ; détection du « HTTP 200 avec corps d'erreur » |
| `.env.example`, `bin/configurer_env.sh` | `OPENROUTER_API_KEY` |

**Une seule valeur d'enum pour toutes les plateformes.** C'est `base_url` qui dit laquelle,
et `variable_de_cle_api` où trouver sa clé. Une valeur par plateforme obligerait à toucher
au code à chaque nouvelle, pour un chemin d'appel rigoureusement identique.

**Trois pièges de déduction du provider, tous silencieux, tous fermés :**

| Identifiant | Ce qui se passait | Pourquoi |
|---|---|---|
| `openai/gpt-4o-mini` | provider **MOCK** → `[MOCK] …` sans erreur | ne matche aucun préfixe, le défaut du champ est MOCK |
| `mistralai/…`, `qwen/…`, `deepseek/…` | provider **OLLAMA** → POST vers `localhost:11434` | matchent les préfixes « mistral », « qwen », « deepseek » |
| `mistral-small-latest` (Mistral en direct) | provider **OLLAMA** | même cause, et la règle `vendor/modele` ne le rattrape pas |

Les deux premiers sont fermés par la règle « un `/` désigne une plateforme », placée
**avant** la table. Le troisième par la règle « un provider posé explicitement gagne ».

**Ollama passe par son endpoint compatible `{base_url}/v1`**, plus par l'API propriétaire
`/api/generate`. Ça **supprime** du code spécifique au lieu d'en ajouter : timeout,
tentatives et détection d'erreur deviennent ceux de toutes les autres plateformes.

**Les garde-fous, et pourquoi ils ne sont pas là où on croit.** Les SDK `openai` (2.21.0)
et `anthropic` (0.84.0) retentent **déjà** deux fois avec leur propre backoff — les
envelopper d'une seconde boucle donnerait neuf tentatives réseau et dépasserait la limite
de trente minutes de Celery. Ce qui manquait vraiment, c'est le **timeout** : leur défaut
vaut **600 s en lecture**, soit dix minutes de worker immobilisé, et il y a deux workers à
concurrence 2. Il est posé à 180 s. Seul le SDK de Google — qui ne retente pas, ne pose
aucun timeout, et est **déprécié en amont** — reçoit une boucle de reprise explicite.

### Gratuit n'est pas non mesuré

`cout_par_million_tokens()` rendait `(0.0, 0.0)` pour tout modèle absent de sa table :
« gratuit » et « non mesuré » étaient confondus **au niveau du modèle**. Un identifiant de
plateforme n'est dans aucune table écrite à la main — l'écran de confirmation aurait
annoncé « ≤ 0,00 € » avant un appel facturé, et c'est sur ce chiffre que l'utilisateur
décide. La méthode rend désormais `None`, et les deux écrans affichent **« non mesuré »**.

### Le banc de comparaison des juges

| Fichier / File | Changement / Change |
|---|---|
| `front/management/commands/geler_l_etalon_du_juge.py` | **Nouveau** — gèle les paires jugées, en lecture seule, en excluant celles dont la question a dérivé |
| `benchmarks/juge_de_verification/comparer_un_juge.py` | **Nouveau** — rejoue l'étalon contre un candidat, **sans rien écrire en base** |
| `benchmarks/juge_de_verification/README.md` | pourquoi un étalon gelé, ce que le banc mesure |
| `core/services/verification.py` | `preparer_les_paires_a_juger()` — le parcours déterministe, **sans aucune écriture**, partagé par la vérification et le gel |

Le banc mesure **l'accord, pas la vérité** : ni le juge de référence ni le candidat ne
détiennent la bonne réponse. Un désaccord entre deux juges sur une citation est en
lui-même une information — c'est ce qui rend l'état contestable plutôt qu'asséné.

`preparer_les_paires_a_juger` existe pour que le gel et la vérification posent
**exactement la même question**. Une seconde copie du découpage, même fidèle le jour où on
l'écrit, finirait par comparer deux questions différentes.

---

## Ce que le banc a trouvé le jour même

Le juge a été basculé et le banc lancé. Trois découvertes, toutes mesurées.

### 1. Un verdict de juge n'est PAS reproductible — et ce n'est pas réparable

Le juge de référence a rejoué ses propres 145 paires **cinq fois**. Le nombre de citations
qu'il déclare « vérifiées » : **105, 115, 118, 120, 133**. Soit un taux oscillant entre
**72 % et 92 %** sur des données identiques. Mesure directe de la reproductibilité, à
température 0, trois minutes d'écart : **77 %**.

**Mais l'instabilité dépend du MODÈLE, pas du dispositif.** Une première rédaction de cette
section attribuait la cause au **jeton imprévisible** du prompt — « donc structurelle, donc
irréparable ». La relecture adverse l'a réfutée par la mesure : les juges candidats
atteignent **95 %** de stabilité avec le même jeton, tiré de la même façon. Le jeton interdit
le déterminisme *parfait* ; il n'explique pas l'écart de 18 points. Le juge de référence met
**150 s** là où les candidats en mettent **8** : il réfléchit longuement, et sa réflexion
n'est pas déterministe.

**Ce que cela impose, et qui tient** : un verdict n'est pas une propriété de la citation,
c'est **un acte daté rendu par un juge nommé**. `SPEC-synthese § 7.2` l'exigeait déjà ; cette
mesure lui donne sa raison la plus forte. **Relancer la vérification change le résultat** —
beaucoup avec un juge qui réfléchit, un peu avec un juge stable, jamais rien.

### 2. `AIModel.temperature` était déclaré et n'était passé à AUCUN appel

Tous les modèles tournaient à la température par défaut de leur fournisseur. Le champ est
désormais transmis sur les quatre chemins (compatible, Google, Anthropic, Ollama).
**Changement de comportement à connaître** : les appels prennent maintenant la valeur du
champ (défaut `0.7`) au lieu de celle du fournisseur (1,0 chez Gemini) — y compris pour la
rédaction d'articles.

### 3. Le référentiel des modèles avait pris du retard sur le catalogue servi

`gemini-2.5-flash-lite`, que le référentiel proposait au clic, répond **404 — « no longer
available to new users, use models/gemini-3.5-flash-lite »**. Trois modèles de la
génération 3.x ont été ajoutés avec leurs tarifs datés, et un test verrouille désormais que
**tout choix du référentiel a un tarif** — sinon on propose un modèle dont on ne sait pas
dire le prix avant de lancer. Au passage, le tarif de `gemini-2.5-flash-lite` avait
**augmenté** depuis le relevé de mars sous un chiffre que rien ne surveillait.

**Et le mot « lite » n'annonce plus une économie** : `gemini-3.5-flash-lite` coûte
exactement le prix de `gemini-2.5-flash` (0,30 / 2,50). Le gain annoncé par l'étude de
fournisseurs — « ÷3, zéro ligne de code » — **n'existe plus**.

### 4. La question posée au juge est SOUS-SPÉCIFIÉE — le seuil n'est écrit nulle part

Deux juges qui se reproduisent chacun à 95 % — `gemini-3.1-flash-lite` et
`mistral-small-latest` — ne s'accordent que sur **57 %** des paires. Quand le hasard est
écarté, le désaccord vient de la **question**.

L'unité jugée est un **paragraphe entier** (713 caractères de médiane pour le wiki, 921 pour
la synthèse) portant de **2 à 15 sources**, et jusqu'à **sept assertions distinctes**.
Aucune source ne les porte toutes.

> **Correction du 18 août.** Cette section a d'abord conclu, après lecture rapide de trois
> paires, que « le juge sévère avait raison de refuser ». **C'était faux**, et l'erreur était
> de méthode : j'appliquais sans le dire la lecture *étroite* — une source devrait établir
> *tout* ce que l'affirmation avance —, sous laquelle **les quinze paires échouent**. Les
> quinze paires d'une affirmation ont depuis été jugées une à une, sous une règle **écrite
> avant de juger** : une source soutient si elle établit **au moins une assertion complète**.
> Résultat : le juge sévère se trompe **sept fois sur quinze**, en refusant des sources qui
> reprennent l'affirmation presque mot pour mot. Détail et motifs dans
> `benchmarks/chaine_complete/rapport.html`, § « Étage 3 bis ».

**« Établir » n'est pas défini** : établir *tout* ce que l'affirmation avance, ou *la part
que cette source revendique* ? Le prompt ne le dit pas, et chaque modèle tranche à sa façon.
C'est un trou de spec, et il s'écrit en addendum daté avant de se coder
(`SPEC-synthese § 7.2`). **Cet addendum n'est pas écrit à ce jour.**

> **Une lecture publiée puis retirée, le même jour.** Cette section a d'abord affirmé que le
> nombre de sources **expliquait** l'écart wiki 97 % / synthèse 71 %. Le recomptage la
> réfute : à **2–6 sources**, le wiki est à **100 %** et la synthèse à **70 %** ; la
> corrélation nombre-de-sources / taux vaut **r = −0,25**. L'écart est porté par le
> document, pas par le compte — la lecture d'origine (« la synthèse ratisse large et étire
> ses sources ») est donc rétablie. Détail dans
> `benchmarks/juge_de_verification/2026-08-17_stabilite-des-juges-gemini.md`.

### Le juge retenu

**`gemini-3.1-flash-lite`**, température 0 : **95 % de stabilité** contre 77 %, **17 fois
plus rapide** (8 s contre 150 s pour les mêmes 8 appels), et **−17 % en entrée, −40 % en
sortie**. Son accord avec l'étalon (81 %) tombe *à l'intérieur* du plancher de bruit de la
référence : il ne juge pas autre chose, il juge la même chose de façon bien plus stable.

**Et pas `mistral-small-latest`, pourtant aussi stable (95 %), moins cher et européen** :
parce qu'il **se trompe**. Les quinze paires d'une affirmation, jugées une à une le 18 août
sous une règle écrite d'avance, le placent à **8/15** — contre 13/15 et 14/15 pour les
juges permissifs. Ses sept écarts vont tous dans le sens de la sévérité, et trois portent sur
des sources qui reprennent l'affirmation **presque mot pour mot**.

**Son erreur est cohérente, et c'est ce qui la rend intéressante** : les six sources qu'il
accepte sont des propositions complètes sans matière étrangère ; les sept qu'il refuse sont
des fragments nominaux ou des phrases qui disent quelque chose *en plus*. Il répond donc à
« *cette source est-elle l'énoncé exact de cette affirmation ?* » — un excellent contrôle
d'**attribution** — quand le prompt demande « *cette source établit-elle ce que l'affirmation
avance ?* », un contrôle de **soutien**. À reprendre comme **second** juge, pas comme
remplaçant.

**Ce qui reste vrai** : tant que le seuil n'est pas écrit dans la spécification, chacun le
fixe implicitement — les modèles comme les relecteurs. Je m'y suis laissé prendre le premier.

Détail, matrices et tarifs datés :
`benchmarks/juge_de_verification/2026-08-17_stabilite-des-juges-gemini.md`.

**Neuf exécutions du banc, zéro écriture en base** — l'étalon est ressorti identique
(118 / 27, une seule provenance).

### 5. L'extraction accepte enfin les plateformes compatibles — sans fork

`resolve_model_params` levait pour `COMPATIBLE_OPENAI` : aucun modèle servi par une
plateforme n'était extractible. Le blocage n'était pas là où on le croyait.

**LangExtract choisit son moteur par expression régulière sur le nom du modèle**
(`providers/patterns.py`) : `^mistral`, `^qwen`, `^llama`, `^gemma`, `^phi`, `^deepseek`
partent tous vers `OllamaLanguageModel`, qui parle l'API **propriétaire** d'Ollama. Pointé
sur `api.mistral.ai`, ce moteur échoue — et rien dans le nom du modèle ne le laissait
deviner. C'est le piège symétrique de celui qu'on a fermé dans notre propre table de
préfixes le matin même.

**La parade n'est pas un fork.** `lx.extract` accepte un `config=ModelConfig(...)` qui
résout le provider par son **nom** et court-circuite la table. C'est une API **publique et
documentée** de la bibliothèque : rien à surcharger, rien à re-vérifier à chaque montée de
version — contrairement au reste de la dette LangExtract.

Mesuré aussitôt, en appel réel : `mistral-small-latest` rend **15 extractions en 19 s** sur
l'extrait de débat qui en donnait 6 à 9 aux modèles Google et OpenAI.

Deux réglages qui comptent, et pourquoi : `use_schema_constraints=False` (ce provider
n'expose aucun schéma structuré ; le laisser actif n'apporte rien et fait émettre un
avertissement **à chaque chunk**), et **pas** de `fence_output` (inerte pour ce provider en
mode JSON — le poser serait du bruit).

> **Le risque résiduel, à connaître** : ce provider pose
> `response_format={'type': 'json_object'}`. Une plateforme qui le **rejette** échoue
> bruyamment — acceptable. Une plateforme qui l'**ignore** et rend du markdown fencé fait
> perdre ses extractions **en silence** (`suppress_parse_errors=True` rend une liste vide,
> et le job finit `completed` avec zéro extraction). À éprouver au premier appel de chaque
> nouvelle plateforme.

### Le fork LangExtract était du CODE MORT — il est retiré

Découvert en instruisant le point précédent : `_creer_annotateur_avec_progression`
(`front/tasks.py`) et son « workaround actif d'auto-wrap des tableaux JSON nus » n'avaient
**aucun appelant** dans tout le dépôt. Leurs propres tests réimplémentent la logique au lieu
de l'appeler. `AGENTS.md` le décrivait comme une « dette technique active » protégeant le
pipeline : il ne protégeait **rien**.

**497 lignes retirées de `front/tasks.py`** (2 143 → 1 646), le 18 août :

| Retiré | Pourquoi |
|---|---|
| `_creer_annotateur_avec_progression` et sa classe `AnnotateurAvecProgression` (364 lignes) | aucun appelant |
| `_recuperer_extractions_json_corrompu` (120 lignes) | n'était appelée que par la précédente |
| `import collections`, `defaultdict`, `Iterable`, `Iterator` + l'en-tête de section | ne servaient qu'à ce bloc — **inspectés un par un**, aucun n'est un import à effet de bord |

`front/tests/test_langextract_overrides.py` reste vert : il définit sa propre copie de la
logique (`pre_traiter_sortie_llm`) et vérifie la documentation, jamais le code retiré.

**Le risque, lui, existe toujours** — une plateforme qui rend `[...]` au lieu de
`{"extractions": [...]}` perd ses extractions en silence, sur tous les chemins. Rien ne le
couvre aujourd'hui, et le point d'injection propre serait
`resolver_params={"format_handler": …}`, pas une sous-classe d'`Annotator`.

### Deux options de plus sur la commande d'affectation

`--choix <valeur du référentiel>` crée et affecte un modèle listé sans passer par un shell
Django — les lignes d'`AIModel` n'étaient créées qu'à l'installation, une par clé d'API.
`--temperature` pose la température : comparer deux juges réglés différemment compare deux
réglages, pas deux modèles, et le réglage doit être rejouable en production.

---

## Ce qui n'a PAS été fait, et pourquoi

- **Le chemin d'extraction n'est plus fermé aux plateformes** — voir la section dédiée
  ci-dessous. Le reste de la dette LangExtract est inchangé. Corollaire toujours vrai :
  `Configuration.ai_model` **reste le modèle d'extraction**, et l'écran de configuration IA
  le pose au clic.
- **Pas de linter de portabilité de schéma JSON.** `response_format` n'apparaît nulle part
  dans le dépôt : ce linter n'aurait aucun consommateur. La seule sortie structurée
  (`proposer_une_maj_de_wiki_task`) est demandée en prose et parsée strictement — ce qui est
  déjà la conclusion à laquelle Atomic est arrivé après deux troncatures silencieuses.
- **Pas de capture des tokens réels ni du coût.** Découverte au passage : les trois champs
  `tokens_input_reels`, `tokens_output_reels` et `cout_reel_euros` (`ExtractionJob`,
  migration `0023`) n'ont **aucun écrivain dans tout le dépôt**, et
  `front/templates/front/includes/extraction_results.html:84` affiche un bloc de coût qui
  ne peut donc jamais apparaître. C'est le chantier suivant : le chemin compatible OpenAI
  rend l'`usage` disponible dans chaque réponse.
- **Pas d'écran d'affectation.** Décision du mainteneur : côté Python uniquement pour
  l'instant. L'écran viendra quand le juge sera choisi — il n'y a rien à dessiner tant
  qu'on ne sait pas quoi y montrer.
- **Pas de rôle `embedder`, et la place lui est pourtant faite.** La demande était de
  « prévoir une place » : c'est la **table** qui est cette place. Ajouter un rôle n'est
  qu'une migration d'**état** sur les choix d'un champ — c'est précisément pourquoi une
  table remplace des champs sur `Configuration`, où chaque usage nouveau aurait coûté une
  migration de schéma. La valeur n'est pas posée aujourd'hui parce qu'un rôle sans
  consommateur est un piège : rien ne le lit, et son repli le ferait pointer vers un
  modèle de **conversation** — un non-sens pour un embedding. Elle s'ajoutera avec pgvector
  (`SPEC-selection-des-preuves`, addendum du 16 août), avec un repli qui ne s'applique pas.
- **MiniCheck n'est pas mesurable ici.** Il n'est pas servi par une plateforme compatible :
  il exige un service d'inférence local (vLLM, Ollama), et sa variante Flan-T5 n'est même
  pas un modèle de chat.

---

## Comment tester (à la main) / Manual test

### Test 1 — rien ne change tant qu'on n'affecte rien

```bash
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --lister
```

Attendu : les deux rôles annoncés en **« repli sur la Configuration »**, avec le modèle de
la configuration. Produire un wiki depuis l'écran carnet : le job porte ce même modèle.

### Test 2 — un juge distinct du rédacteur

```bash
# créer et affecter un juge servi par une plateforme
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role \
    --role juge_de_verification \
    --plateforme https://openrouter.ai/api/v1 \
    --modele-technique mistralai/mistral-small-3.2-24b-instruct \
    --variable-de-cle OPENROUTER_API_KEY

docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --lister
```

Attendu : le juge est « affecté », le rédacteur reste en « repli ». Le modèle créé est
**inactif** — vérifier qu'il n'apparaît PAS dans le sélecteur de l'écran de configuration
IA (bouton IA de la barre d'outils).

Cliquer « Vérifier les citations » sur un article : le panneau de preuve d'un renvoi doit
nommer **le juge affecté**, pas le modèle de la configuration.

Puis revenir en arrière :

```bash
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role \
    --role juge_de_verification --retirer
```

### Test 3 — l'échec du juge se voit

Sans clé valide pour le juge affecté, cliquer « Vérifier les citations ». Attendu :

1. un bandeau d'avertissement sur l'article, qui nomme le motif rapporté ;
2. **aucun verdict modifié** — les états et leurs provenances sont ceux d'avant le clic.

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from collections import Counter
from core.models import SourceLink
print(dict(Counter(SourceLink.objects.values_list('etat_de_verification', flat=True))))"
```

Attendu : `{'verifie': 118, 'faible': 27}` — inchangé.

### Test 4 — l'étalon gelé

```bash
docker exec -w /app hypostasia_web python manage.py geler_l_etalon_du_juge
```

Attendu : « 145 paire(s) gelée(s) », `verifie : 118`, `faible : 27`, et **aucune** ligne de
dérive. Une dérive signalée veut dire qu'un article a été édité ou reproduit depuis son
verdict : c'est un fait à connaître, pas une erreur.

### Test 5 — comparer un juge candidat (FACTURÉ)

```bash
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id_du_modele>
```

Attendu : la matrice d'accord, la liste des désaccords — et **la base inchangée**. Le
vérifier explicitement avec la commande de comptage du test 3.

### Test 6 — Ollama passe par l'endpoint compatible

Sur une machine avec un Ollama local :

```bash
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role \
    --role juge_de_verification --modele <id_d_un_modele_ollama>
```

Vérifier dans les journaux du worker que l'appel vise `{base_url}/v1` et non
`/api/generate` : `make logs S=celery_worker`.
