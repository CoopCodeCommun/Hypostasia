# R2 : la base est 100 % ELEMENT, les pastilles de marge sont mortes, et le filtre par contributeur revit

**Date :** 2026-08-10
**Migration :** Non

**Quoi / What :** premieres etapes de la mort de l'ancien moteur, apres
la reconversion R1. / First steps of the old engine's removal.

**ETAPE 1 — les 2 dernieres pages ANCIEN.** Je les croyais vides et
pretes a supprimer. Verification : **la page 97 porte 4,17 Mo de HTML**
(un .docx de huit images en base64, zero caractere de texte). La
supprimer aurait detruit un document.

Le vrai obstacle n'etait pas la page, c'etait ma propre garde. Elle
refusait de basculer une page sans bloc « parce que le moteur ELEMENT
n'aurait rien a afficher » — or le templatetag `blocs_de_lecture_de`
retombe sur `html_readability` quand une page ELEMENT n'a aucun element.
Le bon critere n'est pas « a-t-elle des blocs ? » mais « la bascule
change-t-elle ce qu'on voit ? » : sans extraction, le rendu est
IDENTIQUE ; avec des extractions, on perdrait des surlignages, donc on
s'abstient. Les deux pages sont passees ELEMENT — **213 pages, 100 %
ELEMENT** — et la page 97 affiche toujours ses 8 images (verifie au
navigateur : 8 `<img>`, 8 visibles, zero erreur JS).

**ETAPE 2 — `marginalia.js`.** Il n'etait PAS supprimable en bloc : il
porte `ouvrirDrawerEtScrollerVersCarte`, vivante et appelee par quatre
autres scripts (clavier, dashboard, hypostasia, drawer). Ce qui est mort
en est retire :
- `construirePastillesMarginales`, neutralisee le 10 aout, ne faisait
  plus que nettoyer d'eventuels residus — plus rien, ni serveur ni JS,
  ne produit une pastille. Supprimee avec ses appels dans `hypostasia.js`
  et `drawer_vue_liste.js`, ses declencheurs (`DOMContentLoaded`,
  `htmx:afterSwap`) et son alias global ;
- **le CSS des pastilles** (~50 l. dans `hypostasia.css` et
  `maquette.css`). Prudence : plusieurs regles etaient PARTAGEES avec
  `.indicateur-statut`, bien vivant dans `_card_body.html` — seul le
  selecteur mort a ete retire de celles-la, jamais la regle entiere. Un
  test de contre-epreuve le protege desormais.

**LE FILTRE PAR CONTRIBUTEUR REVIT.** Il estompait les pastilles ;
celles-ci disparues, il ne trouvait plus un seul noeud et ne faisait
**RIEN, sans que rien ne le dise** — c'etait un des restes du chantier A.
Il agit maintenant sur `mark.hl-extraction`, la seule ancre qui existe.
Verifie au navigateur : 235 ancres estompees sur 238 (3 gardees), 0
apres reset. Le style baisse le SURLIGNAGE et non le texte : le
contraste de lecture est preserve.

**Non-regression prouvee, pas supposee** : clic sur une ancre non
superposee -> la carte correspondante s'active, correspondance exacte
(meme mark 16735 que la verification d'avant ces suppressions). Le
decalage sur les marks SUPERPOSES est un defaut preexistant, deja releve.
545 tests `test_phases` verts.

**Quatre tests-mensonges remplaces par des gardes anti-retour** : ils
exigeaient l'existence de la fabrique de pastilles, de son
`DOMContentLoaded`, et de leur CSS. Ils protegeaient un comportement
supprime ; ils verifient desormais qu'il ne revient pas.

| Fichier | Changement |
|---|---|
| `core/management/commands/basculer_vers_le_moteur_element.py` | `_sort_d_une_page_qui_n_a_aucun_bloc` : le critere devient « la bascule change-t-elle l'affichage ? » |
| `front/static/front/js/marginalia.js` | fabrique de pastilles supprimee, filtre recable sur les ancres inline, en-tete honnete |
| `front/static/front/js/hypostasia.js`, `drawer_vue_liste.js` | appels a la fabrique retires |
| `front/static/front/css/hypostasia.css`, `maquette.css` | CSS des pastilles retire, `.ancre-hors-filtre` ajoute |
| `front/templates/front/base.html` | bumps `?v=` (maquette 24, hypostasia 35, marginalia 23) |
| `core/tests/test_reconversion_moteur.py`, `front/tests/test_phases.py` | gardes anti-retour |

### Migration
- **Migration necessaire / Migration required :** Non.

