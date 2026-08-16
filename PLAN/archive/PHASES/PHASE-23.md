# PHASE-23 — Setup Playwright E2E

**Complexite** : M | **Mode** : Normal | **Prerequis** : toute la Phase 1 terminee (PHASE-01 a PHASE-21)

> **Impact PHASE-26g (2026-03-18)** : le bouton `#btn-toolbar-analyser` a ete supprime.
> Les tests E2E `test_11_confirmation_analyse.py` qui cliquent ce bouton sont obsoletes.
> Le nouveau flux de test est : ouvrir le drawer (E) → cliquer "Lancer une analyse"
> ou "Nouvelle analyse" → voir la confirmation dans `#drawer-contenu`.
> Les tests unitaires `test_phases.py` ont ete mis a jour (largeur 36rem, pas de bouton analyser,
> cible `#drawer-contenu`).

---

## 1. Contexte

Le projet n'a pas encore de tests end-to-end. Playwright permet de tester l'interface HTMX complete (arbre, lecture, import, extraction, config IA, charte visuelle) dans un navigateur reel. Cette phase pose l'infrastructure E2E et ecrit les premiers tests couvrant toutes les fonctionnalites de la Phase 1.

## 2. Prerequis

Toutes les etapes de la Phase 1 doivent etre terminees (PHASE-01 a PHASE-21).

## 3. Objectifs precis

- [ ] Configurer Playwright avec Django test server (`LiveServerTestCase` ou fixture)
- [ ] Creer les fixtures de donnees : pages de test, dossiers, analyseurs, extractions
- [ ] Configurer la CI pour les tests Playwright
- [ ] Tests E2E Phase 1 :
  - [ ] Arbre et navigation : creer dossier, classer page, naviguer
  - [ ] Lecture : ouvrir une page, verifier le contenu, acces direct (F5)
  - [ ] Import document : upload PDF, verifier la page creee
  - [ ] Import audio : upload MP3, polling, verifier transcription (mock)
  - [ ] Edition transcription : renommer locuteur, editer bloc, supprimer bloc
  - [ ] Extraction manuelle : selectionner texte, creer extraction
  - [ ] Config IA : toggle on/off, selectionner modele
  - [ ] Charte visuelle : verifier que les polices B612/B612 Mono/Lora/Srisakdi sont chargees
  - [ ] Cartes d'extraction : verifier couleur par famille d'hypostase, distinction machine (B612 Mono) vs citation (Lora italique)
  - [ ] Statuts de debat : verifier 4 couleurs texte distinctes (`#15803d`, `#B61601`, `#b45309`, `#C2410C`) + fonds pastels + ratio WCAG >= 4.5:1
  - [ ] Interventions lecteur : verifier Srisakdi 20pt sur le nom, 16pt sur le corps du commentaire
  - [ ] Scroll bidirectionnel : clic icone marge → scroll vers carte, clic carte → scroll vers texte
  - [ ] Etats interactifs : hover sur carte (fond change), empty state panneau vide (texte + CTA), loading skeleton pendant analyse mock
  - [ ] Variables CSS : verifier que `:root` contient les variables de surface, texte, bordure, hypostases, statuts, provenances (prerequis dark mode)
  - [ ] Layout : zone de lecture en pleine largeur, drawer s'ouvre en overlay au clic sur E, arbre s'ouvre en overlay au clic sur le menu
  - [ ] Cartes compactes : mode accordeon (une seule carte ouverte), indicateurs de densite (badge commentaires, epaisseur bordure)
  - [ ] Curation : masquer une extraction sans commentaire, verifier que le bouton "Masquer" est absent sur une extraction commentee, restaurer une extraction masquee
  - [ ] Mode focus : toggle avec `L`, centrage du texte, popup inline sur pastille, Escape pour fermer
  - [ ] Alignement basique : selectionner 3 pages, verifier le tableau croise hypostase x documents, verifier les gaps

## 4. Fichiers a modifier

- `tests/e2e/` — nouveau dossier avec les tests Playwright
- `pyproject.toml` — ajout de la dependance `playwright` et configuration
- `tests/e2e/conftest.py` — fixtures Django + Playwright
- `tests/e2e/fixtures/` — donnees de test (pages, dossiers, analyseurs)

## 5. Criteres de validation

- [ ] `uv run playwright install` installe les navigateurs sans erreur
- [ ] `uv run pytest tests/e2e/` lance les tests et ils passent tous
- [ ] Les fixtures creent un environnement de test complet (pages, dossiers, extractions)
- [ ] Les tests couvrent toutes les fonctionnalites listees dans la section 3
- [ ] La CI execute les tests E2E automatiquement

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Lancer `uv run pytest tests/e2e/ -v` (ou equivalent)**
   - **Attendu** : les tests passent en vert
2. **Les tests couvrent au minimum : chargement de la page d'accueil, ouverture de l'arbre, ouverture d'un document, lancement d'une extraction**
   - **Attendu** : chaque scenario est present dans la sortie des tests
3. **Verifier que les tests tournent en mode headless (pas de fenetre visible)**
   - **Attendu** : aucune fenetre navigateur ne s'ouvre pendant l'execution
4. **(Optionnel) Lancer en mode headed pour voir : `uv run pytest tests/e2e/ --headed`**
   - **Attendu** : une fenetre navigateur s'ouvre et execute les tests visuellement

## 6. Extraits du PLAN.md

> ### Etape 1.7 — Setup Playwright et premiers tests E2E
>
> **Actions** :
> - [ ] Configurer Playwright avec Django test server (`LiveServerTestCase` ou fixture)
> - [ ] Fixtures de donnees : pages de test, dossiers, analyseurs, extractions
> - [ ] CI : ajouter les tests Playwright au pipeline
> - [ ] Tests E2E Phase 1 :
>   - Arbre et navigation : creer dossier, classer page, naviguer
>   - Lecture : ouvrir une page, verifier le contenu, acces direct (F5)
>   - Import document : upload PDF, verifier la page creee
>   - Import audio : upload MP3, polling, verifier transcription (mock)
>   - Edition transcription : renommer locuteur, editer bloc, supprimer bloc
>   - Extraction manuelle : selectionner texte, creer extraction
>   - Config IA : toggle on/off, selectionner modele
>   - Charte visuelle : verifier que les polices B612/B612 Mono/Lora/Srisakdi sont chargees
>   - Cartes d'extraction : verifier couleur par famille d'hypostase, distinction machine (B612 Mono) vs citation (Lora italique)
>   - Statuts de debat : verifier 4 couleurs texte distinctes (`#15803d`, `#B61601`, `#b45309`, `#C2410C`) + fonds pastels + ratio WCAG >= 4.5:1
>   - Interventions lecteur : verifier Srisakdi 20pt sur le nom, 16pt sur le corps du commentaire
>   - Scroll bidirectionnel : clic icone marge → scroll vers carte, clic carte → scroll vers texte
>   - Etats interactifs : hover sur carte (fond change), empty state panneau vide (texte + CTA), loading skeleton pendant analyse mock
>   - Variables CSS : verifier que `:root` contient les variables de surface, texte, bordure, hypostases, statuts, provenances (prerequis dark mode)
>   - Layout : verifier que la zone de lecture est en pleine largeur, que le drawer s'ouvre en overlay au clic sur E, que l'arbre s'ouvre en overlay au clic sur ☰
>   - Cartes compactes : verifier le mode accordeon (une seule carte ouverte), les indicateurs de densite (badge commentaires, epaisseur bordure)
>   - Curation : masquer une extraction sans commentaire (verifier disparition), verifier que le bouton "Masquer" est absent sur une extraction commentee, restaurer une extraction masquee
>   - Mode focus : toggle avec `L`, verifier centrage du texte, popup inline sur pastille, Escape pour fermer
>   - Alignement basique : selectionner 3 pages, verifier le tableau croise hypostase × documents, verifier les gaps
>
> **Fichiers concernes** : nouveau dossier `tests/e2e/`, `pyproject.toml`
