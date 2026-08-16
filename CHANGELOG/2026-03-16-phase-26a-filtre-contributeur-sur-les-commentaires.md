# PHASE-26a : Filtre contributeur sur les commentaires

**Date :** 2026-03-16
**Migration :** Non

**Quoi / What:** Filtre par contributeur dans le drawer vue liste des extractions.
Quand un contributeur est selectionne, seules les extractions qu'il a commentees
apparaissent, les commentaires des autres sont dimmes (opacite reduite), les pastilles
de marge non concernees sont desactivees, et la heat map se recalcule pour ne compter
que les commentaires de ce contributeur.

**Pourquoi / Why:** Le facilitateur a besoin de filtrer par contributeur pour preparer
les reunions de consensus ("qu'est-ce que Michel a dit ?"). Ce filtre se combine avec
la heat map pour visualiser la temperature du debat du point de vue d'un contributeur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | +helper `_calculer_scores_temperature_par_contributeur()`, modifier `drawer_contenu()` (param contributeur, liste contributeurs, HX-Trigger), modifier `retrieve()` (heat map par contributeur) |
| `front/templates/front/includes/drawer_vue_liste.html` | +dropdown contributeur, +classe dimming commentaires |
| `front/static/front/js/drawer_vue_liste.js` | +param contributeur sur `chargerContenu()`, event listener select, heatmap reload |
| `front/static/front/js/marginalia.js` | +listener `contributeurFiltreChange`, filtrage pastilles, API `getContributeurFiltre`/`resetContributeurFiltre` |
| `front/static/front/css/hypostasia.css` | +`.commentaire-hors-filtre`, +`.pastille-hors-filtre` |
| `front/tests/test_phases.py` | +13 tests unitaires PHASE-26a (7 base + 6 UX) |
| `front/tests/e2e/test_17_filtre_contributeur.py` | **NOUVEAU** — 6 tests E2E |
| `front/management/commands/charger_fixtures_demo.py` | +24 commentaires sur pages Wikipedia (Ostrom, Alexandre, Sadin) par 4 contributeurs, dossier "Petits textes" rendu public |

### Ameliorations UX (post-implementation)
1. Icone personne devant le select contributeur (differencie du select de tri)
2. Chip/badge actif "nom x" pour retirer le filtre en un clic
3. Compteur "N sur M" quand filtre actif (ex: "2 sur 78")
4. Highlight du nom du contributeur filtre dans les commentaires (fond bleu + gras)
5. Badge point bleu sur le bouton toolbar Extractions quand filtre actif

