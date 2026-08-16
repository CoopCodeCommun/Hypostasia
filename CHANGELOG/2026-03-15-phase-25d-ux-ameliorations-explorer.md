# PHASE-25d UX : Ameliorations Explorer

**Date :** 2026-03-15
**Migration :** Oui

**Quoi / What:** 7 ameliorations UX sur l'Explorer et le systeme d'invitation :
1. Description optionnelle sur les dossiers (champ `description` 200 chars)
2. Compteur de suivis affiche en ambre sur les cards ("3 suivis")
3. Bouton Explorer (globe) ajoute dans la toolbar principale desktop
4. Toasts de confirmation sur Suivre/Ne plus suivre/Inviter
5. Selecteur tri (Plus recents / Plus suivis / Alphabetique)
6. Preview des 3 premiers titres de pages en badges gris dans les cards
7. Fix bug dropdown auteur duplique (Meta.ordering polluait DISTINCT)

**Pourquoi / Why:** Les cards etaient trop minimales (nom + date), l'Explorer
pas assez decouvrable (cache dans le footer de l'arbre uniquement), et pas de
feedback apres les actions Suivre/Inviter.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +champ `description` sur Dossier |
| `core/migrations/0024_dossier_description.py` | Migration auto |
| `front/serializers.py` | +champ `tri` dans ExplorerFiltresSerializer |
| `front/views_explorer.py` | +annotate nombre_suivis, +tri (populaire/nom/recent), +preview pages, +toasts HX-Trigger, fix DISTINCT |
| `front/views.py` | +toast sur action inviter |
| `front/templates/front/includes/explorer_page.html` | +select tri, +listener toast SweetAlert |
| `front/templates/front/includes/explorer_card.html` | +description, +compteur suivis ambre, +preview pages badges |
| `front/templates/front/base.html` | +bouton globe Explorer dans toolbar |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0024_dossier_description.py`
- Commande : `uv run python manage.py migrate`

