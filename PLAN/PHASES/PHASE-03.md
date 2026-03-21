# PHASE-03 — Nettoyage code extraction

**Complexite** : S | **Mode** : Normal | **Prerequis** : aucun

---

## 1. Contexte

`run_langextract_job()`, `run_analyseur_on_page()`, et `analyser_page_task()` font des choses similaires avec du code duplique pour la construction des exemples LangExtract. Ce code duplique rend les evolutions fragiles (un changement doit etre repete en 2-3 endroits).

## 2. Prerequis

Aucun. Cette phase est independante.

## 3. Objectifs precis

- [ ] Extraire une fonction unique `_construire_exemples_langextract(analyseur)` dans `hypostasis_extractor/services.py`
- [ ] Supprimer `run_langextract_job()` si plus utilise (verifier tous les appels dans le projet)
- [ ] Faire de `analyser_page_task` le seul point d'entree pour les analyses (Celery)
- [ ] Verifier que les tests existants passent toujours

## 4. Fichiers a modifier

- `hypostasis_extractor/services.py` — extraire la fonction commune, supprimer le code duplique
- `front/tasks.py` — adapter `analyser_page_task` pour utiliser la nouvelle fonction

## 5. Criteres de validation

- [ ] Une seule fonction pour construire les exemples LangExtract
- [ ] `run_langextract_job()` supprime (ou justification si conserve)
- [ ] `analyser_page_task` est le seul point d'entree Celery pour les analyses
- [ ] Grep dans le projet : aucun appel restant a `run_langextract_job` (sauf la definition si conservee)
- [ ] `uv run python manage.py check` passe sans erreur

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document avec des extractions existantes** : cliquer sur un document dans l'arbre
   - **Attendu** : les cartes d'extraction s'affichent correctement, meme rendu qu'avant
2. **Lancer "Analyser" sur un document** : cliquer sur le bouton Analyser dans la zone de lecture
   - **Attendu** : l'extraction fonctionne, pas de doublon dans les resultats
3. **Verifier les extractions existantes** : revenir sur un document deja analyse
   - **Attendu** : les extractions existantes sont toujours la (pas de perte de donnees)

## 6. Extraits du PLAN.md

> ### Etape 1.1 — Nettoyage et deduplication du code d'extraction
>
> **Probleme** : `run_langextract_job()`, `run_analyseur_on_page()`, et `analyser_page_task()` font des choses similaires avec du code duplique pour la construction des exemples LangExtract.
>
> **Actions** :
> - [ ] Extraire une fonction unique `_construire_exemples_langextract(analyseur)` dans `hypostasis_extractor/services.py`
> - [ ] Supprimer `run_langextract_job()` si plus utilise (verifier les appels)
> - [ ] Faire de `analyser_page_task` le seul point d'entree pour les analyses (Celery)
>
> **Fichiers concernes** : `hypostasis_extractor/services.py`, `front/tasks.py`
