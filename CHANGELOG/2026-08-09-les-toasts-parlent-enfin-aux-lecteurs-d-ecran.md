# Les toasts parlent enfin aux lecteurs d'ecran

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** l'application confirme ses actions par des toasts
SweetAlert (« Note supprimee », « Analyse lancee »…). SweetAlert
annonce ses MODALES — role=dialog, focus deplace — mais **pas ses
toasts** : ni modaux ni focalises, ils apparaissaient, vivaient trois
secondes et disparaissaient en silence. Une personne qui n'a pas les
yeux sur l'ecran ne savait jamais si son action avait abouti. L'etalon
de design n'a pas d'aria-live non plus : c'est un point ou la bascule
devait faire MIEUX que lui.

**Deux decisions de conception.**
1. On n'annonce pas depuis le toast : une region live creee en meme
   temps que son contenu n'est pas annoncee de facon fiable. On ecrit
   dans une region PERSISTANTE (`#zone-annonces`, dans base.html),
   presente des le rendu, que la technologie d'assistance surveille
   depuis le debut.
2. On n'a pas touche aux sept fichiers qui appellent `Swal.fire`
   (hypostasia, keyboard, arbre_overlay, arbre_context_menu,
   drawer_vue_liste, dashboard_consensus, alignement) : `annonces.js`
   ENVELOPPE `Swal.fire` une seule fois. Un seul point d'entree couvre
   l'existant et le futur — le prochain toast ecrit ailleurs sera
   annonce sans que personne y pense.

Les modales restent volontairement exclues : les annoncer en plus
ferait entendre le message deux fois. Le vidage puis la reecriture
differee de 50 ms sont necessaires pour que deux messages IDENTIQUES a
la suite soient bien re-annonces.

Verifie au navigateur, y compris sur un vrai toast du produit
(« Copier en Markdown ») : region presente avant tout toast, invisible
mais non masquee (1x1px hors ecran, ni display:none ni aria-hidden),
`title` + `text` concatenes, `html:` reduit au texte, modale sans
annonce, aucune erreur JS. 543 tests verts, dont 3 neufs qui figent le
contrat — y compris l'ORDRE DE CHARGEMENT : charge avant SweetAlert,
le script renoncerait silencieusement.

| Fichier | Changement |
|---|---|
| `front/static/front/js/annonces.js` | **nouveau** : enveloppe Swal.fire, annonce les toasts |
| `front/templates/front/base.html` | region live persistante + chargement apres SweetAlert |
| `front/tests/test_phases.py` | 3 tests : region live, ordre de chargement, exclusion des modales |

### Migration
- **Migration necessaire / Migration required :** Non.

