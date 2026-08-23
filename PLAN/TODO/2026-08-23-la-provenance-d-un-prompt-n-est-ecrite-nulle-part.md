# La provenance d'un prompt n'est écrite nulle part

**Mesuré le 23 août 2026 sur la base de dev (37 jobs). Rien n'est codé.**
**C'est le préalable de toute mesure : sans lui, aucun banc n'est rattachable à sa cause.**

## Ce que le code fait aujourd'hui

### Le prompt envoyé n'est enregistré sur AUCUN chemin

`ExtractionJob.prompt_description` porte, selon l'appelant, soit le **préambule
système seul**, soit une **étiquette**. Jamais le prompt réellement envoyé.

| Type de job | `prompt_description` | Ce que c'est |
|---|---|---|
| analyse | 4 999 car. | **exactement** `"\n".join(piece.content …)` des 4 pièces de « Hypostasia » |
| synthèse d'une note | 1 239 car. | **exactement** `len(_prompt_systeme_de_synthese())` |
| wiki | 38 car. | `"Production d'article de wiki (phase H)"` |
| synthèse dirigée | 36 car. | `"Synthèse dirigée de carnet (phase H)"` |
| mise à jour | — | `"Proposition d'opérations (phase H)"` |
| vérification | 43 car. | `"Vérification des citations (§ 7), enchaînée"` |
| second avis (4 juges locaux) | 39 car. | `"Avis des 4 juges locaux de vérification"` |

Sur le job 35 (`est_synthese`), le prompt réellement construit par
`_construire_prompt_synthese` fait **75 928 caractères** contre **1 239**
enregistrés — un rapport de **× 61**.

Les deux écritures « vertueuses » viennent de `front/views.py:2735` et `:3190`
(`prompt_snapshot = "\n".join(piece.content …)`). Une huitième convention existe :
`front/views.py:5379` écrit `prompt_complet[:500]`, tronqué, quand `:5327` écrit le
même prompt entier.

### `analyseur_version` est un champ mort

`ExtractionJob.analyseur_version` (FK vers `AnalyseurVersion`, help_text « Version de
l'analyseur au moment de l'extraction ») :

- `grep -rn "analyseur_version=" --include=*.py .` hors tests : **aucun résultat** —
  les quatre occurrences de `views.py` sont des `select_related` ;
- en base : **0 job sur 37** ;
- `AnalyseurVersion.objects.count()` = **0**.

Et il le restera même après correction, tant que trois trous ne sont pas bouchés :
`create` d'un analyseur ne crée **pas de v1** ; `partial_update` ne versionne ni le
type, ni `est_par_defaut`, ni surtout **`inclure_extractions` /
`inclure_texte_original`**, qui décident du contenu envoyé ; et les fixtures
(`front/services/fixtures_analyseurs.py:514-637`) posent les pièces sans version.

### Un tour nocturne ne porte aucune trace

`TourDeWiki.job` existe (FK nullable), mais `mettre_a_jour_un_wiki_la_nuit`
(`front/tasks.py:1874`) appelle `construire_la_proposition_d_operations(wiki,
modele_ia)` **sans job**, puis `appliquer_un_tour_de_wiki(..., job=None)`. En base :
le seul tour existant est un tour du moteur, `fait_par=None`, `job=None`.

## Ce qui est voulu

**Une table dédiée, jamais `ExtractionJob`.** Trois raisons, toutes vérifiées :

1. `ExtractionJob` est exposé publiquement (voir
   `2026-08-23-l-api-des-jobs-est-ouverte-a-tous.md`) : y écrire le prompt assemblé
   ferait fuiter le corpus entier ;
2. le menu des tâches charge **30 `ExtractionJob` complets** sans `.only()` ni
   `.defer()` (`front/views_taches.py:284-286`) ;
3. un tour nocturne n'a pas de job — mais il a un `TourDeWiki`, qui **est** l'objet
   d'histoire du projet.

La table porte : FK nullable vers `ExtractionJob` **et** vers `TourDeWiki`,
`analyseur`, `analyseur_version`, `modele`, **empreinte SHA-256 du prompt assemblé**,
longueur, et la liste des identifiants d'extractions montrés au modèle.

**Deux lots, et seul le premier est bloquant :**

- **la provenance** — analyseur, version, empreinte, longueur, ids montrés :
  **~100 octets**. Elle répond à « quel prompt a écrit ce paragraphe ? » et « le
  prompt a-t-il changé entre deux tours ? », qui sont les deux questions dont
  dépendent tous les bancs ;
- **le texte intégral** — voir `2026-08-23-garder-le-texte-integral-d-un-prompt.md`.

Et, sans quoi la provenance s'écrit `NULL` : **les fixtures doivent créer une v1**,
et `partial_update` doit versionner les deux booléens d'injection.

## Ce qu'il faut mesurer

- **Fixtures étalons à écrire** : un jeu gelé hors base, sur le modèle de
  `benchmarks/juge_de_verification/etalon-du-juge.json` — un carnet, ses notes, ses
  extractions, et les prompts attendus pour chacun des sept chemins. C'est lui qui
  permettra de dire « ce prompt-ci a produit ce texte-là », et de le rejouer.
- **Un test d'empreinte sans appel LLM** : le même carnet, deux assemblages
  successifs, même empreinte. Il n'a besoin d'aucun modèle.
- **Un test LLM réel** (`make test-llm`, tag `llm_reel`, **facturé**, confirmation
  demandée) : une production complète de bout en bout, dont on vérifie que la trace
  écrite correspond au prompt réellement parti.

## Ce qui casse si on ne fait rien

Rien ne casse aujourd'hui, parce qu'il n'existe **qu'un** préambule de rédaction pour
tout le monde : on sait lequel c'était. Le jour où il y en a plusieurs — c'est
l'objet de `2026-08-23-typer-les-analyseurs-par-action.md` — un article devient
inexplicable, et « benchmarker » ne veut plus rien dire.

Le dépôt porte déjà trois champs sans écrivain (`tokens_input_reels`,
`tokens_output_reels`, `cout_reel_euros`). `analyseur_version` est le quatrième. En
ajouter un cinquième sans écrivain serait la même erreur, une fois de plus.

## Coût de mise en œuvre

Un modèle, une migration, les points d'écriture dans les cinq producteurs, la v1 des
fixtures, le versionnage des deux booléens, et les fixtures étalons. Deux à trois
jours, dont la moitié pour l'étalon.
