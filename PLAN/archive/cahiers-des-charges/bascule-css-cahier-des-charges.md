# Bascule CSS — cahier des charges

**Statut** : document de travail, à relire et à arbitrer par le propriétaire
avant exécution. Rien n'est engagé.

**Décision du propriétaire (9 août 2026)** : « On peut vraiment tout changer,
l'app n'est qu'en phase de prototype. L'ancien CSS est à jeter si besoin. Le
nouveau design, celui de la maquette, est très bon. Il faut juste s'assurer
qu'on ne perde pas en feature. »

**Placement** : chantier dédié, **juste avant la phase H de
`SPEC-synthese-carnet.md`** (§ 13 : « UI : onglets Wikis / Synthèses du carnet,
article, panneau de preuve »). La raison est simple : la phase H construit trois
écrans neufs (article de wiki, synthèse dirigée, panneau de preuve) qui
n'existent **que** dans l'étalon `tmp/maquettes/corpus.html`. Les bâtir sur
l'ancien CSS reviendrait à les écrire deux fois.

**Méthode de rédaction** : lecture de code seule. Aucun navigateur Playwright,
aucun test lancé (serveur 8 Go partagé avec la prod). Toutes les affirmations de
ce document sont vérifiables par lecture d'un fichier nommé, à une ligne nommée.

---

## 0. Le périmètre en trois chiffres

| Matière | Volume | Fichier(s) |
|---|---|---|
| CSS maison | **1 985 lignes**, 28 sections numérotées | `front/static/front/css/hypostasia.css` |
| CSS inline dans les templates | **691 lignes** réparties sur 4 fichiers | cf. § 1.7 |
| Tailwind compilé | 68 Ko minifié (v4.2.1 + plugin typography) | `front/static/front/css/tailwind.css`, source `front/tailwind/input.css` |
| Templates du front | **5 679 lignes** (44 fichiers) | `front/templates/front/**` |
| Templates de l'extracteur rendus dans le front | **1 949 lignes** (28 fichiers) | `hypostasis_extractor/templates/**` |
| JavaScript maison | **4 495 lignes** (11 fichiers) | `front/static/front/js/**` |
| Étalon de design | **5 872 lignes** (3 maquettes + données) | `tmp/maquettes/**` |
| Tests qui figent le HTML/CSS/JS | **537 tests** dans un seul fichier | `front/tests/test_phases.py` |

Ordre de grandeur : **~7 600 lignes de gabarit** à re-habiller, **~2 700 lignes
de CSS** à remplacer, contre **~2 000 lignes de CSS d'étalon** (dont ~250
triplées entre les trois maquettes, cf. audit du 8 août, « Transverse »).

---

# 1. Inventaire exhaustif des features visibles — la liste « à ne pas perdre »

Chaque entrée donne : la route réelle, la vue, le template, ce que l'utilisateur
peut y faire, les dépendances HTMX/JS, les `data-testid`. C'est la grille de
recette de la bascule : un écran n'est « basculé » que si toutes les actions de
sa ligne fonctionnent encore.

## 1.1 Point structurant : il n'y a pas d'héritage de template

`front/urls.py` (41 lignes) ne contient **aucune `path()` classique** hormis la
racine : tout passe par un `DefaultRouter` DRF sur 17 `viewsets.ViewSet` avec des
`@action`. Les noms d'URL sont générés (`front:<basename>-<action>`).

`front/templates/front/base.html` (362 lignes) **ne contient aucun `{% block %}`**.
C'est un document HTML monolithique dont la zone `<main id="zone-lecture">`
(lignes 292-320) commute entre **12 contenus** par une cascade
`{% if %}/{% elif %}` sur des variables `*_preloaded` :

```
historique_preloaded → diff_preloaded → versions_list_preloaded →
versions_diff_preloaded → configuration_llm_preloaded → acces_refuse_message →
analyseur_preloaded → carnet_preloaded → carnets_liste_preloaded →
base_preloaded → bases_liste_preloaded → page_preloaded → (sinon) onboarding_vide
```

`front/templates/front/bibliotheque.html` fait **1 ligne** (`{% extends
"front/base.html" %}`, aucun bloc) : c'est une coquille.

**Conséquence** : la bascule n'a pas d'arbre d'héritage à respecter, mais une
page unique portant ~14 conteneurs permanents dans le DOM, présents même quand
ils sont vides. Ce sont les cibles CSS structurantes :

`<nav>` toolbar (h-12) · `#dashboard-consensus-dropdown` · `#arbre-backdrop` ·
`#arbre-overlay` (20rem, `-translate-x-full`) · `#arbre-ctx-menu` ·
`.arbre-footer` · `#drawer-backdrop` · `#drawer-overlay` (`min(36rem,100vw)`,
`translate-x-full`) · `#bottom-sheet-backdrop` · `#bottom-sheet` ·
`#bottom-sheet-contenu` · `#alignement-modale-container` · `#zone-lecture` ·
`#sidebar-right` (`class="hidden"`, conservée **uniquement** comme cible d'OOB
swaps) · `#selection-menu`.

Assets, tous locaux (aucun CDN — c'est un invariant testé par
`Phase02AucunCDNTest`) : `tailwind.css?v=10`, `hypostasia.css?v=34`,
`htmx-2.0.4.min.js`, `sweetalert2-11.min.js`, puis 11 scripts maison avec
cache-busting manuel `?v=NN`. **Pas d'Alpine, pas de Sortable, pas de jQuery.**

## 1.2 Écrans plein cadre

### A. Accueil / onboarding — `GET /`
`views.BibliothequeViewSet.list` (`front/views.py:945`) →
`front/templates/front/bibliotheque.html`, ou en HTMX
`front/templates/front/includes/onboarding_vide.html` (326 lignes).

Actions : parcourir l'onboarding en 4 étapes ; basculer l'onglet « Découvrir
l'app » / « Manifeste » (`onclick` inline, toggle `.hidden`) ; importer un
fichier (`#input-import-fichier-onboarding`) ; lire la légende des statuts
(redondante forme + couleur) et la liste des raccourcis.
Include : `front/templates/front/includes/manifeste.html` (283 lignes).
`data-testid` : `onglets-accueil`, `onglet-decouvrir`, `onglet-manifeste`,
`onboarding-guide`, `onboarding-step-1..4`, `manifeste-article`, `-these`,
`-pourquoi`, `-ostrom`, `-codecommun`, `-principes`, `-trajectoire`.
**CSS inline : 187 lignes** (`onboarding_vide.html:133-319`) + **110 lignes**
(`manifeste.html:174-283`).

### B. Lecture d'une note — `GET /lire/{pk}/`
`LectureViewSet.retrieve` (`front/views.py:975`) →
`front/templates/front/includes/lecture_principale.html` (188 lignes).
C'est **l'écran central du produit**. Actions :

- éditer le titre au clic (`.titre-page-cliquable` → JS pur dans
  `hypostasia.js`, POST `/lire/{pk}/modifier_titre/`, réponse OOB sur
  `#titre-toolbar`) ;
- télécharger la source (`/lire/{pk}/telecharger_source/`) ;
- menu Exporter (`onclick` inline) : export JSON (audio seulement), export
  Markdown, « Copier en Markdown » (`navigator.clipboard`, `hypostasia.js:889`) ;
- bloc « Dans N carnets », chargé en lazy HTMX
  (`hx-get="/notes/{pk}/carnets/bloc/" hx-trigger="load"`) ;
- switcher de versions (`#pill-version-{pk}`), **Comparer**, **Historique**,
  **Supprimer cette version** (`hx-delete` + `hx-confirm`, conditionné par
  `page|est_moderable_par:user`) ;
- sélectionner du texte → menu flottant `#selection-menu` (extraction manuelle
  ✎ / extraction IA ✦) ;
- cliquer une pastille de marge ou un `.hl-extraction` → ouvre le drawer et
  fait défiler jusqu'à la carte ;
- **audio** : filtre locuteurs (pilules), timeline cliquable, barre de
  progression de lecture, renommer un locuteur, éditer/supprimer un bloc de
  transcription.

Zones techniques : `#progress-analyse`, `#switcher-versions`,
`#indicateur-synthese`, `#bandeau-notifications`, `#barre-progression-audio`,
`#readability-content` (classé `prose prose-slate prose-lg` — Tailwind
Typography), `#zone-modal-locuteur`.
`data-testid` : `lecture-zone-principale`, `corpus-bloc-conteneur`,
`btn-comparer-versions`, `btn-historique`, `btn-supprimer-version`,
`bandeau-notifications`.

> **Piège** : le filtre de locuteurs et la timeline audio sont produits en
> **f-strings Python** dans `front/services/transcription_audio.py:422-567`
> (classes `.pilule-locuteur`, id `#timeline-audio`). Ce HTML échappe au
> `@source` de Tailwind (`front/tailwind/input.css`) : il n'est visible ni d'un
> grep de templates, ni du purgeur. À traiter explicitement.

### C. Historique des éditions — `GET /lire/{pk}/historique/`
`views.py:1360` → `front/templates/front/includes/historique_page.html` (160 l.).
Actions : retour lecture, changer de version, lire la timeline typée
(`titre` / `locuteur` / `bloc_transcription`, diff `<del>`/`<ins>`).
`data-testid` : `historique-page`, `btn-retour-lecture`, `historique-titre`,
`historique-timeline`, `historique-entree`, `badge-type-edit`,
`edit-description`, `historique-vide`.

### D. Comparaison de versions — `GET /lire/{pk}/comparer/` et `/comparer_hypostases/`
`views.py:1487` et `views.py:1589` →
`front/templates/front/includes/diff_versions_pages.html` (247 l.) et
`front/templates/front/includes/alignement_versions.html` (187 l.).
Actions : choisir version gauche/droite (`<select>` + JS inline), onglet
**Hypostases** (`hx-trigger="load, click once"`) / **Diff texte**, légende
couleur, replier une famille d'hypostases, basculer Source/Résumé.
`data-testid` : `diff-versions-pages`, `btn-retour-lecture-diff`,
`titre-diff-pages`, `selecteurs-versions`, `select-version-gauche`,
`select-version-droite`, `legende-diff`, `onglets-comparaison`,
`onglet-hypostases`, `onglet-diff-texte`, `diff-colonnes`,
`diff-colonne-gauche`, `diff-colonne-droite`, `diff-para-gauche`,
`diff-para-droite`, `alignement-versions`, `btn-bascule-source-versions`,
`alignement-versions-vide`.
JS : script inline d'environ 38 lignes en fin d'`alignement_versions.html`.

### E. Carnets — liste et détail
`GET /carnets/` (`front/views_corpus.py:230`) →
`front/templates/front/corpus/carnets_liste.html` (38 l.).
`GET /carnets/{pk}/` (`views_corpus.py:272`) →
`front/templates/front/corpus/carnet_detail.html` (112 l.) + partial
`front/templates/front/corpus/partials/notes_du_carnet.html` (94 l.).

Actions : compteurs dérivés (N notes · N axes · N catégories), visibilité icône
+ mot, guide de rédaction, **facettes en puces** (cases à cocher natives
habillées, `hx-trigger="change"` → `#corpus-notes`, `hx-push-url`, avec repli
`<noscript><button>Filtrer</button></noscript>`), résumé des filtres littéral
(« X sur Y notes — Type : A OU B ET Thème : C »), vider les filtres, ordre
narratif ▲/▼ (`hx-post /carnets/{pk}/reordonner/` + `hx-vals`), ouvrir une note.
Endpoints associés : `GET /carnets/{pk}/notes/`, `GET|POST
/carnets/{pk}/categories/`, `POST /carnets/{pk}/reordonner/`.
`data-testid` : `corpus-carnets-liste`, `corpus-lien-bases`,
`corpus-carnet-item`, `corpus-carnet-lien`, `corpus-carnet-detail`,
`corpus-carnet-visibilite`, `corpus-carnet-guide`, `corpus-onglet-notes`,
`corpus-onglets-a-venir`, `corpus-filtres`, `corpus-filtre-axe`,
`corpus-filtre-categorie`, `corpus-filtres-vide`, `corpus-message-ordre`,
`corpus-resume-filtres`, `corpus-filtre-vider`, `corpus-notes-liste`,
`corpus-note-item`, `corpus-note-rang`, `corpus-note-lien`,
`corpus-note-categorie`, `corpus-note-monter`, `corpus-note-descendre`,
`corpus-notes-vide`.
Motif CSS notable à conserver ou remplacer sciemment :
`has-[:checked]:bg-slate-200` (Tailwind v4) et pastilles de couleur en
`style="background:{{ categorie.couleur_effective }}"`.

### F. Bases de connaissances — liste et détail
`GET|POST /bases/` (`views_corpus.py:866`, `:954`), `GET /bases/{slug}/`
(`:900`), `POST /bases/{slug}/carnets/`, `.../carnets/{id}/retirer/`,
`.../carnets/{id}/categories/`, `.../carnets/{id}/epingler/`, `GET|POST
/bases/{slug}/categories/`.
Templates : `front/templates/front/corpus/bases_liste.html` (55 l.),
`corpus/base_detail.html` (124 l.), `corpus/partials/categories_de_la_base.html`
(18 l.), `corpus/partials/erreurs_formulaire.html` (13 l.).
Actions : créer une base, ouvrir, épingler/désépingler un carnet, retirer
(`hx-confirm`), éditer les catégories d'un carnet **dans cette base**
(`<details>` + cases), ajouter un carnet (`<select>`), créer un axe.
`data-testid` : 20 identifiants de la famille `corpus-base-*` et `corpus-axe`,
`corpus-categorie-pastille`, `corpus-categories`, `corpus-avertissement-axes`,
`corpus-erreurs`.

### G. Bloc « Dans N carnets » d'une note
`GET /notes/{pk}/carnets/bloc/`, `POST /notes/{pk}/carnets/`, `DELETE|POST
/notes/{pk}/carnets/{carnet_id}/`, `.../categories/`, `.../epingler/`
(`views_corpus.py:604-775`) →
`front/templates/front/corpus/partials/carnets_de_la_note.html` (116 l.).
HTMX : cible `#corpus-bloc-carnets-{{note.pk}}` en `outerHTML` ; **deux
`hx-confirm` distincts** selon qu'il s'agit ou non du dernier carnet.
`data-testid` : `corpus-bloc-carnets`, `corpus-bloc-carnet-ligne`,
`corpus-bloc-carnet-lien`, `corpus-bloc-categorie`, `corpus-bloc-epingler`,
`corpus-bloc-retirer`, `corpus-bloc-crayon`, `corpus-bloc-case-categorie`,
`corpus-bloc-enregistrer-categories`, `corpus-bloc-ajouter-form`,
`corpus-bloc-ajouter-select`, `corpus-bloc-ajouter-bouton`.

### H. Cinq pages autonomes (hors `base.html`)
Ces templates portent leur propre `<!DOCTYPE html>` et **ne chargent que
`tailwind.css?v=10`** — ni `hypostasia.css`, ni htmx, ni SweetAlert :

| Écran | Route | Vue | Template | Lignes |
|---|---|---|---|---|
| Connexion | `GET` et `POST /auth/login/` | `views_auth.py:32` | `front/templates/front/login.html` | 67 |
| Inscription | `GET` et `POST /auth/register/` | `views_auth.py:84` | `front/templates/front/register.html` | 85 |
| Mon token API | `GET` et `POST /auth/token/` | `views_auth.py:146` | `front/templates/front/mon_token.html` | 92 |
| Accès refusé (403) | helper `_reponse_acces_refuse` | `views.py:430-450` | `front/templates/front/acces_refuse.html` | 58 |
| Invitation invalide | `GET /invitation/{token}/` | `views_invitation.py:36` | `front/templates/front/invitation_erreur.html` | 31 |

`data-testid` : `input-username`, `input-password`, `btn-submit-login`,
`lien-register`, `input-email`, `input-password-confirm`, `btn-submit-register`,
`lien-login`, `token-value`, `btn-copier-token`, `btn-regenerer-token`,
`lien-retour-accueil`, `page-403`, `btn-retour-accueil`, `btn-se-connecter`,
`invitation-erreur-message`, `invitation-erreur-lien-retour`.
JS inline : `copierToken()` dans `mon_token.html`.
Déconnexion : `POST /auth/logout/` (`views_auth.py:188`), formulaire dans
`base.html`.

> Ces cinq pages sont les **plus faciles à basculer** (autonomes, sans HTMX,
> sans JS partagé) et les **moins couvertes par la maquette** (aucun équivalent).

## 1.3 Overlays, tiroirs, modales

### I. Arbre latéral (overlay gauche)
`GET /arbre/` → helper `_render_arbre` (`views.py:497-588`) →
`front/templates/front/includes/arbre_dossiers.html` (81 l.) +
`front/templates/front/includes/_dossier_node.html` (103 l.).
Actions : 3 sections en accordéon (Mes dossiers ouvert, Partagés fermé, Publics
ouvert si anonyme) ; déplier un dossier ; ouvrir une page ; **menu contextuel**
(kebab, dossier et page) ; quitter un partage ; « Aligner (N pages) » si ≥ 2 ;
état vide avec import ; pied « Nouveau dossier » + « Importer ».
JS : `arbre_overlay.js` (264 l., `window.arbreOverlay = {ouvrir, fermer,
basculer, estOuvert}`) et `arbre_context_menu.js` (416 l. : renommer, supprimer,
visibilité, classer, partager — 5 SweetAlert, `contextmenu` + appui long
tactile).
Endpoints : `GET|POST /dossiers/`, `DELETE /dossiers/{pk}/`,
`POST /dossiers/{pk}/renommer/`, `GET|POST /dossiers/{pk}/partager/`,
`POST /dossiers/{pk}/visibilite/`, `POST /dossiers/{pk}/quitter/`,
`POST /dossiers/{pk}/inviter/`, `POST /pages/{pk}/supprimer/`,
`POST /pages/{pk}/classer/`.
`data-testid` : `section-mes-dossiers`, `section-partages`, `section-publics`,
`arbre-empty-state`, `arbre-dossier-item`, `btn-quitter-partage`,
`btn-ctx-dossier`, `btn-aligner-dossier`, `btn-ctx-page`, `arbre-page-link`.

> **Il n'y a AUCUN glisser-déposer dans l'application.** Ni `draggable`, ni
> `dragstart`, ni Sortable.js. Le classement se fait par menu contextuel, et
> l'ordre narratif du carnet par boutons ▲/▼. C'est conforme à l'étalon
> (SPEC-synthese § 8.3, alternative clavier exigée) : rien à porter.

### J. Partage d'un dossier
`GET|POST /dossiers/{pk}/partager/` (`views.py:3227`), `POST
/dossiers/{pk}/inviter/` (`views.py:3378`) →
`front/templates/front/includes/partage_dossier_form.html` (156 l.), cible
`#partage-contenu-{{dossier.pk}}` (défini dans `_dossier_node.html:59`).
Actions : partager par nom d'utilisateur, retirer, partager/retirer avec un
groupe, inviter par email, voir les invitations en attente, `<details>` « Gérer
les groupes » (créer `hx-swap="afterend"`, détails `hx-target="closest
.groupe-item"`).
`data-testid` : `partage-dossier-form`, `partage-input-username`,
`partage-btn-ajouter`, `partage-user-row`, `partage-btn-retirer`,
`partage-groupe-row`, `partage-btn-partager-groupe`,
`partage-btn-retirer-groupe`, `inviter-input-email`, `inviter-btn-envoyer`,
`invitation-en-attente`, `groupe-input-nom`, `groupe-btn-creer`,
`groupe-btn-details`.

### K. Détail de groupe
`GET /groupes/`, `POST /groupes/`, `DELETE /groupes/{pk}/`,
`POST /groupes/{pk}/ajouter_membre/`, `.../retirer_membre/`,
`GET /groupes/{pk}/detail/`, `POST /groupes/{pk}/inviter/` →
`front/templates/front/includes/groupe_detail.html` (58 l.).
`data-testid` : `groupe-detail-{{pk}}`, `btn-supprimer-groupe`,
`groupe-input-membre`, `groupe-btn-ajouter-membre`, `groupe-membre-row`,
`groupe-btn-retirer-membre`.

### L. Drawer « Analyses » (overlay droit)
`GET /extractions/drawer_contenu/?page_id=&tri=&contributeurs=&mode_filtre=`
(`views.py:4482`) → `front/templates/front/includes/drawer_vue_liste.html`
(228 l.), qui inclut
`hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html`
avec `mode="drawer"`.
Actions : bandeau « Analyse IA en cours… » (barre indéterminée, mise à jour
WebSocket en OOB sur `#barre-progression-analyse`) ; bandeau résumé + « Nouvelle
analyse ↻ » ; tri Position / Activité récente ; **filtre multi-contributeurs**
par pilules avec mode inclure/exclure (« Sauf ») et remise à zéro ; cliquer une
carte → défiler vers le passage ; commenter ; masquer (propriétaire) ; déplier
« N non pertinente(s) » ; restaurer.
HTMX : `hx-post="/extractions/restaurer/"` avec `hx-vals` et `hx-swap="none"` ;
OOB `<span id="drawer-titre" hx-swap-oob="innerHTML:#drawer-titre">`.
`HX-Trigger` serveur : `drawerContenuChange`, `contributeurFiltreChange`
(`views.py:4634-4669`).
`data-testid` : `bandeau-analyse-en-cours`, `bandeau-resume-analyse`,
`btn-nouvelle-analyse`, `drawer-compteur`, `drawer-compteur-noms`,
`drawer-select-tri`, `pilules-contributeurs`, `pilule-contributeur-{{id}}`,
`btn-reset-contributeurs`, `btn-toggle-mode-filtre`, `drawer-carte`,
`drawer-attente-extractions`, `drawer-empty-state`, `btn-lancer-analyse-empty`,
`drawer-btn-toggle-masquees`, `drawer-btn-restaurer`.
JS : `drawer_vue_liste.js` (470 l., `window.drawerVueListe`).

### M. Carte d'extraction — le composant le plus réutilisé
`hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html`
(159 l.), employé par le drawer, le panneau droit, le bottom sheet, l'éditeur
d'analyseur et les cartes de test.
Contenu : indicateur de statut binaire (`.indicateur-statut[data-statut]`, forme
par `clip-path`), badges d'hypostases colorés
(`var(--hypostase-{famille}-bg/text)`), résumé IA (`.typo-machine`), citation
source (`.typo-citation`), mots-clés, commentaires avec atténuation
(`.commentaire-hors-filtre` / `.contributeur-actif-highlight`), formulaire de
commentaire replié (`onclick` inline + focus), bouton masquer.
HTMX : `hx-post="/extractions/ajouter_commentaire/"` → `hx-target="closest
.extraction-content"` `hx-swap="outerHTML"` ; `hx-post="/extractions/masquer/"`
`hx-swap="none"`.
`data-testid` : `badge-hypostase`, `drawer-btn-masquer`,
`btn-commenter-extraction`.

> **Anomalie d'architecture** : ce composant, le plus visible du produit, vit
> dans `hypostasis_extractor/` et non dans `front/`. À arbitrer (décision D9).

### N. Confirmation d'analyse IA
`GET /lire/{pk}/previsualiser_analyse/?analyseur_id=` (`views.py:1798`) ;
lancement `POST /lire/{pk}/analyser/` (`views.py:2030`) →
`front/templates/front/includes/confirmation_analyse.html` (182 l.), rendu dans
`#drawer-contenu`.
Actions : choisir l'analyseur (`hx-include="this"`, recharge l'estimation) ;
lire tokens/chunks/thinking/coût € ; « Voir le prompt complet » (script inline) ;
cocher « supprimer les N extractions IA sans commentaire » ; lancer ; annuler.
OOB : le titre du drawer devient un bouton « ◀ Analyse ».
`data-testid` : `confirmation-analyse`, `select-analyseur-confirmation`,
`estimation-tokens`, `btn-voir-prompt`, `btn-lancer-analyse`,
`btn-annuler-analyse`.

### O. Confirmation de synthèse délibérative
`GET /lire/{pk}/previsualiser_synthese/?analyseur_id=` (`views.py:2193`) ; `POST
/lire/{pk}/synthetiser/` (`views.py:2366`) →
`front/templates/front/includes/confirmation_synthese.html` (196 l.).
Actions : choisir le moteur (`btn-analyseur-{{id}}`, recharge tout le drawer) ;
voir le prompt ; lire l'encart « État du débat » (barre binaire) ; lire les
compteurs et l'estimation ; lancer (bouton désactivable avec
`alerte-blocage-synthese`).
`data-testid` : `confirmation-synthese`, `selecteur-analyseur-synthese`,
`btn-analyseur-{{a.id}}`, `btn-voir-prompt-synthese`,
`encart-consensus-synthese`, `estimation-synthese`, `alerte-blocage-synthese`,
`btn-lancer-synthese`.
⚠ `views.py:2362` émet `HX-Trigger: ouvrirDrawer` en **chaîne brute, pas en
JSON** — seul cas du dépôt, à normaliser au passage.

### P. Dashboard consensus (dropdown de la barre d'outils)
`GET /extractions/dashboard/?page_id=` (`views.py:4450`) →
`front/templates/front/includes/dashboard_consensus.html` (44 l.) →
`#dashboard-consensus-contenu`.
Actions : lire « X sur Y extractions commentées (Z %) » + barre ; lancer la
synthèse (`hx-get previsualiser_synthese` → `#drawer-contenu`).
JS : `dashboard_consensus.js` (189 l., `window.dashboardConsensus`, écoute
`dashboardReload`).
`data-testid` : `dashboard-consensus`, `btn-lancer-synthese`.

### Q. Bottom sheet mobile
`GET /extractions/carte_mobile/?entity_id=` (`views.py:3884`) →
`front/templates/front/includes/bottom_sheet_extraction.html` (36 l.) →
`#bottom-sheet-contenu`.
JS : `bottom_sheet.js` (394 l., `window.bottomSheet` avec `ouvrir(entityId)` et
`estOuvert()`, gestes `touchstart`/`touchmove`/`touchend`, isolation et
restauration du surlignage, navigation entre extractions).
`data-testid` : `bottom-sheet-carte`.

### R. Modale d'alignement cross-documents
`GET /alignement/tableau/?dossier_id=|?pages=` (`front/views_alignement.py:390`)
; export `GET /alignement/export_markdown/` (`:427`) →
`front/templates/front/includes/alignement_tableau.html` (136 l.), injecté dans
`#alignement-modale-container`.
Actions : basculer Source/Résumé, exporter en `.md`, fermer (Échap), replier une
famille, cliquer une cellule → naviguer vers l'extraction d'origine.
JS : `alignement.js` (280 l., `window.alignement`, crée
`#alignement-modale-backdrop`).
`data-testid` : `btn-bascule-source` ; ids `btn-export-alignement`,
`btn-fermer-alignement`.

### S. Modale d'aide (raccourcis desktop / gestes mobile)
`GET /lire/aide/` et `?mobile=1` (`views.py:1764`), `hx-target="body"
hx-swap="beforeend"` →
`front/templates/front/includes/aide_desktop.html` (394 l., dont **235 lignes de
`<style>` inline**, l. 119-353) et
`front/templates/front/includes/aide_mobile.html` (275 l., dont **159 lignes de
`<style>` inline**, l. 102-260).
Actions : 3 onglets (Comment ça marche / Statuts / Clavier), fermer.
`data-testid` : `modale-aide`.

**Raccourcis clavier réellement implémentés** (`front/static/front/js/keyboard.js`,
542 l., seul écouteur `keydown` de l'application) :
`T` arbre · `E` drawer · `L` mode focus lecture · `J`/`K` extraction
suivante/précédente · `C` commenter · `X` masquer · `H` heat map · `A`
alignement · `Z` comparer les versions · `/` recherche (**placeholder, ne fait
rien**) · `?` aide · `Échap` fermeture en cascade.

### T. Modale « renommer un locuteur »
`GET /lire/{pk}/formulaire_renommer_locuteur/` (`views.py:2596`), `POST
/lire/{pk}/renommer_locuteur/` (`:2612`) →
`front/templates/front/includes/modal_renommer_locuteur.html` (65 l.) →
`#zone-modal-locuteur`.
Actions : nouveau nom + portée (ce bloc et les suivants / ce bloc seul / toutes
les occurrences) ; annuler (`onclick` inline `.remove()`) ; renommer.
`HX-Trigger` : `fermerModaleRenommer` (`views.py:2741`).

### U. Édition inline d'un bloc de transcription
`GET /lire/{pk}/formulaire_editer_bloc/` (`views.py:2748`), `POST
/lire/{pk}/editer_bloc/` (`:2822`), `POST /lire/{pk}/supprimer_bloc/` (`:2974`)
→ `front/templates/front/includes/editer_bloc_inline.html` (58 l.), remplace
`#speaker-block-{{index}}`.
Actions : textarea (Lora 1.125rem / 1.85), supprimer le bloc, annuler, valider,
sauvegarde automatique au clic ailleurs (`sauvegarderBlocEditionOuvert()`,
`hypostasia.js:951`).

### V. Extraction manuelle
`POST /extractions/panneau/` (`views.py:3756`), `/manuelle/` (`:3772`),
`/creer_manuelle/` (`:3831`) →
`front/templates/front/includes/extraction_manuelle_form.html` (117 l.) →
`#panneau-extractions`.
Actions : résumé libre + choix d'une hypostase parmi **8 groupes / 30 options** ;
créer ; annuler.
`data-testid` : `extraction-form-container`, `extraction-form-manuelle`,
`extraction-btn-creer`.
⚠ **Bug latent** : le mode édition poste vers `/extractions/modifier/`, action
**qui n'existe pas** dans `ExtractionViewSet` (retirée en « A.8 phase 4-bis,
YAGNI extraction edit »).

### W. Panneau d'analyse (sidebar droite masquée)
`front/templates/front/includes/panneau_analyse.html` (50 l.) →
`front/templates/front/includes/extraction_results.html` (110 l.), rendus dans
`<aside id="sidebar-right" class="hidden">` (`base.html:325`) : **visuellement
morts, conservés comme cibles d'OOB swaps**.
Actions théoriques : état d'erreur + réessayer, cartes avec suppression au
survol, « Supprimer les extractions IA », « Ajouter dans les données
d'entraînement » (`GET /extractions/formulaire_promouvoir/` `views.py:4063`,
`POST /extractions/promouvoir_entrainement/` `:4083` →
`front/templates/front/includes/modale_promouvoir_entrainement.html`, 28 l.),
pied coût réel / tokens / version d'analyseur.
`data-testid` : `panneau-btn-analyser`, `panneau-analyse-zone`,
`panneau-empty-state`, `extraction-error-state`, `btn-reessayer-analyse`,
`extraction-card`, `extraction-btn-supprimer`, `footer-cout-reel`.

### X. Questionnaire
`GET /questionnaire/` (`views.py:5365`), `POST /questionnaire/poser_question/`
(`:5378`), `POST /questionnaire/repondre/` (`:5411`) →
`front/templates/front/includes/vue_questionnaire.html` (94 l.) →
`#panneau-extractions`.
⚠ Cette cible vit dans la sidebar `hidden` : **écran très probablement
inatteignable**. À confirmer (décision D8).
`data-testid` : `bandeau-connexion-question`.

### Y. Configuration IA (bascule)
`GET /config-ia/status/`, `POST /config-ia/toggle/`, `POST
/config-ia/select-model/` (`views.py:856-933`) →
`front/templates/front/includes/config_ia_toggle.html` (92 l.) →
`#config-ia-zone`.
4 états : IA active / aucun modèle / un seul modèle / N modèles (select tarifé).
La cible `#config-ia-zone` est définie dans
`hypostasis_extractor/templates/hypostasis_extractor/configuration_llm.html:32`,
lui-même rendu **dans `front/base.html`** par la branche
`configuration_llm_preloaded` : l'écran est donc bien vivant, accessible aux
seuls `is_staff` par le bouton `btn-toolbar-config-llm` de la barre d'outils
(`GET /api/analyseurs/`). Il bascule avec le lot 11.
`data-testid` : `config-ia-toggle-button`, `config-ia-disabled-button`,
`config-ia-model-select`, `config-ia-select-model-button`.

### Z. Import de fichier et d'audio
`POST /import/fichier/` (`views.py:4684`), `/previsualiser_audio/` (`:5124`),
`/confirmer_audio/` (`:5211`) →
`front/templates/front/includes/confirmation_audio.html` (89 l.).
Actions : lire durée/taille/modèle, choisir la langue (14 options + auto), lire
le coût estimé, lancer la transcription, annuler.
Trois `input[type=file]` : `#input-import-fichier` (toolbar),
`#input-import-fichier-overlay` (pied de l'arbre),
`#input-import-fichier-onboarding` (accueil) ; SweetAlert de choix de dossier
(`hypostasia.js:81`), `estFichierAudio()` (`:119`).
`data-testid` : `confirmation-audio`, `select-langue-audio`,
`estimation-cout-audio`, `btn-lancer-transcription`, `btn-annuler-transcription`.

### AA. Bouton et dropdown « Mes tâches »
`GET /taches/bouton/` (`front/views_taches.py:90`), `/taches/dropdown/` (`:100`),
`POST /taches/{pk}/marquer-lue/` (`:153`), `/taches/marquer-toutes-lues/`
(`:176`) → `front/templates/front/includes/taches_bouton.html` (22 l., 4 états
`btn-taches-{neutre|en_cours|succes|erreur}`) et
`front/templates/front/includes/taches_dropdown.html` (114 l.).
Actions : ouvrir, tout marquer comme lu, rafraîchir, « Voir le résultat » /
« Voir détails ».
OOB : `<a id="btn-taches" hx-swap-oob="outerHTML">` en fin de dropdown.
**WebSocket** : `ws(s)://<host>/ws/notifications/` (`hypostasia.js:1539-1581`),
consumer `front/consumers.py`, routes `front/routing.py`, ASGI
`hypostasia/asgi.py`.
`data-testid` : `btn-taches`, `badge-taches-en-cours`, `badge-taches-non-lues`,
`taches-dropdown`, `btn-taches-marquer-toutes-lues`, `btn-taches-reload`,
`taches-item-{{pk}}`, `taches-voir-resultat`, `taches-voir-details`.

## 1.4 Écrans staff rendus dans `front/base.html`

Rendus par `hypostasis_extractor/views.py` en réutilisant `front/base.html` : ils
subissent donc la bascule au même titre que le reste.

| Écran | Branche de cascade | Template | Lignes |
|---|---|---|---|
| Configuration LLM (`GET /api/analyseurs/`) | `configuration_llm_preloaded` | `hypostasis_extractor/templates/hypostasis_extractor/configuration_llm.html` | 91 |
| Éditeur d'analyseur | `analyseur_preloaded` | `.../analyseur_editor.html` (contient un `<style>` inline) | 434 |
| Liste des versions | `versions_list_preloaded` | `.../includes/versions_list.html` | — |
| Diff des versions | `versions_diff_preloaded` | `.../includes/versions_diff.html` | — |

Plus **22 partials** sous `hypostasis_extractor/templates/hypostasis_extractor/includes/`
(1 140 lignes au total), dont `_card_body.html` déjà cité.

## 1.5 Ce qui est mort ou orphelin — à supprimer AVANT la bascule

Ne pas re-habiller du code mort. Chaque ligne est vérifiable par grep du nom de
fichier sur `*.py`, `*.html`, `*.js`.

| Fichier | Lignes | Verdict | Preuve |
|---|---|---|---|
| `front/templates/front/includes/recherche_semantique.html` | 41 | **MORT** | poste vers `GET /extractions/recherche_semantique/` — cette `@action` n'existe pas dans `ExtractionViewSet` (`views.py:3604-4652`). Aucun include, aucun render. **`SPEC-synthese-carnet.md` § 11.4 en demande explicitement la suppression.** |
| `front/templates/front/includes/resultats_recherche.html` | 52 | **MORT par transitivité** | inclus uniquement par `recherche_semantique.html:38` |
| `front/templates/front/includes/panneau_extractions.html` | 52 | **MAQUETTE MORTE** | 0 include, 0 render. Contient 3 cartes en dur aux statuts « Discuté / Controversé / Consensuel », **supprimés par la refonte A.8** (statuts binaires nouveau/commenté) |
| `front/templates/front/includes/modale_prompt_readonly.html` | 68 | **MORT** | seules occurrences : `tmp/maquettes/maquette.html:672` et `:1289`, dans des commentaires CSS qui la disent « orpheline » |
| `front/templates/front/includes/editer_titre_inline.html` | 14 | **ORPHELIN** | 0 occurrence. L'édition de titre est faite en JS pur dans `hypostasia.js` |
| `front/templates/front/includes/item_page.html` | 6 | **ORPHELIN** | 0 occurrence. Remplacé par `_dossier_node.html` |
| `front/templates/front/includes/extraction_card.html` | 6 | **ORPHELIN** | les hits de grep visent `hypostasis_extractor/includes/test_extraction_card.html`, pas celui-ci |
| `front/templates/front/bibliotheque.html` | 1 | **COQUILLE** | `{% extends %}` seul, aucun bloc |
| `hypostasis_extractor/templates/hypostasis_extractor/job_list.html` | 62 | **CASSÉ** | `{% extends "core/base.html" %}` — **ce template n'existe pas dans le dépôt** (seul `front/templates/front/base.html` existe). Rendu par `hypostasis_extractor/views.py:117` → `TemplateDoesNotExist` garanti |
| `.../job_detail.html` | 161 | **CASSÉ** | idem, `views.py:139` |
| `.../example_list.html` | 55 | **CASSÉ** | idem, `views.py:339` |
| `.../analyseur_list.html` | 7 | **ORPHELIN** | 0 référence |

**Total à retirer : ~525 lignes de gabarit.**

Cibles HTMX à traiter en même temps : `#panneau-extractions`
(`front/templates/front/base.html:330`) et `#zone-resultats-extraction`
(`front/templates/front/includes/panneau_analyse.html:38`) n'existent que
**dans la `<aside id="sidebar-right" class="hidden">`** : les swaps aboutissent,
mais rien n'est jamais visible. Endpoint mort référencé dans un template
vivant : `/extractions/modifier/` (`extraction_manuelle_form.html:17`) —
l'action n'existe pas dans `ExtractionViewSet`.

*(Note : `#config-ia-zone` avait été signalé comme orphelin lors de
l'inventaire ; vérification faite, il existe bien
— `hypostasis_extractor/templates/hypostasis_extractor/configuration_llm.html:32`.
L'écran de configuration IA est vivant.)*

Enfin : `front/tests/e2e/__init__.py` réexporte les fichiers 01→13, 15, 16 mais
**pas** `test_14`, `test_17`, `test_20`, `test_22` — inventaire désynchronisé, à
corriger.

## 1.6 Les contrats invisibles — la vraie liste des choses qui cassent

Ces éléments ne sont ni des écrans ni du CSS, mais toute bascule qui les ignore
casse silencieusement des fonctionnalités.

**a) Les 11 événements `HX-Trigger` émis par le serveur** (~55 occurrences dans
`front/views*.py`) — c'est le protocole entre Django et le JavaScript :

| Événement | Occurrences | Consommateur |
|---|---|---|
| `showToast` (`{message, icon}`) | **54** | `hypostasia.js:438` → SweetAlert2 |
| `tachesChanged` | 4 | `hypostasia.js` |
| `ouvrirPanneauDroit` | 4 | `hypostasia.js:358` |
| `fermerDrawer` | 4 | `drawer_vue_liste.js` |
| `lectureReload` | 3 | `hypostasia.js` |
| `drawerContenuChange` | 3 | `drawer_vue_liste.js` |
| `dashboardReload` | 2 | `dashboard_consensus.js` |
| `contributeurFiltreChange` | 1 | `marginalia.js` |
| `fermerModaleRenommer` | 1 | `hypostasia.js` |
| `authRequise` | 1 | `hypostasia.js` |
| `ouvrirDrawer` | 1 (**chaîne brute**) | `drawer_vue_liste.js` |

Plus `HX-Location` (`views.py:1473`). Événements HTMX natifs écoutés :
`htmx:afterSwap` (×8), `htmx:afterSettle` (×3), `htmx:responseError`,
`htmx:pushedIntoHistory`.

**b) Deux systèmes de toasts coexistent** :
- SweetAlert2, `position: 'top-end'`, classe `toast-sous-navbar` pour ne pas
  masquer le bouton « tâches » (`hypostasia.js:451`) ;
- `.ws-toast` maison, empilé en bas à droite, disparition après 6 s
  (`hypostasia.css:1668-1810`), alimenté par le WebSocket.

L'étalon n'en a **qu'un** : `.pile-toasts` centré en bas, 3,2-3,4 s de durée de
vie. Unification à trancher (décision D5).

**c) Deux APIs JavaScript globales sont assertées par les tests** :
`window.bottomSheet` (`ouvrir(entityId)`, `estOuvert()`) et `window.marginalia`
(`getContributeurFiltre()` → Array, `resetContributeurFiltre()`). S'y ajoutent,
non testées : `window.arbreOverlay`, `window.drawerVueListe`,
`window.dashboardConsensus`, `window.alignement`.

**d) L'état ouvert/fermé des overlays est encodé dans des classes Tailwind**, pas
dans un attribut : `#arbre-overlay` fermé porte `pointer-events-none` et
`-translate-x-full` ; `#drawer-overlay` fermé porte `pointer-events-none` et
`translate-x-full`. `front/tests/e2e/base.py` attend littéralement
`#arbre-overlay:not(.pointer-events-none)`. Passer à `[hidden]`, `display:none`
ou `<dialog>` **casse toute la suite e2e** (cf. § 3.4).

**e) Le mode lecture mobile est une classe sur `<body>`** :
`document.body.classList.contains('mode-lecture-mobile')`, asserté par
`test_10_mobile.py`.

**f) `#zone-lecture` est le conteneur défilant**, pas `window` : plusieurs tests
lisent son `scrollTop` / `scrollHeight`.

**g) Du HTML est généré en Python** :
`front/services/transcription_audio.py:422-567` produit `.pilule-locuteur` et
`#timeline-audio` en f-strings. Invisible du `@source` Tailwind.

**h) Les variables CSS sémantiques sont employées en `style="…"` inline** dans
une dizaine de templates : `--statut-*`, `--hypostase-{famille}-{bg,text}`,
`--pilule-hue`, `couleur_effective` des catégories. Elles doivent survivre sous
un nom ou sous un autre.

**i) Le markup du surlignage est figé au caractère près** par
`front/tests/test_rendu_elements.py` :
`'<mark class="portion hl-extraction"'`, `data-superposition="1"|"2"`,
`data-statut="commente"`.

---

# 2. Le design system de l'étalon

Source : `tmp/maquettes/corpus.html` (1 884 l.), `maquette.html` (2 489 l.),
`selection-preuves.html` (1 499 l.), `index.html` (118 l.), `donnees.js` (468 l.).

## 2.1 Tokens

**Mécanisme de thème à trois états** (identique dans les 4 fichiers) :

```css
:root { /* clair — valeurs par défaut */ }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }
:root[data-theme="dark"] { … }
```

`<html lang="fr" data-theme="light">` au chargement ; le bouton
`#bascule-theme` cycle sur `['light', 'dark', '']` (`○ clair` / `● sombre` /
`◑ système`). **Aucune persistance** (pas de `localStorage`) — à ajouter.
L'application n'a aujourd'hui **aucun thème sombre** (audit D12).

**Surfaces et texte** (les 8 seules variables qui basculent en sombre) :

| Variable | Clair | Sombre |
|---|---|---|
| `--papier` | `#fdfcfa` | `#16151a` |
| `--papier-creux` | `#f5f3ef` | `#1e1d23` |
| `--papier-panneau` | `#faf8f4` | `#1a191f` |
| `--revelation` | `#f0ede6` | `#26242c` |
| `--barre` | `#1c1b19` | `#0d0c10` |
| `--encre` | `#1c1b19` | `#eceae4` |
| `--encre-douce` | `#6b6862` | `#9b968d` |
| `--filet` | `#e4e0d8` | `#33313a` |

**Accents** (identiques clair et sombre — **leur contraste sur fond sombre n'a
jamais été vérifié**, c'est un défaut de l'étalon lui-même) : `--cible #7C5CBF`,
`--danger #b91c1c`, `--succes #047857`, `--info #4338ca`,
`--statut-nouveau #999999`, `--statut-commente #E69F00`.

**8 familles d'hypostases**, valeurs identiques partout, en `*-text`
seulement : épistémique `#4338ca`, empirique `#047857`, spéculatif `#b45309`,
structurel `#475569`, normatif `#6d28d9`, problématique `#b91c1c`, mode
`#0e7490`, objet `#64748b`. Les `*-bg` n'existent que dans `maquette.html` et
**ne sont jamais utilisés** (commentaire : « ÉCART ASSUMÉ — le produit les
remplit (hypostasia.css:97-103) »).

**États de vérification** (corpus seulement) : `--verifie #047857`,
`--faible #b45309`, `--non-source #b91c1c`.
**Polarités du débat** (sélection seulement) : `--pour`, `--contre`,
`--constat`, `--proposition`.

**Gabarit** : `--barre-outils 44px`, `--barre-fil 32px` (30px dans
`maquette.html` — **divergence à unifier**), `--preuve 26rem`/`25rem`,
`--panneau 23rem`, `--gouttiere 46px`, `--largeur-lecture 40rem`. Certaines sont
redéfinies contextuellement par attribut sur `<body>`
(`body[data-mode="inspection"] { --gouttiere:124px; --largeur-lecture:52rem }`).

**Variables locales portées en `style` inline** — c'est le mécanisme de la
donnée colorée : `--teinte` (catégories, pilules), `--couleur-famille`,
`--couleur-locuteur`, `--couleur-statut`, `--role-couleur`.

**Typographie — aucune variable CSS**, mais une règle constante :
- serif `Georgia, "Iowan Old Style", "Palatino Linotype", serif` pour le contenu ;
- `ui-monospace, "SF Mono", Menlo, monospace` pour **tout le chrome** ;
- base **17px / 1.7** (16px sous 800-900px) ;
- contenu en `.75–.95rem`, chrome en `.53–.72rem`, titres `1.25–1.7rem` — un
  rapport de 1 à 3 entre chrome et contenu ;
- graisses : **600 et 700 uniquement**. Pas de 300, pas de 500 ;
- `text-transform: uppercase` + `letter-spacing .04–.09em` systématique sur les
  étiquettes mono.

**Rayons** : `999px` (puces, pilules), `50%` (avatars, pastilles), `8px`
(surfaces), `6px` (menus), `5px` (cartes), `4px` (boutons, champs), `3px`, `2px`
(badges, marques), `1px`.
**Ombres** : 8 valeurs littérales, aucune variable, de `0 1px 6px rgba(0,0,0,.07)`
à `0 10px 40px rgba(0,0,0,.22)`.
**Espacement** : échelle em-relative accordée à la typo, pas géométrique — pas
de 4/8/16. Micro `.02–.1rem`, petit `.15–.35rem`, moyen `.4–.8rem`, grand
`1–2rem`, très grand `2.4–5rem`.
**Largeurs max** : `.zone 64rem`, `.zone.large 80rem` (l'app est aujourd'hui en
`max-w-3xl`, soit 46 % de l'écran — audit D16).

## 2.2 Composants

Chacun est nommé par sa classe réelle dans l'étalon.

| Composant | Classe | Note |
|---|---|---|
| Barre d'outils | `.barre-outils` | sticky, `--barre` sombre, boutons fantômes |
| Fil d'Ariane | `.fil-ariane` | sticky sous la barre ; **`overflow:visible` obligatoire** (commentaire explicite : sinon le menu de bascule est invisible) |
| Grille de page | `.plateau`, `.zone`, `.zone.large` | 64rem / 80rem |
| Ligne de note | `.ligne-note` | grille `auto 1fr auto`, ligne entière cliquable, survol `--papier-creux`, `.rang`/`.titre-note`/`.sous-note`/`.etiquettes`/`.boutons-ordre` |
| Carte d'extraction | `.carte` | bord gauche 3px coloré par statut, `.est-active` halo ambre, `.est-masquee` pointillé + opacité |
| Carte de preuve | `.carte-preuve` | variante lecture seule : `.entete-preuve`, `.resume-machine`, `.citation-exacte`, `.debat`, `.selecteurs` |
| Facettes | `.facettes > .axe > .puce-categorie` | `aria-pressed`, `--teinte` inline, **OU dans un axe, ET entre axes** |
| Onglets | `.onglets[role=tablist] > button[role=tab]` | soulignement `--statut-commente`, `.compteur-onglet`, panneaux `.panneau-onglet.est-actif` |
| Panneau de preuve | `.panneau-preuve` | tiroir `translateX(100%)` → `.est-ouvert` (corpus) ; colonne sticky (sélection) |
| Panneau latéral | `.panneau` | permanent ≥1400px, sinon drawer ; 3 écrans par `data-ecran` |
| Surfaces | `.surface` + `.voile` | `.surface-ancree` (popover) et `.surface-modale`. **Aucun `<dialog>`, aucun focus trap, aucun `role="dialog"`** |
| Toasts | `.pile-toasts > .toast[data-genre]` | centré en bas, 3,2-3,4 s. **Aucun `aria-live`** |
| Badges | `.badge-hypostase` | **contour, jamais rempli** : `background:none; border:1px solid currentColor; opacity:.85` |
| Indicateur de statut | `.indicateur-statut[data-statut]` | binaire : cercle creux gris / triangle plein ambre par `clip-path` — identique au produit actuel |
| Autres pastilles | `.pastille-badge`, `.etat-verification`, `.drapeau`, `.raison`, `.marque-cible`, `.pastille-vivante` | |
| Boutons | `.bouton-plat` + `.principal` + `.danger` + `:disabled` | **une seule famille**, aucune classe de taille |
| Champs | `.champ-etiquette`, `.champ-select`, `.champ-texte`, `.case-a-cocher` | **aucun style `:focus`** |
| Arbre | `.arbre` + `.arbre-section` + `.noeud-dossier` + `.liste-pages` | fixe, `translateX(-100%)` → `.est-ouvert`. Décision documentée : **l'arbre ne liste plus jamais de notes, seulement des contenants** (à cause du N-N) |
| Tableaux | `.tableau-alignement` | double sticky (thead top + tbody th left), `.bandeau-famille`, `.cellule-vide` |
| États vides | `.vide` | **les vides expliquent la règle**, ils ne constatent pas |
| Menus | `.menu-bascule`, `.menu-selection` | `role=menu`, `aria-expanded`, fermeture au clic document |
| Chargement | `.tourniquet`, `.barre-progression`, `.carte.vient-d-arriver` | **aucun squelette** |
| Surlignage | `mark.portion.hl-extraction` | **nu au repos**, révélé au survol du bloc, allumé sur `.est-active`. Marques imbriquées, `data-superposition` gère le décalage |
| Feuille mobile | `.feuille` + `.poignee` | balayage horizontal, seuil 50px |
| Lecteur audio | `.lecteur` + `.rail` + `.segment-locuteur` + `.tete-de-lecture` | |

## 2.3 Doctrine

1. **La couleur ne décore jamais.** Un seul accent fonctionnel :
   `--statut-commente #E69F00` = « il y a du débat ici ». Il porte le filet
   d'état, l'onglet actif, le surlignage allumé, le compteur de commentaires, la
   ligne d'arbre active, la bordure d'édition.
2. `--cible #7C5CBF` est **réservé à la méta-information de maquette** (« ceci
   n'existe pas encore »). Aucun usage produit — à ne pas porter tel quel.
3. Rouge / vert / ambre uniquement pour des **états calculés**.
4. Les couleurs de familles et de catégories sont des **contours**, pas des
   remplissages. Justification écrite dans l'étalon : « Trois badges côte à côte
   ne doivent pas peser plus que la phrase qu'ils qualifient. » **C'est un écart
   assumé et documenté par rapport à `hypostasia.css:97-103`.**
5. Les teintes vives ne vivent que comme **données**, via `--teinte` inline.
6. `color-mix(in srgb, X N%, transparent)` (4-55 %) est le seul mécanisme
   d'atténuation — aucune couleur supplémentaire n'est introduite.
7. **Densité assumée** : contenu confortable (17px/1.7), chrome très dense
   (.53-.72rem), paddings de contrôle à `.22rem .55rem`.
8. **Tout chiffre est dérivé.** Règle centrale de `donnees.js` : « tout offset,
   compte, écarté, couverture, similarité est DÉRIVÉ ; un chiffre tapé est un
   défaut. »
9. **Mouvement minimal** : 7 durées seulement (`.12s` `.14s` `.2s` `.22s` `.25s`
   `.3s` `.45s`), deux boucles, `translateX/Y` jamais `display`, et
   `@media (prefers-reduced-motion: reduce)` qui neutralise tout.

**Accessibilité — ce que l'étalon fait bien** : `aria-pressed` sur toutes les
bascules, `role=tablist`/`tab`/`aria-selected`, `aria-expanded` +
`aria-haspopup`, `aria-current`, `role=menu`/`menuitem`,
`nav[aria-label="Fil d'Ariane"]`, `tabindex="0"` sur `mark.hl-extraction`,
`.affirmation` et `.carte`, `prefers-reduced-motion`, alternative clavier au
glisser-déposer (▲/▼ avec `aria-label`), sémantique HTML réelle (`<table>`,
`<details>`, `<nav>`, `<main>`, `<aside>`, `<figure>`, `<kbd>`).

**Accessibilité — ce que l'étalon NE fait PAS** (et qu'il ne faut donc pas
« porter » aveuglément) :
- aucun `aria-live` sur les toasts ni sur la progression — **l'application en a
  déjà** (`aria-live="polite"` sur `#zone-lecture`, `#arbre`, `#sidebar-right`,
  et sur la zone de notes du carnet, ajout correct noté par
  `PLAN/corpus-phase-f-cahier-des-charges.md` § A) ;
- aucune gestion de focus à l'ouverture/fermeture des surfaces, aucun piège de
  focus, aucun `role="dialog"`/`aria-modal`/`aria-labelledby` ;
- aucun `aria-controls` liant onglets et panneaux, aucun `id` sur les panneaux ;
- **aucun style `:focus` sur `.bouton-plat` ni sur les champs** (seuls 4
  éléments ont un `:focus-visible`) ;
- pas de lien d'évitement ;
- contrastes non revérifiés en thème sombre ;
- pastilles : l'étalon ne dit rien de la taille minimale, or l'audit D11 relève
  16×16px < 24px WCAG 2.5.8 dans l'application.

**Conclusion à retenir : la maquette est un étalon esthétique et structurel,
pas un étalon d'accessibilité.** Sur ces sept points, la bascule doit
*améliorer* l'étalon, pas le copier.

## 2.4 Ce que la maquette ne couvre pas — et le traitement proposé

Vingt-quatre trous. Aucun ne doit être comblé en gardant l'ancien CSS : la règle
est **d'étendre le design system**, en réutilisant `.bouton-plat`, `.champ-*`,
`.surface`, `.vide`, `.encart`, `.avertissement`.

| # | Absent de la maquette | Traitement proposé |
|---|---|---|
| 1 | Connexion, inscription, mot de passe oublié | Nouveau gabarit « page nue » : `.zone` étroite (28rem) centrée sur `--papier`, `.champ-*`, `.bouton-plat.principal`. Ces 3 pages n'ont ni htmx ni JS : lot pilote idéal |
| 2 | Mon token API, réglages, préférences | Même gabarit ; le sélecteur de thème (3 états) trouve ici sa place, avec **persistance `localStorage`** que l'étalon n'a pas |
| 3 | Partage, invitations, groupes, rôles, visibilité | `.surface-modale` + listes `.ligne-*` + `.bouton-plat.danger` pour retirer. Les icônes 👥🌐🔒 de l'étalon sont décoratives : leur donner un libellé texte |
| 4 | Import de fichier et d'audio, file d'ingestion | `.surface-modale` + `.encart` (durée, taille, modèle, coût) + `.barre-progression`. Le `<input type=file>` reste natif, habillé en `.bouton-plat` |
| 5 | Création/édition de carnet, d'axe, de catégorie ; guide de rédaction | L'étalon **affiche** le guide (`.guide-redaction`) mais n'a aucun formulaire. Étendre : `<details>` + `.champ-*`, sélecteur de couleur pour `CategorieDossier.couleur` (palette Wong par défaut) |
| 6 | Recherche (plein texte ou sémantique) | **Hors périmètre.** `SPEC-synthese § 11.4` dit de supprimer ce qui existe. La touche `/` est un placeholder à retirer de `keyboard.js` |
| 7 | Historique, versions, diff | L'étalon a **retiré** les pilules V1/V2/V3 « à remplacer par autre chose », sans remplacement. L'app a un écran complet et testé : **le conserver**, l'habiller en `.ligne-note` + `.encart`, garder `<del>`/`<ins>` |
| 8 | Export réel (Markdown, JSON, alignement) | `.bouton-plat` dans une `.rangee-actions` ; l'étalon n'a que des toasts |
| 9 | Écran de tâches, notifications | `.surface-ancree` sous la barre d'outils (l'étalon a `.surface-taches` en dur, 3 lignes). Ajouter l'`aria-live` que l'étalon n'a pas |
| 10 | Renommage de locuteur, extraction manuelle (30 hypostases) | `.surface-modale` + `.champ-select` avec `<optgroup>`. L'étalon les décrit dans des toasts, sans les dessiner |
| 11 | Écrans d'erreur 403/404/500, hors-ligne, quota, document vide | Étendre `.vide` en `.page-etat` : titre serif, phrase FALC, `.bouton-plat` de sortie. `acces_refuse.html` existe déjà et sert de modèle |
| 12 | Chargement, squelettes, état initial vide | L'étalon n'a **aucun** squelette ; l'app en a (`hypostasia.css:559`). **Garder les squelettes de l'app**, les retoken |
| 13 | Confirmations destructives | L'étalon passe tout par des toasts. L'app utilise `hx-confirm` et SweetAlert — **plus sûr, à garder**, habillé en `.surface-modale` |
| 14 | Pagination, chargement progressif | Absent des deux. C'est le défaut **D2** de l'audit (8 095px de liste pour 120 notes) : à traiter dans ce chantier ou juste après |
| 15 | Sélection multiple, actions groupées | Hors périmètre v1 |
| 16 | Navigation mobile, onglets bas, alignement mobile | L'étalon n'a que la feuille mobile. L'app a un mode mobile complet et testé (`test_10_mobile.py`) : **le conserver** |
| 17 | Configuration LLM, éditeur d'analyseur (staff) | Aucun équivalent. Étendre : `.tableau-*` + `.champ-*` + `.piece-prompt[data-role]` (l'étalon a ce dernier composant) |
| 18 | Manifeste, onboarding 4 étapes | Aucun équivalent. Ce sont 297 lignes de CSS inline à retoken sur `.zone` + `.encart` + typographie serif |
| 19 | Questionnaire | À supprimer ou à ressusciter (décision D8) |
| 20 | Dashboard consensus | L'étalon a `.barre-couverture` et `.mini-barre` : réutilisables tels quels |

## 2.5 Les écarts frontaux entre l'app et l'étalon

Ce sont les points où « porter le design » signifie **abandonner une décision
antérieure**. Ils remontent tous en § 4.

| # | Application actuelle | Étalon | Enjeu |
|---|---|---|---|
| É1 | **4 polices locales** (B612, B612 Mono, Srisakdi, Lora), 12 `.woff2`, doctrine « une police = une provenance » documentée dans `front/tailwind/input.css` | **2 familles système** : Georgia + `ui-monospace`. Aucun webfont | La doctrine typographique de provenance disparaît. `test_06_charte_visuelle.py` vérifie que les 4 polices se chargent |
| É2 | Badges d'hypostases **remplis** (`--hypostase-*-bg`, `hypostasia.css:97-103`) | Badges **en contour** ; les `*-bg` existent mais sont inutilisés, écart documenté | Lisibilité vs identité |
| É3 | Tailwind v4 + 1 985 lignes de CSS maison | CSS artisanal, ~2 000 lignes, zéro utilitaire | Garde-t-on Tailwind ? |
| É4 | Aucun thème sombre | Trois états, sans persistance | Audit D12 |
| É5 | Deux systèmes de toasts | Un seul, centré en bas | |
| É6 | `max-w-3xl` sur la vue carnet (46 % de l'écran) | `.zone.large` = 80rem | Audit D16 |
| É7 | Pastilles 16×16px | non spécifié | WCAG 2.5.8 exige 24px — audit D11 |
| É8 | Titres de corpus en bleu lien B612 | Titres en encre Georgia | Audit D3 |
| É9 | `aria-live` présents ; `hx-confirm` ; squelettes | Absents de l'étalon | **L'app est meilleure ici** |
| É10 | L'arbre liste les pages | L'étalon ne liste que des contenants (décision documentée, à cause du N-N) | Audit D2 |

---

# 3. Stratégie de bascule

## 3.1 Principe directeur

**Une seule feuille, un seul jeu de tokens, écran par écran, jamais deux
systèmes en parallèle sur un même écran.**

Concrètement : créer `front/static/front/css/systeme.css` portant les tokens et
les composants de l'étalon, le charger **à côté** de `hypostasia.css` pendant la
transition, et vider `hypostasia.css` section par section (elle en compte 28,
numérotées — c'est le découpage naturel des lots). L'ancienne feuille disparaît
quand la dernière section est vide. `tailwind.css` reste chargé jusqu'au lot
final (décision D3).

Ce qui **ne bascule pas** : les identifiants de conteneurs, les `data-testid`,
les APIs JS globales, le vocabulaire `HX-Trigger`, le mécanisme d'ouverture des
overlays. Ce sont des contrats, pas du style.

## 3.2 Lot 0 — travaux préalables (à faire avant toute ligne de CSS)

Sans ce lot, tous les autres échouent mécaniquement.

| # | Tâche | Vérification |
|---|---|---|
| 0.1 | Supprimer les 12 fichiers morts du § 1.5 (~525 lignes) et les 3 vues cassées de `hypostasis_extractor/views.py:117,139,339` | `grep -r "recherche_semantique\|panneau_extractions\|modale_prompt_readonly" --include=*.py --include=*.html` ne renvoie que le CHANGELOG |
| 0.2 | Retirer le placeholder `/` de `keyboard.js` (`placeholderRecherche`) et l'entrée correspondante des deux modales d'aide | `grep -n "placeholderRecherche" front/static/front/js/keyboard.js` → vide |
| 0.3 | Corriger `/extractions/modifier/` dans `extraction_manuelle_form.html:17` (endpoint inexistant) | l'action existe, ou le bloc est retiré |
| 0.4 | Normaliser `HX-Trigger: ouvrirDrawer` en JSON (`views.py:2362`) | les 11 triggers ont le même format |
| 0.5 | Résynchroniser `front/tests/e2e/__init__.py` (14, 17, 20, 22 manquants) | les 20 fichiers e2e y figurent |
| 0.6 | **Mettre en quarantaine les ~40 classes de `front/tests/test_phases.py` qui assertent sur le texte de `hypostasia.css`, des `.js` et des templates** (cf. § 3.4) | la suite passe avec un `hypostasia.css` vidé |
| 0.7 | Rapatrier les 691 lignes de `<style>` inline (aide desktop 235, onboarding 187, aide mobile 159, manifeste 110) dans un fichier unique | `grep -c "<style" front/templates/front/**/*.html` → 0 |
| 0.8 | Déplacer la génération HTML de `front/services/transcription_audio.py:422-567` vers un template, ou l'ajouter au `@source` Tailwind | le filtre de locuteurs survit à une recompilation Tailwind |
| 0.9 | Corriger `tmp/maquettes/index.html:95` (« 35 contrôles » → 37) | cohérent avec `scripts/verifier_les_maquettes.py` |
| 0.10 | Factoriser les ~250 lignes triplées entre les 3 étalons (`.badge-hypostase`, `.carte-preuve`, `.bouton-plat`, `.toast`, `.indicateur-statut`, `.menu-bascule`) dans `systeme.css` | une seule définition par composant |

**Estimation lot 0 : 1 à 1,5 jour.** Le poste 0.6 est le plus long et le plus
ingrat ; c'est aussi celui qui débloque tout le reste.

## 3.3 Ordre des lots

L'ordre suit deux critères : le risque croissant, et la dépendance de la phase H.

| Lot | Contenu | Fichiers | Risque | Estimation |
|---|---|---|---|---|
| **1 — Socle** | `systeme.css` : tokens, thème 3 états + persistance, `.bouton-plat`, `.champ-*`, `.vide`, `.encart`, `.avertissement`, `.toast`, `.badge-*`, `.indicateur-statut`. Aucun écran touché | 1 fichier neuf | Nul | 1 j |
| **2 — Pages autonomes** | Login, register, token, 403, invitation. Pas d'HTMX, pas de JS partagé, 5 templates de 31 à 92 lignes. **Lot pilote : il valide le socle en conditions réelles** | 5 templates | Faible — testid seulement (`test_13`, `test_15`, `test_16`) | 0,5 j |
| **3 — Chrome** | `base.html` : barre d'outils, fil d'Ariane (à créer, audit D5/P1-6), menu utilisateur, dropdown tâches. **Conserver tous les ids et le mécanisme de classes des overlays** | `base.html`, `taches_*.html` | Moyen — `Phase07LayoutMonoColonneBaseHtmlTest`, `Phase10BaseHtmlDrawerTest`, `Phase21BaseHTMLTest` | 1 j |
| **4 — Écrans corpus** | `/carnets/`, `/carnets/{pk}/`, `/bases/`, `/bases/{slug}/`, bloc « Dans N carnets ». C'est là que l'écart est le plus grand (audit D3) et l'étalon le plus complet | 8 templates `corpus/` | Faible — `test_22_corpus.py` est 100 % testid | 1,5 j |
| **5 — Lecture** | `lecture_principale.html`, surlignage, pastilles de marge, menu de sélection, gouttière. **Le markup de `mark.portion.hl-extraction` est figé par `test_rendu_elements.py` : on change le CSS, pas le HTML.** Traiter D11 (pastilles 24px) et D1 (extractions mobiles) ici | `lecture_principale.html`, `hypostasia.css` §5-9 | **Élevé** | 2 j |
| **6 — Drawer et cartes** | `drawer_vue_liste.html`, `_card_body.html`, bottom sheet, pilules de contributeur | 3 templates + `hypostasia.css` §11, §24, §26 | **Élevé** — `window.bottomSheet`, `window.marginalia`, `.commentaire-hors-filtre` | 1,5 j |
| **7 — Arbre et partage** | `arbre_dossiers.html`, `_dossier_node.html`, menu contextuel, `partage_dossier_form.html`, `groupe_detail.html`. Arbitrer É10 (l'arbre liste-t-il encore les pages ?) et D6 (le tiroir recouvre la nav) | 5 templates | Moyen — `test_14` utilise `.arbre-section-toggle` et `aria-expanded` | 1,5 j |
| **8 — Modales et confirmations** | Analyse, synthèse, audio, renommer locuteur, promouvoir, aide desktop/mobile, alignement, dashboard | 10 templates + 691 l. rapatriées au lot 0 | Moyen | 1,5 j |
| **9 — Historique, diff, alignement** | `historique_page.html`, `diff_versions_pages.html`, `alignement_versions.html`, `alignement_tableau.html`. L'étalon fournit `.tableau-alignement` et `.bandeau-famille` | 4 templates + `hypostasia.css` §21 | Moyen — `test_09`, `test_20`, `Phase18*` | 1 j |
| **10 — Onboarding et manifeste** | 609 lignes, 297 de CSS inline | 2 templates | Faible | 0,5 j |
| **11 — Staff** | Configuration LLM, éditeur d'analyseur, 22 partials de l'extracteur | `hypostasis_extractor/templates/**` | Faible (peu testé) | 1 j |
| **12 — Retrait** | Vider `hypostasia.css`, décider du sort de Tailwind (D3), recompiler, purger les `?v=NN` ou passer à un manifest | tous | Moyen | 0,5 j |

**Total : 14 à 15 jours-agent**, lot 0 compris. Les lots 1-4 (4 jours) forment
un premier jalon livrable et réversible ; les lots 5-6 (3,5 j) concentrent le
risque.

**En un seul lot** : les lots 1, 2 et 3 doivent être livrés ensemble — un socle
sans écran ne se vérifie pas, et un chrome à moitié basculé est visuellement
incohérent sur toutes les pages.
**Progressif** : les lots 4 à 11 sont indépendants les uns des autres et peuvent
être livrés, relus et éprouvés séparément.

## 3.4 Comment garder les e2e verts

**a) Le vrai blocage n'est pas la suite e2e, c'est `front/tests/test_phases.py`.**
Ce fichier (537 tests) lit `front/static/front/css/hypostasia.css`, sept fichiers
`.js` et quatre templates **en texte brut** et assert leur contenu. On y trouve :

- ~54 assertions sur le CSS : présence de `.lecture-article`, `.hl-extraction`,
  `.pastilles-marge`, `.pastille-extraction`, `#drawer-overlay`,
  `.drawer-carte-compacte`, `.alignement-table`, `.bottom-sheet.ouvert`… ;
- des assertions **négatives** : `#sidebar-left {` doit être absent,
  `@media (max-width: 767px)` doit être absent ;
- des assertions **littérales sur des déclarations** :
  `".pastilles-marge { display: none"`, `"#arbre-overlay { width: 100vw"`,
  `"@media (max-width: 768px)"` ;
- une assertion **sur un commentaire de section du fichier** :
  `"24. Mobile + Bottom sheet (PHASE-21)"`.

Ces assertions ne testent aucun comportement : elles **gèlent un fichier**.
Classes concernées (liste de quarantaine, § 0.6) : `Phase01ExtractionCSSJSTest`,
`Phase02TailwindCSSTest`, `Phase02PolicesLocalesTest`, `Phase02FontBodyTest`,
`Phase04TemplatesContiennentBoutonsTest`, `Phase06VariablesCSSStatutTest`,
`Phase07LayoutMonoColonneBaseHtmlTest`, `Phase07LecturePrincipaleTest`,
`Phase07CSSNettoyageTest`, `Phase07JSNettoyageTest`,
`Phase09FichiersStatiquesTest`, `Phase09MarginaliaJSContenuTest`,
`Phase09HypostasiaJSAdaptationsTest`, `Phase10FichiersStatiquesTest`,
`Phase10BaseHtmlDrawerTest`, `Phase10DrawerJSContenuTest`,
`Phase15FichierJSTranscriptionRythmeTest`, `Phase15CSSStylesTranscriptionTest`,
`Phase18FichiersStatiquesTest`, `Phase18BaseHTMLTest`,
`Phase18AlignementJSContenuTest`, `Phase18KeyboardJSTest`,
`Phase18CSSStylesTest`, `Phase18TemplateAlignementContenuTest`,
`Phase18bArbreTemplateTest`, `Phase18bAlignementJSTest`, `Phase18bCSSTest`,
`FixOOBPanneauExtractionsJSTest`, `DrawerAmelioreTemplateTest`,
`Phase21CSSMobileTest`, `Phase21TemplateBottomSheetTest`, `Phase21BaseHTMLTest`,
`Phase21JSBottomSheetTest`, `Phase21JSMarginaliaTest`, `Phase21KeyboardJSTest`,
`Phase21LecturePrincipaleTest`, `Phase23BoutonToolbarAnalyserHTMXTest`,
`Phase23ConfirmationAnalyseTemplateTest`.

**Traitement proposé** : ne pas les supprimer en masse. Pour chaque classe,
trancher en une ligne : *cette assertion protège-t-elle un comportement, ou un
fichier ?* Les premières sont réécrites contre le nouveau nom (par exemple
`.hl-extraction` reste, `.pastilles-marge` reste) ; les secondes sont
supprimées avec une entrée de CHANGELOG. Le résultat attendu est une réduction
nette du nombre de tests, assumée et documentée.

**b) Invariants durs à ne jamais toucher pendant la bascule.**

*Identifiants* : `#arbre-overlay`, `#drawer-overlay`, `#drawer-backdrop`,
`#drawer-contenu`, `#zone-lecture`, `#readability-content`, `#sidebar-right`,
`#panneau-extractions`, `#titre-toolbar`, `#input-import-fichier`,
`#alignement-modale-container`, `#bottom-sheet`, `#bottom-sheet-backdrop`,
`#bottom-sheet-contenu`, `#btn-fermer-drawer`, `#btn-toolbar-drawer`,
`#btn-fermer-modale-raccourcis`, `#btn-bascule-source`, `#btn-export-alignement`,
`#btn-fermer-alignement`, `#arbre`, `#btn-hamburger-arbre`, `#zone-btn-synthese`,
`#filtre-locuteurs`, `#timeline-audio`.

*Mécanisme d'état* : `pointer-events-none`, `translate-x-full`,
`-translate-x-full`, `hidden` sur les overlays, la sidebar droite et le dropdown
utilisateur ; `mode-lecture-mobile` sur `<body>`.

*Classes métier assertées* : `.hl-extraction`, `.pastille-extraction`,
`.pastilles-marge`, `.titre-page-cliquable`, `.drawer-carte-compacte`,
`.drawer-carte-masquee`, `.drawer-extraction-card`, `.drawer-carte-active`,
`.commentaire-hors-filtre`, `.dossier-node`, `.dossier-toggle`,
`.arbre-section-toggle`, `.btn-aligner-dossier`, `.btn-action-renommer`,
`.btn-action-supprimer-dossier`, `.btn-action-deplacer`,
`.btn-masquer-extraction`, `.btn-restaurer-extraction`, `.alignement-*`,
`.bottom-sheet*`, `.titre-app-desktop`, `.lecture-article`, `.tree-arrow`,
`.lecture-zone-conteneur`, `mark.portion.hl-extraction`.

*Charte* : `test_06_charte_visuelle.py` exige que les 4 polices se chargent, que
les 6 variables `--statut-{nouveau,commente}-{text,bg,accent}` existent, et que
leur contraste soit ≥ 4,5:1. **Ce test tombe au premier jour de bascule si É1
est tranché en faveur de Georgia.** À réécrire en même temps que la décision.

*APIs JS* : `window.bottomSheet`, `window.marginalia`.

*Breakpoints* : `@media (max-width: 768px)` doit exister,
`@media (max-width: 767px)` doit ne pas exister (assertion négative).

**c) Le harnais e2e lui-même.** `front/tests/e2e/base.py` attend
`#arbre-overlay:not(.pointer-events-none)` et `#drawer-overlay:not(.pointer-events-none)`.
`test_14_visibilite.py` utilise un helper local **différent**
(`:not(.-translate-x-full)`). Deux mécanismes pour la même chose : à unifier
dans le lot 3, en une seule modification de `base.py` et de `test_14`.

**d) Les fichiers e2e les plus fragiles**, car sans aucun `data-testid` :
`test_02_lecture.py` (sélecteurs `.titre-page-cliquable`, `#readability-content`,
et même `nav` en sélecteur de balise) et `test_08_curation.py` (dont tous les
tests sont conditionnels `if count() > 0` — ils passeraient même si l'interface
disparaissait : **faible valeur de protection, à renforcer avant le lot 6**).

**e) L'inverse du risque : 176 `data-testid` sur 258 ne sont couverts par aucun
test.** Toute la famille `corpus-base-*` (25), les `taches-*`, `groupe-*`,
`partage-*`, `manifeste-*`, `onboarding-step-*`, `diff-*`. Ces écrans peuvent
être cassés silencieusement. Recommandation : pour les lots 7, 8 et 10, la
recette est **manuelle et documentée**, pas automatique.

**f) `scripts/verifier_les_maquettes.py` (37 contrôles) ne teste PAS
l'application** : il tourne sur `file:///app/tmp/maquettes/*.html`. Il ne cassera
pas à la bascule, et il ne protège pas la bascule. Sa valeur est ailleurs :
c'est la **spécification exécutable du comportement cible** (facettes ET/OU,
écartées = périmètre − citées, garde-fou « les synthèses sont hors du corpus
source », aucun lien de preuve mort, aucune erreur console). À la phase H, ces
37 contrôles devront être **transposés en tests e2e Django**.

**g) `scripts/verifier_le_dev_au_navigateur.py` pointe sur
`https://hyp.nasjo.fr`** — à ne pas lancer depuis ce chantier.

## 3.5 Risques

| # | Risque | Probabilité | Parade |
|---|---|---|---|
| R1 | Perte de feature invisible : un écran non couvert par un test est re-habillé et perd un bouton | **Élevée** (176 testid non couverts) | La grille du § 1 sert de recette ; chaque lot est relu contre elle, action par action |
| R2 | Rupture HTMX : une cible (`#drawer-contenu`, `#corpus-notes`, `#partage-contenu-{pk}`) renommée ou déplacée | Moyenne | Interdire tout renommage d'id dans les lots 1-11 ; le lot 12 seul peut y toucher |
| R3 | Rupture OOB : `hx-swap-oob="innerHTML:#titre-toolbar"` ou `#drawer-titre` casse si l'élément disparaît du chrome | Moyenne | Le lot 3 conserve les ids ; test de non-régression manuel sur l'édition de titre |
| R4 | Les 3 sources de vérité de couleur de statut divergent (CSS, `_card_body.html`, `transcription_audio.py`) | Moyenne | Un seul jeu de tokens ; `transcription_audio.py` traité au lot 0.8 |
| R5 | Purge Tailwind : le HTML généré en Python n'est pas vu par `@source` | Élevée si Tailwind reste | Lot 0.8, ou décision D3 (retrait de Tailwind) |
| R6 | Régression d'accessibilité en copiant l'étalon (pas d'`aria-live`, pas de focus visible, pas de focus trap) | **Élevée** | § 2.3 : les 7 points où l'app doit dépasser l'étalon sont explicites et font partie de la recette |
| R7 | Contraste insuffisant en thème sombre (les accents de l'étalon ne basculent pas) | Élevée | Vérifier les 6 paires `--statut-*` et les 8 familles en sombre, au lot 1, avec la même méthode que `test_06` |
| R8 | Le chantier déborde sur les défauts d'ergonomie de l'audit (D1, D2, D5, D11, D15) | Moyenne | Décision D10 : ce qui entre dans la bascule et ce qui reste au backlog |
| R9 | Deux systèmes de CSS coexistent trop longtemps et l'interface devient incohérente | Moyenne | Les lots 1-3 sont indissociables ; aucun lot ne dure plus de 2 jours |
| R10 | Perte du sens « une police = une provenance » sans remplacement | Certaine si É1 tranché pour Georgia | Décision D1 : si l'on abandonne les 4 polices, il faut nommer le mécanisme de remplacement (contour vs plein, étiquette textuelle) |

## 3.6 Ce que la bascule ne fait pas

Pour éviter que le chantier n'absorbe tout : la pagination et la recherche des
listes (audit D2/P1-2), le filtrage du mobilier PDF (D10/P2-10), les homonymes
« Mes imports » (D15/P2-13) et le grisement des actions anonymes (D13/P2-11)
sont des **corrections d'ergonomie**, pas des corrections de style. Ils restent
au backlog sauf arbitrage contraire (décision D10).

---

# 4. Décisions à faire trancher par le propriétaire

Courtes, actionnables, chacune bloque un lot précis.

**D1 — Typographie.** L'étalon n'utilise que Georgia et `ui-monospace`.
L'application charge 4 polices locales encodant « une police = une provenance »
(B612 = système, B612 Mono = machine, Srisakdi = lecteur, Lora = humain cité),
doctrine écrite dans `front/tailwind/input.css` et vérifiée par
`test_06_charte_visuelle.py`.
→ **(a)** adopter l'étalon et abandonner la doctrine ; **(b)** garder Lora + B612
Mono seulement (humain cité / machine) et prendre Georgia pour le reste ;
**(c)** garder les 4 et adapter l'étalon.
*Bloque le lot 1. Conséquence directe sur `test_06`.*

**D2 — Badges d'hypostases : contour ou rempli ?** L'étalon les veut en contour
(« trois badges ne doivent pas peser plus que la phrase qu'ils qualifient ») et
laisse les `--hypostase-*-bg` inutilisés. L'application les remplit.
*Bloque le lot 1.*

**D3 — Tailwind reste-t-il ?** L'étalon n'a aucun utilitaire. Garder Tailwind
signifie deux vocabulaires (`text-slate-600` et `var(--encre-douce)`) ; le
retirer signifie réécrire toutes les classes utilitaires des 44 templates, et
retirer aussi le plugin `typography` dont dépend `#readability-content`.
→ **(a)** retrait complet au lot 12 ; **(b)** conservation pour la mise en page
seule (flex/grid/spacing), tokens pour tout le reste ; **(c)** statu quo.
*Bloque le lot 12, oriente tous les autres.*

**D4 — Thème sombre : dans ce chantier ou après ?** L'étalon fournit le
mécanisme à 3 états mais aucune persistance, et n'a jamais vérifié le contraste
de ses accents en sombre. L'inclure ajoute environ 1 jour (audit du contraste
compris).
*Bloque le lot 1.*

**D5 — Un seul système de toasts.** SweetAlert2 top-end (54 `HX-Trigger
showToast`) + `.ws-toast` bas-droite maison, contre `.pile-toasts` centré en bas
dans l'étalon. Unifier signifie soit retirer SweetAlert2 (qui sert aussi aux
prompts de renommage et aux confirmations : 7 fichiers JS), soit l'habiller.
*Bloque le lot 1.*

**D6 — `base.html` : blocs ou cascade ?** La phase F a tranché « branche dans la
cascade » (CHANGELOG du 8 août, décision 2). La phase H ajoute 3 écrans. À 15
branches, la cascade devient difficile à lire.
→ **(a)** conserver la cascade ; **(b)** introduire `{% block contenu %}` au lot 3.
*Bloque le lot 3 et la phase H.*

**D7 — L'arbre liste-t-il encore les pages ?** L'étalon a explicitement décidé
que l'arbre ne montre plus que des contenants, à cause de la relation N-N
notes/carnets. L'audit D2 confirme le symptôme (120 lignes injectées dans un
tiroir de 320px).
*Bloque le lot 7. Casse `test_01` (`arbre-page-link`) si tranché pour l'étalon.*

**D8 — Le questionnaire et la sidebar droite : suppression ou résurrection ?**
`vue_questionnaire.html` (94 l.), `panneau_analyse.html` (50 l.),
`extraction_results.html` (110 l.) et `extraction_manuelle_form.html` (117 l.)
ciblent `#panneau-extractions`, qui vit dans une `<aside class="hidden">`
conservée seulement pour les OOB swaps. Soit ces écrans sont morts et partent au
lot 0, soit ils doivent retrouver un point d'entrée.
*Bloque les lots 0 et 8. 371 lignes en jeu.*

**D9 — `_card_body.html` déménage-t-il dans `front/` ?** Le composant le plus
visible du produit vit dans `hypostasis_extractor/templates/`. Le déplacer touche
5 points d'inclusion.
*Bloque le lot 6.*

**D10 — Quels défauts de l'audit entrent dans le chantier ?** Proposition :
**dedans** parce qu'ils sont indissociables du style — D3 (titres corpus), D5
(fil d'Ariane et état actif), D11 (pastilles 24px, focus visible, surlignage au
survol), D12 (thème sombre, si D4), D16 (`.zone.large`), D6 (tiroir sous la
nav) ; **dehors** parce qu'ils sont fonctionnels — D1 (extractions mobiles), D2
(recherche et pagination), D10 (mobilier PDF), D13 (actions anonymes), D15
(homonymes).
*Bloque le cadrage global.*

**D11 — Le budget de test.** La quarantaine du § 3.4 supprimera net plusieurs
dizaines de tests qui figent des fichiers plutôt que des comportements. Est-ce
accepté, et faut-il compenser en ajoutant des e2e sur les 176 `data-testid`
aujourd'hui non couverts (notamment `corpus-base-*`, `taches-*`, `partage-*`) ?
*Bloque le lot 0.*

---

*Rédigé le 9 août 2026 par lecture de code seule, sans exécution de test ni de
navigateur. Sources vérifiées : `front/urls.py`, `front/views.py`,
`front/views_corpus.py`, `front/views_auth.py`, `front/views_alignement.py`,
`front/views_groupes.py`, `front/views_invitation.py`, `front/views_taches.py`,
`front/templates/front/**` (44 fichiers), `hypostasis_extractor/templates/**`
(28 fichiers), `front/static/front/css/hypostasia.css`,
`front/tailwind/input.css`, `front/static/front/js/**` (11 fichiers),
`front/tests/test_phases.py`, `front/tests/e2e/**` (21 fichiers),
`scripts/verifier_les_maquettes.py`, `scripts/verifier_le_dev_au_navigateur.py`,
`tmp/maquettes/**`, `PLAN/audit-ux-ui-2026-08-08.md`,
`PLAN/corpus-phase-f-cahier-des-charges.md`, `SPEC-synthese-carnet.md`,
`CHANGELOG.md` (entrées des 8 et 9 août).*
