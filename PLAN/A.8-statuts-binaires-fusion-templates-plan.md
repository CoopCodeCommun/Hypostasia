# A.8 — Statuts binaires + fusion templates carte + commenter dans drawer (plan)

> **Pour les exécutants agentiques :** SUB-SKILL REQUISE — utiliser `superpowers:subagent-driven-development` (recommandé) ou `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les étapes utilisent la syntaxe checkbox (`- [ ]`).

**Goal :** simplifier `ExtractedEntity.statut_debat` de 6 valeurs à 2 (`nouveau` / `commente`) auto-dérivées par signal Django, fusionner les 2 templates de contenu carte (inline + drawer) en un seul partial paramétré, ajouter le bouton commenter dans le drawer, fusionner `non_pertinent` (statut) → `masquee=True` (champ).

**Architecture :** retrait par couches (signal d'abord pour automatiser le statut → migration data + AlterField → retrait action manuelle changer_statut → fusion templates → simplification dashboard + helper consensus → CSS/JS allégés → templates aide). Commits fréquents (1 par phase). Tests TDD pour le signal et la fusion templates.

**Tech Stack :** Django 6 / DRF (ViewSet explicite) / HTMX / PostgreSQL / Tailwind subset. Skill djc/stack-ccc respectée : noms verbeux, commentaires bilingues FR/EN, ViewSet jamais ModelViewSet, DRF Serializers jamais Forms.

**Référence spec :** `PLAN/A.8-statuts-binaires-fusion-templates-spec.md`

---

## Convention pour cette session

- Le mainteneur Jonas commit lui-même manuellement. **Ne jamais lancer `git commit`, `git add`, `git push` ni opération git destructive (checkout --, stash, reset, restore, clean).**
- **Ne jamais lancer `ruff format`** sur des fichiers existants.
- App tourne en Docker : `runserver:8000` + Celery + Redis + PostgreSQL + Nginx + Traefik. URL : https://h.localhost
- Commandes Django : `docker exec hypostasia_web uv run python manage.py <commande>`
- Tests : `docker exec hypostasia_web uv run python manage.py test --keepdb -v 1`
- Login user fixture : `marie` ou autre utilisateur existant
- Skill djc/stack-ccc : ViewSet explicite, DRF Serializers, HTMX, noms verbeux, commentaires FR/EN

---

## File Structure

### Fichiers à créer

```
hypostasis_extractor/
├── signals.py                 # Signal post_save/post_delete sur CommentaireExtraction
└── migrations/
    ├── 00XX_a8_recalcul_statuts_fusion_non_pertinent.py    # data migration RunPython
    └── 00YY_a8_alter_statut_debat_choices.py               # AlterField enum 6→2
```

### Fichiers à modifier

```
hypostasis_extractor/
├── models.py                  # statut_debat enum 6→2, save() simplifié
├── apps.py                    # ready() connecte les signals
└── templates/hypostasis_extractor/includes/
    └── _card_body.html        # paramétré mode="lecture"|"drawer"

front/
├── views.py                   # retire action changer_statut, simplifie _calculer_consensus, retire logique statut manuel dans ajouter_commentaire/masquer/restaurer
├── serializers.py             # retire ChangerStatutSerializer
├── static/front/
│   ├── css/hypostasia.css    # 6 paires variables → 2 paires
│   └── js/marginalia.js      # matrice 6 statuts → 2
└── templates/front/includes/
    ├── carte_inline.html              # retire 4 boutons changer_statut
    ├── drawer_vue_liste.html          # remplace contenu inline par {% include _card_body.html %}
    ├── dashboard_consensus.html       # graphique 6 segments → barre binaire
    ├── confirmation_synthese.html     # adapte affichage consensus
    ├── aide_desktop.html              # simplifie explication 6 statuts
    ├── aide_mobile.html               # idem
    └── onboarding_vide.html           # idem

front/management/commands/
└── charger_fixtures_demo.py   # supprime statut_debat riche dans fixtures

front/tests/
├── test_phase_a8_signal.py    # NOUVEAU : tests signal synchroniser_statut_debat
├── test_phase_a8_fusion_templates.py # NOUVEAU : tests _card_body.html paramétré
└── test_phases.py            # retire ~5-8 tests changer_statut, statuts riches

CHANGELOG.md                  # entrée A.8
```

---

## Phase 0 — Préparation et état initial

### Task 0.1 — Vérifier état git propre

**Files :** aucun

- [ ] **Step 1 : git status**

```bash
git status
```

Expected : `rien à valider, la copie de travail est propre`. Si A.7 n'est pas commité, demander à Jonas avant de continuer.

### Task 0.2 — Snapshot tests pré-A.8

**Files :** aucun

- [ ] **Step 1 : lancer la suite complète**

```bash
docker exec hypostasia_web uv run python manage.py test --keepdb -v 1 2>&1 | tee /tmp/A8_tests_avant.log | tail -10
```

Expected : sortie type `Ran X tests, Y errors`. Noter le nombre de tests OK / FAIL / ERROR. **Référence anti-régression.**

- [ ] **Step 2 : capturer stats DB**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity
from django.db.models import Count
print('=== Stats statut_debat actuelles ===')
qs = ExtractedEntity.objects.values('statut_debat').annotate(n=Count('id')).order_by('-n')
for r in qs:
    print(f'  {r[\"statut_debat\"]:18} : {r[\"n\"]} entites')
"
```

Noter les valeurs (référence pour vérification post-migration).

---

## Phase 1 — Signal Django auto-update du statut

### Task 1.1 — Créer le test du signal (TDD)

**Files :**
- Create : `front/tests/test_phase_a8_signal.py`

- [ ] **Step 1 : écrire les tests qui échouent (signal pas encore créé)**

```python
"""
Tests pour le signal Django de synchronisation automatique du statut de debat.
/ Tests for Django signal that auto-syncs debate status.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from core.models import Page, Dossier
from hypostasis_extractor.models import (
    AnalyseurSyntaxique, CommentaireExtraction, ExtractedEntity, ExtractionJob,
)

User = get_user_model()


class PhaseA8SignalSynchroniseStatutTest(TestCase):
    """Le signal doit maintenir statut_debat synchronise avec l'existence
    de commentaires sur l'entite.
    / Signal must keep statut_debat synced with comment existence."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="signal_test", password="x")
        cls.dossier = Dossier.objects.create(name="Test signal", owner=cls.user)
        cls.page = Page.objects.create(
            dossier=cls.dossier, title="Page test signal",
            url="https://example.com/signal", source_type="web",
            text_readability="Texte test", owner=cls.user,
        )
        cls.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur test signal", type_analyseur="analyser",
        )
        cls.job = ExtractionJob.objects.create(
            page=cls.page, analyseur=cls.analyseur, status="completed",
        )

    def _creer_entite(self):
        return ExtractedEntity.objects.create(
            job=self.job, extraction_class="hypostase",
            extraction_text="Test", start_char=0, end_char=4,
            attributes={}, statut_debat="nouveau",
        )

    def test_creation_commentaire_passe_statut_a_commente(self):
        """A la creation d'un commentaire, statut_debat doit passer a 'commente'."""
        entite = self._creer_entite()
        self.assertEqual(entite.statut_debat, "nouveau")

        CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Premier commentaire",
        )

        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")

    def test_suppression_dernier_commentaire_repasse_a_nouveau(self):
        """A la suppression du dernier commentaire, statut_debat doit repasser a 'nouveau'."""
        entite = self._creer_entite()
        commentaire = CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Seul commentaire",
        )
        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")

        commentaire.delete()

        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "nouveau")

    def test_suppression_avec_commentaires_restants_garde_commente(self):
        """A la suppression d'un commentaire alors qu'il en reste, statut_debat reste 'commente'."""
        entite = self._creer_entite()
        commentaire1 = CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Commentaire 1",
        )
        CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Commentaire 2",
        )
        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")

        commentaire1.delete()

        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")
```

- [ ] **Step 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase_a8_signal --keepdb -v 2
```

Expected : 3 tests FAIL — pas de signal connecté, le statut ne change pas automatiquement (reste à "nouveau" même après création de commentaire).

### Task 1.2 — Créer le module signals.py

**Files :**
- Create : `hypostasis_extractor/signals.py`

- [ ] **Step 1 : écrire le signal**

```python
"""
Signaux pour la synchronisation automatique du statut de debat.
Le statut est auto-derive de l'existence d'au moins un commentaire :
- "nouveau" si zero commentaire
- "commente" si >= 1 commentaire

Utilise update() plutot que save() pour eviter de redeclencher les signaux
post_save d'ExtractedEntity (recursion potentielle, et inutile ici).

/ Signals for automatic debate status synchronization.
Status is auto-derived from comment existence:
- "nouveau" if zero comments
- "commente" if >= 1 comment

Uses update() instead of save() to avoid retriggering ExtractedEntity
post_save signals (potential recursion, unnecessary here).

LOCALISATION : hypostasis_extractor/signals.py
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import CommentaireExtraction, ExtractedEntity


@receiver([post_save, post_delete], sender=CommentaireExtraction)
def synchroniser_statut_debat(sender, instance, **kwargs):
    """
    Met a jour ExtractedEntity.statut_debat selon l'existence de commentaires.
    Declenche apres save (creation/modification) ou delete d'un CommentaireExtraction.
    / Updates ExtractedEntity.statut_debat based on comment existence.
    Triggered after save or delete of a CommentaireExtraction.
    """
    entite_id = instance.entity_id
    if not entite_id:
        return
    a_des_commentaires = CommentaireExtraction.objects.filter(
        entity_id=entite_id,
    ).exists()
    nouveau_statut = "commente" if a_des_commentaires else "nouveau"
    ExtractedEntity.objects.filter(
        pk=entite_id,
    ).exclude(statut_debat=nouveau_statut).update(statut_debat=nouveau_statut)
```

### Task 1.3 — Connecter les signals dans apps.py

**Files :**
- Modify : `hypostasis_extractor/apps.py`

- [ ] **Step 1 : lire le fichier actuel**

```bash
cat /home/jonas/Gits/Hypostasia/hypostasis_extractor/apps.py
```

- [ ] **Step 2 : ajouter la méthode `ready()` qui importe les signals**

Si le fichier ressemble à :
```python
from django.apps import AppConfig

class HypostasisExtractorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hypostasis_extractor"
```

Le compléter en :
```python
from django.apps import AppConfig


class HypostasisExtractorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hypostasis_extractor"

    def ready(self):
        # Import des signals pour les enregistrer / Import signals to register them
        from . import signals  # noqa: F401
```

Si une méthode `ready()` existe déjà, ajouter la ligne d'import à l'intérieur sans rien casser.

### Task 1.4 — Lancer les tests, vérifier qu'ils passent

- [ ] **Step 1 : tester le signal**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase_a8_signal --keepdb -v 2
```

Expected : `Ran 3 tests, OK`.

- [ ] **Step 2 : `manage.py check`**

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : `System check identified no issues (0 silenced)`.

### Task 1.5 — Commit Phase 1

- [ ] **Step 1 : afficher le diff**

```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggérer le message (Jonas commit)**

```
A.8 phase 1 : signal Django auto-update statut_debat depuis commentaires.

Nouveau module hypostasis_extractor/signals.py avec un receiver post_save/post_delete
sur CommentaireExtraction qui met a jour ExtractedEntity.statut_debat via update()
(evite recursion). Connecte dans apps.py:ready(). 3 tests TDD verifient :
- creation commentaire -> commente
- suppression dernier commentaire -> nouveau
- suppression avec commentaires restants -> reste commente
```

---

## Phase 2 — Migration data + AlterField

### Task 2.1 — Modifier l'enum dans models.py

**Files :**
- Modify : `hypostasis_extractor/models.py:190`

- [ ] **Step 1 : lire la zone**

```bash
sed -n '185,225p' /home/jonas/Gits/Hypostasia/hypostasis_extractor/models.py
```

- [ ] **Step 2 : modifier le champ et la classe StatutDebat**

Localiser le bloc actuel et le remplacer. Exemple typique du bloc à remplacer :

Ancien :
```python
class StatutDebat(models.TextChoices):
    NOUVEAU = "nouveau", "Nouveau"
    DISCUTABLE = "discutable", "Discutable"
    DISCUTE = "discute", "Discuté"
    CONSENSUEL = "consensuel", "Consensuel"
    CONTROVERSE = "controverse", "Controversé"
    NON_PERTINENT = "non_pertinent", "Non pertinent"
```

Nouveau :
```python
class StatutDebat(models.TextChoices):
    NOUVEAU = "nouveau", "Nouveau"
    COMMENTE = "commente", "Commenté"
```

Si la classe `StatutDebat` n'existe pas encore en tant que TextChoices et que les choix sont inline (`choices=[("nouveau", "Nouveau"), ...]`), créer la classe et l'utiliser via `choices=StatutDebat.choices`.

Vérifier le `help_text` : le mettre à jour pour refléter la nouvelle réalité :
```python
help_text=(
    "Statut auto-derive de l'existence de commentaires. "
    "Mis a jour par signal Django, jamais set manuellement. "
    "/ Status auto-derived from comment existence. "
    "Updated by Django signal, never set manually."
),
```

### Task 2.2 — Retirer la sync masquee dans save()

**Files :**
- Modify : `hypostasis_extractor/models.py:209-212`

- [ ] **Step 1 : lire la méthode save()**

```bash
sed -n '205,220p' /home/jonas/Gits/Hypostasia/hypostasis_extractor/models.py
```

- [ ] **Step 2 : retirer le bloc qui sync masquee**

Trouver le bloc :
```python
def save(self, *args, **kwargs):
    # Synchronise masquee avec statut_debat : non_pertinent ↔ masquee=True
    # / Sync masquee with statut_debat: non_pertinent ↔ masquee=True
    self.masquee = (self.statut_debat == "non_pertinent")
    super().save(*args, **kwargs)
```

Si c'est tout ce que fait `save()`, retirer la méthode entière (le défaut `Model.save()` suffit).

Si `save()` fait autre chose, retirer uniquement le commentaire et la ligne `self.masquee = ...`, en gardant `super().save(*args, **kwargs)`.

### Task 2.3 — Créer la data migration (recalcul + fusion non_pertinent)

**Files :**
- Create : `hypostasis_extractor/migrations/00XX_a8_recalcul_statuts_fusion_non_pertinent.py`

- [ ] **Step 1 : trouver le numéro de la dernière migration**

```bash
ls -1 /home/jonas/Gits/Hypostasia/hypostasis_extractor/migrations/ | grep -v __init__ | grep -v __pycache__ | sort | tail -5
```

Le prochain numéro = dernier + 1. Exemple : si la dernière est `0028_a7_retrait_reformulation_restitution_fields.py`, le prochain est `0029_a8_recalcul_statuts_fusion_non_pertinent.py`.

- [ ] **Step 2 : créer le fichier**

Avec Write (remplacer `0028` par le bon numéro précédent dans `dependencies`) :

```python
"""
Recalcul des statuts existants et fusion non_pertinent -> masquee=True.

Doit etre execute AVANT le AlterField qui retrecit l'enum, sinon Django
rejette les anciennes valeurs (consensuel, discutable, etc.) au moment
de l'AlterField check.

/ Recalculate existing statuses and fold non_pertinent -> masquee=True.
Must run BEFORE the AlterField that shrinks the enum, otherwise Django
rejects old values when AlterField runs validation.
"""
from django.db import migrations


def recalculer_statuts(apps, schema_editor):
    """
    Etape 1 : non_pertinent -> masquee=True (statut sera ecrase a l'etape 2)
    Etape 2 : recalcul depuis les commentaires
    """
    ExtractedEntity = apps.get_model('hypostasis_extractor', 'ExtractedEntity')
    CommentaireExtraction = apps.get_model('hypostasis_extractor', 'CommentaireExtraction')

    # Etape 1 : non_pertinent -> masquee=True
    nb_non_pertinent = ExtractedEntity.objects.filter(
        statut_debat='non_pertinent',
    ).update(masquee=True)
    if nb_non_pertinent:
        print(f"  -> A.8 : {nb_non_pertinent} entites non_pertinent fusionnees dans masquee=True")

    # Etape 2 : recalcul des statuts depuis les commentaires
    ids_commentees = set(CommentaireExtraction.objects.values_list(
        'entity_id', flat=True,
    ).distinct())

    nb_commente = ExtractedEntity.objects.filter(
        pk__in=ids_commentees,
    ).exclude(statut_debat='commente').update(statut_debat='commente')

    nb_nouveau = ExtractedEntity.objects.exclude(
        pk__in=ids_commentees,
    ).exclude(statut_debat='nouveau').update(statut_debat='nouveau')

    print(f"  -> A.8 : {nb_commente} entites passees a 'commente', "
          f"{nb_nouveau} entites repassees a 'nouveau'")


def restaurer_statuts(apps, schema_editor):
    """
    Reverse no-op : on ne peut pas restaurer les valeurs riches perdues.
    / Reverse no-op: we can't restore lost rich values.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hypostasis_extractor', '0028_a7_retrait_reformulation_restitution_fields'),
    ]

    operations = [
        migrations.RunPython(recalculer_statuts, reverse_code=restaurer_statuts),
    ]
```

⚠️ Adapter le nom du fichier dépendant en Step 1 si la dernière migration A.7 a un autre numéro.

### Task 2.4 — Créer la migration AlterField

**Files :**
- Create : `hypostasis_extractor/migrations/00YY_a8_alter_statut_debat_choices.py`

- [ ] **Step 1 : générer la migration via makemigrations**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations hypostasis_extractor --name a8_alter_statut_debat_choices
```

Expected : Django génère un fichier `00YY_a8_alter_statut_debat_choices.py` qui contient une opération `AlterField` sur `ExtractedEntity.statut_debat` avec les nouvelles `choices` (2 valeurs).

- [ ] **Step 2 : vérifier que la migration n'altère QUE statut_debat**

```bash
ls -1t /home/jonas/Gits/Hypostasia/hypostasis_extractor/migrations/*.py | head -1 | xargs cat
```

Si Django a généré aussi des opérations sur d'autres champs (improbable mais possible), signaler à Jonas avant d'appliquer.

### Task 2.5 — Appliquer les migrations

- [ ] **Step 1 : appliquer dans l'ordre**

```bash
docker exec hypostasia_web uv run python manage.py migrate hypostasis_extractor
```

Expected : 
```
Applying hypostasis_extractor.00XX_a8_recalcul_statuts_fusion_non_pertinent... OK
  -> A.8 : 2 entites non_pertinent fusionnees dans masquee=True
  -> A.8 : 22 entites passees a 'commente', 1 entites repassees a 'nouveau'
Applying hypostasis_extractor.00YY_a8_alter_statut_debat_choices... OK
```

(les nombres exacts dépendent de l'état DB live).

### Task 2.6 — Vérifier l'état DB post-migration

- [ ] **Step 1 : vérifier**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity
from django.db.models import Count
print('=== Stats post-A.8 ===')
qs = ExtractedEntity.objects.values('statut_debat').annotate(n=Count('id')).order_by('-n')
for r in qs:
    print(f'  {r[\"statut_debat\"]:18} : {r[\"n\"]} entites')
print(f'Masquees : {ExtractedEntity.objects.filter(masquee=True).count()}')
print(f'Total : {ExtractedEntity.objects.count()}')
"
```

Expected : seulement `nouveau` et `commente`. Aucune autre valeur. `Masquees` doit avoir augmenté de 2 (les ex-non_pertinent).

- [ ] **Step 2 : `manage.py check`**

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : System check identified no issues.

### Task 2.7 — Commit Phase 2

- [ ] **Step 1 : suggestion de message**

```
A.8 phase 2 : enum StatutDebat 6->2 valeurs + migration data + retrait sync masquee.

models.py : StatutDebat passe a {NOUVEAU, COMMENTE}, save() retire la sync
masquee/non_pertinent. 2 migrations consolidees :
- recalcul_statuts_fusion_non_pertinent : RunPython qui fusionne non_pertinent
  -> masquee=True puis recalcule tous les statuts depuis les commentaires
- alter_statut_debat_choices : AlterField avec les 2 nouvelles valeurs
Stats DB post-migration : N nouveau / M commente / K masquees.
```

---

## Phase 3 — Retrait action changer_statut + 4 boutons + logique manuelle

### Task 3.1 — Retirer l'action changer_statut dans front/views.py

**Files :**
- Modify : `front/views.py:4468-4500` (approximatif)

- [ ] **Step 1 : localiser**

```bash
grep -n "url_path=\"changer_statut\"\|def changer_statut" /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : lire la zone complète**

```bash
sed -n '4465,4505p' /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 3 : repérer la fin de l'action**

L'action commence par `@action(detail=False, methods=["POST"], url_path="changer_statut")` et termine juste avant la prochaine `@action` ou la fin de la classe ViewSet.

- [ ] **Step 4 : supprimer le bloc complet**

Utiliser Edit avec un old_string qui couvre du décorateur jusqu'à la dernière ligne de la fonction.

### Task 3.2 — Retirer l'import ChangerStatutSerializer

**Files :**
- Modify : `front/views.py:29`

- [ ] **Step 1 : localiser**

```bash
grep -n "ChangerStatutSerializer" /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : retirer du multi-line import**

Localiser la ligne 29 :
```python
    ChangerStatutSerializer, ChangerVisibiliteSerializer,
```

La remplacer par :
```python
    ChangerVisibiliteSerializer,
```

### Task 3.3 — Retirer le serializer ChangerStatutSerializer

**Files :**
- Modify : `front/serializers.py:441` (approximatif)

- [ ] **Step 1 : localiser**

```bash
grep -n "class ChangerStatutSerializer" /home/jonas/Gits/Hypostasia/front/serializers.py
```

- [ ] **Step 2 : lire la classe**

```bash
sed -n '438,470p' /home/jonas/Gits/Hypostasia/front/serializers.py
```

- [ ] **Step 3 : supprimer la classe**

Utiliser Edit avec un old_string couvrant `class ChangerStatutSerializer(serializers.Serializer):` jusqu'à la classe suivante.

### Task 3.4 — Retirer la logique statut manuel dans ajouter_commentaire

**Files :**
- Modify : `front/views.py` autour de ligne 213 et 3807-3809

- [ ] **Step 1 : localiser les sites manuels**

```bash
grep -n "if entite.statut_debat\|if entity.statut_debat\|statut_debat = .discute\|statut_debat = \"discute\"" /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : pour chaque site, retirer le bloc**

Le bloc typique :
```python
if entite.statut_debat in ("nouveau", "discutable"):
    entite.statut_debat = "discute"
    entite.save(update_fields=["statut_debat"])
```

À retirer entièrement (le signal s'en charge maintenant).

⚠️ **Attention** : ne pas confondre avec d'autres `entite.save(update_fields=...)` qui sauvegardent d'autres champs. Lire le contexte (~10 lignes avant et après) avant de supprimer.

### Task 3.5 — Retirer la logique statut dans masquer / restaurer

**Files :**
- Modify : `front/views.py:4379` (action `masquer`) + `:4431` (action `restaurer`)

- [ ] **Step 1 : lire l'action masquer**

```bash
sed -n '4377,4425p' /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : retirer la ligne qui set non_pertinent**

Trouver :
```python
entite_a_masquer.statut_debat = "non_pertinent"
entite_a_masquer.save(update_fields=["statut_debat", "masquee"])
```

Remplacer par :
```python
entite_a_masquer.save(update_fields=["masquee"])
```

(retirer la ligne `statut_debat = ...` et retirer `"statut_debat"` de `update_fields`).

- [ ] **Step 3 : idem pour `restaurer` (ligne 4431+)**

Trouver :
```python
entite_a_restaurer.statut_debat = "nouveau"
entite_a_restaurer.save(update_fields=["statut_debat", "masquee"])
```

Remplacer par :
```python
entite_a_restaurer.save(update_fields=["masquee"])
```

### Task 3.6 — Retirer les 4 boutons changer_statut dans carte_inline.html

**Files :**
- Modify : `front/templates/front/includes/carte_inline.html:42-89` (approximatif)

- [ ] **Step 1 : lire la zone**

```bash
sed -n '38,95p' /home/jonas/Gits/Hypostasia/front/templates/front/includes/carte_inline.html
```

- [ ] **Step 2 : repérer les 4 boutons à supprimer**

Les boutons commencent par `{% if est_proprietaire %}` et contiennent les 4 boutons (`Discutable`, `Consensuel`, `Controversé`, `Non pertinent`). Ils se terminent juste avant le bloc du bouton "Masquer" et "Commenter".

- [ ] **Step 3 : supprimer les 4 boutons**

Utiliser Edit avec un old_string qui couvre les 4 boutons. **Garder** les boutons `Masquer` et `Commenter` qui suivent.

⚠️ Vérifier que le `{% if est_proprietaire %}` enveloppant les 4 boutons est aussi à retirer (sinon le fichier reste valide mais avec un bloc vide).

### Task 3.7 — Vérification Phase 3

- [ ] **Step 1 : grep des refs obsolètes**

```bash
grep -rn "changer_statut\|ChangerStatutSerializer\|btn-discutable\|btn-consensuel\|btn-controverse" /home/jonas/Gits/Hypostasia/front/ /home/jonas/Gits/Hypostasia/hypostasis_extractor/ 2>/dev/null | grep -v "migrations\|__pycache__\|tests/test_phase_a8"
```

Expected : 0 occurrence (sauf éventuellement dans les tests à retirer en Phase 8).

- [ ] **Step 2 : `manage.py check`**

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : System check identified no issues.

### Task 3.8 — Commit Phase 3

- [ ] **Step 1 : suggestion**

```
A.8 phase 3 : retrait action changer_statut + 4 boutons + logique manuelle.

views.py : action ViewSet changer_statut retiree, import ChangerStatutSerializer
retire, logique manuelle "if statut in (...) -> set discute" retiree dans
ajouter_commentaire (lignes 213 et 3807-3809), set "non_pertinent" retire de
masquer, set "nouveau" retire de restaurer (champ masquee suffit).
serializers.py : ChangerStatutSerializer supprime.
carte_inline.html : 4 boutons (Discutable, Consensuel, Controverse, Non pertinent)
retires. Reste : "Masquer" + "Commenter".
```

---

## Phase 4 — Fusion templates `_card_body.html` paramétré

### Task 4.1 — Créer les tests TDD pour la fusion

**Files :**
- Create : `front/tests/test_phase_a8_fusion_templates.py`

- [ ] **Step 1 : écrire les tests**

```python
"""
Tests pour la fusion des 2 templates de carte d'extraction en un partial
parametre via mode="lecture"|"drawer".
/ Tests for the fusion of 2 extraction card templates into one partial
parameterized via mode="lecture"|"drawer".
"""
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from core.models import Page, Dossier
from hypostasis_extractor.models import (
    AnalyseurSyntaxique, CommentaireExtraction, ExtractedEntity, ExtractionJob,
)

User = get_user_model()


class PhaseA8FusionTemplatesTest(TestCase):
    """Le partial _card_body.html doit s'adapter au mode "lecture" ou "drawer"."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="fusion_test", password="x")
        cls.dossier = Dossier.objects.create(name="Test fusion", owner=cls.user)
        cls.page = Page.objects.create(
            dossier=cls.dossier, title="Page test fusion",
            url="https://example.com/fusion", source_type="web",
            text_readability="Texte test fusion",
            owner=cls.user,
        )
        cls.analyseur = AnalyseurSyntaxique.objects.create(
            name="A8 Fusion Test", type_analyseur="analyser",
        )
        cls.job = ExtractionJob.objects.create(
            page=cls.page, analyseur=cls.analyseur, status="completed",
        )
        cls.entite = ExtractedEntity.objects.create(
            job=cls.job, extraction_class="hypostase",
            extraction_text="Texte source", start_char=0, end_char=12,
            attributes={"hypostases": "Théorie", "resume": "Mon résumé"},
            statut_debat="commente",
        )
        CommentaireExtraction.objects.create(
            entity=cls.entite, user=cls.user, commentaire="Mon commentaire",
        )

    def _rendre(self, mode):
        return render_to_string(
            "hypostasis_extractor/includes/_card_body.html",
            {
                "entity": self.entite,
                "mode": mode,
                "attr_0": "Théorie",
                "attr_1": "Mon résumé",
                "attr_2": "",
                "attr_3": "",
                "est_proprietaire": True,
            },
        )

    def test_card_body_mode_lecture_pas_de_commentaires_inline(self):
        """En mode=lecture, les commentaires ne doivent PAS etre rendus inline."""
        html = self._rendre(mode="lecture")
        self.assertNotIn("Mon commentaire", html)

    def test_card_body_mode_drawer_affiche_commentaires_inline(self):
        """En mode=drawer, les commentaires doivent etre rendus inline."""
        html = self._rendre(mode="drawer")
        self.assertIn("Mon commentaire", html)

    def test_card_body_les_2_modes_contiennent_btn_commenter(self):
        """Les 2 modes doivent contenir le bouton 'Commenter' et la zone deroulable."""
        for mode in ("lecture", "drawer"):
            html = self._rendre(mode=mode)
            self.assertIn("btn-commenter-extraction", html, f"mode={mode}")
            self.assertIn("zone-commentaire-deroulable", html, f"mode={mode}")

    def test_card_body_mode_drawer_owner_voit_btn_masquer(self):
        """En mode=drawer + owner, le bouton btn-masquer-drawer apparait."""
        html = self._rendre(mode="drawer")
        self.assertIn("btn-masquer-drawer", html)

    def test_card_body_mode_lecture_pas_de_btn_masquer_drawer(self):
        """En mode=lecture, le bouton btn-masquer-drawer ne doit PAS apparaitre."""
        html = self._rendre(mode="lecture")
        self.assertNotIn("btn-masquer-drawer", html)
```

- [ ] **Step 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase_a8_fusion_templates --keepdb -v 2
```

Expected : 5 tests FAIL (le partial n'a pas encore le paramètre `mode` ni les sections conditionnelles).

### Task 4.2 — Étendre `_card_body.html` avec le paramètre mode

**Files :**
- Modify : `hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html`

- [ ] **Step 1 : lire le fichier actuel**

```bash
cat /home/jonas/Gits/Hypostasia/hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html
```

- [ ] **Step 2 : réécrire le fichier**

Remplacer entièrement par (Write) :

```django
{# Corps unique de carte d'extraction — paramétré par mode="lecture"|"drawer" #}
{# Receives : entity, attr_0, attr_1, attr_2, attr_3, mode (default "lecture"), est_proprietaire #}
{# / Single body of extraction card — parameterized by mode="lecture"|"drawer" #}
{# LOCALISATION : hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html #}
{% load extractor_tags %}
{% with mode=mode|default:"lecture" %}

{# === 1. Header : indicateur statut + hypostases + compteur commentaires === #}
{# / === 1. Header: status indicator + hypostases + comments counter === #}
<div class="flex items-center gap-2 mb-2">
    {# Indicateur statut binaire (gris ou vert) — meme dans les 2 modes #}
    {# / Binary status indicator (grey or green) — same in both modes #}
    <span class="indicateur-statut w-3.5 h-3.5 flex-shrink-0 rounded-full"
          data-statut="{{ entity.statut_debat }}"
          style="background-color: var(--statut-{{ entity.statut_debat }}-accent);"
          title="{{ entity.get_statut_debat_display }}"></span>

    {# Badges hypostases colores par famille #}
    {# / Hypostase badges colored by family #}
    {% if attr_0 %}
        <div class="flex flex-wrap gap-0.5 min-w-0 overflow-hidden">
            {% for tag in attr_0|split_comma %}
            <span class="typo-hypostase inline-block px-1.5 py-0.5 rounded-full"
                  style="background: var(--hypostase-{{ tag|hypostase_famille }}-bg); color: var(--hypostase-{{ tag|hypostase_famille }}-text);"
                  title="{{ tag }} — {{ tag|hypostase_definition }}"
                  data-testid="badge-hypostase">{{ tag }}</span>
            {% endfor %}
        </div>
    {% endif %}

    <span class="flex-1"></span>

    {# Compteur commentaires (les 2 modes) #}
    {# / Comments counter (both modes) #}
    {% if entity.nombre_commentaires %}
    <span class="inline-flex items-center gap-1 text-[10px] text-amber-600 flex-shrink-0"
          title="{{ entity.nombre_commentaires }} commentaire{{ entity.nombre_commentaires|pluralize:"s" }}">
        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>
        </svg>
        {{ entity.nombre_commentaires }}
    </span>
    {% endif %}

    {# Bouton masquer (drawer only, owner only, hover) #}
    {# / Hide button (drawer only, owner only, hover) #}
    {% if mode == "drawer" and est_proprietaire %}
    <button class="btn-masquer-drawer opacity-0 group-hover:opacity-100 p-0.5 rounded text-slate-300 hover:text-red-500 transition-all flex-shrink-0"
            data-entity-id="{{ entity.pk }}"
            data-page-id="{{ entity.job.page_id }}"
            {% if entity.nombre_commentaires %}disabled title="Extraction avec commentaires"{% else %}title="Masquer cette extraction"
            hx-post="/extractions/masquer/"
            hx-vals='{"entity_id": "{{ entity.pk }}", "page_id": "{{ entity.job.page_id }}"}'
            hx-swap="none"
            {% endif %}
            data-testid="drawer-btn-masquer">
        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"/>
        </svg>
    </button>
    {% endif %}
</div>

{# === 2. Body : résumé IA (attr_1) + citation source === #}
{# / === 2. Body: AI summary (attr_1) + source citation === #}
{% if attr_1 %}
<p class="typo-machine text-xs leading-relaxed text-slate-600 mb-1">{{ attr_1 }}</p>
{% endif %}

<p class="typo-citation text-xs leading-relaxed text-slate-500 italic">
    [{{ entity.extraction_text|truncatechars:120 }}]
</p>

{# === 3. Mots-clés (attr_3) — les 2 modes === #}
{# / === 3. Keywords (attr_3) — both modes === #}
{% if attr_3 %}
<div class="flex flex-wrap gap-1 mt-1">
    {% for mc in attr_3|split_comma %}
    <span class="text-[9px] text-slate-500 bg-slate-50 px-1 rounded">#{{ mc }}</span>
    {% endfor %}
</div>
{% endif %}

{# === 4. Commentaires affichés inline (drawer only) === #}
{# / === 4. Comments displayed inline (drawer only) === #}
{% if mode == "drawer" %}
    {% for commentaire in entity.commentaires.all %}
    <div class="px-2 py-1 mt-2 bg-slate-50 border-l-2 border-slate-200 rounded
        {% if contributeurs_actifs %}
            {% if mode_filtre == "exclure" %}
                {% if commentaire.user.pk in contributeurs_actifs %}commentaire-hors-filtre{% endif %}
            {% else %}
                {% if commentaire.user.pk not in contributeurs_actifs %}commentaire-hors-filtre{% endif %}
            {% endif %}
        {% endif %}">
        <div class="flex items-start gap-2">
            <span class="typo-lecteur-nom text-xs font-semibold text-slate-700 flex-shrink-0">{{ commentaire.user.first_name|default:commentaire.user.username|title }}</span>
            <p class="text-xs text-slate-700 leading-relaxed">{{ commentaire.commentaire }}</p>
        </div>
    </div>
    {% endfor %}
{% endif %}

{# === 5. Zone formulaire commentaire — masquée par défaut === #}
{# / === 5. Comment form zone — hidden by default === #}
<div class="zone-commentaire-deroulable hidden mt-2"
     data-extraction-id="{{ entity.pk }}">
    <form hx-post="/extractions/ajouter_commentaire/"
          hx-vals='{"entity_id": "{{ entity.pk }}", "page_id": "{{ entity.job.page_id }}"}'
          hx-swap="none"
          class="flex flex-col gap-1">
        <textarea name="commentaire" rows="2"
                  class="w-full text-xs border border-slate-200 rounded p-1.5 resize-none focus:outline-none focus:border-amber-400"
                  placeholder="Votre commentaire..."
                  required></textarea>
        <button type="submit"
                class="self-end text-xs px-2 py-1 bg-amber-50 text-amber-700 rounded hover:bg-amber-100 transition-colors">
            Envoyer
        </button>
    </form>
</div>

{# === 6. Footer : bouton commenter (les 2 modes) === #}
{# / === 6. Footer: comment button (both modes) === #}
<button class="btn-commenter-extraction text-xs text-slate-400 hover:text-amber-600 transition-colors mt-2 flex items-center gap-1"
        data-entity-id="{{ entity.pk }}"
        data-testid="btn-commenter-extraction"
        onclick="this.previousElementSibling.classList.toggle('hidden'); var ta = this.previousElementSibling.querySelector('textarea'); if (ta) ta.focus();"
        title="Commenter">
    <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>
    </svg>
    Commenter
</button>

{% endwith %}
```

### Task 4.3 — Lancer les tests, vérifier qu'ils passent

- [ ] **Step 1 : test du partial**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase_a8_fusion_templates --keepdb -v 2
```

Expected : `Ran 5 tests, OK`.

### Task 4.4 — Adapter drawer_vue_liste.html pour utiliser le partial

**Files :**
- Modify : `front/templates/front/includes/drawer_vue_liste.html` (lignes ~131-235)

- [ ] **Step 1 : lire la zone à remplacer**

```bash
sed -n '125,240p' /home/jonas/Gits/Hypostasia/front/templates/front/includes/drawer_vue_liste.html
```

- [ ] **Step 2 : remplacer le contenu inline par un include**

Localiser le bloc qui commence par :
```django
{% for entity in entites_visibles %}
{% entity_json_attrs entity as entity_attrs %}
<div class="drawer-carte-compacte mb-2 rounded-lg border border-slate-100 ...
```

Remplacer le contenu de cette boucle par :
```django
{% for entity in entites_visibles %}
{% entity_json_attrs entity as entity_attrs %}
<div class="drawer-carte mb-2 rounded-lg border border-slate-100 overflow-hidden cursor-pointer hover:border-slate-200 transition-colors group"
     data-extraction-id="{{ entity.pk }}"
     data-page-id="{{ page.pk }}"
     data-testid="drawer-carte"
     style="border-left: 3px solid var(--statut-{{ entity.statut_debat }}-accent);">
    <div class="px-3 py-2">
        {% with attr_0=entity_attrs.0 attr_1=entity_attrs.1 attr_2=entity_attrs.2 attr_3=entity_attrs.3 %}
            {% include "hypostasis_extractor/includes/_card_body.html" with mode="drawer" %}
        {% endwith %}
    </div>
</div>
{% empty %}
... (laisser le bloc {% empty %} existant inchangé)
{% endfor %}
```

⚠️ Lire attentivement les ~105 lignes que tu remplaces pour t'assurer de :
- Garder les variables `entity_attrs` calculées par `{% entity_json_attrs %}`
- Préserver le `style="border-left: 3px solid var(--statut-{{ entity.statut_debat }}-accent);"` au niveau de la div wrapper
- Préserver la classe `data-testid="drawer-carte"` (utilisée par les tests)
- Garder le bloc `{% empty %}` qui suit (cas "aucune extraction")

### Task 4.5 — Adapter carte_inline.html pour utiliser le partial avec mode="lecture"

**Files :**
- Modify : `front/templates/front/includes/carte_inline.html`

- [ ] **Step 1 : lire le fichier actuel post-Phase 3 (boutons retirés)**

```bash
cat /home/jonas/Gits/Hypostasia/front/templates/front/includes/carte_inline.html
```

- [ ] **Step 2 : vérifier que le fichier inclut déjà `_card_body.html`**

Si oui (ligne `{% include "hypostasis_extractor/includes/_card_body.html" %}` présente), ajouter `with mode="lecture"` :
```django
{% include "hypostasis_extractor/includes/_card_body.html" with mode="lecture" %}
```

- [ ] **Step 3 : retirer le badge statut "CONTROVERSÉ" en haut**

Le bloc :
```django
<div class="flex items-center gap-2 mb-2 pr-6">
    <span class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
          style="color: var(--statut-{{ entity.statut_debat }}-text); background: var(--statut-{{ entity.statut_debat }}-bg);">
        {{ entity.get_statut_debat_display }}
    </span>
    {% if nombre_commentaires %}...{% endif %}
</div>
```
À retirer (le `_card_body.html` s'en charge maintenant via l'indicateur statut + le compteur commentaires).

⚠️ Garder `<button class="btn-replier-carte" ...>` (bouton replier la carte) qui n'est pas dans le partial.

⚠️ Le footer avec "Masquer" et "Commenter" était dans `carte_inline.html` ; il bouge maintenant dans le partial. Donc retirer `<button class="btn-commenter-extraction">` et le `<button class="btn-masquer-...">` (s'il existe) dans `carte_inline.html` puisqu'ils sont dans le partial.

Si après ces retraits il ne reste presque plus rien dans `carte_inline.html` à part le wrapper div + bouton replier + include, c'est attendu.

### Task 4.6 — Vérification visuelle Chrome

- [ ] **Step 1 : reload la page lecture**

Aller sur `https://h.localhost/lire/4/` dans Chrome et vérifier :
- ✅ Cartes inline affichent : indicateur statut (gris ou vert) + hypostase (badge) + résumé IA + citation + bouton "Commenter"
- ✅ Aucun bouton "Discutable" / "Consensuel" / "Controversé" / "Non pertinent"
- ✅ Bouton "Replier" toujours présent

- [ ] **Step 2 : ouvrir le drawer Analyses, vérifier le contenu des cartes**

- ✅ Les cartes du drawer affichent maintenant l'**hypostase** (qui manquait auparavant)
- ✅ Les commentaires apparaissent inline sous la carte
- ✅ Bouton "Commenter" présent en bas de chaque carte du drawer

- [ ] **Step 3 : tester création commentaire depuis le drawer**

- Cliquer sur "Commenter" dans une carte du drawer → la zone formulaire se déplie
- Taper un commentaire → cliquer "Envoyer"
- Vérifier que l'entité passe en statut "commente" (indicateur passe au vert) — peut nécessiter un reload de la page

### Task 4.7 — Commit Phase 4

- [ ] **Step 1 : suggestion**

```
A.8 phase 4 : fusion templates carte inline + drawer en _card_body.html parametré.

_card_body.html (hypostasis_extractor/templates/...) recoit maintenant un parametre
"mode" ("lecture" ou "drawer") qui controle :
- l'affichage des commentaires inline (drawer only)
- l'affichage du bouton masquer hover (drawer only, owner only)
Le partial inclut maintenant : header (indicateur statut + hypostases + compteur),
body (resume + citation), mots-cles, commentaires (drawer only), formulaire commenter
deroulable, bouton commenter.

drawer_vue_liste.html : retire ~105 lignes de contenu duplique, remplace par
{% include "_card_body.html" with mode="drawer" %}.

carte_inline.html : retire le badge statut texte ("CONTROVERSE", etc.) et delegue
au partial.

5 tests TDD verifient :
- mode="lecture" n'affiche pas commentaires inline
- mode="drawer" affiche commentaires inline
- les 2 modes contiennent btn-commenter-extraction et zone-commentaire-deroulable
- mode="drawer" + owner affiche btn-masquer-drawer
- mode="lecture" n'affiche pas btn-masquer-drawer

Bonus UX : les cartes du drawer affichent maintenant l'hypostase (manquait avant
la fusion). Le commenter est aussi disponible depuis le drawer.
```

---

## Phase 5 — Dashboard de consensus + helper simplifiés

### Task 5.1 — Réécrire `_calculer_consensus`

**Files :**
- Modify : `front/views.py:618-650` (approximatif)

- [ ] **Step 1 : lire la fonction actuelle**

```bash
sed -n '615,680p' /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : repérer les bornes**

La fonction commence par `def _calculer_consensus(page):` (ligne 618) et termine au `return {...}` final (probablement vers 650-680).

- [ ] **Step 3 : remplacer par la version simplifiée**

```python
def _calculer_consensus(page):
    """
    Calcule des stats binaires de debat pour une page :
    - total : nombre d'extractions visibles (non masquees)
    - commentees : nombre d'extractions avec au moins 1 commentaire
    - non_commentees : difference
    - pourcentage : ratio commentees/total en %

    / Computes binary debate stats for a page:
    - total : number of visible (non-hidden) extractions
    - commentees : number of extractions with at least 1 comment
    - non_commentees : difference
    - pourcentage : commentees/total ratio in %

    LOCALISATION : front/views.py
    """
    entites_visibles = ExtractedEntity.objects.filter(
        job__page=page, masquee=False,
    )
    total = entites_visibles.count()
    commentees = entites_visibles.filter(statut_debat="commente").count()
    return {
        "total": total,
        "commentees": commentees,
        "non_commentees": total - commentees,
        "pourcentage": int(100 * commentees / total) if total else 0,
    }
```

⚠️ Vérifier que les 2 sites d'usage (lignes 2165 et 4527) compilent encore après cette réécriture. Les clés du dict retourné sont nouvelles (`total`, `commentees`, `non_commentees`, `pourcentage`). Si l'ancien code utilisait des clés différentes (ex: `nb_consensuels`, `nb_controverse`, `bloquantes`), il faut adapter les sites d'usage en Tasks 5.2 et 5.3.

### Task 5.2 — Adapter le template dashboard_consensus.html

**Files :**
- Modify : `front/templates/front/includes/dashboard_consensus.html`

- [ ] **Step 1 : lire le fichier actuel**

```bash
cat /home/jonas/Gits/Hypostasia/front/templates/front/includes/dashboard_consensus.html
```

- [ ] **Step 2 : remplacer par version simple**

Réécrire entièrement (Write) :

```django
{# Dashboard consensus simplifie A.8 — barre binaire 'commentees / total' #}
{# / A.8 simplified consensus dashboard — binary 'commented / total' bar #}
{# LOCALISATION : front/templates/front/includes/dashboard_consensus.html #}

<div class="dashboard-consensus rounded-lg bg-white border border-slate-200 p-4 mb-3"
     data-testid="dashboard-consensus">
    <h3 class="text-sm font-semibold text-slate-700 mb-2">État du débat</h3>

    <p class="text-xs text-slate-600 mb-2">
        <strong class="text-slate-800">{{ consensus.commentees }}</strong> sur
        <strong class="text-slate-800">{{ consensus.total }}</strong>
        extraction{{ consensus.total|pluralize:"s" }} commentée{{ consensus.commentees|pluralize:"s" }}
        <span class="text-slate-400">({{ consensus.pourcentage }} %)</span>
    </p>

    {# Barre de progression binaire / Binary progress bar #}
    <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
        <div class="h-2 transition-all duration-500"
             style="width: {{ consensus.pourcentage }}%;
                    background-color: var(--statut-commente-accent);"
             aria-label="{{ consensus.pourcentage }}% du débat est engagé"></div>
    </div>

    {% if consensus.total == 0 %}
    <p class="text-xs text-slate-400 mt-2 italic">
        Aucune extraction sur cette page. Lance une analyse pour commencer.
    </p>
    {% endif %}
</div>
```

### Task 5.3 — Adapter `previsualiser_synthese` pour utiliser le nouveau format

**Files :**
- Modify : `front/views.py:2165` + `confirmation_synthese.html`

- [ ] **Step 1 : lire le contexte de previsualiser_synthese**

```bash
sed -n '2160,2200p' /home/jonas/Gits/Hypostasia/front/views.py
```

- [ ] **Step 2 : adapter le contexte passé au template**

Vérifier comment `donnees_consensus` est passé. Avec les nouvelles clés (`total`, `commentees`, `non_commentees`, `pourcentage`), le template `confirmation_synthese.html` doit afficher ces nouvelles infos.

- [ ] **Step 3 : adapter `confirmation_synthese.html`**

```bash
grep -n "consensuel\|controverse\|discutable\|nb_consensuels\|nb_controverse\|bloquantes\|donnees_consensus\|consensus\." /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_synthese.html
```

Pour chaque ligne qui utilise des anciens champs (ex: `{{ consensus.nb_consensuels }}`), la remplacer par le nouveau format. Ex :

Ancien :
```django
<p>{{ consensus.nb_consensuels }} consensuel(s), {{ consensus.nb_controverse }} controversé(s)</p>
```

Nouveau :
```django
<p>{{ consensus.commentees }} sur {{ consensus.total }} extraction{{ consensus.total|pluralize:"s" }} commentée{{ consensus.commentees|pluralize:"s" }} ({{ consensus.pourcentage }} %)</p>
```

- [ ] **Step 4 : retirer le gate / blocage si présent**

Si `previsualiser_synthese` ou `confirmation_synthese.html` contenait une logique "si controverse > 0 → bloquer", retirer ce blocage. Le bouton "Lancer la synthèse" doit toujours être actif.

- [ ] **Step 5 : `manage.py check`**

```bash
docker exec hypostasia_web uv run python manage.py check
```

### Task 5.4 — Vérifier dashboard_consensus.js

**Files :**
- Modify ou Delete : `front/static/front/js/dashboard_consensus.js`

- [ ] **Step 1 : lire le JS**

```bash
cat /home/jonas/Gits/Hypostasia/front/static/front/js/dashboard_consensus.js
```

- [ ] **Step 2 : décider**

Si le JS gérait des graphiques complexes (Chart.js, conditions sur 6 segments, etc.), le simplifier ou le supprimer.

- Si le nouveau dashboard est purement HTML/CSS (barre statique) → **supprimer le fichier** :
  ```bash
  rm /home/jonas/Gits/Hypostasia/front/static/front/js/dashboard_consensus.js
  ```
  Et retirer la ligne `<script src="...dashboard_consensus.js"></script>` dans `base.html`.

- Si le JS animait juste la barre de progression → garder une version minimale (~10 lignes) ou tout faire en CSS.

### Task 5.5 — Commit Phase 5

- [ ] **Step 1 : suggestion**

```
A.8 phase 5 : Dashboard consensus + helper _calculer_consensus simplifies.

_calculer_consensus passe de ~30 a ~10 lignes : retourne {total, commentees,
non_commentees, pourcentage} au lieu de l'agregation 6 segments.
dashboard_consensus.html : graphique 6 segments remplace par barre de progression
binaire avec compteur "X / Y commentees (Z%)".
confirmation_synthese.html : adapte pour le nouveau format consensus, gate retire
(l'utilisateur lance la synthese quand il veut).
dashboard_consensus.js : supprime / simplifie selon contenu actuel.
```

---

## Phase 6 — CSS + JS allégés

### Task 6.1 — Réduire les variables CSS de 6 paires à 2

**Files :**
- Modify : `front/static/front/css/hypostasia.css`

- [ ] **Step 1 : lire la zone**

```bash
grep -n "statut-" /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css | head -25
```

- [ ] **Step 2 : retirer les 5 paires obsolètes**

Localiser les blocs `--statut-consensuel-*`, `--statut-discutable-*`, `--statut-discute-*`, `--statut-controverse-*`, `--statut-non_pertinent-*`. Les retirer.

- [ ] **Step 3 : conserver `--statut-nouveau-*` et créer/garder `--statut-commente-*`**

Si `--statut-commente-*` n'existe pas, l'ajouter (récupérer la teinte verte de l'ex-`--statut-consensuel-*`) :

```css
--statut-commente-text: #047857;
--statut-commente-bg: #ecfdf5;
--statut-commente-accent: #009E73;
```

- [ ] **Step 4 : vérifier la cohérence**

```bash
grep -n "statut-" /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css
```

Expected : seulement 6 lignes (3 pour `nouveau`, 3 pour `commente`).

### Task 6.2 — Simplifier marginalia.js

**Files :**
- Modify : `front/static/front/js/marginalia.js`

- [ ] **Step 1 : lire le fichier**

```bash
grep -n "statut\|--statut-\|consensuel\|controvers\|discutable" /home/jonas/Gits/Hypostasia/front/static/front/js/marginalia.js | head -20
```

- [ ] **Step 2 : adapter la matrice de couleurs**

Si le JS contient un mapping type :
```javascript
const couleursParStatut = {
    nouveau: '#999999',
    discutable: '#E69F00',
    discute: '#0369a1',
    consensuel: '#009E73',
    controverse: '#FF4000',
    non_pertinent: '#6b7280',
};
```

Le réduire à :
```javascript
const couleursParStatut = {
    nouveau: '#999999',
    commente: '#009E73',
};
```

- [ ] **Step 3 : retirer les conditions sur les anciens statuts**

Tout `if (statut === 'consensuel')`, `case 'controverse':`, etc. → à retirer ou consolider en `if (statut === 'commente')`.

### Task 6.3 — Vérifier les autres fichiers JS

```bash
grep -rn "consensuel\|controverse\|discutable\|discute\|non_pertinent" /home/jonas/Gits/Hypostasia/front/static/front/js/ 2>/dev/null
```

- [ ] **Step 1 : pour chaque hit, adapter**

Soit retirer la branche obsolète (ex: handler de bouton supprimé), soit la consolider.

### Task 6.4 — Commit Phase 6

```
A.8 phase 6 : CSS + JS allegement.

hypostasia.css : 6 paires de variables --statut-* reduites a 2 (nouveau + commente),
~30 lignes retirees.
marginalia.js : matrice couleurs 6 cases -> 2 cases, simplification des conditions
sur statut.
```

---

## Phase 7 — Templates aide / onboarding + fixtures

### Task 7.1 — Simplifier aide_desktop.html

**Files :**
- Modify : `front/templates/front/includes/aide_desktop.html`

- [ ] **Step 1 : grep**

```bash
grep -n "statut\|consensuel\|controvers\|discutable\|discute\|non_pertinent" /home/jonas/Gits/Hypostasia/front/templates/front/includes/aide_desktop.html
```

- [ ] **Step 2 : pour chaque section qui explique les 6 statuts**

Remplacer par un court paragraphe :

```html
<p class="text-sm text-slate-700 mb-2">
    <strong>Statut d'une extraction</strong> — Le statut passe automatiquement à
    <span class="font-semibold text-emerald-700">commenté</span> dès qu'au moins
    une personne y écrit. Plus tard, l'alignement automatique enrichira ces statuts.
</p>
```

### Task 7.2 — Idem pour aide_mobile.html

**Files :**
- Modify : `front/templates/front/includes/aide_mobile.html`

Mêmes étapes que Task 7.1.

### Task 7.3 — Idem pour onboarding_vide.html

**Files :**
- Modify : `front/templates/front/includes/onboarding_vide.html`

Mêmes étapes.

### Task 7.4 — Adapter `charger_fixtures_demo.py`

**Files :**
- Modify : `front/management/commands/charger_fixtures_demo.py`

- [ ] **Step 1 : grep**

```bash
grep -n "statut_debat" /home/jonas/Gits/Hypostasia/front/management/commands/charger_fixtures_demo.py
```

- [ ] **Step 2 : pour chaque set explicite**

Si la fixture set explicitement `statut_debat="consensuel"` ou similaire (valeurs riches), remplacer par `statut_debat="nouveau"`. Le signal Django passera automatiquement à `commente` lorsque les commentaires de la fixture seront créés ensuite.

⚠️ **Ordre des create dans la fixture** : créer les ExtractedEntity AVANT les CommentaireExtraction (sinon le signal échoue car l'entité n'existe pas). Vérifier que c'est déjà le cas.

### Task 7.5 — Tester le rechargement des fixtures

```bash
docker exec hypostasia_web uv run python manage.py charger_fixtures_demo
```

Expected : succès sans erreur. Le signal s'auto-applique et les statuts sont cohérents.

- [ ] **Step 1 : vérifier les stats DB**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity
from django.db.models import Count
qs = ExtractedEntity.objects.values('statut_debat').annotate(n=Count('id'))
for r in qs:
    print(r)
"
```

Expected : seulement `nouveau` et `commente`.

### Task 7.6 — Commit Phase 7

```
A.8 phase 7 : templates aide + fixtures.

aide_desktop.html, aide_mobile.html, onboarding_vide.html : sections explicatives
des 6 statuts remplacees par paragraphe court "le statut passe automatiquement a
commente quand une personne y ecrit".
charger_fixtures_demo.py : valeurs riches statut_debat remplacees par "nouveau"
(le signal Django les passera a "commente" lorsque les commentaires sont crees).
```

---

## Phase 8 — Tests : retrait des morts + lancement complet

### Task 8.1 — Identifier les tests qui plantent ou sont obsolètes

- [ ] **Step 1 : lancer la suite**

```bash
docker exec hypostasia_web uv run python manage.py test --keepdb -v 1 2>&1 | tee /tmp/A8_tests_phase8.log | tail -40
```

- [ ] **Step 2 : analyser**

```bash
grep -E "^ERROR|^FAIL" /tmp/A8_tests_phase8.log | head -30
```

Identifier les tests qui plantent à cause des refs obsolètes (`changer_statut`, `statut_debat="consensuel"`, etc.).

### Task 8.2 — Retirer les classes / méthodes mortes

```bash
grep -rnE "test_.*changer_statut|test_.*consensuel|test_.*discutable|test_.*controvers|test_.*non_pertinent|statut_debat=.consensuel|statut_debat=.discutable|statut_debat=.discute|statut_debat=.controverse|statut_debat=.non_pertinent" /home/jonas/Gits/Hypostasia/front/tests/ 2>/dev/null | grep -v "test_phase_a8"
```

- [ ] **Step 1 : pour chaque hit**

Lire le contexte. Décider :
- Méthode dont le seul but est de tester un statut riche disparu → retirer la méthode entière
- Méthode qui mentionne juste une chaîne (ex: `commentaire.commentaire = "le statut consensuel..."`) → garder
- setUp d'une classe qui crée une entité avec `statut_debat="consensuel"` → adapter en `statut_debat="nouveau"` ou `"commente"` selon le sens du test

Utiliser Edit pour chaque modification.

### Task 8.3 — Lancer la suite finale et comparer

```bash
docker exec hypostasia_web uv run python manage.py test --keepdb -v 1 2>&1 | tee /tmp/A8_tests_apres.log | tail -10
```

- [ ] **Step 1 : comparer**

```bash
grep -E "^Ran|^OK|^FAILED" /tmp/A8_tests_avant.log /tmp/A8_tests_apres.log
```

Expected : 
- Tests retirés ⇒ `Ran X` après < `Ran X` avant
- Errors ne doit pas augmenter par rapport au snapshot pré-A.8 (les errors préexistantes restent)
- Pas de NOUVEAU fail

⚠️ Si un test qui passait avant fail maintenant, **diagnostiquer et fixer**. Ne pas tolérer une régression.

### Task 8.4 — Commit Phase 8

```
A.8 phase 8 : retrait tests morts + verification anti-regression.

Retire les tests dependant des features supprimees (changer_statut, statuts riches
consensuel/controverse/etc.). Snapshot pre-A.8 : X tests OK. Snapshot post-A.8 :
Y tests OK (Y < X attendu, zero regression). Les 3 nouvelles classes de tests
A.8 (signal + fusion templates) passent OK.
```

---

## Phase 9 — Vérification anti-régression UI Chrome + finalisation

### Task 9.1 — `manage.py check`

```bash
docker exec hypostasia_web uv run python manage.py check
```

Expected : System check identified no issues.

### Task 9.2 — Test UI complet via Chrome

- [ ] **Step 1 : page lecture `/lire/4/`**

Vérifier visuellement :
- ✅ Cartes inline : indicateur statut binaire (gris ou vert) + hypostase + résumé + citation + bouton "Commenter"
- ✅ Aucun bouton statut riche (pas de Discutable/Consensuel/Controversé/Non pertinent)
- ✅ Bouton "Replier" toujours présent
- ✅ Bouton "Masquer" si owner (hover)

- [ ] **Step 2 : ouvrir le drawer Analyses**

- ✅ Liste des extractions avec **hypostases visibles** (corrigé par fusion templates)
- ✅ Commentaires affichés inline sous chaque carte
- ✅ Bouton "Commenter" en bas de chaque carte (nouveau dans drawer)

- [ ] **Step 3 : créer un commentaire depuis le drawer**

- Cliquer sur "Commenter" dans une carte du drawer → zone formulaire se déplie
- Taper "Test commentaire A.8" → cliquer "Envoyer"
- Vérifier que la requête HTMX réussit
- Recharger la page → l'entité a maintenant statut `commente` (indicateur vert)
- Recharger le drawer → le commentaire apparaît inline

- [ ] **Step 4 : supprimer le dernier commentaire d'une entité**

- Trouver une entité avec un seul commentaire
- Le supprimer
- Vérifier que l'entité repasse en statut `nouveau` (indicateur gris)

- [ ] **Step 5 : action `masquer`**

- Cliquer sur le bouton masquer hover dans le drawer
- Vérifier que l'entité disparaît (ou passe dans la zone "non pertinentes" si elle existe)
- Le statut `masquee` est indépendant — l'entité peut avoir `statut_debat=commente` ET `masquee=True`

- [ ] **Step 6 : Dashboard consensus**

- Aller sur `/lire/4/dashboard_consensus/` ou via le bouton dédié
- Vérifier l'affichage : "X sur Y extraction(s) commentée(s) (Z%)" + barre de progression simple

- [ ] **Step 7 : Synthèse délibérative**

- Cliquer "Synthèse" → choisir un analyseur synthétiseur (ex: "Charte")
- Vérifier que `confirmation_synthese.html` affiche le ratio `commentees / total`
- Aucun gate qui bloque le lancement
- Lancer → toast → bouton tâches passe en spinner puis vert
- Cliquer "Voir résultat" → ouvre la nouvelle Page Vn+1

### Task 9.3 — Mise à jour CHANGELOG

**Files :**
- Modify : `CHANGELOG.md`

- [ ] **Step 1 : ajouter une entrée en tête**

Ouvrir le fichier et ajouter après `# Changelog — Hypostasia V3` :

```markdown
## 2026-MM-DD — Session A.8 : Statuts de débat binaires + fusion templates carte + commenter dans drawer

**Quoi / What:** simplification de `ExtractedEntity.statut_debat` de 6 valeurs à 2
(`nouveau` / `commente`) auto-dérivées par signal Django, fusion des 2 templates
carte inline + drawer en un seul partial paramétré, ajout du bouton commenter dans
le drawer, fusion `non_pertinent` (statut) → `masquee=True` (champ).

**Pourquoi / Why:** suite logique du brainstorming YAGNI 2026-05-01 et de la session
A.7. Découverte en pré-audit Chrome qu'un même objet ExtractedEntity était rendu par
2 templates distincts (carte inline `_card_body.html` + carte drawer dans
`drawer_vue_liste.html`) avec divergence (drawer ne montrait pas l'hypostase). Les 6
valeurs de statut riches ne servaient pas car définies manuellement par bouton, et
le moteur d'alignement RAG (Phase B) prendra le relais pour la déduction
sémantique. Permet de retirer ~600 lignes net.

### Changements principaux / Main changes

1. **Signal Django auto-update** : nouveau `hypostasis_extractor/signals.py`. Le
   statut `statut_debat` est auto-dérivé de l'existence de commentaires (post_save +
   post_delete sur CommentaireExtraction).
2. **Enum réduit** : `StatutDebat` passe de 6 valeurs à 2 (`NOUVEAU`, `COMMENTE`).
   Migration data + AlterField.
3. **Fusion `non_pertinent` → `masquee`** : le statut `non_pertinent` disparaît, ses
   2 instances en DB sont fusionnées dans `masquee=True`. Le champ `masquee` devient
   indépendant du statut.
4. **Action `changer_statut` retirée** : 4 boutons UI (Discutable, Consensuel,
   Controversé, Non pertinent) supprimés de `carte_inline.html`. Action ViewSet +
   `ChangerStatutSerializer` retirés.
5. **Fusion templates** : `_card_body.html` paramétré par `mode="lecture"|"drawer"`
   est désormais l'unique partial de contenu de carte. `drawer_vue_liste.html`
   retire ~105 lignes de contenu dupliqué. **Bénéfice UX visible** : le drawer
   affiche maintenant l'hypostase (manquait avant) et permet de commenter.
6. **Dashboard consensus simplifié** : graphique 6 segments remplacé par barre
   binaire `commentees / total`.
7. **`_calculer_consensus`** simplifié de ~30 à ~10 lignes.
8. **CSS** : 6 paires de variables `--statut-*` réduites à 2.
9. **Marginalia.js** : matrice 6 statuts → 2.
10. **Templates aide** simplifiés.

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/00XX_a8_recalcul_statuts_fusion_non_pertinent.py` :
  RunPython qui fusionne `non_pertinent` → `masquee=True` puis recalcule tous les
  statuts depuis les commentaires (option A : recalcul pur).
- `hypostasis_extractor/migrations/00YY_a8_alter_statut_debat_choices.py` : AlterField
  qui réduit l'enum à 2 valeurs.

### Solde net / Net balance

- Cumul cleanup A.1 → A.8 : ~13500 lignes net retirées en 8 sessions.
- Phase A.8 contribue : ~−600 lignes nettes.

### Vérification anti-régression / Anti-regression check

- Snapshot tests pré-A.8 : X tests OK
- Snapshot tests post-A.8 : Y tests OK (zero régression introduite)
- Test UI Chrome : page lecture, drawer Analyses, création/suppression commentaire,
  dashboard consensus, synthèse délibérative — tous OK.

### Hors périmètre / Out of scope (conservé intact)

- Moteur d'alignement RAG (Phase B)
- Synthèse délibérative + analyseurs synthétiseurs
- Système de commentaires
- Champ `masquee` (devient indépendant mais reste fonctionnel)
- Versionning de pages (`parent_page`, `versions_enfants`)

### Références / References

- Spec A.8 : `PLAN/A.8-statuts-binaires-fusion-templates-spec.md`
- Plan d'exécution : `PLAN/A.8-statuts-binaires-fusion-templates-plan.md`
- Spec maître YAGNI : `PLAN/REVUE_YAGNI_2026-05-01.md`

---
```

⚠️ Ne pas oublier de remplacer `2026-MM-DD` par la date du jour, et `X tests OK / Y tests OK / ...` par les vraies valeurs.

### Task 9.4 — Mise à jour CLAUDE.md / GUIDELINES si refs obsolètes

```bash
grep -n "statut\|consensuel\|controvers\|discutable" /home/jonas/Gits/Hypostasia/CLAUDE.md
```

- [ ] **Step 1 : si refs aux 6 statuts**, simplifier en mention courte "2 statuts auto-dérivés des commentaires (nouveau / commente)".

### Task 9.5 — Commit final Phase 9

- [ ] **Step 1 : afficher le diff total**

```bash
git status && git diff --stat
```

- [ ] **Step 2 : suggestion**

```
A.8 phase 9 : finalisation + verification anti-regression UI + CHANGELOG.

Test manuel Chrome complet :
- page /lire/4/ : cartes inline avec indicateur statut binaire, sans boutons
  statut riche, hypostase + resume + citation + bouton commenter
- drawer Analyses : hypostases maintenant visibles (correctif), commentaires inline,
  bouton commenter operationnel
- creation commentaire depuis drawer -> entite passe a commente, indicateur passe
  au vert
- suppression dernier commentaire -> entite repasse a nouveau
- dashboard consensus : barre binaire commentees/total
- synthese deliberative : ratio commentees affiche, pas de gate, lancement OK

Aucune regression observee. CHANGELOG mis a jour. Cumul cleanup A.1 -> A.8 : ~13500
lignes net retirees en 8 sessions.
```

---

## Annexe — Plan B en cas de problème

### Si le signal ne se déclenche pas (Phase 1)

- Vérifier que `apps.py:ready()` importe bien `signals` (avec `# noqa: F401`)
- Vérifier que `INSTALLED_APPS` dans `hypostasia/settings.py` contient bien la classe `'hypostasis_extractor.apps.HypostasisExtractorConfig'` (et pas juste `'hypostasis_extractor'` qui ne déclenche pas `ready()`).
- Si OK, vérifier que `CommentaireExtraction.entity` est bien le ForeignKey vers `ExtractedEntity` (et pas un autre nom de champ).

### Si la migration data échoue (Phase 2)

- Vérifier que la dépendance dans le `Migration` pointe bien vers la dernière migration A.7 (`0028_a7_retrait_reformulation_restitution_fields` ou autre).
- Si Django dit "circular dependency" ou "migration not found" : relire la chaîne de migrations existantes via `showmigrations`.

### Si le test fusion templates échoue (Phase 4)

- Vérifier que `entity_json_attrs` template tag fonctionne bien. En pré-audit on a vu qu'il retourne `[hypostase, resume, statut, mots_cles]` (liste de 4 éléments), donc `entity_attrs.0`, `entity_attrs.1` etc. sont indexables.
- Vérifier que `attr_0`, `attr_1` etc. sont bien passés au partial via `{% with %}` dans le template parent.

### Si une régression UI apparaît (Phase 9)

- Vérifier que `data-statut="{{ entity.statut_debat }}"` reçoit bien `nouveau` ou `commente` (pas vide ou autre).
- Vérifier que les CSS variables `--statut-nouveau-accent` et `--statut-commente-accent` sont bien définies dans `hypostasia.css`.
- Vérifier que le JS `marginalia.js` utilise les nouvelles 2 valeurs et pas les anciennes.

### Rollback complet

Si à mi-chemin Jonas décide d'annuler, tous les commits sont conventionnels et peuvent être `git revert` un par un, dans l'ordre inverse. La donnée perdue (statuts riches mappés vers binaire) ne peut pas être restaurée par revert — il faudrait restaurer un dump DB pré-A.8.

---

## Auto-revue du plan

**1. Spec coverage** :
- ✅ Décision Q1 (`_calculer_consensus` signal binaire B) : Phase 5
- ✅ Décision Q2 (signal Django A) : Phase 1
- ✅ Décision Q3 (champ statut_debat Voie 1) : Phase 2
- ✅ Décision Q4 (recalcul pur A) : Phase 2
- ✅ Dashboard simplifié : Phase 5
- ✅ Fusion non_pertinent → masquee : Phase 2 + Phase 3
- ✅ Fusion templates Option A : Phase 4
- ✅ Commenter dans drawer : Phase 4 (intégré dans le partial paramétré)
- ✅ CSS allégé : Phase 6
- ✅ Templates aide : Phase 7
- ✅ Tests retirés + ajoutés : Phase 8
- ✅ Anti-régression UI : Phase 9
- ✅ CHANGELOG : Phase 9

**2. Placeholder scan** : aucun "TBD", "TODO". Les `00XX` / `00YY` dans les noms de migration sont explicitement marqués (numérotation auto par Django). Les "X tests OK" du CHANGELOG sont à remplacer à l'exécution avec les vrais chiffres.

**3. Type consistency** :
- `mode` parameter : `"lecture"` ou `"drawer"` partout.
- Clés du dict `consensus` : `total`, `commentees`, `non_commentees`, `pourcentage` partout.
- Statut values : `"nouveau"` ou `"commente"` partout.
- Signal handler name : `synchroniser_statut_debat` partout.
- Variable name : `entite_id` cohérent dans le signal.

---

## Solde net estimé

- **Lignes retirées** : ~700 (logique manuelle + boutons + dashboard riche + 4 paires CSS + duplication templates + JS branches + tests morts)
- **Lignes ajoutées** : ~100 (signal + 2 migrations + 5 tests TDD + paramètre mode dans partial + dashboard simplifié + fixture commenter dans drawer)
- **Net** : **~−600 lignes**

---

## Références

- Spec A.8 : `PLAN/A.8-statuts-binaires-fusion-templates-spec.md`
- Plans précédents : A.1 → A.7
- Cumul A.1 → A.7 : ~12900 lignes net retirées
- Skill exécution : `superpowers:subagent-driven-development` (un subagent par phase recommandé) ou `superpowers:executing-plans`
