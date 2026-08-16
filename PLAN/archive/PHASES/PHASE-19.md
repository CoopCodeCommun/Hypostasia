# PHASE-19 — Heat map du debat sur le texte

> ⚠️ **DEPRECATED 2026-05-01 — YAGNI.** Personne ne s'en sert. Code, CSS, raccourci `H`,
> variables `--heatmap-*` et tests seront retires dans une session de cleanup dediee.
> La sous-phase 37d (heat map semantique) qui en dependait devient sans objet.
> Voir `../discussions/YAGNI 2026-05-01.md`.

**Complexite** : S | **Mode** : Normal | **Prerequis** : PHASE-09

---

## 1. Contexte

Les pastilles de marge indiquent ou se trouvent les extractions et quel est leur statut individuel. Mais elles ne montrent pas l'intensite du debat. Un passage avec 12 commentaires et 3 desaccords a la meme pastille qu'un passage avec 1 commentaire consensuel. La heat map resout ca en colorant le fond du texte selon l'intensite du debat : plus il y a de commentaires et de desaccords, plus le fond est chaud (rouge/orange). Les passages consensuels sont en vert pale. Les passages non extraits sont neutres. Ca donne une "temperature du texte" lisible en 2 secondes, particulierement utile pour les textes longs (20+ pages).

Cette heat map est la brique visuelle de base de la "geometrie du debat" — un concept plus large qui rend compte de la forme et de la sante d'un debat a l'echelle d'un dossier entier.

## 2. Prerequis

- **PHASE-09** : pastilles de marge et surlignage des extractions (les `<span class="hl-extraction">` doivent exister pour que la heat map puisse les colorer)

**Dependance souple** : PHASE-17 (mode focus) — si PHASE-17 est deja faite, implementer la compatibilite (heat map desactivee en mode focus). Sinon, laisser un TODO.

## 3. Objectifs precis

- [ ] Toggle "Heat map" dans la barre d'outils (icone thermometre ou flamme). Desactive par defaut — c'est un mode d'analyse, pas le mode de lecture normal
- [ ] Le fond colore est applique sur les `<span class="hl-extraction">` existants via une classe CSS supplementaire `.heatmap-active`
- [ ] **Calcul de la temperature** :
  - Score par passage = `(nombre_commentaires * 1) + (nombre_statuts_non_consensuels * 3)`
  - Normalise sur une echelle 0-1 (0 = consensuel sans commentaire, 1 = maximum du document)
  - Mapping couleur :
    - Score 0 -> `--statut-consensuel-bg` (vert pale `#f0fdf4`)
    - Score 0.3 -> `--heatmap-tiede` (jaune pale `#fefce8`)
    - Score 0.6 -> `--heatmap-chaud` (orange pale `#fff7ed`)
    - Score 1.0 -> `--heatmap-brulant` (rouge pale `#fef2f2`)
    - Pas d'extraction -> pas de fond (neutre)
- [ ] La couleur de fond est calculee cote serveur (dans `front/utils.py` ou `front/views.py`) et injectee en `style="background-color: ..."` sur chaque span
- [ ] Quand la heat map est active, les pastilles de marge restent visibles (double signal : couleur marge = statut, couleur fond = intensite)
- [ ] L'etat du toggle est persiste en `localStorage`
- [ ] Compatible avec le mode focus (PHASE-17) : en mode focus, la heat map est desactivee (lecture pure)

## 4. Fichiers a modifier

- `front/utils.py` — calcul du score de temperature + injection CSS par passage
- `front/views.py` — LectureViewSet : passage du flag heatmap au template
- `front/static/front/css/hypostasia.css` — CSS variables pour la palette heat map (`--heatmap-tiede`, `--heatmap-chaud`, `--heatmap-brulant`), classe `.heatmap-active`
- `front/static/front/js/marginalia.js` — toggle heat map (ajout/retrait de la classe)
- `front/templates/front/includes/lecture_principale.html` — bouton toggle dans la barre d'outils

## 5. Criteres de validation

- [ ] Activer la heat map : les passages extraits ont un fond colore selon l'intensite
- [ ] Un passage avec beaucoup de commentaires a un fond plus chaud qu'un passage consensuel
- [ ] Les passages non extraits n'ont pas de fond
- [ ] Desactiver la heat map : les fonds disparaissent
- [ ] Mode focus + heat map : la heat map est desactivee en mode focus
- [ ] Le calcul du score est correct : `(commentaires * 1) + (statuts_non_consensuels * 3)`

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document avec beaucoup d'extractions de statuts varies**
   - **Attendu** : le document se charge avec les pastilles de marge visibles
2. **Activer la heat map (bouton dans la toolbar ou raccourci)**
   - **Attendu** : le fond du texte est colore par intensite — les passages tres debattus sont plus colores (rouge/orange), les passages consensuels sont verts, les passages sans extraction sont neutres
3. **Survoler un passage colore**
   - **Attendu** : un tooltip montre le score (nb commentaires, nb desaccords)
4. **Verifier que la heat map est compatible avec le mode focus : activer L — la heat map disparait. Desactiver L — elle revient.**
   - **Attendu** : en mode focus la heat map est desactivee, elle se reactive a la sortie du mode focus

## 6. Extraits du PLAN.md

> ### Etape 1.15 — Heat map du debat sur le texte
>
> **Argumentaire** : les pastilles de marge indiquent **ou** se trouvent les extractions et **quel** est leur statut individuel. Mais elles ne montrent pas l'**intensite** du debat. Un passage avec 12 commentaires et 3 desaccords a la meme pastille qu'un passage avec 1 commentaire consensuel.
>
> La heat map resout ca en colorant le **fond du texte** selon l'intensite du debat :
> - Plus il y a de commentaires et de desaccords sur un passage, plus le fond est **chaud** (rouge/orange)
> - Les passages consensuels sont en **vert pale**
> - Les passages non extraits sont **neutres** (pas de fond)
>
> **Calcul de la temperature** :
> - Score par passage = `(nombre_commentaires * 1) + (nombre_statuts_non_consensuels * 3)`
> - Normalise sur une echelle 0-1
> - Mapping couleur : Score 0 -> vert pale, Score 0.3 -> jaune pale, Score 0.6 -> orange pale, Score 1.0 -> rouge pale
>
> **Actions** :
> - [ ] Toggle "Heat map" dans la barre d'outils. Desactive par defaut
> - [ ] Fond colore sur les `<span class="hl-extraction">` via classe `.heatmap-active`
> - [ ] Couleur calculee cote serveur, injectee en `style="background-color: ..."`
> - [ ] Pastilles de marge restent visibles (double signal)
> - [ ] Etat persiste en `localStorage`
> - [ ] Compatible avec le mode focus (desactivee en mode focus)
>
> **Fichiers concernes** : `front/utils.py` (calcul du score), `front/views.py` (flag heatmap), `marginalia.js` (toggle), CSS variables pour la palette.
