# PHASE-15 — Rythme visuel de la transcription (anti-mur-de-texte)

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-11, PHASE-12

---

## 1. Contexte

Une reunion d'une heure genere 50 a 100 blocs de texte. Sans rythme visuel, c'est un mur uniforme ou l'oeil n'a aucun point d'accroche. Contrairement a un article (qui a des titres, sous-titres, paragraphes), une transcription est une suite monotone de `LOCUTEUR: texte`. L'objectif est d'introduire des reperes visuels qui cassent la monotonie sans ajouter de contenu : alternance de fond par locuteur, marqueurs temporels, groupement des tours de parole, timeline audio et filtrage par locuteur.

## 2. Prerequis

- **PHASE-11** : variables CSS typographiques (polices et couleurs necessaires)
- **PHASE-12** : charte visuelle des cartes (coherence visuelle avec le reste de l'interface)

Note : les donnees `TextBlock` (`speaker`, `start_time`, `end_time`) existent deja dans le POC, aucun prerequis de phase supplementaire necessaire pour cela.

## 3. Objectifs precis

- [ ] **Alternance de fond par locuteur** : chaque locuteur a un fond tres pale distinct (bulles de chat). Ex: locuteur A -> `#f8fafc`, locuteur B -> `#fdf4ff`, locuteur C -> `#f0fdf4`. Le changement de locuteur est visible d'un coup d'oeil
- [ ] **Marqueurs temporels periodiques** : separateur leger toutes les 5 minutes. Format : fine ligne horizontale + timestamp (`-- 05:00 --`). Cree des "chapitres" implicites
- [ ] **Groupement des tours de parole** : si un locuteur a 3 blocs consecutifs, les grouper sous un seul header de locuteur (nom + timestamp du premier bloc). Les blocs suivants n'affichent pas le nom, seulement le texte avec indent
- [ ] **Mini-barre de progression temporelle** : barre fine en haut de la zone de lecture (debut -> fin). Au scroll, la barre suit. Clic sur la barre -> scroll vers le timestamp correspondant
- [ ] **Timeline audio horizontale** (uniquement pour pages `source_type=audio`) :
  - Barre horizontale en haut de la zone de lecture (sous le titre, au-dessus de l'article)
  - Chaque segment colore par locuteur (meme couleur que les fonds de blocs)
  - Largeur proportionnelle a la duree
  - Survol -> tooltip avec nom du locuteur + timestamp + preview du texte (30 premiers chars)
  - Clic -> scroll vers le bloc correspondant
  - Marqueurs d'extraction : les extractions apparaissent comme des points sur la timeline, colores par statut de debat
  - Genere cote serveur (HTML/CSS pur) a partir des donnees `TextBlock`
- [ ] **Filtrage par locuteur** :
  - Menu deroulant ou boutons-pilules en haut de la zone de lecture : liste des locuteurs avec leur couleur
  - Clic sur un locuteur -> masque les blocs des autres (`display: none` ou filtre HTMX)
  - Bouton "Tous" pour restaurer l'affichage complet
  - Filtre local (pur JS/CSS sur les blocs existants, pas de requete serveur)
  - La timeline se met a jour pour montrer uniquement les segments du locuteur filtre

## 4. Fichiers a modifier

- `front/views.py` — LectureViewSet : generation du HTML diarise + timeline
- `front/templates/front/includes/lecture_principale.html` — affichage des blocs avec alternance, groupement, marqueurs temporels, timeline
- `front/static/front/css/hypostasia.css` — styles pour alternance de fond, marqueurs temporels, timeline, filtrage
- `front/static/front/js/hypostasia.js` (ou nouveau fichier dedié) — barre de progression temporelle, filtrage par locuteur, interaction timeline

## 5. Criteres de validation

- [ ] Transcription longue (20+ blocs) : l'alternance de fond par locuteur est visible
- [ ] Des marqueurs temporels apparaissent toutes les 5 minutes dans le flux
- [ ] Les tours de parole consecutifs d'un meme locuteur sont groupes sous un seul header
- [ ] Timeline : les segments sont colores par locuteur, le clic scroll vers le bon bloc
- [ ] Timeline : les marqueurs d'extraction apparaissent sur la timeline
- [ ] Filtrage : selectionner un locuteur masque les autres blocs, "Tous" restaure l'affichage
- [ ] La timeline est generee cote serveur (HTML/CSS pur, pas de librairie JS externe)

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Importer un fichier audio (ou ouvrir une page de transcription existante)**
   - **Attendu** : les blocs de transcription ne forment plus un mur de texte
   - **Attendu** : chaque changement de locuteur est visuellement marque (separateur, couleur alternee, ou retrait)
2. **Les timestamps sont visibles a gauche ou au-dessus de chaque bloc**
   - **Attendu** : on peut reperer la position temporelle de chaque intervention
3. **Les noms de locuteurs sont mis en evidence**
   - **Attendu** : gras, couleur distincte par locuteur
4. **Si timeline audio : une barre de progression cliquable permet de naviguer dans la transcription**
   - **Attendu** : cliquer sur un point de la barre scroll vers le bloc correspondant

## 6. Extraits du PLAN.md

> ### Etape 1.9 — Rythme visuel de la transcription (anti-mur-de-texte)
>
> **Pourquoi** : le mockup de Yves (`DEBAT transcription - ex.pdf`) montre une transcription bien aeree avec quelques blocs. Mais une reunion d'une heure genere 50 a 100 blocs de texte. Sans rythme visuel, c'est un mur uniforme ou l'oeil n'a aucun point d'accroche. L'utilisateur ne sait pas ou il en est, ne peut pas scanner rapidement, et perd le contexte temporel.
>
> C'est un probleme specifique aux transcriptions longues : contrairement a un article (qui a des titres, sous-titres, paragraphes), une transcription est une suite monotone de `LOCUTEUR: texte`. La seule variation est le nom du locuteur — mais si 3 personnes parlent alternativement pendant une heure, les blocs se ressemblent tous.
>
> **Solution** : introduire 4 types de reperes visuels qui cassent la monotonie sans ajouter de contenu.
>
> **Actions** :
> - [ ] **Alternance de fond par locuteur** : chaque locuteur a un fond tres pale distinct (comme les bulles de chat). Ex: locuteur A -> `#f8fafc`, locuteur B -> `#fdf4ff`, locuteur C -> `#f0fdf4`.
> - [ ] **Marqueurs temporels periodiques** : inserer un separateur leger toutes les 5 minutes dans le flux de blocs. Format : fine ligne horizontale + timestamp (`-- 05:00 --`).
> - [ ] **Groupement des tours de parole** : si un locuteur a 3 blocs consecutifs, les grouper visuellement sous un seul header de locuteur.
> - [ ] **Mini-barre de progression temporelle** : barre fine en haut de la zone de lecture qui indique la position dans la transcription.
> - [ ] **Timeline audio horizontale** (uniquement pour les pages `source_type=audio`) : barre horizontale en haut de la zone de lecture, segments colores par locuteur, survol/clic interactifs, marqueurs d'extraction.
> - [ ] **Filtrage par locuteur** : boutons-pilules en haut de la zone de lecture, filtre local JS/CSS.
>
> **Fichiers concernes** : `front/views.py` (LectureViewSet), CSS, JS pour la barre de progression temporelle, le filtrage par locuteur et l'interaction timeline.
