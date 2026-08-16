# PHASE-29 : Synthese deliberative dans le drawer + bool est_par_defaut + fix WebSocket OOB + audit HTMX (alpha:0.3.1)

**Date :** 2026-04-29
**Migration :** Oui

**Quoi / What:** Refonte UX complete de la synthese deliberative dans le drawer (miroir
du flow extraction), avec markdown server-side, sélecteur d'analyseurs en boutons,
notification cross-page via WebSocket, audit HTMX complet et nombreux fix adjacents.

**Pourquoi / Why:** Le modal de synthese etait construit en JS (anti-pattern djc) et
manquait l'estimation prix / le prompt complet / la gate Stripe. L'utilisateur voulait
le meme niveau d'information que pour l'extraction. Les bool `inclure_extractions` et
`inclure_texte_original` etaient sauvegardes mais ignores par la tache Celery.
Long audit HTMX en fin de session pour stabiliser les retours et ne plus avoir de
"bordel" dans les comportements selon la page.

### Changements principaux / Main changes

1. **Endpoint `previsualiser_synthese`** sur `PageViewSet` : calcule estimation tokens
   (50% output, sans chunking), consensus complet (compteurs + bloquantes), compteurs
   d'extractions/commentaires disponibles, gate Stripe, conditions de blocage.
2. **Drawer de confirmation** (`confirmation_synthese.html`) : selecteur d'analyseur,
   encart consensus, infos analyseur, estimation, bouton « Voir le prompt complet ».
3. **Polling drawer** : `synthese_en_cours_drawer.html` (spinner pendant la synthese,
   message d'erreur + retry sinon). Auto-fermeture du drawer + chargement V2 en zone-lecture
   via `HX-Trigger: fermerDrawer` + OOB sur `#zone-lecture`.
4. **Bool `est_par_defaut`** sur l'analyseur (un par type) : `save()` decoche
   automatiquement les autres du meme type. Toast info quand un autre est decoche.
5. **Bool `inclure_extractions` / `inclure_texte_original`** branches dans
   `_construire_prompt_synthese` : sections injectees selon les bool de l'analyseur.
   Validation « au moins l'un des deux » dans la vue.
6. **Helper `_calculer_consensus(page)`** extrait de la vue dashboard, reutilise par
   le drawer de confirmation.
7. **WebSocket synthese terminee** : la tache Celery envoie au groupe
   `notifications_user_{user.pk}` un message `synthese_terminee`. Le `NotificationConsumer`
   emet un toast OOB cliquable « Voir la version V{N} ». Notification cross-page : meme
   si l'utilisateur a navigue ailleurs, il est notifie.
8. **Tableau analyseurs** dans `/api/analyseurs/` : Nom / Type / Texte / Extractions /
   Actif / Defaut. La liste affiche TOUS les analyseurs (actifs et inactifs).
   Le filtre `is_active=True` ne s'applique qu'au selecteur du drawer.
9. **Markdown server-side pour la synthese** : ajout de la lib `markdown` Python.
   Le prompt impose explicitement le format markdown (titres, gras, citations,
   listes). Le rendu HTML passe par `html.escape()` puis `markdown.markdown(...)` :
   securite XSS preservee + structure HTML propre. Avant : split paragraphes nu.
10. **Selecteur d'analyseur en boutons** dans le drawer (vs select deroulant).
    Titre « Quel moteur utiliser ? » + sous-titre explicatif. Bouton actif en violet,
    etoile bleue pour le defaut. Au clic = recharge le drawer (estimation/prompt
    re-calcules pour le nouvel analyseur).
11. **Bouton « Voir le prompt complet »** deplace juste sous le selecteur d'analyseur
    pour comparer rapidement les prompts entre moteurs.
12. **Toggle `is_active` dans l'editeur d'analyseur** : permet de desactiver un
    analyseur sans le supprimer (il reste visible dans la liste mais exclu du
    selecteur du drawer).
13. **Bouton « Supprimer cette version »** dans `lecture_principale.html` (a cote
    de Historique) : visible uniquement si `parent_page` non-null ET utilisateur
    proprietaire du dossier. Action `LectureViewSet.destroy()` qui refuse :
    (a) la racine, (b) les versions avec commentaires (preserve le travail
    collaboratif), (c) les non-proprietaires. Apres suppression : `HX-Location`
    vers la racine.
14. **Empecher l'import sans connexion** : `data-user-authenticated` sur `<body>`
    + guard JS sur les 3 inputs d'import (toolbar, overlay, onboarding) qui
    dispatch `authRequise` -> SweetAlert connexion.
15. **URL push apres import** : header `X-Hypostasia-Page-Url` cote serveur +
    `history.pushState()` cote JS. L'URL change apres import (avant : restait
    sur l'ancien document).
16. **Titre de version = nom de l'analyseur** : `version_label = analyseur_synthese.name`
    (ex: « V2 - Mathemagique » au lieu de « V2 - Synthese deliberative »).
    Permet de distinguer les versions selon l'analyseur utilise.
17. **Audit HTMX en fin de session** : 3 agents Explore deployes en parallele
    pour cartographier les `hx-target`/`hx-swap-oob`, valider les fallbacks F5
    (15/15 vues OK), et tracer les flows analyse + synthese. Resultat : projet
    globalement sain, 3 vrais problemes corriges (voir ci-dessous).

### Ameliorations issues de l'audit HTMX (fin de session)

| # | Action | Resolution |
|---|---|---|
| P1 | Polling synthese qui continue apres navigation cross-page (fuite ~60 requetes inutiles sur 3 min) | Filtre conditionnel `every 3s [document.querySelector('#zone-lecture [data-page-id]')?.dataset.pageId === '{{ page.pk }}']` : HTMX evalue la condition a chaque tick, pas de requete si l'utilisateur a navigue ailleurs |
| P3 | OOB complexe `synthese_terminee_oob.html` (3 swaps + HX-Trigger) en fin de synthese | Remplace par `HX-Location` natif HTMX vers `/lire/V{N}/` + `HX-Trigger fermerDrawer`. URL pushed proprement, etat coherent, pas d'OOB fragile. Partial supprime |
| P5 | `comparer_hypostases` sans fallback F5 (URL partagee = page nue) | Si non-HTMX, redirige vers la vue parente `/lire/{pk}/comparer/?v2=...` qui affiche l'onglet correctement |
| Doublon | Toast `Synthese terminee` envoye deux fois (SweetAlert + WS) | Retire le SweetAlert de `synthese_status` completed, garde le toast WS qui est plus riche (lien cliquable) |
| Cohérence | Liste/api/analyseurs/ filtrait `is_active=True` (analyseurs disparaissaient) | Affiche TOUS les analyseurs, le filtre `is_active=True` ne s'applique qu'au selecteur du drawer |

### Bugs corriges / Bugs fixed

| Bug | Cause | Fix |
|---|---|---|
| Option « Synthetiser » absente du formulaire de creation | `hypostasia.js:273-277` n'avait que 3 options dans le SweetAlert | +1 option |
| Analyseur disparait apres save | `BooleanField(required=False)` de DRF rempli `validated_data` avec `False` quand le PATCH est en form-urlencoded sans le champ. Le `setattr` desactivait alors `is_active` | `partial_update` ne setter QUE les champs explicitement dans `request.data.keys()` |
| `analyseurId is not defined` dans le JS de l'editeur | La variable etait declaree dans le scope local d'un callback de click | Hisser au scope du IIFE global |
| Le toast WS HTMX ne s'affichait jamais | `htmx-ext-ws-2.0.4` ne gere pas la syntaxe courte `<div id="X" hx-swap-oob="beforeend">`. Bug touchait aussi `notification` standard du projet | Utiliser la syntaxe explicite `<div hx-swap-oob="beforeend:#X">` |
| Migration `synthetiser` manquante | Le model avait 4 types mais la migration 0011 n'en avait que 3 | Migration `0025_alter_analyseursyntaxique_type_analyseur.py` (ajoutee dans le merge precedent) |
| `analyseurId is not defined` dans le JS de l'editeur (callbacks externes au scope) | Variable declaree dans le scope local d'un callback de click | Hisser au scope du IIFE global |
| Selecteur d'analyseur de synthese : changement non pris en compte | `hx-vals` codait l'ID au render serveur (capture statique) | Switch vers `hx-include="#select-analyseur-synthese"` (lecture LIVE), puis remplace par boutons (rechargement complet du drawer a chaque clic) |
| `bg-violet-400` invisible (toggle, pastille) | Pas dans le subset Tailwind compile du projet | Switch vers `bg-violet-500` (present) |
| `peer-checked:bg-emerald-500` ne se colore pas | Variant non genere par Tailwind | Switch vers `peer-checked:bg-blue-500` (present) |
| Commentaires Django multi-lignes visibles dans le HTML | `{# ... #}` ne fonctionne QUE sur une ligne en Django (test reproduit) | Switch vers `{% comment %}...{% endcomment %}` (1 occurrence trouvee dans `synthese_en_cours_drawer.html`) |
| Lien navbar `/api/analyseurs/` bug HTMX (JS auto-save ne se re-bind pas correctement apres swap) | `hx-get` HTMX au lieu d'un GET classique | Retire les attributs HTMX → navigation classique avec full page reload |
| Toast info `est_par_defaut` decoche → ne s'affichait pas | `fetch().then()` ne propageait pas le HX-Trigger du serveur | Lecture du header HX-Trigger dans `.then()` + `dispatchEvent(new CustomEvent(name, {detail}))` |

### Fichiers crees / Created files

| Fichier / File | Description |
|---|---|
| `front/templates/front/includes/confirmation_synthese.html` | Partial confirmation drawer (estimation, consensus, prompt, selecteur boutons) |
| `front/templates/front/includes/synthese_en_cours_drawer.html` | Partial polling (spinner / erreur retry) avec filtre conditionnel anti-zombie |
| `front/templates/front/includes/ws_synthese_terminee.html` | Toast WS cross-page envoye par le `NotificationConsumer` |
| `front/tests/test_phase29_synthese_drawer.py` | 20 tests unitaires |
| `hypostasis_extractor/migrations/0026_analyseursyntaxique_est_par_defaut.py` | Migration auto |
| `docs/superpowers/specs/2026-04-29-synthese-drawer-confirmation-design.md` | Spec brainstorming |
| `docs/superpowers/plans/2026-04-29-synthese-drawer-confirmation.md` | Plan d'implementation 14 taches |

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | +champ `est_par_defaut` + override `save()` pour decocher les autres du meme type |
| `hypostasis_extractor/serializers.py` | +`est_par_defaut` dans `AnalyseurSyntaxiqueUpdateSerializer` |
| `hypostasis_extractor/views.py` | `partial_update` : ne setter que les champs envoyes (fix bug DRF) + toast info `est_par_defaut`. `list` affiche TOUS les analyseurs (plus de filtre `is_active=True`) |
| `hypostasis_extractor/templates/.../analyseur_editor.html` | +option `synthetiser`, +toggle est_par_defaut, label « extractions et leurs commentaires », hisser `analyseurId`, propagation HX-Trigger via fetch.then |
| `hypostasis_extractor/templates/.../configuration_llm.html` | Liste → tableau (Nom/Type/Actif/Defaut) |
| `hypostasis_extractor/templates/.../includes/analyseur_item.html` | Refait en `<tr>` avec colonnes |
| `front/views.py` | Helper `_calculer_consensus` extrait. Nouvelle action `previsualiser_synthese`. `synthetiser` (POST) renvoie partial drawer + `HX-Trigger: ouvrirDrawer`. `synthese_status` adapte (3 branches drawer + OOB completed + fermerDrawer) |
| `front/tasks.py` | `_construire_prompt_synthese(page, job, analyseur)` (3e arg). Sections conditionnees aux bool. Guard `dernier_job_analyse=None`. `synthetiser_page_task` envoie au groupe utilisateur `notifications_user_{pk}` un signal `synthese_terminee` |
| `front/consumers.py` | +handler `synthese_terminee` qui rend le toast WS |
| `front/templates/front/includes/ws_toast.html` | Syntaxe corrigee `hx-swap-oob="beforeend:#ws-toasts"` (resout aussi le bug global de tous les toasts WS du projet) |
| `front/templates/front/includes/dashboard_consensus.html` | Bouton synthese : `hx-get` direct vers `previsualiser_synthese` (suppression `onclick="ouvrirModaleSynthese"`) |
| `front/templates/front/includes/carte_analyseur.html` | +badge « Par defaut » et badge type `synthetiser` (etait manquant) |
| `front/templates/front/includes/detail_analyseur_readonly.html` | Idem |
| `front/static/front/js/hypostasia.js` | +option `synthetiser` au SweetAlert. +listener `fermerDrawer`. `ouvrirPanneauDroit` appelle `ouvrir(false)` pour ne pas ecraser le contenu pre-swap |
| `front/static/front/js/dashboard_consensus.js` | Suppression de `ouvrirModaleSynthese` et `fermerModaleSynthese` (anti-pattern JS-built HTML) |
| `front/static/front/js/drawer_vue_liste.js` | `ouvrirDrawer(rechargerLeContenu=true)` ne charge le contenu que si demande explicitement |
| `front/management/commands/charger_fixtures_demo.py` | `est_par_defaut=True` sur les 3 analyseurs demo |

### Fichiers supprimes / Deleted files

- `front/templates/front/includes/synthese_en_cours.html` (remplace par `synthese_en_cours_drawer.html`)
- `front/templates/front/includes/synthese_terminee_oob.html` (remplace par `HX-Location` natif HTMX en fin de session)

### Dependances ajoutees / New dependencies

- `markdown==3.10.2` (pyproject.toml) — parser markdown server-side pour le rendu de la synthese

### WebSocket — flux complet

Le WS pre-existant `NotificationConsumer` (route `/ws/notifications/`) est connecte sur
toutes les pages via `<div ws-connect="/ws/notifications/">` dans `base.html`, avec un
groupe par utilisateur (`notifications_user_{user.pk}`). Il reste connecte cross-page
tant que le navigateur ne ferme pas l'onglet. PHASE-29 reutilise ce mecanisme :

```
1. Utilisateur clique "Lancer la synthèse" dans le drawer.
2. POST /lire/{pk}/synthetiser/ → cree un ExtractionJob + Celery .delay()
3. Celery (synthetiser_page_task) :
   - construit le prompt selon les bool de l'analyseur
   - appelle le LLM
   - cree une Page enfant V2
   - emet : envoyer_progression_websocket(
         f"notifications_user_{owner.pk}",
         "synthese_terminee",
         {"page_synthese_id": ..., "version_number": ..., "titre_page": ...},
     )
4. NotificationConsumer.synthese_terminee() rend ws_synthese_terminee.html et
   envoie le HTML au client via WebSocket.
5. htmx-ext-ws receptionne, applique les OOB swaps :
   - <div hx-swap-oob="beforeend:#ws-toasts">...</div> → ajoute un toast cliquable
6. Le toast contient un lien hx-get vers la V2 → clic = chargement zone-lecture.
```

**Piege OOB important** : la syntaxe courte `<div id="ws-toasts" hx-swap-oob="beforeend">`
ne marche PAS avec `htmx-ext-ws-2.0.4`. Toujours utiliser la syntaxe explicite
`<div hx-swap-oob="beforeend:#ws-toasts">`.

### Tests / Tests

- 20 nouveaux tests unitaires (`test_phase29_synthese_drawer.py`)
- 38 tests `test_phase28_light` adaptes au nouveau flux drawer
- Total : 74 tests verts (`phase29` + `phase28_light` + `analyse_drawer_unifie`)
- Pas de tests E2E (projet en alpha)

### Decisions de design / Design decisions

- **Approche miroir extraction** plutot que generique unifie (YAGNI, djc privilegie le verbeux et lisible top-to-bottom).
- **Bool `est_par_defaut` par type** (vs default global) — chaque type a son contexte.
- **Polling drawer + WS** : le polling rafraichit en temps reel quand l'utilisateur reste sur la page ; le WS notifie cross-page. Les deux mecanismes coexistent comme dans le flux extraction. **MAIS** le polling est protege par un filtre conditionnel JS qui le pause si l'utilisateur a navigue ailleurs.
- **Pas de bouton Annuler explicite** dans la confirmation — la croix du drawer ou Escape suffisent.
- **Auto-fermeture du drawer en fin de synthese** + bascule auto sur la V2 via `HX-Location` natif HTMX (vs OOB complexes).
- **Ratio output 50%** comme l'extraction (a affiner apres mesure reelle).
- **Selecteur d'analyseur en boutons** plutot qu'en `<select>` : indique mieux le choix possible et permet d'afficher visuellement le defaut (etoile bleue).
- **Audit HTMX** : conserver le pattern `polling drawer + WS cross-page` plutot que tout migrer vers WS-only. Defense en profondeur, le WS peut tomber, le polling rattrape. Cout de la refonte > benefice marginal.

### Pieges documentes / Documented pitfalls

- **`htmx-ext-ws-2.0.4` syntaxe OOB** : la forme courte `<div id="X" hx-swap-oob="beforeend">` ne marche PAS, il faut la forme explicite `<div hx-swap-oob="beforeend:#X">`. Bug reproduit, fix dans `ws_toast.html` et `ws_synthese_terminee.html`.
- **DRF + form-urlencoded + `BooleanField(required=False)`** : DRF rempli `validated_data` avec `False` pour les BooleanField non envoyes, ce qui peut desactiver des champs accidentellement. Solution : `partial_update` ne setter que les champs explicitement dans `request.data.keys()`.
- **Django commentaires `{# #}`** : ne fonctionnent QUE sur une seule ligne. Multi-ligne = `{% comment %}...{% endcomment %}` obligatoire (sinon le commentaire apparait visible dans le HTML rendu).
- **Subset Tailwind** : seules certaines variantes de couleurs/peer-checked sont compilees. Verifier avec `grep` dans `tailwind.css` avant d'utiliser une classe rare.
- **Polling HTMX et navigation** : le polling continue dans le DOM masque apres swap de la zone-lecture. Solution : filtre conditionnel `every Ns [expr]` qui pause si conditions non remplies.

### Migration

- **Migration necessaire / Migration required:** Oui — `0026_analyseursyntaxique_est_par_defaut.py`
- `docker exec hypostasia_web uv run python manage.py migrate`

