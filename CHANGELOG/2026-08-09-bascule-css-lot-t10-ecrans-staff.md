# Bascule CSS, lot T10 : les ecrans staff, et la fin du chantier

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** les ecrans d'administration de `hypostasis_extractor`
(configuration des LLM, editeur d'analyseur, historique et diff de
versions, exemples, entrainements) n'avaient jamais ete touches. Ils
sont ecrits ENTIEREMENT en utilitaires Tailwind : ~300 occurrences
colorees sur 18 gabarits.

**Aucun de ces gabarits n'a ete modifie.** Les enumerer classe par
classe aurait double la feuille sans jamais couvrir les variantes
(`hover:`, `peer-checked:`, `focus:`, `border-l-`) : on a remappe les
ECHELLES elles-memes — slate/gray, green/emerald, red/rose,
amber/yellow/orange, violet/purple — en laissant le NIVEAU porter le
role (50-100 fond, 200-300 filet, 400+ teinte pleine). Les ambres
partent sur `--faible` et non sur `--statut-commente` : en texte,
l'ambre pur ne fait que 2,2:1.

La verification a trouve six defauts que le seul remappage ne pouvait
pas corriger, tous repares :
- un fond semantique PLEIN portait du texte `blanc` : en sombre ces
  fonds s'eclaircissent et le blanc y tombait a **1,52:1** (badge
  « IA active »). Le texte y est desormais `--papier`, qui suit le
  theme ;
- `.text-slate-300` sert de TEXTE (numeros d'ordre a 9px) la ou le
  niveau 300 de l'echelle est reserve aux filets de controle : 3,02:1 ;
- **241 champs** dessines avec `border-slate-200`, un filet decoratif a
  1,19:1 — les elements de formulaire prennent maintenant
  `--filet-controle` ;
- **`focus:outline-none` battait le focus visible global** (0,2,0
  contre 0,1,0) : un champ focalise au clavier ne montrait plus rien
  des que son `ring` etait absent. Le focus est un invariant
  d'accessibilite (WCAG 2.4.7), il passe en `!important` ;
- sous 640px, les rangees de controles poussaient leur bouton
  « Sauver » HORS du viewport, sans defilement pour le rattraper ;
- les deux ecrans de versions n'avaient aucun conteneur et commencaient
  au bord gauche de la fenetre.

**Le code mort du poste 0.1, supprime dans la foulee.** Verification
faite, il ne s'agissait pas de trois VUES cassees mais de trois
BRANCHES HTML a l'interieur de ViewSets DRF qui servent aussi du JSON —
supprimer les vues aurait casse l'API. Ces branches etaient
**doublement mortes** : leur template etend `core/base.html`, absent du
depot, ET la condition `request.accepted_renderer.format == 'html'` ne
pouvait jamais etre vraie, aucun renderer HTML n'etant configure (DRF
s'en tient a JSON + BrowsableAPI, dont le format est `api`). Verifie
en reel avant et apres : `/api/extraction-jobs/` et
`/api/extraction-examples/` repondent 200 en JSON comme en HTML, avant
comme apres. Retire : les 3 branches, et 4 gabarits
(`job_list.html`, `job_detail.html`, `example_list.html`, plus
`analyseur_list.html`, orphelin sans aucune reference).

782 tests `hypostasis_extractor` + `test_phases` et 104 e2e verts apres
la suppression.

104 tests e2e et 585 tests unitaires verts.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | section T10 : 5 echelles remappees + 6 correctifs cibles |
| `front/templates/front/*.html` | cache-busting maquette.css v15 |
| `hypostasis_extractor/views.py` | 3 branches HTML mortes retirees (l'API JSON est intacte) |
| `hypostasis_extractor/templates/.../{job_list,job_detail,example_list,analyseur_list}.html` | supprimes (~285 lignes) |

### Migration
- **Migration necessaire / Migration required :** Non.

