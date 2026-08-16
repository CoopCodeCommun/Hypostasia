# Bascule CSS v2 : les correctifs des trois audits

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** trois agents (visuel Playwright, audit statique,
audit accessibilite avec ratios calcules) ont confronte le re-skin ;
TOUS les bloquants corriges le soir meme :
- **Chrome repare** : les menus deroulants de la barre (utilisateur,
  taches) etaient BLANC SUR BLANC (1,59:1) — regles nav.h-12
  restreintes aux enfants directs, panneaux en papier/encre ; nom
  d'utilisateur lisible ; focus PAPIER sur la barre sombre (2,18 ->
  16,79:1) ; 4 etats du bouton taches lisibles ; separateur re-teinte.
- **Source unique des tokens** (le :root de _style_maquette retire) +
  REMAPPAGE des ~50 tokens de hypostasia.css vers la palette papier —
  surfaces blanches, textes slate et halo d'ancre bleu (desormais
  AMBRE) suivent d'un coup.
- **Accueil onboarding** re-skinne (etait reste entier a l'ancien
  design, 4 contrastes < 2,6) ; **corps de lecture en Georgia/encre**
  (decision D1 : Lora quitte le corps, la maquette fait foi) ;
  **surlignages d'extraction recolores** (les statuts riches
  controverse/consensuel/discutable restes en base n'avaient PLUS
  AUCUNE couleur — bug pre-existant repare : vert/rouge/ambre legers).
- **Semantique des messages** : ambre/vert/info/danger re-teintes DANS
  leur teinte (plus jamais fusionnes en beige), bordures assorties,
  bg-red-50 et bg-amber-50/30 couverts.
- **Accessibilite** : teintes Wong plus jamais en texte (1,29:1 !) —
  contour + fond 18 % + encre ; soulignements de verdicts >= 3:1 ;
  cibles boutons d'ordre/renvois elargies ; focus visible des
  puces-filtres ; panneau de preuve ferme NON tabulable + role dialog
  + focus donne a l'ouverture + Escape conditionne (ne vole plus le
  focus) ; reduced-motion GLOBAL (46 animations de hypostasia.css
  comprises) ; noscript des filtres fonctionnel (method/action).
- **Acces direct** : /wikis/{id}/ et /syntheses/{id}/ rendent la page
  COMPLETE hors HTMX (branche article_preloaded), les collections
  carnet redirigent — plus de fragments nus en Times New Roman.
- Arbre/drawers : monospace etalon, boutons/etats actifs en
  papier/ambre (plus d'indigo) ; bottom-sheet papier.

Verifie en navigation reelle apres redeploiement. Lots restants et
restes a11y consignes dans PLAN/bascule-css-etat-2026-08-09.md (~6 j).

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | v2 : tokens uniques + remappage + tous les correctifs |
| `front/templates/front/corpus/_style_maquette.html` | :root retire, Wong, verdicts 3:1, cibles, focus, panneau |
| `front/templates/front/corpus/article.html` | role dialog, focus, Escape conditionne |
| `front/templates/front/corpus/carnet_detail.html` | noscript fonctionnel |
| `front/templates/front/base.html` | branche article_preloaded |
| `front/views_synthese.py` | acces direct -> page complete / redirect |

### Migration
- **Migration necessaire / Migration required :** Non.

