# Bascule CSS — état au 9 août 2026 (nuit) : chantier TERMINÉ (T4-T10)

## Fait ce soir (vérifié par 3 agents + navigation réelle)

- **Écrans corpus/synthèse** : design system complet de l'étalon
  (`front/templates/front/corpus/_style_maquette.html`, scopé
  `.zone-corpus`) — carnet, notes, wikis, synthèses, article, panneau
  de preuve latéral, diff d'opérations.
- **Couche globale** (`front/static/front/css/maquette.css`, source
  unique des tokens) : body Georgia/papier, barre sombre monospace,
  REMAPPAGE des ~50 tokens de hypostasia.css (surfaces/textes/bordures
  → palette papier, halo d'ancre bleu → ambre), re-teinte des
  utilitaires Tailwind, fonds sémantiques DANS leur teinte
  (ambre/vert/info/danger), accueil onboarding, lecture en Georgia
  (décision D1 : Lora quitte le corps de texte), surlignages
  d'extraction recolorés (statuts riches restés en base), menus
  déroulants de la barre réparés (étaient blanc-sur-blanc), focus
  visible partout (papier sur la barre sombre), reduced-motion global.
- **Accessibilité** : teintes Wong plus jamais en texte (1,29:1 → encre
  sur fond teinté 18 %), soulignements de verdicts ≥ 3:1 (mélanges
  80-85 %), cibles élargies (boutons d'ordre, renvois), focus des
  puces-filtres visible, panneau de preuve fermé non tabulable
  (visibility) + role dialog + focus donné/rendu + Escape conditionné,
  états du bouton tâches lisibles sur la barre, noscript des filtres
  fonctionnel.
- **Accès direct** : /wikis/{id}/ et /syntheses/{id}/ servent la page
  COMPLÈTE hors HTMX (branche article_preloaded de base.html) ; les
  collections /carnets/{pk}/wikis|syntheses/ redirigent vers l'écran
  carnet.

## Rapports d'agents (9 août, nuit) — sources
Visuel (Playwright 6 écrans + mobile), audit statique des couches,
audit accessibilité (ratios calculés). Constats bloquants TOUS corrigés
le soir même. Restes ci-dessous.

## T4 et T5 — FAITS (9 août, nuit, vérifiés au navigateur)

**T4 — lecture.** Remappage à la source des échelles Tailwind
`--color-blue-*` / `--color-indigo-*` → `var(--info)` dans maquette.css
(atteint `hover:`, `prose-a:`, `prose-blockquote:`, que la liste de
classes ne pouvait pas couvrir). Liens du corps 7,71:1, blockquote au
filet `--info`, légendes/`th` en monospace, chrome de la page en
monospace, halo des pastilles en ambre, gap des pastilles à 8px
(exception d'espacement WCAG 2.5.8 : la géométrie ne peut pas grandir,
le clip-path du triangle l'interdit). Trois défauts trouvés par la
vérification et corrigés : `@keyframes hl-pulse` et `bloc-flash-pulse`
en bleu Tailwind écrit en dur (keyframes de même nom **redéfinies**
dans maquette.css — hypostasia.css intacte) ; nom d'utilisateur de la
barre **noir sur noir** (1:1 → 10,56:1, un `<span>` à quatre niveaux
échappait aux sélecteurs « enfant direct ») ; avatar et lien Connexion
sur la barre (2,18:1 → 10,18:1) ; bouton de fermeture du bottom sheet
(4,49 → 5,24:1).

**T5 — les 3 écrans corpus** portés sur `.zone-corpus`/`.ligne-note`.
Vérifié : mêmes polices, tailles et largeur (64rem) que le témoin
carnet_detail — les quatre écrans forment un système. Tous les
`data-testid` conservés. Design system enrichi de `.lien-navigation`,
`.vide`, `.rangee-champ`, `.bouton-icone`, `.marque-visibilite`,
`.groupe-actions`.

### Écarts assumés vs l'étalon (décidés ici, T4-T5)
- **`--filet-controle` (3,27:1) remplace `--filet` (1,28:1)** sur le
  contour des champs, boutons et flèches d'ordre. L'étalon dessine ses
  contrôles avec un filet à 1,28:1, sous les 3:1 de WCAG 1.4.11 quand
  ce contour est le seul indice visuel. Les séparateurs décoratifs
  restent en `--filet`.
- **Pastilles de marge : 16px conservés** plutôt que 24px, avec un gap
  porté à 8px. Le `clip-path` du triangle interdit à la fois
  d'agrandir la boîte et d'ajouter un pseudo-élément de cible.
- **Visibilité en icône ET mot** dans les listes (l'étalon n'affiche
  que l'emoji).

### Non vérifié en navigation (à retester quand les données existeront)
- `figcaption` : aucune note du dev n'en contient (`blockquote` et
  `table` ont été trouvés dans les notes 9, 11, 45, 122, 611 et
  vérifiés). Règle vérifiée par lecture seulement.
- `corpus-base-categorie`, `-crayon`, `-axe`, `-categorie-pastille` :
  la seule base du dev (« default ») n'a aucun axe. Rendu couvert par
  les tests Django, pas par le navigateur.
- **`.puce-categorie`** (les puces de filtre) : aucun carnet du dev
  n'a d'axe de classement, donc ni le rendu nominal ni le repli
  `@supports` n'ont pu être mesurés à l'écran. Un carnet doté d'axes et
  de catégories manque à la recette.

## T6 a T9 — FAITS (9 août, nuit, vérifiés au navigateur)

**T6 — les 5 pages nues** sur un gabarit `.page-nue` (une
`.zone-corpus` de 26rem) qui réutilise `.champ-*`, `.bouton-plat`,
`.surface-formulaire`, `.message-etat`. Ce sont les premières pages
hors `base.html` à charger la couche maquette. Un défaut trouvé et
corrigé : `font-family:inherit` de `.champ-texte` battait la règle
`.mono` et affichait le token API en serif (0/O indistinguables).

**T7 — le thème sombre.** Trois états + persistance `localStorage`
(que l'étalon n'a pas), appliqués dans le `<head>` avant le premier
rendu. Les 8 surfaces sont celles de l'étalon **au bit près** (vérifié
contre le fichier). Cinq défauts trouvés par la vérification, tous
corrigés : l'onboarding entier resté en Tailwind (titre à 1,02:1) et
son îlot `#fafbfc` ; les contours `.border-slate-300` et
`.arbre-footer-btn` restés en `--filet` ; les soulignements de statut
en `rgba()` fixe ; les ombres portées noires invisibles en sombre ; et
l'absence de bascule sur les pages nues. Puis quatre autres au second
passage : l'onglet actif du corpus (voir ci-dessous), `.onglet-accueil`,
les deux `--statut-*-text` non basculés, et le survol du bouton de
thème.

**T8 — les overlays.** Modale d'alignement, badges d'hypostase du
drawer, bottom sheet, voiles. **Piège trouvé par la vérification** : la
règle visait `.tableau-alignement`, classe de l'ÉTALON, absente de
l'application — 35 fonds blancs survivaient. Les vraies classes sont
`.alignement-th-page`, `.alignement-th-corner`,
`.alignement-td-hypostase`. Leçon générale : **une règle écrite
d'après la maquette doit être vérifiée contre le gabarit Django.**

**T9 — la purge.** `lora-medium.woff2` et `lora-semibold.woff2`
supprimés (aucun `@font-face` ne les nomme ; Lora reste vivante pour
`.typo-citation`). Les deux tests-mensonges réécrits.

### Restes accessibilité — TOUS TRAITÉS
Lien d'évitement ; `aria-expanded`/`aria-haspopup`/`aria-controls` +
Échap avec retour du focus sur le menu utilisateur ; tablist complet du
carnet (`aria-controls`, `role=tabpanel`, `aria-labelledby` qui suit
l'onglet courant, flèches en **activation manuelle** — l'activation
automatique rechargeait `#zone-lecture` dès qu'on traversait « Notes ») ;
`aria-live` resserré sur `#corpus-notes` ; repli `@supports` pour
`:has()` ; pastilles traitées par l'espacement (cf. T4).

### Le troisième réservoir de couleurs : Tailwind Typography
Découvert à la toute fin, sur une note contenant une citation en bloc :
le plugin `@tailwindcss/typography` porte ses propres couleurs dans des
variables **`--tw-prose-*`** (en `oklch`), qu'aucun sélecteur du
chantier ne touchait — ni le remappage des échelles `--color-*`, ni les
règles par classe. Le texte d'un `blockquote` tombait à **1,07:1** en
sombre : un bloc vide avec une barre bleue. Les 16 variables sont
désormais remappées à la source sur
`.prose, .lecture-article, #readability-content`.
**Règle générale du chantier, confirmée trois fois** : quand une
couleur résiste, chercher la VARIABLE qui la porte plutôt qu'ajouter un
sélecteur — il y avait trois réservoirs (les tokens de hypostasia.css,
les échelles `--color-*` de Tailwind, les `--tw-prose-*` du plugin), et
seuls les `@keyframes` et les `rgba()` écrits en dur ont exigé une
surcharge classique.

Corollaire trouvé dans la foulée : un utilitaire **`prose-headings:text-slate-900`**
posé sur le conteneur pose un `color` en dur sur les descendants et bat
la variable. Les six utilitaires `prose-*` COLORÉS de
`lecture_principale.html` ont donc été retirés du gabarit ; seules
restent les classes de mise en forme (graisse, marges, arrondis).

### Deux pièges de JavaScript inline, à connaître
- **Un `<script>` inline placé AVANT l'élément qu'il cherche** ne le
  trouve pas au chargement direct de la page (F5, lien externe), et le
  garde `if (element)` ne fait alors plus rien de toute la vie de la
  page. Le même code marche pourtant après un swap HTMX, qui exécute
  les scripts une fois le fragment entier inséré — d'où un défaut
  invisible en navigation interne. Résoudre l'élément au moment de s'en
  servir, pas au parsing.
- **Playwright `check()` refuse un input invisible** : depuis que les
  cases de filtre sont masquées au profit des puces, les tests doivent
  cliquer le label, comme un utilisateur.

### CSS mort découvert (à supprimer quand hypostasia.css sera vidée)
- **`.ws-toast*`, hypostasia.css:1668-1810, ~150 lignes** : zéro
  occurrence de `ws-toast` dans un `.js`, un `.html` ou un `.py`. Les
  « deux systèmes de toasts » du cahier des charges (§ 1.6 b) n'en font
  plus qu'un depuis longtemps : SweetAlert2. C'est lui qui est habillé.
- `.alignement-footer` et `.alignement-backdrop` : sélecteurs sans
  élément correspondant dans le gabarit.

### Écarts assumés supplémentaires (T6-T9)
- **Les accents basculent en sombre**, alors que l'étalon les laisse
  tels quels : `--info` y tombe à 2,26:1, `--cible` à 3,51:1. Même
  chose pour les 8 familles d'hypostases, employées en texte.
- **`--filet-statut-commente`** : l'ambre `#E69F00` ne fait que 2,20:1
  sur le papier clair. Là où il porte un ÉTAT (onglet actif,
  soulignement de statut), il est foncé de 30 % d'encre en clair, et
  reste pur en sombre où il vaut 7,9:1. Le fond teinté, lui, ne bouge
  pas.
- **Quatre `--hypostase-*-text` foncés d'un cran en clair** (objet,
  spéculatif, mode, empirique) : ils étaient déjà limites sur du papier
  nu (4,64:1 pour objet) et tombaient sous 4,5:1 sur un fond dérivé de
  leur propre teinte.
- **`h1` des pages nues à 1,4rem** contre 1,65rem ailleurs : la page
  fait 26rem de large.
- **La puce de liste (`ul::marker`) reste à 3,03:1 en clair.** Un
  ornement typographique n'est ni un indicateur d'état (1.4.11) ni du
  texte porteur d'information (1.4.3) : la structure de liste est
  portée par le balisage `ul`/`li`, qu'une technologie d'assistance
  annonce indépendamment de la couleur du marqueur. La forcer en encre
  alourdirait chaque liste sans rien apprendre au lecteur.
  **Réserve** : ce raisonnement tombe si une puce colorée sert un jour
  à distinguer des types d'items — elle deviendrait alors porteuse
  d'information, et le seuil s'appliquerait.
- **Les filets décoratifs (`hr`, séparateurs) restent à 1,28:1.** Même
  raisonnement : ils ne portent aucune information.

## T10 — FAIT (9 août, nuit, vérifié au navigateur)

Les écrans staff de `hypostasis_extractor` sont écrits **entièrement**
en utilitaires Tailwind : ~300 occurrences colorées sur 18 gabarits.
**Aucun gabarit n'a été modifié** — les cinq échelles restantes
(slate/gray, green/emerald, red/rose, amber/yellow/orange,
violet/purple) sont remappées à la source, le NIVEAU portant le rôle
(50-100 fond, 200-300 filet, 400+ teinte pleine). Les ambres partent
sur `--faible`, pas sur `--statut-commente` : en texte l'ambre pur ne
fait que 2,2:1.

Six défauts que le remappage seul ne pouvait pas corriger, trouvés par
la vérification et réparés :
1. un fond sémantique PLEIN portait du texte `blanc` — en sombre ces
   fonds s'éclaircissent et le blanc y tombait à **1,52:1**. Le texte
   y est désormais `--papier`, qui suit le thème ;
2. `.text-slate-300` sert de TEXTE (numéros d'ordre à 9px) là où le
   niveau 300 est réservé aux filets de contrôle : 3,02:1 ;
3. **241 champs** dessinés avec `border-slate-200`, filet décoratif à
   1,19:1 → les éléments de formulaire prennent `--filet-controle` ;
4. **`focus:outline-none` battait le focus visible global** (0,2,0
   contre 0,1,0) — un champ focalisé au clavier ne montrait plus rien
   quand son `ring` était absent. Le focus passe en `!important` ;
5. sous 640px, les rangées de contrôles poussaient leur « Sauver »
   hors du viewport, sans défilement pour le rattraper ;
6. les deux écrans de versions n'avaient aucun conteneur.

### Le `<style>` inline de l'éditeur : fausse alerte
Le cahier des charges annonçait « `analyseur_editor.html` (434 l.)
contient un `<style>` inline » — le fichier fait 434 lignes, le style
en fait **8**, et ne contient aucune couleur (uniquement
`overflow`/`resize` des textareas). Rien à tokeniser.

### Le code mort du poste 0.1 — SUPPRIMÉ
L'inventaire parlait de « trois vues cassées ». Vérification faite,
c'étaient trois **branches HTML à l'intérieur de ViewSets DRF qui
servent aussi du JSON** : supprimer les vues aurait cassé l'API. Elles
étaient **doublement mortes** — leur template étend `core/base.html`,
absent du dépôt, **et** la condition
`request.accepted_renderer.format == 'html'` ne pouvait jamais être
vraie, aucun renderer HTML n'étant configuré (DRF s'en tient à JSON +
BrowsableAPI, dont le format est `api`). Vérifié en réel avant et
après : `/api/extraction-jobs/` et `/api/extraction-examples/`
répondent 200 dans les deux formats.
Retirés : les 3 branches (`views.py`), et 4 gabarits — `job_list.html`,
`job_detail.html`, `example_list.html` et `analyseur_list.html`
(orphelin, aucune référence), soit ~285 lignes.
**Leçon** : « vue cassée » dans un inventaire mérite d'être rouverte
avant d'être supprimée — ici la vue était bien vivante, seule une de
ses branches était morte.

## Les toasts — FAIT (dernier reste d'accessibilité)
Les toasts SweetAlert n'étaient annoncés par aucun lecteur d'écran.
Deux décisions : (1) une région live **persistante** dans `base.html`,
car une région créée en même temps que son contenu n'est pas annoncée
de façon fiable ; (2) `annonces.js` **enveloppe `Swal.fire` une seule
fois** plutôt que de modifier les sept fichiers qui l'appellent — le
prochain toast écrit ailleurs sera annoncé sans que personne y pense.
Les modales sont exclues (SweetAlert les annonce déjà). Vérifié au
navigateur sur un vrai toast du produit.

## Lot « architecture de page » — FAIT (vérifié au navigateur)
Quatre ajouts de structure : le **fil d'Ariane** `Base › Carnet › Note`
avec sa **bascule de carnet** (le N-N a tué l'arbre : une note sous deux
carnets n'a pas de parent unique, le fil montre un chemin et le chevron
en change) ; les deux **boutons de création** dans l'en-tête du carnet,
qui activent l'onglet portant déjà le formulaire ; l'**onglet
Alignement**, qui rouvre le flux existant ; les **sous-notes enrichies**
(source, nom de fichier, compteurs) sans une requête de plus.

Six écarts trouvés par la vérification, tous corrigés. Trois méritent
d'être retenus :
- **Un élément `sticky` se cale sur la boîte de CONTENU**, pas sur le
  bord du conteneur défilant. Le `p-8` de `#zone-lecture` figeait donc
  le fil 32px trop bas, en laissant défiler du texte dans la bande
  au-dessus. Correctif : `#zone-lecture:has(> .fil-ariane) {
  padding-top: 0 }`, sous `@supports`.
- **Un écouteur posé sur `document` par un fragment réinjecté à chaque
  échange HTMX s'empile à l'infini**, chaque exemplaire retenant un
  nœud détaché. Il doit être posé UNE FOIS (drapeau sur `window`) et
  relire le nœud vivant à chaque événement.
- **Un débordement horizontal ne vient pas toujours de ce qu'on croit.**
  À 390px, `#zone-lecture` mesurait 558px : les tableaux de
  transcription étaient les suspects évidents (et ils avaient bien
  besoin d'`overflow-x:auto`), mais le coupable était le formulaire
  « + Ajouter à… » du bloc carnets — un flex sans wrap dont le
  `<select>` porte le nom de tous les carnets disponibles. C'est la
  chaîne d'ancêtres de l'élément le plus à droite qui l'a désigné ;
  sans elle, on aurait classé l'affaire après le premier correctif.

### Deux constats à remonter (hors périmètre front)
- ~~`/alignement/tableau/?dossier_id=N` ne vérifie aucune permission~~
  **CORRIGÉ le 9 août** (voir le CHANGELOG). La faille touchait aussi
  `?page_ids=`, vecteur plus grave encore, et `export_markdown`.
  Filtrage silencieux (interdit indistinguable d'absent), 11 tests
  dédiés, et trois classes de tests existantes qui passaient *grâce* au
  trou ont été connectées.
- **La durée et les locuteurs d'un audio ne sont pas sur `Page`** — ils
  dérivent de la transcription. Les afficher dans les sous-notes
  demanderait une requête lourde par ligne : écarté, comme convenu.

### Non vérifiable faute de données
Aucune note du dev n'appartient à plus d'un carnet : la bascule **sur
une note** (relire la même note sous un autre classement) n'a pas pu
être exercée en réel. Vérifié par lecture du gabarit et par
`?carnet=` forcé — un identifiant invalide est bien ignoré.

## Lots restants
Aucun sur le périmètre de la bascule CSS.

## Deux sessions en parallèle : une base de test par session
Les deux sessions de développement lançaient `manage.py test` sur la
MÊME base `test_hypostasia` : chaque run détruisait celui de l'autre en
plein vol (EOFError sur « voulez-vous supprimer la base ? », deadlocks,
43 erreurs fantômes en une passe). Chaque session a désormais la sienne :
`hypostasia/settings_test_fable.py` et `hypostasia/settings_test_opus.py`
(`TEST["NAME"]` dédié), à passer en `--settings=…`.
La contrainte machine ne change pas pour autant : deux bases coexistent
sans peine, deux runs LOURDS simultanés non — le serveur a 8 Go et
héberge aussi la prod.

## Recette au navigateur — le piège d'environnement
Le dev n'expose aucun port sur l'hôte : Playwright doit tourner DANS le
conteneur. Mais `hypostasia_dev_web` (daphne, :8000) **ne sert pas les
fichiers statiques** — c'est `hypostasia_dev_nginx` qui le fait. Un
agent qui navigue sur `http://localhost:8000/` obtient une page NUE
(404 sur tout le CSS) et rapporte des écarts imaginaires. Recette qui
marche : lancer chromium avec
`--host-resolver-rules="MAP localhost <ip-de-hypostasia_dev_nginx>"`
puis naviguer sur `http://localhost/…` — ALLOWED_HOSTS est satisfait et
nginx sert les statiques.

## Restes accessibilité — soldés
Tous les points de cette liste ont été traités dans les lots T4 à T9
(voir ci-dessus). Il reste un point OUVERT, hors CSS :
- **Les toasts SweetAlert ne sont annoncés par aucun `aria-live`.** Le
  correctif est dans `hypostasia.js` (options SweetAlert), pas dans une
  feuille de style — donc hors du périmètre « front pur, CSS » de ce
  chantier. À traiter avec le lot T10 ou séparément.

## Ce que les agents ont validé
Barre sombre lisible partout (10,5:1), re-teinte des gris = gain de
contraste net (slate-400 : 2,56 → 5,42), aucun data-testid perdu,
marks d'extraction intacts avec leurs formes, aucun débordement mobile,
écrans corpus « zéro utilitaire coloré survivant ».
