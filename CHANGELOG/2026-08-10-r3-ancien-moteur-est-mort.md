# R3 : L'ANCIEN MOTEUR EST MORT (~1 100 lignes retirees, le flag `Page.moteur` avec)

**Date :** 2026-08-10
**Migration :** Oui

**Quoi / What :** fin du chantier ouvert par la decision du 10 aout. Il
n'y a plus qu'un moteur d'ancrage ; le code qui permettait d'en choisir
un autre a disparu. / One engine left; the code that chose between two
is gone.

### ⚠️ DEPLOIEMENT EN DEUX TEMPS — A LIRE AVANT DE METTRE EN PRODUCTION

La base de dev a ete reconvertie AVANT cette livraison. Une autre base —
**la production**, une sauvegarde restauree — a toutes ses pages sur
l'ANCIEN moteur. Deployer ce code d'un coup la-bas ne casserait rien
bruyamment : les pages s'afficheraient sans leurs surlignages, en
silence. La migration `core.0056` **REFUSE donc de s'appliquer** tant
qu'une page reste ANCIEN, et dit quoi lancer.

L'ordre est le suivant, et il n'y en a pas d'autre :

1. deployer la version **R2** (celle qui porte encore le flag ET la
   commande `basculer_vers_le_moteur_element`) ;
2. `manage.py basculer_vers_le_moteur_element --a-blanc`, lire le bilan,
   puis le lancer pour de vrai ;
3. deployer **R3** : la migration 0056 constate « 0 page sur l'ancien
   moteur » et retire le champ.

La commande de reconversion est SUPPRIMEE dans R3 (elle selectionnait
les pages par un flag qui n'existe plus). C'est un outil de migration a
usage unique : il vit dans R2, qui reste accessible par git.
/ Two-step deployment: reconvert with R2, then deploy R3.

### Ce qui a ete retire

| Ce qui part | Lignes |
|---|---|
| `front/utils.py` — le pont texte<->HTML | **504** |
| `analyser_page_task` + son routage par moteur | **440** |
| La classe de tests de l'annotation par offsets | 109 |
| La fabrique de pastilles (JS + CSS), R2 | ~120 |
| Le champ `Page.moteur`, sa classe et ses 12 points de decision | migration 0056 |

`extraire_texte_depuis_html` etait la SEULE fonction de `front/utils.py`
a avoir une vie propre : elle derive `text_readability` a l'ingestion, ce
qui n'a rien a voir avec l'ancrage. Elle est deplacee dans
`front/services/texte_depuis_html.py` (105 l.) avec la seule aide dont
elle depend, sous un nom qui dit ce qu'elle fait.

### UN BUG TROUVE EN CHEMIN, ET IL ETAIT SERIEUX

Cinq actions du panneau (`panneau`, `creer_manuelle`, `supprimer_ia`,
`promouvoir_entrainement`, `ia`) renvoyaient un swap « out of band » qui
REMPLACE tout `#readability-content` — construit par l'ancien moteur.
Sur une page ELEMENT, **creer une extraction a la main effacait donc les
blocs, les boutons d'operations et les ancres** jusqu'au rechargement
complet. Ces vues ne consultaient jamais `Page.moteur` : ecrites avant
lui, jamais rouvertes depuis. Le rendu passe desormais par le meme
service que la lecture (`_contenu_de_lecture`), donc par la meme verite.
3 tests (`front/tests/test_oob_lecture_element.py`).

### Ce qui a ete ADAPTE plutot que supprime

- Le test e2e du bottom sheet mobile batissait une page ANCIEN dont les
  surlignages venaient de `html_annote` : sans blocs ni ancres, il
  n'avait plus rien vers quoi scroller. Reconstruit sur ELEMENT (20
  blocs, ancrage sur le 15e).
- `core/tests/test_moteur_flag.py` verifiait un champ qui disparait. Il
  prouve maintenant la seule chose qui reste : que la garde de la
  migration 0056 refuse une base non reconvertie ET dit quoi faire.
- Trois tests dont le NOM parlait d'une « page ancienne » testent en
  realite une page SANS ELEMENT — renommes en consequence. Un nom qui
  ment est un defaut.
- Les 12 conditions `if page.moteur == ELEMENT` deviennent
  inconditionnelles ; le tri du panneau suit toujours l'ancre.

### Migration
- **Migration necessaire / Migration required :** OUI —
  `core.0056_suppression_du_flag_moteur`, avec son garde-fou. Voir la
  procedure en deux temps ci-dessus.

