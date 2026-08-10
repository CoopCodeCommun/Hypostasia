# Changelog — Hypostasia V3

> Journal des modifications par phase. Format bilingue FR/EN.
> Reverse chronological order.

---

## 2026-08-10 — R3 : L'ANCIEN MOTEUR EST MORT
## (~1 100 lignes retirees, le flag `Page.moteur` avec)

**Quoi / What :** fin du chantier ouvert par la decision du 10 aout. Il
n'y a plus qu'un moteur d'ancrage ; le code qui permettait d'en choisir
un autre a disparu. / One engine left; the code that chose between two
is gone.

### ⚠️ DEPLOIEMENT EN DEUX TEMPS — A LIRE AVANT DE METTRE EN PRODUCTION

La base de dev a ete reconvertie AVANT cette livraison. Une autre base —
**la production**, une sauvegarde restauree — a toutes ses pages sur
l'ANCIEN moteur. Deployer ce code d'un coup la-bas ne casserait rien
bruyamment : les pages s'afficheraient sans leurs surlignages, en
silence. La migration `core.0056` **REFUSE donc de s'appliquer** tant
qu'une page reste ANCIEN, et dit quoi lancer.

L'ordre est le suivant, et il n'y en a pas d'autre :

1. deployer la version **R2** (celle qui porte encore le flag ET la
   commande `basculer_vers_le_moteur_element`) ;
2. `manage.py basculer_vers_le_moteur_element --a-blanc`, lire le bilan,
   puis le lancer pour de vrai ;
3. deployer **R3** : la migration 0056 constate « 0 page sur l'ancien
   moteur » et retire le champ.

La commande de reconversion est SUPPRIMEE dans R3 (elle selectionnait
les pages par un flag qui n'existe plus). C'est un outil de migration a
usage unique : il vit dans R2, qui reste accessible par git.
/ Two-step deployment: reconvert with R2, then deploy R3.

### Ce qui a ete retire

| Ce qui part | Lignes |
|---|---|
| `front/utils.py` — le pont texte<->HTML | **504** |
| `analyser_page_task` + son routage par moteur | **440** |
| La classe de tests de l'annotation par offsets | 109 |
| La fabrique de pastilles (JS + CSS), R2 | ~120 |
| Le champ `Page.moteur`, sa classe et ses 12 points de decision | migration 0056 |

`extraire_texte_depuis_html` etait la SEULE fonction de `front/utils.py`
a avoir une vie propre : elle derive `text_readability` a l'ingestion, ce
qui n'a rien a voir avec l'ancrage. Elle est deplacee dans
`front/services/texte_depuis_html.py` (105 l.) avec la seule aide dont
elle depend, sous un nom qui dit ce qu'elle fait.

### UN BUG TROUVE EN CHEMIN, ET IL ETAIT SERIEUX

Cinq actions du panneau (`panneau`, `creer_manuelle`, `supprimer_ia`,
`promouvoir_entrainement`, `ia`) renvoyaient un swap « out of band » qui
REMPLACE tout `#readability-content` — construit par l'ancien moteur.
Sur une page ELEMENT, **creer une extraction a la main effacait donc les
blocs, les boutons d'operations et les ancres** jusqu'au rechargement
complet. Ces vues ne consultaient jamais `Page.moteur` : ecrites avant
lui, jamais rouvertes depuis. Le rendu passe desormais par le meme
service que la lecture (`_contenu_de_lecture`), donc par la meme verite.
3 tests (`front/tests/test_oob_lecture_element.py`).

### Ce qui a ete ADAPTE plutot que supprime

- Le test e2e du bottom sheet mobile batissait une page ANCIEN dont les
  surlignages venaient de `html_annote` : sans blocs ni ancres, il
  n'avait plus rien vers quoi scroller. Reconstruit sur ELEMENT (20
  blocs, ancrage sur le 15e).
- `core/tests/test_moteur_flag.py` verifiait un champ qui disparait. Il
  prouve maintenant la seule chose qui reste : que la garde de la
  migration 0056 refuse une base non reconvertie ET dit quoi faire.
- Trois tests dont le NOM parlait d'une « page ancienne » testent en
  realite une page SANS ELEMENT — renommes en consequence. Un nom qui
  ment est un defaut.
- Les 12 conditions `if page.moteur == ELEMENT` deviennent
  inconditionnelles ; le tri du panneau suit toujours l'ancre.

### Migration
- **Migration necessaire / Migration required :** OUI —
  `core.0056_suppression_du_flag_moteur`, avec son garde-fou. Voir la
  procedure en deux temps ci-dessus.

---

## 2026-08-10 — R2 : la base est 100 % ELEMENT, les pastilles de marge
## sont mortes, et le filtre par contributeur revit

**Quoi / What :** premieres etapes de la mort de l'ancien moteur, apres
la reconversion R1. / First steps of the old engine's removal.

**ETAPE 1 — les 2 dernieres pages ANCIEN.** Je les croyais vides et
pretes a supprimer. Verification : **la page 97 porte 4,17 Mo de HTML**
(un .docx de huit images en base64, zero caractere de texte). La
supprimer aurait detruit un document.

Le vrai obstacle n'etait pas la page, c'etait ma propre garde. Elle
refusait de basculer une page sans bloc « parce que le moteur ELEMENT
n'aurait rien a afficher » — or le templatetag `blocs_de_lecture_de`
retombe sur `html_readability` quand une page ELEMENT n'a aucun element.
Le bon critere n'est pas « a-t-elle des blocs ? » mais « la bascule
change-t-elle ce qu'on voit ? » : sans extraction, le rendu est
IDENTIQUE ; avec des extractions, on perdrait des surlignages, donc on
s'abstient. Les deux pages sont passees ELEMENT — **213 pages, 100 %
ELEMENT** — et la page 97 affiche toujours ses 8 images (verifie au
navigateur : 8 `<img>`, 8 visibles, zero erreur JS).

**ETAPE 2 — `marginalia.js`.** Il n'etait PAS supprimable en bloc : il
porte `ouvrirDrawerEtScrollerVersCarte`, vivante et appelee par quatre
autres scripts (clavier, dashboard, hypostasia, drawer). Ce qui est mort
en est retire :
- `construirePastillesMarginales`, neutralisee le 10 aout, ne faisait
  plus que nettoyer d'eventuels residus — plus rien, ni serveur ni JS,
  ne produit une pastille. Supprimee avec ses appels dans `hypostasia.js`
  et `drawer_vue_liste.js`, ses declencheurs (`DOMContentLoaded`,
  `htmx:afterSwap`) et son alias global ;
- **le CSS des pastilles** (~50 l. dans `hypostasia.css` et
  `maquette.css`). Prudence : plusieurs regles etaient PARTAGEES avec
  `.indicateur-statut`, bien vivant dans `_card_body.html` — seul le
  selecteur mort a ete retire de celles-la, jamais la regle entiere. Un
  test de contre-epreuve le protege desormais.

**LE FILTRE PAR CONTRIBUTEUR REVIT.** Il estompait les pastilles ;
celles-ci disparues, il ne trouvait plus un seul noeud et ne faisait
**RIEN, sans que rien ne le dise** — c'etait un des restes du chantier A.
Il agit maintenant sur `mark.hl-extraction`, la seule ancre qui existe.
Verifie au navigateur : 235 ancres estompees sur 238 (3 gardees), 0
apres reset. Le style baisse le SURLIGNAGE et non le texte : le
contraste de lecture est preserve.

**Non-regression prouvee, pas supposee** : clic sur une ancre non
superposee -> la carte correspondante s'active, correspondance exacte
(meme mark 16735 que la verification d'avant ces suppressions). Le
decalage sur les marks SUPERPOSES est un defaut preexistant, deja releve.
545 tests `test_phases` verts.

**Quatre tests-mensonges remplaces par des gardes anti-retour** : ils
exigeaient l'existence de la fabrique de pastilles, de son
`DOMContentLoaded`, et de leur CSS. Ils protegeaient un comportement
supprime ; ils verifient desormais qu'il ne revient pas.

| Fichier | Changement |
|---|---|
| `core/management/commands/basculer_vers_le_moteur_element.py` | `_sort_d_une_page_qui_n_a_aucun_bloc` : le critere devient « la bascule change-t-elle l'affichage ? » |
| `front/static/front/js/marginalia.js` | fabrique de pastilles supprimee, filtre recable sur les ancres inline, en-tete honnete |
| `front/static/front/js/hypostasia.js`, `drawer_vue_liste.js` | appels a la fabrique retires |
| `front/static/front/css/hypostasia.css`, `maquette.css` | CSS des pastilles retire, `.ancre-hors-filtre` ajoute |
| `front/templates/front/base.html` | bumps `?v=` (maquette 24, hypostasia 35, marginalia 23) |
| `core/tests/test_reconversion_moteur.py`, `front/tests/test_phases.py` | gardes anti-retour |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — R1 : LA RECONVERSION — l'ancien moteur n'affiche plus rien
## (540 pages basculees, 983 commentaires intacts) + allegement de la base

**Quoi / What :** decision de gouvernance du 10 aout (le moteur ELEMENT
devient le SEUL moteur) appliquee A LA BASE. 540 des 542 pages ANCIEN
sont passees sur ELEMENT ; il reste 2 pages sans un bloc a lire, laissees
en ANCIEN a dessein. / The 540 remaining ANCIEN pages now run on ELEMENT.

**Ce que la mesure a change dans le plan.** La reconversion s'annoncait
couteuse (§ 9.5 : « reconvertir_avec_docling », et Docling = OOM sur cet
hote). Mesure prealable : **537 des 542 pages portaient DEJA leurs
elements** (dormants, issus des phases de test) et **94 % des extractions
etaient deja ancrees**. Il ne manquait que le flag. Aucun appel Docling
n'a ete necessaire, et la bascule a pris 13 secondes.
/ Measured first: the expensive part was already done.

**Le trou trouve dans la commande existante.**
`basculer_vers_le_moteur_element` (a) ne traitait que les pages SANS
elements — 537 sur 542 lui etaient invisibles, y compris par `--page` —
et (b) ne posait JAMAIS `Page.moteur`, etant anterieure a BR-A. D'ou
l'etat constate : des pages pourvues d'elements ET d'ancrages, toutes
affichees par l'ANCIEN moteur.

**Ce que la reconversion a refuse de faire.** Deux relectures adverses
ont montre que « dans les bornes du texte » n'est pas « au bon
endroit » :
- **47 ancres neuves refusees** : le span etait exploitable mais ne
  montrait pas la citation (dont une de 500 caracteres dont les offsets
  ne couvraient que « l' »). Une ancre n'est posee que si le texte
  surligne EGALE la citation, ou la couvre a 95 % ou plus, la couverture
  etant bornee **dans les deux sens** — surligner sept fois trop est le
  meme mensonge que surligner deux caracteres.
- **1 402 ancres DORMANTES detachees** (5,0 % des 28 096) : ces ancres
  n'avaient jamais ete auditees et devenaient officielles par la
  bascule ; celles-la designaient un passage sans rapport avec leur
  citation — **36 portaient un commentaire humain**. Decision du
  proprietaire : detacher les mensongeres, garder les tronquees (une
  partie du bon passage reste honnete). Detacher n'efface rien —
  extraction et commentaires restent, et chaque pk detache est NOMME sur
  la sortie pour le triage.
  *(Une premiere mesure annoncait 1 746 dont 59 commentees : elle collait
  les portions d'une citation a cheval sur deux blocs SANS separateur et
  condamnait 343 ancres justes. Chiffres corriges apres correctif.)*
- **L'ambiguite est reperee en placant les elements deux fois**, une fois
  depuis le debut et une fois depuis la fin : tout element que les deux
  lectures separent avait le choix, on n'y ancre pas. Regarder la « zone
  libre » autour de la position gloutonne revenait a supposer resolu ce
  qu'on cherchait a verifier.

**Le repli par recherche de texte a ete SUPPRIME** (~100 l. de code
mort) : mesure sur les 1 707 extractions a offsets 0-0 — il en retrouve
12 sans ambiguite (0,7 %), en trouve 75 a plusieurs endroits, et AUCUNE
des 92 commentees. Le gain ne payait ni la complexite ni le risque.

**Deux defauts d'affichage exposes par la bascule, corriges :**
1. Un bloc portant plus de 400 marques rend le texte nu — la page 419
   affichait 623 ancres et pas un surlignage, SANS un mot. Le code
   promettait de « le dire dans le bloc » et n'emettait qu'un
   `logger.warning`. Le bloc l'annonce desormais (5,01:1 clair /
   5,69:1 sombre, mesure au navigateur).
2. Les extractions detachees etaient atteignables mais INDISCERNABLES
   dans le panneau. Etiquette « ancre detachee — aucun passage, a
   replacer » (etalon maquette l. 1671-1682), sur les seules cartes
   concernees : 65/65 sur la page 419, 156/156 sur la 235.

**ALLEGEMENT DE LA BASE (decision du proprietaire, meme jour)** : la base
d'essai portait 98 titres en plusieurs exemplaires, un sujet jusqu'a 33
fois. `purger_les_notes_inutiles` retire les doublons en gardant un
exemplaire par titre. Trois gardes : jamais une note commentee, jamais
une source citee (les sources d'une synthese sont des NOTES — la
supprimer viderait la preuve en laissant l'article debout) ni une page
parent, jamais le dernier exemplaire d'un titre (ce qui garantit qu'il
reste des wikis et des syntheses). Un garde-fou refuse d'agir si la
selection emporte le moindre commentaire, et il se **reverifie dans la
transaction** — le controle du bilan a lieu avant, l'application est en
service. `AncrageExtraction.element` etant en PROTECT, les portions
partent d'abord, sinon la suppression echoue en bloc.

**La purge CONVERGE, et c'est un correctif de relecture** : les gardes se
calculent sur l'etat AVANT suppression, or un protecteur peut lui-meme
partir dans le passage (l'article citant emporte ses SourceLink, le
parent perd ses enfants). Un premier passage donne pour complet laissait
encore 15 pages et 1 179 extractions au lancement suivant — un bilan
incomplet, donc un bilan faux. La commande simule desormais les tours
successifs jusqu'au point fixe. Relancee apres coup : « 0 page a
supprimer ».

| Etat | Avant | Apres |
|---|---|---|
| Pages | 546 (542 ancien / 4 element) | 213 (2 ancien / 211 element) |
| **Commentaires humains** | **983** | **983** |
| Pages commentees | 37 | 37 |
| Extractions | 30 325 | 24 253 |
| Ancrages | 28 617 toutes « ancree » | 22 148 ancree / 1 311 detachee |
| Types de note | — | 204 notes / 7 syntheses / 2 wikis |

**Verifications** : 38 tests de reconversion, 14 de purge, 6 d'etiquette
detachee et d'avis de plafond, 2 du service de rendu. Suite complete :
1 621 tests. TROIS relectures adverses, la derniere portant sur le code
ET sur les chiffres de cette entree — elle a trouve la non-convergence
de la purge et trois chiffres faux, corriges ici. Deux passages au
navigateur reel avec contrastes CALCULES dans les deux themes.
Sauvegardes `tmp/sauvegardes/` (avant-reconversion,
apres-reconversion-avant-purge).

**Deux tests-mensonges PREEXISTANTS corriges au passage** (tous deux
rouges sur la branche avant cette session, sans rapport avec elle) :
`test_drawer_z_index_superieur_backdrop` cherchait les classes
`z-40`/`z-50`, disparues le 10 aout quand les z-index sont passes en
style INLINE (build Tailwind fige) ; `test_type_lien_choices` attendait
QUATRE types de lien alors qu'un cinquieme, `cite`, est arrive avec la
phase B de la synthese (migration core.0048, 9 aout).

**Consigne d'environnement** : les 15 e2e Playwright echouent en
`setUpClass` sans `PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/
ms-playwright` — le defaut pointe `/app/.cache`. Avec la variable, ils
passent.

| Fichier | Changement |
|---|---|
| `core/management/commands/basculer_vers_le_moteur_element.py` | selection par flag, deux chemins, pose du flag, verification des ancres neuves ET dormantes, ambiguite aller-retour, resilience par page, verrou, repli mort supprime |
| `core/management/commands/purger_les_notes_inutiles.py` | **nouveau** : allegement garde |
| `core/tests/test_reconversion_moteur.py` | **nouveau** : 38 tests |
| `core/tests/test_purge_notes.py` | **nouveau** : 12 tests |
| `front/services/rendu_elements.py` | `le_surlignage_depasse_le_plafond`, `idees_non_surlignees` par bloc |
| `front/templates/front/includes/_blocs_elements.html` | l'avis « trop d'idees pour les surligner » |
| `front/templates/front/includes/drawer_vue_liste.html` | l'etiquette « ancre detachee » |
| `front/views.py` | `est_detachee` par entite (drawer), seulement sur page ELEMENT |
| `front/tests/test_ancres_detachees_drawer.py` | **nouveau** : 4 tests |
| `front/static/front/css/maquette.css` | avis + etiquette (grammaire des etats : filet gauche) |
| `front/templates/front/base.html` | bump `maquette.css?v=23` |

### Migration
- **Migration necessaire / Migration required :** Non. Les deux commandes
  sont des operations de DONNEES, a lancer a la demande, `--a-blanc`
  d'abord.

---

## 2026-08-10 — U1 : les operations d'element ont leurs BOUTONS
## (mode structure de la lecture)

**Quoi / What :** les endpoints BR-E (corriger, scinder, fusionner,
masquer, demasquer) etaient prets et testes mais SANS un seul bouton.
La lecture d'une page ELEMENT gagne un MODE STRUCTURE :
- un bouton a bascule « Modifier la structure » (aria-pressed), rendu
  pour qui PEUT ECRIRE la note (filtre `est_modifiable_par`, meme
  regle que les endpoints — le bouton et le droit ne divergent pas) ;
- chaque bloc porte un groupe de boutons monospace (corriger, couper
  en deux, recoller avec le suivant, masquer), rendu par le serveur,
  INVISIBLE hors mode structure (la classe vit sur #zone-lecture et
  SURVIT au rechargement lectureReload) ;
- les elements MASQUES deviennent des placeholders demasquables
  (etiquette « Passage masqué », extrait, bouton) — visibles en mode
  structure, ABSENTS du DOM d'un simple lecteur ;
- corriger et couper ouvrent des formulaires rendus par le serveur
  dans un <dialog> natif (focus piege, Echap) ; couper se fait EN
  PLACANT LE CURSEUR dans le texte (lecture seule) puis « Couper ici ».
/ The element operations get their buttons: a structure mode on the
reading zone, server-rendered per-block button groups, un-hideable
placeholders for masked elements, native-dialog forms.

**Relecture adverse appliquee (3 HAUTE, 9 MOYENNE, 5 BASSE) — les
correctifs qui meritent d'etre retenus :**
1. HAUTE — `selectionStart` compte des unites UTF-16, le serveur coupe
   en points de code : un emoji avant le curseur decalait la coupe
   d'un cran, EN SILENCE. Conversion `Array.from(...)` a l'envoi.
2. HAUTE — le parseur HTML avale le premier retour a la ligne apres
   `<textarea>` : un texte commencant par \n perdait un caractere
   (offsets faux, correction « identique » qui reconcilie). Les deux
   formulaires prefixent un \n VOLONTAIRE.
3. HAUTE — la position de coupe n'a de sens que sur le texte AFFICHE :
   l'empreinte du texte voyage avec le formulaire et le serveur
   compare SOUS LE VERROU — texte change entre-temps = 409 FALC, pas
   une coupe posee sur un autre texte.
4. HAUTE — l'include des boutons injectait ~24 retours a la ligne
   VISIBLES dans les blocs `<pre>` (white-space:pre) : gabarit reecrit
   sans un blanc hors du span + `white-space:normal`.
5. Un pk mort (l'element vient d'etre scinde/fusionne par un autre)
   repond un toast FALC + rechargement — plus jamais la page 404
   brute dans un SweetAlert. `hx-disabled-elt` contre le double-clic.
6. Le toast d'erreur passait SOUS le voile du dialogue modal (top
   layer) : une zone role="alert" DANS le dialogue reprend le message.
7. Un script inline injecte par innerHTML ne s'execute JAMAIS : la
   resynchronisation aria-pressed + focus vit dans le gestionnaire
   lectureReload (hypostasia.js). Session expiree (403 nu DRF) =
   invite de connexion au lieu d'un echec silencieux.
8. Les boutons ne sortent plus DANS les h2/h3 (nom accessible du titre
   pollue) ; « recoller » n'est pas propose quand le suivant est
   masque ; messages de scission/fusion FALC dedies (jamais
   str(erreur) brut) ; droit evalue UNE fois par rendu (M7).
Consignes sans code : oracle 403/404 des endpoints element (coherent
avec BR-F, a trancher globalement), textarea readonly peu fiable sur
iOS, aria-live large de #zone-lecture, \r\n theorique (0 en base).

37 tests neufs/renforces (test_boutons_elements 16, test_views_element
+13, test_lecture_elements adapte). 93 verts sur le perimetre.

**Verification au navigateur reel (agent Opus, clair + sombre,
contrastes CALCULES)** : fonctionnel entierement conforme (bascule,
9 groupes de boutons, dialogues modaux avec focus piege et Echap,
erreur de scission DANS le dialogue, cycle masquer/demasquer reversible
prouve — etat de la base identique avant/apres, aria-pressed conserve a
travers lectureReload, anonyme sans un seul bouton, zero erreur JS).
Tous les contrastes au-dessus des seuils (boutons 5,4-6,2:1, contours
3,3-4,4:1, dialogue 14,5-16,8:1, focus 5,9-6,6:1). Cinq defauts, TROIS
CORRIGES dans la foulee : le <dialog> se collait en haut a gauche (le
preflight Tailwind `*{margin:0}` ecrase le centrage natif — `margin:
auto` retabli) ; en sombre le modal ne se detachait pas du voile
(1,08:1 — bordure passee a --filet-controle + ombre) ; la zone d'erreur
n'avait aucun style (filet gauche danger, grammaire des etats). Cibles
tactiles montees a 24 px (WCAG 2.5.8). CONSIGNES : le toast d'erreur
s'affiche brievement EN PLUS de la zone du dialogue (duplication de
4,5 s assumee) ; les boutons d'un titre s'affichent sous lui, entre
titre et paragraphe (l'aria-label leve l'ambiguite, cosmetique a
revoir).

| Fichier | Changement |
|---|---|
| `front/templates/front/includes/_actions_element.html` | **nouveau** : le groupe de boutons d'un bloc |
| `front/templates/front/includes/_blocs_elements.html` | placeholders masques, boutons, listes toutes-masquees |
| `front/templates/front/includes/_formulaire_element_correction.html` | **nouveau** : dialogue de correction |
| `front/templates/front/includes/_formulaire_element_scission.html` | **nouveau** : dialogue de scission (curseur) |
| `front/templates/front/includes/lecture_principale.html` | bascule mode structure, conteneur du dialogue |
| `hypostasis_extractor/views_element.py` | 2 actions GET formulaires, empreinte, messages FALC, pk morts |
| `hypostasis_extractor/serializers.py` | `empreinte_du_texte` sur la scission |
| `front/services/rendu_elements.py` | `fusion_possible`, `toutes_masquees` |
| `front/templatetags/corpus_permissions.py` | filtre `est_modifiable_par` |
| `front/static/front/js/hypostasia.js` | `basculerModeStructure`, resync lectureReload, 403 nu, anti double-Swal |
| `front/static/front/css/maquette.css` | section U1 (actions, placeholders, dialogue) |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — U4 : la capture web nourrit le moteur ELEMENT

**Quoi / What :** apres l'import fichier (BR-B), c'est au tour de la
capture web (extension navigateur, `POST /api/pages/`) de basculer sur
le moteur ELEMENT (decision D2, ordre 2). Meme patron :
- la source est `page.html_original` (le HTML capture), pas un fichier
  sur disque : Docling convertit un `DocumentStream` nomme `.html`
  (`convertir_du_html_avec_docling`, service `ingerer_une_capture_web`) ;
- la tache `ingerer_une_capture_web_avec_docling` partage la MEME file
  dediee `ingestion_docling` (concurrence 1) — une conversion a la
  fois sur l'hote 8 Go, fichier ou HTML confondus ;
- double ecriture de transition : le pipeline synchrone a rempli
  `html_readability`, l'affichage reste ANCIEN jusqu'a ce que les
  elements existent ; la page devient ELEMENT quand la tache aboutit ;
- repli honnete + etat U2 : un echec laisse une page ANCIEN lisible,
  la puce d'etat le dit et permet la relance ; broker en panne = la
  capture reste un succes, sans fausse promesse.
/ Web capture now feeds the ELEMENT engine, same pattern as file
import: background Docling conversion of the captured HTML on the
shared dedicated queue, honest fallback, U2 state surfaced.

7 tests (front/tests/test_capture_web_docling.py).

| Fichier | Changement |
|---|---|
| `hypostasis_extractor/services/ingestion_docling.py` | `convertir_du_html_avec_docling`, `ingerer_une_capture_web` |
| `hypostasis_extractor/tasks_element.py` | tache `ingerer_une_capture_web_avec_docling` (etats U2, repli) |
| `hypostasia/celery.py` | la tache web partage la file `ingestion_docling` |
| `core/views.py` | `PageViewSet.create` lance l'ingestion web + etat en_attente |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — U2 : l'ingestion Docling n'echoue plus en silence

**Quoi / What :** la dette n°1 du § 5 du cahier de branchement. Quand
la conversion Docling echouait, la page restait ANCIEN et lisible mais
RIEN ne le disait, et aucune relance n'existait — le journal Celery
faisait foi. Desormais :
- l'ETAT du decoupage vit sur la Page (`ingestion_etat` : en_attente /
  en_cours / reussie / echouee + `ingestion_detail` FALC), ecrit par la
  vue d'import (en_attente), par la tache (en_cours puis
  reussie/echouee, messages simples — le detail technique reste au
  journal), et par la relance ;
- la lecture montre une PUCE d'etat a qui peut ecrire : attente/cours
  avec sonde auto-rafraichie 5 s (patron F1/F2 : plafond d'essais ~5
  min, puis « Verifier a nouveau » — un worker mort devient un message,
  pas un poll infini) ; echec avec le detail et « Relancer le
  decoupage ». La reussite est SILENCIEUSE a l'ecran : la sonde repond
  vide + lectureReload, la lecture passe aux blocs toute seule ;
- la RELANCE manuelle est gardee : droit d'ecriture, pas pendant une
  ingestion active (409), pas sur une page qui a deja ses elements
  (409 — la re-ingestion qui preserve les ancres est un autre flux),
  type couvert par Docling seulement, broker en panne = 503 honnete.
/ Docling ingestion failures now show a status chip with a guarded
manual relaunch; success silently reloads the reading.

17 tests (front/tests/test_ingestion_ui.py). Migration core.0054
appliquee sur dev : 4 pages ELEMENT estampillees reussie ; les 537
pages ANCIEN aux elements dormants restent vierges (§ 9.2).

| Fichier | Changement |
|---|---|
| `core/models.py` | `EtatIngestion`, `Page.ingestion_etat/_detail` |
| `core/migrations/0054_page_ingestion_etat.py` | **nouvelle** : schema + estampillage ELEMENT |
| `hypostasis_extractor/tasks_element.py` | la tache ecrit les etats, messages FALC |
| `front/views.py` | etat en_attente a l'import ; actions `etat_ingestion` (sonde) et `relancer_ingestion` |
| `front/templates/front/includes/_etat_ingestion.html` | **nouveau** : la puce d'etat |
| `front/templates/front/includes/lecture_principale.html` | inclusion de la puce |
| `front/static/front/css/maquette.css` | styles de la puce (filet gauche danger en echec) |

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0054`
  (appliquee sur dev le 10 aout).

---

## 2026-08-10 — SECURITE : quatre lectures d'extractions ne verifiaient aucune permission

**Quoi / What :** decouvert en preparant U3 — quatre actions GET
d'`ExtractionViewSet` (front/views.py) ne controlaient RIEN :
- `/extractions/drawer_contenu/?page_id=N` donnait le TEXTE de toutes
  les extractions de n'importe quelle page, plus les noms des
  contributeurs, SANS ETRE CONNECTE — la meme famille que la faille de
  l'alignement corrigee le 9 aout ;
- `/extractions/carte_mobile/?entity_id=N` : une extraction et son
  activite ; `/extractions/dashboard/` : les stats de debat ;
  `/extractions/formulaire_promouvoir/` : le titre (et un oracle
  d'existence).
/ Four unauthenticated extraction READ endpoints leaked private
content — same family as the alignment hole fixed on Aug 9.

**Correctif** : la regle du produit (`_utilisateur_a_acces_page`,
SPEC-corpus § 5.2) + doctrine du 404 — l'interdit repond au MEME OCTET
que l'absent (`Http404` au message identique a get_object_or_404, DRF
le transmet). Une note d'un carnet public reste lisible : c'est la
regle, pas un mur de connexion.

**Preuve que les tests mordent** : garde du drawer neutralisee
temporairement -> 3 tests tombent (200 != 404) -> garde restauree.
9 tests (front/tests/test_extractions_permissions.py), dont l'octet
identique interdit/absent et la non-regression note publique.

**La FAMILLE n'etait pas eteinte (relecture adverse) — le reste
corrige dans la foulee.** Constat de fond : le projet n'a AUCUN
`DEFAULT_PERMISSION_CLASSES` — chaque ViewSet est `AllowAny` sauf garde
manuelle. Restaient :
- des LECTEURS ANONYMES rendant le texte integral d'une note privee :
  `/lire/<pk>/exporter/` et `previsualiser_analyse` (le prompt complet
  contient tout le texte — aussi grave que le drawer),
  `previsualiser_synthese`, `telecharger_source`, les formulaires
  audio, `panneau`, `manuelle` -> garde de lecture ;
  `/questionnaire/?page_id=` -> doctrine du 404 ;
- des IDOR authentifies : `modifier_titre`, `renommer_locuteur`,
  `editer_bloc`, `supprimer_bloc`, `creer_manuelle`, `ia` (analyse LLM
  payante) -> droit d'ecriture ; `supprimer_ia` (destructif) et
  `promouvoir_entrainement` (copie le texte dans un exemple GLOBAL) ->
  proprietaire ; `ajouter_commentaire`, `poser_question`, `repondre`
  -> acces en lecture (le debat est ouvert a qui peut LIRE) ;
  `DossierViewSet.partager` (le GET fuyait les emails des invitations,
  le POST modifiait les partages du dossier d'AUTRUI) -> owner du
  dossier. 19 tests (front/tests/test_permissions_famille.py), preuve
  de morsure faite (garde de l'export neutralisee -> le test tombe).

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — U3 : les cartes du panneau suivent le DOCUMENT, l'estimation compte les chunks REELS

**Quoi / What :** les deux restes cosmetiques § 5 du cahier de
branchement (consignes BR-C/BR-D) :
1. Le drawer des extractions d'une page ELEMENT etait trie par
   `start_char` — un offset DE CHUNK pour ce moteur : les cartes de
   chunks differents s'entrelacaient. Le tri « position » suit
   desormais l'ANCRE (ordre de l'element, debut dans l'element, via la
   premiere portion non detachee) ; les extractions sans portion
   ferment la marche au lieu de s'intercaler au hasard. L'ANCIEN
   moteur garde start_char (offset de page, fiable).
2. L'estimation du drawer d'analyse chunkait `text_readability` a
   l'arithmetique ; pour une page ELEMENT elle rejoue desormais le
   VRAI decoupage (`construire_les_chunks` sur les elements visibles) :
   nombre de chunks exact, overhead de prompt compte juste.
/ Anchor-ordered extraction cards and real chunk counts for ELEMENT
pages; OLD pages unchanged.

5 tests (front/tests/test_restes_moteur_element.py).
Fichiers : front/views.py (`_trier_les_entites_par_ancre`,
`drawer_contenu`, `previsualiser_analyse`).

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — Mesure D3 : la frontiere audio est TRANCHEE par les chiffres

**Quoi / What :** la question ouverte n°1 de SPEC-ancrage (frontiere
preferentielle du chunking audio) est fermee par une MESURE sur les 24
transcriptions diarisees reelles de la base dev (2 153 tours de
parole), pas par une opinion. Protocole rejouable :
`tmp/mesure_d3_audio.py` ; chiffres complets :
`PLAN/mesure-D3-frontiere-audio-2026-08-10.md` ; addendum date dans la
spec. / Open question #1 settled by measurement on 24 real diarised
transcriptions.

**Les trois decisions que les chiffres imposent :**
1. PAS de frontiere preferee au changement de locuteur : +12,6 %
   d'appels LLM pour 2 points de gain (chunks multi-locuteurs 59,3 %
   → 57,3 %) — un tour median fait 125 caracteres, l'attribution est
   portee par l'ancre M2M, pas par la frontiere.
2. L'element audio est le TOUR DE PAROLE, pas le segment ASR :
   elements=segments donnerait 605 coupes en plein tour (85 % des
   frontieres internes), elements=tours zero.
3. Un tour au-dela du budget (6,5 % des tours, max observe 34 715
   caracteres — un podcast) est scinde A L'INGESTION a la frontiere de
   segment la plus proche du budget, sinon la regle « jamais couper un
   element » enverrait des chunks de 35 000 caracteres au LLM.

Aucun code de production touche : c'est le prealable exige avant la
bascule audio (decision D2, ordre 3).

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — Recette connectee : les sept dernieres frictions
## (F4 a F10) — l'ecran en savait plus qu'il n'en disait

**Quoi / What :** les sept defauts d'experience restants de la recette
du carnet 1. Un fil les relie : **l'ecran detenait l'information et ne
la donnait pas**.

**F4 — lire un article ne changeait pas l'URL.** Pas de `hx-push-url`
sur les liens des listes : on lisait un wiki a l'adresse du carnet, F5
ramenait a la liste des notes, et le lien n'etait pas partageable
depuis l'endroit meme ou on lisait.

**F5 — le diff parlait en langage machine** au moment precis ou l'on
demande d'accepter ou de refuser : `append_to_section` s'affichait tel
quel, et `[[ext:35284]]` exposait une syntaxe interne masquee PARTOUT
ailleurs. Deux filtres de gabarit traduisent desormais a l'affichage,
sans toucher aux donnees. Un troisieme detecte une operation dont le
contenu n'est QUE des marqueurs et le DIT : le defaut B2 a ete corrige
cote back, mais un diff qu'on accepte les yeux fermes est un diff
inutile — l'ecran doit rester capable de le signaler.

**F6 — le verdict se lisait comme une separation.** Un filet bas
pleine largeur sous le paragraphe : en recette, il a d'abord ete pris
pour une bordure decorative. Dans ce design system un etat se porte a
GAUCHE — c'est deja le cas du guide de redaction, des operations de
diff, des messages d'etat. Le verdict rejoint cette grammaire, et
chaque paragraphe porte un `title` qui NOMME son etat : une couleur ne
se lit pas toute seule.

**F7 — la legende promettait des couleurs absentes.** Elle annoncait
les six etats, « non source » compris, avant meme la premiere
verification. Elle n'annonce plus que ceux que le texte porte
reellement, et s'ouvre en disant ce que la couleur qualifie — le
paragraphe, par son verdict le PLUS FAIBLE.

**F8 — trois actions, une seule ligne.** Produire un wiki, proposer une
mise a jour et verifier des citations donnaient trois entrees
identiques dans « Mes taches », parce que tout ce qui n'etait pas une
synthese tombait dans « analyse ». Un `libelle_de_tache` les distingue
— la logique (`type_tache`, marquage lu, cible du lien) n'a pas bouge.
Les accents manquants de ce panneau, seul endroit de l'interface dans
ce cas, sont retablis.

**F9 — le titre de l'onglet** disait « Bibliotheque » partout. C'est
pourtant souvent le SEUL nom qu'une page recoit : dans une barre de dix
onglets, dans un signet, dans un historique.

**F10 — le moteur n'etait pas nommable.** On ne le choisit pas a la
creation ; a defaut, l'ecran le NOMME et dit ou il se change.

Quatre ecarts de contraste trouves par la verification et corriges,
dont un de ce lot : le filet « pas encore verifie » tombait a
**2,94:1**, six centiemes sous le seuil, a cause d'un alpha de 70 %.
Les trois autres etaient preexistants — filet du guide de redaction
(2,12:1), compteur du bouton taches (3,30:1), taille de la pastille de
renvoi.

**Une regression introduite puis levee, qui merite d'etre ecrite.** En
remappant le fond du compteur de taches sur `--succes`, on a **re-commis
l'erreur que le lot T10 avait pourtant corrigee ailleurs** : un fond
semantique PLEIN ne peut pas porter un `white` fige. En theme sombre
ces tokens sont des pastels CLAIRS — ils y servent de texte sur fond
sombre — et le `color: white !important` de hypostasia.css:1920 y
tombait a **1,52:1**, pire qu'avant le correctif. Le token qui suit le
theme est `--papier`. Les quatre etats du badge (y compris l'etat
neutre, dernier `white` fige du composant) sont desormais entre 5,3 et
11,9:1 dans les deux themes. Regle a appliquer sans reflechir : **quand
on remappe un fond, on verifie ce que le TEXTE devient dans les deux
themes**, et on cherche un `color` en dur dans l'ancienne feuille.

14 tests neufs, 659 tests unitaires et 104 e2e verts.

| Fichier | Changement |
|---|---|
| `front/templatetags/lisibilite_diff.py` | **nouveau** : 3 filtres d'affichage pour le diff |
| `front/templates/front/corpus/partials/diff_operations.html` | operations nommees, marqueurs lisibles, alerte « sans redaction » |
| `front/templates/front/corpus/article.html` | legende conditionnee aux etats presents |
| `front/views_synthese.py` | `etats_de_verification_presents`, `title` des verdicts, moteur annonce |
| `front/views_taches.py` | `libelle_de_tache` : les actions se distinguent |
| `front/templates/front/includes/taches_dropdown.html` | libelles distincts, accents retablis |
| `front/templates/front/base.html` | `<title>` par ecran |
| `front/templates/front/corpus/liste_{wikis,syntheses}.html` | `hx-push-url`, moteur annonce |
| `front/templates/front/corpus/_style_maquette.html` | verdict a gauche, pastille de renvoi, filets ≥ 3:1 |
| `front/tests/test_frictions_recette_f4_f10.py` | **nouveau** : 14 tests |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — Recette connectee : les trois frictions FRONT sont
## corrigees (F1, F2, F3)

**Quoi / What :** les trois defauts d'experience releves par la recette
connectee du carnet 1 (PLAN/recette-connectee-2026-08-10.md). Ils
avaient un point commun : **le produit travaillait sans le dire**.

**F1 — une production se lancait sans le moindre retour.** « Creer le
wiki » et « Produire la synthese » renvoyaient LA LISTE. Le nouvel
objet y apparaissait comme s'il etait fini — « tour 1 · 0 sources · 465
ecartees » — alors que la tache venait de partir. Rien ne disait
d'attendre, rien ne se rafraichissait : en recette, la conclusion
naturelle etait « le wiki est vide » et le reflexe, recliquer.

**F2 — la verification ne disait jamais qu'elle etait finie.** Son
message « Verification lancee… » restait affiche POUR TOUJOURS : le
partial etait rendu sans `hx_get`, donc sans interrogation. Les
verdicts n'apparaissaient qu'apres un rechargement manuel que rien ne
suggerait.

**F3 — appliquer un diff depuis l'URL d'un article ne faisait RIEN.**
Le formulaire visait `#corpus-panneau-onglet`, qui n'existe que dans
l'onglet du carnet : un utilisateur arrive par lien partage ou par F5
cliquait « Appliquer les operations cochees » sans aucun effet. La
cible est desormais l'article lui-meme (`closest
[data-testid='synthese-article']`, remplace en `outerHTML`), present
dans les DEUX contextes — et la reponse EST l'article.

**Un seul point d'entree pour F1 et F2** : `GET /wikis/{pk}/etat/` et
`GET /syntheses/{page_pk}/etat/`, avec `?job_id=N`. Tant que le job
tourne, il se renvoie lui-meme (`hx-trigger="load delay:3s"`) ; quand
il finit, il rend ce que l'utilisateur attend — la LISTE apres une
production (il est dans l'onglet, il voit sa ligne avec ses vrais
compteurs), l'ARTICLE apres une verification (il y est deja, ce sont
les verdicts qu'il attend).

**Trois garde-fous**, parce qu'un ecran qui interroge en boucle est une
friction de plus : un compteur d'essais transforme un worker mort en
MESSAGE au bout de ~5 minutes au lieu d'interroger indefiniment ; un
job en erreur le dit et rassure (« Rien n'a ete modifie ») ; et un job
qui appartient a une AUTRE page n'est pas suivi (404) — le suivi
respecte l'acces a l'article comme le reste du produit.

10 tests neufs verrouillent le tout, y compris ce qu'on ne peut pas
exercer au navigateur sans declencher un appel LLM facture : job en
attente, plafond d'essais, job en erreur, job d'une autre page. Verifie
aussi au navigateur (endpoint, cablage, non-regression, aucune erreur
JS), sans lancer une seule production.

591 tests unitaires + 104 e2e verts.

| Fichier | Changement |
|---|---|
| `front/views_synthese.py` | `_etat_de_la_tache()`, action `etat` sur les deux ViewSets, retours de creation et de verification |
| `front/templates/front/corpus/partials/diff_operations.html` | la cible d'application existe enfin dans les deux contextes |
| `front/tests/test_retour_de_production.py` | **nouveau** : 10 tests (F1, F2, F3, garde-fous, acces) |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-10 — Recette connectee : les trois defauts BACK sont corriges (B1, B2, B3)

**Contexte / Context :** la recette connectee du carnet 1 (session
Opus, PLAN/recette-connectee-2026-08-10.md) a revele 4 defauts back
dans la couche synthese livree la veille. Trois sont corriges en TDD :

**B1 — les compteurs du wiki se contredisaient** (23 renvois annonces,
25 affiches) : l'indexation absorbait les doublons d'un marqueur dans
un meme paragraphe (un lien par couple, § 4.4) mais le TEXTE gardait
toutes les occurrences. Le doublon sort desormais du texte aussi
(`indexer_les_citations`, nouveau compteur `doublons_absorbes` dans le
bilan) : tous les compteurs de l'ecran coincident. Verification faite
au passage : le clic, lui, pointait deja le BON lien (mapping par
extraction + position, zero orphelin sur le wiki 3 reel) — le defaut
etait le comptage, pas l'attribution.

**B2 — les operations de mise a jour au contenu reduit a un marqueur
nu** (`"contenu": "[[ext:35284]]"` → paragraphes orphelins [4]) : une
operation dont le contenu, marqueurs retires, est vide est REJETEE
avec motif FALC (`section_ops._controler_les_sources`) — le modele
doit proposer un passage redige ET source.

**B3 — la troncature du volet des ecartees etait muette** (« 458 »
au resume, 200 lignes affichees) : le volet affiche desormais le TOTAL
et annonce « les 200 premieres sont affichees ».

**B4 consigne, pas code** : la pauvrete du sourçage (2 extractions
citees sur 465) est un probleme de PROMPT — B2 forcera deja le modele
a rediger ; les `marqueurs_retires` sont signales dans raw_result
depuis la phase C mais n'ont pas de surface UI. A retravailler avec
les consignes de production.

Tests : `core.tests.test_synthese_citations` (3 nouveaux, 38 verts),
`core.tests.test_section_ops` (3 nouveaux, 27 verts),
`front.tests.test_synthese_phase_h` (1 nouveau, 17 verts) +
non-regression synthese (52 + 25 verts).
Fichiers : `core/services/synthese.py`, `core/services/section_ops.py`,
`front/views_synthese.py`, `partials/ecartees.html`.

## 2026-08-10 — Branchement du moteur d'ancrage, BR-F : fixtures representatives et parcours e2e — LE BRANCHEMENT BR-A→F EST COMPLET

**Quoi / What :** fixtures § 9.4 versionnees
(`hypostasis_extractor/tests/fixtures/` : pad markdown structure,
texte brut temoin du repli) + tests de conversion REELLE par Docling
(pad → title/section_header/list_item/chemins de section ; docx avec
TABLEAU fabrique par python-docx → element `table` au contenu
ancrable). Opt-in : `TESTS_DOCLING=1` + `--tag=docling` — jamais dans
une suite ordinaire (8 Go). Et le parcours E2E complet au navigateur
(`front/tests/e2e/test_23_moteur_element.py`) : import d'un `.md` par
le bouton reel → ingestion eager → la note rouverte se lit par BLOCS
(h2/h3/p/ul-li, `data-testid="blocs-elements"`), 8,6 s.
/ Representative fixtures + real-Docling conversion tests (opt-in) +
the full browser journey.

**Decouverte consignee (le role meme des fixtures)** : le backend
markdown de Docling traite chaque LIGNE source comme un element — un
paragraphe a retours a la ligne durs se fragmente (« l'ete. » devient
un element), et une puce continuee sur deux lignes perd son label
`list_item`. Reel documente dans le test, pas corrige : les pads reels
s'ecrivent sans retour dur ; a reevaluer si la recette montre une gene.

**Relecture adverse BR-E appliquee (9 defauts, 5 corriges + tests)** :
1. HAUTE — deux scissions simultanees sur la MEME page se percutaient
   au commit (renumerotation page-entiere + contrainte d'ordre
   DEFERRED → IntegrityError → 500) : les operations de STRUCTURE
   (scinder, fusionner) posent desormais le verrou de PAGE avant tout ;
   corriger/masquer restent au verrou de ligne.
2. La justification > 500 caracteres etait AVALEE en silence
   (is_valid sans controle) : refusee en 400 desormais, partout.
3. La justification de scinder/fusionner passait en brut (un dict JSON
   → 500 psycopg) : serializers partout, convention respectee.
4. Les toasts 409 montraient les messages internes des exceptions
   (pk, « job(s) », moitie anglaise) : messages FALC dedies — celui de
   la synthese NOMME toujours la synthese bloquante (§ 5.3).
5. Corriger sans changement polluait PageEdit : no-op propre + toast
   « Aucun changement » ; le journal porte l'identifiant STABLE (l'ordre
   est renumerote par les scissions).
Consignes sans code (BASSE, § 5 du cahier) : verrou avant controle de
droit (oracle d'existence conforme au reste du depot), messages de
course fusion/scission perfectibles, error_messages morts des
serializers.

Tests : 18 verts sur test_views_element (5 nouveaux TDD RED→GREEN),
fixtures 4 + 2 docling reels, e2e 1.

**Le § 9 de la spec est tenu de bout en bout** : import → ingestion
Docling (file dediee, bornee) → flag ELEMENT → analyse par elements
(LLM reel verifie) → lecture par blocs marques par portion (verifiee
au navigateur, clair/sombre) → operations d'element sous verrou et
gardes. L'existant ANCIEN n'a pas bouge (543 test_phases verts).
Restent, hors perimetre du branchement : BR-G (visualiseur PDF,
curseur audio — a cadrer separement), la bascule de la capture web et
de l'audio (D2), la reconversion explicite § 9.5.

## 2026-08-09 — Branchement du moteur d'ancrage, BR-E : les operations sur un element ont leurs endpoints

**Quoi / What :** nouveau `ElementViewSet`
(`hypostasis_extractor/views_element.py`, routes `/elements/<pk>/...`) :
`corriger` (texte + reconciliation des portions + journal PageEdit),
`scinder`, `fusionner_avec_le_suivant`, `masquer`, `demasquer` — un
serializer par action (convention du depot). Les GARDES des services
(analyse en cours, synthese figee qui cite) remontent en **409 avec
leur message FALC** ; les entrees invalides en 400 ; un tiers sans
droit d'ecriture en 403 (meme regle que la lecture :
`_utilisateur_peut_ecrire_page`, import paresseux anti-cycle).
/ Element operation endpoints; service guards surface as 409 FALC.

**Le verrou § 7 est POSE** (defaut de concurrence consigne le 8 aout) :
chaque action ouvre une transaction et `select_for_update()` la ou les
lignes ElementDocument AVANT d'appeler le service — la fusion
verrouille les DEUX voisins. Reponses : 200 + HX-Trigger
{showToast, lectureReload} — le front recharge la lecture, qui re-rend
les blocs BR-D. Pas d'UI dediee encore (boutons a venir avec BR-F/G).

**Verification visuelle BR-D (agent maquette, Chromium reel)** — 2
defauts HAUTE decouverts et corriges dans la foulee : le passage
`span`→`mark` reveillait les DEFAUTS NAVIGATEUR de `<mark>` — texte
MarkText noir dur (1,28:1 en mode sombre) et fond jaune fluo pour tout
statut sans regle CSS, dont `non_pertinent` (4 182 extractions en
base). Correctif : reset `mark.hl-extraction` dans maquette.css,
specificite (0,1,1) calculee pour perdre contre les fonds par statut.
Conformes par ailleurs : structure des blocs, typographie identique a
la zone de lecture, 4 marques sur les bonnes portions a travers
h2/p/li/h3, zero regression sur l'ancien rendu (verifie sur 2 pages
temoins, clair et sombre), zero erreur console. Ecart de parti pris
consigne : surlignage permanent (choix T7) la ou l'etalon revele au
survol — a trancher plus tard.

Tests : `hypostasis_extractor.tests.test_views_element` (14) + verrou
CSS dans test_lecture_elements — TDD RED→GREEN, 40 verts sur le
perimetre BR. Fichiers : `hypostasis_extractor/views_element.py`
(nouveau), `hypostasis_extractor/serializers.py` (3 serializers),
`front/urls.py`, `front/static/front/css/maquette.css`.

Suite : BR-F (fixtures representatives + parcours e2e ELEMENT).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-D : la lecture rend les elements

**Quoi / What :** une page ELEMENT est desormais AFFICHEE depuis ses
ElementDocument — titres, paragraphes, listes regroupees, chaque
portion d'extraction marquee `mark.portion.hl-extraction` sur SON
passage exact (`front/services/rendu_elements.py`, ecrit en phase G,
enfin branche). Une page ANCIEN, ou une page ELEMENT a zero element
(ingestion echouee), retombe sur `html_annote`/`html_readability`
comme avant — jamais de page blanche.
/ ELEMENT pages now render from their elements with per-portion marks;
OLD pages are untouched.

**Le branchement passe par un tag de template**
(`front/templatetags/rendu_moteur.py`), pas par les contextes de vue :
lecture_principale.html est rendu depuis PLUS DE SIX endroits, et
injecter `blocs_de_lecture` dans chacun garantissait l'oubli — le meme
piege que corpus_permissions avait resolu pour est_proprietaire. Les
elements MASQUES ne sont pas rendus (leur gestion arrive avec BR-E).

**Relecture BR-C appliquee dans la foulee (3 correctifs testes)** :
1. HAUTE — battement de coeur par chunk dans l'analyse ELEMENT
   (`analyse_par_element.py`) + le juge de blocage distingue un job
   PENDING en file (tolere 90 min, plafond de la garde d'edition) d'un
   PROCESSING fige (5 min sans battement = mort) : fini les faux
   « Timeout » qui relancaient des analyses en double.
2. MOYENNE — `analyser_page_task` revalide le moteur A L'EXECUTION et
   delegue au moteur ELEMENT si la page a bascule entre le clic et
   l'execution (course avec l'ingestion Docling) : jamais
   d'extractions a offsets sans portions sur une page ELEMENT.
3. Consignes au § 5 du cahier (pas de code) : ordre des cartes du
   panneau encore par start_char (entrelace pour ELEMENT — cosmetique),
   drawer d'estimation chunke encore a l'ancienne, anti-doublon sans
   verrou sur double-clic rapide (preexistant, attenue par la
   transition atomique de la tache ELEMENT).

**Collisions de tests entre sessions resolues** :
`hypostasia/settings_test_fable.py` donne a cette session sa base de
test dediee (`test_hypostasia_fable`) — les runs paralleles des deux
sessions ne se detruisent plus (« database test_hypostasia does not
exist », deadlocks : c'etait ca).

Tests : `front.tests.test_lecture_elements` (5) +
`front.tests.test_analyse_routage` (9 au total) + battement de coeur
(`test_analyse_par_element.BattementDeCoeurTest`) — TDD RED→GREEN ;
`front.tests.test_phases` : 543 verts (non-regression totale).
Fichiers : `front/templatetags/rendu_moteur.py` (nouveau),
`front/templates/front/includes/_blocs_elements.html` (nouveau),
`lecture_principale.html`, `front/views.py`, `front/tasks.py`,
`hypostasis_extractor/services/analyse_par_element.py`,
`hypostasia/settings_test_fable.py` (nouveau).

Suite : BR-E (ElementViewSet : corriger, scinder, fusionner, masquer —
avec le verrou ElementDocument).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-C : l'analyse route selon le moteur

**Quoi / What :** le bouton « analyser » lance desormais
`analyser_une_page_avec_le_moteur_element` (ancres par PORTIONS) quand
`page.moteur == element`, et `analyser_page_task` (offsets) sinon.
Meme ExtractionJob, meme toast : le moteur est un detail
d'implementation pour la personne qui lit.
/ The "analyse" button now routes by the page's engine flag.

**M6 tranché — coexistence des jobs** : la relance ne purge pas les
jobs precedents (meme semantique que l'ancien moteur) ; la promesse
§ 4.2 de SPEC-synthese est tenue par les gardes deja en place
(`nettoyer_ia` refuse AVANT purge et AVANT l'appel LLM ; le chemin
ELEMENT porte sa garde interne). Ecarts § 4.2 assumes par addendum
date (pas de compteur de tokens, boucle sequentielle — une vertu sur
8 Go —, `suppress_parse_errors`).

**Verifie en reel** : job 938 sur la page 674 (ELEMENT) —
`raw_result.moteur='element'`, 1 chunk, LLM reel, 2,9 s, zero erreur.
La fenetre « analyse ANCIEN sur page ELEMENT » (relecture BR-B, defaut
n°4) s'est refermee avant toute analyse reelle.

Tests : `front.tests.test_analyse_routage` (2, TDD RED→GREEN).
Fichiers : `front/views.py` (action `analyser`).

Suite : BR-D (affichage par elements dans lecture_principale).

## 2026-08-09 — Branchement du moteur d'ancrage, BR-B : l'import de fichier nourrit le moteur ELEMENT

**Quoi / What :** quand un fichier importe est d'un type que Docling
sait convertir (`.pdf`, `.docx`, `.md`, `.pptx`, `.xlsx`), la vue
d'import lance desormais `ingerer_un_fichier_avec_docling` en
arriere-plan, EN PLUS du pipeline synchrone existant. C'est la premiere
vraie bascule de flux du § 9 : les nouvelles pages couvertes deviennent
ELEMENT (le flag est pose par la tache, mecanique BR-A).
/ Covered file imports now ALSO launch Docling element ingestion in the
background — the first real flow switch of § 9.

**Decision de transition (double ecriture)** : le pipeline synchrone
continue de remplir `html_readability` — l'AFFICHAGE reste celui de
l'ancien moteur jusqu'a BR-D (`rendu_elements` n'a pas encore
d'appelant). Aucune regression visible ; les elements s'accumulent en
attendant leur ecran. Le `.txt` (sans structure) et le `.json` de
transcription restent entierement sur leurs pipelines d'origine, et le
toast le dit honnetement : « Fichier importé — découpage en éléments
lancé » seulement quand c'est vrai.

**Verifie en reel** : import d'un `.md` par la vraie vue, ingestion par
le vrai worker Celery (meme conteneur, chemin `source_file.path`
partage) — page 674, 4 elements, `moteur=element`, premiere page
ELEMENT nee du flux reel en dev. Pas de course delay/commit
(autocommit, pas d'ATOMIC_REQUESTS) ; les e2e (eager) n'uploadent que
du `.txt`, donc aucun Docling synchrone dans les suites.

**Relecture adverse (7 défauts, tous traités le soir même)** :
1. HAUTE — aucun garde-fou de ressources : conversion bornée
   (`max_num_pages=200`, `max_file_size=50 Mo` — un `.docx` est un zip,
   la limite d'upload porte sur la taille compressée) et **file Celery
   dédiée `ingestion_docling` à concurrence 1** (task_routes +
   programme supervisord `celery_worker_docling` ; redémarrage du
   conteneur requis pour l'activer) — jamais deux Docling en même temps
   sur l'hôte 8 Go partagé avec la prod.
2. Broker en panne : `.delay` encadré, l'import reste un succès (page
   ANCIEN lisible), toast sans fausse promesse.
3. Échec d'ingestion silencieux : assumé et consigné (pas de surface UI
   avant BR-D/E — fiche A TESTER + § 5 du cahier).
4. Fenêtre BR-B→BR-D (analyse ANCIEN payée sur page ELEMENT →
   extractions sans portions) : dette écrite au § 5 du cahier, à
   trancher à BR-C.
5. La vue ne passe plus que `page.pk` : la tâche résout le chemin
   depuis `source_file` (découplage du stockage).
6. Tests renforcés : `.docx` réel (binaire), conversion en échec →
   Docling jamais lancé, media de test nettoyé.
7. Toast double : timer paramétrable (`showToast.timer`), 4,5 s pour ce
   message (public FALC).

Tests : `front.tests.test_import_docling` (8) +
`hypostasis_extractor.tests.test_tasks_element` (3 nouveaux) +
`hypostasis_extractor.tests.test_ingestion_docling` (3 nouveaux), TDD
RED→GREEN — 46 verts au total sur le périmètre.
Fichiers : `hypostasis_extractor/services/ingestion_docling.py`,
`hypostasis_extractor/tasks_element.py`, `front/views.py`,
`hypostasia/celery.py`, `supervisord.conf`,
`front/static/front/js/hypostasia.js`.

Suite : BR-C (routage de l'analyse pour les pages ELEMENT).

## 2026-08-09 — SECURITE : l'alignement ne verifiait aucune permission

**Quoi / What :** `/alignement/tableau/` et
`/alignement/export_markdown/` ne controlaient RIEN.
`?dossier_id=N` alignait n'importe quel carnet, `?page_ids=1,2`
n'importe quelles notes — par leur simple identifiant, sans etre
connecte. Le tableau produit affiche le TEXTE des extractions et leurs
resumes, et l'export en fait un fichier telechargeable : c'etait une
fuite directe et complete du contenu prive d'autrui. Repere en portant
l'onglet Alignement du carnet, corrige ici.

**Le correctif** applique la regle deja en vigueur partout ailleurs
(`_utilisateur_a_acces_dossier`, `_utilisateur_a_acces_page` : on
accede a une note si on accede a AU MOINS UN carnet qui la contient),
aux DEUX vecteurs — le mode `page_ids` etait le plus grave, deux
identifiants suffisaient.

**Le filtrage est SILENCIEUX**, et c'est un choix : une page interdite
est retiree exactement comme une page inexistante, un carnet interdit
repond comme un carnet absent, **au meme octet**. Repondre « acces
refuse » aurait confirme l'existence de la note — c'est la doctrine du
404 plutot que du 403 deja retenue pour les bases privees (phase H
corpus). Deux tests le verifient en comparant les reponses.

**Le superuser garde son acces en lecture** : la regle du produit lui
en accorde un, et un alignement plus strict que le reste serait
incoherent.

**Trois classes de tests existantes passaient GRACE au trou**
(`Phase18EndpointTableauTest`, `Phase18EndpointExportMarkdownTest`,
`Phase18bDossierAlignementEndpointTest`) : elles creent des pages et un
dossier sans owner et appelaient l'endpoint en ANONYME. Ces objets
« legacy » sont lisibles par tout utilisateur AUTHENTIFIE — c'est deja
ce que fait `/lire/` pour eux. Les tests se connectent desormais et
redeviennent ce qu'ils sont : des tests du RENDU du tableau.

**Preuve que les tests mordent** : les gardes ont ete temporairement
neutralisees, 7 des 11 tests de securite echouent ; restaurees, les 11
passent. Verifie aussi en conditions reelles sur le dev — anonyme, un
carnet prive repond 404, ses notes par `page_ids` 400, l'export 404,
aucune occurrence de leur contenu ; le carnet public repond 200.

616 tests unitaires et 104 e2e verts.

| Fichier | Changement |
|---|---|
| `front/views_alignement.py` | controle d'acces sur les deux vecteurs, filtrage silencieux |
| `front/tests/test_alignement_permissions.py` | **nouveau** : 11 tests (fuite, oracle, export, superuser, non-regression) |
| `front/tests/test_phases.py` | 3 classes Phase18 connectees — elles passaient grace au trou |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Architecture de page : le fil d'Ariane, les actions du
## carnet, l'alignement, la provenance des notes

**Quoi / What :** quatre ajouts de structure, front pur, sur le design
de l'etalon (`tmp/maquettes/corpus.html`).

**1. LE FIL D'ARIANE « Base > Carnet > Note »**, colle sous la barre,
sur les ecrans carnet, article et note. Il porte la BASCULE DE CARNET.
Sa raison d'etre est ecrite dans l'etalon : **le N-N a tue l'arbre**.
Une note rangee dans deux carnets n'a pas de parent unique, donc pas de
place dans une arborescence. Le fil montre UN chemin parmi ceux qui
existent, et son chevron permet d'en changer — sur un carnet il liste
les carnets accessibles, sur une note **les carnets qui contiennent
cette note** (basculer = relire la meme note sous un autre classement,
via `?carnet=N`).
Trois decisions de securite : la regle d'acces est EXTRAITE dans
`carnets_visibles_par()` pour n'exister qu'une fois (le fil et la liste
des carnets la partagent) ; un `?carnet=N` n'est honore que si le
carnet contient vraiment la note et que le visiteur y a acces — un
parametre d'URL ne sert jamais d'oracle ; une base non publique
n'apparait pas dans le fil d'un visiteur qui n'y a pas acces, le nom
seul etant deja une fuite.

**2. « Nouveau wiki » et « Nouvelle synthese » dans l'en-tete du
carnet.** Ils n'ouvrent AUCUN chemin nouveau : ils activent l'onglet qui
porte deja le formulaire, attendent son arrivee en HTMX
(MutationObserver plutot qu'un delai devine), y font defiler et posent
le focus.

**3. UN ONGLET ALIGNEMENT** qui rouvre le flux EXISTANT
(`window.alignement.ouvrirDossier`, soit
`/alignement/tableau/?dossier_id=N` — l'endpoint prenait deja le
carnet). Il ne prend PAS la selection d'onglet : le gabarit du tableau
est un fragment de MODALE, l'injecter dans un panneau aurait demande de
le reecrire, donc du back.

**4. SOUS-NOTES ENRICHIES** : marque de source (audio / web / fichier),
nom de fichier tronque, extractions, « dans N carnets ». Tout vient du
`select_related('page')` et des annotations DEJA calculees : aucune
requete de plus.

Verifie au navigateur. Six ecarts trouves et corriges, dont trois qui
valaient le detour : le fil **ne collait pas** au haut de la zone — un
element sticky se cale sur la boite de CONTENU, et le `p-8` du
conteneur le figeait 32px plus bas en laissant defiler du texte dans la
bande au-dessus ; et l'ecouteur « clic dehors » du menu, pose a chaque
injection du fragment, **s'empilait a chaque navigation HTMX** sur des
menus depuis longtemps detaches. Le troisieme est un piege de
diagnostic : le debordement horizontal a 390px semblait venir des
tableaux de transcription ; ils ont bien ete corriges, mais le vrai
coupable etait le formulaire « + Ajouter a… » du bloc carnets, un flex
sans wrap dont le `<select>` porte le nom de TOUS les carnets
disponibles. Sans la chaine d'ancetres de l'element le plus a droite,
on aurait cru le probleme regle.

### Deux constats a remonter (hors perimetre front)
- **`/alignement/tableau/?dossier_id=N` ne verifie AUCUNE permission**
  (`front/views_alignement.py`, `_recuperer_pages_depuis_parametres`) :
  `Dossier.objects.get(pk=...)` sans controle d'acces. N'importe qui
  peut aligner les notes d'un carnet prive. Le lot n'aggrave rien —
  l'onglet n'apparait que sur un carnet deja ouvert — mais la faille
  existe et merite un correctif.
- **La duree et les locuteurs d'un audio ne sont pas sur `Page`** : ils
  derivent de la transcription. Impossible de les afficher dans les
  sous-notes sans requete lourde, donc absents (demande consignee).

623 tests verts.

| Fichier | Changement |
|---|---|
| `front/views_corpus.py` | `carnets_visibles_par()` extrait, `contexte_du_fil_d_ariane()` |
| `front/views.py` | fil d'Ariane sur la lecture ; l'acces direct reutilise le contexte partage |
| `front/views_synthese.py` | fil d'Ariane sur l'article |
| `front/templates/front/corpus/_fil_ariane.html` | **nouveau** : le fil et sa bascule |
| `front/templates/front/corpus/carnet_detail.html` | 2 boutons d'en-tete, onglet Alignement |
| `front/templates/front/corpus/partials/notes_du_carnet.html` | sous-notes enrichies |
| `front/static/front/css/maquette.css` | `.fil-ariane`, `.menu-bascule`, collant reel, tableaux larges, formulaires enroulables |
| `hypostasia/settings_test_opus.py` | **nouveau** : base de test dediee a cette session (fin des collisions entre les deux sessions paralleles) |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Les toasts parlent enfin aux lecteurs d'ecran

**Quoi / What :** l'application confirme ses actions par des toasts
SweetAlert (« Note supprimee », « Analyse lancee »…). SweetAlert
annonce ses MODALES — role=dialog, focus deplace — mais **pas ses
toasts** : ni modaux ni focalises, ils apparaissaient, vivaient trois
secondes et disparaissaient en silence. Une personne qui n'a pas les
yeux sur l'ecran ne savait jamais si son action avait abouti. L'etalon
de design n'a pas d'aria-live non plus : c'est un point ou la bascule
devait faire MIEUX que lui.

**Deux decisions de conception.**
1. On n'annonce pas depuis le toast : une region live creee en meme
   temps que son contenu n'est pas annoncee de facon fiable. On ecrit
   dans une region PERSISTANTE (`#zone-annonces`, dans base.html),
   presente des le rendu, que la technologie d'assistance surveille
   depuis le debut.
2. On n'a pas touche aux sept fichiers qui appellent `Swal.fire`
   (hypostasia, keyboard, arbre_overlay, arbre_context_menu,
   drawer_vue_liste, dashboard_consensus, alignement) : `annonces.js`
   ENVELOPPE `Swal.fire` une seule fois. Un seul point d'entree couvre
   l'existant et le futur — le prochain toast ecrit ailleurs sera
   annonce sans que personne y pense.

Les modales restent volontairement exclues : les annoncer en plus
ferait entendre le message deux fois. Le vidage puis la reecriture
differee de 50 ms sont necessaires pour que deux messages IDENTIQUES a
la suite soient bien re-annonces.

Verifie au navigateur, y compris sur un vrai toast du produit
(« Copier en Markdown ») : region presente avant tout toast, invisible
mais non masquee (1x1px hors ecran, ni display:none ni aria-hidden),
`title` + `text` concatenes, `html:` reduit au texte, modale sans
annonce, aucune erreur JS. 543 tests verts, dont 3 neufs qui figent le
contrat — y compris l'ORDRE DE CHARGEMENT : charge avant SweetAlert,
le script renoncerait silencieusement.

| Fichier | Changement |
|---|---|
| `front/static/front/js/annonces.js` | **nouveau** : enveloppe Swal.fire, annonce les toasts |
| `front/templates/front/base.html` | region live persistante + chargement apres SweetAlert |
| `front/tests/test_phases.py` | 3 tests : region live, ordre de chargement, exclusion des modales |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Bascule CSS, lot T10 : les ecrans staff, et la fin du
## chantier

**Quoi / What :** les ecrans d'administration de `hypostasis_extractor`
(configuration des LLM, editeur d'analyseur, historique et diff de
versions, exemples, entrainements) n'avaient jamais ete touches. Ils
sont ecrits ENTIEREMENT en utilitaires Tailwind : ~300 occurrences
colorees sur 18 gabarits.

**Aucun de ces gabarits n'a ete modifie.** Les enumerer classe par
classe aurait double la feuille sans jamais couvrir les variantes
(`hover:`, `peer-checked:`, `focus:`, `border-l-`) : on a remappe les
ECHELLES elles-memes — slate/gray, green/emerald, red/rose,
amber/yellow/orange, violet/purple — en laissant le NIVEAU porter le
role (50-100 fond, 200-300 filet, 400+ teinte pleine). Les ambres
partent sur `--faible` et non sur `--statut-commente` : en texte,
l'ambre pur ne fait que 2,2:1.

La verification a trouve six defauts que le seul remappage ne pouvait
pas corriger, tous repares :
- un fond semantique PLEIN portait du texte `blanc` : en sombre ces
  fonds s'eclaircissent et le blanc y tombait a **1,52:1** (badge
  « IA active »). Le texte y est desormais `--papier`, qui suit le
  theme ;
- `.text-slate-300` sert de TEXTE (numeros d'ordre a 9px) la ou le
  niveau 300 de l'echelle est reserve aux filets de controle : 3,02:1 ;
- **241 champs** dessines avec `border-slate-200`, un filet decoratif a
  1,19:1 — les elements de formulaire prennent maintenant
  `--filet-controle` ;
- **`focus:outline-none` battait le focus visible global** (0,2,0
  contre 0,1,0) : un champ focalise au clavier ne montrait plus rien
  des que son `ring` etait absent. Le focus est un invariant
  d'accessibilite (WCAG 2.4.7), il passe en `!important` ;
- sous 640px, les rangees de controles poussaient leur bouton
  « Sauver » HORS du viewport, sans defilement pour le rattraper ;
- les deux ecrans de versions n'avaient aucun conteneur et commencaient
  au bord gauche de la fenetre.

**Le code mort du poste 0.1, supprime dans la foulee.** Verification
faite, il ne s'agissait pas de trois VUES cassees mais de trois
BRANCHES HTML a l'interieur de ViewSets DRF qui servent aussi du JSON —
supprimer les vues aurait casse l'API. Ces branches etaient
**doublement mortes** : leur template etend `core/base.html`, absent du
depot, ET la condition `request.accepted_renderer.format == 'html'` ne
pouvait jamais etre vraie, aucun renderer HTML n'etant configure (DRF
s'en tient a JSON + BrowsableAPI, dont le format est `api`). Verifie
en reel avant et apres : `/api/extraction-jobs/` et
`/api/extraction-examples/` repondent 200 en JSON comme en HTML, avant
comme apres. Retire : les 3 branches, et 4 gabarits
(`job_list.html`, `job_detail.html`, `example_list.html`, plus
`analyseur_list.html`, orphelin sans aucune reference).

782 tests `hypostasis_extractor` + `test_phases` et 104 e2e verts apres
la suppression.

104 tests e2e et 585 tests unitaires verts.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | section T10 : 5 echelles remappees + 6 correctifs cibles |
| `front/templates/front/*.html` | cache-busting maquette.css v15 |
| `hypostasis_extractor/views.py` | 3 branches HTML mortes retirees (l'API JSON est intacte) |
| `hypostasis_extractor/templates/.../{job_list,job_detail,example_list,analyseur_list}.html` | supprimes (~285 lignes) |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Bascule CSS, lots T6 a T9 : pages nues, theme sombre,
## overlays, purge — et les restes d'accessibilite

**Quoi / What :** la fin du chantier de bascule. Toujours du front pur :
aucun modele, aucune migration, aucun endpoint touche. Chaque lot a ete
verifie au navigateur par un agent Playwright avec contrastes calcules,
et chaque ecart trouve a ete corrige puis contre-verifie.

**T6 — les cinq pages nues** (connexion, inscription, token, 403,
invitation) : elles n'avaient AUCUN equivalent dans la maquette
(cahier des charges § 2.4, trou n°1). Gabarit neuf `.page-nue` — une
`.zone-corpus` etroite de 26rem — qui REUTILISE les composants
existants (`.champ-*`, `.bouton-plat`, `.surface-formulaire`,
`.message-etat`, `.pied-page`) plutot que d'inventer un systeme
parallele. Elles chargent maintenant la couche maquette : ce sont les
premieres pages hors `base.html` a le faire.

**T7 — le theme sombre, qui n'existait pas.** Mecanisme a trois etats
de l'etalon (`:root` / `@media prefers-color-scheme` /
`[data-theme="dark"]`) plus la PERSISTANCE `localStorage` que l'etalon
n'a pas, appliquee dans le `<head>` avant le premier rendu pour ne pas
clignoter. Les 8 tokens de surface sont ceux de l'etalon au bit pres
(verifie contre le fichier). **Ses accents, eux, ne survivent pas au
fond sombre** — `--info` y tombe a 2,26:1 — donc ils basculent aussi,
ainsi que les 8 familles d'hypostases, les deux tokens de statut et le
filet de controle. Trouve et repare a la verification : l'onboarding
entier reste en couleurs Tailwind (titre a 1,02:1), un ilot `#fafbfc`
oublie, les ombres portees noires devenues invisibles, les soulignements
de statut ecrits en `rgba()` fixe (1,37:1) et **l'ambre pur lui-meme,
qui ne fait que 2,20:1 sur le papier clair** — d'ou un token
`--filet-statut-commente` qui le fonce en clair et le laisse pur en
sombre.

**T8 — les overlays.** Modale d'alignement (les fonds blancs sticky
etaient vises par les classes de la MAQUETTE, absentes de
l'application : corrige sur les vraies classes), badges d'hypostase du
drawer re-derives de la teinte de leur famille, bottom sheet, voiles.
**Decouverte du lot** : les 150 lignes de `.ws-toast*`
(hypostasia.css:1668-1810) sont du CSS MORT — zero occurrence dans un
`.js`, un `.html` ou un `.py`. Les « deux systemes de toasts » du
cahier des charges n'en font plus qu'un : c'est SweetAlert qu'on
habille.

**T9 — la purge.** Deux `.woff2` de Lora orphelins supprimes (aucun
`@font-face` ne les nommait). Et les **deux tests-mensonges** reecrits
sur le contrat REEL : « le body est en B612 » devient « la couche
maquette, chargee en dernier, met le body en Georgia », avec un test
qui verifie l'ORDRE DE CHARGEMENT — c'est lui le contrat, l'inverser
rendrait le corps a B612 sans qu'aucun autre test ne bronche.

**Accessibilite — les restes du plan, tous traites :** lien
d'evitement (la barre compte quinze controles avant le contenu),
`aria-expanded`/`aria-haspopup`/`aria-controls` et fermeture a Echap
avec retour du focus sur le menu utilisateur, onglets du carnet devenus
un vrai tablist (`aria-controls`, `role=tabpanel`, `aria-labelledby`
qui SUIT l'onglet courant, fleches en activation manuelle, un seul
onglet dans l'ordre de tabulation), `aria-live` resserre du panneau
entier vers la seule liste rechargee, repli `@supports` pour `:has()`,
et le manifeste — page entiere jamais basculee, 1,02:1 en sombre —
passe integralement en tokens.

**Le troisieme reservoir de couleurs**, trouve a la toute fin : le
plugin Tailwind Typography porte les siennes dans des variables
`--tw-prose-*` en `oklch`, hors de portee du remappage des echelles
comme des regles par classe. Le texte d'une citation en bloc tombait a
**1,07:1** en sombre — un bloc vide avec une barre bleue. Les 16
variables sont remappees a la source. Regle du chantier, confirmee
trois fois : quand une couleur resiste, chercher la VARIABLE qui la
porte plutot qu'ajouter un selecteur.

**Deux tests-mensonges de plus, decouverts par la suite e2e** :
« la police B612 est chargee » et « la police Lora est chargee »
echouaient — non parce qu'une police avait disparu, mais parce que le
navigateur ne charge une police que si un element l'emploie, et que
depuis la decision D1 ni B612 ni Lora n'habillent plus le corps. Elles
ne servent plus qu'aux ilots de provenance, absents d'une page sans
extraction. Les deux tests verifient desormais la DECLARATION (comme
celui de Srisakdi, deja ecrit ainsi), et un test neuf assied le
nouveau contrat : le corps de lecture est en Georgia.

**Une regression trouvee par la suite mobile et corrigee** : le bouton
de bascule du theme mangeait la largeur du titre du document dans la
barre, jusqu'a le faire disparaitre sous 640px. Il y est masque — le
titre est plus utile la, et la bascule reste accessible depuis la page
de reglages et les pages nues.

669 tests verts (test_phases, test_rendu_elements, corpus D a H,
phase28) et **les 104 tests e2e** de la suite complete.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | theme sombre 3 etats, tokens d'accents sombres, `--filet-statut-*`, overlays, SweetAlert, onboarding, lien d'evitement, repli `:has()` |
| `front/static/front/js/theme.js` | **nouveau** : le theme 3 etats et sa persistance |
| `front/static/front/js/user_menu.js` | aria-expanded, Echap, retour du focus |
| `front/templates/front/{login,register,mon_token,acces_refuse,invitation_erreur}.html` | gabarit `.page-nue` + bascule de theme |
| `front/templates/front/base.html` | lien d'evitement, bouton de theme, aria du menu |
| `front/templates/front/corpus/_style_maquette.html` | `.page-nue`, `.vide`, `.bouton-icone`, `.groupe-actions`, contours de controles, onglet actif |
| `front/templates/front/corpus/carnet_detail.html` | tablist complet, aria-live resserre |
| `front/templates/front/includes/manifeste.html` | 14 couleurs en dur -> tokens |
| `front/templates/front/includes/lecture_principale.html` | les 6 utilitaires `prose-*` COLORES retires (ils battaient les variables) |
| `front/tests/test_phases.py` | 2 tests-mensonges reecrits + 3 tests neufs |
| `front/tests/e2e/test_22_corpus.py` | clique la puce et non la case masquee |
| `front/tests/e2e/test_06_charte_visuelle.py` | 2 tests de police reecrits + 1 test neuf (corps en Georgia) |
| `front/static/front/fonts/lora-{medium,semibold}.woff2` | supprimes (orphelins) |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Bascule CSS, lots T4 et T5 : la lecture, puis les
## trois derniers ecrans corpus

**Quoi / What :** deux lots livres et verifies au navigateur (agent
Playwright, contrastes calcules), sans toucher un modele, une migration
ni un endpoint.

**T4 — l'ecran de lecture.** Les derniers bleus du produit y vivaient.
Plutot qu'un selecteur par utilitaire, on REMAPPE A LA SOURCE les
echelles Tailwind `--color-blue-*` et `--color-indigo-*` vers
`var(--info)` : d'un coup, `hover:`, `prose-a:`, `prose-blockquote:` et
`border-l-` suivent, la ou une liste de classes ne les atteignait pas.
Puis : liens du corps en `--info` souligne (7,71:1), citation en bloc au
filet `--info`, legendes et en-tetes de tableau en monospace, chrome de
la page (Source / Exporter / Historique / pilules de version) en
monospace dense. Les PASTILLES de marge perdent leur halo bleu au profit
de l'ambre, et leur ecart passe a 8px : 16px + 8px = 24px de centre a
centre, soit l'EXCEPTION D'ESPACEMENT de WCAG 2.5.8 (la geometrie ne
peut pas grandir, le clip-path du triangle l'interdit).
Trois defauts trouves par la verification et corrigees dans la foulee :
le flash au clic (`@keyframes hl-pulse`, `bloc-flash-pulse`, ecrits en
bleu Tailwind en dur — les keyframes de meme nom sont REDEFINIES dans
maquette.css, hypostasia.css n'est pas touchee) ; le nom d'utilisateur
de la barre, NOIR SUR NOIR (1:1 -> 10,56:1) parce qu'un `<span>` a
quatre niveaux echappait aux selecteurs « enfant direct » ; l'avatar et
le lien Connexion sur la barre sombre (2,18:1 -> 10,18:1).

**T5 — carnets_liste, bases_liste, base_detail** portes sur
`.zone-corpus` / `.ligne-note` comme carnet_detail : ils forment
desormais un systeme avec lui (memes polices, memes tailles, meme
largeur de 64rem, verifie au pixel). Tous les `data-testid` sont
conserves a l'identique. La visibilite passe en icone ET mot, les etats
vides EXPLIQUENT la regle au lieu de la constater, et le design system
gagne cinq composants (`.lien-navigation`, `.vide`, `.rangee-champ`,
`.bouton-icone`, `.marque-visibilite`, `.groupe-actions`).
**Ecart assume vs l'etalon** : un token `--filet-controle` (3,27:1)
remplace `--filet` (1,28:1) sur le contour des champs et des boutons —
WCAG 1.4.11 demande 3:1 quand le contour est le seul indice visuel du
controle. L'etalon est fautif sur ce point ; la doctrine du chantier est
de faire mieux que lui en accessibilite, pas de le copier.

571 tests (test_phases + test_rendu_elements) et 122 tests corpus verts.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | remappage des echelles Tailwind, section T4, keyframes ambre, barre (utilisateur/avatar/connexion), `--filet-controle` |
| `front/templates/front/corpus/_style_maquette.html` | 6 composants ajoutes, contours de controles renforces |
| `front/templates/front/corpus/carnets_liste.html` | porte sur .zone-corpus / .ligne-note |
| `front/templates/front/corpus/bases_liste.html` | idem |
| `front/templates/front/corpus/base_detail.html` | idem + edition des categories dans la ligne |
| `front/templates/front/corpus/partials/categories_de_la_base.html` | axes et categories en .axe / .etiquette-categorie |
| `front/templates/front/corpus/partials/erreurs_formulaire.html` | rouge Tailwind -> tokens |
| `front/templates/front/base.html` | cache-busting maquette.css v4 |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Branchement du moteur d'ancrage, BR-A : le flag Page.moteur

**Quoi / What :** premiere phase du branchement (SPEC-ancrage v2 § 9,
cahier PLAN/branchement-moteur-ancrage-cahier-des-charges.md) :
- `Page.moteur` (ancien/element, defaut ancien, db_index) — un CHAMP
  explicite, decision D1 : le discriminant implicite elements.exists()
  prendrait une ingestion echouee pour une page ANCIEN.
- Migration core.0053 (appliquee sur dev) : schema + AUCUN estampillage
  — c'est un choix documente (§ 9.2) : tout l'existant reste ANCIEN,
  y compris les 537 pages/541 du dev decouvertes porteuses d'elements
  DORMANTS (phases de test du moteur). Les basculer serait changer le
  rendu du corpus entier d'un coup ; la reconversion est une decision
  explicite (§ 9.5), quasi gratuite le jour venu.
- Le flag ELEMENT est pose au point de passage unique de l'ingestion
  (creer_les_elements_d_une_page) — teste, y compris le cas D1 (page
  ELEMENT a zero element).
- Addendum date pose dans SPEC-ancrage-par-element-v2.md (D1-D2 +
  decouverte).

| Fichier | Changement |
|---|---|
| `core/models.py` | + MoteurDePage, + Page.moteur |
| `core/migrations/0053_page_moteur.py` | Schema + noop documente |
| `hypostasis_extractor/services/ingestion_docling.py` | Pose du flag |
| `core/tests/test_moteur_flag.py` | 5 tests |

Suite : BR-B (routage de l'import fichier vers l'ingestion Docling).

### Migration
- **Migration necessaire / Migration required :** Oui — core.0053
  (appliquee sur dev).

---

## 2026-08-09 — Bascule CSS v2 : les correctifs des trois audits

**Quoi / What :** trois agents (visuel Playwright, audit statique,
audit accessibilite avec ratios calcules) ont confronte le re-skin ;
TOUS les bloquants corriges le soir meme :
- **Chrome repare** : les menus deroulants de la barre (utilisateur,
  taches) etaient BLANC SUR BLANC (1,59:1) — regles nav.h-12
  restreintes aux enfants directs, panneaux en papier/encre ; nom
  d'utilisateur lisible ; focus PAPIER sur la barre sombre (2,18 ->
  16,79:1) ; 4 etats du bouton taches lisibles ; separateur re-teinte.
- **Source unique des tokens** (le :root de _style_maquette retire) +
  REMAPPAGE des ~50 tokens de hypostasia.css vers la palette papier —
  surfaces blanches, textes slate et halo d'ancre bleu (desormais
  AMBRE) suivent d'un coup.
- **Accueil onboarding** re-skinne (etait reste entier a l'ancien
  design, 4 contrastes < 2,6) ; **corps de lecture en Georgia/encre**
  (decision D1 : Lora quitte le corps, la maquette fait foi) ;
  **surlignages d'extraction recolores** (les statuts riches
  controverse/consensuel/discutable restes en base n'avaient PLUS
  AUCUNE couleur — bug pre-existant repare : vert/rouge/ambre legers).
- **Semantique des messages** : ambre/vert/info/danger re-teintes DANS
  leur teinte (plus jamais fusionnes en beige), bordures assorties,
  bg-red-50 et bg-amber-50/30 couverts.
- **Accessibilite** : teintes Wong plus jamais en texte (1,29:1 !) —
  contour + fond 18 % + encre ; soulignements de verdicts >= 3:1 ;
  cibles boutons d'ordre/renvois elargies ; focus visible des
  puces-filtres ; panneau de preuve ferme NON tabulable + role dialog
  + focus donne a l'ouverture + Escape conditionne (ne vole plus le
  focus) ; reduced-motion GLOBAL (46 animations de hypostasia.css
  comprises) ; noscript des filtres fonctionnel (method/action).
- **Acces direct** : /wikis/{id}/ et /syntheses/{id}/ rendent la page
  COMPLETE hors HTMX (branche article_preloaded), les collections
  carnet redirigent — plus de fragments nus en Times New Roman.
- Arbre/drawers : monospace etalon, boutons/etats actifs en
  papier/ambre (plus d'indigo) ; bottom-sheet papier.

Verifie en navigation reelle apres redeploiement. Lots restants et
restes a11y consignes dans PLAN/bascule-css-etat-2026-08-09.md (~6 j).

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | v2 : tokens uniques + remappage + tous les correctifs |
| `front/templates/front/corpus/_style_maquette.html` | :root retire, Wong, verdicts 3:1, cibles, focus, panneau |
| `front/templates/front/corpus/article.html` | role dialog, focus, Escape conditionne |
| `front/templates/front/corpus/carnet_detail.html` | noscript fonctionnel |
| `front/templates/front/base.html` | branche article_preloaded |
| `front/views_synthese.py` | acces direct -> page complete / redirect |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — La couche maquette GLOBALE : le chrome du site re-skinne

**Quoi / What :** suite de la bascule (decision du proprietaire) — le
design de l'etalon applique au RESTE du site par une couche globale :
- `front/static/front/css/maquette.css`, chargee EN DERNIER dans
  base.html : body Georgia sur papier, barre du haut SOMBRE en
  monospace (le pupitre de l'etalon), arbre lateral et drawers en
  papier-panneau avec filets, re-teinte des utilitaires Tailwind les
  plus porteurs de l'ancien look (bg-white -> papier, text-blue ->
  info, border-slate -> filet, bg-slate -> papier-creux), focus
  visible global, selection ambre.
- STRATEGIE DE COUCHE, pas de reecriture : aucun CSS existant modifie
  (tailwind.css et hypostasia.css intacts — les ~40 classes de
  test_phases qui assertent leur texte restent vertes, 537 tests OK),
  aucun template du reste du site touche. Les ecrans corpus/synthese
  gardent leur design system complet (.zone-corpus).
- collectstatic fait, verifie en navigation reelle (fond papier,
  Georgia, barre sombre calcules par getComputedStyle).
- Verification en cours par 3 agents (visuel Playwright, audit
  statique des couches, accessibilite/regressions) — rapports a
  consigner.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | Nouveau : la couche globale |
| `front/templates/front/base.html` | + le link de la couche (en dernier) |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Le design de la maquette porte dans Django (ecrans corpus/synthese)

**Quoi / What :** decision du proprietaire (« l'ancien CSS est a
jeter, le design de la maquette est tres bon ») : le design system de
l'etalon tmp/maquettes/corpus.html est PORTE dans Django, avec les P0
de la confrontation maquette integres.
- `front/templates/front/corpus/_style_maquette.html` : les tokens et
  composants de l'etalon (Georgia, papier/encre/filet, onglets a
  soulignement ambre, puces-facettes, lignes de notes en grille,
  article-synthese, renvois exposants, panneau de preuve LATERAL fixe
  + voile, operations a liseret par type, surfaces de creation),
  SCOPES sous .zone-corpus pour cohabiter avec l'ancien CSS du reste
  du site jusqu'a la bascule complete. prefers-reduced-motion
  respecte. Etats etendus vs etalon : source_debat, conteste,
  non_verifie (pointille).
- **Les P0 de la confrontation** :
  1. LES VERDICTS AU FIL DU TEXTE : chaque paragraphe est une
     .affirmation[data-verification] coloree (pire verdict de ses
     citations ; AUCUNE citation = non_source ROUGE, § 4.4) +
     legende des etats + comptes de verdicts dans l'en-tete.
  2. Panneau de preuve LATERAL (.est-ouvert, voile, ✕, Escape,
     renvoi marque actif, focus rendu a la fermeture).
  3. /lire/ REDIRIGE les articles de synthese vers leur ecran
     (un wiki ouvert par l'arbre ne perd plus ses citations) ;
     les syntheses historiques versionnees gardent l'ecran lecture.
  4. Navigation : bouton retour-liste, hx-push-url sur l'onglet
     Notes, etat actif des onglets tenu par 3 lignes de JS
     (aria-selected ne ment plus), compteurs Wikis (n) /
     Syntheses (n).
  5. Le compteur d'ecartees DANS le summary (« 46 extractions du
     perimetre n'ont pas ete reprises »), charge a l'ouverture du
     pli ; « Sources citees : N extractions (M renvois) » — deux
     comptes, deux mots. Les lignes de liste sont QUALIFIEES
     (sources · ecartees · verifiees · faibles).
- La garde zero-citation (voir phases H-I) est nee d'un constat reel
  pendant cette livraison.

Verifie en navigation reelle (Playwright, hyp.nasjo.fr/carnets/1/) :
onglet actif honnete, 8 affirmations colorees (6 faibles oranges,
2 verifiees vertes), legende, panneau lateral + Escape, summary
chiffre, qualification des listes, zero erreur JS.

| Fichier | Changement |
|---|---|
| `front/templates/front/corpus/_style_maquette.html` | Nouveau : le design system de l'etalon, scope |
| `carnet_detail.html`, `partials/notes_du_carnet.html` | Refonte aux classes maquette (testids conserves) |
| `article.html`, `liste_wikis.html`, `liste_syntheses.html` | Refonte + P0 |
| `partials/preuve.html`, `partials/diff_operations.html` | Classes maquette (etat-verification, operation[data-op]) |
| `front/views_synthese.py` | Affirmations colorees, comptes distincts, qualification des lignes, compteur d'ecartees |
| `front/views_corpus.py` | Compteurs d'onglets wikis/syntheses |
| `front/views.py` | Redirection /lire/ des articles de synthese |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Couche synthese, phases H-I : les ecrans wikis et syntheses

**Quoi / What :** la couche synthese devient VISIBLE (§ 10) :
- **Onglets reels** sur l'ecran carnet : Notes / Wikis / Syntheses
  dirigees (role tablist ARIA revenu avec le 2e vrai onglet, audit D8).
- **Taches carnet-niveau** (front/tasks.py) : `produire_un_wiki_task`
  (perimetre RECALCULE § 3.1.1), `produire_une_synthese_de_carnet_task`
  (multi-notes — la vue cree l'acte date et FIGE le perimetre AU MOMENT
  DU GESTE, la tache remplit), `proposer_une_maj_de_wiki_task` (des
  operations § 6 sur les ecartees, JAMAIS auto-appliquees, fraicheur
  addendum n°1), `verifier_les_citations_task` (§ 7 a la demande).
  Toutes sur le contrat phase C (marqueurs, CITATIONS_USED, perimetre
  obligatoire). NOUVELLE GARDE (constat sur GPT-4o-mini reel) : un
  article sans AUCUNE citation sur un perimetre non vide est REFUSE —
  un texte sans preuve n'est pas un succes.
- **Endpoints** (front/views_synthese.py) : WikiViewSet (liste/creer
  par carnet, article, mise_a_jour -> proposition -> appliquer,
  verifier), SyntheseViewSet (liste/creer par carnet — garde-fou § 3.3
  mecanique et DIT a l'utilisateur —, article, ecartees § 8 avec refus
  honnete des historiques, couverture § 9 par note, verifier, PAS de
  mise a jour : bouton desactive avec motif § 10), CitationViewSet
  (panneau de preuve : citation exacte, verdict AVEC provenance § 7.2,
  debat joint, etat de la source, retour a la source).
- **Phase I** : le diff des operations previsualise par UN PASSAGE A
  BLANC de l'applieur reel (jamais deux verites) — l'humain coche
  operation par operation, le replace montre l'AVANT (§ 6.4), les
  rejets mecaniques sont montres avec contenu conserve, les
  contestations perdues sont affichees apres application (relecture G).
- **Renvois [N] cliquables** : le HTML de l'article est re-rendu avec
  des ancres HTMX liees a LEUR SourceLink (couple paragraphe-extraction
  par bornes cibles) -> panneau de preuve.

Valide sur DONNEES REELLES (carnet public « Demonstration », GPT-4o-mini) :
synthese de carnet a 8 citations (verification reelle : 2 verifiees /
6 faibles, provenance posee), wiki a 9 citations apres renforcement de
la consigne de sourcage.

| Fichier | Changement |
|---|---|
| `front/views_synthese.py` | Nouveau : 3 ViewSets |
| `front/tasks.py` | + 4 taches + helpers partages + garde zero-citation |
| `front/urls.py` | Routes /wikis/, /syntheses/, /citations/ + collections carnet |
| `front/templates/front/corpus/` | liste_wikis, liste_syntheses, article + partials (preuve, ecartees, couverture, diff_operations, tache_lancee, erreur) |
| `front/templates/front/corpus/carnet_detail.html` | Onglets reels (tablist) |
| `front/tests/test_synthese_phase_h.py` | 16 tests |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Couche synthese, phase G : la verification des citations

**Quoi / What :** SPEC-synthese § 7 — deux controles en cascade, PAR
PAIRE (affirmation, source) :
1. **Verbatim** (deterministe, gratuit) : le texte cite existe-t-il
   litteralement dans la source ACTUELLE ? Tolerant aux espaces,
   sensible au reste. En echec sur l'extraction, on cherche dans les
   COMMENTAIRES : une affirmation qui reprend fidelement un commentaire
   est SOURCEE PAR LE DEBAT (§ 7.4, nouvel etat SOURCE_DEBAT +
   commentaires_source rempli) — pas « faible ». En echec partout :
   FAIBLE, sans payer d'appel au juge.
2. **Implication (NLI)** : jugee par LE LLM CONFIGURE, EN LOT (une
   requete pour N paires) et A LA DEMANDE — question ouverte n°3
   TRANCHEE par le proprietaire (9 aout) : pas de modele local sur un
   serveur 8 Go partage ; ~0,01-0,05 EUR par synthese en lot.

Les garanties § 7.2 :
- chaque verdict porte sa PROVENANCE (`verifie_par` = methode + modele,
  `verifie_le`) — « un etat sans provenance est un argument d'autorite
  automatise » ;
- l'etat CONTESTE pose par un humain n'est JAMAIS ecrase par une
  re-verification ;
- un verdict ABSENT de la reponse du juge (troncature, refus) laisse la
  paire NON_VERIFIE et le signale — jamais un faux « verifie ».

| Fichier | Changement |
|---|---|
| `core/models.py` | EtatDeVerification + CONTESTE + SOURCE_DEBAT ; SourceLink + verifie_par/verifie_le |
| `core/migrations/0052_provenance_du_verdict.py` | Schema (appliquee sur dev) |
| `core/services/verification.py` | Nouveau : la cascade + le juge en lot |
| `core/tests/test_verification.py` | 7 tests |

Le declenchement (endpoint « verifier cette synthese ») est la phase H —
le service est A LA DEMANDE par construction, jamais appele a la
production d'une synthese.

### Relecture / Review
Relecture adverse passee (9 aout, nuit — parsing et normalisation
prouves par execution), 2 bloquants et 7 importants corriges avec
leurs tests (19 au total) :
- **B1 (le plus grave)** : reconstruire l'index des citations
  (indexer_les_citations, phase B) DETRUISAIT tous les verdicts — y
  compris un CONTESTE humain. L'indexeur RECONCILIE desormais : un
  verdict est reporte quand la paire (extraction, paragraphe) est
  inchangee ; une contestation dont la paire a disparu est SIGNALEE
  (bilan["contestations_perdues"]), jamais perdue en silence.
- **B2 (injection)** : le prompt du juge encadre chaque donnee par des
  delimiteurs NONCE (l'affirmation et la source viennent de notes
  potentiellement hostiles), et une reponse aux indices dupliques,
  hors lot ou surnumeraires est REJETEE EN ENTIER — le lot reste
  NON_VERIFIE, jamais un faux « verifie » injectable.
- **I1** : une exception du juge (timeout, quota) ne degrade RIEN —
  les verdicts precedents survivent, l'echec est au bilan.
- **I2** : une source supprimee perd son verdict vert (provenance
  « source supprimee — verdict retire »).
- **I3** : des bornes cibles perimees (article edite sans
  re-indexation) ne sont JAMAIS jugees — le paragraphe doit contenir
  son marqueur.
- **I4** : la fidelite au DEBAT se juge aussi — reprendre un
  commentaire verbatim puis le deformer dans la conclusion donnait un
  SOURCE_DEBAT immerite ; le chemin debat passe au juge (soutient ->
  SOURCE_DEBAT, sinon FAIBLE).
- **I5** : le lot est decoupe par paquets de 20 (contextes et timeouts
  bornes), echec par paquet isole.
- **I6** : une extraction masquee ou une ancre detachee n'est pas
  blanchie par un verdict frais (non_jugeables au bilan).
- **I7** : commentaires_source suit toujours le verdict (plus de
  provenance « debat » orpheline sous un verdict faible).
- Mineurs : juge jamais anonyme (name ou model_choice), NFKC +
  apostrophes typographiques dans le verbatim, tolerance puces dans
  les lignes de verdict (indices controles strictement), marqueurs
  retires de l'affirmation envoyee au juge, texte source charge une
  fois par note, ordre deterministe des paires, NON_SOURCE documente
  comme etat d'affichage (jamais pose en base).
- Pour la phase H (fiche A TESTER) : l'etalon corpus.html ne connait
  pas encore source_debat/conteste/non_verifie — la maquette et
  verifier_les_maquettes.py devront etre etendus.

### Migration
- **Migration necessaire / Migration required :** Oui — core.0052
  (appliquee sur dev).

---

## 2026-08-09 — Couche synthese, phase F : l'applieur d'operations de section

**Quoi / What :** SPEC-synthese § 6 : le modele ne reecrit jamais un
wiki — il propose des operations (no_change, append_to_section,
replace_section, insert_section) qu'un applieur fusionne et qu'un
humain accepte.
- `core/services/section_ops.py` : `appliquer_les_operations()`,
  fonction PURE (l'appelant phase H sauvera, reindexera les citations
  et incrementera tours_de_mise_a_jour).
- Un titre introuvable est une HALLUCINATION : operation rejetee
  VISIBLEMENT avec son motif, contenu CONSERVE — jamais de fallback en
  fin d'article, jamais de perte silencieuse (§ 6.2, corrige
  INSPIRATION_ATOMIC § 7). Titre duplique = cible ambigue = rejet.
- Rejet PAR OPERATION (addendum n°4) : une hallucination ne jette pas
  les faits des autres operations.
- Controles § 6.3 deterministes : sources DERIVEES des marqueurs
  [[ext:N]] du contenu (le markdown est la verite) — operation sans
  marqueur ou citant hors perimetre : rejetee.
- Seuls les ## font frontiere (addendum n°3) ; replace retourne
  l'ancien corps pour le diff (§ 6.4).
- `verifier_que_la_proposition_est_fraiche()` : concurrence optimiste
  par updated_at (addendum n°1) — proposition perimee refusee
  visiblement, horodatage illisible traite comme perime.

| Fichier | Changement |
|---|---|
| `core/services/section_ops.py` | Nouveau : l'applieur + la garde de fraicheur |
| `core/tests/test_section_ops.py` | 13 tests (§ 12 + par-operation, ambiguite, ## seulement, ISO) |

**Egalement** : question ouverte n°5 TRANCHEE par le proprietaire (au
plus simple : editer_bloc reste non garde, le gel § 5 effectif sera
livre avec le branchement du moteur element).

### Relecture / Review
Relecture adverse passee (9 aout soir, constats PROUVES par execution),
1 bloquant et 6 importants corriges avec leurs tests (+11) :
- **B1** : le contenu d'une operation pouvait CONTENIR un titre ## et
  fabriquer une section que l'humain n'a pas approuvee — avec un titre
  duplique rendant la section ambigue pour toujours. Rejet : seule
  insert_section cree une section.
- **I1** : insert d'un titre deja present -> rejet (meme corruption).
- **I2** : reconnaissance de frontiere PARTAGEE applieur/indexeur
  (`titre_de_section()`, permissive sur l'indentation) — un titre
  indente ne range plus un ajout dans la mauvaise section.
- **I3** : les titres se comparent tronques a 200 (la taille de
  SourceLink.section, la forme que le prompt peut montrer au modele).
- **I4** : une operation JSON malformee (mauvais types) est rejetee
  PAR OPERATION avec motif, plus jamais une exception qui detruisait
  le lot entier (addendum n°4 respecte jusqu'au bout).
- **I5** : ancre d'insertion absente -> motif honnete (« non
  renseignee », pas « hallucinee »).
- **I6/addendum n°15** : le schema des operations (type/section/titre/
  apres/contenu, snake_case FR) est contractualise dans la spec.
- Mineurs : no_change fantome signale (M1), CRLF normalise (M2), titre
  d'insertion multi-lignes ou en # rejete (M3), recherche par indice
  (M4), UNE operation de contenu par section et par lot (M5 — sinon
  l'« avant » du diff § 6.4 mentirait), indice d'origine dans les
  resultats (M6), motifs FALC (M7), assertion discriminante (M8).
- Caveats d'integration phase H consignes dans la docstring de
  verifier_que_la_proposition_est_fraiche (re-controle sous verrou,
  .isoformat() jamais un filtre localise).

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Couche synthese, phase E : le blocage d'edition d'une source citee

**Quoi / What :** SPEC-synthese § 5 : editer un ElementDocument dont une
portion appartient a une extraction citee par une synthese DIRIGEE est
refuse — la preuve d'un acte adopte ne bouge pas. Un wiki ne bloque
rien (il est vivant, le tour suivant corrige).
- `EditionBloqueeParUneSynthese` + `verifier_qu_aucune_synthese_ne_cite`
  (element) + `verifier_qu_aucune_synthese_ne_cite_la_page`
  (reingestion) dans garde_edition.py. Le refus NOMME la synthese et sa
  date (§ 5.3) ; seuls les liens CITE gelent (jamais les liens de
  versionnage historiques).
- Six sites gardes, juste apres verifier_qu_aucune_analyse_ne_tourne :
  reconciliation, masquage, demasquage, scission, fusion (les DEUX
  elements), reingestion (page entiere).
- ATTENTION AU M2M : citer une extraction gele TOUS les elements
  qu'elle traverse — une preuve coupee en deux n'est plus une preuve.
- La reconciliation reste intacte (§ 5.2) : elle repositionne les
  ancres des editions AUTORISEES ; le blocage protege les actes dates.

| Fichier | Changement |
|---|---|
| `hypostasis_extractor/services/garde_edition.py` | + exception + 2 gardes |
| `reconciliation.py`, `masquage.py`, `moteur_structure.py`, `reingestion.py` | + appels aux 6 sites |
| `core/tests/test_garde_synthese.py` | 7 tests (§ 12 + masquage, scission, lien non-CITE) |

115 tests extractor relances : aucune regression.

### Relecture / Review
Relecture adverse des lots D+E passee (9 aout soir), 3 bloquants et
4 importants corriges avec leurs tests :
- **B1** : la garde § 4.2 de run_langextract_job etait placee APRES
  l'appel LLM — on payait des minutes de modele pour un job voue au
  refus. Hissee AVANT l'appel (et gardee en profondeur avant la purge).
- **B2** : « nettoyer les extractions IA » sur une page citee par une
  dirigee faisait un 500 au milieu du delete. Garde § 4.2 en amont dans
  la vue analyser, refus 409 FALC, l'extraction citee survit.
- **B3** : le figement du perimetre (.set d'ids captures avant l'appel)
  pouvait exploser sur une extraction purgee PENDANT la generation et
  perdre la synthese entiere — re-requete des survivantes.
- **I1** : le blocage du DEMASQUAGE etait un sur-blocage qui enfermait
  (element masque par erreur puis cite -> plus jamais demasquable) :
  retire — le demasquage verifie le hash et rend la preuve PLUS fidele.
  La garde § 5 couvre donc CINQ sites, pas six.
- **I2** : les ecartees d'une dirigee HISTORIQUE (perimetre jamais
  fige) auraient annonce « 100 % ecarte » : refus explicite
  (PerimetreDExtractionsInconnu) plutot qu'un mensonge a charge.
- **I4** : fusion (le SECOND element bloque aussi) et reingestion page
  desormais testees. **I5** : verifier_les_citations=False depuis la
  reingestion (la garde page est un sur-ensemble). **M6/M8/M9** :
  filtre « citable » unique, fixtures sur statuts morts corrigees,
  no-op « deja masque » avant la garde.
- **I3 (decision a trancher, consignee § 14 de la spec)** : le seul
  chemin d'edition de texte REELLEMENT expose aujourd'hui (editer_bloc,
  ancien moteur) n'est pas garde — le § 5.2 l'exonere explicitement,
  mais sa justification (« reconciliation.py rend l'interdiction
  inutile ») ne tient pas sur l'ancien moteur. Le gel effectif attend
  le branchement du moteur element, ou une decision inverse.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-09 — Couche synthese, phase D : ecartees et couverture (calculs purs)

**Quoi / What :** les deux controles que personne n'offre (SPEC-synthese
§ 8-9), calculables sans aucun appel au modele :
- `extractions_ecartees(article)` : ce qu'une synthese N'A PAS repris —
  difference d'ensembles (perimetre − citees), JAMAIS une liste
  stockee. Perimetre : notes figees pour une dirigee, notes sources du
  carnet AU MOMENT DU CALCUL pour un wiki ; par note, les extractions
  citables de son dernier job d'analyse — la MEME definition que le
  prompt de la tache (`extractions_citables_d_un_job` et
  `dernier_job_d_analyse_de_la_note`, extraites en service partage,
  front/tasks.py refactore pour les utiliser).
- `couverture_de_la_note(page)` : quels elements portent au moins une
  extraction — une jointure, pas une estimation. Separe « le modele a
  invente » de « le passage n'a jamais ete extrait » (§ 9.1).
- Une page ni wiki ni dirigee n'a pas de perimetre : ValueError
  explicite, pas un resultat vide trompeur.

| Fichier | Changement |
|---|---|
| `core/services/synthese.py` | + 5 fonctions (section PHASE D) |
| `front/tasks.py` | Refactor : definitions partagees avec le service |
| `core/tests/test_synthese_citations.py` | + 7 tests (3 configurations d'ecartees, wiki qui suit le carnet, refus des pages sans genre, jointure vs LEFT JOIN manuel) |

### Relecture / Review
Relecture adverse passee (9 aout soir) : 3 bloquants corriges avec
leurs tests (+ 8 tests, classes CorrectifsRelectureDTest et
CouvertureFiltreeTest) :
- **B1** : « le dernier job » attrapait les jobs d'extraction manuelle
  et de selection — UNE extraction ajoutee a la main evincait les 40 de
  l'analyse et le § 8 devenait un blanc-seing. Nouvelle definition :
  TOUS les jobs termines non-synthese de la note (celle de l'ecran
  d'analyse), partagee par le prompt, le perimetre de citation et les
  ecartees.
- **B2** : le perimetre d'une dirigee n'etait pas vraiment fige — une
  re-analyse posterieure reecrivait ses ecartees. La production fige
  desormais AUSSI les extractions (M2M `extractions_du_perimetre` +
  flag, migration core.0051, appliquee sur dev). Les 292 historiques
  restent en recalcul dynamique assume (flag False).
- **B3** : analyseur sans extractions -> perimetre fige VIDE -> rien
  n'est declare « ecarte » (rien n'avait ete propose).
- **I4** : filtre § 3.3 mecanique sur notes_du_perimetre (une synthese
  glissee dans le perimetre fige est ignoree). **I6** : la couverture
  ne compte plus les masquees, les ancres DETACHEE ni les jobs
  inacheves. **I8** : le filtre non_pertinent etait MORT (fusionne dans
  masquee par extractor 0029) — retire, tests et fixtures corriges, le
  tri du prompt reduit a commente-d'abord. **M10/M11** : plus de N+1
  (une requete), departage -pk. Addendums n°11-13 consignes.

### Migration
- **Migration necessaire / Migration required :** Oui — core.0051
  (perimetre d'extractions fige, appliquee sur dev).

---

## 2026-08-09 — Couche synthese, phase C : la synthese devient une note du carnet

**Quoi / What :** le coeur de SPEC-synthese § 2-3 :
- Les deux genres au modele : `Wiki` (vivant — perimetre par CATEGORIES,
  recalcule a chaque appel par `notes_du_perimetre_d_un_wiki()`, OU dans
  un axe / ET entre axes) et `SyntheseDirigee` (acte date — perimetre de
  NOTES fige a la production, jamais recalcule). Migration core.0049.
- Migration core.0050 : les syntheses existantes (typees en phase A)
  recoivent leur enregistrement SyntheseDirigee — produite_le =
  created_at, perimetre fige = la racine dont elles etaient la version.
  Reversible, bilan chiffre.
- `synthetiser_page_task` REECRITE : la synthese est une note
  `type_de_note=SYNTHESE` du carnet — plus jamais une version de page
  (parent_page n'a plus AUCUN ecrivain, § 1). Le prompt expose
  « Identifiant : ext:N » et exige les marqueurs `[[ext:N]]` + la ligne
  finale `CITATIONS_USED:` ; sans elle, la generation est TRONQUEE :
  echec bruyant (`SyntheseTronqueeError`, message FALC), rien n'est
  enregistre. `indexer_les_citations()` est appelee avec le PERIMETRE
  des extractions envoyees au modele (une seule definition,
  `_extractions_pour_la_synthese`, pour le prompt ET le perimetre) — le
  parametre est desormais OBLIGATOIRE dans la signature. Les marqueurs
  hallucines sont retires ET signales (`raw_result["marqueurs_retires"]`).
  Le HTML derive rend des renvois `[N]` (jamais persistes, § 4.4).
  Tout-ou-rien : page + liens + appartenances + acte date naissent dans
  une transaction.
- La vue `synthetiser` accepte `dossier_id` (le carnet d'origine de la
  demande, § 2.1) : ECRITURE exigee sur ce carnet, sinon 400 FALC. Elle
  pose demandeur_id + dossier_id dans le job ; la tache range la
  synthese dans ce carnet (sinon repli : les carnets de la note source)
  via `ranger_une_note_dans_un_carnet`.

**4 decisions consignees en addendum de la spec (n°5-8)** : dossier de
la dirigee SET_NULL nullable (l'acte date survit au carnet), carnet
d'origine optionnel avec repli, format exact de CITATIONS_USED, rendu
[N] au HTML.

### Fichiers / Files
| Fichier | Changement |
|---|---|
| `core/models.py` | + `Wiki`, + `SyntheseDirigee` (fin de fichier) |
| `core/migrations/0049_wiki_et_synthese_dirigee.py` | Schema |
| `core/migrations/0050_estampiller_les_syntheses_dirigees_existantes.py` | Donnees, reversible |
| `core/services/synthese.py` | + `notes_du_perimetre_d_un_wiki` ; perimetre obligatoire dans `indexer_les_citations` |
| `front/tasks.py` | Tache reecrite + `_extractions_pour_la_synthese`, `_detacher_la_ligne_citations_used`, `_remplacer_les_marqueurs_par_des_renvois`, prompt SOURCAGE |
| `front/views.py`, `front/serializers.py` | `dossier_id` valide (ecriture requise) + demandeur_id dans le job |
| `core/tests/test_synthese_modele.py` | + 8 tests (genres, perimetres, migration 0050) |
| `front/tests/test_synthese_phase_c.py` | 12 tests (note typee, citations, troncature, carnet d'origine, vue) |
| `front/tests/test_phase28_light.py` | Adapte au nouveau contrat (CITATIONS_USED, plus de version) |

### Relecture / Review
Relecture adverse passee (9 aout) : 3 bloquants et 6 importants
corriges, chacun avec son test (dans test_synthese_phase_c,
test_synthese_citations, test_synthese_modele) :
- **B1** : la ligne CITATIONS_USED habillee par le modele (backticks,
  gras, bloc de code — le format que le prompt lui montre) n'est plus
  rejetee comme troncature. Le fond reste strict.
- **B2 (XSS stocke)** : la sortie markdown passe par bleach (allowlist
  balises + protocoles http/https/mailto). `html.escape` ne touche pas
  `[texte](url)` : un `javascript:` reconstruit APRES echappement etait
  rendu `|safe`.
- **B3** : on ne synthetise JAMAIS une synthese (§ 3.3) — refus 400
  FALC dans la vue ET garde en profondeur dans la tache.
- **I1** : le perimetre fige est la note ANALYSEE, pas sa racine (le
  § 8 en depend).
- **I2** : les notifications ciblent les carnets de LA SYNTHESE + le
  demandeur (la vue lui promettait une notification).
- **I3** : une source hors carnet -> la synthese est rangee dans le
  « A ranger » du demandeur, jamais orpheline invisible.
- **I5** : un titre de section > 200 caracteres est tronque au lieu de
  detruire la synthese entiere (bulk_create).
- **I6** : le perimetre est fige AVANT l'appel LLM — une extraction
  masquee pendant la generation reste une citation legitime.
- Mineurs : rollback 0050 filtre (ne supprime que ses lignes, compteur
  exact), carnet via les appartenances si FK vide, titre date
  (« Synthese du JJ/MM/AAAA — ... »), select_related sur l'indexeur.
- Arbitrage I4 consigne en addendum n°9 (synthese visible dans l'arbre,
  ecran carnet en phase H). Limites connues restantes documentees dans
  la fiche A TESTER (garde § 4.2 no-op sur la relance nominale — les
  anciennes extractions ne sont pas purgees ; TOCTOU dossier_id
  vue->tache ; analyseur "texte seul" exige quand meme une analyse).

### Migration
- **Migration necessaire / Migration required :** Oui — core.0049 et
  core.0050 (appliquees sur dev).

---

## 2026-08-09 — Couche synthese, phase B : le lien de citation ecrit

**Quoi / What :** le prealable a tout le sourcing (SPEC-synthese § 4) :
- `SourceLink` gagne `section`, `ordre_dans_la_section`,
  `etat_de_verification` (par PAIRE affirmation-source),
  `etat_de_la_source` (presente/supprimee/detachee), et
  `TypeLien.CITE` (migration core.0048). `page_cible` EST l'article
  citant ; `ancrage_source` = la premiere portion (§ 4.5).
- `indexer_les_citations()` : le parseur `[[ext:<id>]]`. Le markdown est
  la verite, les liens son index, reconstruits a chaque enregistrement.
  Un marqueur inexistant ou hors perimetre est RETIRE du texte et
  SIGNALE — jamais garde en silence. Sections aux titres `##` seulement
  (addendum n°3). Bornes cibles = le paragraphe citant.
- Signal `pre_delete` sur ExtractedEntity : citee par une DIRIGEE ->
  suppression refusee (`SuppressionRefuseeSourceCitee`) ; citee par des
  wikis seulement -> autorisee, citations basculees SUPPRIMEE. Jamais
  d'orphelinage silencieux.
- Propagation de derive : une ancre passee DETACHEE par la
  reconciliation detache la citation qui la pointait (§ 4.2 fin).

8 tests (`core/tests/test_synthese_citations.py`). L'ecriture DANS la
tache part en phase C avec la reecriture complete de
`synthetiser_page_task` (note typee + marqueurs + ligne CITATIONS_USED).

### Relecture / Review
Relecture adverse passee (9 aout), correctifs appliques avec leurs tests
(17 au total) :
- **Garde § 4.2 avant les purges** (le bloquant) : les 3 sites de purge
  (analyse_par_element, front/tasks re-extraction, run_langextract_job)
  appellent `verifier_qu_aucune_dirigee_ne_cite_les_extractions()` AVANT
  de supprimer — refus propre en amont, plus d'exception au milieu d'une
  purge. Les vues de suppression (extraction, page entiere) repondent un
  message FALC (« citee par une synthese adoptee... ») au lieu d'un 500.
- **Parseur robuste** : CRLF normalise, titre colle a son paragraphe
  reconnu (« ## Titre\\nPhrase », courant chez les LLM), un lien par
  couple (paragraphe, extraction) meme si le marqueur est duplique,
  marqueur dans un titre retire ET signale (nom de section propre).
- **La reindexation ne blanchit pas une derive** : une ancre deja
  DETACHEE donne un lien DETACHEE.
- **Propagation complete** : le masquage et la reingestion detachent
  aussi les citations (helper partage), plus seulement la reconciliation.
- Spec § 4.2 corrigee (views.py:904 = ExampleExtraction, pas une
  extraction de corpus).
- Decision documentee : « l'ecriture dans la tache » part en phase C avec
  la reecriture complete de synthetiser_page_task — la phase B livre la
  bibliotheque et TOUTES ses gardes, branchees aux flux existants.

### Migration
- **Migration necessaire / Migration required :** Oui — core.0048,
  appliquee sur dev.

---

## 2026-08-08 — Couche synthese, phase A : le type de note et le garde-fou

**Quoi / What :** `TypeDeNote` (note/wiki/synthese) sur Page (un champ,
pas une propriete : la regle doit etre une clause filter),
`core/services/synthese.py:notes_sources_du_carnet()` — le garde-fou
« une synthese n'est JAMAIS source d'une autre synthese », exerce par
test (N notes + M syntheses → N). Migration 0047 : 292 syntheses
existantes typees (reperage par versionnage ; 0 par raw_result — les
jobs anciens n'ont pas le marqueur). Le filtre corpus passe du
versionnage au TYPE (dependance C.6, = estUneSource de l'etalon).

**Design relu avant d'ecrire** (consigne du proprietaire) : la note
d'architecture de la memoire Atomic + l'etalon corpus.html § 8 (articles
= sections → paragraphes → sources, numerotation a l'affichage).
**4 trous de spec releves et consignes en addendum de
SPEC-synthese-carnet.md** : controle optimiste de concurrence sur les
propositions (updated_at), ligne de controle anti-troncature
(CITATIONS_USED), niveaux de titre exposes (## seulement), et la
justification du rejet PAR OPERATION (pas de point de reprise chez nous,
contrairement a Atomic).

### Migration
- **Migration necessaire / Migration required :** Oui — core.0046 (champ)
  et 0047 (donnees, reversible), appliquees sur dev.

---

## 2026-08-08 — Trous de spec § 9 bouches, e2e § 10, audit UX/UI

**Quoi / What :**
1. La relation carnet-base est complete : POST /bases/{slug}/carnets/{id}/categories/
   (validation phase B en filet) et .../epingler/, avec l'UI (crayon +
   epingle dans le detail de base). 19 tests.
2. Les 5 scenarios e2e que la spec § 10 prevoyait existent enfin :
   front/tests/e2e/test_22_corpus.py (2e carnet, categorisation isolee,
   filtres ET/OU, avertissement dernier carnet, ordre au clavier) —
   verts dans un vrai navigateur. Les 37 controles de l'etalon passent.
3. Audit UX/UI en navigation reelle (agent Opus, donnees = copie de
   prod) : rapport complet dans PLAN/audit-ux-ui-2026-08-08.md
   (16 defauts D1-D16, 18 propositions P1/P2/P3). Corrections immediates
   appliquees : navigation « Carnets » / « Bases » dans la barre (une
   fonctionnalite sans point d'entree n'existe pas), etat vide didactique
   de /bases/, compteurs a zero tus, onglets « cible » regroupes en un
   indicateur « a venir » (jargon de spec retire), bloc « Dans N
   carnets » SOUS le titre (ordre de l'etalon), middleware
   Cache-Control: no-cache sur le HTML (UI perimee constatee en direct).

**Incident repare / Incident fixed :** hyp.nasjo.fr etait en 500 depuis
~7 h — workers gunicorn demarres avant les changements du jour (vieux
models.py en memoire, views.py neuf sur disque). Redemarrage du conteneur
dev. A retenir : redemarrer hypostasia_dev_web apres chaque session de
dev (ou ajouter --reload au gunicorn de dev).

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-08 — Couche corpus, phase H : la base de connaissances

**Quoi / What :** le troisieme niveau du modele Praxis : GET /bases/ et
/bases/{slug}/ (carnets de la base avec les categories de CHAQUE relation
carnet-base — meme patron que la note, un cran au-dessus),
POST carnets/ (ranger un carnet, idempotent, exige ecriture base +
lecture carnet), GET/POST categories/ (axes de la base, validation
phase B deja en place). Acces : public / owner / legacy — pas de partage
fin en v1 (§ 6.2), pas de bypass superuser en ecriture. On ne nomme
jamais un carnet que le demandeur ne peut pas lire.

| Fichier | Changement |
|---|---|
| `front/views_corpus.py` | + BaseViewSet + les deux fonctions d'acces base |
| `front/templates/front/corpus/` | bases_liste, base_detail, partials/categories_de_la_base |
| `front/urls.py`, `front/templates/front/base.html` | routes /bases/ + branches de cascade |
| `front/tests/test_corpus_phase_h.py` | 11 tests |

### Relecture / Review
Relecture adverse passee (8 aout), 4 bloquants corriges avec tests :
- le compteur de carnets de la liste ne compte plus les carnets
  invisibles (meme doctrine « jamais de fuite » que « dans N carnets ») ;
- la clause legacy est RETIREE des bases : BaseDeConnaissances est un
  modele neuf, owner=None ne peut venir que d'un compte supprime — une
  base privee orpheline se FERME, elle ne s'ouvre pas a tout authentifie ;
- POST /bases/ cree une base (sinon aucune base ne pouvait exister,
  l'admin etant desactive) + formulaire dans la liste ;
- formulaires « Ajouter un carnet » et « + Axe » dans le detail (les
  endpoints etaient orphelins), liens croises /carnets/ ↔ /bases/.
Egalement : 404 (pas 403) sur base privee — le slug EST le nom, un 403
serait un oracle d'existence ; et POST .../carnets/{id}/retirer/ —
l'owner de la base OU l'owner du carnet peut retirer (doctrine du 8 aout).

### Trous de spec § 9 releves (a trancher)
La relation carnet-base a des categories, un epinglage et un ordre manuel
au modele (§ 3.2) mais AUCUN endpoint dans la spec § 9 pour les poser
(pas d'equivalent de categoriser/epingler/reordonner cote base). Le
patron « meme chose, un cran au-dessus » s'arrete a mi-chemin.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-08 — Couche corpus, phase G : l'ecran note et le bloc « Dans N carnets »

**Quoi / What :** le bloc « Dans N carnets » editable sur l'ecran de
lecture (spec § 8.1) : chaque ligne montre un carnet ET les categories de
la note dans CE carnet-la, avec epingler, retirer (avertissement special
sur la DERNIERE appartenance, § 9), edition des categories par relation
(crayon → axes de CE carnet), « Ajouter a... » avec l'avertissement
carnet public dit AU MOMENT du geste (§ 7.3), et bascule de contexte
(le nom du carnet ouvre le carnet). Charge en HTMX par
GET /notes/{id}/carnets/bloc/ — aucun des 8 contextes de
lecture_principale.html n'est touche. Racines seulement (pas les versions).

**Egalement** : validateur hex strict sur CategorieDossier.couleur
(migration core.0045 — le champ finit dans un style= inline).

| Fichier | Changement |
|---|---|
| `front/views_corpus.py` | `bloc_carnets` (GET) + bloc enrichi (droits par ligne, carnets disponibles) |
| `front/templates/front/corpus/partials/carnets_de_la_note.html` | Reecrit : edition complete par relation |
| `front/templates/front/includes/lecture_principale.html` | + conteneur lazy du bloc |
| `core/migrations/0045_alter_categoriedossier_couleur.py` | Validateur hex |
| `front/tests/test_corpus_phase_g.py` | 7 tests |

### Migration
- **Migration necessaire / Migration required :** Oui — core.0045 (appliquee sur dev).

---

## 2026-08-08 — Couche corpus, phase F : l'ecran carnet contre l'etalon

**Quoi / What :** l'UI carnet integree au site, construite contre l'etalon
tmp/maquettes/corpus.html a partir du cahier des charges
PLAN/corpus-phase-f-cahier-des-charges.md.

**Decisions du proprietaire (deleguees le 8 aout, « securite et FALC
d'abord ») :**
1. Facettes en PUCES TOUJOURS VISIBLES (comme l'etalon), realisees en
   cases a cocher natives habillees — etat annonce nativement, fonctionne
   sans JavaScript (bouton Filtrer en noscript).
2. Integration par une BRANCHE dans la cascade de base.html (le patron
   existant du depot), pas de refonte en blocks.
3. Retrait d'une note : ecriture sur le carnet OU propriete de la note —
   personne ne peut rendre votre note publique sans que vous puissiez
   l'en sortir. Teste.

### Ce que l'ecran fait desormais / What the screen now does
- En-tete : « N notes · N axes · N categories » (tout derive), visibilite
  icone + mot, guide de redaction (nouveau champ Dossier.guide_de_redaction,
  migration core.0044 — la spec § 2 le disait « Pris », § 3 avait oublie
  le champ).
- Facettes : puces par axe avec compteur « Type (3) », point colore
  (couleur choisie ou palette Wong — jamais la couleur seule, § 8.3),
  restauration depuis l'URL (?categorie=), etat vide explicite.
- Resume des filtres : « X sur Y notes — Type : AAP OU Subvention ET ... »
  avec OU et ET ecrits, bouton « Tout afficher ».
- Ligne de note : rang ou epingle, « N extractions », « dans N carnets »
  si N>1 (annotations en une requete), etiquettes teintees.
- Ordre narratif au clavier : boutons monter/descendre (§ 8.3), echange
  des voisines VISIBLES avec transfert d'epingle (etalon:1188-1194) ;
  premier geste : l'ordre courant est fige (1..n). Les filtres actifs
  accompagnent chaque geste.
- Onglets : Notes actif avec compteur ; Wikis / Syntheses dirigees /
  Selection des preuves en pastille « cible » (le produit ne pretend pas).
- epingler/categoriser rendent la liste (ecran=carnet) ou le bloc de la
  note selon l'origine du geste.

### Fichiers / Files
| Fichier | Changement |
|---|---|
| `core/models.py` | + `Dossier.guide_de_redaction`, + `CategorieDossier.couleur_effective` (palette Wong) |
| `core/migrations/0044_dossier_guide_de_redaction.py` | Migration du champ |
| `front/views_corpus.py` | Contexte enrichi, phrase des filtres, double contrat reordonner, cible selon l'ecran, rendu base.html vs HTMX |
| `front/templates/front/base.html` | + branches carnet_preloaded / carnets_liste_preloaded |
| `front/templates/front/corpus/` | carnet_detail et carnets_liste en includes du site ; notes_du_carnet avec resume et boutons |
| `front/tests/test_corpus_phase_f.py` | 11 tests (URL, resume, ordre, epingle transferee, cible d'ecran, compteurs) |

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0044`
  (guide_de_redaction, appliquee sur dev).

---

## 2026-08-08 — Couche corpus, phase E : endpoints du carnet et du rangement

**Quoi / What :** la premiere couche HTTP de la couche corpus
(SPEC-corpus § 9) : `CarnetViewSet` (liste, detail, notes filtrees par
facettes, gestion des axes/categories, ordre manuel) et
`NoteCorpusViewSet` (ajouter a un carnet, retirer — sans jamais supprimer
la note —, categoriser par relation, epingler). Reponses HTML/HTMX
uniquement, `AllowAny` avec controle PAR OBJET.

**Pourquoi / Why :** les phases A-D ont pose la mecanique ; ces endpoints
la rendent actionnable. Les filtres § 8.2 : OU dans un axe, ET entre les
axes. Ranger exige la lecture de la note ET l'ecriture sur le carnet
cible (on ne range pas — donc on n'expose pas — ce qu'on ne peut pas lire).

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `front/views_corpus.py` | Les deux ViewSets + le filtre par facettes |
| `front/templates/front/corpus/` | 2 ecrans + 4 partials (bloc « Dans N carnets », notes filtrees, categories, erreurs) — mise en forme definitive en phase F contre l'etalon corpus.html |
| `front/tests/test_corpus_phase_e.py` | 21 tests : permissions par objet, anonyme sur public, ET/OU des facettes, rangement/retrait, categorie etrangere en 400, epinglage, reordonnancement |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/serializers.py` | + AjouterAUnCarnetSerializer, ReordonnerLeCarnetSerializer, GererCategoriesSerializer |
| `front/urls.py` | + routes `/carnets/` et `/notes/` |

### Relecture / Review
Relecture adverse + comparaison structurelle a l'etalon (agent Opus)
passees le 8 aout. 3 bloquants corriges, chacun avec son test :
- IDOR sur retirer_d_un_carnet (l'appartenance doit exister → 404, sinon
  l'endpoint servait d'oracle d'enumeration) ;
- le bloc « Dans N carnets » ne montre plus que les carnets que le
  DEMANDEUR peut lire (nommer le carnet prive d'un tiers etait une fuite) ;
- ?categorie=abc ne fait plus de 500 (ids numeriques seulement).
Egalement : versions non rangeables (404), reordonner en transaction +
bulk_update, les notes sans ordre manuel (0) trient APRES les ordonnees.
Le cahier des charges de la phase F (ecarts vs corpus.html + 7 arbitrages
spec/etalon) est dans PLAN/corpus-phase-f-cahier-des-charges.md.

### Question ouverte relevee / Open question raised
Le proprietaire d'une note ne peut pas la retirer d'un carnet ou il n'a
pas l'ecriture — alors qu'un tiers peut ranger sa note dans un carnet
public et la rendre publique. La spec § 9 ne tranche pas ; « ecriture sur
le carnet OU propriete de la note » serait defendable. A trancher.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-08 — Couche corpus, phase D : bascule des lecteurs vers la table de liaison

**Quoi / What :** la conversion EN UN SEUL LOT (SPEC-corpus § 4.3) de tous
les lecteurs et ecrivains de `Page.dossier` vers la table de liaison
`AppartenancePageDossier`. Une note rangee dans deux carnets apparait
desormais dans les deux, partout.

**Pourquoi / Why :** une conversion progressive etait incompatible avec la
regle « toute lecture passe par la table de liaison » — pendant la
transition, une note ajoutee a un second carnet n'y apparaissait pas.

### Le service de rangement (§ 4.3)
`core/services/corpus.py` : `ranger_une_note_dans_un_carnet` (appartenance +
FK « premier carnet », idempotent), `retirer_une_note_d_un_carnet`
(reaffectation de la FK a une appartenance restante, ou NULL),
`deplacer_une_note_vers_un_carnet` (semantique actuelle du classement).
La FK n'est plus ecrite QUE par ce service pendant la coexistence.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/views.py` | Creation de page et `classer_depuis_extension` via le service ; perimetre de dedup par les appartenances |
| `front/views.py` | `_verifier_acces_page` → `_utilisateur_a_acces_page` ; 13 appels `_est_proprietaire_dossier` → `_est_proprietaire_page` (fonction supprimee) ; controles d'ecriture → `_utilisateur_peut_ecrire_page` ; imports/audio ranges via le service ; deplacement drag-drop via le service ; suppression de dossier reaffecte les FK avant delete ; arbre precharge les appartenances (`to_attr`, zero N+1) |
| `front/templates/front/includes/_dossier_node.html` | Compteurs et liste des pages par les appartenances prechargees |
| `front/views_alignement.py` | Perimetre par les appartenances |
| `front/tasks.py` | Versions de synthese : appartenances repliquees depuis la racine (§ 11) ; notifications elargies aux proprietaires des carnets, dedoublonnees (`_destinataires_de_notification`) |
| `front/tests/test_corpus_phase_d.py` | 6 tests : note visible sous ses deux carnets, compteurs, assertNumQueries(12) sur l'arbre, dedup par liaison (cas que la FK ne voyait pas), notifications dedoublonnees |
| `front/tests/test_phases.py` | 7 setUp adaptes : l'appartenance accompagne la FK (prevu par la spec § 4.3) |
| `core/tests/test_corpus_rangement.py` | 11 tests du service (FK premier carnet, reaffectation, idempotence) |
| `core/tests/test_corpus_permissions.py` | + ecriture legacy des orphelines preservee (decision point 1) |

### Les 4 decisions prealables (relecture C)
1. Ecriture des orphelines owner=None : comportement actuel PRESERVE
   (tout authentifie), symetrique de la lecture legacy. Teste.
2. Proprietaire sans lecture : § 5.2 garde tel quel — les vues verifient
   l'acces avant la propriete, l'ordre des controles protege.
3. Dossiers legacy owner=None : 0 en dev (= copie de prod), risque vide.
4. assertNumQueries : pose sur l'arbre (12 requetes, independant du nombre
   de notes — l'ancien template faisait 5 COUNT par dossier).

### Relecture / Review
Relecture adverse passee (8 aout) : 2 bloquants corriges — les comptages
d'en-tete de l'arbre restaient sur la FK (incoherence avec les noeuds,
versions comptees, N+1 que le test assertNumQueries absorbait : recale de
12 a 9 requetes, desormais independant du nombre de dossiers) ; et un 500
sur import avec dossier_id perime (le service refuse None proprement, les
4 sites d'import laissent la page orpheline comme avant). Egalement :
FK des versions ecrite par le service seul, reaffectation des FK deplacee
dans un signal pre_delete (couvre l'admin et le shell, teste), message de
suppression honnete (orphelines vs restees ailleurs), bouton « Supprimer
cette version » aligne sur la regle de l'endpoint via le filtre
`est_moderable_par` (front/templatetags/corpus_permissions.py).

### Limites connues / Known limits
- Drag-drop de page : semantique mono-carnet conservee (la vue ne connait
  que la destination ; « sortir » retire du carnet FK, pas du carnet
  d'origine du geste). A reprendre avec l'UI multi-carnets (phase G).
- L'ordre des notes dans l'arbre suit desormais le tri des appartenances
  (epinglees, ordre manuel, plus recentes d'abord).
- Notifications elargies pour la synthese seulement (§ 11) ; analyse et
  transcription restent owner-only, comme avant.

### Migration
- **Migration necessaire / Migration required :** Non (le schema date de la
  phase A). `Page.dossier` reste en place — son retrait est la migration 3,
  apres recette.

---

## 2026-08-08 — Couche corpus, phase C : permissions par les carnets

**Quoi / What :** les trois fonctions de permission de la couche corpus
(SPEC-corpus § 5.2) : `_utilisateur_a_acces_page`,
`_utilisateur_peut_ecrire_page`, `_est_proprietaire_page`, plus le helper
`_dossiers_contenant_la_page` (contrat prefetch, § 5.3).

**Pourquoi / Why :** sous le N-N, « le dossier de la page » n'existe plus.
L'acces se derive des carnets (le plus permissif gagne), la propriete
s'ELARGIT (owner de la note OU owner d'un carnet la contenant) — le prof
garde la moderation sur les captures des eleves, l'eleve garde ses droits.
Le comportement legacy (note sans carnet sans owner → tout authentifie)
est preserve.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | + les 3 fonctions + helper ; `_est_proprietaire_dossier` marquee DEPRECIEE (bascule des appelants en phase D, en un seul lot) |
| `core/tests/test_corpus_permissions.py` | 17 tests : carnet le plus permissif, anonyme sur carnet public, legacy, cas-piege (owner sans acces : les carnets decident), partage direct et par groupe, superuser (lecture oui / ecriture non), moderation du prof, droits de l'auteur, lecture != ecriture, zero requete avec prefetch (chemins sans DossierPartage) |

### Relecture / Review
Relecture adverse passee (8 aout) : 1 bloquant corrige — le bypass
superuser en ECRITURE, absent de la spec et de l'existant, a ete retire
(seule la lecture a un bypass, prescrit). 4 points « a trancher avant la
phase D » consignes dans la fiche A TESTER (ecriture des orphelines,
proprietaire sans lecture, dossiers legacy owner=None — 0 en dev —,
assertNumQueries de la vue de liste).

### Migration
- **Migration necessaire / Migration required :** Non. Aucun appelant
  converti : les vues existantes lisent toujours `page.dossier` (phase D).

---

## 2026-08-08 — Couche corpus, phase B : validation des categories

**Quoi / What :** la validation « qui n'a pas le droit de manquer »
(SPEC-corpus § 3.4) : une categorie appliquee a une appartenance doit venir
du carnet (ou de la base) de cette appartenance.

**Pourquoi / Why :** sans elle, le vocabulaire d'un carnet fuit dans un
autre — exactement ce que la categorie portee par la relation existe pour
empecher. Deux etages : le serializer (erreur de formulaire propre) et les
signaux m2m_changed (filet de securite, meme un .add() en shell est refuse).

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `core/services/corpus.py` | Les deux validateurs (cote carnet, cote base) |
| `core/signals.py` | Les deux signaux m2m_changed, avec le kwarg `reverse` gere dans les deux sens (le cas que la v1.0 de la spec cassait) |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/apps.py` | `ready()` importe les signaux |
| `core/serializers.py` | + `CategoriserUneNoteSerializer` |
| `core/tests/test_corpus_modele.py` | + 14 tests de validation (sens direct, inverse — nominal ET refus —, .set(), cote base, serializer : etrangere, introuvable, liste vide) |

### Relecture / Review
Relecture adverse passee (8 aout) : pas de bloquant. Correctifs appliques —
tests nominaux de la branche reverse (le seul trou par lequel une regression
sur LE point v1.0 serait passee), garde de contexte du serializer,
`dispatch_uid` sur les signaux, docstring honnete sur la limite du through
(les ecritures directes sur la table de liaison ne declenchent aucun signal),
borne `max_length=100` sur la liste.

### Piege documente / Documented pitfall
Une ValidationError levee par le signal sort du bloc atomique interne du
`.add()` : dans un test (ou une vue sous transaction), les requetes
suivantes exigent un savepoint (`with transaction.atomic():` autour de
l'appel refuse). Les tests montrent le patron.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## 2026-08-08 — Couche corpus, phase A : modeles, migrations, role_special

**Quoi / What :** le socle de donnees de la couche corpus
(SPEC-corpus-base-carnet-note.md v1.1 § 3, § 4.2, § 6.3) : les modeles
`BaseDeConnaissances`, `AppartenancePageDossier`, `AppartenanceDossierBase`,
`ListeDeCategories`, `CategorieDossier`, `CategorieBase`, le champ
`Dossier.role_special`, et les migrations de schema + donnees.

**Pourquoi / Why :** une note doit pouvoir vivre dans plusieurs carnets sans
duplication, avec un classement propre a chaque carnet — la categorie est un
attribut de la RELATION note-carnet, pas de la note. Et les carnets
« magiques » (« A ranger », « Mes imports ») etaient retrouves par leur nom :
les renommer cassait la capture et l'import.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | + 6 modeles corpus, + `RoleSpecialDossier`, + `Dossier.role_special` avec contrainte `unicite_role_special_par_proprietaire` |
| `core/migrations/0040_...py` | Schema : les 6 modeles + role_special + contraintes |
| `core/migrations/0041_creer_les_appartenances_depuis_la_fk.py` | Donnees, REVERSIBLE : une appartenance par page ayant un dossier, `integree_le=page.created_at`, bilan chiffre + controle d'integrite qui leve si les comptes different |
| `core/migrations/0042_estampiller_les_dossiers_speciaux.py` | Donnees, REVERSIBLE : pose `role_special` sur les carnets historiques (plus ancien seulement en cas d'homonymes, jamais sans owner) |
| `core/views.py` | `_resoudre_dossier` : fallback retrouve par `role_special`, plus par nom |
| `front/views.py` | `_obtenir_ou_creer_dossier_imports` : idem |
| `core/migrations/0043_...py` | Contrainte role_special reprise avec `nulls_distinct=False` (les fourre-tout sans owner sont limites aussi — retour de relecture) |
| `core/tests/` | `tests.py` (vide) converti en paquet : `test_corpus_modele.py` (18 tests), `test_corpus_migration.py` (4 tests MigrationExecutor), `test_role_special.py` (8 tests) |

### Decisions / Decisions
- `Page.dossier` reste en place, intouchee : la FK porte le « premier carnet »
  pendant la coexistence. Son retrait est la migration 3 de la spec, apres
  recette. / The FK stays during coexistence.
- La question ouverte n°1 de la spec (pages sans dossier -> « A ranger » ?)
  est tranchee de facon conservatrice : on ne les touche pas. Le comportement
  d'acces legacy (tout authentifie si owner=None) sera preserve par la
  phase C (§ 5.2). Sur la base de dev : 1 seule page concernee.
- L'extension continue de filtrer par nom (`popup.js`), sans casser : les noms
  par defaut ne changent pas (spec § 6.3). Reserve : un carnet special
  renomme AVANT la migration n'est pas estampille — un doublon apparaitra
  a la capture suivante (aucun cas sur la base de dev, verifie).
- Relecture adverse passee (8 aout) : 3 correctifs appliques — idempotence
  de 0042 sur base partiellement estampillee, controle d'integrite de 0041
  compte les lignes creees (pas la table), `nulls_distinct=False` sur la
  contrainte role_special. Chaque correctif a son test.

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0040`, `0041`,
  `0042`, `0043`. Appliquees sur la base de dev : 537 pages avec dossier ->
  537 appartenances (COHERENT), 14 « Mes imports » estampilles.

---

## 2026-08-05 — Ingestion Docling, simplifications, bascule des pages existantes

**Quoi / What :** Docling installe et branche, deux simplifications du modele, et
une commande de bascule des pages du moteur ANCIEN vers le moteur ELEMENT.

### Ingestion Docling / Docling ingestion
`services/ingestion_docling.py` convertit un fichier en ElementDocument. Verifie
sur un markdown avec titres, liste et tableau : 9 elements, labels corrects
(`title`, `section_header`, `text`, `list_item`, `table`), chemins de section
hierarchiques.

Deux points traites que Docling ne fait pas seul :
- **Les tableaux sont serialises en markdown.** Un tableau Docling n'a pas
  d'attribut texte : son contenu est dans sa structure. Sans serialisation, il
  arriverait vide et tout son contenu serait perdu pour l'analyse.
- **Chaque boite PDF garde SON numero de page.** `page_no` est unique au niveau
  de la provenance, alors que les boites sont une liste : un paragraphe a cheval
  sur deux pages aurait vu ses boites de la page 2 dessinees sur la page 1.

Chaine complete verifiee avec un appel LLM reel : Docling -> 9 elements ->
1 chunk -> 4 extractions -> 14 portions, dont 2 couvrant plusieurs elements.

### Deux simplifications / Two simplifications
| Quoi / What | Pourquoi / Why |
|---|---|
| `ElementDocument.element_parent` supprime | Scission et fusion suppriment toujours leurs sources, et le `SET_NULL` vidait donc la reference a chaque fois. Un champ qui ne peut jamais rien indiquer invite a s'y fier a tort. La filiation vit dans `ElementOperation.donnees` |
| `EtatAncrage` passe de trois etats a deux | `EXACTE` et `RETROUVEE` se comportaient exactement pareil : ni le regime d'edition, ni l'affichage, ni le calcul d'etat ne les distinguaient. Fusionnes en `ANCREE` |

### Bascule des pages existantes / Migrating existing pages
`manage.py basculer_vers_le_moteur_element` decoupe `text_readability` en
elements et tente de re-ancrer les extractions en cherchant leur texte, avec la
regle habituelle : plusieurs occurrences, on ne devine pas.

Resultat sur le dev (538 pages, 29 921 extractions) : **13 174 elements crees,
8 585 ancres recuperees (28,7 %)**. Aucune extraction ni commentaire supprime :
celles qu'on ne retrouve pas restent en base, detachees.

### On traduit les anciens offsets, on ne cherche pas le texte
Les anciennes extractions portent `start_char` et `end_char` : des positions
dans `text_readability`, ecrites par l'alignement de LangExtract au moment de
l'analyse. **Ces positions sont fiables** — verifie sur echantillon : aucune
hors bornes, 5 % seulement a 0-0 (jamais alignees).

Comme les elements sont decoupes dans CE MEME texte, il suffit de noter ou
commence chaque paragraphe pour traduire un ancien offset en portions. C'est un
calcul d'intersection, exactement celui que `services/ancrage.py` fait deja pour
le nouveau moteur.

Trois versions successives de la commande, et ce que chacune a appris :

| Methode | Re-ancrage | Extractions commentees |
|---|---|---|
| Chercher `extraction_text`, element par element | 39,7 % | 51/115 |
| + insensible a la casse et a la typographie, sur le texte colle | 48,6 % | 66/115 |
| **Traduire `start_char`/`end_char`** | **99,7 %** | **113/115** |

Chercher le texte etait a la fois inutile et moins bon :
- ca rejetait des ancres correctes au motif que le texte apparaissait ailleurs
  dans la page (« ambigu »), alors que l'offset, lui, savait laquelle etait la
  bonne ;
- ca echouait sur les alignements partiels de LangExtract, ou `extraction_text`
  est plus long que ce qui a reellement ete trouve dans le document ;
- ca echouait sur les differences d'ecriture entre le texte rendu et le
  document (un `\n` devenu espace, une apostrophe courbe).

**Note** : une analyse intermediaire avait conclu que 73 % des extractions
etaient des reformulations et non des citations. C'etait faux, et c'etait un
artefact de la methode de mesure — une recherche de texte trop litterale, pas
un fait sur les donnees. `extraction_text` porte bien la citation.

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0039` et
  `hypostasis_extractor.0033` (suppression du champ, fusion des etats, avec
  conversion des donnees existantes).
- La commande de bascule, elle, se lance a la demande, et accepte `--a-blanc`
  pour voir ce qui se passerait sans rien ecrire.

---

## 2026-08-05 — Ancrage par element, phase D : pipeline d'analyse + garde d'edition

**Quoi / What :** `services/analyse_par_element.py` (chunks -> LangExtract ->
ancres) et `services/garde_edition.py` (interdire l'edition pendant une analyse).

**Pourquoi / Why :** c'est la piece qui relie tout le reste. Le chunking (phase C)
decoupe sur les frontieres d'elements, le LLM analyse chaque chunk seul,
l'intersection (phase B) traduit les positions rendues en portions d'ancrage.
Verifie contre Gemini 2.5 Flash : sur une liste a puces de trois elements, le
modele rend un span qui les traverse tous les trois, et le pipeline produit trois
portions ordonnees pointant chacune le bon texte.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/analyse_par_element.py` | Pipeline d'analyse du moteur ELEMENT |
| `hypostasis_extractor/services/garde_edition.py` | Refus d'editer pendant une analyse |
| `hypostasis_extractor/tests/test_analyse_par_element.py` | 19 tests, LLM simule |
| `hypostasis_extractor/tests/test_analyse_llm_reel.py` | 3 tests d'integration, appels LLM reels |
| `hypostasis_extractor/tests/test_garde_edition.py` | 24 tests |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | `"updated_at"` ajoute aux `update_fields` des jobs (battement de coeur pour la garde d'edition) |
| `front/views.py` | `_refuser_si_une_analyse_tourne()` + garde sur `renommer_locuteur`, `editer_bloc`, `supprimer_bloc` |
| `services/reconciliation.py`, `moteur_structure.py`, `masquage.py`, `reingestion.py` | Appel de la garde en tete de chaque operation d'edition |

### Deux decisions du proprietaire / Two owner decisions
1. **Les gros elements partent entiers**, sans decoupage. `max_char_buffer` est
   calcule plus grand que le chunk pour que LangExtract le recoive tel quel.
   A noter : ca ne protege pas les positions (LangExtract les re-base de toute
   facon), ca garantit que le modele lit chaque element ENTIER, dans son
   contexte.
2. **L'edition est bloquee pendant une analyse.** Un delai de grace de 90 minutes
   empeche qu'un worker Celery interrompu condamne une page pour toujours — cas
   documente dans le CHANGELOG du 19 juin 2026.

### Defauts corriges apres relecture adverse / Fixed after adversarial review
| Defaut / Defect | Correction |
|---|---|
| `lx.extract` telecharge le texte s'il ressemble a une URL (`fetch_urls=True` par defaut) : un element qui est un lien nu aurait fait analyser la page distante, avec des ancres fausses et une requete sortante pilotee par le document ingere | `fetch_urls=False` |
| Une analyse dont TOUS les chunks echouent finissait `COMPLETED`, indiscernable d'une page sans rien a extraire | Passage en `ERROR`, et bilan persiste dans `raw_result` |
| Une extraction incoherente (span a l'envers) faisait tomber toute l'analyse | Attrapee par extraction, comptee dans `extractions_refusees` |
| Relancer un job dupliquait toutes ses extractions | Purge des entites du job avant analyse |
| Un JSON tronque par `max_output_tokens` perdait le chunk entier | `resolver_params={"suppress_parse_errors": True}` |
| `updated_at` n'etait jamais rafraichi : le delai de grace mesurait l'age depuis la creation, pas la vie du job | Battement de coeur dans `front/tasks.py`, et la garde regarde les deux dates |
| La garde ne protegeait que la couche elements, qu'aucun code n'appelle encore, alors que les vraies editions passent par `front/views.py` | Garde ajoutee sur les trois vues d'edition |

### Tests avec appels LLM reels / Real LLM tests
Ils coutent de l'argent et dependent de ce que le modele repond. Double verrou :
le tag `llm_reel` **et** la variable `TESTS_LLM_REELS`. Django n'excluant pas les
tags par defaut, le tag seul ne protegerait pas.

```bash
docker exec -e TESTS_LLM_REELS=1 hypostasia_dev_web \
    uv run python manage.py test hypostasis_extractor --tag=llm_reel
```

### Migration
- **Migration necessaire / Migration required :** Non.

### Ce qui reste avant utilisation / Remaining before use
Le pipeline n'est appele par aucune tache Celery ni vue. Il manque : la tache
Celery (avec `_check_ia_active`, notifications, progression), le bouton dans
l'interface, et le compteur de tokens que la spec section 4.2 declare necessaire.

---

## 2026-08-05 — Ancrage par element, phase G : masquage et re-ingestion

**Quoi / What :** `services/masquage.py` (masquer, demasquer) et
`services/reingestion.py` (reconcilier les elements par empreinte).

**Pourquoi / Why :** deux besoins distincts.
- **Masquer** : la transcription audio invente du contenu — un bruit de fond
  transcrit en mots, une phrase repetee. Ce n'est ni une coquille a corriger
  (il n'y a rien a corriger VERS) ni une note d'incertitude. L'element sort du
  contenu utile sans etre supprime, et l'operation est reversible.
- **Re-ingerer** : un pad de 200 comptes-rendus grossit d'un compte-rendu par
  semaine. Il faut re-analyser sans repayer 200 appels au LLM ni perdre les
  debats attaches aux 199 autres. Les elements sont reconnus par empreinte de
  contenu, jamais par position.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/masquage.py` | Masquer, demasquer, detacher les portions |
| `hypostasis_extractor/services/reingestion.py` | Reconciliation des elements par empreinte |
| `hypostasis_extractor/tests/test_masquage_et_reingestion.py` | 26 tests |

### Ecarts avec la spec, et pourquoi / Deviations from the spec
| Ou / Where | Ecart / Deviation | Raison / Reason |
|---|---|---|
| 5.4 | Le demasquage ne reutilise pas la reconciliation | Celle-ci repositionne apres un CHANGEMENT de texte et rend la main quand le texte est inchange — exactement le cas du demasquage. Elle exclut de plus les portions detachees, a raison |
| 5.4 | Le journal note un hash du texte BRUT, pas l'empreinte normalisee | L'empreinte ecrase les espaces et la casse. Corriger une double espace pendant un masquage decale tous les offsets qui suivent sans changer l'empreinte d'un iota : les portions seraient rattachees a des positions fausses |
| 5.4 | Le journal note les identifiants des portions detachees | Un element peut porter des portions detachees AVANT le masquage, par une correction anterieure. Les rattacher au demasquage les ferait pointer n'importe quoi. Seules celles que ce masquage a detachees reviennent |
| 5.3 | Les elements deja masques sont apparies, pas exclus | En les excluant, un element masque dont le texte reste dans la source serait recree en doublon a chaque re-ingestion, masque a son tour, exclu, recree... Un pad re-ingere cinquante fois accumulerait cinquante copies du meme bruit |
| 5.3 | Les empreintes en double sont signalees des DEUX cotes | Ne regarder que l'ancien document laisse passer le cas le plus probable : un intitule repete qui apparait une seconde fois dans le NOUVEAU contenu |
| 5.3 | Le masquage par re-ingestion passe par `masquer_un_element` | Un masquage ecrit a la main ne serait ni journalise ni recuperable : l'element ne pourrait jamais retrouver ses ancres, meme a texte strictement identique |
| 5.3 | Numerotation en deux temps (plage temporaire puis renumerotation) | Un element masque restant a l'ordre 0 entre en collision definitive avec un nouvel element cree a l'ordre 0. Ce conflit-la n'est pas transitoire, donc la contrainte differee le refuse a juste titre |
| 5.2 | La fusion refuse un element masque avec un visible | Le resultat ne pourrait etre ni l'un ni l'autre : visible, il renverrait au LLM le bruit qu'un humain avait retire ; masque, il ferait disparaitre du contenu utile |

### Migration
- **Migration necessaire / Migration required :** Non — aucun changement de schema.

---

## 2026-08-05 — Ancrage par element, phase F : moteur scission / fusion

**Quoi / What :** `services/moteur_structure.py` — couper un element en deux,
recoller deux elements adjacents, en redistribuant les portions d'ancrage.
Plus deux changements de schema que ces operations rendent necessaires.

**Pourquoi / Why :** une transcription audio colle deux tours de parole en un
seul element, ou attribue le mauvais locuteur au milieu d'un segment. Sans
scission ni fusion, la seule facon de corriger serait de tout re-analyser et de
perdre le debat attache. « Recoller un tour de parole scinde » est l'operation
numero un sur une vraie diarisation.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/moteur_structure.py` | Scission, fusion, coalescence, renumerotation |
| `hypostasis_extractor/tests/test_moteur_structure.py` | 41 tests |

### Changement de schema 1 : contraintes d'unicite DEFERRABLE
Les contraintes `unicite_ordre_dans_la_page` et `unicite_ordre_dans_l_extraction`
sont desormais verifiees au COMMIT, plus a chaque ligne ecrite.

**Raison :** le pseudo-code de la spec section 5.1 est incodable autrement. Il
cree le premier morceau avec l'`ordre` de l'element d'origine, qui existe encore
a cet instant — `IntegrityError` immediate, verifiee empiriquement. Meme
probleme pour le decalage des `ordre_dans_extraction` : decaler des numeros
de +1 fait forcement se telescoper deux lignes en chemin.

**Consequences a connaitre :**
- Une violation d'unicite sur ces deux tables ne se manifeste plus au `save()`
  mais au commit, donc hors de tout `try/except` place autour de l'ecriture.
- `bulk_create(ignore_conflicts=True)` et tout `ON CONFLICT` sont desormais
  refuses par PostgreSQL sur ces deux tables : une contrainte deferrable ne peut
  pas servir d'arbitre a un upsert.

### Changement de schema 2 : le journal des operations tient a la Page
`ElementOperation.element` passe de `CASCADE` a `SET_NULL`, et le modele gagne
`page` (FK obligatoire), `identifiant_stable_element` et `donnees`.

**Raison :** scission et fusion suppriment toujours leurs elements sources. Avec
une CASCADE sur l'element, chaque operation effacait l'historique de la
precedente — scinder puis refusionner ne laissait aucune trace de la scission.
Le journal etait decoratif, et l'invariant « rien ne disparait en silence » faux
la ou il compte le plus.

### Defauts de la spec corriges au passage / Spec defects fixed
| Section | Defaut / Defect |
|---|---|
| 5.1 | Le pseudo-code viole la contrainte d'unicite des la premiere ligne ; son `transaction.atomic()` arrive apres les `create` |
| 5.2 | La fusion promeut toutes les portions en `RETROUVEE`, y compris celles qui etaient `DETACHEE` — une portion detachee ressuscitait sur des offsets jamais valides |
| 5.2 | La coalescence recollait deux portions distantes de la longueur du separateur, ou qu'elles soient. Deux portions separees par deux caracteres de vrai texte etaient recollees en avalant ce texte. On ne recolle plus qu'a la couture |
| 5.2 | `_fusionner_les_provenances` : les boites PDF du second element heritaient du `page_no` du premier, donc auraient ete dessinees sur la mauvaise page. Chaque boite porte desormais sa page |

### Migration
- **Migration necessaire / Migration required :** Oui
- `core.0037` (contrainte deferrable), `hypostasis_extractor.0032` (idem),
  `core.0038` (journal rattache a la page, ecrite a la main car la table est
  vide et le champ `page` non-nullable).
- **Sans effet sur les donnees existantes** : les trois tables concernees ne
  sont alimentees par aucun pipeline a ce stade.

---

## 2026-08-05 — Ancrage par element, phases B, C et E : intersection, chunking, reconciliation

**Quoi / What :** les trois algorithmes du moteur ELEMENT qui ne dependent
d'aucune decision d'interface.
- **Phase B** — `services/ancrage.py` : transforme un span rendu par LangExtract
  (des offsets dans le texte d'un chunk) en portions d'ancrage, une par element
  traverse.
- **Phase C** — `services/chunking.py` : regroupe les elements en chunks sans
  jamais couper un element en deux.
- **Phase E** — `services/reconciliation.py` : repositionne les portions apres
  une correction de texte, et serialise les corrections concurrentes.

**Pourquoi / Why :** ce sont les trois endroits ou une ancre peut devenir fausse.
Un chunk qui coupe un element fait lire une demi-phrase au LLM ; un span mal
traduit ancre au mauvais endroit ; une correction de texte fait glisser toutes
les positions. Chacun des trois refuse de deviner : quand la position n'est pas
certaine, la portion est marquee `DETACHEE` plutot que placee au hasard.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/ancrage.py` | Decoupage d'un span en portions + table des offsets |
| `hypostasis_extractor/services/chunking.py` | Construction des chunks alignes sur les elements |
| `hypostasis_extractor/services/reconciliation.py` | Repositionnement des portions + verrou de concurrence |
| `hypostasis_extractor/tests/test_chunking_par_element.py` | 23 tests |
| `hypostasis_extractor/tests/test_reconciliation.py` | 23 tests |

### Fichiers deplaces / Moved files
| Avant / Before | Apres / After | Raison / Reason |
|---|---|---|
| `hypostasis_extractor/services.py` | `hypostasis_extractor/services/__init__.py` | La spec impose un paquet `services/`. Les imports existants restent valides ; les imports relatifs internes sont passes de `from .models` a `from ..models` |
| `hypostasis_extractor/tests.py` | `hypostasis_extractor/tests/test_modeles_extraction.py` | Un module et un paquet de meme nom empechaient `manage.py test` de decouvrir les tests |

### Ecarts avec la spec, et pourquoi / Deviations from the spec
| Ou / Where | Ecart / Deviation | Raison / Reason |
|---|---|---|
| section 2.3 | Parametre `decalages_dans_l_element` ajoute | La table d'offsets de la spec dit ou un morceau d'element est DANS LE CHUNK, jamais ou il est DANS L'ELEMENT. Sans cette information, une portion d'un element trop gros serait ancree a 0 |
| section 2.3 | Un element absent de la table leve une erreur au lieu d'etre saute | Un saut silencieux produit une ancre incomplete que rien en aval ne detecte : la portion du milieu disparait et la numerotation se resserre |
| section 4.1 | Taille calculee par somme des longueurs, pas par `position_debut/fin_dans_page` | Ces attributs n'existent pas sur `ElementDocument`. La somme mesure en plus exactement ce que le budget veut borner : le texte reellement envoye au LLM |
| section 4.1 | Cle `offsets` ajoutee a chaque chunk | La section 2.3 dit reutiliser « la meme table que celle utilisee pour construire le chunk » — table que le chunker de la spec ne produisait pas |
| section 4.1 | Un element plus gros que le budget part entier | La regle 1 est declaree obligatoire. Consequence : un chunk ne contient jamais une sous-chaine d'element, contrairement a ce que la section 2.3 envisage |
| section 6 | `reconcilier_les_portions_de_l_element` ecrit aussi le texte | La spec appelle `texte_de_la_portion_avant_edition()`, methode inexistante, tout en ayant retire `ancien_texte`. Les deux sont inconciliables |
| section 6 | Les portions des extractions masquees sont repositionnees | Les ignorer laisserait des offsets perimes qui ressortiraient faux au demasquage |
| section 6 | Les portions deja `DETACHEE` sont exclues | Leurs offsets ne veulent plus rien dire : les reutiliser pouvait faire repasser une portion `EXACTE` sur un passage sans rapport |

### Migration
- **Migration necessaire / Migration required :** Non — aucun changement de schema.

---

## 2026-08-05 — Ancrage par element, phase A : modeles et signal d'etat

**Quoi / What :** ajout du socle de donnees du moteur ELEMENT — `ElementDocument`,
`AncrageExtraction` (ancre multi-elements), `ElementOperation`, le champ
`SourceLink.ancrage_source`, et le signal `recalculer_etat_de_l_element`.
Implemente la phase A de `SPEC-ancrage-par-element-v2.md` (section 11).

**Pourquoi / Why :** l'ancrage actuel se fait par offsets de caracteres dans un
texte plat. Des qu'un texte est corrige, les positions glissent et le lien avec
le passage source est perdu. Le nouveau moteur ancre dans un element de document
identifie par un UUID stable, via une table de liaison ordonnee qui permet a une
extraction de couvrir plusieurs elements — mesure : une extraction d'une phrase
enjambe deja deux elements dans 7,5 % des cas, une extraction de deux phrases
dans 76 % des cas.

**Etat / Status :** socle de donnees uniquement. Aucun pipeline ne cree encore
d'element : le moteur d'intersection (phase B), le chunking (phase C) et
l'ingestion (phase D) restent a ecrire. Le nouveau moteur n'est donc lu par
aucun code existant.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | + `empreinte_du_texte()`, `EtatElement`, `ElementDocument`, `TypeOperationElement`, `ElementOperation` ; + champ `SourceLink.ancrage_source` ; imports `hashlib`, `re`, `uuid` |
| `hypostasis_extractor/models.py` | + `EtatAncrage`, `AncrageExtraction` (table de liaison M2M ordonnee) |
| `hypostasis_extractor/signals.py` | + `recalculer_etat_de_l_element()` et ses trois recepteurs (ancrage, commentaire, masquage d'extraction) |
| `hypostasis_extractor/tests/` | Nouveau package + `test_ancrage_m2m.py` (37 tests) |
| `core/migrations/0035_elementdocument_elementoperation.py` | Creation des modeles |
| `core/migrations/0036_sourcelink_ancrage_source_and_more.py` | FK croisees + contrainte d'unicite |
| `hypostasis_extractor/migrations/0031_ancrageextraction.py` | Creation de la table de liaison |

### Coexistence des deux moteurs / Both engines coexist
Conformement a la section 9 de la spec, **aucun ancien champ n'est retire ni
modifie**. `ExtractedEntity.start_char` / `end_char` et
`SourceLink.start_char_source` / `end_char_source` restent en place et
fonctionnent comme avant. Les trois migrations sont purement additives
(`CreateModel`, `AddField`, `AddConstraint`) — aucun `RemoveField`, aucun
`AlterField`, aucun `RunPython`. Trois tests de non-regression verifient
explicitement que les anciens champs existent toujours.

### Regle de calcul de l'etat / State computation rule
Une portion d'ancrage ne compte dans l'etat d'un element que si son extraction
n'est **pas masquee** et que son ancrage n'est **pas detache**. Consequence
voulue : un element dont toutes les portions sont detachees redevient `LIBRE`,
donc librement editable. Il n'y a pas d'etat `SCELLE` — le scellement a ete
abandonne (YAGNI).

### Migration
- **Migration necessaire / Migration required :** Oui
- `core.0035`, `hypostasis_extractor.0031`, `core.0036` — dans cet ordre, gere
  automatiquement par les dependances.
- Commande : `docker exec hypostasia_web uv run python manage.py migrate`
- **Sans effet sur les donnees existantes** : uniquement des tables nouvelles et
  une colonne nullable sur `SourceLink`.

---

## 2026-06-19 — Fix : taches en erreur bloquees en « En cours » (statut "error" vs "failed")

**Quoi / What :** correction d'une regression du widget « taches » : un job
d'analyse / synthese / transcription termine en erreur s'affichait indefiniment
« En cours… » (spinner) dans le dropdown et ne passait jamais le bouton en rouge.
Cause : le modele ecrit `status="error"` (`ExtractionJobStatus.ERROR`, coherent avec
`PageStatus` et `TranscriptionJobStatus`), mais `views_taches.py` et
`taches_dropdown.html` testaient `"failed"` — une valeur qui n'existe dans aucun enum.

**Pourquoi / Why :** introduit lors de la session A.8 (simplification des statuts).
Le vocabulaire du front a diverge de celui des modeles. `"failed"` n'etant jamais egal
a `"error"`, les jobs en erreur n'etaient ni comptes (badge non lu), ni detectes comme
erreur (etat rouge prioritaire), et tombaient dans le `else` du template → spinner
« En cours » permanent. Les erreurs ne remontaient donc jamais a l'utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views_taches.py` | Comparaisons de statut `"failed"` → `"error"` (compteurs non lues, etat erreur, marquer-toutes-lues) |
| `front/templates/front/includes/taches_dropdown.html` | `{% elif tache.status == "failed" %}` → `"error"` (icone + libelle Erreur) |
| `front/tasks.py` | Libelle WebSocket `notifier_tache_terminee(status="failed")` → `"error"` + docstring |
| `front/tests/test_phases.py` | `test_bouton_erreur_si_failed_non_lu` → `_si_error_non_lu`, `status="error"` |

### Migration
- **Migration necessaire / Migration required :** Non
- **Nettoyage des jobs deja bloques :** repasser en `"error"` les jobs orphelins restes
  `pending` / `processing` (worker interrompu) via `manage.py shell`
  (`ExtractionJob` + `TranscriptionJob`).

---

## 2026-05-02 — Session A.8 : Statuts binaires + drawer-only + FALC additionnel

**Quoi / What :** simplification massive de la couche debat — `ExtractedEntity.statut_debat`
passe de 6 valeurs (nouveau, discutable, discute, consensuel, controverse, non_pertinent)
a **2 valeurs binaires** (`nouveau`, `commente`) auto-derivees par signal Django depuis
l'existence de commentaires. Refonte UX en **drawer-only** : suppression de la carte
inline (fusion vers `_card_body.html` unique). Retrait additionnel FALC : edition
d'extraction, edition/suppression de commentaire, onglet "Tous les commentaires",
bouton "Replier la carte", tri "Statut de debat".

**Pourquoi / Why :** suite logique du brainstorming YAGNI 2026-05-01 et de la session
A.7. Les 6 statuts manuels (consensuel/controverse/etc.) demandaient un effort cognitif
non valide par l'usage : sur l'instance live, la majorite des entites restaient en
"nouveau" et la curation manuelle etait quasi-inexistante. La logique de gating
"synthese bloquee si <80% consensus" empechait de lancer des syntheses dont l'utilisateur
voulait quand meme tester la qualite. La carte inline + drawer = 2 templates a maintenir
pour le meme objet ; la fusion supprime la divergence. Les autres retraits FALC (edition
d'extraction, edition/suppression de commentaire, onglet doublon, replier) ciblent des
features a usage faible/nul.

### Changements principaux / Main changes

1. **Signal Django auto-update** : nouveau `hypostasis_extractor/signals.py`. Le statut
   `statut_debat` est auto-derive de l'existence de commentaires (post_save +
   post_delete sur `CommentaireExtraction`). Plus de set manuel.
2. **Enum reduit** : `StatutDebat` passe de 6 valeurs a 2 (`NOUVEAU`, `COMMENTE`).
   Migration data + AlterField.
3. **Fusion `non_pertinent` -> `masquee`** : le statut `non_pertinent` disparait, ses
   instances en DB sont fusionnees dans `masquee=True`. Le champ `masquee` devient
   independant du statut.
4. **Action `changer_statut` retiree** : 4 boutons UI supprimes de la carte.
5. **Refonte drawer-only** : suppression de `carte_inline.html` + JS de creation
   dynamique de carte sous les paragraphes. Clic pastille -> ouvre drawer + scroll
   vers la carte concernee. **Le drawer est l'unique endroit pour voir et commenter
   une extraction.**
6. **`_card_body.html` unique** : retrait du parametre `mode`, partial unique pour
   le drawer (et le bottom_sheet mobile). Le formulaire commenter cible
   `closest .extraction-content` avec swap `outerHTML` -> les commentaires apparaissent
   immediatement sans toast ni rechargement.
7. **Pastille triangle orange** : le statut `commente` s'affiche en triangle orange
   (clip-path CSS) au lieu d'un cercle vert. Plus distinctif visuellement et coherent
   avec le code couleur "discussion en cours".
8. **Layout commentaires Facebook-like** : pseudo en haut (gras), commentaire en
   dessous. Plus lisible que l'ancien layout horizontal avec typo Srisakdi.
9. **Dashboard consensus simplifie** : graphique 6 segments remplace par barre binaire
   `commentees / total`. Le bouton "Lancer la synthese" reste present (sans gate).
10. **`_calculer_consensus`** simplifie de ~30 a ~10 lignes.
11. **Action `vue_commentaires`** retiree + template + onglet "Tous les commentaires"
    (redondant avec le drawer).
12. **Actions `modifier_commentaire` + `supprimer_commentaire`** retirees + serializers.
13. **YAGNI edition d'extraction** : actions `editer` + `modifier`, helper
    `_peut_editer_extraction`, bouton "Modifier" et modale d'edition retires entierement.
14. **Tri "Statut de debat"** retire du selecteur du drawer (plus de sens binaire).
15. **Bouton "Replier la carte"** (▴) retire (drawer a son ✕).
16. **Bouton "tâches" (A.6)** : distingue maintenant `analyse` vs `synthese` dans le
    dropdown, lien "Voir le resultat" pointe vers la page V2/V3 creee pour les syntheses.
17. **CSS** : 6 paires de variables `--statut-*` reduites a 2.
18. **Marginalia.js** : matrice 6 statuts -> 2 (couleur orange `#E69F00` pour
    `commente`).
19. **Templates aide** (`aide_desktop`, `aide_mobile`, `onboarding_vide`) simplifies :
    section explicative des 6 statuts -> bloc binaire + mention "le statut est automatique".
20. **Fixtures** (`charger_fixtures_demo.py`) : valeurs riches `statut_debat` retirees
    -> `nouveau` (le signal complete a `commente` quand les commentaires sont crees).

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/0029_a8_recalcul_statuts_fusion_non_pertinent.py` :
  RunPython qui fusionne `non_pertinent` -> `masquee=True` puis recalcule tous les
  statuts depuis les commentaires (option A : recalcul pur).
- `hypostasis_extractor/migrations/0030_a8_alter_statut_debat_choices.py` : AlterField
  qui reduit l'enum a 2 valeurs.

### Solde net / Net balance

- 8 phases (1-8) + 4-bis : **~-2950 lignes nettes** sur cette session
- Cumul cleanup A.1 -> A.8 : ~15500 lignes net retirees en 8 sessions

### Verification anti-regression / Anti-regression check

- Snapshot tests pre-A.8 : 743 tests / 723 OK / 0 fail / 20 errors préexistantes
- Snapshot tests post-A.8 : **690 tests / 658 OK / 0 fail** / 20 errors préexistantes (mêmes E2E + test_analysis)
- 53 tests obsoletes retires/adaptes, **aucune regression introduite**
- Test UI Chrome : page lecture, drawer Analyses (avec hypostases visibles, commentaires
  inline, bouton commenter), creation/suppression commentaire (signal -> statut auto),
  dashboard consensus avec bouton synthese, mobile (bottom_sheet) — tous OK.

### Hors perimetre / Out of scope (conserve intact)

- Synthese deliberative + analyseurs synthetiseurs
- Versionning de pages (`parent_page`, `versions_enfants`)
- Bouton "Historique" + "Comparer V1↔V2" + tabs versions
- Suppression d'extraction (`btn-supprimer-extraction`) + masquer/restaurer
- Filtre contributeurs avec dimming
- Bouton "tâches" A.6 + signal WebSocket + dropdown + marquer-lue
- Systeme de commentaires (`CommentaireExtraction`)

### References / References

- Spec A.8 : `PLAN/A.8-statuts-binaires-fusion-templates-spec.md`
- Plan d'execution : `PLAN/A.8-statuts-binaires-fusion-templates-plan.md`
- Spec maître YAGNI : `PLAN/REVUE_YAGNI_2026-05-01.md`

---

## 2026-05-02 — Session A.7 : Retrait Reformulation IA + Restitution IA + Restitution manuelle

**Quoi / What :** retrait integral des fonctionnalites Reformulation IA, Restitution IA
et Restitution manuelle (code mort en pratique : 0/134 extractions utilisaient ces
champs en DB, sections invisibles dans l'UI). Conservation totale de la Synthese
(seul mecanisme IA reellement utilise) et du versionning de pages (utilise par la
Synthese).

**Pourquoi / Why :** suite logique du brainstorming YAGNI 2026-05-01 (cf.
`PLAN/REVUE_YAGNI_2026-05-01.md`) et de la refonte WebSocket A.6. Audit DB +
Chrome a confirme l'absence d'usage : aucune entite avec `texte_reformule`,
aucune avec `texte_restitution_ia`, aucune `restitution_page` non-null sur les
134 extractions de l'instance live. Aucun bouton Reformuler/Restituer/Pre-remplir-IA
visible dans l'UI courante (sidebar droite cachee + sections conditionnees a des
champs DB vides). Le code mort cumule represente une dette technique non
justifiee qui complique la refonte RAG a venir.

### Changements principaux / Main changes

1. **2 taches Celery supprimees / 2 Celery tasks removed** : `reformuler_entite_task`
   (~110 lignes), `restituer_debat_task` (~115 lignes) dans `front/tasks.py`.
2. **9 actions ViewSet retirees / 9 ViewSet actions removed** : 3 actions
   reformulation IA (`choisir_reformulateur`, `previsualiser_reformulation`,
   `reformuler`), 4 actions restitution IA (`choisir_restituteur`,
   `previsualiser_restitution`, `generer_restitution`, `restitution_ia_status`),
   1 action restitution manuelle (`creer_restitution`), 1 action `fil_discussion`
   + helper `_re_rendre_fil_discussion`.
3. **3 serializers retires / 3 serializers removed** : `RunReformulationSerializer`,
   `RunRestitutionSerializer`, `RestitutionDebatSerializer`.
4. **7 templates supprimes / 7 templates deleted** : `reformulation_en_cours.html`,
   `choisir_reformulateur.html`, `confirmation_reformulation.html`,
   `restitution_ia_en_cours.html`, `choisir_restituteur.html`,
   `confirmation_restitution.html`, `fil_discussion.html`.
5. **13 champs DB retires / 13 DB fields removed** via migration consolidee :
   - `ExtractedEntity` : `texte_reformule`, `reformule_par`, `reformulation_en_cours`,
     `reformulation_lancee_a`, `reformulation_erreur`, `restitution_page`,
     `restitution_texte`, `restitution_date`, `restitution_ia_en_cours`,
     `restitution_ia_lancee_a`, `restitution_ia_erreur`, `texte_restitution_ia`
   - `ExtractionJob` : `est_reformulation`
6. **Enum `TypeAnalyseur` reduit de 4 a 2 valeurs** : suppression de `REFORMULER`
   et `RESTITUER`. Reste `ANALYSER` + `SYNTHETISER`.
7. **Modele vestige `core.Reformulation` supprime** : zero usage en code et zero
   ligne en DB. Heritage d'une architecture TextBlock-based abandonnee.
8. **Related_name renomme** : `Page.parent_page.related_name` passe de `restitutions`
   a `versions_enfants` pour coherence semantique (la Synthese aussi cree des
   versions enfants).
9. **Templates branches nettoyes** : sections `{% if reformulation_* %}` /
   `{% if restitution_* %}` retirees de `vue_commentaires.html` ; bouton hover
   `btn-commenter-extraction` (qui pointait vers `fil_discussion`) retire de
   `extraction_results.html` et `bottom_sheet_extraction.html` ; logique de timeout
   reset des reformulations bloquees (~50 lignes) retiree de l'action
   `vue_commentaires` ; contexte `analyseurs_reformuler_existent` /
   `analyseurs_restituer_existent` retire des actions ViewSet.
10. **JS nettoye / JS cleaned** : handler clic `.restitution-ancre` retire de
    `hypostasia.js` (pastille violette inline orpheline) ; options select
    `<option value="reformuler">` et `<option value="restituer">` retirees du
    SwAlert d'edition d'analyseur.
11. **Templates de l'editeur d'analyseur mis a jour** : `analyseur_editor.html`
    (2 options `<option>` retirees), `analyseur_item.html` (couleur badge
    `bg-amber-400` pour reformuler retiree), `modale_prompt_readonly.html` (2
    branches `{% elif %}` retirees + ajout d'une branche `synthetiser` manquante).
12. **Vestige template** : `core/templates/core/includes/sidebar_items_partial.html`
    referencait `block.reformulations.all` (related_name du modele supprime). Aurait
    plante au prochain rendu de la sidebar — VIEW 3 (`reformulations`), VIEW 7
    (`edit_reformulations`) et bouton toolbar « Re-ecriture » retires (~75 lignes).
13. **3 fichiers fixtures JSON nettoyes** des 13 champs DB retires :
    `exemple_deliberation.json`, `demo_alignement_versions.json`, `demo_completes.json`.
14. **Fixture analyseur "FALC" (type reformuler) retiree** de `charger_fixtures_demo.py`.
15. **Tests morts retires** : 1 classe `Phase24IntegrationReformulationMockTest` +
    4 methodes individuelles dans test_phases.py + adaptation de 3 methodes de tests
    survivants (`Phase04ModifierCommentaireTest`, `Phase04SupprimerCommentaireTest`,
    `Phase24ResolveModelParamsAnthropicTest`) qui referençaient des chaines obsoletes.

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/0028_a7_retrait_reformulation_restitution_fields.py` :
  13 RemoveField + 1 AlterField (TypeAnalyseur).
- `core/migrations/0033_a7_retrait_modele_reformulation.py` : 1 DeleteModel.
- `core/migrations/0034_a7_renommer_related_name_versions_enfants.py` : 1 AlterField
  (related_name).

### Solde net / Net balance

- 28 fichiers modifies, 7 templates supprimes, 3 nouvelles migrations
- **+304 / −4794 = −4490 lignes nettes**
- Cumul cleanup A.1 → A.7 : ~12900 lignes net retirees en 7 sessions

### Verification anti-regression / Anti-regression check

- Snapshot tests pre-A.7 : 748 tests, 728 OK, 0 fail, 20 errors (preexistantes E2E
  playwright + script orphelin)
- Snapshot tests post-A.7 : **743 tests, 723 OK, 0 fail, 20 errors** (memes 20
  preexistantes — zero regression introduite)
- `manage.py check` : System check identified no issues (0 silenced)
- Test UI Chrome : page `/lire/4/` se charge proprement (33 cartes inline + 59
  pastilles + onglets V1/V2/V3/V4 + Synthese deliberative). Endpoint
  `/extractions/vue_commentaires/?page_id=4` rend 77 KB sans aucune ref obsolete.
  Aucun lien hx-get/hx-post avec URL obsolete dans le DOM.

### Hors perimetre / Out of scope (conserve intact)

- Tache Celery `synthetiser_page_task` et helper `_construire_prompt_synthese`
- Type analyseur `SYNTHETISER` + 3 analyseurs synthetiseurs en fixture
  (Charte, Mathemagique, Synthese deliberative)
- Versionning Page (`parent_page`, `version_number`, `version_label`)
- Carte inline `carte_inline.html` + bouton "Commenter" inline (pure JS local)
- Systeme de commentaires (`CommentaireExtraction`) + statuts de debat +
  action `changer_statut`
- Helper `core/llm_providers.py:appeler_llm` (utilise par la Synthese)

### References / References

- Plan d'execution : `PLAN/A.7-retrait-reformulation-restitution.md`
- Spec maitre : `PLAN/REVUE_YAGNI_2026-05-01.md`
- Sessions precedentes A.1-A.6 : retrait Explorer / Heatmap / Mode focus /
  Stripe / Bibliotheque analyseurs / refonte WebSocket

---

## 2026-04-29 — PHASE-29 : Synthese deliberative dans le drawer + bool est_par_defaut + fix WebSocket OOB + audit HTMX (alpha:0.3.1)

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

---

## 2026-03-17 — PHASE-26c : Refactoring statuts de debat (6 statuts + ownership)

**Quoi / What:** Refactoring du systeme de statuts de debat : passage de 4 a 6 statuts, ajout du controle d'ownership, suppression du double badge, integration de "masquer" dans le cycle deliberatif.

**Pourquoi / Why:** 3 problemes UX identifies : toutes les extractions demarraient en rouge (alarmant), n'importe quel user pouvait changer le statut, et "masquer" etait deconnecte du cycle deliberatif.

### Changements principaux / Main changes

1. **6 statuts** : nouveau (gris), discutable (orange), discute (ambre), consensuel (vert), controverse (rouge), non_pertinent (gris pale)
2. **Ownership** : seul le proprietaire du dossier peut changer statut, masquer, restaurer
3. **Non pertinent** remplace le boolean `masquee` (synchronise via `save()`)
4. **Double badge supprime** : le `_card_body.html` n'affiche plus le statut en doublon
5. **Auto-promotion** : commentaire sur nouveau/discutable → discute
6. **Dashboard 6 compteurs** : grille 3x2, non_pertinent exclu du calcul de consensus

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | +2 choices, default→nouveau, save() sync masquee |
| `hypostasis_extractor/migrations/0021_*.py` | AlterField + RunPython data migration |
| `front/views.py` | Helper _est_proprietaire_dossier, ownership checks, est_proprietaire contexte |
| `front/serializers.py` | +2 choices ChangerStatutSerializer |
| `front/static/front/css/hypostasia.css` | 6 couleurs statut, discutable rouge→orange |
| `front/static/front/js/marginalia.js` | +2 entrees COULEURS_STATUT |
| `front/static/front/js/keyboard.js` | Check ownership avant raccourci S |
| `front/templates/.../carte_inline.html` | Boutons owner-only, +discutable, +non_pertinent |
| `front/templates/.../_card_body.html` | Suppression double badge statut |
| `front/templates/.../drawer_vue_liste.html` | Masquer/restaurer owner-only, "Non pertinentes" |
| `front/templates/.../dashboard_consensus.html` | Grille 3x2, 6 compteurs |
| `front/templates/front/base.html` | data-est-proprietaire sur #zone-lecture |
| `hypostasis_extractor/templatetags/extractor_tags.py` | +2 icones statut |
| `front/tests/test_phases.py` | ~17 updates + 5 nouvelles classes test |
| `front/management/commands/charger_fixtures_demo.py` | Redistribution 6 statuts |

### Migration
- **Migration necessaire / Migration required:** Oui — `hypostasis_extractor/migrations/0021_refactoring_statuts_debat.py`
- `uv run python manage.py migrate`

---

## 2026-03-16 — PHASE-26a UX : 5 ameliorations filtre multi-contributeurs

**Quoi / What:** 5 ameliorations UX du filtre multi-contributeurs :
1. **Scroll-to-first** : le drawer scrolle en haut apres activation/desactivation d'un filtre
2. **Noms dans compteur** : "2 sur 78 (marie)" au lieu de "2 sur 78"
3. **Badge entites** : la pilule active affiche le nombre d'entites distinctes (pas de commentaires)
4. **Couleur HSL** : chaque contributeur a une couleur deterministe (hash MD5 du username)
5. **Mode Sauf** : bouton "Sauf" pour inverser le filtre (exclure au lieu d'inclure)

**Pourquoi / Why:** Le facilitateur utilise le filtre pour preparer ses reunions de consensus.
Ces ameliorations rendent l'outil plus lisible (couleurs distinctes, noms), plus precis
(entites vs commentaires), et plus flexible (mode exclure pour voir "tout sauf X").

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | Helper `_calculer_teinte_contributeur()`, enrichissement contributeurs (nombre_entites + couleur_hsl), mode `exclure` avec `.exclude()` |
| `front/templates/front/includes/drawer_vue_liste.html` | Compteur avec noms + sauf, pilule-exclue/pilule-active, bouton Sauf, badge entites, commentaires mode inversé |
| `front/static/front/js/drawer_vue_liste.js` | Scroll-to-first, variable `modeFiltre`, handler bouton Sauf, `getContributeursActuels` inclut pilule-exclue |
| `front/static/front/js/marginalia.js` | `appliquerFiltreContributeurs` supporte `modeFiltre` pour inverser le dimming pastilles |
| `front/static/front/css/hypostasia.css` | `.pilule-contributeur.pilule-active` HSL, `.pilule-exclue` hachures, `.pilule-toggle-mode` |
| `front/tests/test_phases.py` | 8 tests : compteur noms, entites count, couleur HSL (3), exclure, compteur sauf, HX-Trigger mode |

### Migration
- **Migration necessaire / Migration required:** Non

---

## 2026-03-16 — PHASE-26a-bis : Filtre multi-contributeurs (pilules toggle)

**Quoi / What:** Remplacement du `<select>` mono-sélection contributeur par des pilules toggle
réutilisant le pattern `.pilule-locuteur` existant (PHASE-15). Supporte la sélection multiple :
cliquer plusieurs pilules → union des commentaires. Le paramètre `?contributeur=` accepte
désormais une liste séparée par virgules (`?contributeur=1,2,3`), rétro-compatible avec le
format single (`?contributeur=42`).

**Pourquoi / Why:** Le facilitateur veut comparer 2+ contributeurs ("qu'est-ce que Marie ET
Thomas ont dit ?"). Les pilules toggle survivent au swap HTMX, zéro JS custom fragile,
mobile-friendly, FALC.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | `drawer_contenu()` : parsing multi-IDs virgule-séparée, `user_id__in`, HX-Trigger `contributeurs_ids` (plural). Renommage `_calculer_scores_temperature_par_contributeurs()`. `LectureViewSet.retrieve()` : parsing multi-IDs. |
| `front/templates/front/includes/drawer_vue_liste.html` | Select+chip → pilules `.pilule-locuteur` toggle + bouton "Tous ×". Conditions `contributeur_actif` → `contributeurs_actifs` (set). |
| `front/static/front/js/drawer_vue_liste.js` | `getContributeursActuels()` (lecture pilules actives), handler clic pilule toggle, suppression handler select/chip. |
| `front/static/front/js/marginalia.js` | `contributeursFiltresActuels = []`, `appliquerFiltreContributeurs()` (array), listener `contributeurs_ids`. |
| `front/static/front/css/hypostasia.css` | +`.pilule-reset-contributeurs`, suppression `.chip-contributeur-actif` et `.btn-retirer-filtre-contributeur`. |
| `front/tests/test_phases.py` | 4 tests existants adaptés + 5 nouveaux tests PHASE-26a-bis (multi-filtre, HX-Trigger multi, pilules, heatmap union, rétro-compat). |

---

## 2026-03-16 — PHASE-26a : Filtre contributeur sur les commentaires

**Quoi / What:** Filtre par contributeur dans le drawer vue liste des extractions.
Quand un contributeur est selectionne, seules les extractions qu'il a commentees
apparaissent, les commentaires des autres sont dimmes (opacite reduite), les pastilles
de marge non concernees sont desactivees, et la heat map se recalcule pour ne compter
que les commentaires de ce contributeur.

**Pourquoi / Why:** Le facilitateur a besoin de filtrer par contributeur pour preparer
les reunions de consensus ("qu'est-ce que Michel a dit ?"). Ce filtre se combine avec
la heat map pour visualiser la temperature du debat du point de vue d'un contributeur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | +helper `_calculer_scores_temperature_par_contributeur()`, modifier `drawer_contenu()` (param contributeur, liste contributeurs, HX-Trigger), modifier `retrieve()` (heat map par contributeur) |
| `front/templates/front/includes/drawer_vue_liste.html` | +dropdown contributeur, +classe dimming commentaires |
| `front/static/front/js/drawer_vue_liste.js` | +param contributeur sur `chargerContenu()`, event listener select, heatmap reload |
| `front/static/front/js/marginalia.js` | +listener `contributeurFiltreChange`, filtrage pastilles, API `getContributeurFiltre`/`resetContributeurFiltre` |
| `front/static/front/css/hypostasia.css` | +`.commentaire-hors-filtre`, +`.pastille-hors-filtre` |
| `front/tests/test_phases.py` | +13 tests unitaires PHASE-26a (7 base + 6 UX) |
| `front/tests/e2e/test_17_filtre_contributeur.py` | **NOUVEAU** — 6 tests E2E |
| `front/management/commands/charger_fixtures_demo.py` | +24 commentaires sur pages Wikipedia (Ostrom, Alexandre, Sadin) par 4 contributeurs, dossier "Petits textes" rendu public |

### Ameliorations UX (post-implementation)
1. Icone personne devant le select contributeur (differencie du select de tri)
2. Chip/badge actif "nom x" pour retirer le filtre en un clic
3. Compteur "N sur M" quand filtre actif (ex: "2 sur 78")
4. Highlight du nom du contributeur filtre dans les commentaires (fond bleu + gras)
5. Badge point bleu sur le bouton toolbar Extractions quand filtre actif

---

## 2026-03-15 — PHASE-25d UX : Ameliorations Explorer

**Quoi / What:** 7 ameliorations UX sur l'Explorer et le systeme d'invitation :
1. Description optionnelle sur les dossiers (champ `description` 200 chars)
2. Compteur de suivis affiche en ambre sur les cards ("3 suivis")
3. Bouton Explorer (globe) ajoute dans la toolbar principale desktop
4. Toasts de confirmation sur Suivre/Ne plus suivre/Inviter
5. Selecteur tri (Plus recents / Plus suivis / Alphabetique)
6. Preview des 3 premiers titres de pages en badges gris dans les cards
7. Fix bug dropdown auteur duplique (Meta.ordering polluait DISTINCT)

**Pourquoi / Why:** Les cards etaient trop minimales (nom + date), l'Explorer
pas assez decouvrable (cache dans le footer de l'arbre uniquement), et pas de
feedback apres les actions Suivre/Inviter.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +champ `description` sur Dossier |
| `core/migrations/0024_dossier_description.py` | Migration auto |
| `front/serializers.py` | +champ `tri` dans ExplorerFiltresSerializer |
| `front/views_explorer.py` | +annotate nombre_suivis, +tri (populaire/nom/recent), +preview pages, +toasts HX-Trigger, fix DISTINCT |
| `front/views.py` | +toast sur action inviter |
| `front/templates/front/includes/explorer_page.html` | +select tri, +listener toast SweetAlert |
| `front/templates/front/includes/explorer_card.html` | +description, +compteur suivis ambre, +preview pages badges |
| `front/templates/front/base.html` | +bouton globe Explorer dans toolbar |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0024_dossier_description.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25d : Invitation par email + Explorer + DossierSuivi

**Quoi / What:** Invitation par email pour dossiers et groupes (email connu = partage direct,
email inconnu = invitation avec token + email). Page Explorer pour decouvrir les dossiers publics
(recherche, filtre auteur, pagination). Suivi de dossiers publics (4e section "Suivis" dans l'arbre).
Inscription avec token d'invitation → auto-acceptation.

**Pourquoi / Why:** PHASE-25c imposait de connaitre le username exact pour partager. Pas de
decouverte de contenu public. Pas moyen d'inviter un non-inscrit.

### Fichiers crees / Created files
| Fichier / File | Description |
|---|---|
| `front/views_invitation.py` | InvitationViewSet + helpers (creer, accepter, envoyer email) |
| `front/views_explorer.py` | ExplorerViewSet (list, suivre, ne_plus_suivre) |
| `front/templates/front/includes/explorer_page.html` | Page Explorer complete |
| `front/templates/front/includes/explorer_resultats.html` | Resultats pagines |
| `front/templates/front/includes/explorer_card.html` | Card dossier individuelle |
| `front/templates/front/invitation_erreur.html` | Page erreur invitation |
| `front/templates/front/emails/invitation_dossier.txt` | Email invitation dossier (texte) |
| `front/templates/front/emails/invitation_dossier.html` | Email invitation dossier (HTML) |
| `front/templates/front/emails/invitation_groupe.txt` | Email invitation groupe (texte) |
| `front/templates/front/emails/invitation_groupe.html` | Email invitation groupe (HTML) |
| `front/tests/e2e/test_16_invitation_explorer.py` | 8 tests E2E |
| `core/migrations/0023_dossiersuivi_invitation.py` | Migration auto |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +Invitation, +DossierSuivi |
| `hypostasia/settings.py` | +config email (EMAIL_BACKEND, SITE_URL, etc.) |
| `front/serializers.py` | +InviterEmailSerializer, +ExplorerFiltresSerializer |
| `front/views.py` | +action inviter sur DossierViewSet, _render_arbre 4 sections (+ Suivis) |
| `front/views_auth.py` | Handle ?token= dans register |
| `front/views_groupes.py` | +action inviter sur GroupeViewSet |
| `front/urls.py` | +ExplorerViewSet, +InvitationViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | +section Suivis |
| `front/templates/front/includes/_dossier_node.html` | +bouton Ne plus suivre |
| `front/templates/front/includes/partage_dossier_form.html` | +section email + invitations en attente |
| `front/templates/front/register.html` | +hidden field token |
| `front/templates/front/base.html` | +lien Explorer dans footer arbre |
| `front/tests/test_phases.py` | +18 tests unitaires PHASE-25d |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0023_dossiersuivi_invitation.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25c : Visibilite 3 niveaux + groupes + arbre restructure

**Quoi / What:** Systeme de visibilite a 3 niveaux (prive/partage/public) sur les dossiers.
Groupes d'utilisateurs (CRUD) pour faciliter le partage. Arbre restructure en 3 sections
accordeon (Mes dossiers / Partages avec moi / Dossiers publics). Anonymes limites aux dossiers
publics. Controle d'acces lecture/ecriture sur LectureViewSet. Moderation : owner du dossier
peut supprimer les commentaires. Auto-classement des imports dans "Mes imports". Menu contextuel
avec sous-menu visibilite. OOB swaps corriges (centralises via _render_arbre).

**Pourquoi / Why:** Le modele de visibilite PHASE-25 etait binaire (tout ou rien). Pas de
distinction prive/partage/public, pas de groupes, les anonymes voyaient tout.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +VisibiliteDossier, +GroupeUtilisateurs, visibilite sur Dossier, DossierPartage avec groupe+constraints |
| `core/migrations/0022_*.py` | Migration auto |
| `front/views.py` | +3 helpers acces, _render_arbre 3 sections, +changer_visibilite, +quitter, acces LectureViewSet, auto-classify imports, OOB fixes, moderation, DossierViewSet.list filtre |
| `front/views_groupes.py` | **Nouveau** — GroupeViewSet CRUD |
| `front/serializers.py` | +ChangerVisibiliteSerializer, +GroupeCreateSerializer, +GroupeAjouterMembreSerializer |
| `front/urls.py` | +GroupeViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | Rewrite — 3 sections accordeon |
| `front/templates/front/includes/_dossier_node.html` | **Nouveau** — partial reutilisable |
| `front/templates/front/includes/partage_dossier_form.html` | +section groupes |
| `front/static/front/js/arbre_context_menu.js` | +sous-menu visibilite |
| `front/static/front/js/arbre_overlay.js` | +JS accordeon + bouton quitter |
| `front/templates/front/includes/groupe_detail.html` | **Nouveau** — partial template detail groupe |
| `front/tests/test_phases.py` | +23 tests PHASE-25c |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0022_alter_dossierpartage_unique_together_and_more.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25b : Auth extension navigateur

**Quoi / What:** Authentification par token API pour l'extension navigateur Chrome.
L'extension envoie le token dans les headers HTTP. POST /api/pages/ exige un token valide (401 sinon).
Page `/auth/token/` pour generer/regenerer le token. Apres recolte, boutons dossiers pour classer
la page. Dossier "A ranger" auto-cree par defaut. Dedup filtree par owner + partages.
Fix URL hardcodee dans sidebar.js.

**Pourquoi / Why:** L'extension fonctionnait sans authentification — impossible de tracer
qui envoie quoi, ni de classer les pages par utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasia/settings.py` | +rest_framework.authtoken dans INSTALLED_APPS, +CORS_ALLOW_HEADERS |
| `core/views.py` | TokenAuthentication, owner sur create, endpoints me/mes_dossiers/classer_depuis_extension, dedup filtree owner+partages |
| `front/views_auth.py` | +action mon_token (GET/POST) — generation et regeneration de token |
| `front/templates/front/mon_token.html` | **Nouveau** — page standalone token avec bouton copier/regenerer |
| `front/templates/front/base.html` | Lien "Mon token API" dans dropdown menu utilisateur |
| `extension/popup.js` | Token dans headers, feedback auth, boutons dossiers post-recolte |
| `extension/popup.html` | Zones #authStatus et #dossiersChoix |
| `extension/sidebar.js` | Fix URL hardcodee → lecture serverUrl depuis storage + token dans headers |
| `extension/options.html` | Renommer "Cle API" en "Token d'authentification" + help-text |
| `front/tests/test_phases.py` | +12 tests unitaires PHASE-25b |
| `front/tests/e2e/test_15_token.py` | **Nouveau** — 3 tests E2E page token |

---

## 2026-03-15 — PHASE-25 : Users et partage

**Quoi / What:** Authentification Django (login/register/logout), propriete des ressources
(owner sur Dossier/Page), remplacement de `prenom` par `user` FK obligatoire sur
CommentaireExtraction/Question/ReponseQuestion, partage binaire de dossiers (DossierPartage),
protection des ecritures (lectures restent publiques).

**Pourquoi / Why:** L'app fonctionnait en mono-utilisateur avec identification par prenom libre.
Cette phase ajoute une vraie authentification pour tracer les contributions et permettre
le partage de dossiers entre utilisateurs.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +owner sur Dossier/Page, +DossierPartage, user FK sur Question/ReponseQuestion |
| `hypostasis_extractor/models.py` | user FK remplace prenom sur CommentaireExtraction |
| `core/migrations/0021_*.py` | Migration PHASE-25 (owner, DossierPartage, user FK) |
| `hypostasis_extractor/migrations/0020_*.py` | Migration PHASE-25 (user FK commentaire) |
| `core/admin.py` | Adapte pour user FK |
| `front/views_auth.py` | **Nouveau** — AuthViewSet (login/register/logout) |
| `front/views.py` | +_exiger_authentification(), protection ~28 actions POST, request.user dans create, _render_arbre filtre owner |
| `front/serializers.py` | +LoginSerializer, +RegisterSerializer, +DossierPartageSerializer, -prenom sur 3 serializers |
| `front/urls.py` | Enregistrer AuthViewSet |
| `front/templates/front/login.html` | **Nouveau** — page de connexion |
| `front/templates/front/register.html` | **Nouveau** — page d'inscription |
| `front/templates/front/base.html` | Menu utilisateur dans navbar |
| `front/templates/front/includes/fil_discussion.html` | Supprimer prenom, user FK, layout SMS server-side |
| `front/templates/front/includes/vue_commentaires.html` | Idem |
| `front/templates/front/includes/vue_questionnaire.html` | Supprimer prenom, gater formulaires |
| `front/templates/front/includes/drawer_vue_liste.html` | Affichage user.username |
| `front/templates/front/includes/arbre_dossiers.html` | Bouton partager |
| `front/templates/front/includes/partage_dossier_form.html` | **Nouveau** — formulaire partage |
| `front/management/commands/charger_fixtures_demo.py` | Creer users demo, assigner ownership |
| `front/tests/test_phases.py` | +19 tests unitaires PHASE-25, adaptation tests existants |
| `front/tests/e2e/base.py` | Helpers creer_utilisateur_demo, se_connecter |
| `front/tests/e2e/test_13_auth.py` | **Nouveau** — 10 tests E2E auth |
| `front/tests/e2e/__init__.py` | Import test_13 |
| `hypostasia/settings.py` | LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL |

### Audit stack-ccc

Audit complet de conformite au skill stack-ccc realise. 10 non-conformites detectees et corrigees :
- LOCALISATION ajoutee dans toutes les docstrings (views, serializers, helpers)
- Imports deplaces en haut de fichier (plus d'import interne dans les methodes)
- `role="alert"` + `aria-live="assertive"` sur les zones d'erreurs (login, register)
- `aria-label` sur les formulaires d'authentification et le dropdown menu
- `data-testid` sur tous les elements interactifs du partage (input, boutons, lignes)
- `aria-hidden="true"` sur les SVG decoratifs du partage

### Tests — 712 tests verts (614 unitaires + 98 E2E)

| Suite | Nombre | Statut |
|---|---|---|
| Tests unitaires PHASE-25 | 19 | OK |
| Tests unitaires existants (adaptes) | 595 | OK |
| Tests E2E PHASE-25 (auth) | 10 | OK |
| Tests E2E existants (adaptes) | 88 | OK |

---

## 2026-03-15 — PHASE-24 : Providers IA unifies

**Quoi / What:** Couche d'abstraction unique `core/llm_providers.py` pour les appels LLM directs.
Ajout de 2 nouveaux providers : Ollama (local) et Anthropic (Claude).
Suppression du code mort `core/services.py`.

**Pourquoi / Why:** 3 chemins d'appel LLM disperses dans le code. Cette phase les unifie
en un seul point d'entree `appeler_llm()` et ajoute le support Ollama (gratuit, local)
et Anthropic Claude (reformulation/restitution uniquement).

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `pyproject.toml` | Ajout dependance `anthropic>=0.40` |
| `core/models.py` | Provider +2 (OLLAMA, ANTHROPIC), AIModelChoices +9 modeles, champ `base_url`, prefix_to_provider etendu, tarifs |
| `core/llm_providers.py` | **Nouveau** — fonction unique `appeler_llm()` dispatche vers 5 providers |
| `core/migrations/0020_*.py` | **Nouveau** — migration auto (base_url + choices) |
| `front/tasks.py` | Supprime `_appeler_llm_reformulation()`, remplace par `appeler_llm()` |
| `hypostasis_extractor/services.py` | Ajout Ollama (model_url) et Anthropic (ValueError) dans `resolve_model_params()` |
| `core/services.py` | **Supprime** — code mort (dispatch legacy) |
| `front/tests/test_phases.py` | +10 tests unitaires PHASE-24 |
| `PLAN/PHASES/INDEX.md` | PHASE-24 cochee |

### Migration
- **Migration necessaire / Migration required:** Oui
- `uv run python manage.py migrate` — ajoute `base_url` sur `AIModel`, etend les choices

---

## 2026-03-11 — Corrections post-audit phases 1-6

- Renommage du skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + dossier `skills/`)
  / Renamed skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + `skills/` directory)
- Ajout attributs `aria-*` et `data-testid` dans les templates
  / Added `aria-*` and `data-testid` attributes in templates
- Mise a jour INDEX.md (phases 01-06 marquees completees)
  / Updated INDEX.md (phases 01-06 marked as completed)
- Creation de ce CHANGELOG
  / Created this CHANGELOG

**Fichiers modifies / Modified files:**
- `CLAUDE.md`
- `PLAN/PHASES/INDEX.md`
- `front/templates/front/base.html`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/templates/front/includes/panneau_analyse.html`
- `front/templates/front/includes/extraction_results.html`
- `front/templates/front/includes/extraction_manuelle_form.html`
- `front/templates/front/includes/lecture_principale.html`
- `skills/django-htmx-readable/` → `skills/stack-ccc/`
- `CHANGELOG.md` (nouveau / new)

**Migration** : non / no

---

## 2026-03-11 — PHASE-06 : Modeles de donnees (statut_debat + masquee)

- Ajout des champs `statut_debat` et `masquee` sur `ExtractedEntity`
  / Added `statut_debat` and `masquee` fields on `ExtractedEntity`

**Fichiers modifies / Modified files:**
- `hypostasis_extractor/models.py`
- `hypostasis_extractor/migrations/0018_extractedentity_masquee_extractedentity_statut_debat.py`

**Migration** : oui / yes

---

## 2026-03-11 — PHASE-05 : Extension navigateur robustesse

- Amelioration de la robustesse de l'extension navigateur (gestion d'erreurs, retry)
  / Improved browser extension robustness (error handling, retry)

**Fichiers modifies / Modified files:**
- `core/views.py`

**Migration** : non / no

---

## 2026-03-11 — PHASE-04 : CRUD manquants

- Ajout des operations CRUD manquantes (renommer/supprimer dossiers, supprimer pages, deplacer pages)
  / Added missing CRUD operations (rename/delete folders, delete pages, move pages)

**Fichiers modifies / Modified files:**
- `front/views.py`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/static/front/js/hypostasia.js`

**Migration** : non / no

---

## 2026-03-10 — PHASE-03 : Nettoyage code extraction

- Nettoyage et refactorisation du code d'extraction
  / Cleanup and refactoring of extraction code

**Migration** : non / no

---

## 2026-03-11 — PHASE-02 : Assets locaux (polices, CDN, collectstatic)

- Localisation des assets : Tailwind CSS, HTMX, SweetAlert2 en fichiers statiques
  / Localized assets: Tailwind CSS, HTMX, SweetAlert2 as static files
- Ajout des polices Lora (via Google Fonts, sera localise plus tard)
  / Added Lora fonts (via Google Fonts, to be localized later)

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/tailwind.css`
- `front/static/front/css/hypostasia.css`
- `front/static/front/vendor/htmx-2.0.4.min.js`
- `front/static/front/vendor/sweetalert2-11.min.js`

**Migration** : non / no

---

## 2026-03-11 — PHASE-01 : Extraction CSS/JS depuis base.html

- Extraction du CSS inline vers `hypostasia.css` et du JS inline vers `hypostasia.js`
  / Extracted inline CSS to `hypostasia.css` and inline JS to `hypostasia.js`
- Mise en place de la structure `front/static/front/`
  / Set up `front/static/front/` structure

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/hypostasia.css` (nouveau / new)
- `front/static/front/js/hypostasia.js` (nouveau / new)

**Migration** : non / no
