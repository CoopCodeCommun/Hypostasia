# Le moteur de mise à jour du wiki ne produisait rien / The wiki update engine produced nothing

**Date :** 2026-08-16
**Migration :** Oui — `hypostasis_extractor/0035_prompt_de_synthese_sans_statuts_abolis`
(`docker exec -w /app hypostasia_web python manage.py migrate hypostasis_extractor`)

## Résumé / Summary

**Quoi / What :** sur un article réel, la mise à jour d'un wiki rejetait **6 opérations
sur 6** et l'article ne bougeait jamais. Quatre causes indépendantes, toutes corrigées.
Le prompt système de synthèse enseignait par ailleurs un produit disparu. Et une
installation neuve n'a plus ses deux onglets vides : elle produit un wiki et une
synthèse dirigée par le vrai modèle.
*/ On a real article, a wiki update rejected 6 operations out of 6. Four independent
causes, all fixed; the synthesis system prompt taught an abolished product; a fresh
install now ships a real wiki and a real directed synthesis.*

**Pourquoi / Why :** la couche synthèse était livrée et testée, mais **jamais éprouvée
de bout en bout sur un vrai modèle**. Les 129 tests passaient parce qu'ils fournissaient
des réponses LLM bien formées. Un modèle réel ne se comporte pas comme une fixture.
*/ The layer was delivered and tested, but never exercised end-to-end against a real
model: the tests fed it well-formed answers.*

### Les quatre causes

| # | Ce qui n'allait pas | Où |
|---|---|---|
| 1 | Un titre recopié avec ses dièses (`## Le seuil`) ne correspondait à aucune section : le modèle **obéissait** à la consigne « reprends les titres de l'article », et son obéissance était lue comme une hallucination | `core/services/section_ops.py` — `_cle_de_titre` |
| 2 | Le prompt de mise à jour exposait l'article **brut**, `###` compris, alors que l'applieur ne résout que les `##` — l'addendum n°3 de la spec l'interdisait déjà, il n'était pas implémenté | `front/tasks.py` — `proposer_une_maj_de_wiki_task` |
| 3 | Un article produit pouvait contenir des `###`. Le prompt les interdit **déjà** ; Gemini 2.5 Flash a rendu 1 `##` et 5 `###` quand même. La garde devait être **mécanique** | `front/tasks.py` — `_normaliser_les_niveaux_de_titre` |
| 4 | Le prompt était en forme « par extraction », donc le modèle répondait par extraction : **46 entrées, 46 `no_change`**, aucune intégrable | `front/tasks.py` — la consigne |

### Le prompt système enseignait un produit disparu

Deux dérives indépendantes, dans la même fixture :

- les **six statuts de débat** (`CONSENSUEL`, `DISCUTABLE`, `DISCUTÉ`, `CONTROVERSÉ`,
  `NON PERTINENT`) ont été fusionnés en **deux** le 2 mai 2026 ;
- la synthèse a cessé d'être une **version d'un texte** le 9 août 2026 pour devenir une
  **note du carnet** — or le prompt réclamait « une nouvelle version du document » et un
  « style cohérent avec le texte original », que la synthèse de carnet n'a pas.

Sur un appel réel, le modèle justifiait ses opérations par « avec le statut CONSENSUEL ».
La fixture ne suffisait pas à réparer les installations existantes (le garnissage ne pose
ses pièces que si l'analyseur n'en a aucune) : d'où la migration, qui ne remplace une
pièce **que si elle porte encore la marque de l'ancien texte** — un prompt réécrit à la
main n'est jamais écrasé.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/section_ops.py` | `_cle_de_titre` retire les dièses de tête ; la garde B1 couvre tous les niveaux de titre |
| `front/tasks.py` | `_normaliser_les_niveaux_de_titre` et `_refuser_les_titres_en_collision` ; appel avant indexation ; prompt de MAJ : liste des titres adressables, réparation des `###` hérités **par le chemin d'écriture normal**, consigne par section |
| `front/services/fixtures_analyseurs.py` | les trois pièces du prompt de synthèse réécrites, **et sa description** |
| `hypostasis_extractor/migrations/0035_*.py` | **Nouveau** — propage le prompt aux installations existantes |
| `front/management/commands/produire_les_syntheses_etalons.py` | **Nouveau** — le wiki et la synthèse étalons, idempotents **sur le résultat**, appels facturés |
| `bin/install.sh` | appelle la commande, après l'analyse |
| `core/tests/test_section_ops.py` | +5 tests (titre avec dièses, ancre d'insertion, non-régression du rejet, contrebande `###` et `####`) |
| `front/tests/test_maj_wiki_niveaux_de_titre.py` | **Nouveau** — 12 tests |
| `front/tests/test_prompt_de_synthese_a_jour.py` | **Nouveau** — 4 tests |

### Mesuré en conditions réelles / Measured for real

Gemini 2.5 Flash, carnet « Documents étalons », 99 extractions.

| | Avant | Après |
|---|---|---|
| Titres de l'article | 1 `##` + 5 `###` | **6 `##`, 0 `###`** |
| Opérations proposées | 6 | 1 |
| Opérations **rejetées** | **6 sur 6** | **0** |
| Forme de la réponse | 46 entrées par extraction | 1 opération globale, conforme au schéma |

Production étalon : wiki **54 citations / 48 écartées**, synthèse **82 citations /
18 écartées**, périmètre figé à 5 notes et 99 extractions. Vérification réelle sur un
tirage antérieur : **15 vérifiées / 66 faibles** (wiki), **13 / 72** (synthèse), verdicts
horodatés et signés `verbatim+nli-lot v2 — Gemini 2.5 Flash`.

> **Le `no_change` global est ici la BONNE réponse**, et non un échec : le wiki porte sur
> les open badges, ses 48 écartées parlent d'IA et d'épistémologie. C'est exactement ce
> que le panneau des écartées doit donner à voir.

### Ce que la relecture adverse a rattrapé

Le premier jet de ce correctif introduisait **trois régressions**. Elles sont corrigées ;
elles sont écrites ici parce qu'elles se ressemblent toutes les trois — *une garde qui
répare un symptôme en ouvre un autre ailleurs*.

1. **La réparation des `###` hérités détruisait les verdicts de vérification.** Elle
   sauvait `text_readability` sans réindexer. Or chaque `###` ramené à `##` retire **un
   caractère** : toutes les bornes `SourceLink` en aval se périment, et la réindexation
   suivante ne retrouve plus la paire (extraction, paragraphe) — le verdict disparaît
   **sans signalement**, seules les contestations humaines étant signalées. Le HTML et
   l'empreinte restaient également en désaccord avec le texte. La réparation passe
   désormais par `_ecrire_le_corps_d_un_article`, qui réconcilie les verdicts sur les
   **anciennes** bornes avant d'écrire.
2. **Un `###` de contrebande fabriquait une section non approuvée.** La garde B1 ne
   détectait que les `##` ; depuis que l'écriture promeut les `###`, un contenu
   d'opération contenant un `###` passait, puis devenait une section **après**
   l'acceptation humaine. La garde couvre maintenant tous les niveaux.
3. **L'aplatissement pouvait fabriquer deux sections homonymes.** `## Conclusion` +
   `### Conclusion` donnaient deux `## Conclusion`, et l'applieur les déclare alors
   ambiguës **toutes les deux** — plus jamais atteignables. C'est l'état que la
   relecture F interdisait à l'insertion de créer. Refus bruyant désormais, comme la
   garde « zéro citation ».

Deux constats mineurs traités dans la foulée : la commande de fixtures sautait sur
l'**existence** de la ligne `Wiki` et non sur le **résultat** — une tâche échouée gelait
un article vide pour toujours ; et `DESCRIPTION_DE_L_ANALYSEUR_DE_SYNTHESE`, affichée
dans l'interface, enseignait encore « une nouvelle version du texte » et le « statut de
consensus ».

**Deux de mes propres tests étaient trop indulgents** et passaient alors que le bug était
là : un décalage d'un caractère laisse encore le marqueur dans la tranche, et la perte de
verdict ne survient qu'à la réindexation *suivante*. Ils exigent maintenant le début
exact du paragraphe, et jouent le second temps.

### Ce qui reste ouvert (signalé, non corrigé)

- **Les titres de niveau 1 et les formes sans espace** (`###Sans espace`) restent des
  zones non adressables : `_normaliser_les_niveaux_de_titre` ne prend que `#{3,} +`, et
  python-markdown rend pourtant `###Sans espace` en `<h3>`.
- **La migration 0035 importe `front.services.fixtures_analyseurs`**. Renommer une de ces
  constantes casserait `migrate` sur toute base pas encore à 0035. La pratique Django est
  de figer les textes dans la migration.
- **Le prompt de mise à jour promet des commentaires qu'il ne fournit pas** : les écartées
  y sont montrées « identifiant + citation » seulement, alors que la nouvelle pièce du
  prompt système affirme que les commentaires accompagnent l'extraction.
- **Rien ne verrouille l'appel à `produire_les_syntheses_etalons` dans `bin/install.sh`** :
  la retirer ne casserait aucun test.
- **`appliquer` ne refait pas son contrôle de fraîcheur sous `select_for_update`**, comme
  l'exige la note d'intégration de `section_ops.py`. Pré-existant, hors de ce chantier.

---

## Comment tester (à la main) / Manual test

### Test 1 — le wiki et la synthèse existent après une installation

```bash
make install     # ou, seul : docker exec -w /app hypostasia_web \
                 #   python manage.py produire_les_syntheses_etalons
```

1. Ouvrir `/carnets/1/`, onglet **Wikis** → « Les open badges et la reconnaissance des
   compétences ».
2. Onglet **Synthèses dirigées** → « État des lieux du carnet de démonstration ».
3. Dans chaque article : les renvois `[N]` sont cliquables et ouvrent le panneau de
   preuve avec la citation exacte et le retour à la source.
4. Dérouler « Ce qui n'a pas été repris » et « Couverture de l'analyse ».

**Relancer la commande une seconde fois** : elle doit afficher « déjà produit — sauté »
et ne créer **aucun** job. C'est ce qui garantit qu'un redémarrage ne refacture rien.

### Test 2 — la mise à jour propose quelque chose d'applicable

1. Sur le wiki, connecté avec le droit d'écriture : « Proposer une mise à jour ».
2. Attendre la proposition, puis lire le diff **opération par opération**.
3. Vérifier qu'**aucune** opération n'est rejetée avec « la section … n'existe pas ».
4. Cocher, appliquer : le tour s'incrémente et les écartées diminuent.

> Si le modèle rend un `no_change` global, c'est légitime — vérifier alors que les
> écartées sont bien hors du sujet du wiki.

### Test 3 — un article ne contient plus jamais de `###`

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
import re
from core.models import Page
for p in Page.objects.exclude(type_de_note='note'):
    print(p.pk, p.title[:40], '| ### :', len(re.findall(r'^### ', p.text_readability, re.M)))"
```
Toutes les lignes doivent afficher `### : 0`.

### Test 4 — le prompt système ne parle plus des statuts abolis

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from front.tasks import _prompt_systeme_de_synthese
p = _prompt_systeme_de_synthese()
print([m for m in ('CONSENSUEL','DISCUTABLE','CONTROVERSÉ','nouvelle version','texte original') if m.lower() in p.lower()])"
```
Doit afficher `[]`.

### Suites automatiques

```bash
docker exec -w /app hypostasia_web python manage.py test \
  core.tests.test_section_ops \
  front.tests.test_maj_wiki_niveaux_de_titre \
  front.tests.test_prompt_de_synthese_a_jour \
  front.tests.test_synthese_phase_c front.tests.test_synthese_phase_h \
  front.tests.test_script_d_installation --noinput
```

### Piège à connaître

**Toute modification de `front/tasks.py` exige `make restart S=celery_worker`.** Pendant
cette session, une mise à jour a tourné avec l'ancien code et donné un faux négatif.
