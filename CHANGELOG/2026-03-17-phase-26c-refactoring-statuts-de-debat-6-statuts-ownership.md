# PHASE-26c : Refactoring statuts de debat (6 statuts + ownership)

**Date :** 2026-03-17
**Migration :** Oui

**Quoi / What:** Refactoring du systeme de statuts de debat : passage de 4 a 6 statuts, ajout du controle d'ownership, suppression du double badge, integration de "masquer" dans le cycle deliberatif.

**Pourquoi / Why:** 3 problemes UX identifies : toutes les extractions demarraient en rouge (alarmant), n'importe quel user pouvait changer le statut, et "masquer" etait deconnecte du cycle deliberatif.

### Changements principaux / Main changes

1. **6 statuts** : nouveau (gris), discutable (orange), discute (ambre), consensuel (vert), controverse (rouge), non_pertinent (gris pale)
2. **Ownership** : seul le proprietaire du dossier peut changer statut, masquer, restaurer
3. **Non pertinent** remplace le boolean `masquee` (synchronise via `save()`)
4. **Double badge supprime** : le `_card_body.html` n'affiche plus le statut en doublon
5. **Auto-promotion** : commentaire sur nouveau/discutable → discute
6. **Dashboard 6 compteurs** : grille 3x2, non_pertinent exclu du calcul de consensus

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | +2 choices, default→nouveau, save() sync masquee |
| `hypostasis_extractor/migrations/0021_*.py` | AlterField + RunPython data migration |
| `front/views.py` | Helper _est_proprietaire_dossier, ownership checks, est_proprietaire contexte |
| `front/serializers.py` | +2 choices ChangerStatutSerializer |
| `front/static/front/css/hypostasia.css` | 6 couleurs statut, discutable rouge→orange |
| `front/static/front/js/marginalia.js` | +2 entrees COULEURS_STATUT |
| `front/static/front/js/keyboard.js` | Check ownership avant raccourci S |
| `front/templates/.../carte_inline.html` | Boutons owner-only, +discutable, +non_pertinent |
| `front/templates/.../_card_body.html` | Suppression double badge statut |
| `front/templates/.../drawer_vue_liste.html` | Masquer/restaurer owner-only, "Non pertinentes" |
| `front/templates/.../dashboard_consensus.html` | Grille 3x2, 6 compteurs |
| `front/templates/front/base.html` | data-est-proprietaire sur #zone-lecture |
| `hypostasis_extractor/templatetags/extractor_tags.py` | +2 icones statut |
| `front/tests/test_phases.py` | ~17 updates + 5 nouvelles classes test |
| `front/management/commands/charger_fixtures_demo.py` | Redistribution 6 statuts |

### Migration
- **Migration necessaire / Migration required:** Oui — `hypostasis_extractor/migrations/0021_refactoring_statuts_debat.py`
- `uv run python manage.py migrate`

