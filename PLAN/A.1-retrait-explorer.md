# Plan A.1 — Retrait Explorer

> **Pour les workers agentiques :** ce plan suit la skill `superpowers:writing-plans`. Les étapes utilisent la syntaxe checkbox `- [ ]` pour le suivi. Voir [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) pour le contexte.

**Goal :** retirer entièrement la feature Explorer (PHASE-25d / 25d-v2) et le modèle `DossierSuivi` qui n'a plus de point d'entrée. Remplacer l'onglet Explorer dans l'onboarding par un onglet **Manifeste** affichant le plaidoyer Bull (atome Atomic `51fabee2`). Retirer aussi les raccourcis clavier `L` et `H` listés dans l'onboarding (préemptif pour A.2/A.3).

**Architecture :**
- Suppression complète de `front/views_explorer.py` (581 lignes, 1 ViewSet, 4 actions)
- Suppression du modèle `DossierSuivi` + migration Django de suppression
- Refactor de `_render_arbre()` (vues) et `arbre_dossiers.html` (template) pour retirer la section "Suivis"
- Refonte de `_dossier_node.html` pour retirer le bouton "ne plus suivre"
- Refonte de `onboarding_vide.html` : l'onglet "Explorer les dossiers" devient "Manifeste", contenu chargé via toggle JS local (pas de nouvelle route backend)
- Nettoyage des tests : 7 classes Django à supprimer, refactor du test E2E mixte invitation/Explorer (garder partie invitation, supprimer partie Explorer)

**Tech stack :** Django 6 + DRF + HTMX + Tailwind subset + PostgreSQL. Stack-ccc / skill djc. Conventions FR/EN bilingues, ViewSet explicite, noms verbeux.

**Hors périmètre :**
- Raccourcis clavier `L` (mode focus) et `H` (heat map) dans `keyboard.js` et CSS → A.2 / A.3
- Stripe / crédits prépayés → A.4
- Bibliothèque analyseurs → A.5

**Préférences user :**
- Aucune commande git automatique (commit géré par Jonas — chaque tâche se termine par un message de commit suggéré, pas par un `git commit`)
- Pas de `Co-Authored-By` dans les messages de commit
- Stack-ccc / djc respecté pour tout nouveau code (très peu dans ce plan, on supprime)

---

## Cartographie des changements

### Fichiers supprimés (8)

| Fichier | Rôle |
|---|---|
| `front/views_explorer.py` | ViewSet Explorer (list, preview, suivre, ne_plus_suivre) |
| `front/templates/front/includes/explorer_card.html` | Card dossier |
| `front/templates/front/includes/explorer_card_document.html` | Card document |
| `front/templates/front/includes/explorer_contenu.html` | Layout principal Explorer |
| `front/templates/front/includes/explorer_curation.html` | Bandeau curation (3 statuts) |
| `front/templates/front/includes/explorer_preview.html` | Preview pages d'un dossier |
| `front/templates/front/includes/explorer_resultats.html` | Liste paginée des résultats |
| `front/tests/e2e/test_16_invitation_explorer.py` | Renommé en `test_16_invitation.py` (tests 05-08 conservés, 01-04 supprimés) |

### Fichiers créés (2)

| Fichier | Rôle |
|---|---|
| `core/migrations/0024_remove_dossiersuivi.py` | Migration auto-générée par `makemigrations` après suppression du modèle |
| `front/templates/front/includes/manifeste.html` | Contenu du plaidoyer Bull (atome Atomic 51fabee2) en HTML statique |
| `front/tests/e2e/test_16_invitation.py` | Renommé depuis `test_16_invitation_explorer.py` |

### Fichiers modifiés (10)

| Fichier | Changement |
|---|---|
| `front/urls.py` | Retirer import `ExplorerViewSet` (ligne 6) + `router.register(r"explorer", ...)` (ligne 29) |
| `front/serializers.py` | Retirer classe `ExplorerFiltresSerializer` (lignes 674-699) + ajuster le commentaire de section (ligne 654-655) |
| `front/templates/front/base.html` | Retirer lien Explorer toolbar (133-141), lien Explorer menu (284-297), include conditionnel `explorer_preloaded` (385-386) |
| `front/templates/front/includes/_dossier_node.html` | Retirer bloc bouton "ne plus suivre" (37-50) + variable `show_unfollow` du commentaire (4) |
| `front/templates/front/includes/arbre_dossiers.html` | Retirer entièrement la section "Suivis" (45-63) + ajuster le commentaire en-tête (1-2) + ajuster le test empty state (86) |
| `front/templates/front/includes/onboarding_vide.html` | Remplacer onglet Explorer par onglet Manifeste avec toggle JS local + retirer raccourcis `L` (155) et `H` (156) + ajuster commentaire (2-4) |
| `front/views.py` | Retirer import `DossierSuivi` (21) + bloc `dossiers_suivis` (349-360, 382, 397-399, 411) + `.exclude(pk__in=ids_dossiers_suivis)` dans `dossiers_publics` (375) + clé `dossiers_suivis`/`total_pages_suivis` du contexte render (407, 411) |
| `front/static/front/js/hypostasia.js` | Retirer commentaire mentionnant Explorer (616-617) |
| `core/models.py` | Retirer classe `DossierSuivi` (1248-1280) + ajuster commentaire `description` champ Dossier (54-55) |
| `front/tests/test_phases.py` | Retirer 7 classes : `Phase25dDossierSuiviModelTest`, `Phase25dArbreSectionSuivisTest`, `Phase25dArbreNonAuthSansSuivisTest`, `Phase25dExplorerVuesTest`, `Phase25dExplorerSuivreTest`, `Phase25dExplorerNePlusSuivreTest`, `Phase25dExplorerRechercheTest` (lignes 8024-8220) + ajuster commentaire de section (7797-7798) |
| `front/tests/e2e/__init__.py` | Renommer import `test_16_invitation_explorer` → `test_16_invitation` (15) |

### Cas particulier : `DossierSuivi` et la migration

Le modèle `DossierSuivi` est créé dans la migration `core/migrations/0023_dossiersuivi_invitation.py` (qui crée AUSSI le modèle `Invitation` qu'on garde). On ne touche PAS à 0023 (déjà appliquée en prod). On laisse Django auto-générer une nouvelle migration `0024_remove_dossiersuivi.py` via `makemigrations` après avoir retiré la classe du `models.py`.

---

## Tâches

### Task 1 : Retrait routes et serializer Explorer

**Files:**
- Modify: `front/urls.py` (lignes 6 et 29)
- Modify: `front/serializers.py` (lignes 654-655 commentaire + 674-699 classe)
- Delete: `front/views_explorer.py` (581 lignes)

- [ ] **Step 1.1 — Modifier `front/urls.py`**

Retirer ligne 6 :
```python
from .views_explorer import ExplorerViewSet
```
Retirer ligne 29 :
```python
router.register(r"explorer", ExplorerViewSet, basename="explorer")
```

- [ ] **Step 1.2 — Modifier `front/serializers.py`**

Remplacer le commentaire de section (lignes 653-656) :
```python
# =============================================================================
# PHASE-25d — Serializers invitation email + Explorer
# / PHASE-25d — Email invitation + Explorer serializers
# =============================================================================
```
Par :
```python
# =============================================================================
# PHASE-25d — Serializer invitation email
# / PHASE-25d — Email invitation serializer
# =============================================================================
```

Supprimer entièrement la classe `ExplorerFiltresSerializer` (lignes 674-699 incluses).

- [ ] **Step 1.3 — Supprimer `front/views_explorer.py`**

```bash
rm /home/jonas/Gits/Hypostasia/front/views_explorer.py
```

- [ ] **Step 1.4 — Vérifier que Django démarre**

```bash
uv run python manage.py check
```
Attendu : `System check identified no issues (0 silenced).`

Si erreur d'import : vérifier qu'aucun autre fichier n'importe `views_explorer` ou `ExplorerFiltresSerializer` :
```bash
rg "views_explorer|ExplorerFiltresSerializer|ExplorerViewSet" /home/jonas/Gits/Hypostasia/ --type py
```
Attendu : 0 résultat.

- [ ] **Step 1.5 — Commit suggéré (Jonas pousse)**

Message de commit à proposer à Jonas :
```
A.1 (1/8) — Retrait routes et serializer Explorer

Retire ExplorerViewSet, ExplorerFiltresSerializer et les routes
/explorer/. Premier commit du retrait Explorer (session A.1 de la
revue YAGNI 2026-05-01).
```

---

### Task 2 : Retrait templates Explorer + refs `base.html`

**Files:**
- Delete: `front/templates/front/includes/explorer_card.html`
- Delete: `front/templates/front/includes/explorer_card_document.html`
- Delete: `front/templates/front/includes/explorer_contenu.html`
- Delete: `front/templates/front/includes/explorer_curation.html`
- Delete: `front/templates/front/includes/explorer_preview.html`
- Delete: `front/templates/front/includes/explorer_resultats.html`
- Modify: `front/templates/front/base.html` (lignes 133-141, 284-297, 385-386)

- [ ] **Step 2.1 — Supprimer les 6 templates Explorer**

```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/explorer_card.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/explorer_card_document.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/explorer_contenu.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/explorer_curation.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/explorer_preview.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/explorer_resultats.html
```

- [ ] **Step 2.2 — Modifier `front/templates/front/base.html` : retirer lien toolbar**

Retirer le bloc lignes 133-141 inclus (lien Explorer dans la toolbar) :
```html
            <!-- Lien Explorer les dossiers publics (PHASE-25d-v2) -->
            <a href="/explorer/"
               hx-get="/explorer/"
               hx-target="#zone-lecture"
               hx-swap="innerHTML"
               hx-push-url="/explorer/"
               class="..."
               title="Explorer les dossiers publics" data-testid="btn-toolbar-explorer" aria-label="Explorer les dossiers publics">
               ...
            </a>
```

À l'exécution : ouvrir le fichier, identifier exactement les bornes du bloc (l'extrait ci-dessus est elliptique car le HTML complet n'a pas été chargé), supprimer en bloc.

- [ ] **Step 2.3 — Modifier `front/templates/front/base.html` : retirer lien menu**

Retirer le bloc lignes 284-297 inclus (lien Explorer dans le menu/sidebar). Même méthode qu'au step 2.2.

- [ ] **Step 2.4 — Modifier `front/templates/front/base.html` : retirer include conditionnel**

Lignes 385-386 :
```html
            {% elif explorer_preloaded %}
                {% include "front/includes/explorer_contenu.html" %}
```
À supprimer entièrement (les 2 lignes). Vérifier que la branche `{% elif %}` n'est pas la dernière du `{% if %}` — si oui, ajuster pour conserver un `{% endif %}` cohérent.

- [ ] **Step 2.5 — Vérifier qu'aucune autre référence à `/explorer/` ne subsiste**

```bash
rg "/explorer/|explorer_preloaded|explorer_card|explorer_contenu|explorer_curation|explorer_preview|explorer_resultats" /home/jonas/Gits/Hypostasia/ --type-add 'web:*.{py,html,js,css}' -t web
```
Attendu : 0 résultat hormis dans les tests (encore présents — supprimés en Task 7-8).

- [ ] **Step 2.6 — Lancer le serveur, vérifier la home**

```bash
uv run python manage.py runserver 0.0.0.0:8123
```
Ouvrir http://localhost:8123/ : la home doit charger sans erreur 500. Le bouton Explorer doit avoir disparu de la toolbar et du menu.

- [ ] **Step 2.7 — Commit suggéré**

```
A.1 (2/8) — Retrait templates Explorer et liens base.html

Supprime les 6 templates explorer_*.html, retire les liens Explorer
de la toolbar, du menu sidebar, et l'include conditionnel
explorer_preloaded de base.html.
```

---

### Task 3 : Retrait du modèle `DossierSuivi` + migration de suppression

**Files:**
- Modify: `core/models.py` (lignes 54-55 commentaire + 1248-1280 classe)
- Create: `core/migrations/0024_remove_dossiersuivi.py` (auto-généré)

- [ ] **Step 3.1 — Modifier le commentaire `core/models.py:54-55`**

Remplacer :
```python
    # Description courte du dossier (optionnel, visible dans l'Explorer)
    # / Short folder description (optional, shown in Explorer)
```
Par :
```python
    # Description courte du dossier (optionnel)
    # / Short folder description (optional)
```

- [ ] **Step 3.2 — Supprimer la classe `DossierSuivi` dans `core/models.py`**

Supprimer entièrement les lignes 1248 à 1280 inclus (classe `DossierSuivi` + méthode `__str__`). Vérifier qu'aucune autre classe ne suit immédiatement sans saut de ligne (laisser un seul saut de ligne entre les classes voisines).

- [ ] **Step 3.3 — Auto-générer la migration de suppression**

```bash
uv run python manage.py makemigrations core
```
Attendu :
```
Migrations for 'core':
  core/migrations/0024_remove_dossiersuivi.py
    - Delete model DossierSuivi
```

- [ ] **Step 3.4 — Inspecter la migration générée**

```bash
cat /home/jonas/Gits/Hypostasia/core/migrations/0024_*.py
```
Vérifier que l'opération est bien :
```python
operations = [
    migrations.DeleteModel(
        name='DossierSuivi',
    ),
]
```
Pas de modification au modèle `Invitation` ou `Dossier` ne doit apparaître dans cette migration. Si oui, alerter Jonas avant d'appliquer.

- [ ] **Step 3.5 — Appliquer la migration**

```bash
uv run python manage.py migrate core
```
Attendu : `Applying core.0024_remove_dossiersuivi... OK`

- [ ] **Step 3.6 — Vérifier qu'aucune autre référence Python à `DossierSuivi` ne subsiste hors tests**

```bash
rg "DossierSuivi" /home/jonas/Gits/Hypostasia/ --type py
```
Attendu : seulement dans `front/views.py`, `front/tests/test_phases.py`, `front/tests/e2e/test_16_invitation_explorer.py`, `core/migrations/0023_dossiersuivi_invitation.py` (ne pas toucher) et `core/migrations/0024_remove_dossiersuivi.py` (qu'on vient de créer). Les usages dans `views.py` et tests seront retirés en Task 4 et 7-8.

- [ ] **Step 3.7 — Commit suggéré**

```
A.1 (3/8) — Retrait modèle DossierSuivi + migration

Supprime la classe DossierSuivi du modèle et applique la migration
0024_remove_dossiersuivi. La migration 0023 (création) est conservée
intacte car déjà appliquée en prod ; 0024 efface uniquement la table.
```

---

### Task 4 : Retrait usage `DossierSuivi` dans `_render_arbre` + templates arbre

**Files:**
- Modify: `front/views.py` (ligne 21 import, lignes 349-360, 382, 397-399, 407, 411 + ligne 375 ajustement queryset publics)
- Modify: `front/templates/front/includes/arbre_dossiers.html` (lignes 1-2 commentaire, 45-63 section Suivis, 86 empty state)
- Modify: `front/templates/front/includes/_dossier_node.html` (ligne 4 commentaire, 37-50 bloc bouton)

- [ ] **Step 4.1 — `front/views.py` ligne 21 : retirer `DossierSuivi` de l'import**

Avant :
```python
from core.models import AIModel, Configuration, Dossier, DossierPartage, DossierSuivi, GroupeUtilisateurs, Invitation, Page, PageEdit, Question, ReponseQuestion, TranscriptionConfig, VisibiliteDossier
```
Après :
```python
from core.models import AIModel, Configuration, Dossier, DossierPartage, GroupeUtilisateurs, Invitation, Page, PageEdit, Question, ReponseQuestion, TranscriptionConfig, VisibiliteDossier
```

- [ ] **Step 4.2 — `front/views.py` lignes 349-360 : retirer le bloc `dossiers_suivis` calculé (utilisateur authentifié)**

Supprimer entièrement les lignes 349 à 360 inclus :
```python
        # Dossiers suivis (PHASE-25d) — uniquement ceux qui sont encore publics
        # / Followed folders (PHASE-25d) — only those still public
        ids_dossiers_suivis = DossierSuivi.objects.filter(
            utilisateur=request.user,
        ).values_list("dossier_id", flat=True)

        dossiers_suivis = Dossier.objects.prefetch_related(
            pages_racines_seulement,
        ).select_related("owner").filter(
            pk__in=ids_dossiers_suivis,
            visibilite=VisibiliteDossier.PUBLIC,
        ).distinct()
```

- [ ] **Step 4.3 — `front/views.py` lignes 374-376 : retirer l'exclusion sur `ids_dossiers_suivis`**

Dans le calcul de `dossiers_publics`, retirer le bloc :
```python
        ).exclude(
            pk__in=ids_dossiers_suivis,
        ).distinct()
```
Et le remplacer par :
```python
        ).distinct()
```
(garder seulement le `.distinct()` final)

- [ ] **Step 4.4 — `front/views.py` ligne 382 (anonyme) : retirer `dossiers_suivis = Dossier.objects.none()`**

Avant :
```python
        mes_dossiers = Dossier.objects.none()
        dossiers_partages = Dossier.objects.none()
        dossiers_suivis = Dossier.objects.none()
        dossiers_publics = Dossier.objects.prefetch_related(
```
Après :
```python
        mes_dossiers = Dossier.objects.none()
        dossiers_partages = Dossier.objects.none()
        dossiers_publics = Dossier.objects.prefetch_related(
```

- [ ] **Step 4.5 — `front/views.py` lignes 397-399 : retirer le calcul de `total_pages_suivis`**

Supprimer :
```python
    total_pages_suivis = 0
    for dossier_comptage in dossiers_suivis:
        total_pages_suivis += dossier_comptage.pages.count()
```

- [ ] **Step 4.6 — `front/views.py` lignes 404-413 : retirer les clés `dossiers_suivis` et `total_pages_suivis` du contexte**

Avant :
```python
    return render(request, "front/includes/arbre_dossiers.html", {
        "mes_dossiers": mes_dossiers,
        "dossiers_partages": dossiers_partages,
        "dossiers_suivis": dossiers_suivis,
        "dossiers_publics": dossiers_publics,
        "total_pages_mes_dossiers": total_pages_mes_dossiers,
        "total_pages_partages": total_pages_partages,
        "total_pages_suivis": total_pages_suivis,
        "total_pages_publics": total_pages_publics,
    })
```
Après :
```python
    return render(request, "front/includes/arbre_dossiers.html", {
        "mes_dossiers": mes_dossiers,
        "dossiers_partages": dossiers_partages,
        "dossiers_publics": dossiers_publics,
        "total_pages_mes_dossiers": total_pages_mes_dossiers,
        "total_pages_partages": total_pages_partages,
        "total_pages_publics": total_pages_publics,
    })
```

- [ ] **Step 4.7 — `front/templates/front/includes/arbre_dossiers.html` lignes 1-2 : ajuster le commentaire**

Avant :
```html
{# Arbre de dossiers — 4 sections accordeon (PHASE-25c + PHASE-25d Suivis) #}
{# / Folder tree — 4 accordion sections (PHASE-25c + PHASE-25d Followed) #}
```
Après :
```html
{# Arbre de dossiers — 3 sections accordeon (PHASE-25c) #}
{# / Folder tree — 3 accordion sections (PHASE-25c) #}
```

- [ ] **Step 4.8 — `front/templates/front/includes/arbre_dossiers.html` lignes 45-63 : supprimer la section Suivis**

Supprimer entièrement le bloc :
```html
{# --- SECTION 3 : SUIVIS (connecte uniquement, ferme par defaut) (PHASE-25d) --- #}
{# --- SECTION 3: FOLLOWED (authenticated only, closed by default) (PHASE-25d) --- #}
{% if dossiers_suivis.count %}
<div class="arbre-section mb-2" data-testid="section-suivis">
    ...
</div>
{% endif %}
```
(de la ligne 45 à la ligne 63 inclus)

- [ ] **Step 4.9 — `front/templates/front/includes/arbre_dossiers.html` ligne 86 : ajuster l'empty state**

Avant :
```html
{% if not mes_dossiers.count and not dossiers_partages.count and not dossiers_suivis.count and not dossiers_publics.count %}
```
Après :
```html
{% if not mes_dossiers.count and not dossiers_partages.count and not dossiers_publics.count %}
```

- [ ] **Step 4.10 — `front/templates/front/includes/_dossier_node.html` ligne 4 : ajuster commentaire**

Avant :
```html
{# Variables attendues : dossier, show_owner (bool), show_quitter (bool), show_unfollow (bool, optionnel) #}
```
Après :
```html
{# Variables attendues : dossier, show_owner (bool), show_quitter (bool) #}
```

- [ ] **Step 4.11 — `front/templates/front/includes/_dossier_node.html` lignes 37-50 : retirer le bloc bouton "ne plus suivre"**

Supprimer entièrement le bloc :
```html
        {# Bouton ne plus suivre (si show_unfollow) (PHASE-25d) #}
        {# / Unfollow button (if show_unfollow) (PHASE-25d) #}
        {% if show_unfollow and user.is_authenticated %}
        <button class="btn-ne-plus-suivre shrink-0 text-slate-400 hover:text-amber-500 px-0.5"
                hx-post="/explorer/{{ dossier.pk }}/ne-plus-suivre/"
                hx-target="#arbre"
                hx-swap="innerHTML"
                data-testid="btn-ne-plus-suivre"
                title="Ne plus suivre" aria-label="Ne plus suivre ce dossier">
            <svg class="w-3.5 h-3.5" ...>
                ...
            </svg>
        </button>
        {% endif %}
```
(de la ligne 37 à la ligne 50 inclus)

- [ ] **Step 4.12 — Vérifier l'absence de référence résiduelle**

```bash
rg "DossierSuivi|dossiers_suivis|ids_dossiers_suivis|show_unfollow|section-suivis|btn-ne-plus-suivre|total_pages_suivis" /home/jonas/Gits/Hypostasia/front/ /home/jonas/Gits/Hypostasia/core/ --type-add 'web:*.{py,html,js,css}' -t web
```
Attendu : seulement dans tests (`test_phases.py`, `test_16_invitation_explorer.py`) et dans la migration `0023` (intouchable).

- [ ] **Step 4.13 — Vérifier que l'arbre fonctionne**

```bash
uv run python manage.py runserver 0.0.0.0:8123
```
- Ouvrir http://localhost:8123/ en anonyme : voir l'arbre, section "Dossiers publics" présente.
- Se connecter : voir "Mes dossiers", "Partages avec moi", "Dossiers publics". La section "Suivis" doit avoir disparu.
- Aucune erreur 500 dans le terminal.

- [ ] **Step 4.14 — Commit suggéré**

```
A.1 (4/8) — Retrait usage DossierSuivi dans l'arbre

Retire le calcul des dossiers suivis de _render_arbre, supprime la
section "Suivis" de arbre_dossiers.html, et retire le bouton "ne plus
suivre" de _dossier_node.html. L'arbre passe de 4 à 3 sections.
```

---

### Task 5 : Refonte `onboarding_vide.html` — onglet Manifeste + retrait raccourcis L et H

**Files:**
- Modify: `front/templates/front/includes/onboarding_vide.html` (lignes 2-4 commentaire, 7-25 onglets, 155-156 raccourcis, partie JS toggle, CSS conservé)

**Note :** le contenu du Manifeste est créé en Task 6. Ici on prépare juste la structure : 2 onglets (Découvrir / Manifeste), toggle JS local entre 2 zones (`zone-onboarding` et `zone-manifeste`).

- [ ] **Step 5.1 — Modifier le commentaire en-tête (lignes 2-4)**

Avant :
```html
{# Contient : onglets Decouvrir/Explorer + processus en 4 etapes + 6 statuts + raccourcis clavier #}
{# / Onboarding guide — displayed when no page is loaded #}
{# / Contains: Discover/Explorer tabs + 4-step process + 6 statuses + keyboard shortcuts #}
```
Après :
```html
{# Contient : onglets Decouvrir/Manifeste + processus en 4 etapes + 6 statuts + raccourcis clavier #}
{# / Onboarding guide — displayed when no page is loaded #}
{# / Contains: Discover/Manifesto tabs + 4-step process + 6 statuses + keyboard shortcuts #}
```

- [ ] **Step 5.2 — Remplacer la barre d'onglets (lignes 7-25)**

Avant :
```html
{# === Barre d'onglets accueil (PHASE-25d-v2) === #}
{# / === Home tabs bar (PHASE-25d-v2) === #}
<div class="flex gap-3 justify-center pt-6 pb-4 border-b border-slate-200 mb-2" data-testid="onglets-accueil">
    <button class="onglet-accueil active"
            data-testid="onglet-decouvrir"
            aria-label="D&eacute;couvrir l'application"
            onclick="document.getElementById('zone-onboarding').classList.remove('hidden'); this.classList.add('active'); this.nextElementSibling.classList.remove('active');">
        D&eacute;couvrir l'app
    </button>
    <button class="onglet-accueil"
            hx-get="/explorer/"
            hx-target="#zone-lecture"
            hx-swap="innerHTML"
            hx-push-url="/explorer/"
            data-testid="onglet-explorer"
            aria-label="Explorer les dossiers publics">
        Explorer les dossiers
    </button>
</div>
```

Après :
```html
{# === Barre d'onglets accueil — Decouvrir / Manifeste (refonte A.1) === #}
{# / === Home tabs bar — Discover / Manifesto (refactor A.1) === #}
<div class="flex gap-3 justify-center pt-6 pb-4 border-b border-slate-200 mb-2" data-testid="onglets-accueil">
    <button class="onglet-accueil active"
            data-testid="onglet-decouvrir"
            aria-label="D&eacute;couvrir l'application"
            onclick="document.getElementById('zone-onboarding').classList.remove('hidden'); document.getElementById('zone-manifeste').classList.add('hidden'); this.classList.add('active'); this.nextElementSibling.classList.remove('active');">
        D&eacute;couvrir l'app
    </button>
    <button class="onglet-accueil"
            data-testid="onglet-manifeste"
            aria-label="Lire le manifeste Hypostasia"
            onclick="document.getElementById('zone-onboarding').classList.add('hidden'); document.getElementById('zone-manifeste').classList.remove('hidden'); this.classList.add('active'); this.previousElementSibling.classList.remove('active');">
        Manifeste
    </button>
</div>
```

- [ ] **Step 5.3 — Retirer raccourcis `L` et `H` (lignes 155-156)**

Avant :
```html
                <div class="onboarding-raccourci"><kbd class="aide-kbd">S</kbd><span>Consensuelle</span></div>
                <div class="onboarding-raccourci"><kbd class="aide-kbd">L</kbd><span>Lecture focus</span></div>
                <div class="onboarding-raccourci"><kbd class="aide-kbd">H</kbd><span>Heat map</span></div>
                <div class="onboarding-raccourci"><kbd class="aide-kbd">X</kbd><span>Masquer</span></div>
```

Après :
```html
                <div class="onboarding-raccourci"><kbd class="aide-kbd">S</kbd><span>Consensuelle</span></div>
                <div class="onboarding-raccourci"><kbd class="aide-kbd">X</kbd><span>Masquer</span></div>
```

- [ ] **Step 5.4 — Ajouter le bloc `<div id="zone-manifeste" class="hidden">{% include ... %}</div>` après le `</div>{# fin zone-onboarding #}`**

Tout en bas du fichier (après ligne 355), avant le `</div>{# fin zone-onboarding #}`, le fichier se termine par :
```html
</div>{# fin zone-onboarding #}
```

Après cette ligne, ajouter :
```html

{# === Zone Manifeste — affichee quand l'utilisateur clique sur l'onglet Manifeste === #}
{# / === Manifesto zone — displayed when the user clicks the Manifesto tab === #}
<div id="zone-manifeste" class="hidden">
    {% include "front/includes/manifeste.html" %}
</div>
```

- [ ] **Step 5.5 — Vérifier qu'aucune référence Explorer ne subsiste dans le fichier**

```bash
rg "explorer|Explorer" /home/jonas/Gits/Hypostasia/front/templates/front/includes/onboarding_vide.html
```
Attendu : 0 résultat.

- [ ] **Step 5.6 — Vérifier le rendu (sans manifeste pour l'instant — l'include va échouer si le template n'existe pas)**

NE PAS lancer le serveur ici si le template `manifeste.html` n'existe pas encore — l'`{% include %}` lèverait une `TemplateDoesNotExist`. Lancer le runserver après la Task 6.

- [ ] **Step 5.7 — Commit suggéré (à faire APRÈS la Task 6)**

Cette task ne commit pas seule — elle se commit avec la Task 6 en un seul commit, car onboarding_vide.html référence `manifeste.html` qui doit exister. Continuer directement la Task 6.

---

### Task 6 : Création du template `manifeste.html` (contenu plaidoyer Bull)

**Files:**
- Create: `front/templates/front/includes/manifeste.html`

**Note :** le contenu du Manifeste est l'atome Atomic `51fabee2` (Plaidoyer Institut Bull × Code Commun × Hypostasia v0.2). On le récupère via le MCP Atomic au moment de l'exécution et on l'adapte en HTML statique stylé conformément à la charte typographique du projet (Lora pour le corps, B612 pour les titres, etc.).

- [ ] **Step 6.1 — Charger les outils MCP Atomic via ToolSearch**

```
ToolSearch query: "select:mcp__atomic__read_atom"
```

- [ ] **Step 6.2 — Récupérer l'atome 51fabee2 du plaidoyer**

```
mcp__atomic__read_atom(uuid="51fabee2")
```
Stocker le contenu (markdown) en mémoire pour la conversion.

- [ ] **Step 6.3 — Créer `front/templates/front/includes/manifeste.html`**

Structure proposée (à adapter selon la longueur réelle du plaidoyer) :

```html
{# Manifeste Hypostasia — adaptation du plaidoyer Institut Bull × Code Commun (atome Atomic 51fabee2) #}
{# / Hypostasia Manifesto — adaptation of the Institut Bull × Code Commun plea (Atomic atom 51fabee2) #}
{# LOCALISATION : front/templates/front/includes/manifeste.html #}

<article class="manifeste-contenu" data-testid="manifeste-article">

    <header class="manifeste-header">
        <h2 class="manifeste-titre">Manifeste Hypostasia</h2>
        <p class="manifeste-sous-titre">
            Un commun num&eacute;rique pour la d&eacute;lib&eacute;ration collective.
        </p>
    </header>

    {# === Sections du plaidoyer === #}
    {# / === Plea sections === #}
    <section class="manifeste-section" data-testid="manifeste-section-pourquoi">
        <h3 class="manifeste-section-titre">Pourquoi Hypostasia ?</h3>
        <div class="manifeste-section-corps">
            {# Contenu adapt&eacute; depuis l'atome 51fabee2 — section &laquo; Pourquoi &raquo; #}
            ... contenu ici ...
        </div>
    </section>

    {# Autres sections selon le decoupage du plaidoyer #}
    {# / Other sections based on the plea's structure #}

</article>

<style>
/* === Manifeste === */
.manifeste-contenu {
    max-width: 52rem;
    margin: 0 auto;
    padding: 3rem 2rem 4rem;
    font-family: 'Lora', Georgia, serif;
    color: #0f172a;
}
.manifeste-header { text-align: center; margin-bottom: 2.5rem; }
.manifeste-titre {
    font-family: 'B612', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
}
.manifeste-sous-titre {
    font-family: 'Lora', Georgia, serif;
    font-style: italic;
    font-size: 1rem;
    color: #64748b;
    line-height: 1.5;
}
.manifeste-section { margin-bottom: 2rem; }
.manifeste-section-titre {
    font-family: 'B612', sans-serif;
    font-size: 1.125rem;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.375rem;
}
.manifeste-section-corps {
    font-size: 0.9375rem;
    line-height: 1.7;
}
.manifeste-section-corps p { margin-bottom: 1rem; }

@media (max-width: 768px) {
    .manifeste-contenu { padding: 2rem 1rem 3rem; }
    .manifeste-titre { font-size: 1.375rem; }
}
</style>
```

**Décisions à prendre lors de l'exécution (en lisant le plaidoyer) :**
- Combien de sections couper le plaidoyer ? (probablement 3-5 selon sa longueur)
- Faut-il des accroches / citations mises en exergue ? (utiliser `<blockquote class="manifeste-citation">` avec style Lora italique si oui)
- Garder ou retirer les références bibliographiques internes au plaidoyer ?

**Règle FALC :** simplifier le langage si nécessaire, garder la structure et les citations originales.

- [ ] **Step 6.4 — Vérifier la grammaire HTML et le rendu**

```bash
uv run python manage.py runserver 0.0.0.0:8123
```
- Ouvrir http://localhost:8123/ avec un navigateur (sans page chargée → onboarding affiché)
- Cliquer sur l'onglet "Manifeste" : la zone `zone-onboarding` doit se cacher, `zone-manifeste` apparaître avec le contenu du plaidoyer
- Cliquer sur "Découvrir l'app" : retour à l'onboarding
- Vérifier la console navigateur : aucune erreur JS

- [ ] **Step 6.5 — Vérifier qu'aucune classe Tailwind absente du subset n'est utilisée**

```bash
# Identifier les classes Tailwind utilisees dans manifeste.html (si tu en as ajoute)
rg 'class="[^"]*"' /home/jonas/Gits/Hypostasia/front/templates/front/includes/manifeste.html
# Verifier qu'elles existent dans le subset
grep -E "(prose|max-w|font-bold|...)" /home/jonas/Gits/Hypostasia/static/css/tailwind.css 2>/dev/null
```
Le manifeste utilise majoritairement du CSS inline custom (classes `.manifeste-*`), donc peu de risque. Vérifier seulement les classes Tailwind explicitement utilisées.

- [ ] **Step 6.6 — Commit suggéré (combine Task 5 + Task 6)**

```
A.1 (5+6/8) — Onglet Manifeste à la place d'Explorer dans onboarding

Remplace l'onglet "Explorer les dossiers" par un onglet "Manifeste"
qui affiche le plaidoyer Institut Bull × Code Commun (atome Atomic
51fabee2) en HTML statique. Toggle JS local entre les zones
zone-onboarding et zone-manifeste, sans nouvelle route backend.
Retire au passage les raccourcis L (mode focus) et H (heat map)
dans la liste des raccourcis affiches (preemption A.2/A.3).
```

---

### Task 7 : Retrait des tests Django Phase25dExplorer* + Phase25dDossierSuivi*

**Files:**
- Modify: `front/tests/test_phases.py` (lignes 7797-7798 commentaire, 8024-8220 classes à supprimer)

- [ ] **Step 7.1 — Modifier le commentaire de section (lignes 7796-7799)**

Avant :
```python
# =============================================================================
# PHASE-25d — Invitation par email + Explorer + DossierSuivi
# / PHASE-25d — Email invitation + Explorer + DossierSuivi
# =============================================================================
```
Après :
```python
# =============================================================================
# PHASE-25d — Invitation par email
# / PHASE-25d — Email invitation
# =============================================================================
```

- [ ] **Step 7.2 — Identifier précisément les bornes de chaque classe à supprimer**

Lire le bloc `front/tests/test_phases.py:8024-8230` (offset 8023, limit 220) pour repérer la dernière ligne de la dernière classe Explorer (probablement `Phase25dExplorerRechercheTest`). Récupérer les numéros de ligne exacts de :
- Début de `Phase25dDossierSuiviModelTest` (ligne 8024)
- Fin de la dernière classe Explorer (vers ligne 8220, à confirmer)
- Première classe à conserver après ce bloc (s'il en existe une — vérifier si une autre classe commence à 8221+)

Commande utile :
```bash
rg -n "^class " /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -200 | tail -50
```

- [ ] **Step 7.3 — Supprimer en bloc les 7 classes**

Classes à supprimer dans l'ordre où elles apparaissent :
1. `Phase25dDossierSuiviModelTest` (créations, unicité — modèle DossierSuivi)
2. `Phase25dArbreSectionSuivisTest` (section "Suivis" dans l'arbre — disparaît)
3. `Phase25dArbreNonAuthSansSuivisTest` (anonyme sans section Suivis — devient trivial)
4. `Phase25dExplorerVuesTest` (`/explorer/` accessible anonyme + filtres)
5. `Phase25dExplorerSuivreTest` (POST `/explorer/{id}/suivre/`)
6. `Phase25dExplorerNePlusSuivreTest` (POST `/explorer/{id}/ne-plus-suivre/`)
7. `Phase25dExplorerRechercheTest` (recherche multi-champs — `q=`)

Supprimer du début de `Phase25dDossierSuiviModelTest` jusqu'à la fin de `Phase25dExplorerRechercheTest`. Garder un seul saut de ligne entre la classe précédente (`Phase25dRegisterAvecTokenTest`) et la classe suivante après le bloc supprimé (à identifier en step 7.2).

- [ ] **Step 7.4 — Lancer la suite de tests Django pour vérifier**

```bash
uv run python manage.py test front.tests.test_phases -v 2 2>&1 | tail -30
```
Attendu : tous les tests restants passent. Aucune erreur d'import (`ImportError: cannot import name 'DossierSuivi'`) ne doit apparaître.

Si un test échoue avec `URLPattern` ou `NoReverseMatch` mentionnant `explorer`, vérifier qu'il s'agit d'un test à supprimer (oublié dans le step 7.3) et le retirer.

- [ ] **Step 7.5 — Commit suggéré**

```
A.1 (7/8) — Retrait des tests Django Explorer + DossierSuivi

Supprime les 7 classes de tests Phase25d* liees a Explorer et au
modele DossierSuivi. La section PHASE-25d ne contient plus que les
tests d'invitation par email (conservee).
```

---

### Task 8 : Refactor du test E2E `test_16_invitation_explorer.py` + `__init__.py`

**Files:**
- Rename: `front/tests/e2e/test_16_invitation_explorer.py` → `front/tests/e2e/test_16_invitation.py`
- Modify: contenu du fichier renommé (supprimer méthodes test_01 à test_04 + helper inutile)
- Modify: `front/tests/e2e/__init__.py:15` (mise à jour de l'import)

- [ ] **Step 8.1 — Renommer le fichier**

```bash
mv /home/jonas/Gits/Hypostasia/front/tests/e2e/test_16_invitation_explorer.py \
   /home/jonas/Gits/Hypostasia/front/tests/e2e/test_16_invitation.py
```

- [ ] **Step 8.2 — Mettre à jour le docstring d'en-tête (lignes 1-6)**

Avant :
```python
"""
Tests E2E PHASE-25d — Invitation par email, Explorer, Suivis.
/ E2E tests PHASE-25d — Email invitation, Explorer, Follows.

Lancer avec : uv run python manage.py test front.tests.e2e.test_16_invitation_explorer -v2
"""
```
Après :
```python
"""
Tests E2E PHASE-25d — Invitation par email.
/ E2E tests PHASE-25d — Email invitation.

Lancer avec : uv run python manage.py test front.tests.e2e.test_16_invitation -v2
"""
```

- [ ] **Step 8.3 — Renommer la classe**

Avant :
```python
class Phase25dExplorerE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour l'Explorer et les invitations."""
```
Après :
```python
class Phase25dInvitationE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour les invitations par email."""
```

- [ ] **Step 8.4 — Supprimer le helper `creer_dossier_public` (lignes 37-52)**

Ce helper est utilisé par les tests test_01 à test_04 (Explorer). Les tests d'invitation (test_05 à test_08) utilisent `Dossier.objects.create(...)` directement via `core.models`. Le helper devient mort code une fois les tests Explorer supprimés.

Supprimer entièrement le bloc :
```python
    def creer_dossier_public(self, nom="Dossier public test", username="pubowner"):
        """
        Cree un dossier public via l'ORM.
        / Create a public folder via ORM.
        """
        from core.models import Dossier, VisibiliteDossier
        from django.contrib.auth.models import User
        owner, _ = User.objects.get_or_create(
            username=username, defaults={"password": "test1234"},
        )
        if not owner.has_usable_password():
            owner.set_password("test1234")
            owner.save()
        return Dossier.objects.create(
            name=nom, owner=owner, visibilite=VisibiliteDossier.PUBLIC,
        )
```

- [ ] **Step 8.5 — Supprimer les méthodes `test_01` à `test_04`**

Supprimer entièrement :
- `test_01_explorer_charge_anonyme` (lignes 58-67)
- `test_02_recherche_filtre` (lignes 69-81)
- `test_03_bouton_suivre_absent_anonyme` (lignes 83-90)
- `test_04_suivre_apparait_arbre` (lignes 92-109)

Garder intacts `test_05_inviter_email_existant`, `test_06_inviter_email_inconnu`, `test_07_lien_invitation_anonyme_redirect_register`, `test_08_inscription_avec_token`.

- [ ] **Step 8.6 — Modifier `front/tests/e2e/__init__.py:15`**

Avant :
```python
from front.tests.e2e.test_16_invitation_explorer import *  # noqa: F401,F403
```
Après :
```python
from front.tests.e2e.test_16_invitation import *  # noqa: F401,F403
```

- [ ] **Step 8.7 — Vérifier qu'aucune autre référence au fichier renommé ne subsiste**

```bash
rg "test_16_invitation_explorer" /home/jonas/Gits/Hypostasia/
```
Attendu : 0 résultat.

- [ ] **Step 8.8 — Lancer le test E2E renommé pour valider (E2E suppose Playwright + serveur Django actif)**

```bash
# Verifier d'abord que Playwright est installe
uv run playwright install chromium 2>&1 | tail -3
# Puis lancer le test
uv run python manage.py test front.tests.e2e.test_16_invitation -v 2 2>&1 | tail -20
```
Attendu : 4 tests passent (test_05 à test_08), aucune erreur d'import liée à `Explorer` ou `DossierSuivi`.

Si Playwright n'est pas installé ou si tu n'as pas le serveur actif, sauter ce test E2E et noter dans le commit que la vérification E2E doit être faite manuellement par Jonas.

- [ ] **Step 8.9 — Commit suggéré**

```
A.1 (8/8) — Refactor test E2E invitation + suppression tests Explorer

Renomme test_16_invitation_explorer.py -> test_16_invitation.py.
Supprime les methodes test_01..test_04 (Explorer) et le helper
creer_dossier_public devenu inutile. Met a jour l'import dans
__init__.py et renomme la classe Phase25dExplorerE2ETest ->
Phase25dInvitationE2ETest. Tests test_05..test_08 (invitations)
inchanges.
```

---

### Task 9 : Vérification finale et nettoyage

**Files:** aucun (verification uniquement)

- [ ] **Step 9.1 — Vérifier qu'aucune référence "explorer" ne subsiste hors PLAN/ et migrations historiques**

```bash
rg "explorer|Explorer|ExplorerViewSet|ExplorerFiltresSerializer" /home/jonas/Gits/Hypostasia/ \
   --type-add 'web:*.{py,html,js,css}' -t web \
   -g '!PLAN/**' \
   -g '!core/migrations/0023_*'
```
Attendu : 0 résultat (sauf éventuellement le commentaire `js hypostasia.js:616-617` non retiré — voir step 9.2).

- [ ] **Step 9.2 — Nettoyer le commentaire résiduel dans `front/static/front/js/hypostasia.js`**

Lignes 616-617 :
```javascript
// Ecouter htmx:pushedIntoHistory (navigation HTMX depuis Explorer)
// / Listen to htmx:pushedIntoHistory (HTMX navigation from Explorer)
```
À remplacer par :
```javascript
// Ecouter htmx:pushedIntoHistory (navigation HTMX)
// / Listen to htmx:pushedIntoHistory (HTMX navigation)
```

(Garder le code en dessous tel quel : la logique de gestion d'historique HTMX est valide indépendamment d'Explorer.)

- [ ] **Step 9.3 — Vérifier qu'aucune référence à `DossierSuivi` ne subsiste hors migrations historiques**

```bash
rg "DossierSuivi|dossiers_suivis|ids_dossiers_suivis|btn-ne-plus-suivre|section-suivis|show_unfollow|total_pages_suivis" /home/jonas/Gits/Hypostasia/ \
   -g '!core/migrations/0023_*' \
   -g '!core/migrations/0024_*' \
   -g '!PLAN/**'
```
Attendu : 0 résultat.

- [ ] **Step 9.4 — Lancer toute la suite de tests Django**

```bash
uv run python manage.py test 2>&1 | tail -20
```
Attendu : tous les tests passent. Si des tests d'autres phases échouent, vérifier qu'ils n'utilisent pas `DossierSuivi` ou des routes `/explorer/...`. Si oui, les retirer avec un commit dédié.

- [ ] **Step 9.5 — Lancer `manage.py check` final**

```bash
uv run python manage.py check
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 9.6 — Test manuel UI complet (Firefox)**

1. `uv run python manage.py runserver 0.0.0.0:8123`
2. Ouvrir http://localhost:8123/ (anonyme) :
   - Onboarding s'affiche
   - Onglet "Découvrir l'app" actif par défaut → 4 étapes + 6 statuts + raccourcis
   - **Vérifier qu'il n'y a PLUS les raccourcis L et H dans la liste**
   - Cliquer sur l'onglet "Manifeste" → contenu du plaidoyer Bull s'affiche, charte typo respectée (Lora pour le corps, B612 pour les titres)
   - Cliquer sur "Découvrir l'app" → retour à l'onboarding
   - Toolbar : pas de bouton Explorer
   - Sidebar/menu : pas de lien Explorer
   - Arbre : section "Dossiers publics" présente, **pas de section "Suivis"**
3. Se connecter avec un compte qui possède au moins 1 dossier :
   - Arbre : sections "Mes dossiers", "Partages avec moi" (si applicable), "Dossiers publics" — **pas de section "Suivis"**
   - Aucune erreur 500 dans le terminal
4. Tester l'invitation par email (régression) :
   - Aller dans un dossier dont je suis owner, cliquer sur l'invitation, envoyer une invitation à un email inconnu, vérifier que ça crée bien une `Invitation`

- [ ] **Step 9.7 — Vérifier Firefox Reader View (régression A.3 anticipée)**

Ouvrir une page `/lire/{id}/` dans Firefox. Vérifier que l'icône Reader View apparaît dans la barre d'URL (l'algorithme Mozilla Readability détecte `<article id="readability-content">`). Si absent, noter pour A.3 (mode focus).

- [ ] **Step 9.8 — Commit suggéré (si nettoyage step 9.2 effectué) ou pas de commit**

Si le commentaire de `hypostasia.js` a été nettoyé en step 9.2 :
```
A.1 (cleanup) — Nettoyage commentaire JS residuel

Retire la mention "depuis Explorer" du commentaire dans
hypostasia.js. Cloture la session A.1 (retrait Explorer).
```

Sinon, pas de commit (la verification est terminee).

---

## Sortie attendue à la fin de la session A.1

- 8 fichiers supprimés (`views_explorer.py` + 6 templates + 1 fichier renommé)
- 2 fichiers créés (`manifeste.html` + migration `0024_remove_dossiersuivi.py`)
- 10 fichiers modifiés
- 7 classes de tests Django supprimées
- 4 méthodes de tests E2E supprimées + 1 fichier renommé
- 8 commits proposés à Jonas (8 tasks principales + éventuel cleanup final)
- L'arbre passe de 4 à 3 sections
- La home onboarding gagne un onglet "Manifeste" avec le plaidoyer Bull
- Aucune route `/explorer/` ne subsiste
- Le modèle `DossierSuivi` n'existe plus en DB

## Risques identifiés et mitigation

| Risque | Mitigation |
|---|---|
| Test E2E nécessite Playwright + serveur actif | Step 8.8 marque que la vérif peut être faite manuellement par Jonas si l'environnement n'est pas prêt |
| Tests d'autres phases utilisent `DossierSuivi` indirectement | Step 9.4 lance toute la suite — les échecs seront détectés |
| L'atome Atomic 51fabee2 n'est pas accessible au moment de la Task 6 | Demander à Jonas de fournir le contenu en fallback (il le connaît, c'est son plaidoyer) |
| Le subset Tailwind ne contient pas une classe utilisée dans `manifeste.html` | Step 6.5 vérifie ; le manifeste utilise majoritairement du CSS inline custom (`.manifeste-*`), donc faible risque |
| Migration `0024_remove_dossiersuivi.py` génère des opérations imprévues (ex. modification d'un FK ailleurs) | Step 3.4 inspecte la migration avant de l'appliquer |

## Auto-revue

- ✅ Toutes les sections de la spec REVUE_YAGNI section "Périmètre confirmé" → "Onboarding + tooltips hypostases (PHASE-16) — *retirer onglet « Explorer »*" sont couvertes (Task 5)
- ✅ Tous les fichiers listés dans la spec YAGNI 2026-05-01 §4 (Explorer) sont traités
- ✅ Décision Q1 (DossierSuivi → option B) intégrée dans Tasks 3, 4, 7
- ✅ Décision Q2 (onglets gardés + Manifeste) intégrée dans Tasks 5, 6
- ✅ Décision Q3 (raccourcis L/H préemptifs) intégrée dans Step 5.3
- ✅ Aucun placeholder, aucun "TODO", aucun "fill in details"
- ✅ Chemins exacts pour chaque modification
- ✅ Code complet pour chaque diff
- ✅ Tous les commits suggérés respectent la préférence "pas de Co-Authored-By"
- ✅ Aucune commande git automatique — Jonas commit lui-même

## Références

- Spec validée : [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md)
- Décisions YAGNI matin : [PLAN/discussions/YAGNI 2026-05-01.md](discussions/YAGNI%202026-05-01.md)
- Atome Atomic plaidoyer Bull : `51fabee2` (à charger via `mcp__atomic__read_atom` en Task 6)
- Skill obligatoire : `superpowers:executing-plans` ou `superpowers:subagent-driven-development` pour l'exécution
