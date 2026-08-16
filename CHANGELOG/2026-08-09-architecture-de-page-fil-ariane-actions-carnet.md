# Architecture de page : le fil d'Ariane, les actions du carnet, l'alignement, la provenance des notes

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** quatre ajouts de structure, front pur, sur le design
de l'etalon (`tmp/maquettes/corpus.html`).

**1. LE FIL D'ARIANE « Base > Carnet > Note »**, colle sous la barre,
sur les ecrans carnet, article et note. Il porte la BASCULE DE CARNET.
Sa raison d'etre est ecrite dans l'etalon : **le N-N a tue l'arbre**.
Une note rangee dans deux carnets n'a pas de parent unique, donc pas de
place dans une arborescence. Le fil montre UN chemin parmi ceux qui
existent, et son chevron permet d'en changer — sur un carnet il liste
les carnets accessibles, sur une note **les carnets qui contiennent
cette note** (basculer = relire la meme note sous un autre classement,
via `?carnet=N`).
Trois decisions de securite : la regle d'acces est EXTRAITE dans
`carnets_visibles_par()` pour n'exister qu'une fois (le fil et la liste
des carnets la partagent) ; un `?carnet=N` n'est honore que si le
carnet contient vraiment la note et que le visiteur y a acces — un
parametre d'URL ne sert jamais d'oracle ; une base non publique
n'apparait pas dans le fil d'un visiteur qui n'y a pas acces, le nom
seul etant deja une fuite.

**2. « Nouveau wiki » et « Nouvelle synthese » dans l'en-tete du
carnet.** Ils n'ouvrent AUCUN chemin nouveau : ils activent l'onglet qui
porte deja le formulaire, attendent son arrivee en HTMX
(MutationObserver plutot qu'un delai devine), y font defiler et posent
le focus.

**3. UN ONGLET ALIGNEMENT** qui rouvre le flux EXISTANT
(`window.alignement.ouvrirDossier`, soit
`/alignement/tableau/?dossier_id=N` — l'endpoint prenait deja le
carnet). Il ne prend PAS la selection d'onglet : le gabarit du tableau
est un fragment de MODALE, l'injecter dans un panneau aurait demande de
le reecrire, donc du back.

**4. SOUS-NOTES ENRICHIES** : marque de source (audio / web / fichier),
nom de fichier tronque, extractions, « dans N carnets ». Tout vient du
`select_related('page')` et des annotations DEJA calculees : aucune
requete de plus.

Verifie au navigateur. Six ecarts trouves et corriges, dont trois qui
valaient le detour : le fil **ne collait pas** au haut de la zone — un
element sticky se cale sur la boite de CONTENU, et le `p-8` du
conteneur le figeait 32px plus bas en laissant defiler du texte dans la
bande au-dessus ; et l'ecouteur « clic dehors » du menu, pose a chaque
injection du fragment, **s'empilait a chaque navigation HTMX** sur des
menus depuis longtemps detaches. Le troisieme est un piege de
diagnostic : le debordement horizontal a 390px semblait venir des
tableaux de transcription ; ils ont bien ete corriges, mais le vrai
coupable etait le formulaire « + Ajouter a… » du bloc carnets, un flex
sans wrap dont le `<select>` porte le nom de TOUS les carnets
disponibles. Sans la chaine d'ancetres de l'element le plus a droite,
on aurait cru le probleme regle.

### Deux constats a remonter (hors perimetre front)
- **`/alignement/tableau/?dossier_id=N` ne verifie AUCUNE permission**
  (`front/views_alignement.py`, `_recuperer_pages_depuis_parametres`) :
  `Dossier.objects.get(pk=...)` sans controle d'acces. N'importe qui
  peut aligner les notes d'un carnet prive. Le lot n'aggrave rien —
  l'onglet n'apparait que sur un carnet deja ouvert — mais la faille
  existe et merite un correctif.
- **La duree et les locuteurs d'un audio ne sont pas sur `Page`** : ils
  derivent de la transcription. Impossible de les afficher dans les
  sous-notes sans requete lourde, donc absents (demande consignee).

623 tests verts.

| Fichier | Changement |
|---|---|
| `front/views_corpus.py` | `carnets_visibles_par()` extrait, `contexte_du_fil_d_ariane()` |
| `front/views.py` | fil d'Ariane sur la lecture ; l'acces direct reutilise le contexte partage |
| `front/views_synthese.py` | fil d'Ariane sur l'article |
| `front/templates/front/corpus/_fil_ariane.html` | **nouveau** : le fil et sa bascule |
| `front/templates/front/corpus/carnet_detail.html` | 2 boutons d'en-tete, onglet Alignement |
| `front/templates/front/corpus/partials/notes_du_carnet.html` | sous-notes enrichies |
| `front/static/front/css/maquette.css` | `.fil-ariane`, `.menu-bascule`, collant reel, tableaux larges, formulaires enroulables |
| `hypostasia/settings_test_opus.py` | **nouveau** : base de test dediee a cette session (fin des collisions entre les deux sessions paralleles) |

### Migration
- **Migration necessaire / Migration required :** Non.

