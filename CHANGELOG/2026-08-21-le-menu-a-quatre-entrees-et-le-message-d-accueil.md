# Le menu à quatre entrées, et le message d'accueil / The four-entry menu and the welcome message

**Date :** 2026-08-21
**Migration :** Non

## Résumé / Summary

**Quoi / What :** La page racine ne rend plus d'écran : elle **redirige vers
`/carnets/`**. Les trois onglets JavaScript qu'elle portait — « Découvrir
l'app », « Bases de connaissances », « Manifeste » — deviennent des **entrées de
menu adressables**, dans l'ordre **Carnets · Bases · Aide · Manifeste**, visibles
sur téléphone comme sur ordinateur. L'onglet des bases disparaît : sa vue est
rendue à `/bases/`, qui reprend ses deux zones. Une **modale d'accueil** explique
les quatre entrées et reparaît tant que personne n'a coché « j'ai compris ».

*The root page no longer renders a screen: it redirects to `/carnets/`. Its three
JavaScript tabs become addressable menu entries — Carnets, Bases, Aide,
Manifeste — visible on phones as on desktops. The bases tab is gone, its view
returned to `/bases/`. A welcome modal explains the four entries and comes back
until someone ticks "j'ai compris".*

**Pourquoi / Why :** L'onglet « Bases de connaissances » de l'accueil et
`/bases/` étaient **deux vues du même objet**, et elles avaient déjà divergé :
l'onglet ignorait l'explication de ce qu'est une base, les compteurs et la carte
de création. Plus généralement, **un onglet n'a pas d'adresse** — ni signet, ni
partage, ni bouton « précédent ». Les quatre entrées en ont une.

*The home tab and `/bases/` were two views of one thing, already drifted apart.
And a tab has no address: no bookmark, no sharing, no back button.*

### Ce que l'unification ne perd pas / What the merge keeps

La distinction **« Mes bases » / « Bases publiques et partagées »** — décision du
mainteneur du 12 août — est **portée à `/bases/`** au lieu d'être supprimée avec
l'onglet. `/bases/` garde par ailleurs tout ce que l'onglet n'avait pas :
l'explication permanente, les compteurs distincts, la carte de création.

*The 12 August two-zone split moved to `/bases/` instead of dying with the tab.*

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/views_accueil.py` | **NEUF** — `AideViewSet`, `ManifesteViewSet`, l'UUID du message d'accueil et la règle d'affichage |
| `front/context_processors.py` | **NEUF** — porte `afficher_le_message_d_accueil` jusqu'à `base.html` |
| `front/templates/front/includes/message_d_accueil.html` | **NEUF** — la modale et son script de fermeture |
| `front/templates/front/includes/manifeste_ecran.html` | **NEUF** — le manifeste + effacement du fil et du lecteur audio |
| `front/tests/test_le_menu_et_le_message_d_accueil.py` | **NEUF** — 27 tests serveur |
| `front/tests/e2e/test_29_menu_et_message_d_accueil.py` | **NEUF** — 17 tests navigateur (remplace `test_29_bases_sur_la_home.py`, supprimé) |
| `front/tests/test_ce_que_dit_l_aide.py` | **NEUF** — 9 tests : les listes de raccourcis contre `keyboard.js`, et le vocabulaire mort |
| `front/templates/front/bibliotheque.html` | **SUPPRIMÉ** — une ligne, plus aucun appelant |
| `front/views.py` | `BibliothequeViewSet.list` → `redirect("/carnets/")` ; `_les_deux_zones_de_bases` déplacée |
| `front/views_corpus.py` | `_les_deux_zones_de_bases` accueillie ici ; `BaseViewSet.list` pose les deux zones |
| `front/urls.py` | `aide` et `manifeste` enregistrés au routeur |
| `front/templates/front/base.html` | Quatre enfants directs dans la barre ; les 4 entrées ; branches `aide_preloaded` / `manifeste_preloaded` ; include de la modale |
| `front/templates/front/corpus/bases_liste.html` | Deux zones, la création dans « Mes bases » |
| `front/templates/front/includes/onboarding_vide.html` | Onglets, script de bascule, zone des bases et zone manifeste retirés ; OOB du lecteur audio ajouté ; **les 7 affirmations fausses corrigées** |
| `front/views.py` (bis) | `liste_raccourcis` : `S — Marquer consensuelle` retiré (non lié, statut disparu le 2 mai) |
| `front/static/front/css/maquette.css` | Modale, `.entrees-de-navigation` (repli sous 560 px), `.section-de-bases` recalée et renommée — `?v=73` |
| `hypostasia/settings.py` | Le context processor branché |
| `front/tests/e2e/base.py` | La session de test porte l'UUID du message : sinon la modale intercepte les clics de **toute** la suite |
| `front/tests/e2e/__init__.py`, `test_01_navigation.py`, `test_phases.py`, `test_effacement_du_fil_d_ariane.py` | Adaptés à la redirection et aux écrans neufs |

### Mesures / Measurements

Toutes prises au navigateur le 21 août 2026, sur `/carnets/` et `/lire/1/`.

**Pourquoi les entrées passent au rang du dessous sous 560 px.** En 390 px, les
contrôles de droite occupent **243 px** des 366 px utiles ; la zone gauche tombe
à **119 px**, et les quatre entrées en réclament **237**. Dans l'ancienne forme —
un conteneur `overflow-hidden` — « Aide » et « Manifeste » étaient **rognés en
silence**. Les abréger ou les changer en pictogrammes contredirait le retrait du
burger : elles descendent d'un rang, et `--barre-outils` passe de 44 à 78 px avec
elles (quatre autres règles lisent ce token).

Après correction, à **360, 390, 480, 560, 640, 768, 1024 et 1600 px** : aucune
entrée rognée, aucun débordement horizontal.

**Contrastes calculés** (WCAG AA = 4,5:1 pour du texte normal) :

| | clair | sombre |
|---|---|---|
| entrées du menu | 10,56 | 11,58 |
| modale — titre | 16,79 | 15,10 |
| modale — intro / case / croix | 5,42 | 6,18 |
| modale — nom d'entrée | 15,53 | 13,91 |
| modale — rôle d'entrée | 5,01 | 5,69 |
| modale — bouton « C'est parti » | 16,79 | 19,01 |

Identiques en 1400 px et en 390 px. Aucune valeur sous 4,5:1.

### Le mécanisme du message d'accueil / How the welcome message works

La session ne retient pas « cette personne a vu le message » mais **« cette
personne a vu CE message-là »** : `UUID_DU_MESSAGE_D_ACCUEIL`
(`front/views_accueil.py`). Changer cette constante republie le message à tout le
monde, y compris à ceux qui avaient coché — c'est le mécanisme prévu pour
annoncer une mise à jour, sans second dispositif ni effacement de sessions.

*The session remembers WHAT was seen, not THAT something was.*

### L'audit de l'écran « Aide » / Auditing the Help screen

Promouvoir cet écran au rang d'entrée de menu a imposé de vérifier **ce
qu'il affirme**, ligne à ligne, contre le code. **Sept affirmations étaient
fausses.** Aucune n'avait jamais levé d'erreur : une aide ne plante pas, elle
ment.

*Promoting this screen to a menu entry meant checking every claim it makes
against the code. Seven were false, and none had ever raised an error.*

| Ce qu'il disait | Ce que le code fait | Corrigé en |
|---|---|---|
| « une **pastille en marge** » | Les pastilles sont mortes avec l'ancien moteur d'ancrage (10 août 2026) ; `test_phases.py` verrouille déjà la disparition de leur CSS | « **surligné dans le texte** », plus la **gouttière** et son compteur d'idées |
| « Cliquez sur une **pastille** » | `marginalia.js` écoute le clic sur `mark.hl-extraction` — panneau latéral au-dessus de 768 px, feuille du bas en dessous | « Cliquez un **passage surligné**, ou le compteur de la gouttière » |
| « **L'IA** extrait les passages clés » | `selection_menu.html` : le **crayon** crée une extraction à la main ; l'étincelle IA n'apparaît que si un modèle est configuré | « Sélectionnez un passage et cliquez le crayon, **ou** laissez l'IA le faire » |
| « Lancez la synthèse quand vous le souhaitez » | Une synthèse est une note **du carnet**, en deux genres (`liste_wikis.html`, `liste_syntheses.html`) | « Depuis un carnet, pas depuis une note : un **wiki** vivant, ou une **synthèse dirigée** figée » |
| Raccourci **`T` — Bibliothèque** | **Non lié.** `keyboard.js` porte à sa place un commentaire expliquant pourquoi : « laisser un raccourci sans effet est pire que pas de raccourci du tout » | Retiré |
| Raccourci **`S` — Consensuelle** | **Non lié**, et le statut n'existe plus depuis la fusion des six en deux (2 mai 2026). Il était dans les **deux** listes d'aide | Retiré des deux |
| « Appuyez sur `?` pour revoir **cette aide** » | `?` fait `htmx.ajax('GET', '/lire/aide/')` : c'est la **modale des raccourcis**, pas cet écran | « `?` les rappelle par-dessus n'importe quel écran » |

Deux précisions mineures au passage : « PDF, audio, **page web**, Word » — or
l'attribut `accept` du bouton n'admet aucun format de page web, elle vient de
l'**extension navigateur** ; et « rond gris » désignait un cercle que le CSS
dessine **vide** (fond transparent, bordure de 2 px).

### Le garde-fou / The guard

`front/tests/test_ce_que_dit_l_aide.py` **compare les listes de raccourcis aux
touches réellement liées** dans `keyboard.js`, en lisant son `switch` — jamais
une copie. Un raccourci retiré du JS fait désormais tomber la suite, au lieu de
survivre des mois dans un écran que personne ne rouvre.

Il verrouille **les deux** listes du produit (l'écran « Aide » et la modale
« ? ») : c'est en n'en gardant qu'une sous surveillance que `S` a survécu dans
l'autre. Il porte aussi une **contre-épreuve** — sans elle, une lecture qui
rendrait un ensemble vide ferait passer les deux tests au vert.

Les tests de vocabulaire lisent le **rendu**, pas le gabarit : Django retire les
`{% comment %}`, et lire la source ferait tomber la suite sur les commentaires
qui expliquent pourquoi un mot a été retiré (mesuré : la première version s'est
cassée sur son propre commentaire).

---

## Comment tester (à la main) / Manual test

### Test 1 — la racine mène aux carnets

1. Ouvrir `https://beta.hypostasia.org/` (ou `http://localhost:8000/`).
2. **Attendu** : la barre d'adresse affiche `/carnets/`, la liste des carnets
   s'affiche sous le menu.
3. Cliquer le mot « Hypostasia » depuis n'importe quel écran.
4. **Attendu** : retour aux carnets, l'adresse affiche `/carnets/` (pas de
   rechargement complet — c'est un swap HTMX).

### Test 2 — les quatre entrées, sur ordinateur

1. Sur `/carnets/`, lire la barre : **Carnets · Bases · Aide · Manifeste**, dans
   cet ordre, à droite du mot « Hypostasia ».
2. Cliquer chacune. **Attendu** : l'écran change, l'adresse suit
   (`/carnets/`, `/bases/`, `/aide/`, `/manifeste/`), le fil d'Ariane de l'écran
   précédent disparaît.
3. Recharger la page sur `/manifeste/` (F5). **Attendu** : le manifeste
   s'affiche, avec le menu au-dessus — jamais seul.
4. Utiliser le bouton « précédent » du navigateur. **Attendu** : on revient à
   l'écran précédent.

### Test 3 — les quatre entrées, sur téléphone

1. Réduire la fenêtre à **390 px** de large (ou ouvrir sur un téléphone).
2. **Attendu** : le mot « Hypostasia » disparaît, et les quatre entrées passent
   sur un **second rang**, sous les contrôles, séparées par un filet.
3. Vérifier que les quatre mots sont **entiers** — ni coupés, ni suivis de « … ».
4. Réduire encore à **360 px**. **Attendu** : idem, et aucune barre de défilement
   horizontale n'apparaît en bas de la page.
5. Élargir au-delà de **560 px**. **Attendu** : les quatre entrées remontent sur
   la ligne des contrôles.

### Test 4 — le message d'accueil

1. Ouvrir une fenêtre de **navigation privée** (session neuve) sur `/carnets/`.
2. **Attendu** : la modale « Bienvenue dans Hypostasia » s'ouvre, et nomme les
   quatre entrées du menu.
3. Cliquer « C'est parti » **sans** cocher la case. **Attendu** : elle se ferme.
4. Recharger la page. **Attendu** : **elle revient** — c'est voulu.
5. Cocher « J'ai compris, ne plus afficher ce message », puis « C'est parti ».
6. Recharger. **Attendu** : elle ne revient plus.
7. Décocher la case (rouvrir la modale via une session neuve pour la revoir), et
   vérifier qu'un décochage la fait revenir au rechargement suivant.
8. Vérifier aussi la croix et la touche **Échap** : les deux ferment sans
   enregistrer.

### Test 5 — les deux zones de `/bases/`

1. Connecté, ouvrir `/bases/`.
2. **Attendu** : deux sections — « Mes bases » (avec la carte
   « + Nouvelle base » en dernière cellule) et « Bases publiques et partagées ».
3. Rendre une de ses bases publique. **Attendu** : elle reste du côté « Mes
   bases », et n'apparaît **pas** dans l'autre zone.
4. Se déconnecter. **Attendu** : la section « Mes bases » disparaît entièrement,
   la carte de création aussi.
5. Vérifier qu'une base **privée d'autrui** n'apparaît nulle part.

### Test 6 — le mode sombre

Rejouer les tests 2, 4 et 5 après avoir basculé le thème (le bouton ○/● de la
barre). Tout doit rester lisible : les mesures de contraste ci-dessus sont
toutes au-dessus de 4,5:1, mais l'œil vérifie ce qu'un ratio ne dit pas.

### Test 7 — ce que dit l'écran « Aide »

Le but est de vérifier que chaque affirmation **se vérifie à l'écran**.

1. Ouvrir `/aide/`, puis ouvrir une note dans un autre onglet pour comparer.
2. **Étape 2** : dans la note, sélectionner une phrase. **Attendu** : un menu
   flottant apparaît avec un **crayon** (extraction à la main) et, si un modèle
   est configuré, une **étincelle** (IA). C'est ce que l'aide décrit.
3. **Étape 2 (suite)** : vérifier qu'un passage extrait est **surligné dans le
   texte**, et que la **gouttière de gauche** porte un chiffre — le compteur
   d'idées. **Il ne doit y avoir aucune pastille en marge** : elles n'existent
   plus.
4. **Étape 3** : cliquer un passage surligné. **Attendu** : sa carte s'ouvre
   dans le panneau de droite. Réduire la fenêtre sous 768 px et recommencer :
   la carte s'ouvre en **feuille du bas**.
5. **Étape 4** : ouvrir un carnet, chercher où lancer une synthèse. **Attendu** :
   deux entrées, **wiki** et **synthèse dirigée** — et rien de tel sur une note.
6. **Raccourcis** : depuis une note, presser **`T`** puis **`S`**. **Attendu** :
   rien ne se passe, et l'aide ne les annonce plus. Presser `E`, `J`, `K`, `C`,
   `X`, `A`, `Z`, `Échap` : chacun agit.
7. Presser **`?`**. **Attendu** : la modale des raccourcis s'ouvre (ce n'est
   *pas* l'écran « Aide »), et **`S` n'y figure plus** non plus.
8. **Étape 1** : cliquer « Importer un fichier » et regarder les formats
   proposés par le sélecteur. **Attendu** : aucun format de page web — c'est
   l'extension navigateur qui les capture, comme l'aide le dit maintenant.

### Vérifs automatiques / Automated checks

```bash
# 27 tests serveur
docker exec -w /app hypostasia_web python manage.py test \
    front.tests.test_le_menu_et_le_message_d_accueil

# 9 tests : ce que l'aide affirme, contre keyboard.js et le rendu
docker exec -w /app hypostasia_web python manage.py test \
    front.tests.test_ce_que_dit_l_aide

# 17 tests navigateur (mesure les 4 entrées à 360 px et 1600 px)
make test-e2e S=test_29_menu_et_message_d_accueil

# Les suites voisines touchées par le changement
make test-e2e S=test_25_liste_des_bases
make test-e2e S=test_10_mobile
make test-e2e S=test_01_navigation
```

### Ce qui reste à trancher / Open questions

**Deux chantiers reportés à une autre session**, à la demande du mainteneur.
Tous deux demanderont une ligne dans l'écran « Aide » une fois faits — écrite
maintenant, elle serait fausse jusque-là.

1. **Déplacer le bouton d'import dans le carnet**, pour qu'un fichier atterrisse
   dans **ce** carnet et non dans le vrac. Le socle est déjà là :
   `ImportFichierSerializer` accepte `dossier_id`, et `front/views.py` s'en sert
   (`if dossier_id: …`). Ce qui manque est côté client — `hypostasia.js`
   n'envoie **jamais** `dossier_id`, si bien que tout import tombe dans le
   carnet de rôle « Mes imports » (`_get_ou_creer_dossier_mes_imports`,
   `front/views.py:559`). Attention en retirant le bouton de la barre :
   `front/tests/test_aucun_geste_orphelin.py` verrouille `btn-toolbar-import`
   comme point d'entrée, et c'est le **seul** chemin d'import sur téléphone
   depuis le retrait du tiroir.

2. **Le menu garde le nom de la note après retour au carnet.** *Reproduit au
   navigateur le 21 août 2026* : après `/lire/1/`, une navigation HTMX vers
   `/carnets/1/`, `/bases/` puis `/aide/` laisse `#titre-toolbar` afficher
   « Badgeons la Normandie » sur les trois écrans.
   **Cause** : `#titre-toolbar` vit hors de `#zone-lecture`, donc un swap HTMX
   ne le touche jamais — exactement comme le fil d'Ariane et la barre du lecteur
   audio. Ces deux-là ont chacun un partial OOB que **tout écran** inclut
   (`_fil_ariane_oob.html`, `_lecteur_audio_oob.html`) ; le titre est le
   troisième élément de cette famille et **n'en a pas**. Un seul gabarit dépose
   son OOB, `lecture_principale.html:289` — celui de la note. Personne ne
   l'efface.
   **Correctif attendu** : un `_titre_toolbar_oob.html` sur le modèle des deux
   autres, inclus partout où `_lecteur_audio_oob.html` l'est déjà, plus un test
   qui énumère les écrans (le patron existe :
   `front/tests/test_effacement_du_fil_d_ariane.py`).
