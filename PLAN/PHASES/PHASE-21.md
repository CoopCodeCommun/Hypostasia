# PHASE-21 — Mobile : bottom sheet + responsive

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-14

---

## 1. Contexte

Le mobile n'est pas un ecran desktop "en plus petit". C'est un contexte d'usage different avec ses propres forces. Hypostasia sur mobile doit offrir l'interface adaptee a ce qu'on fait reellement sur un telephone : lecture immersive (pas de distractions laterales), reaction rapide (commenter en 30 secondes), capture en mobilite (envoyer un article depuis le navigateur), suivi d'avancement (dashboard en un coup d'oeil).

Le cas d'usage cle est la capture + lecture augmentee en mobilite : tomber sur un article, l'envoyer sur Hypostasia via l'extension, lancer l'extraction IA, et lire l'article avec les extractions deja en place — le tout sur le telephone.

Le mobile fait volontairement l'impasse sur certaines fonctionnalites (extraction manuelle, choix d'analyseur avance, wizard de synthese, alignement cross-documents, raccourcis clavier, curation) car elles sont inadaptees au contexte mobile.

## 2. Prerequis

- **PHASE-14** : dashboard de consensus (version compacte affichee en haut de page sur mobile)

## 3. Objectifs precis

### Ce que fait le mobile

- [x] **Breakpoint mobile** : `max-width: 768px`. Layout mono-colonne pleine largeur, pas de colonnes laterales
- [x] **Navbar mobile adaptee** : pas de mot "Hypostasia", titre du document tronque avec "...", boutons toggle mode et aide toujours visibles a droite. Les boutons desktop (Dashboard, Analyser, Extractions, Focus, Heatmap, Import, Config) sont masques.
- [x] **Surlignage colore par statut de debat** : les textes extraits ont un fond et un soulignement colore selon le statut (vert consensuel, rouge discutable, ambre discute, orange controverse). Opacite plus forte que sur desktop car pas de pastilles de marge. Extractions commentees : soulignement pointille.
- [x] **Tap sur un marqueur -> bottom sheet** : bottom sheet depuis le bas avec la carte d'extraction complete (hypostase, resume IA, citation source, statut de debat, commentaires existants)
  - Composant JS simple : div position fixed, transition CSS translateY
  - Bouton X en haut a droite pour fermer (remplace l'ancienne poignee de drag)
  - Clic sur le backdrop (texte grise) ferme aussi la carte
  - Pas de librairie tierce
  - Reutilise les memes donnees que la carte desktop (meme endpoint HTMX, template different)
- [x] **Scroll automatique du paragraphe source** : quand le bottom sheet s'ouvre, le paragraphe surligne correspondant est scrolle en vue (positionne a ~25% du haut de l'ecran, au-dessus du bottom sheet)
- [x] **Swipe gauche/droite pour naviguer** : dans le bottom sheet, glisser horizontalement passe a l'extraction suivante (swipe gauche) ou precedente (swipe droite), dans l'ordre du texte. Le paragraphe source est scrolle a chaque changement. Animation de transition horizontale.
- [x] **Commenter une extraction** : depuis le bottom sheet, bouton "Commenter" charge le fil de discussion dans le bottom sheet via HTMX
- [x] **Lancer une extraction IA** : bouton "Analyser" dans la toolbar. Sur mobile, la confirmation (tokens, cout, prompt) s'affiche dans la zone de lecture, comme sur desktop. Pas de choix de parametres avances.
- [x] **Toggle mode 3 etats** : bouton oeil dans la toolbar mobile, cycle entre :
  1. **Surlignage** (defaut) — fond + soulignement colore par statut
  2. **Lecture pure** — surlignage masque, texte brut
  3. **Heat map** — couleurs d'intensite du debat (meme heatmap que desktop)
  Les 3 etats sont mutuellement exclusifs (CSS classes `mode-lecture-mobile`, `mode-heatmap-mobile`).
- [x] **Aide mobile** : bouton "?" dans la toolbar charge une modale via HTMX (`GET /lire/aide/?mobile=1`) avec un template Django modifiable (`aide_mobile.html`). Contenu : gestes tactiles illustres avec les vrais elements de l'UI (icones SVG, pastilles de couleur, barre de poignee).
- [x] **Arbre mobile** : plein ecran (100vw), navigation tap, bouton retour. Pas de vue arbre + lecture simultanee.
- [x] **Indicateur de chargement** : skeleton ou spinner pendant l'extraction (meme pattern que desktop)
- [x] **Detection du contexte** : media queries CSS `@media (max-width: 768px)` + classes `.btn-mobile-only` / `.btn-desktop-only` pour les boutons de toolbar. Pas de user-agent detection.

### Choix de design documentes

**Mode lecture pure dans le toggle mobile** : le plan initial excluait le "mode focus" du mobile
au motif que "sur mobile on EST deja en mode focus". En pratique, sur un texte avec beaucoup
d'extractions, le surlignage colore peut gener la lecture immersive. Le toggle 3 etats permet
de passer temporairement en lecture pure (surlignage masque) puis de revenir. Ce n'est pas le
mode focus desktop (pas de centrage du texte, pas de masquage des pastilles, pas de raccourci L) —
c'est juste un nettoyage visuel pour lire le texte brut sans distraction. Decision prise le 2026-03-15.

**Surlignage colore par statut** : le plan initial PHASE-09 prevoyait un surlignage generique.
On a enrichi pour que chaque statut de debat ait sa propre couleur (vert consensuel, rouge discutable,
ambre discute, orange controverse) avec un soulignement pointille pour les extractions commentees.
Les couleurs sont les memes variables CSS (`--statut-*-accent`) que les pastilles de marge et les
badges de statut dans les cartes. Sur mobile l'opacite est legerement plus forte (0.12-0.14 vs
0.08-0.10 sur desktop) car les pastilles de marge sont absentes.

**Aide via HTMX + templates Django** : l'aide mobile et desktop sont des templates Django modifiables
en HTML (`aide_mobile.html`, `aide_desktop.html`), charges via un endpoint HTMX (`GET /lire/aide/`).
Pas de generation HTML dans le JS — le contenu est editable sans toucher au code JS.

**Bouton X au lieu de poignee de drag** : la poignee (barre grise en haut du bottom sheet) a ete
remplacee par un bouton X en haut a droite. Le drag vers le bas est retire car sur mobile le geste
vertical entre en conflit avec le scroll du contenu. Le bouton X + clic backdrop sont suffisants
pour fermer. Decision prise le 2026-03-15.

**Navigation swipe gauche/droite** : dans le bottom sheet, glisser horizontalement navigue entre les
extractions dans l'ordre du texte (position start_char). Le paragraphe source est scrolle en vue a
chaque changement. L'ordre du texte a ete choisi (option A) plutot que l'ordre par statut (option B)
car c'est le plus intuitif — swipe droite = extraction suivante dans le texte = scroll vers le bas.
Decision prise le 2026-03-15.

### Ce que le mobile ne fait PAS

| Fonctionnalite exclue | Raison |
|---|---|
| Extraction manuelle | Selection precise au doigt frustrant |
| Choix d'analyseur avance | Workflow desktop |
| Wizard de synthese | 5 etapes avec formulaires, travail de bureau |
| Alignement cross-documents | Tableau illisible sur 375px |
| Raccourcis clavier | Pas de clavier physique |
| Curation (masquer/restaurer) | Gestion fine, workflow desktop |

## 4. Fichiers modifies

- `front/templates/front/base.html` — navbar adaptee mobile (titre tronque, boutons mobile/desktop)
- `front/templates/front/includes/bottom_sheet_extraction.html` — template bottom sheet extraction mobile
- `front/templates/front/includes/aide_mobile.html` — **(nouveau)** modale aide mobile (gestes tactiles)
- `front/templates/front/includes/aide_desktop.html` — **(nouveau)** modale aide desktop (raccourcis clavier)
- `front/static/front/css/hypostasia.css` — media queries 768px, surlignage colore par statut (desktop + mobile), bottom sheet, toggle mode, `.btn-mobile-only`/`.btn-desktop-only`
- `front/static/front/js/bottom_sheet.js` — composant bottom sheet (position fixed, translateY, drag handle)
- `front/static/front/js/keyboard.js` — toggle mode 3 etats, aide via HTMX (templates Django)
- `front/views.py` — endpoint `LectureViewSet.aide()` (renvoie aide_mobile ou aide_desktop)
- `front/templates/front/includes/lecture_principale.html` — OOB conditionnel bouton Analyser

## 5. Criteres de validation

- [x] Sur viewport 390px : le layout est mono-colonne, pas de sidebar visible
- [x] Pas de scroll horizontal
- [x] Titre du document tronque dans la navbar, "Hypostasia" masque
- [x] Boutons toggle mode et aide visibles et dans le viewport
- [x] Boutons desktop (Dashboard, Analyser, etc.) masques
- [x] Surlignage colore par statut de debat visible dans le texte
- [x] Tap sur un marqueur d'extraction -> le bottom sheet s'ouvre avec la bonne carte
- [x] Bouton "Commenter" dans le bottom sheet charge le fil de discussion
- [x] Bouton "Analyser" -> la confirmation s'affiche (tokens, cout, prompt)
- [x] Drag handle vers le bas -> le bottom sheet se ferme
- [x] Toggle mode : surlignage → lecture pure → heat map → retour au surlignage
- [x] Aide mobile : modale avec gestes tactiles (icones correspondant a l'UI reelle)
- [x] Navigation arbre -> plein ecran, tap document -> retour a la lecture

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir DevTools > mode responsive (Ctrl+Shift+M) > choisir iPhone 12 (390px) ou Galaxy S21 (360px)**
   - **Attendu** : le navigateur passe en mode emulation mobile
2. **Ouvrir http://localhost:8000/**
   - **Attendu** : layout mono-colonne, texte lisible, pas de scroll horizontal
   - **Attendu** : navbar avec titre tronque, boutons oeil et "?" a droite
3. **Tap sur un texte souligne de couleur dans le texte**
   - **Attendu** : un bottom sheet monte depuis le bas avec la carte d'extraction
4. **Drag le handle du bottom sheet vers le bas**
   - **Attendu** : il se ferme
5. **Ouvrir l'arbre (hamburger)**
   - **Attendu** : il prend tout l'ecran sur mobile
6. **Le bouton "Analyser" est accessible dans la toolbar desktop (pas sur mobile)**
   - **Attendu** : la confirmation s'affiche avec tokens, cout et prompt
7. **Taper sur le bouton oeil (toggle mode)**
   - **Attendu** : 1er tap → lecture pure (surlignage disparait). 2eme tap → heatmap. 3eme tap → retour au surlignage.
8. **Taper sur le bouton "?" (aide)**
   - **Attendu** : modale avec gestes tactiles, icones correspondant aux elements reels de l'UI
