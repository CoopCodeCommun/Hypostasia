# Prompt de passation — session suivante (UX/UI)

> Rédigé le 13 août 2026, à la fin de la session « uiux ».
> Tout chiffre ci-dessous a été **mesuré**, pas estimé. Ce qui n'a pas
> été vérifié est dit comme tel.

---

## LE PROMPT À COLLER

Tu reprends le chantier esthétique et ergonomique d'Hypostasia. La
mission d'origine était, dans l'ordre : **le panneau d'extraction, la
gouttière, puis le lecteur audio et le visualiseur PDF.** Les **trois
premiers sont faits** — le lecteur audio a été bâti le 13 août, après
la première rédaction de ce prompt. **Il ne reste que le visualiseur
PDF** (chantier 2 ci-dessous), et les proportions à mesurer.

### Règles non négociables — lis-les avant tout le reste

- **JAMAIS d'opération git.** Ni `commit`, ni `add`, ni `push`, ni
  `checkout --`, ni `stash`, ni `reset`, ni `restore --`, ni `clean`. Le
  dépôt appartient au mainteneur, et le working tree porte 86 fichiers
  de travail non commités. Une seule commande destructive les efface.
  **Jamais de `Co-Authored-By`** dans quoi que ce soit.
- **JAMAIS `ruff format` ni `ruff check --fix` sur un fichier existant.**
  `format` réécrit des milliers de lignes hors sujet ; `--fix` supprime
  les imports à effet de bord (`@admin.register`, `@receiver`) et fait
  tomber Django au démarrage. Sur fichier neuf uniquement.
- **TDD strict** : le test d'abord, qui échoue, puis le code.
- **Relecture adverse par un agent** avant de déclarer une étape finie.
  Sur cette session elle a rattrapé ce que ma relecture laissait passer :
  neuf extractions sur douze ancrées à `start_char = 0`, et des
  commentaires de démo posés sous le vrai compte du mainteneur.
- **Vérification au navigateur, en clair ET en sombre**, avec les
  contrastes calculés. Ne jamais inventer un chiffre.
- **Conventions du dépôt** : `viewsets.ViewSet` explicites (jamais
  `ModelViewSet`), DRF serializers (jamais Django Forms), HTMX (jamais
  de SPA), commentaires bilingues FR puis EN, noms de variables verbeux
  en français, en-tête `LOCALISATION` en tête de chaque fichier.

### L'environnement

```bash
# Le serveur — port 8000, PAS 8123 (nginx/dev.conf proxie vers web:8000)
docker exec -w /app hypostasia_web uv run python manage.py <commande>

# Les tests e2e — SANS cette variable, tout échoue en setUpClass
docker exec -w /app -e PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright \
  hypostasia_web uv run python manage.py test front.tests.e2e.<module> --noinput
```

**Le build Tailwind est FIGÉ** : toute classe arbitraire (`z-[70]`,
`min-w-[160px]`) est inerte. Passe par les tokens CSS de `maquette.css`
(`--papier`, `--encre`, `--panneau`, `--gouttiere`, `--barre-audio`…).

### L'étalon

`front/static/front/maquettes/maquette.html`. Son en-tête porte deux
tableaux que **tu dois tenir à jour** — une session précédente est
repartie sur une carte périmée, ça a coûté du travail :

1. **Les sept écarts**, avec leur état réel. Six sont résolus. **Seul le
   n°2 — le lecteur audio — reste ouvert**, et le n°3 (progression en
   direct) est un écart *assumé*, pas une dette.
2. **« Ce sur quoi le produit s'écarte de cet étalon — par décision »** :
   trois arbitrages du mainteneur. **Les lire comme des retards ferait
   défaire ses décisions.** C'est l'étalon qui devra évoluer, pas le
   produit.

---

## CHANTIER 1 — Le lecteur audio : FAIT le 13 août

Livré, mesuré au navigateur en clair et en sombre, 7 tests e2e
(`test_32_lecteur_audio`) plus 12 tests serveur. Ce qui existe :

- **La barre** : 62 px, `fixed` en bas, `<audio preload="metadata">` sur
  `page.source_file`, bouton, minutage, rail. Elle ne paraît que si la
  note est un audio **et** qu'un média est attaché — une transcription
  sans son garderait un bouton qui ne joue rien.
- **Le rail** : un segment par tour, à la couleur de son locuteur,
  opacité `.85` quand le tour porte des idées. Cliquable pour se
  déplacer, `role="slider"` avec les flèches au clavier.
- **Le minutage de la gouttière est devenu un bouton** : il *disait*
  déjà l'instant du tour, il ne manquait qu'à pouvoir l'atteindre.
- Le tour entendu se marque dans la marge, et le texte suit l'oreille
  **pendant la lecture seulement** — une page qui bouge toute seule
  quand on la lit à l'arrêt serait insupportable.

**Deux écarts assumés avec l'étalon**, tous deux vers la justesse : les
segments sont positionnés en **absolu** (l'étalon les empile en `flex`,
ce qui suppose des tours contigus — ils ne le sont pas, et chaque
segment dériverait de la somme des silences), et le filet du haut est
`--filet` et non le violet `--cible`, qui marque ce qui n'existe pas
encore.

**Corrigé au passage** : le même locuteur portait **deux couleurs** sur
le même écran — bleu dans les pilules et la timeline (palette Tailwind),
orange dans la gouttière (palette de Wong). Les widgets prennent
désormais Wong (`test_couleurs_des_locuteurs`).

### Ce qui reste ouvert sur l'audio, et qui t'appartient

1. **Deux rails à l'écran.** Celui du lecteur, en bas, et la timeline
   click-to-scroll de PHASE-15, en haut — celle que l'étalon décrivait
   comme « l'existant » que le lecteur devait remplacer. Leurs couleurs
   concordent maintenant, mais faut-il garder les deux ? Le rail fait
   plus (il déplace la lecture) ; la timeline garde le click-to-scroll,
   qui n'a pas d'équivalent. **Décision du mainteneur** — un retrait
   « propre » a déjà failli supprimer deux fonctions entières le 12 août.
2. **Le seek exige nginx.** `/media/` est servi par
   `django.views.static` en dev (`hypostasia/urls.py:32`), qui **ne gère
   pas les requêtes `Range`** : sur un enregistrement long, se déplacer
   ne marchera pas en dev. En prod, nginx le sert (`nginx/default.conf:25`)
   et gère `Range` nativement. Rien à corriger dans le lecteur, mais à
   savoir avant de croire à un bug.

---

## CHANTIER 2 — Le visualiseur PDF

**Il est possible depuis le 11 août, et c'est neuf** : la base porte 72
coordonnées. Le bouton « voir la source » existe déjà dans la gouttière
(`_blocs_elements.html:113`) et **dit honnêtement qu'il ne sait pas
encore le faire** plutôt que de promettre.

La donnée, exactement :

```json
{"page_no": 1,
 "boites": [{"l": 46.0, "t": 739.232, "r": 472.768, "b": 661.032,
             "page_no": 1, "coord_origin": "BOTTOMLEFT"}]}
```

Trois pièges, chacun a une conséquence visible :

- **`boites` est une LISTE.** Un paragraphe à cheval sur deux pages en a
  plusieurs, chacune avec son propre `page_no`. Prendre `boites[0]`
  perdrait la seconde moitié du surlignage.
- **`coord_origin` vaut `BOTTOMLEFT`** : `t` se mesure depuis le **bas**.
  PDF.js travaille en origine haut-gauche → `y_écran = hauteur_page − t`.
  Inverser dessine les surlignages à l'envers.
- **Les pages font 612 × 792 points** (Letter, pas A4) pour le PDF étude.
  **Ne code pas cette taille en dur** : lis-la du document.

`SPEC-ancrage-par-element-v2.md § 8.2` existe mais **ne suffit pas pour
coder** : elle donne trois corrections (`convertToViewportRectangle`,
`devicePixelRatio`, `boites` en liste) sans le socle — rien sur le
composant PDF.js, la pagination, le zoom, le calque de surlignage.
**Écris cette spec en addendum daté avant de coder.**

Restent à décider : PDF.js servi en local (cohérent avec le
`collectstatic` du projet) ou par CDN ; SVG au-dessus du canvas ou divs
positionnés ; et le cas d'un PDF **sans couche texte** — un scan pur, où
il n'y a aucune coordonnée à surligner.

---

## CHANTIER 3 — Les proportions générales

Demandé par le mainteneur, **jamais fait, et non mesuré**. Il ne reste
pas d'écart de proportion *connu* : le centrage a été corrigé le 12 août
(la colonne tombait 42 px à gauche du centre, contre 13 px dans
l'étalon), et le panneau tient ses 368 px sous les 1400 px de seuil.

Donc : **mesure avant de conclure**. Compare largeur de colonne de
lecture, interlignes, tailles de police, hauteurs de bandes, en 1600 px
et en mobile. S'il n'y a rien, dis-le — c'est un résultat.

---

## DÉCISION EN ATTENTE DU MAINTENEUR

**La granularité de l'ancrage sur un tableau.** Un tableau est **un
seul** `ElementDocument` de 4 471 signes : une idée ancrée dessus
désigne le tableau entier, pas une ligne. Rendre un vrai `<table>` (fait
le 13 août) n'y change rien — c'est une décision de **modèle**, pas de
rendu. Signalée deux fois, jamais tranchée. Découper par ligne à
l'ingestion, ou assumer le bloc : à lui de dire.

---

## L'ÉTAT DES TESTS — mesuré le 13 août, pas estimé

**1874 tests, tous verts.** La suite complète tourne en **12 min 51 s**
(`front core hypostasis_extractor`), dont 25 sautés. Elle prenait bien
plus avant l'optimisation du 13 août — navigateur Playwright partagé
entre modules, `networkidle` remplacé par des attentes sur l'objet
mesuré. Un module e2e de 13 tests passe désormais en 23 s.

Le dernier échec a été trouvé et corrigé le 13 août, et il vaut d'être
lu — c'est le genre de défaut qu'un travail d'UX peut créer sans le
voir :

> Supprimer une note citée par une synthèse adoptée répondait **204 No
> Content** au lieu de refuser. Le refus lui-même marchait (rien n'était
> supprimé, le toast partait), mais 204 se lit comme **un succès sans
> corps**. Cause : la réponse de cet endpoint était l'arbre latéral —
> toujours du HTML, donc toujours 200. L'arbre retiré, elle est devenue
> la liste des notes du carnet, qui vaut `None` quand la requête ne dit
> pas d'où part le geste. Corrigé en **409**, comme le refus jumeau
> `supprimer_entite` : même cause, même code.

**La leçon pour toi** : retirer un composant change les réponses de tous
les endpoints qui le rendaient. `manage.py check` ne voit rien de tout
ça — seule la suite complète l'a montré. Lance-la avant de déclarer une
étape finie.

---

## L'ÉTAT DU DÉPÔT

`git status` : 86 entrées, **rien de commité** — le mainteneur commite
lui-même, ne le fais jamais à sa place.

Ce qui a été livré pendant la session du 12–13 août :

| Livré | Où |
|---|---|
| Panneau d'analyse intégré au corps de la note | `base.html`, `.plateau` |
| Bande de contexte unique (fil + titre du panneau) | décision A de l'étalon |
| Dashboard retiré, avec tout son code | `dashboard_consensus.*` supprimés |
| Menu burger et arbre latéral retirés définitivement | `arbre_*.js`, `_dossier_node.html` supprimés |
| Onglet « Bases de connaissances » sur la home, deux zones | `test_29` |
| Pages liste des carnets et des bases | `test_24`, `test_25` |
| Champ image de couverture sur les bases | migration `0062` |
| Analyseurs branchés à l'installation | `front/services/fixtures_analyseurs.py` |
| Fixture d'extractions déterministe, sans LLM | `charger_extractions_demo.py` |
| Formes par label : `<table>`, `<blockquote>`, `<figure>` | `rendu_elements.py:88` |
| Optimisation des tests e2e (navigateur partagé) | `front/tests/e2e/base.py` |

**Un garde-fou à ne pas casser** : `front/tests/test_aucun_geste_orphelin.py`
vérifie que chaque geste porté par l'arbre latéral supprimé a gardé un
point d'entrée quelque part. Il existe parce que deux fois dans la même
journée, un retrait « propre » a failli supprimer une fonction entière
sans que personne ne le voie — le dashboard portait le **seul** accès à
la synthèse, et le bouton « Analyses » le **seul** moyen de rouvrir le
panneau.

### Plans écrits et NON exécutés

- `docs/superpowers/specs/2026-08-11-dedup-import-design.md` —
  déduplication à l'import par empreinte du fichier source.

### Défauts connus, différés

Listés dans
`.superpowers/sdd/2026-08-11-charger-fixtures-sample/progress.md`. Les
plus notables : les médias orphelins (`Page.delete()` ne supprime pas le
fichier), et une transcription échouée qui relance un appel Voxtral
**facturé** à chaque rechargement.

---

## PAR QUOI COMMENCER

1. **Ouvre l'étalon et le produit côte à côte**, en clair puis en sombre.
   Les sept écarts sont désormais tous résolus ou assumés — mais les
   tableaux périment, et celui-ci s'est déjà révélé faux sur quatre
   lignes. Mesure avant de croire.
2. Charge de quoi travailler : `charger_fixtures_demo` puis
   `charger_extractions_demo`. Sans extractions posées, le panneau est
   vide et tu styles à l'aveugle.
3. **Tranche la question des deux rails** avec le mainteneur (chantier 1,
   point 1) — c'est une décision de produit, pas de style.
4. **Écris la spec du visualiseur PDF** avant de l'attaquer.
5. **Mesure les proportions** (chantier 3). S'il n'y a rien à corriger,
   dis-le : c'est un résultat.
6. **Mets à jour le tableau des sept écarts** dans l'en-tête de
   `maquette.html` à chaque ligne que tu touches. La session suivante
   repart de là.

### Pour vérifier au navigateur

Le script de la session du 13 août, à reprendre : il ouvre le vrai
serveur, bascule les deux thèmes, calcule les contrastes WCAG et écrit
des captures. Deux pièges y sont déjà désamorcés — `hypostasia_nginx`
n'est pas dans `ALLOWED_HOSTS` (passer par `localhost` avec
`--host-resolver-rules=MAP localhost <ip nginx>`), et `color-mix()` rend
des composantes en 0–1 quand `rgb()` les donne en 0–255, ce qui avait
fait annoncer un contraste de 1,15:1 là où il valait 4,13:1.

**Et `collectstatic` après toute modification de CSS ou de JS** : les
statiques sont servis depuis `staticfiles/`, pas depuis les sources. Un
fichier neuf non collecté donne un 404 silencieux — le JS ne tourne
pas, et rien ne le dit.
