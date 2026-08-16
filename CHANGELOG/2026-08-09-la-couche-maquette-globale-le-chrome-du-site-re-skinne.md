# La couche maquette GLOBALE : le chrome du site re-skinne

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** suite de la bascule (decision du proprietaire) — le
design de l'etalon applique au RESTE du site par une couche globale :
- `front/static/front/css/maquette.css`, chargee EN DERNIER dans
  base.html : body Georgia sur papier, barre du haut SOMBRE en
  monospace (le pupitre de l'etalon), arbre lateral et drawers en
  papier-panneau avec filets, re-teinte des utilitaires Tailwind les
  plus porteurs de l'ancien look (bg-white -> papier, text-blue ->
  info, border-slate -> filet, bg-slate -> papier-creux), focus
  visible global, selection ambre.
- STRATEGIE DE COUCHE, pas de reecriture : aucun CSS existant modifie
  (tailwind.css et hypostasia.css intacts — les ~40 classes de
  test_phases qui assertent leur texte restent vertes, 537 tests OK),
  aucun template du reste du site touche. Les ecrans corpus/synthese
  gardent leur design system complet (.zone-corpus).
- collectstatic fait, verifie en navigation reelle (fond papier,
  Georgia, barre sombre calcules par getComputedStyle).
- Verification en cours par 3 agents (visuel Playwright, audit
  statique des couches, accessibilite/regressions) — rapports a
  consigner.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | Nouveau : la couche globale |
| `front/templates/front/base.html` | + le link de la couche (en dernier) |

### Migration
- **Migration necessaire / Migration required :** Non.

