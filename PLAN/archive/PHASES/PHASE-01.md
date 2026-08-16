# PHASE-01 — Extraction CSS/JS depuis base.html

**Complexite** : M | **Mode** : Normal | **Prerequis** : aucun

---

## 1. Contexte

Tout le CSS (~219 lignes) et tout le JS (~1260 lignes) sont inline dans `base.html`, ce qui rend le design difficile a iterer. Extraire ces blocs dans des fichiers statiques separes est un prerequis pour toute evolution CSS/JS future (PHASE-02, PHASE-07).

## 2. Prerequis

Aucun. Cette phase est independante.

## 3. Objectifs precis

- [ ] Creer la structure `front/static/front/css/` et `front/static/front/js/` (le repertoire `front/static/` n'existe pas encore)
- [ ] Extraire le CSS inline de `base.html` dans `front/static/front/css/hypostasia.css`
- [ ] Extraire le JS inline de `base.html` dans `front/static/front/js/hypostasia.js`
- [ ] Remplacer les blocs `<style>` et `<script>` inline par des `{% static %}` links
- [ ] Verifier que les references HTMX (`hx-headers`, CSRF token) continuent de fonctionner
- [ ] Verifier que le JS utilise par d'autres templates (includes) est toujours accessible

## 4. Fichiers a modifier

- `front/templates/front/base.html` — supprimer les blocs inline, ajouter les liens static
- `front/static/front/css/hypostasia.css` — nouveau fichier, CSS extrait
- `front/static/front/js/hypostasia.js` — nouveau fichier, JS extrait

## 5. Criteres de validation

- [ ] `base.html` ne contient plus de `<style>` ni de `<script>` inline (sauf eventuellement le CSRF token inline si necessaire)
- [ ] L'app demarre sans erreur avec `uv run python manage.py runserver`
- [ ] `uv run python manage.py collectstatic --noinput` fonctionne
- [ ] L'interface fonctionne comme avant (arbre, lecture, extractions, overlay)
- [ ] Le navigateur charge bien les fichiers `.css` et `.js` (verifier dans l'onglet Network)

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir http://localhost:8000/** : la page charge normalement
   - **Attendu** : aucune erreur dans la console, le rendu est identique a avant
2. **Ouvrir DevTools > onglet Network** : filtrer par CSS et JS
   - **Attendu** : les fichiers `hypostasia.css` et `hypostasia.js` (ou noms choisis) apparaissent comme requetes separees — pas de `<style>` inline dans le HTML
3. **Ouvrir DevTools > onglet Sources** : naviguer vers les fichiers JS
   - **Attendu** : on peut lire et debugger les fichiers JS separement
4. **Naviguer dans l'arbre, ouvrir un document, lancer une extraction** : parcourir le flux complet
   - **Attendu** : tout fonctionne comme avant (arbre, lecture, extractions, overlay)

## 6. Extraits du PLAN.md

> ### Etape 1.5 — Assets statiques locaux (Tailwind, HTMX, fonts) et extraction CSS/JS
>
> **Probleme** : Tailwind CSS est charge via CDN (`cdn.tailwindcss.com`). En mode hors-ligne ou si le CDN tombe, l'app est inutilisable. C'est aussi un prerequis pour la Phase 9 (mode local). De plus, tout le CSS (219 lignes) et tout le JS (~1260 lignes) sont inline dans `base.html`, ce qui rend le design difficile a iterer.
>
> **Actions** :
> - [ ] Extraire le CSS inline de `base.html` dans `front/static/front/css/hypostasia.css`
> - [ ] Extraire le JS inline de `base.html` dans `front/static/front/js/hypostasia.js`
>
> **Fichiers concernes** : templates (`bibliotheque.html`, `base.html`), `front/static/`, `hypostasia/settings.py`
