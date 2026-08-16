# PHASE-13 — Charte visuelle : etats interactifs + empty states

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-12, PHASE-10

---

## 1. Contexte

Les mockups montrent des etats statiques. Mais une interface reelle a 5 etats par composant : repos, survol, actif/selectionne, chargement, vide, erreur. Si ces etats ne sont pas definis dans le design system, chaque composant invente le sien au cas par cas — un hover bleu ici, un hover gris la, un spinner a droite et un texte "Chargement..." a gauche. L'incoherence visuelle mine la confiance utilisateur. Cette phase definit une fois chaque etat pour reutilisation partout dans l'app.

## 2. Prerequis

- **PHASE-12** — Les cartes d'extraction et statuts doivent etre styles pour que les etats interactifs s'appliquent sur des composants finalises.
- **PHASE-10** — Le drawer (vue liste) doit exister pour y appliquer les etats hover/active et empty states.

## 3. Objectifs precis

### Etats hover

- [ ] Fond `slate-50` (`--hover-bg: #f8fafc`) + `cursor-pointer` sur tous les elements interactifs (cartes, items arbre, boutons)
- [ ] Transition `150ms ease`
- [ ] Pas de changement de taille (evite les decalages de layout)

### Etats active / selectionne

- [ ] Bordure gauche 3px couleur accent + fond teinte
- [ ] Carte d'extraction selectionnee : bordure gauche couleur famille d'hypostase + fond pale
- [ ] Item arbre selectionne : fond `indigo-50` + bordure gauche `indigo-500`

### Etats loading

- [ ] Boutons : icone spinner inline + texte "En cours..." + `pointer-events: none` + opacite reduite
- [ ] Cartes : squelette anime (skeleton screen) avec shimmer gris pulse — pas un spinner centre
- [ ] Zone de lecture : barre de progression fine en haut (style YouTube) pour les analyses longues
- [ ] Classe CSS `.is-loading` applicable a tout conteneur → affiche le skeleton, cache le contenu

### Empty states

- [ ] Arbre sans pages : icone document + texte "Importez votre premier document" + bouton CTA "Importer"
- [ ] Drawer vue liste vide : icone loupe + texte "Aucune extraction pour cette page" + bouton "Lancer une analyse"
- [ ] Fil de commentaires vide : texte "Pas encore de commentaire" + formulaire visible directement
- [ ] Chaque empty state a une illustration ou icone + un texte explicatif + une action primaire

### Error states

- [ ] Erreur LLM : message inline rouge avec bouton "Reessayer" (pas d'alerte bloquante)
- [ ] Erreur reseau : bandeau jaune en haut de la zone concernee avec message + auto-retry apres 5s
- [ ] Erreur de validation : champs en rouge + message sous le champ (jamais de toast pour les erreurs de formulaire)

### Variables CSS pour les etats

- [ ] Definir dans `:root` :
  - `--hover-bg: #f8fafc` (slate-50)
  - `--active-bg: #f1f5f9` (slate-100)
  - `--loading-shimmer: #e2e8f0` (slate-200)
  - `--error-text: #dc2626` (red-600)
  - `--error-bg: #fef2f2` (red-50)

## 4. Fichiers a modifier

- `front/static/front/css/hypostasia.css` — classes pour hover, active, loading (skeleton, shimmer, spinner, progress bar), empty states, error states, variables CSS
- `front/templates/front/includes/arbre_dossiers.html` — empty state arbre, etat selectionne
- `front/templates/front/includes/drawer_vue_liste.html` — empty state drawer, etat hover/active sur cartes
- `front/templates/front/includes/vue_commentaires.html` — empty state commentaires
- `front/templates/front/includes/lecture_principale.html` — barre de progression loading, error states LLM/reseau
- `front/templates/front/includes/carte_inline.html` — etats hover/active sur carte inline

## 5. Criteres de validation

- [ ] Hover : fond `slate-50` uniforme sur tous les elements interactifs avec transition 150ms
- [ ] Active : bordure gauche accent visible sur la carte selectionnee et l'item arbre selectionne
- [ ] Loading boutons : spinner inline + texte "En cours..." + non-cliquable
- [ ] Loading cartes : skeleton shimmer anime (pas de spinner)
- [ ] Loading zone de lecture : barre de progression fine en haut
- [ ] Empty state arbre : icone + texte + bouton "Importer" affiches quand aucun document
- [ ] Empty state drawer : icone + texte + bouton "Lancer une analyse" affiches quand aucune extraction
- [ ] Empty state commentaires : texte + formulaire visible
- [ ] Erreur LLM : message rouge inline + bouton "Reessayer"
- [ ] Erreur reseau : bandeau jaune + auto-retry
- [ ] Toutes les couleurs d'etat passent par des variables CSS

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Survoler une pastille de marge** : passer la souris sur un cercle colore
   - **Attendu** : effet hover visible (grossissement ou halo)
2. **Survoler une carte dans le drawer** : passer la souris sur une carte compacte
   - **Attendu** : effet hover (border ou fond change)
3. **Ouvrir un document SANS extractions** : selectionner un document non analyse
   - **Attendu** : un "empty state" guide s'affiche ("Aucune extraction. Cliquez sur Analyser pour commencer")
4. **Ouvrir un dossier VIDE** : selectionner un dossier sans documents
   - **Attendu** : message guide ("Ce dossier est vide. Importez un document ou recoltez une page web")
5. **Ouvrir l'arbre sans aucun dossier** : vider tous les dossiers (ou tester sur une base vierge)
   - **Attendu** : message d'accueil avec les etapes pour commencer

## 6. Extraits du PLAN.md

> **Actions etats interactifs** (ajust. 5) :
>
> - [ ] **Hover** : fond `slate-50` + `cursor-pointer` sur tous les elements interactifs. Transition `150ms ease`. Pas de changement de taille
> - [ ] **Active / selectionne** : bordure gauche 3px couleur accent + fond teinte. Ex : carte selectionnee = bordure gauche couleur famille d'hypostase + fond pale. Item arbre selectionne = fond `indigo-50` + bordure gauche `indigo-500`
> - [ ] **Loading** :
>   - Boutons : icone spinner inline + texte "En cours..." + `pointer-events: none` + opacite reduite
>   - Cartes : squelette anime (skeleton screen) avec shimmer gris pulse — pas un spinner centre
>   - Zone de lecture : barre de progression fine en haut (style YouTube) pour les analyses longues
>   - Classe CSS `.is-loading` applicable a tout conteneur → affiche le skeleton, cache le contenu
> - [ ] **Empty states** :
>   - Arbre sans pages : icone document + texte "Importez votre premier document" + bouton CTA "Importer"
>   - Drawer vue liste vide : icone loupe + texte "Aucune extraction pour cette page" + bouton "Lancer une analyse"
>   - Fil de commentaires vide : texte "Pas encore de commentaire" + formulaire visible directement
>   - Chaque empty state a une illustration ou icone + un texte explicatif + une action primaire
> - [ ] **Error states** :
>   - Erreur LLM : message inline rouge avec bouton "Reessayer" (pas d'alerte bloquante)
>   - Erreur reseau : bandeau jaune en haut de la zone concernee avec message + auto-retry apres 5s
>   - Erreur de validation : champs en rouge + message sous le champ (jamais de toast pour les erreurs de formulaire)
> - [ ] Definir les variables CSS pour les etats :
>   ```css
>   --hover-bg: #f8fafc;       /* slate-50 */
>   --active-bg: #f1f5f9;      /* slate-100 */
>   --loading-shimmer: #e2e8f0; /* slate-200 */
>   --error-text: #dc2626;      /* red-600 */
>   --error-bg: #fef2f2;        /* red-50 */
>   ```
