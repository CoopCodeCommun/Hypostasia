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
| `front/templates/front/bibliotheque.html` | **SUPPRIMÉ** — une ligne, plus aucun appelant |
| `front/views.py` | `BibliothequeViewSet.list` → `redirect("/carnets/")` ; `_les_deux_zones_de_bases` déplacée |
| `front/views_corpus.py` | `_les_deux_zones_de_bases` accueillie ici ; `BaseViewSet.list` pose les deux zones |
| `front/urls.py` | `aide` et `manifeste` enregistrés au routeur |
| `front/templates/front/base.html` | Quatre enfants directs dans la barre ; les 4 entrées ; branches `aide_preloaded` / `manifeste_preloaded` ; include de la modale |
| `front/templates/front/corpus/bases_liste.html` | Deux zones, la création dans « Mes bases » |
| `front/templates/front/includes/onboarding_vide.html` | Onglets, script de bascule, zone des bases et zone manifeste retirés ; OOB du lecteur audio ajouté |
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

### Vérifs automatiques / Automated checks

```bash
# 27 tests serveur
docker exec -w /app hypostasia_web python manage.py test \
    front.tests.test_le_menu_et_le_message_d_accueil

# 17 tests navigateur (mesure les 4 entrées à 360 px et 1600 px)
make test-e2e S=test_29_menu_et_message_d_accueil

# Les suites voisines touchées par le changement
make test-e2e S=test_25_liste_des_bases
make test-e2e S=test_10_mobile
make test-e2e S=test_01_navigation
```

### Ce qui reste à trancher / Open questions

L'écran « Aide » (ex-onglet « Découvrir l'app ») liste deux raccourcis clavier
qui **n'existent plus**, et ce contenu est antérieur à ce chantier :

- **`T` — Bibliothèque** : retiré le 12 août 2026 avec l'arbre latéral.
  `front/views.py` l'a déjà retiré de la modale « ? » pour cette raison exacte
  (« une aide qui annonce un raccourci mort est pire qu'une aide incomplète »).
- **`S` — Consensuelle** : les six statuts ont été fusionnés en deux le 2 mai
  2026 ; « consensuelle » n'existe plus. La modale « ? » le liste encore aussi
  (`front/views.py`, `liste_raccourcis`).

Les deux figurent dans **deux** listes qu'il faudrait corriger ensemble. Non
touchés ici : c'est un arbitrage de vocabulaire métier, pas une conséquence de ce
chantier.
