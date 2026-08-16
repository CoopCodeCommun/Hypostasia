# PHASE-25c : Visibilite 3 niveaux + groupes + arbre restructure

**Date :** 2026-03-15
**Migration :** Oui

**Quoi / What:** Systeme de visibilite a 3 niveaux (prive/partage/public) sur les dossiers.
Groupes d'utilisateurs (CRUD) pour faciliter le partage. Arbre restructure en 3 sections
accordeon (Mes dossiers / Partages avec moi / Dossiers publics). Anonymes limites aux dossiers
publics. Controle d'acces lecture/ecriture sur LectureViewSet. Moderation : owner du dossier
peut supprimer les commentaires. Auto-classement des imports dans "Mes imports". Menu contextuel
avec sous-menu visibilite. OOB swaps corriges (centralises via _render_arbre).

**Pourquoi / Why:** Le modele de visibilite PHASE-25 etait binaire (tout ou rien). Pas de
distinction prive/partage/public, pas de groupes, les anonymes voyaient tout.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +VisibiliteDossier, +GroupeUtilisateurs, visibilite sur Dossier, DossierPartage avec groupe+constraints |
| `core/migrations/0022_*.py` | Migration auto |
| `front/views.py` | +3 helpers acces, _render_arbre 3 sections, +changer_visibilite, +quitter, acces LectureViewSet, auto-classify imports, OOB fixes, moderation, DossierViewSet.list filtre |
| `front/views_groupes.py` | **Nouveau** — GroupeViewSet CRUD |
| `front/serializers.py` | +ChangerVisibiliteSerializer, +GroupeCreateSerializer, +GroupeAjouterMembreSerializer |
| `front/urls.py` | +GroupeViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | Rewrite — 3 sections accordeon |
| `front/templates/front/includes/_dossier_node.html` | **Nouveau** — partial reutilisable |
| `front/templates/front/includes/partage_dossier_form.html` | +section groupes |
| `front/static/front/js/arbre_context_menu.js` | +sous-menu visibilite |
| `front/static/front/js/arbre_overlay.js` | +JS accordeon + bouton quitter |
| `front/templates/front/includes/groupe_detail.html` | **Nouveau** — partial template detail groupe |
| `front/tests/test_phases.py` | +23 tests PHASE-25c |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0022_alter_dossierpartage_unique_together_and_more.py`
- Commande : `uv run python manage.py migrate`

