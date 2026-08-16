# PHASE-02 — Assets locaux : polices, CDN, collectstatic

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-01

---

## 1. Contexte

Tailwind CSS est charge via CDN (`cdn.tailwindcss.com`). En mode hors-ligne ou si le CDN tombe, l'app est inutilisable. Les polices (Lora, B612, B612 Mono, Srisakdi) sont egalement chargees depuis Google Fonts. Cette phase self-hoste toutes les dependances et configure `collectstatic` pour un fonctionnement 100% offline.

## 2. Prerequis

- **PHASE-01** : le CSS et le JS doivent deja etre extraits dans des fichiers statiques. Sinon on modifie `base.html` deux fois pour la meme zone.

## 3. Objectifs precis

- [ ] Inventorier toutes les ressources chargees depuis un CDN (Tailwind, HTMX, SweetAlert2, fonts, icones)
- [ ] Telecharger ou compiler Tailwind en local (option : Tailwind CLI standalone, fichier CSS pre-compile)
- [ ] Verifier que HTMX est deja servi en local (sinon le telecharger)
- [ ] Telecharger les polices B612, B612 Mono, Srisakdi et Lora en local (formats woff2)
- [ ] Creer les `@font-face` declarations dans le CSS local
- [ ] Configurer `django.contrib.staticfiles` et `collectstatic` pour servir tout en local
- [ ] Supprimer toutes les references CDN de `base.html`
- [ ] Tester l'app avec acces internet coupe

## 4. Fichiers a modifier

- `front/templates/front/base.html` — supprimer les liens CDN, remplacer par `{% static %}`
- `front/static/front/fonts/` — nouveau repertoire avec les fichiers woff2
- `front/static/front/css/hypostasia.css` — ajouter les `@font-face` (ou fichier dedie `fonts.css`)
- `hypostasia/settings.py` — verifier/ajouter `STATIC_ROOT`, `STATICFILES_DIRS`
- `front/static/front/vendor/` — Tailwind CSS compile, HTMX, SweetAlert2 si necessaire

## 5. Criteres de validation

- [ ] Aucune requete vers un CDN externe dans l'onglet Network du navigateur
- [ ] L'app demarre et fonctionne normalement avec internet coupe
- [ ] `uv run python manage.py collectstatic --noinput` rassemble tous les fichiers
- [ ] Les polices B612, B612 Mono, Srisakdi et Lora s'affichent correctement
- [ ] Le build Tailwind (si CLI) produit un CSS complet

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Couper la connexion internet** (mode avion ou bloquer les CDN dans DevTools > Network > Block) puis recharger la page
   - **Attendu** : la page charge normalement avec toutes les polices (Lora, B612, B612 Mono, Srisakdi) visibles. Pas de FOUT ni de fallback serif/sans-serif
2. **Ouvrir DevTools > Network** : inspecter les requetes sortantes
   - **Attendu** : aucune requete vers fonts.googleapis.com, cdnjs.cloudflare.com, ou unpkg.com
3. **Ouvrir DevTools > Application > Fonts** : verifier l'origine des polices
   - **Attendu** : les polices sont servies depuis /static/

## 6. Extraits du PLAN.md

> ### Etape 1.5 — Assets statiques locaux (Tailwind, HTMX, fonts) et extraction CSS/JS
>
> **Probleme** : Tailwind CSS est charge via CDN (`cdn.tailwindcss.com`). En mode hors-ligne ou si le CDN tombe, l'app est inutilisable. C'est aussi un prerequis pour la Phase 9 (mode local).
>
> **Actions** :
> - [ ] Inventorier toutes les ressources chargees depuis un CDN (Tailwind, HTMX, SweetAlert2, fonts, icones)
> - [ ] Telecharger ou compiler Tailwind en local (option : Tailwind CLI standalone, fichier CSS pre-compile)
> - [ ] Verifier que HTMX est deja servi en local (sinon le telecharger)
> - [ ] Configurer `django.contrib.staticfiles` et `collectstatic` pour servir tout en local
> - [ ] Charger les polices B612, B612 Mono et Srisakdi (Google Fonts, puis fichiers locaux pour le mode offline)
> - [ ] Tester l'app avec acces internet coupe
>
> **Fichiers concernes** : templates (`bibliotheque.html`, `base.html`), `front/static/`, `hypostasia/settings.py`
