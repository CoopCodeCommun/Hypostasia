# A.8 — Statuts de débat binaires + fusion templates carte + commenter dans drawer (spec)

**Date** : 2026-05-02 (brainstorming après A.7)
**Auteur** : Jonas Turbeaux (Code Commun) + brainstorming Claude Code via skill `superpowers:brainstorming`
**Statut** : design validé, prêt pour `writing-plans`

> **Note** : ce document est la **spec** (design produit). Le **plan d'implémentation détaillé** sera écrit ensuite dans `PLAN/A.8-statuts-binaires-fusion-templates-plan.md` via la skill `superpowers:writing-plans`.

---

## Contexte

A.7 vient de retirer Reformulation IA + Restitution IA + Restitution manuelle (~4490 lignes). Au cours de l'audit Chrome, on a découvert deux templates concurrents pour afficher une extraction (`_card_body.html` utilisé par les cartes inline + un contenu dupliqué dans `drawer_vue_liste.html`), et 6 valeurs de statut de débat manuellement set par boutons utilisateur, avec un Dashboard de consensus dédié et un gate avant synthèse.

**Brief utilisateur** :

> *« On va retirer aussi les boutons controversé et consensuel. Au final on peut le deviner grâce aux commentaires avec un alignement futur, non ? J'aimerais aussi qu'on puisse commenter depuis le drawer. Dans ce cas-là, on a le même objet non ? »*

L'idée : simplifier en **2 valeurs uniquement** (`nouveau` / `commente`) auto-dérivées de l'existence d'au moins 1 commentaire. Le moteur d'alignement RAG (Phase B) raffinera plus tard. Cela permet aussi la **fusion des deux templates** (carte inline + carte drawer) qui deviennent vraiment identiques en contenu.

---

## Décisions du brainstorming (Q1-Q4)

| # | Question | Décision | Conséquence |
|---|---|---|---|
| **Q1** | `_calculer_consensus` dans `previsualiser_synthese` | **B** — Signal binaire informatif | Affiche "X commentées sur Y total (%)" avant lancement de synthèse, **sans gate**. L'utilisateur lance quand il veut. |
| **Q2** | Mécanisme d'auto-update du statut | **A** — Signal Django | `post_save` / `post_delete` sur `CommentaireExtraction` met à jour `statut_debat` via `update()` (évite récursion). Filtrage SQL natif conservé. |
| **Q3** | Champ `statut_debat` | **Voie 1** — garder + rétrécir | Le champ DB reste, mais l'enum passe de 6 valeurs à 2. Pas de refactor des querysets, pas de risque N+1. |
| **Q4** | Migration data | **A** — Recalcul pur | Toutes les entités sont recalculées : `commente` si ≥1 commentaire, `nouveau` sinon. Une entité orpheline (statut actif sans commentaire — 1 cas en DB live) repassera à `nouveau`. |

Décisions structurelles préalables (validées en discussion) :
- Dashboard de consensus : **simplifié** (pas retiré), passe d'un graphique 6 segments à un compteur binaire + barre de progression
- Fusion `non_pertinent` (statut) → `masquee=True` (champ bool) : **OK**
- Fusion templates : **Option A** — `_card_body.html` paramétré par `mode="lecture"|"drawer"`, point unique de vérité pour le contenu de carte

---

## Architecture

### 1. Modèle de données

#### Champ `statut_debat`

```python
# hypostasis_extractor/models.py
class ExtractedEntity(models.Model):

    class StatutDebat(models.TextChoices):
        NOUVEAU = "nouveau", "Nouveau"
        COMMENTE = "commente", "Commenté"

    statut_debat = models.CharField(
        max_length=20,
        choices=StatutDebat.choices,
        default=StatutDebat.NOUVEAU,
        help_text=(
            "Statut auto-derive de l'existence de commentaires. "
            "Mis a jour par signal Django, jamais set manuellement. "
            "/ Status auto-derived from comment existence. "
            "Updated by Django signal, never set manually."
        ),
    )
```

Suppression : `discutable`, `discute`, `consensuel`, `controverse`, `non_pertinent` (5 valeurs retirées).

#### Méthode `save()` — retrait de la sync masquee/non_pertinent

Le bloc actuel (lignes 210-212) :
```python
# Synchronise masquee avec statut_debat : non_pertinent ↔ masquee=True
self.masquee = (self.statut_debat == "non_pertinent")
```

À retirer. Le champ `masquee` reste indépendant, set uniquement par les actions `masquer` / `restaurer` du ViewSet.

### 2. Signal Django d'auto-update

#### Nouveau fichier : `hypostasis_extractor/signals.py`

```python
"""
Signaux pour la synchronisation automatique du statut de debat.
/ Signals for automatic debate status synchronization.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import CommentaireExtraction, ExtractedEntity


@receiver([post_save, post_delete], sender=CommentaireExtraction)
def synchroniser_statut_debat(sender, instance, **kwargs):
    """
    Met a jour ExtractedEntity.statut_debat selon l'existence de commentaires.
    Utilise update() pour eviter de redeclencher save() de l'entite.
    / Update ExtractedEntity.statut_debat based on comment existence.
    Uses update() to avoid re-triggering entity save().
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

#### Connexion : `hypostasis_extractor/apps.py`

```python
class HypostasisExtractorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hypostasis_extractor"

    def ready(self):
        from . import signals  # noqa: F401
```

#### Logique manuelle existante à retirer

`front/views.py:213` (action `ajouter_commentaire`) et `:3807-3809` (autre site) ont une logique manuelle :
```python
if entite.statut_debat in ("nouveau", "discutable"):
    entite.statut_debat = "discute"
    entite.save(update_fields=["statut_debat"])
```

À retirer — le signal s'en charge automatiquement.

`views.py:4414` (action `masquer`) et `:4454` (action `restaurer`) :
```python
entite_a_masquer.statut_debat = "non_pertinent"  # à retirer
entite_a_masquer.save(update_fields=["statut_debat", "masquee"])  # devient juste ["masquee"]
```

À retirer la première ligne. Garder uniquement le set/unset de `masquee`.

### 3. Action `changer_statut` retirée

`views.py:4476-4500` (approximatif post-A.7) — l'action ViewSet `changer_statut` complète + son URL `@action(detail=False, methods=["POST"], url_path="changer_statut")`.

`front/serializers.py` — `ChangerStatutSerializer` retiré.

`front/templates/front/includes/carte_inline.html:42-89` — les 4 boutons (`Discutable`, `Consensuel`, `Controversé`, `Non pertinent`) qui appelaient `hx-post="/extractions/changer_statut/"` retirés. Reste uniquement le bouton `Masquer` et le bouton `Commenter` inline.

### 4. Migration data — recalcul pur

#### Fichier 1 : data migration (RunPython)

```python
# hypostasis_extractor/migrations/00XX_a8_recalcul_statuts_fusion_non_pertinent.py
from django.db import migrations


def recalculer_statuts(apps, schema_editor):
    """
    1. Fusionne non_pertinent → masquee=True (en gardant le statut pour l'instant)
    2. Recalcule tous les statuts depuis les commentaires
    """
    ExtractedEntity = apps.get_model('hypostasis_extractor', 'ExtractedEntity')
    CommentaireExtraction = apps.get_model('hypostasis_extractor', 'CommentaireExtraction')

    # Etape 1 : non_pertinent → masquee=True
    nb_non_pertinent = ExtractedEntity.objects.filter(
        statut_debat='non_pertinent',
    ).update(masquee=True)
    print(f"  -> A.8 : {nb_non_pertinent} entites non_pertinent fusionnees dans masquee=True")

    # Etape 2 : recalcul depuis les commentaires
    ids_commentees = set(CommentaireExtraction.objects.values_list(
        'entity_id', flat=True,
    ).distinct())

    nb_commente = ExtractedEntity.objects.filter(
        pk__in=ids_commentees,
    ).exclude(statut_debat='commente').update(statut_debat='commente')

    nb_nouveau = ExtractedEntity.objects.exclude(
        pk__in=ids_commentees,
    ).exclude(statut_debat='nouveau').update(statut_debat='nouveau')

    print(f"  -> A.8 : {nb_commente} entites passees a commente, "
          f"{nb_nouveau} entites repassees a nouveau")


class Migration(migrations.Migration):
    dependencies = [
        ('hypostasis_extractor', '00XX_PRECEDENTE'),
    ]
    operations = [
        migrations.RunPython(recalculer_statuts, reverse_code=migrations.RunPython.noop),
    ]
```

#### Fichier 2 : AlterField (rétrécissement enum)

```python
# hypostasis_extractor/migrations/00XX_a8_alter_statut_debat_choices.py
class Migration(migrations.Migration):
    dependencies = [
        ('hypostasis_extractor', '00XX_a8_recalcul_statuts_fusion_non_pertinent'),
    ]
    operations = [
        migrations.AlterField(
            model_name='extractedentity',
            name='statut_debat',
            field=models.CharField(
                choices=[('nouveau', 'Nouveau'), ('commente', 'Commenté')],
                default='nouveau',
                max_length=20,
            ),
        ),
    ]
```

**Ordre critique** : data migration AVANT AlterField, sinon Django rejette les valeurs `consensuel`/`discutable`/etc. encore présentes en DB.

---

### 5. Architecture UI — `_card_body.html` paramétré

#### Partial unique : `hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html`

Reçoit le paramètre `mode` (défaut `"lecture"`). Structure :

```django
{% load extractor_tags %}
{% with mode=mode|default:"lecture" %}
<div class="extraction-content">

    {# === Header : indicateur statut + hypostases + compteur commentaires === #}
    <div class="flex items-center gap-2 mb-2">
        {# Indicateur statut binaire (gris ou vert) #}
        <span class="indicateur-statut w-3.5 h-3.5 flex-shrink-0"
              data-statut="{{ entity.statut_debat }}"
              style="background-color: var(--statut-{{ entity.statut_debat }}-accent);"
              title="{{ entity.get_statut_debat_display }}"></span>

        {# Badges hypostases #}
        {% if attr_0 %}
            <div class="flex flex-wrap gap-0.5 min-w-0">
                {% for tag in attr_0|split_comma %}
                <span class="typo-hypostase ..."
                      style="background: var(--hypostase-{{ tag|hypostase_famille }}-bg);
                             color: var(--hypostase-{{ tag|hypostase_famille }}-text);"
                      title="{{ tag }} — {{ tag|hypostase_definition }}">{{ tag }}</span>
                {% endfor %}
            </div>
        {% endif %}

        <span class="flex-1"></span>

        {# Compteur commentaires #}
        {% if entity.nombre_commentaires %}
            <span class="inline-flex items-center gap-1 text-[10px] text-amber-600 flex-shrink-0">
                {{ entity.nombre_commentaires }}
            </span>
        {% endif %}

        {# Bouton masquer hover (drawer only, owner only) #}
        {% if mode == "drawer" and est_proprietaire %}
            <button class="btn-masquer-drawer ...">...</button>
        {% endif %}
    </div>

    {# === Body : résumé IA + citation source === #}
    {% if attr_1 %}
        <p class="typo-machine ...">{{ attr_1 }}</p>
    {% endif %}
    <p class="typo-citation italic ...">
        [{{ entity.extraction_text|truncatechars:120 }}]
    </p>

    {# === Mots-clés (les 2 modes) === #}
    {% if attr_3 %}
        <div class="flex flex-wrap gap-1 mt-1">
            {% for mc in attr_3|split_comma %}
                <span class="text-[9px] text-slate-500 bg-slate-50 px-1 rounded">
                    #{{ mc }}
                </span>
            {% endfor %}
        </div>
    {% endif %}

    {# === Commentaires affichés inline (drawer only) === #}
    {% if mode == "drawer" %}
        {% for commentaire in entity.commentaires.all %}
            <div class="commentaire-bulle-drawer mt-2
                {% if contributeurs_actifs %}
                    {% if mode_filtre == "exclure" %}
                        {% if commentaire.user.pk in contributeurs_actifs %}commentaire-hors-filtre{% endif %}
                    {% else %}
                        {% if commentaire.user.pk not in contributeurs_actifs %}commentaire-hors-filtre{% endif %}
                    {% endif %}
                {% endif %}">
                <span class="typo-lecteur-nom">{{ commentaire.user.first_name|default:commentaire.user.username|title }}</span>
                <p class="text-sm text-slate-700">{{ commentaire.commentaire }}</p>
            </div>
        {% endfor %}
    {% endif %}

    {# === Zone formulaire commentaire — masquée par défaut, dépliée au clic === #}
    <div class="zone-commentaire-deroulable hidden mt-2"
         data-extraction-id="{{ entity.pk }}">
        <form hx-post="/extractions/ajouter_commentaire/"
              hx-vals='{"entity_id": "{{ entity.pk }}", "page_id": "{{ entity.job.page_id }}"}'
              hx-target="..."
              hx-swap="...">
            <textarea name="commentaire" class="..." rows="2"></textarea>
            <button type="submit" class="...">Envoyer</button>
        </form>
    </div>

    {# === Footer : bouton commenter (les 2 modes) === #}
    <button class="btn-commenter-extraction text-xs text-slate-400 hover:text-amber-600 mt-2"
            data-entity-id="{{ entity.pk }}"
            onclick="this.previousElementSibling.classList.toggle('hidden');
                     var ta = this.previousElementSibling.querySelector('textarea');
                     if (ta) ta.focus();">
        Commenter
    </button>

</div>
{% endwith %}
```

**~150 lignes total** (vs 100 lignes actuelles dans `_card_body.html` + 100 lignes de duplication dans `drawer_vue_liste.html` lignes 131-235 = ~200 lignes économisées).

#### Wrappers consommateurs

**`carte_inline.html`** :
```django
<div class="carte-inline carte-inline-entree" id="carte-inline-{{ entity.pk }}"
     data-extraction-id="{{ entity.pk }}"
     data-statut="{{ entity.statut_debat }}">
    <button class="btn-replier-carte" ...>&#9652;</button>
    {% include "hypostasis_extractor/includes/_card_body.html" with mode="lecture" %}
</div>
```

**`drawer_vue_liste.html`** :
```django
{% for entity in entites_visibles %}
{% entity_json_attrs entity as entity_attrs %}
<div class="drawer-carte mb-2 rounded-lg border border-slate-100 cursor-pointer ..."
     data-extraction-id="{{ entity.pk }}"
     data-page-id="{{ page.pk }}"
     style="border-left: 3px solid var(--statut-{{ entity.statut_debat }}-accent);">
    {% with attr_0=entity_attrs.0 attr_1=entity_attrs.1 attr_2=entity_attrs.2 attr_3=entity_attrs.3 %}
        {% include "hypostasis_extractor/includes/_card_body.html" with mode="drawer" %}
    {% endwith %}
</div>
{% endfor %}
```

`drawer_vue_liste.html` retire les ~105 lignes de contenu dupliqué (lignes 131-235), gardé uniquement le wrapper + bandeau du drawer + filtres.

### 6. CSS — réduction des variables

`front/static/front/css/hypostasia.css` :

**Conserver** (2 paires) :
```css
--statut-nouveau-text: #6b7280;
--statut-nouveau-bg: #f3f4f6;
--statut-nouveau-accent: #999999;

--statut-commente-text: #047857;     /* récupère la teinte vert consensuel */
--statut-commente-bg: #ecfdf5;
--statut-commente-accent: #009E73;
```

**Retirer** : 5 paires (`consensuel`, `discutable`, `discute`, `controverse`, `non_pertinent`).

### 7. JS — `marginalia.js` simplifié

La matrice de couleurs des pastilles de marge passe de 6 cases à 2. ~30 lignes simplifiées.

### 8. Dashboard de consensus simplifié

#### Helper `_calculer_consensus` (`front/views.py:618`) — réécriture

Avant (~30 lignes) : agrégation par `values_list("statut_debat").annotate(count)`, calcul des ratios, détection bloquantes.

Après (~10 lignes) :
```python
def _calculer_consensus(page):
    """
    Calcule des stats binaires de debat pour une page.
    / Computes binary debate stats for a page.
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

#### Template `dashboard_consensus.html` simplifié

Remplace le graphique 6-segments par :
```django
<div class="dashboard-consensus">
    <h3>Etat du debat</h3>
    <p class="text-sm text-slate-600">
        <strong>{{ consensus.commentees }}</strong> sur
        <strong>{{ consensus.total }}</strong> extraction{{ consensus.total|pluralize:"s" }}
        commentee{{ consensus.commentees|pluralize:"s" }}
        <span class="text-slate-400">({{ consensus.pourcentage }}%)</span>
    </p>
    <div class="progress-bar mt-2">
        <div class="progress-fill" style="width: {{ consensus.pourcentage }}%;
             background-color: var(--statut-commente-accent);"></div>
    </div>
</div>
```

JS `dashboard_consensus.js` : à simplifier ou supprimer si plus de logique conditionnelle nécessaire.

### 9. Templates d'aide / onboarding

`aide_desktop.html`, `aide_mobile.html`, `onboarding_vide.html` : sections expliquant les 6 statuts → remplacer par court paragraphe :

> *"Le statut d'une extraction passe à 'commenté' dès qu'une personne y écrit. Plus tard, l'alignement automatique enrichira ces statuts."*

### 10. Fixture demo

`charger_fixtures_demo.py` : si elle set explicitement `statut_debat="consensuel"` ou autres valeurs riches sur des entités, les réduire à `nouveau` (le signal s'occupera de set `commente` quand les commentaires sont créés à la suite par la même fixture).

---

## Tests

### Tests à retirer

À identifier en exécution via :
```bash
grep -rnE "test_.*changer_statut|test_.*consensuel|test_.*discutable|test_.*controvers|test_.*non_pertinent|statut_debat=.consensuel|statut_debat=.discutable|statut_debat=.discute|statut_debat=.controverse" /home/jonas/Gits/Hypostasia/front/tests/
```

Estimation pré-audit :
- ~5-8 méthodes dans `test_phases.py`
- Refs `statut_debat=` dans setUp de `test_phase27b.py`, `test_phase28_light.py`, `test_phase29_synthese_drawer.py`
- 4-5 fichiers E2E (déjà dans les 19 errors pré-existantes asyncio — adaptation seulement)

### Tests à ajouter

**Classe `Phase8SignalSynchroniseStatutTest`** (~3 tests) :
- `test_creation_commentaire_passe_statut_a_commente` — créer un `CommentaireExtraction` sur une entité `nouveau` → assertion statut == `commente`
- `test_suppression_dernier_commentaire_repasse_a_nouveau` — supprimer le dernier commentaire → statut repasse à `nouveau`
- `test_suppression_avec_commentaires_restants_garde_commente` — supprimer un commentaire parmi 2 → statut reste `commente`

**Classe `Phase8MigrationDataTest`** (~2 tests) :
- `test_recalcul_statuts_pur` — mock l'état pré-migration, exécute la fonction, vérifier les stats post
- `test_fusion_non_pertinent_vers_masquee` — créer 1 entité `non_pertinent`, exécuter migration, vérifier `masquee=True` et statut recalculé

**Classe `Phase8FusionTemplatesTest`** (~3 tests) :
- `test_card_body_mode_lecture_pas_de_commentaires_inline` — render avec mode=lecture, vérifier `commentaires.all` n'est pas itéré
- `test_card_body_mode_drawer_affiche_commentaires_inline` — render avec mode=drawer, vérifier les bulles de commentaires sont présentes
- `test_card_body_les_2_modes_contiennent_btn_commenter` — les 2 modes ont le bouton "Commenter" et la zone déroulable

---

## Ordre d'exécution recommandé

```
Phase 0 — Préparation
  - git status propre, snapshot tests, audit DB

Phase 1 — Modèle + signal (sans toucher l'enum encore)
  - Créer hypostasis_extractor/signals.py
  - Connecter dans apps.py
  - Tests Phase8SignalSynchroniseStatutTest

Phase 2 — Migration data + AlterField
  - 2 fichiers de migration (data puis enum)
  - Application + vérification stats DB

Phase 3 — Retrait action changer_statut + serializer + 4 boutons
  - Retire l'action ViewSet, le serializer, les 4 boutons dans carte_inline.html
  - Retire la logique manuelle ligne 213, 3807-3809 de views.py
  - Retire la sync masquee dans models.py:save()
  - Retire la set non_pertinent dans masquer/restaurer

Phase 4 — Fusion templates _card_body.html paramétré
  - Étendre _card_body.html avec mode + commentaires + bouton commenter
  - Mettre à jour carte_inline.html (with mode="lecture")
  - Mettre à jour drawer_vue_liste.html (with mode="drawer", retirer ~105 lignes)
  - Tests Phase8FusionTemplatesTest

Phase 5 — Dashboard consensus + helper simplifiés
  - Réécrire _calculer_consensus
  - Simplifier dashboard_consensus.html
  - Adapter previsualiser_synthese pour utiliser le nouveau format

Phase 6 — CSS + JS simplifiés
  - 6 paires → 2 paires de variables CSS
  - marginalia.js : matrice 6 cases → 2 cases
  - dashboard_consensus.js : simplification ou suppression

Phase 7 — Templates aide + fixtures
  - Simplifier aide_desktop, aide_mobile, onboarding_vide
  - Adapter charger_fixtures_demo si besoin

Phase 8 — Tests : retrait des morts + ajout des nouveaux
  - Lancer tests, identifier les morts, retirer/adapter
  - Vérifier zéro régression vs snapshot Phase 0

Phase 9 — Vérification anti-régression UI Chrome
  - Page /lire/4/ (cartes inline + drawer)
  - Création commentaire → statut passe à commente, pastille verte
  - Suppression dernier commentaire → statut repasse à nouveau
  - Synthèse → confirmation_synthese.html affiche % commentées
  - Doc CLAUDE.md / CHANGELOG mis à jour
```

---

## Volume net estimé

| Élément | Lignes net |
|---|---|
| Action `changer_statut` + serializer + tests | -90 |
| 4 boutons changer_statut + JS handler | -70 |
| `_calculer_consensus` simplifié | -50 |
| Dashboard consensus simplifié (template + JS) | -120 |
| Migration data + AlterField + signal + apps.py | +60 |
| Fusion `_card_body.html` paramétré (fusion 2 templates) | -150 |
| Drawer commenter ajouté (intégré dans le partial) | +30 |
| CSS variables (6→2 paires) | -30 |
| `marginalia.js` simplifié | -30 |
| Templates aide / onboarding simplifiés | -50 |
| Tests retirés - tests ajoutés | -100 |
| `save()` ExtractedEntity (sync masquee) retirée | -5 |

**Total estimé : ~-600 lignes nettes**

---

## Hors périmètre A.8

À NE PAS toucher :
- **Moteur d'alignement RAG** (Phase B) — la déduction de consensus/controverse riche viendra plus tard
- **Synthèse** (`synthetiser_page_task` + analyseur SYNTHETISER) — conservée intacte, juste son gate `_calculer_consensus` est simplifié
- **Système de commentaires** (`CommentaireExtraction`, ajout/modification/suppression) — intacte ; le signal vit en plus
- **Filtre contributeurs avec dimming** dans le drawer — reste, juste l'affichage des bulles passe par le partial paramétré
- **Champ `masquee`** — devient indépendant du statut mais reste un champ DB normal avec ses actions
- **Versionning de pages** (`parent_page`, `versions_enfants`) — A.7 a déjà nettoyé ça
- **Extension navigateur** — pas concernée

---

## Auto-revue de la spec

- ✅ **Pas de placeholders** : "TBD", "TODO", sections vagues — aucun. Les "00XX" dans les noms de migration sont des marqueurs explicites (numérotation auto par Django à la création).
- ✅ **Cohérence interne** : les décisions Q1-Q4 sont reportées fidèlement dans Architecture/Migration/Tests. Pas de contradiction.
- ✅ **Scope** : single subsystem (statuts + templates + signal). Décomposable en 9 phases mais c'est bien un seul plan d'implémentation cohérent.
- ✅ **Ambiguïté** :
  - L'ordre des migrations data → AlterField est explicitement documenté (data avant AlterField pour éviter rejet).
  - Le pattern `update()` dans le signal vs `save()` est expliqué (évite récursion).
  - Le bouton "Commenter" dans le drawer utilise le **même** pattern JS que la carte inline (toggle hidden + focus textarea), garantissant la cohérence d'UX.
- ✅ **Tests** : périmètre clair (tests à retirer + 3 nouvelles classes Phase8*).
- ✅ **Migration** : 2 fichiers atomiques + ordre critique documenté.

---

## Références

- Spec maître YAGNI : `PLAN/REVUE_YAGNI_2026-05-01.md`
- Plans précédents : A.1 → A.7 (cumul ~12900 lignes net retirées en 7 sessions)
- Cartographie pré-A.8 : conversation Claude Code 2026-05-02 (audit DB + UI Chrome confirmant l'état actuel des statuts)
- Skill suivante (à invoquer pour le plan d'implémentation) : `superpowers:writing-plans`
