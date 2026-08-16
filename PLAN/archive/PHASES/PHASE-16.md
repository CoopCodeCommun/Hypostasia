# PHASE-16 — Onboarding et tooltips hypostases

**Complexite** : S | **Mode** : Normal | **Prerequis** : PHASE-12

---

## 1. Contexte

Un nouvel utilisateur arrive sur une page vide sans aucune indication de quoi faire. Le concept d'hypostase (PHENOMENE, CONJECTURE, INVARIANT) est puissant mais inhabituel — sans guidage, l'utilisateur traite les extractions comme des surligneurs et passe a cote du modele epistemique qui fait la valeur du produit. Le cycle deliberatif (Lecture -> Extraction -> Commentaire -> Debat -> Synthese) doit etre compris des la premiere session.

## 2. Prerequis

- **PHASE-12** : import de documents fonctionnel (pour que le parcours d'onboarding puisse guider vers l'import)

## 3. Objectifs precis

- [ ] **Etats vides guides** : quand la bibliotheque est vide, afficher un parcours en 4 etapes dans la zone de lecture :
  1. "Importez votre premier document" -> bouton import (texte, PDF, audio)
  2. "Lancez une extraction IA" -> explication en 1 phrase + bouton "Analyser"
  3. "Lisez les hypostases" -> explication de ce que sont les hypostases et pourquoi c'est different d'un surligneur
  4. "Commentez et debattez" -> explication du cycle deliberatif
  - Pas un tutoriel modal bloquant — juste l'etat vide de la zone de lecture. Disparait des que l'utilisateur a une page
  - S'integre avec les empty states de l'arbre vide, du panneau vide, du fil vide (chacun avec son message contextuel)
- [ ] **Tooltips sur les hypostases** : au survol d'une pastille d'hypostase dans les cartes d'extraction, un mini-tooltip affiche la definition en 1 phrase. Ex: *"Conjecture — Affirmation plausible non demontree"*
  - Les 29 definitions existent deja dans `HypostasisChoices` (`core/models.py:214-248`) -> les exposer via un template tag ou un dict dans le template
  - Attribut HTML `title` ou tooltip CSS/JS leger (pas de librairie externe)
- [ ] **Document exemple pre-charge** : livrer l'app avec un texte deja extrait et commente
  - L'utilisateur voit le resultat final (cartes d'extraction colorees, commentaires, statuts de debat) avant de creer le sien
  - Sert aussi de fixture pour les tests E2E Playwright — double usage
  - Commande `uv run python manage.py loaddata exemple_deliberation`
  - Illustre le cycle complet : texte source -> extractions typees -> commentaires -> au moins une restitution

## 4. Fichiers a modifier

- `front/templates/front/includes/lecture_principale.html` — etat vide guide (parcours 4 etapes)
- `front/templates/front/includes/` — empty states contextuels pour arbre, panneau, fil
- `hypostasis_extractor/templatetags/extractor_tags.py` — template tag pour tooltips hypostases
- `front/templates/front/includes/extraction_card.html` — attribut title sur les pastilles d'hypostase
- `front/fixtures/exemple_deliberation.json` — nouveau fichier fixture avec document exemple
- `front/static/front/js/` — tooltip JS leger si necessaire (pas de librairie externe)

## 5. Criteres de validation

- [ ] Premiere visite : l'etat vide guide s'affiche avec les 4 etapes dans la zone de lecture
- [ ] Apres import d'une page : l'etat vide disparait
- [ ] Survol d'une pastille d'hypostase : le tooltip affiche la definition en 1 phrase
- [ ] Chargement du document exemple (`loaddata`) : les cartes, commentaires et versions sont presents
- [ ] Les empty states contextuels s'affichent correctement (arbre vide, panneau vide, fil vide)

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Creer un compte fresh (ou vider les donnees) — ouvrir http://localhost:8000/**
   - **Attendu** : un parcours d'onboarding guide en 4 etapes (importer, analyser, commenter, synthetiser)
2. **Survoler un label d'hypostase (ex: "CONJECTURE")**
   - **Attendu** : un tooltip explique ce que c'est
3. **Ouvrir la liste des hypostases**
   - **Attendu** : les 29 definitions sont accessibles (tooltip ou modale)
4. **Un document exemple est pre-charge (fixture) pour que l'utilisateur puisse explorer immediatement**
   - **Attendu** : apres `uv run python manage.py loaddata exemple_deliberation`, un document avec extractions et commentaires est visible

## 6. Extraits du PLAN.md

> ### Etape 1.10 — Onboarding et etats vides intelligents
>
> **Pourquoi** : un nouvel utilisateur arrive sur une page vide. Aucune indication de quoi faire. Le concept d'hypostase (PHENOMENE, CONJECTURE, INVARIANT) est puissant mais inhabituel — sans guidage, l'utilisateur traite les extractions comme des surligneurs et passe a cote du modele epistemique qui fait la valeur du produit.
>
> Le cycle deliberatif (Lecture -> Extraction -> Commentaire -> Debat -> Synthese) est le coeur du produit. Si l'utilisateur ne comprend pas ce cycle des sa premiere session, il ne reviendra pas.
>
> **Actions** :
> - [ ] **Etats vides guides** : quand la bibliotheque est vide, afficher un parcours en 4 etapes dans la zone de lecture (import, extraction, lecture hypostases, commentaire/debat). Pas un tutoriel modal bloquant.
> - [ ] **Tooltips sur les hypostases** : au survol d'une pastille d'hypostase, mini-tooltip avec la definition. Les 29 definitions existent deja dans `HypostasisChoices` (`core/models.py:214-248`).
> - [ ] **Document exemple pre-charge** : fixture avec texte deja extrait et commente. Double usage : demo + tests E2E.
>
> **Fichiers concernes** : `front/templates/front/includes/lecture_principale.html` (etat vide guide), `hypostasis_extractor/templatetags/extractor_tags.py` (tooltips hypostases), `extraction_card.html` (attribut title), nouveau fixture `front/fixtures/exemple_deliberation.json`.
