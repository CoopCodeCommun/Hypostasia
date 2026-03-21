# PHASE-26a-bis — Filtre multi-contributeurs (checkboxes)

**Complexite** : S | **Mode** : Normal | **Prerequis** : PHASE-26a

---

## 1. Contexte

La PHASE-26a a implemente un filtre contributeur mono-selection (un `<select>` natif). En pratique, le facilitateur veut souvent comparer 2 ou 3 contributeurs simultanement ("qu'est-ce que Marie ET Thomas ont dit ?"). Le select natif ne le permet pas — il faut un composant multi-selection.

Ce changement est purement front-end + une adaptation du query param backend.

## 2. Prerequis

- PHASE-26a (Filtre contributeur sur les commentaires) — toute l'infrastructure est deja en place.

## 3. Objectifs precis

### 3.1 — Composant dropdown multi-checkboxes

- [ ] Remplacer le `<select>` contributeur natif par un dropdown custom avec checkboxes
  - Bouton declencheur affichant "Filtrer par contributeur" ou "marie, thomas" si actifs
  - Liste deroulante avec une checkbox par contributeur (nom + count)
  - Option "Tous / Aucun" en haut pour reset rapide
  - Fermeture au clic exterieur ou Escape
- [ ] Un chip par contributeur selectionne (meme style que l'actuel `.chip-contributeur-actif`)
  - Chaque chip a son bouton "x" pour retirer un contributeur individuellement
  - Les chips s'empilent horizontalement avec wrap

### 3.2 — Backend : query param multi-valeurs

- [ ] Le param `?contributeur=42` devient `?contributeur=42,43` (liste d'IDs separes par virgule)
- [ ] `drawer_contenu()` parse la liste et filtre par OR (entites commentees par AU MOINS un des contributeurs)
- [ ] `LectureViewSet.retrieve()` accepte aussi la liste pour la heat map combinee
- [ ] `_calculer_scores_temperature_par_contributeur()` prend une liste d'IDs au lieu d'un seul

### 3.3 — Template et JS

- [ ] Le template rend le composant dropdown au lieu du `<select>`
- [ ] Le JS gere l'etat multi-selection (Set d'IDs) et serialise en query param
- [ ] Le compteur "N sur M" reste identique (nombre d'extractions matchant au moins un contributeur)
- [ ] Le HX-Trigger `contributeurFiltreChange` envoie l'union des IDs entites
- [ ] Le badge toolbar s'affiche des qu'au moins un contributeur est selectionne

### 3.4 — Dimming par contributeur

- [ ] Les commentaires des contributeurs NON selectionnes sont dimmes (comme actuellement)
- [ ] Les commentaires des contributeurs selectionnes sont tous en pleine opacite
- [ ] Le highlight du nom s'applique a tous les contributeurs selectionnes

## 4. Fichiers a modifier

| Fichier | Action |
|---------|--------|
| `front/views.py` | Adapter `drawer_contenu()` et `retrieve()` pour parser une liste d'IDs contributeurs |
| `front/views.py` | Adapter `_calculer_scores_temperature_par_contributeur()` pour une liste d'IDs |
| `front/templates/front/includes/drawer_vue_liste.html` | Remplacer `<select>` par dropdown checkboxes + chips multiples |
| `front/static/front/js/drawer_vue_liste.js` | Gestion etat multi-selection, serialisation, events |
| `front/static/front/js/marginalia.js` | Adapter `appliquerFiltreContributeur()` pour union d'IDs |
| `front/static/front/css/hypostasia.css` | Styles du dropdown custom (ouvert/ferme, checkboxes, focus) |
| `front/tests/test_phases.py` | Adapter les 13 tests existants + ajouter tests multi-contributeur |
| `front/tests/e2e/test_17_filtre_contributeur.py` | Adapter les 6 tests E2E + ajouter test multi-selection |

## 5. Criteres de validation

- [ ] Selectionner 2+ contributeurs affiche les extractions commentees par au moins un d'entre eux
- [ ] Les chips s'affichent pour chaque contributeur selectionne, retirables individuellement
- [ ] Le compteur affiche "N sur M" avec le bon total
- [ ] Le dimming s'applique uniquement aux commentaires des contributeurs non selectionnes
- [ ] La heat map combine les commentaires de tous les contributeurs selectionnes
- [ ] "Tous / Aucun" restaure la vue complete
- [ ] Le dropdown se ferme au clic exterieur et a Escape
- [ ] Compatible mobile (les checkboxes restent utilisables en tactile)
- [ ] Les tests existants continuent de passer (retrocompatibilite : `?contributeur=42` seul fonctionne toujours)
- [ ] `uv run python manage.py check` passe

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver 0.0.0.0:8123`

1. **Ouvrir Ostrom, ouvrir le drawer**
   - **Attendu** : dropdown multi-checkboxes au lieu du select natif
2. **Cocher marie + thomas**
   - **Attendu** : extractions commentees par l'un ou l'autre, 2 chips affiches, badge toolbar visible
3. **Retirer thomas via son chip "x"**
   - **Attendu** : retour au filtre marie seule, 1 chip
4. **Cliquer "Tous"**
   - **Attendu** : tout restaure, pas de chip, badge toolbar cache
5. **Activer heat map + cocher fatima + pierre**
   - **Attendu** : la heat map se recalcule sur les commentaires des 2 contributeurs
6. **Mobile (390px)**
   - **Attendu** : le dropdown s'ouvre correctement en tactile

## 6. Notes de design

Le dropdown custom doit rester sobre et coherent avec le reste du drawer :
- Meme style `text-xs border border-slate-200 rounded` que le select de tri
- Checkboxes avec le nom en Srisakdi (`.typo-lecteur-nom`) pour la coherence visuelle
- Pas de librairie externe — composant vanilla JS dans la IIFE existante
- Le composant est un enhancement du `<select>` actuel : si JS desactive, le `<select>` natif fonctionne toujours (progressive enhancement)
