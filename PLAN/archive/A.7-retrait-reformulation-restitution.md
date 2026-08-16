# A.7 — Retrait Reformulation IA + Restitution IA + Restitution manuelle + nettoyage code mort

> **Pour les exécutants agentiques :** SUB-SKILL REQUISE — utiliser `superpowers:subagent-driven-development` (recommandé) ou `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les étapes utilisent la syntaxe checkbox (`- [ ]`).

**Goal :** retirer intégralement les fonctionnalités Reformulation IA, Restitution IA et Restitution manuelle d'Hypostasia (code mort en pratique : 0/134 entités utilisent ces champs en DB, sections invisibles dans l'UI), tout en préservant la Synthèse et le mécanisme de versionning de pages (utilisé par la Synthèse).

**Architecture :** retrait par couches successives (vues → templates → JS → serializers → tâches Celery → fixtures → tests → migrations DB → modèle vestige). On nettoie d'abord tout ce qui touche les champs DB avant de les supprimer, sinon les migrations cassent. On commit après chaque phase pour pouvoir reculer en cas de problème.

**Tech Stack :** Django 6 / DRF (ViewSet explicite) / HTMX / Celery / Channels / PostgreSQL. Skill djc/stack-ccc respectée : ViewSet jamais ModelViewSet, DRF Serializers jamais Forms, HTMX jamais SPA, noms verbeux, commentaires bilingues FR/EN.

---

## Contexte de cartographie (à lire avant de commencer)

### Faits constatés en pré-audit (2026-05-02)

- **DB live** : 134 ExtractedEntity, 0 reformulations, 0 restitutions IA ni manuelles, 0 `restitution_page` non-null
- **Configuration IA** : `ai_active=True`, GPT-4o Mini configuré, 4 analyseurs actifs (analyser, reformuler, restituer, 3 synthétiseurs)
- **UI** : aucun bouton Reformuler / Restituer / Pré-remplir avec IA visible — sidebar droite cachée par défaut, sections IA dans `vue_commentaires.html` jamais déclenchées car les champs DB sont vides
- **Synthèse** : seul mécanisme IA opérationnel, crée Page V2/V3 markdown via `synthetiser_page_task` — **conservé intégralement**

### Périmètre de retrait

| Élément | Localisation | Volume |
|---|---|---|
| Tâches Celery | `front/tasks.py` lignes 697-797 (reformuler) + 801-914 (restituer) | ~220 lignes |
| Actions ViewSet | `front/views.py` 4341-4744 (8 actions reformul/restit IA) + 4746-4820 (creer_restitution) | ~480 lignes |
| Action `fil_discussion` | `front/views.py` 3778-3909 + helper 3911-3934 | ~155 lignes |
| Sections `vue_commentaires` IA | `front/views.py` 4256-4334 (timeout reset reformulations) + sections du template | ~80 lignes vues + ~250 lignes template |
| Templates IA | 6 fichiers `front/templates/front/includes/` | ~520 lignes |
| Template `fil_discussion.html` | idem | ~340 lignes |
| Serializers | `RunReformulationSerializer`, `RunRestitutionSerializer`, `RestitutionDebatSerializer` | ~50 lignes |
| Champs DB ExtractedEntity | 12 champs (5 reformul + 4 restit IA + 3 restit manuelle) | 1 migration consolidée |
| Champ DB ExtractionJob | `est_reformulation` | inclus migration |
| Type analyseurs | `REFORMULER`, `RESTITUER` dans `TypeAnalyseur` | 1 migration AlterField |
| JS | hypostasia.js:304-305 + 1125-1140 (restitution-ancre) | ~20 lignes |
| Fixtures | analyseurs FALC + "rest" dans charger_fixtures_demo.py | ~40 lignes |
| Modèle vestige | `core.Reformulation` (zéro usage hors définition) | ~7 lignes + 1 migration |
| Tests | classes Phase24Integration*, ReformulationLLMTest, et autres dans test_phases.py + test_phase27a partiel | ~400 lignes |

**Volume total estimé :** ~3000 lignes nettes retirées.

### Hors périmètre (à NE PAS toucher)

- Tâche Celery `synthetiser_page_task` (tasks.py:1029) et helper `_construire_prompt_synthese` (tasks.py:917) — c'est la Synthèse, on garde
- Helper `core/llm_providers.py:appeler_llm` — utilisé aussi par la Synthèse
- Type `SYNTHETISER` dans `TypeAnalyseur` + analyseurs synthétiseurs en fixture
- Modèle `Page.parent_page` + champs `version_number` + `version_label` — utilisés par la Synthèse pour créer V2/V3
- Related_name `restitutions` sur `Page.parent_page` — mauvaise dénomination historique mais utilisé par views.py:1373 et tasks.py:1139. **À renommer en `versions_enfants` dans Phase 8 pour cohérence sémantique** (puisqu'aucune "restitution" n'existera plus).
- Bouton "Commenter" inline dans `carte_inline.html` (pure JS local) — fonctionnel et indépendant
- Système de commentaires (`CommentaireExtraction`), statuts de débat, action `changer_statut`

### Convention de commit

L'utilisateur Jonas commit manuellement. Le plan suggère un message de commit par phase, **sans** ligne `Co-Authored-By:`. Ne jamais lancer `git commit` automatiquement.

### Commandes utilitaires

- Vérification Django : `docker exec hypostasia_web uv run python manage.py check`
- Tests : `docker exec hypostasia_web uv run python manage.py test front.tests.test_phases -v 1` (ou cible précise)
- Shell Django : `docker exec hypostasia_web uv run python manage.py shell -c "..."`
- App tourne déjà : runserver:8000 + celery + redis + postgres + nginx + traefik
- URL : https://h.localhost (login `marie` ou autre user fixture)

---

## File Structure

### Fichiers à supprimer intégralement (suppression)

```
front/templates/front/includes/
├── reformulation_en_cours.html              # template polling reformul IA
├── choisir_reformulateur.html               # modal choix analyseur reformul
├── confirmation_reformulation.html          # modal confirmation reformul
├── restitution_ia_en_cours.html             # template polling restitut IA
├── choisir_restituteur.html                 # modal choix analyseur restit
├── confirmation_restitution.html            # modal confirmation restit
└── fil_discussion.html                      # vue détaillée extraction (orpheline)
```

### Fichiers à modifier (nettoyage partiel)

```
front/
├── views.py                  # retire 8 actions IA + creer_restitution + fil_discussion + sections vue_commentaires + import serializers
├── serializers.py            # retire 3 serializers
├── tasks.py                  # retire 2 tâches Celery
├── static/front/js/hypostasia.js     # retire options select + handler restitution-ancre
├── templates/front/base.html         # retire onglet "Tous les commentaires" si on supprime aussi vue_commentaires
├── templates/front/includes/vue_commentaires.html    # retire sections IA + restitution
├── templates/front/includes/extraction_results.html  # retire bouton hover btn-commenter-extraction (qui pointe vers fil_discussion)
├── templates/front/includes/bottom_sheet_extraction.html # retire hx-get fil_discussion
├── management/commands/charger_fixtures_demo.py      # retire fixture FALC + rest
└── tests/
    ├── test_phases.py        # retire ~6 classes Phase24Integration*/Reformulation*
    └── test_phase27a.py      # retire 1 ref reformulation

hypostasis_extractor/
├── models.py                 # retire 12 champs ExtractedEntity + 1 champ ExtractionJob + 2 valeurs TypeAnalyseur
├── services.py               # retire 1 ligne mention reformulation
└── templates/hypostasis_extractor/
    ├── analyseur_editor.html         # retire 2 options reformuler/restituer
    └── includes/
        ├── analyseur_item.html       # retire couleur reformuler
        └── example_card.html         # retire mention "non reformule"

core/
├── models.py                 # retire modèle Reformulation (lignes 358-364)
└── llm_providers.py          # retire mentions reformulation/restitution dans docstrings (cosmétique)
```

### Fichiers à créer (migrations)

```
hypostasis_extractor/migrations/
├── 0028_a7_retrait_reformulation_restitution_fields.py    # AddField inverse : retire 12+1 champs
├── 0029_a7_retrait_types_analyseurs_reformul_restit.py    # AlterField TypeAnalyseur choices
core/migrations/
└── 00XX_a7_retrait_modele_reformulation.py                # DeleteModel Reformulation
```

(Numéros à confirmer en lançant `makemigrations` à chaque étape — Django incrémente.)

---

## Phase 0 — État initial et préparation

### Task 0.1 : Vérifier l'état git propre

**Files :** aucun

- [ ] **Step 1 : vérifier aucun changement non commité**

Run :
```bash
git status
```

Expected : "rien à valider, la copie de travail est propre" — sinon, demander à Jonas avant de continuer.

### Task 0.2 : Snapshot des tests qui passent actuellement

**Files :**
- Aucun (production d'un fichier de log temporaire)

- [ ] **Step 1 : lancer la suite complète et capturer le résultat**

Run :
```bash
docker exec hypostasia_web uv run python manage.py test --keepdb -v 1 2>&1 | tee /tmp/A7_tests_avant.log | tail -30
```

Note dans `/tmp/A7_tests_avant.log` le nombre de tests OK / FAIL / ERROR. **Ce sera la référence anti-régression.**

- [ ] **Step 2 : noter le résultat au début du plan**

Ajouter en haut du présent fichier (à la main) une ligne : `> État initial tests : X OK, Y FAIL, Z ERROR (capture YYYY-MM-DD HH:MM)`. Cela servira pour vérifier qu'on n'introduit pas de régression non liée au retrait.

### Task 0.3 : Vérifier l'absence d'usage runtime

**Files :** aucun

- [ ] **Step 1 : confirmer qu'aucune analyse / reformulation / restitution n'est en cours**

Run :
```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob
print('reformulation_en_cours =', ExtractedEntity.objects.filter(reformulation_en_cours=True).count())
print('restitution_ia_en_cours =', ExtractedEntity.objects.filter(restitution_ia_en_cours=True).count())
print('jobs reformulation =', ExtractionJob.objects.filter(est_reformulation=True).count())
print('jobs status pending =', ExtractionJob.objects.filter(status='pending').count())
print('jobs status processing =', ExtractionJob.objects.filter(status='processing').count())
"
```

Expected : tous à 0. Si l'un est non nul, attendre la fin ou demander à Jonas comment procéder.

---

## Phase 1 — Retrait Reformulation IA

### Task 1.1 : Retirer les 3 actions ViewSet de Reformulation IA

**Files :**
- Modify : `front/views.py:4341-4496` (3 actions : `choisir_reformulateur`, `previsualiser_reformulation`, `reformuler`)

- [ ] **Step 1 : lire la zone exacte à retirer**

Run :
```bash
docker exec hypostasia_web uv run python -c "
with open('/app/front/views.py') as f: lines = f.readlines()
print('=== Début zone (4340-4345) ===')
print(''.join(lines[4339:4344]))
print('=== Fin zone (4493-4498) ===')
print(''.join(lines[4492:4497]))
"
```

Expected : la zone commence à `@action(detail=False, methods=["GET"], url_path="choisir_reformulateur")` et termine juste avant `@action(detail=False, methods=["GET"], url_path="choisir_restituteur")`.

- [ ] **Step 2 : supprimer les lignes 4341-4496 dans `front/views.py`**

Utiliser l'outil Edit avec une `old_string` qui couvre l'intégralité des 3 actions et une `new_string` vide (ou un commentaire de suppression). Le bloc commence par le décorateur de `choisir_reformulateur` et se termine à la dernière ligne de `reformuler` juste avant le décorateur de `choisir_restituteur`.

- [ ] **Step 3 : vérifier que Django se charge sans erreur**

Run :
```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : `System check identified no issues` (peut signaler des warnings de migrations à appliquer — c'est OK, on les fera plus tard).

### Task 1.2 : Retirer les imports inutilisés du serializer Reformulation

**Files :**
- Modify : `front/views.py:39` (import `RunReformulationSerializer`)

- [ ] **Step 1 : retirer l'import `RunReformulationSerializer`**

Localiser ligne 39 :
```python
    RunAnalyseSerializer, RunReformulationSerializer,
```

Remplacer par :
```python
    RunAnalyseSerializer,
```

- [ ] **Step 2 : vérifier qu'aucun autre usage ne subsiste**

Run :
```bash
grep -n "RunReformulationSerializer" /home/jonas/Gits/Hypostasia/front/views.py
```

Expected : aucune sortie (toutes les occurrences ont été retirées avec les actions de Task 1.1).

### Task 1.3 : Retirer la tâche Celery `reformuler_entite_task`

**Files :**
- Modify : `front/tasks.py:697-797`

- [ ] **Step 1 : repérer les bornes de la tâche**

La tâche commence par `@shared_task(bind=True)\ndef reformuler_entite_task(self, entity_id, analyseur_id):` (ligne 696-697) et termine ligne 797 avant `@shared_task(bind=True)\ndef restituer_debat_task(...)`.

- [ ] **Step 2 : supprimer la tâche complète (décorateur + corps)**

Utiliser Edit avec une `old_string` couvrant `@shared_task(bind=True)` ligne 696 jusqu'à la dernière ligne de la tâche ligne 797, remplacé par chaîne vide.

- [ ] **Step 3 : vérifier `manage.py check`**

Run :
```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : pas d'erreur d'import.

### Task 1.4 : Retirer le serializer `RunReformulationSerializer`

**Files :**
- Modify : `front/serializers.py:234-249` (classe et docstring)

- [ ] **Step 1 : repérer le bloc**

```bash
sed -n '232,251p' /home/jonas/Gits/Hypostasia/front/serializers.py
```

- [ ] **Step 2 : supprimer la classe complète**

Edit avec `old_string` couvrant la ligne 234 (`class RunReformulationSerializer(serializers.Serializer):`) jusqu'à la ligne juste avant `class RunRestitutionSerializer`.

- [ ] **Step 3 : vérifier**

Run :
```bash
grep -n "RunReformulationSerializer" /home/jonas/Gits/Hypostasia/front/
```

Expected : aucune occurrence.

### Task 1.5 : Retirer les 3 templates de Reformulation IA

**Files :**
- Delete : `front/templates/front/includes/reformulation_en_cours.html`
- Delete : `front/templates/front/includes/choisir_reformulateur.html`
- Delete : `front/templates/front/includes/confirmation_reformulation.html`

- [ ] **Step 1 : supprimer les 3 fichiers**

Run :
```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/reformulation_en_cours.html /home/jonas/Gits/Hypostasia/front/templates/front/includes/choisir_reformulateur.html /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_reformulation.html
```

- [ ] **Step 2 : vérifier qu'aucun template ne les inclut encore**

Run :
```bash
grep -rln "reformulation_en_cours\|choisir_reformulateur\|confirmation_reformulation" /home/jonas/Gits/Hypostasia/front/templates/ /home/jonas/Gits/Hypostasia/front/views.py
```

Expected : aucune sortie. Si la grep trouve des références dans `vue_commentaires.html` ou `fil_discussion.html`, c'est OK — elles seront nettoyées en Phase 4 et 5.

### Task 1.6 : Retirer la fixture analyseur "FALC"

**Files :**
- Modify : `front/management/commands/charger_fixtures_demo.py:1086-1110` (bloc analyseur FALC)

- [ ] **Step 1 : repérer le bloc FALC**

```bash
sed -n '1085,1112p' /home/jonas/Gits/Hypostasia/front/management/commands/charger_fixtures_demo.py
```

Le bloc commence par `# --- Analyseur FALC (type: reformuler) ---` (ligne 1086) et finit juste avant `# --- Analyseur Synthèse délibérative ---` ou similaire.

- [ ] **Step 2 : supprimer le bloc complet**

Edit avec `old_string` couvrant tout le bloc FALC (commentaires + code + le `self.stdout.write` final).

### Task 1.7 : Commit Phase 1

- [ ] **Step 1 : afficher le diff pour relecture**

Run :
```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggérer le commit (Jonas le lance manuellement)**

Suggestion de message :
```
A.7 phase 1 : retrait Reformulation IA — actions ViewSet, serializer, tâche Celery, templates, fixture FALC.

Retire les 3 actions (choisir_reformulateur, previsualiser_reformulation, reformuler), la tâche Celery reformuler_entite_task, le RunReformulationSerializer, les 3 templates IA et la fixture analyseur FALC. 0/134 entités utilisaient ce flow en DB. Les champs reformulation_* sur ExtractedEntity et est_reformulation sur ExtractionJob restent pour l'instant (retrait DB en Phase 8).
```

**Ne pas exécuter `git commit` — Jonas s'en charge.**

---

## Phase 2 — Retrait Restitution IA

### Task 2.1 : Retirer les 4 actions ViewSet de Restitution IA

**Files :**
- Modify : `front/views.py:4498-4744` (4 actions : `choisir_restituteur`, `previsualiser_restitution`, `generer_restitution`, `restitution_ia_status`)

- [ ] **Step 1 : repérer les bornes**

Le bloc commence par `@action(detail=False, methods=["GET"], url_path="choisir_restituteur")` (ligne 4498) et termine juste avant `@action(detail=False, methods=["POST"], url_path="creer_restitution")` (ligne 4746).

- [ ] **Step 2 : supprimer les 4 actions**

Edit avec `old_string` couvrant lignes 4498-4744, remplacé par chaîne vide.

- [ ] **Step 3 : vérifier `manage.py check`**

Run :
```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : pas d'erreur.

### Task 2.2 : Retirer l'import `RunRestitutionSerializer` dans views.py

**Files :**
- Modify : `front/views.py:39-40`

- [ ] **Step 1 : trouver l'import**

```bash
grep -n "RunRestitutionSerializer" /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : retirer l'import**

Localiser l'import ligne ~39-40 :
```python
    RunRestitutionSerializer, SelectModelSerializer,
```

Le retirer en gardant les autres serializers de la même ligne.

### Task 2.3 : Retirer la tâche Celery `restituer_debat_task`

**Files :**
- Modify : `front/tasks.py:801-914`

- [ ] **Step 1 : repérer les bornes**

Commence par `@shared_task(bind=True)\ndef restituer_debat_task(self, entity_id, analyseur_id):` ligne 800-801, termine ligne 914 avant la fonction `_construire_prompt_synthese` (ligne 917).

- [ ] **Step 2 : supprimer la tâche**

Edit avec `old_string` couvrant lignes 800-914 (incluant le décorateur).

- [ ] **Step 3 : vérifier**

Run :
```bash
grep -n "restituer_debat_task" /home/jonas/Gits/Hypostasia/front/
docker exec hypostasia_web uv run python manage.py check
```

Expected : aucune occurrence + check OK.

### Task 2.4 : Retirer le serializer `RunRestitutionSerializer`

**Files :**
- Modify : `front/serializers.py:251-275` (approximatif — dépend de ce qui reste après Task 1.4)

- [ ] **Step 1 : localiser**

```bash
grep -n "class RunRestitutionSerializer" /home/jonas/Gits/Hypostasia/front/serializers.py
```

- [ ] **Step 2 : supprimer la classe**

Edit avec `old_string` du début de `class RunRestitutionSerializer` jusqu'à la classe suivante.

### Task 2.5 : Retirer les 3 templates de Restitution IA

**Files :**
- Delete : `front/templates/front/includes/restitution_ia_en_cours.html`
- Delete : `front/templates/front/includes/choisir_restituteur.html`
- Delete : `front/templates/front/includes/confirmation_restitution.html`

- [ ] **Step 1 : supprimer**

Run :
```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/restitution_ia_en_cours.html /home/jonas/Gits/Hypostasia/front/templates/front/includes/choisir_restituteur.html /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_restitution.html
```

- [ ] **Step 2 : vérifier les références orphelines (hors fichiers à nettoyer en Phase 4-5)**

Run :
```bash
grep -rln "restitution_ia_en_cours\|choisir_restituteur\|confirmation_restitution" /home/jonas/Gits/Hypostasia/front/templates/ /home/jonas/Gits/Hypostasia/front/views.py
```

Expected : seules `vue_commentaires.html` et `fil_discussion.html` peuvent encore en avoir — sera nettoyé en Phases 4-5.

### Task 2.6 : Retirer la fixture analyseur "rest" (s'il existe en DB ; aucune fixture déclarée mais analyseur créé manuellement)

**Files :**
- Aucun fichier de fixture (analyseur "rest" pk=8 a été créé à la main dans la DB de dev de Jonas)

- [ ] **Step 1 : optionnellement, supprimer l'analyseur "rest" en DB de dev**

Run :
```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import AnalyseurSyntaxique
qs = AnalyseurSyntaxique.objects.filter(type_analyseur='restituer')
print(f'Analyseurs restituer en DB : {qs.count()}')
qs.delete()
print('Supprimes.')
"
```

Note : ce nettoyage est local à la machine de dev de Jonas. La migration Phase 8 (retrait du choix `RESTITUER`) refusera de faire `AlterField` si des analyseurs avec ce type subsistent. Donc cette étape est un prérequis aux migrations.

### Task 2.7 : Commit Phase 2

- [ ] **Step 1 : afficher le diff**

```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggestion de message**

```
A.7 phase 2 : retrait Restitution IA — actions ViewSet, serializer, tâche Celery, templates.

Retire les 4 actions (choisir_restituteur, previsualiser_restitution, generer_restitution, restitution_ia_status), la tâche Celery restituer_debat_task, le RunRestitutionSerializer et les 3 templates IA. La restitution manuelle (creer_restitution) reste en place — sera retirée en Phase 3. Champs restitution_ia_* restent pour l'instant (retrait DB en Phase 8).
```

---

## Phase 3 — Retrait Restitution manuelle

### Task 3.1 : Retirer l'action `creer_restitution`

**Files :**
- Modify : `front/views.py:4746-4820` (action `creer_restitution`)

- [ ] **Step 1 : repérer les bornes**

```bash
sed -n '4744,4825p' /home/jonas/Gits/Hypostasia/front/views.py
```

Commence par `@action(detail=False, methods=["POST"], url_path="creer_restitution")` (ligne 4746) et termine ligne ~4820 avant l'action suivante.

- [ ] **Step 2 : supprimer l'action**

Edit avec `old_string` couvrant l'ensemble.

### Task 3.2 : Retirer le serializer `RestitutionDebatSerializer`

**Files :**
- Modify : `front/serializers.py:465-505` (approximatif)

- [ ] **Step 1 : localiser**

```bash
grep -n "class RestitutionDebatSerializer\|class SynthetiserSerializer" /home/jonas/Gits/Hypostasia/front/serializers.py
```

- [ ] **Step 2 : supprimer la classe complète (incluant les 2 méthodes `validate_*`)**

Edit avec `old_string` du début de `class RestitutionDebatSerializer` jusqu'à la classe suivante.

- [ ] **Step 3 : vérifier**

```bash
grep -n "RestitutionDebatSerializer" /home/jonas/Gits/Hypostasia/front/
```

Expected : aucune occurrence (l'import était dynamique dans `creer_restitution` qu'on a retiré).

### Task 3.3 : Retirer le handler JS `restitution-ancre`

**Files :**
- Modify : `front/static/front/js/hypostasia.js:1125-1140` (approximatif)

- [ ] **Step 1 : localiser**

```bash
grep -n "restitution-ancre\|restitution_ancre\|ancreRestitution" /home/jonas/Gits/Hypostasia/front/static/front/js/hypostasia.js
```

- [ ] **Step 2 : lire le bloc complet**

```bash
sed -n '1120,1150p' /home/jonas/Gits/Hypostasia/front/static/front/js/hypostasia.js
```

- [ ] **Step 3 : supprimer le `document.body.addEventListener('click', ...)` qui gère `.restitution-ancre`**

Edit avec `old_string` couvrant tout le handler (du commentaire FR/EN au `});` final).

### Task 3.4 : Retirer le CSS `.restitution-ancre` si présent

**Files :**
- Modify : `front/static/front/css/hypostasia.css` (si applicable)

- [ ] **Step 1 : vérifier la présence**

```bash
grep -n "restitution-ancre\|restitution_ancre" /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css 2>/dev/null
```

- [ ] **Step 2 : si présent, retirer les règles CSS**

Si la grep trouve des règles, les retirer via Edit. Si rien, passer (probable car la pastille est inline avec classes Tailwind).

### Task 3.5 : Commit Phase 3

- [ ] **Step 1 : afficher le diff**

```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggestion de message**

```
A.7 phase 3 : retrait Restitution manuelle — action creer_restitution, serializer RestitutionDebatSerializer, handler JS pastille violette.

Retire l'action ViewSet creer_restitution (qui créait une Page V2 avec balise inline restitution-ancre), le RestitutionDebatSerializer et le JS qui gérait le clic sur la pastille violette. Champs restitution_page/texte/date sur ExtractedEntity restent pour l'instant (retrait DB en Phase 8).
```

---

## Phase 4 — Retrait `fil_discussion` (devenu orphelin)

### Task 4.1 : Retirer l'action ViewSet `fil_discussion`

**Files :**
- Modify : `front/views.py:3778-3909` (action `fil_discussion` complète + helpers internes)

- [ ] **Step 1 : repérer les bornes**

```bash
sed -n '3776,3912p' /home/jonas/Gits/Hypostasia/front/views.py
```

Commence par `@action(detail=False, methods=["GET"], url_path="fil_discussion")` ligne 3778, termine ligne 3909 avant le helper `_re_rendre_fil_discussion`.

- [ ] **Step 2 : supprimer l'action**

Edit avec `old_string` couvrant lignes 3778-3909.

### Task 4.2 : Retirer le helper `_re_rendre_fil_discussion`

**Files :**
- Modify : `front/views.py:3911-3934` (helper)

- [ ] **Step 1 : repérer**

```bash
grep -n "def _re_rendre_fil_discussion\|html_fil = self._re_rendre_fil_discussion" /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : repérer les 2 sites d'appel à supprimer**

Lignes 3965 et 4011 contiennent `html_fil = self._re_rendre_fil_discussion(request, entite)`. **Ces lignes appellent le helper depuis 2 actions qui restent** (probablement `commenter` et `modifier_commentaire` ou similaires). Il faut :

```bash
sed -n '3960,3975p' /home/jonas/Gits/Hypostasia/front/views.py
sed -n '4006,4020p' /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 3 : analyser les 2 actions appelantes**

Lire le contexte pour comprendre ce que fait chaque action. Il faudra :
- Soit retirer aussi ces 2 actions appelantes (si elles ne servent qu'à rendre fil_discussion)
- Soit remplacer `html_fil = self._re_rendre_fil_discussion(...)` par une réponse 204 No Content (`return HttpResponse(status=204)`) si l'action a un effet de bord (ex: créer un commentaire) qui est utile mais n'a plus besoin de re-rendre fil_discussion.

**Décision à prendre lors de l'exécution** : ne pas trancher dans le plan ; lire le code et décider en fonction. Documenter la décision dans le commit.

- [ ] **Step 4 : retirer le helper `_re_rendre_fil_discussion` lui-même**

Une fois les sites d'appel modifiés, supprimer le helper avec Edit (lignes 3911-3934).

- [ ] **Step 5 : vérifier**

```bash
grep -n "_re_rendre_fil_discussion\|fil_discussion" /home/jonas/Gits/Hypostasia/front/views.py
docker exec hypostasia_web uv run python manage.py check
```

Expected : aucune occurrence dans views.py + check OK.

### Task 4.3 : Supprimer le template `fil_discussion.html`

**Files :**
- Delete : `front/templates/front/includes/fil_discussion.html`

- [ ] **Step 1 : supprimer**

Run :
```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/fil_discussion.html
```

- [ ] **Step 2 : vérifier les inclusions orphelines**

Run :
```bash
grep -rln "fil_discussion" /home/jonas/Gits/Hypostasia/front/templates/ /home/jonas/Gits/Hypostasia/front/views.py
```

Expected : références encore présentes dans `extraction_results.html`, `bottom_sheet_extraction.html`, `vue_commentaires.html` — seront nettoyées en Phase 5.

### Task 4.4 : Commit Phase 4

- [ ] **Step 1 : suggestion de message**

```
A.7 phase 4 : retrait fil_discussion — action ViewSet, helper _re_rendre_fil_discussion, template.

Le template fil_discussion.html n'était jamais ouvert dans l'UI actuelle (la sidebar droite contenant ses points d'entrée est cachée par défaut, et le panneau ouvert via "Analyses" charge extraction_results.html, pas fil_discussion). 0/134 entités avaient un texte_reformule ou texte_restitution_ia, donc même si le template s'était chargé il aurait été vide. Les liens hx-get vers /extractions/fil_discussion/ dans extraction_results.html et bottom_sheet_extraction.html seront retirés en Phase 5.
```

---

## Phase 5 — Nettoyage des templates branchés (vue_commentaires, extraction_results, bottom_sheet)

### Task 5.1 : Nettoyer `vue_commentaires.html` — retirer les sections IA et restitution

**Files :**
- Modify : `front/templates/front/includes/vue_commentaires.html`

- [ ] **Step 1 : lire le template complet**

Lire le fichier avec l'outil Read (limit=400 ou tout le fichier).

- [ ] **Step 2 : identifier les zones à retirer**

Les sections sont :
1. Lignes 25-58 : section "Reformulation en lecture seule" (3 `{% if %}` : `reformulation_en_cours`, `reformulation_erreur`, `texte_reformule`)
2. Lignes 180+ : section "Restitution effectuée" (`{% if entity.restitution_page %}` + bandeau "Débat restitué" + lien vers la version)
3. Le lien `hx-get="/extractions/fil_discussion/?entity_id={{ entite.pk }}"` ligne 15 — **mais on garde la carte cliquable**, juste retirer le hx-get/hx-target/hx-swap pour transformer en simple `<div>` non-cliquable. À discuter : l'objectif UX est-il de rendre la carte non-cliquable ? Peut-être ouvrir une vue alternative ? **Décision** : retirer simplement les attributs HTMX (la carte reste affichée mais ne déclenche plus rien au clic). Si Jonas veut un comportement différent, il le précisera après le test.

- [ ] **Step 3 : retirer les attributs HTMX de la carte (lignes ~14-18)**

Edit : remplacer
```html
        <div class="extraction-card bg-white rounded-lg border p-3 hover:shadow-sm transition-shadow cursor-pointer relative group border-amber-400"
             data-extraction-id="{{ entite.pk }}"
             hx-get="/extractions/fil_discussion/?entity_id={{ entite.pk }}"
             hx-target="#panneau-extractions"
             hx-swap="innerHTML"
             title="Position: {{ entite.start_char }}-{{ entite.end_char }}">
```
par
```html
        <div class="extraction-card bg-white rounded-lg border p-3 hover:shadow-sm transition-shadow relative group border-amber-400"
             data-extraction-id="{{ entite.pk }}"
             title="Position: {{ entite.start_char }}-{{ entite.end_char }}">
```
(retire `cursor-pointer`, `hx-get`, `hx-target`, `hx-swap`).

- [ ] **Step 4 : retirer la section "Reformulation" (lignes 25-58 environ)**

Edit avec `old_string` couvrant le bloc complet du commentaire `{# === 2. Reformulation en lecture seule (pleine largeur) === #}` jusqu'au `{% endif %}` qui ferme la section.

- [ ] **Step 5 : retirer la section "Restitution effectuée" si présente**

Run :
```bash
grep -n "restitution_page\|restitution_texte\|restitution_date\|Debat restitue" /home/jonas/Gits/Hypostasia/front/templates/front/includes/vue_commentaires.html
```

Si trouvé, retirer le bloc `{% if entity.restitution_page %}` jusqu'au `{% endif %}` correspondant.

- [ ] **Step 6 : vérifier qu'aucune référence ne subsiste**

```bash
grep -n "reformul\|restitu" /home/jonas/Gits/Hypostasia/front/templates/front/includes/vue_commentaires.html
```

Expected : aucune occurrence.

- [ ] **Step 7 : tester le rendu**

Run :
```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from django.test import Client
from django.contrib.auth import get_user_model
user = get_user_model().objects.first()
c = Client(HTTP_HOST='h.localhost')
c.force_login(user)
r = c.get('/extractions/vue_commentaires/?page_id=4', HTTP_HX_REQUEST='true')
print(f'STATUS = {r.status_code}, taille = {len(r.content)}')
"
```

Expected : status 200, taille similaire à avant (légèrement réduite).

### Task 5.2 : Nettoyer `extraction_results.html` — retirer le bouton hover btn-commenter-extraction

**Files :**
- Modify : `front/templates/front/includes/extraction_results.html:43-55`

- [ ] **Step 1 : lire la zone**

```bash
sed -n '40,60p' /home/jonas/Gits/Hypostasia/front/templates/front/includes/extraction_results.html
```

- [ ] **Step 2 : retirer le bouton "btn-commenter-extraction" (lignes 45-55)**

Le bouton avec `hx-get="/extractions/fil_discussion/?entity_id={{ entity.pk }}"` est à supprimer. Edit avec `old_string` couvrant le `<button class="btn-commenter-extraction"...` jusqu'au `</button>` correspondant.

- [ ] **Step 3 : vérifier**

```bash
grep -n "btn-commenter-extraction\|fil_discussion" /home/jonas/Gits/Hypostasia/front/templates/front/includes/extraction_results.html
```

Expected : aucune occurrence.

### Task 5.3 : Nettoyer `bottom_sheet_extraction.html`

**Files :**
- Modify : `front/templates/front/includes/bottom_sheet_extraction.html:65-70` (zone hx-get fil_discussion)

- [ ] **Step 1 : repérer**

```bash
grep -n "fil_discussion" /home/jonas/Gits/Hypostasia/front/templates/front/includes/bottom_sheet_extraction.html
```

- [ ] **Step 2 : lire le bloc complet (parent du hx-get)**

```bash
sed -n '60,80p' /home/jonas/Gits/Hypostasia/front/templates/front/includes/bottom_sheet_extraction.html
```

- [ ] **Step 3 : retirer le bloc (probablement un bouton mobile vers fil_discussion)**

Décision : si le bouton est isolé, le retirer. Si la cible HTMX fait partie d'un mécanisme central, retirer juste les attributs HTMX (comme Task 5.1 step 3) sans casser la structure.

- [ ] **Step 4 : vérifier**

```bash
grep -n "fil_discussion" /home/jonas/Gits/Hypostasia/front/templates/
```

Expected : aucune occurrence dans les templates.

### Task 5.4 : Retirer le contexte `analyseurs_reformuler_existent` / `analyseurs_restituer_existent` du ViewSet

**Files :**
- Modify : `front/views.py` — toutes les actions qui passaient ces variables au template

- [ ] **Step 1 : lister tous les sites**

```bash
grep -n "analyseurs_reformuler_existent\|analyseurs_restituer_existent" /home/jonas/Gits/Hypostasia/front/views.py
```

Sites identifiés en pré-audit :
- 3791-3808 (action `fil_discussion` — déjà retiré en Phase 4)
- 3855-3897 (autre site dans une action — vérifier laquelle)
- 3911-3934 (helper `_re_rendre_fil_discussion` — déjà retiré en Phase 4)
- 4264-4334 (action `vue_commentaires` — y compris la logique de timeout reset)

- [ ] **Step 2 : retirer la logique de timeout reset des reformulations bloquées dans `vue_commentaires` (lignes 4264-4308)**

Cette logique était :
```python
delai_max_reformulation = timedelta(minutes=5)
reformulations_bloquees = ExtractedEntity.objects.filter(
    reformulation_en_cours=True,
    reformulation_lancee_a__isnull=False,
    reformulation_lancee_a__lt=timezone.now() - delai_max_reformulation,
)
if reformulations_bloquees.exists():
    nb_reset = reformulations_bloquees.update(
        reformulation_en_cours=False,
        reformulation_erreur="Timeout : ...",
    )
```

À retirer entièrement (les champs vont disparaître en Phase 8 + plus aucune tâche ne les remplit).

- [ ] **Step 3 : retirer les query `analyseurs_reformuler_existent` / `analyseurs_restituer_existent`**

Pour chaque site identifié, retirer les lignes :
```python
analyseurs_reformuler_existent = AnalyseurSyntaxique.objects.filter(
    is_active=True, type_analyseur="reformuler",
).exists()
analyseurs_restituer_existent = AnalyseurSyntaxique.objects.filter(
    is_active=True, type_analyseur="restituer",
).exists()
```

ET retirer leur passage au contexte du template (les clés `"analyseurs_reformuler_existent"` et `"analyseurs_restituer_existent"`).

- [ ] **Step 4 : vérifier**

```bash
grep -n "analyseurs_reformuler_existent\|analyseurs_restituer_existent\|reformulation_en_cours\|reformulation_lancee_a" /home/jonas/Gits/Hypostasia/front/views.py
```

Expected : aucune occurrence.

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : check OK.

### Task 5.5 : Retirer les options select `reformuler` / `restituer` dans hypostasia.js

**Files :**
- Modify : `front/static/front/js/hypostasia.js:303-306`

- [ ] **Step 1 : lire la zone**

```bash
sed -n '300,310p' /home/jonas/Gits/Hypostasia/front/static/front/js/hypostasia.js
```

- [ ] **Step 2 : retirer les 2 lignes**

Edit : retirer les lignes :
```javascript
        + '  <option value="reformuler">Reformuler</option>'
        + '  <option value="restituer">Restituer</option>'
```

### Task 5.6 : Retirer le `data-onglet="commentaires"` de l'onglet "Tous les commentaires" — décision

**Files :**
- Modify : `front/templates/front/base.html:310-311`
- Modify : `front/static/front/js/hypostasia.js:40-44`

**Question de scope** : on garde ou on supprime l'onglet "Tous les commentaires" ?

Arguments **garder** : utile pour voir tous les commentaires d'une page sur une seule vue.
Arguments **supprimer** : l'onglet n'est jamais accessible visuellement (sidebar droite cachée), Jonas ne le voit pas, c'est du code mort en pratique.

- [ ] **Step 1 : trancher (Jonas décide à l'exécution)**

**Recommandation** : **garder** `vue_commentaires` action ViewSet + template (sans les sections IA déjà retirées en Task 5.1) — il pourra resurfacer dans la session future qui unifie les vues. Aucun coût supplémentaire à le garder maintenant que le template est nettoyé.

- [ ] **Step 2 : si garder, sauter cette task**

- [ ] **Step 3 : si supprimer**, retirer :
   - `front/templates/front/base.html` lignes 310-311 (le bouton onglet)
   - `front/static/front/js/hypostasia.js` lignes 40-44 (le `else if (ongletChoisi === 'commentaires')`)
   - L'action `vue_commentaires` dans `front/views.py:4246-4334`
   - Le template `front/templates/front/includes/vue_commentaires.html`

### Task 5.7 : Commit Phase 5

- [ ] **Step 1 : afficher le diff**

```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggestion de message**

```
A.7 phase 5 : nettoyage templates branchés — vue_commentaires, extraction_results, bottom_sheet, hypostasia.js.

Retire les sections IA et restitution dans vue_commentaires.html (zones désormais inaccessibles). Retire le bouton hover btn-commenter-extraction qui pointait vers fil_discussion (action retirée en Phase 4). Retire les options select reformuler/restituer dans hypostasia.js. Retire le contexte analyseurs_reformuler_existent / analyseurs_restituer_existent et la logique de timeout reset des reformulations bloquées dans vue_commentaires.
```

---

## Phase 6 — Retrait des types d'analyseurs `REFORMULER` et `RESTITUER`

### Task 6.1 : Confirmer aucun analyseur ne porte ces types

**Files :** aucun

- [ ] **Step 1 : compter**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import AnalyseurSyntaxique
print('reformuler:', AnalyseurSyntaxique.objects.filter(type_analyseur='reformuler').count())
print('restituer:', AnalyseurSyntaxique.objects.filter(type_analyseur='restituer').count())
"
```

Expected : 0 et 0. Si non zero, la Task 1.6 (suppression FALC) ou 2.6 (suppression "rest") n'a pas été faite — y revenir.

### Task 6.2 : Modifier la classe `TypeAnalyseur` dans le modèle

**Files :**
- Modify : `hypostasis_extractor/models.py:354-358`

- [ ] **Step 1 : retirer les 2 valeurs**

Edit le bloc :
```python
class TypeAnalyseur(models.TextChoices):
    ANALYSER = "analyser", "Analyser"
    REFORMULER = "reformuler", "Reformuler"
    RESTITUER = "restituer", "Restituer"
    SYNTHETISER = "synthetiser", "Synthétiser"
```

en :
```python
class TypeAnalyseur(models.TextChoices):
    ANALYSER = "analyser", "Analyser"
    SYNTHETISER = "synthetiser", "Synthétiser"
```

- [ ] **Step 2 : mettre à jour le `help_text` du champ `type_analyseur`**

Trouver à la ligne ~370 :
```python
help_text="Type d'analyseur : analyser, reformuler ou restituer",
```

Remplacer par :
```python
help_text="Type d'analyseur : analyser ou synthetiser / Analyzer type: analyser or synthetiser",
```

### Task 6.3 : Mettre à jour les templates de l'éditeur d'analyseur

**Files :**
- Modify : `hypostasis_extractor/templates/hypostasis_extractor/analyseur_editor.html:60-63`
- Modify : `hypostasis_extractor/templates/hypostasis_extractor/includes/analyseur_item.html:14`

- [ ] **Step 1 : analyseur_editor.html — retirer 2 options**

Edit ligne 61-62 :
```html
<option value="reformuler" {% if analyseur.type_analyseur == "reformuler" %}selected{% endif %}>Reformuler</option>
<option value="restituer" {% if analyseur.type_analyseur == "restituer" %}selected{% endif %}>Restituer</option>
```

→ supprimer les 2 lignes.

- [ ] **Step 2 : analyseur_item.html — retirer la couleur `bg-amber-400` pour reformuler**

Edit ligne 14 — retirer le `{% elif analyseur.type_analyseur == 'reformuler' %}bg-amber-400`. Lire le contexte complet (lignes 10-20) pour ne pas casser la structure if/elif.

- [ ] **Step 3 : vérifier autres templates**

```bash
grep -rn "type_analyseur.*reformuler\|type_analyseur.*restituer\|REFORMULER\|RESTITUER\|'reformuler'\|'restituer'" /home/jonas/Gits/Hypostasia/hypostasis_extractor/templates/ /home/jonas/Gits/Hypostasia/front/templates/
```

Expected : aucune occurrence (modale_prompt_readonly.html peut en avoir — voir Task 6.4).

### Task 6.4 : Nettoyer `modale_prompt_readonly.html` si présent

**Files :**
- Modify : `front/templates/front/includes/modale_prompt_readonly.html` (si présent)

- [ ] **Step 1 : vérifier**

```bash
grep -n "reformuler\|restituer" /home/jonas/Gits/Hypostasia/front/templates/front/includes/modale_prompt_readonly.html
```

- [ ] **Step 2 : si trouvé (lignes 15 + 17), retirer les `{% elif %}` correspondants**

Edit pour retirer les branches `{% elif analyseur.type_analyseur == 'reformuler' %}` et `{% elif analyseur.type_analyseur == 'restituer' %}` en gardant les autres branches intactes.

### Task 6.5 : Nettoyer `hypostasis_extractor/services.py`

**Files :**
- Modify : `hypostasis_extractor/services.py:103`

- [ ] **Step 1 : ligne à retirer ou modifier**

```bash
sed -n '100,108p' /home/jonas/Gits/Hypostasia/hypostasis_extractor/services.py
```

- [ ] **Step 2 : retirer la mention `"Anthropic est disponible pour la reformulation et la restitution."`**

Edit : retirer cette ligne ou la remplacer par une mention neutre (ex : `"Anthropic est disponible pour la synthese."`).

### Task 6.6 : Nettoyer `core/llm_providers.py` (cosmétique docstrings)

**Files :**
- Modify : `core/llm_providers.py:2-4` + `:49-50`

- [ ] **Step 1 : moduler la docstring du module**

Edit ligne 2-4 :
```python
"""
Couche d'abstraction unique pour les appels LLM directs (reformulation, restitution).
/ Unified abstraction layer for direct LLM calls (reformulation, restitution).
"""
```
→
```python
"""
Couche d'abstraction unique pour les appels LLM directs (synthese).
/ Unified abstraction layer for direct LLM calls (synthesis).
"""
```

- [ ] **Step 2 : retirer la mention dans la docstring de `appeler_llm`**

Edit ligne 49-50 :
```python
Appelants : front/tasks.py (reformuler_entite_task, restituer_debat_task)
/ Callers: front/tasks.py (reformuler_entite_task, restituer_debat_task)
```
→
```python
Appelants : front/tasks.py (synthetiser_page_task)
/ Callers: front/tasks.py (synthetiser_page_task)
```

### Task 6.7 : Nettoyer `example_card.html` (cosmétique)

**Files :**
- Modify : `hypostasis_extractor/templates/hypostasis_extractor/includes/example_card.html:97`

- [ ] **Step 1 : modifier la mention "non reformule"**

Edit ligne 97 :
```html
<p><span class="...">texte</span> → texte extrait (non reformule)</p>
```
→
```html
<p><span class="...">texte</span> → texte extrait</p>
```

### Task 6.8 : Commit Phase 6

- [ ] **Step 1 : suggestion de message**

```
A.7 phase 6 : retrait types d'analyseurs REFORMULER et RESTITUER.

Le TypeAnalyseur enum passe de 4 valeurs à 2 (ANALYSER, SYNTHETISER). Mise à jour des templates analyseur_editor, analyseur_item, modale_prompt_readonly. Nettoyage cosmétique des docstrings core/llm_providers.py et hypostasis_extractor/services.py. La migration AlterField sera générée en Phase 8.
```

---

## Phase 7 — Retrait du modèle vestige `core.Reformulation`

### Task 7.1 : Confirmer l'absence d'usage

**Files :** aucun

- [ ] **Step 1 : grep imports**

```bash
grep -rn "from core.models import.*Reformulation\b\|core\.Reformulation\b" /home/jonas/Gits/Hypostasia --include="*.py" --include="*.html" 2>/dev/null | grep -v ".venv\|migrations\|__pycache__\|class Reformulation"
```

Expected : aucune occurrence.

- [ ] **Step 2 : compter les lignes en DB (par sécurité)**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from core.models import Reformulation
print('Reformulation rows:', Reformulation.objects.count())
"
```

Expected : 0. Si non-zero, Jonas devra trancher (probablement TRUNCATE manuel).

### Task 7.2 : Supprimer le modèle `core.Reformulation`

**Files :**
- Modify : `core/models.py:358-364`

- [ ] **Step 1 : supprimer la classe**

Edit lignes 358-364 :
```python
class Reformulation(models.Model):
    origin = models.ForeignKey(
        TextBlock, on_delete=models.CASCADE, related_name="reformulations"
    )
    text = models.TextField()
    style = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
```
→ supprimer entièrement.

- [ ] **Step 2 : vérifier**

```bash
grep -n "class Reformulation\|Reformulation" /home/jonas/Gits/Hypostasia/core/models.py
docker exec hypostasia_web uv run python manage.py check
```

Expected : aucune occurrence + check OK.

### Task 7.3 : Pas de commit standalone — fusionner avec Phase 8

Le retrait du modèle nécessite une migration. La migration sera créée en Phase 8 avec les autres.

---

## Phase 8 — Migrations DB consolidées

### Task 8.1 : Générer la migration de retrait des champs ExtractedEntity + ExtractionJob

**Files :**
- Create : `hypostasis_extractor/migrations/00XX_a7_retrait_reformulation_restitution_fields.py` (auto)

- [ ] **Step 1 : lancer makemigrations**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations hypostasis_extractor --name a7_retrait_reformulation_restitution_fields
```

Expected : Django génère un fichier de migration qui retire :
- ExtractedEntity : `texte_reformule`, `reformule_par`, `reformulation_en_cours`, `reformulation_lancee_a`, `reformulation_erreur`, `restitution_page`, `restitution_texte`, `restitution_date`, `restitution_ia_en_cours`, `restitution_ia_lancee_a`, `restitution_ia_erreur`, `texte_restitution_ia`
- ExtractionJob : `est_reformulation`

- [ ] **Step 2 : relire la migration générée**

```bash
ls -1t /home/jonas/Gits/Hypostasia/hypostasis_extractor/migrations/*.py | head -1
cat $(ls -1t /home/jonas/Gits/Hypostasia/hypostasis_extractor/migrations/*.py | head -1)
```

Vérifier que la migration contient bien 13 `RemoveField` et n'altère rien d'autre.

- [ ] **Step 3 : appliquer**

```bash
docker exec hypostasia_web uv run python manage.py migrate hypostasis_extractor
```

Expected : `Applying hypostasis_extractor.00XX_a7_retrait_reformulation_restitution_fields... OK`.

### Task 8.2 : Générer la migration AlterField TypeAnalyseur

**Files :**
- Create : `hypostasis_extractor/migrations/00XX_a7_retrait_types_analyseurs_reformul_restit.py` (auto)

- [ ] **Step 1 : lancer makemigrations**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations hypostasis_extractor --name a7_retrait_types_analyseurs_reformul_restit
```

Expected : Django génère une migration `AlterField` sur `AnalyseurSyntaxique.type_analyseur` avec les nouvelles `choices` (2 valeurs).

- [ ] **Step 2 : appliquer**

```bash
docker exec hypostasia_web uv run python manage.py migrate hypostasis_extractor
```

### Task 8.3 : Générer la migration de retrait du modèle `core.Reformulation`

**Files :**
- Create : `core/migrations/00XX_a7_retrait_modele_reformulation.py` (auto)

- [ ] **Step 1 : lancer makemigrations**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations core --name a7_retrait_modele_reformulation
```

Expected : Django génère une migration `DeleteModel` sur `Reformulation`.

- [ ] **Step 2 : appliquer**

```bash
docker exec hypostasia_web uv run python manage.py migrate core
```

### Task 8.4 : Renommer le related_name `restitutions` en `versions_enfants` (cohérence sémantique)

**Files :**
- Modify : `core/models.py:89-90` (Page.parent_page related_name)
- Modify : `front/views.py:1373` (page_droite = page_gauche.restitutions...)
- Modify : `front/tasks.py:1139` (prochain_numero = page_racine.restitutions.count() + 2)
- Create : `core/migrations/00XX_a7_renommer_related_name.py` (auto)

- [ ] **Step 1 : modifier le related_name dans le modèle**

Edit `core/models.py` ligne ~89 :
```python
parent_page = models.ForeignKey(
    "self",
    on_delete=models.CASCADE,
    null=True, blank=True,
    related_name="restitutions",
    help_text="Page originale dont celle-ci est une restitution / Original page this is a restitution of",
)
```
→
```python
parent_page = models.ForeignKey(
    "self",
    on_delete=models.CASCADE,
    null=True, blank=True,
    related_name="versions_enfants",
    help_text="Page parente — celle-ci est une version (synthese) de la parente / Parent page — this is a version (synthesis) of parent",
)
```

- [ ] **Step 2 : mettre à jour les 2 sites d'usage**

Site `front/views.py:1373` :
```python
page_droite = page_gauche.restitutions.order_by("version_number").first()
```
→
```python
page_droite = page_gauche.versions_enfants.order_by("version_number").first()
```

Site `front/tasks.py:1139` :
```python
prochain_numero = page_racine.restitutions.count() + 2
```
→
```python
prochain_numero = page_racine.versions_enfants.count() + 2
```

- [ ] **Step 3 : générer la migration**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations core --name a7_renommer_related_name_versions_enfants
```

Expected : `AlterField` sur `Page.parent_page`. **Note** : un `related_name` change ne nécessite pas réellement de migration de schéma (c'est purement Python), mais Django peut générer une migration vide ou ne rien générer. Si rien n'est généré, c'est OK.

- [ ] **Step 4 : appliquer (si migration générée)**

```bash
docker exec hypostasia_web uv run python manage.py migrate core
```

- [ ] **Step 5 : vérifier**

```bash
grep -rn "\.restitutions\." /home/jonas/Gits/Hypostasia --include="*.py" 2>/dev/null | grep -v ".venv\|__pycache__\|migrations"
```

Expected : aucune occurrence (sauf commentaires).

### Task 8.5 : Vérifier `manage.py check` global

- [ ] **Step 1 : check**

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : `System check identified no issues (0 silenced).`

### Task 8.6 : Commit Phase 7+8

- [ ] **Step 1 : suggestion de message**

```
A.7 phase 7-8 : migrations DB et retrait modèle vestige.

3 migrations consolidées :
1. hypostasis_extractor : retrait 13 champs (12 sur ExtractedEntity, 1 sur ExtractionJob)
2. hypostasis_extractor : AlterField TypeAnalyseur (4 → 2 valeurs)
3. core : DeleteModel Reformulation (vestige zéro usage)

+ renommage related_name Page.parent_page de "restitutions" en "versions_enfants" pour cohérence sémantique (la synthèse aussi crée des versions enfants).
```

---

## Phase 9 — Tests

### Task 9.1 : Identifier les classes de tests à retirer

**Files :** aucun (audit)

- [ ] **Step 1 : lister les classes ciblant les features supprimées**

```bash
grep -nE "class .*ReformulationLLM|class .*Phase24Integration|class .*Reformul.*Test|class .*Restitut.*Test|class .*FilDiscussion.*Test|class .*VueCommentaires.*Test|class .*RestitutionDebat.*Test" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py /home/jonas/Gits/Hypostasia/front/tests/test_phase27a.py /home/jonas/Gits/Hypostasia/front/tests/test_phase28_light.py /home/jonas/Gits/Hypostasia/front/tests/test_phase29_synthese_drawer.py /home/jonas/Gits/Hypostasia/front/tests/test_phase29_normalize.py /home/jonas/Gits/Hypostasia/front/tests/test_phase27b.py 2>/dev/null
```

Expected : liste des classes à retirer. Connue d'avance : `Phase24IntegrationReformulationMockTest` (test_phases.py:5565+).

- [ ] **Step 2 : lister les méthodes de test individuelles à retirer**

```bash
grep -nE "def test_.*reformul|def test_.*restitu|def test_.*fil_discussion" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py /home/jonas/Gits/Hypostasia/front/tests/test_phase27a.py /home/jonas/Gits/Hypostasia/front/tests/test_phase28_light.py /home/jonas/Gits/Hypostasia/front/tests/test_phase29_synthese_drawer.py 2>/dev/null
```

### Task 9.2 : Retirer les classes/méthodes de test mortes

**Files :**
- Modify : `front/tests/test_phases.py` (classes Phase24Integration*Reformulation*, etc.)
- Modify : `front/tests/test_phase27a.py` (refs `justification="Passage reformulé"` ligne 187 — peut-être seulement le label de chaîne, pas une vraie dépendance — à vérifier)

- [ ] **Step 1 : pour chaque classe/méthode identifiée en Task 9.1, supprimer le bloc complet**

Utiliser Edit avec `old_string` couvrant la classe entière (du `class XxxTest(TestCase):` jusqu'à la classe suivante ou la fin du fichier).

- [ ] **Step 2 : vérifier qu'aucune référence `reformul`/`restitu` ne subsiste**

```bash
grep -n "reformul\|restitu" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py /home/jonas/Gits/Hypostasia/front/tests/test_phase27a.py /home/jonas/Gits/Hypostasia/front/tests/test_phase28_light.py /home/jonas/Gits/Hypostasia/front/tests/test_phase29_synthese_drawer.py /home/jonas/Gits/Hypostasia/front/tests/test_phase27b.py /home/jonas/Gits/Hypostasia/front/tests/test_phase29_normalize.py 2>/dev/null
```

Expected : seules quelques refs cosmétiques (chaînes de test) si présentes. Décider au cas par cas.

### Task 9.3 : Lancer la suite de tests complète

- [ ] **Step 1 : exécuter**

```bash
docker exec hypostasia_web uv run python manage.py test --keepdb -v 1 2>&1 | tee /tmp/A7_tests_apres.log | tail -40
```

- [ ] **Step 2 : comparer au snapshot Phase 0**

```bash
diff /tmp/A7_tests_avant.log /tmp/A7_tests_apres.log | head -50
```

Vérifier que :
- **Aucun test qui passait avant ne fail maintenant** (régression interdite)
- Les tests retirés sont absents de la sortie
- Le total `Ran X tests` est inférieur à avant (puisqu'on a retiré des tests)
- Tous les tests restants : `OK`

### Task 9.4 : Commit Phase 9

- [ ] **Step 1 : suggestion de message**

```
A.7 phase 9 : retrait tests dépendant des features supprimées.

Retire les classes Phase24IntegrationReformulationMockTest et autres classes ciblant la reformulation IA, restitution IA, fil_discussion. Snapshot avant : X tests OK. Snapshot après : Y tests OK (Y < X attendu, aucune régression).
```

---

## Phase 10 — Vérification anti-régression UI et finalisation

### Task 10.1 : Vérification serveur OK

- [ ] **Step 1 : check Django**

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : pas d'erreur.

- [ ] **Step 2 : vérifier le runserver tourne toujours**

```bash
docker exec hypostasia_web ps aux | grep -E "runserver|celery" | grep -v grep
```

Expected : runserver et celery worker actifs. Si un est tombé, le redémarrer.

### Task 10.2 : Test manuel UI dans Firefox via /chrome

- [ ] **Step 1 : ouvrir https://h.localhost/lire/4/**

Vérifier visuellement :
- ✅ La page se charge
- ✅ Les blocs de texte s'affichent
- ✅ Les pastilles de marge sont présentes
- ✅ Les cartes inline d'extraction se déplient
- ✅ Le bouton "Commenter" inline (pure JS local) ouvre le formulaire de commentaire
- ✅ Les statuts (Consensuel / Discutable / Controversé / Non pertinent) changent au clic
- ✅ La synthèse se lance toujours (bouton "Synthèse" en haut, choix d'analyseur, toast, dropdown tâches)
- ✅ Les versions V1/V2/V3 (synthèses) sont accessibles dans le sélecteur de versions
- ✅ Aucun bouton Reformuler/Restituer/Pré-remplir IA visible (normal — supprimés)
- ✅ Pas d'erreur JS dans la console développeur
- ✅ Pas d'erreur 500 sur les requêtes HTMX

### Task 10.3 : Test manuel — ouvrir la sidebar "Analyses"

- [ ] **Step 1 : cliquer sur le bouton "Analyses" dans le header**

Vérifier que la sidebar droite s'ouvre.

- [ ] **Step 2 : vérifier le panneau "Extractions"**

- ✅ Liste des extractions affichée
- ✅ Pas de bouton hover "Commenter" (retiré)
- ✅ Boutons "Modifier" et "Supprimer" hover toujours présents

- [ ] **Step 3 : vérifier l'onglet "Tous les commentaires"**

- ✅ Charge `vue_commentaires` sans erreur
- ✅ Affiche les commentaires existants
- ✅ Aucune section "Reformulation" ni "Restitution" visible (retirées)

### Task 10.4 : Test manuel — créer un commentaire

- [ ] **Step 1 : sur une extraction, taper un commentaire et soumettre**

Vérifier qu'il s'enregistre et s'affiche.

### Task 10.5 : Test manuel — lancer une synthèse

- [ ] **Step 1 : cliquer "Synthèse" dans la toolbar**

- [ ] **Step 2 : choisir un analyseur (ex: "Charte")**

- [ ] **Step 3 : confirmer**

- [ ] **Step 4 : observer le toast "Synthèse lancée"**

- [ ] **Step 5 : observer le bouton tâches (A.6) passer en spinner bleu puis vert**

- [ ] **Step 6 : cliquer dans le dropdown tâches → "Voir résultat"**

Expected : ouvre la nouvelle Page V4 (ou Vn+1) markdown.

### Task 10.6 : Mettre à jour le CHANGELOG

**Files :**
- Modify : `CHANGELOG.md` (si existe) ou `PLAN/A.7-retrait-reformulation-restitution.md` (cette page, section "Résumé final")

- [ ] **Step 1 : ajouter une entrée**

```markdown
### Alpha 0.3.X — 2026-MM-DD — Session A.7

Retrait Reformulation IA + Restitution IA + Restitution manuelle (~3000 lignes net retirées).

- Tâches Celery `reformuler_entite_task` + `restituer_debat_task` supprimées
- 8 actions ViewSet IA + action `creer_restitution` + action `fil_discussion` retirées
- 6 templates IA + template `fil_discussion.html` supprimés
- 13 champs DB (ExtractedEntity + ExtractionJob) retirés via migration
- Types d'analyseurs `REFORMULER` et `RESTITUER` retirés (TypeAnalyseur passe à 2 valeurs)
- Modèle vestige `core.Reformulation` supprimé
- Related_name `Page.parent_page` renommé `restitutions` → `versions_enfants`
- 0/134 entités utilisaient ces features en DB ; aucune régression UI

Hors périmètre : Synthèse intégralement conservée. Versionning Page conservé. Système de commentaires + statuts de débat intacts. Carte inline (bouton "Commenter" pure JS) intacte.
```

### Task 10.7 : Mise à jour CLAUDE.md / GUIDELINES.md

**Files :**
- Modify : `/home/jonas/Gits/Hypostasia/CLAUDE.md` (ou GUIDELINES) — section "Surcharges LangExtract" (dette technique)

- [ ] **Step 1 : si la doc référence reformulation/restitution**, retirer ces refs

```bash
grep -n "reformul\|restitu" /home/jonas/Gits/Hypostasia/CLAUDE.md
```

Si trouvé, ouvrir et nettoyer les passages obsolètes.

### Task 10.8 : Commit Phase 10 (final)

- [ ] **Step 1 : afficher le diff total**

```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggestion de message**

```
A.7 phase 10 : finalisation — vérifs anti-régression UI + CHANGELOG.

Test manuel UI complet : page lecture OK, cartes inline + bouton Commenter inline OK, statuts OK, sidebar Analyses + onglets OK, vue_commentaires sans sections IA OK, synthèse + dropdown tâches OK. Aucune régression observée. CHANGELOG mis à jour. Documentation interne (CLAUDE.md / GUIDELINES) nettoyée des refs obsolètes.

Solde Session A.7 : ~3000 lignes net retirées. 0/134 entités impactées (toutes les features supprimées étaient inutilisées en DB). 6 templates supprimés, 7e (fil_discussion) supprimé. 9 actions ViewSet retirées. 2 tâches Celery retirées. 13 champs DB retirés. 1 modèle vestige supprimé.

Cumul cleanup A.1 → A.7 : ~11400 lignes net retirées en 7 sessions.
```

---

## Annexe — Plan B en cas de problème

### Si Task 4.2 trouve des actions appelantes complexes (`_re_rendre_fil_discussion` site d'appel)

**Hypothèse** : les 2 sites d'appel (lignes 3965 et 4011) sont dans des actions `commenter` ou `modifier_commentaire` qui doivent re-rendre le panneau commentaires après une modification. Si fil_discussion est retiré, ces actions doivent renvoyer une réponse alternative.

**Plan B** : 
- Si l'action est appelée par HTMX qui attend du HTML : retourner un partial existant qui rend la liste des commentaires de l'extraction (ex: re-render `vue_commentaires.html` filtré sur cette extraction)
- Si l'action peut se contenter de 204 : retourner `HttpResponse(status=204)` et laisser HTMX rafraîchir via un autre mécanisme (`hx-trigger="commentaire-modifie"` côté client)

**Décision** : à prendre lors de l'exécution. Documenter dans le commit.

### Si une migration échoue

- **Si `RemoveField` échoue** : probablement parce qu'un index ou une contrainte référence le champ. Inspecter l'erreur, créer une migration séparée pour `RemoveIndex`/`RemoveConstraint` avant le `RemoveField`.
- **Si `AlterField` TypeAnalyseur échoue** : il reste des analyseurs avec un type `reformuler` ou `restituer` en DB. Retourner à Task 1.6 / 2.6 pour les supprimer manuellement avant.
- **Si `DeleteModel Reformulation` échoue** : il reste des lignes en DB. Retourner à Task 7.1 step 2 pour les supprimer.

### Rollback complet

Si à mi-chemin Jonas décide d'annuler, tous les commits sont conventionnels et peuvent être `git revert` un par un, dans l'ordre inverse. Aucune perte de donnée car aucune ligne n'utilisait ces champs.

---

## Auto-revue du plan (vérifications à mes propres yeux)

**1. Spec coverage :**
- ✅ Reformulation IA retirée (Phase 1) : tâche, actions, serializer, templates, fixture, champs DB, type analyseur, tests
- ✅ Restitution IA retirée (Phase 2) : tâche, actions, serializer, templates, champs DB, type analyseur
- ✅ Restitution manuelle retirée (Phase 3) : action, serializer, JS pastille, champs DB
- ✅ Code mort fil_discussion retiré (Phase 4)
- ✅ Templates branchés nettoyés (Phase 5)
- ✅ Types analyseurs réduits à 2 (Phase 6)
- ✅ Modèle vestige supprimé (Phase 7)
- ✅ Migrations consolidées (Phase 8)
- ✅ Tests nettoyés (Phase 9)
- ✅ Vérif anti-régression UI + CHANGELOG (Phase 10)

**2. Placeholder scan :** vérifié — aucun "TBD", "TODO", "voir plus tard". Les rares ambiguïtés (Task 4.2 step 3, Task 5.6) sont explicitement marquées "Décision à prendre lors de l'exécution" avec critères de choix.

**3. Type consistency :** noms verbeux respectés tout du long (`analyseur_reformuler`, `texte_reformule`, `restituer_debat_task`). Le helper `appeler_llm` est bien conservé (utilisé par Synthèse). Le related_name est cohérent (Phase 8 Task 8.4 = `versions_enfants`).

---

## Solde net estimé

- **Lignes retirées** : ~3000 (220 tâches Celery + 480 actions IA + 155 fil_discussion + 80 vue_commentaires + 520 templates IA + 340 fil_discussion.html + 50 serializers + 20 JS + 40 fixtures + 7 modèle vestige + 250 sections vue_commentaires + 400 tests + ~200 lignes diverses)
- **Lignes ajoutées** : ~50 (commentaires bilingues mis à jour, help_text ajustés, related_name renommé)
- **Net** : **~-2950 lignes**
- **Cumul cleanup A.1→A.7** : ~11400 lignes net retirées en 7 sessions

---

## Références

- Spec maître : `PLAN/REVUE_YAGNI_2026-05-01.md`
- Plans précédents : A.1 (Explorer), A.2 (Heatmap), A.3 (Mode focus), A.4 (Stripe), A.5 (Bibliothèque analyseurs), A.6 (refonte WebSocket)
- Cartographie pré-plan A.7 : conversation Claude Code 2026-05-02 (audit DB + UI via /chrome confirmant 0 usage)
- Skill djc / stack-ccc : `skills/stack-ccc/SKILL.md`
