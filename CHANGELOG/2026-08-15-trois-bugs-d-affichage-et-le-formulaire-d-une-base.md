# TROIS BUGS D'AFFICHAGE, ET LE FORMULAIRE D'UNE BASE

**Date :** 2026-08-15
**Migration :** Non

**Quoi / What :** un commentaire de gabarit affiche a l'ecran, l'onglet
« Bases de connaissances » rendu sans style, le fil d'Ariane qui survit
a la navigation et son menu rogne. Puis le nom et la visibilite d'une
base deviennent modifiables.
/ Three display bugs fixed, then a base's name and visibility became
editable.

**Migration :** Non.

### 1. Un commentaire de gabarit s'affichait a l'ecran

`{# #}` ne vaut que sur UNE ligne. Sur plusieurs, Django ne le
reconnait pas comme commentaire et son texte part dans le rendu. Six
blocs etaient dans ce cas, dont celui en tete de `carte_de_base.html` —
un pavé de onze lignes affiché en toutes lettres sur `/bases/` et sur
l'accueil. Un septieme, dans le meme fichier, fuyait a l'INTERIEUR d'une
balise `<img>` : invisible a l'oeil, mais le HTML etait corrompu.
Tous passent en `{% comment %}`.
/ Django's `{# #}` is single-line only; six multi-line blocks were
leaking their text into the page, one of them inside an `<img>` tag.

### 2. L'onglet « Bases de connaissances » de l'accueil etait sans style

Le markup etait juste et arrivait au bon endroit : il manquait les
REGLES. Chaque ecran du corpus inclut lui-meme `_style_maquette.html`,
ou vivent les regles de `.grille-bases` et `.carte-base` — scopees
`.zone-corpus`. `onboarding_vide.html`, la branche « sinon » de la
cascade de `base.html`, montre les memes cartes par le meme partial mais
ne faisait pas cet include : les cartes tombaient en texte brut.
/ The markup was right; the rules were missing. The home tab reuses the
corpus cards but did not include the stylesheet partial that draws them.

### 3. Le fil d'Ariane survivait a la navigation, et son menu etait rogne

Deux defauts distincts sous un seul symptome :

- **Il persistait.** `_fil_ariane_oob.html` n'etait inclus que par
  `article.html`, `carnet_detail.html` et `lecture_principale.html`.
  En revenant sur `/bases/` depuis une note, aucune reponse ne
  redeposait le fil : celui de la note restait en place, au-dessus de la
  racine du corpus. Les trois ecrans qui manquaient l'incluent
  desormais — sans `fil_carnet`, le partial depose un conteneur VIDE,
  qui efface le fil precedent et escamote la bande.
- **Son menu etait invisible.** Pas un z-index : un CLIPPAGE.
  `.fil-ariane-conteneur` portait `overflow: hidden`, alors que le menu
  de bascule est un `position: absolute` ancre SOUS le fil. Mesure : le
  menu s'ouvrait bien (`display: block`, bas a y=194) mais son conteneur
  s'arretait a y=79. Le fichier se contredisait lui-meme — le
  commentaire de `.fil-ariane` exige « overflow VISIBLE, sinon le menu
  de bascule est invisible ». La protection contre un titre trop long
  passe du conteneur au dernier segment (`nowrap` + ellipsis).

/ Two distinct faults: the breadcrumb was never cleared by screens that
have none, and its switcher menu was clipped — not a z-index issue.

### 4. Le nom et la visibilite d'une base deviennent modifiables

Ni l'un ni l'autre n'etait atteignable : l'admin Django est ferme, et la
creation etait la seule occasion d'ecrire le nom — une faute de frappe y
devenait definitive, et une base restait `prive` a jamais. Un carnet,
lui, se renomme et change de visibilite depuis « Gerer ce carnet » : les
deux objets sont maintenant symetriques.

**Le slug ne suit PAS le nom.** Il est l'adresse publique de la base ;
le regenerer casserait toute URL deja partagee, sans redirection pour la
rattraper. Un test verrouille ce choix.

**La creation reste au nom seul**, et c'est delibéré : elle vit dans une
cellule de la grille, a cote des cartes, et au moment ou l'on cree une
base on ne sait pas encore quoi ecrire dans sa description. Elle passe
en revanche par un serializer, comme le reste du depot — elle lisait
`request.data` en direct.

Le formulaire est un PARTIAL PARTAGE entre les deux gestes : les champs
d'une base se presentent pareil qu'on la fabrique ou qu'on la corrige.
/ A base's name and visibility became editable, reaching parity with a
notebook. The slug stays frozen so shared links keep working; creation
stays name-only and now goes through a serializer.

### 5. Une base peut enfin etre supprimee

Le geste manquait, alors qu'un carnet l'a. **Les carnets survivent** :
le niveau « base » est facultatif dans le modele, seule l'appartenance
se defait — ils ressortent au niveau plateforme, la ou `/carnets/` les
montre. Les AXES DE CLASSEMENT de la base, eux, partent avec elle : ils
ne decrivent que cette base. Le libelle de confirmation annonce les
deux, comme celui du carnet annonce le sort de ses notes.

Le bouton est HORS du `<form>`, separe par un filet : a l'interieur, il
se soumettrait au clavier comme n'importe quel bouton du formulaire.
/ Deleting a base now exists and spares its notebooks; its own axes go
with it, and the confirmation says both.

### 6. Trois reglages trouves en parcourant les ecrans

- **Le formulaire d'edition etait illisible.** Il portait
  `.rangee-champ`, un flex HORIZONTAL prevu pour « etiquette, champ,
  bouton » sur un rang — ce qu'il faut au renommage d'un carnet, qui n'a
  qu'un champ. Avec quatre champs et leurs textes d'aide, les etiquettes
  se detachaient de leurs champs et « Description » finissait a l'autre
  bout de la ligne. Une classe `.formulaire-de-base` les empile.
- **Enregistrer etait muet.** La reponse re-rend la page et le panneau
  se replie : a l'oeil, rien ne distinguait « c'est enregistre » de « le
  clic n'a pas pris ». Un toast le dit, comme pour le carnet.
- **L'accueil gardait le fil d'Ariane.** Le logo « Hypostasia » de la
  barre est un `hx-get="/"`, pas un rechargement : le fil du carnet d'ou
  l'on venait restait affiche au-dessus de l'accueil.

/ Three fixes found by walking the screens: the edit form rode a
one-row flex and was unreadable, saving was silent, and the home screen
kept the breadcrumb of wherever you came from.

### 7. UN `code` INLINE NE COUPE PLUS LA PHRASE

Le defaut de lisibilite le plus grave de la lecture. Une phrase citant
trois noms de fichiers se lisait en SIX BLOCS empiles sur trois ecrans,
chacun avec sa gouttiere et son numero :

```
ordre 13  text  'Hypostasia V2 est un outil « un dossier contient… »'
ordre 14  code  'synthetiser_page_task'
ordre 15  text  'créait une nouvelle'
ordre 16  code  'Page'
ordre 17  text  'avec un'
ordre 18  code  'parent_page'
```

Le recollage des fragments d'une meme ligne EXISTAIT DEJA — Docling
range un `<strong>` et le texte qui l'entoure dans un groupe `inline`,
et `extraire_les_elements_bruts` les rejoint. Mais sa condition etait
`label == "text"`, et un backtick inline ne sort pas en `text` : il sort
en `code`. Il echappait donc a la regle, et `BALISE_PAR_LABEL["code"]`
valant `pre`, chaque nom cite devenait un bloc pleine largeur.

**DOCLING PORTE LUI-MEME LA DISTINCTION** — aucune heuristique de
longueur n'a ete necessaire : un `code` inline a pour parent un groupe
`inline`, un vrai bloc en triples backticks a pour parent `#/body` et
n'a aucun groupe. Le label du resultat fusionne est force a `text`,
sinon une phrase qui OUVRE sur du code partirait entiere en `<pre>`.

**PORTEE** : la correction vaut pour les ingestions A VENIR. Les pages
deja en base gardent leur decoupage — les reingerer detruirait et
recreerait leurs elements, donc casserait l'ancrage des extractions
existantes. Aucune commande de reconversion n'est fournie.
/ An inline backtick came out as a `code` item and escaped the existing
inline-rejoin rule, so every quoted filename became a full-width block.
Docling itself tells inline code from a real code block by its parent
group. Applies to future ingestions only: re-ingesting would break the
anchoring of existing extractions.

### 8. Deux gestes qui se taisaient

- **« Ajouter un carnet » disparaissait en silence** des que tous les
  carnets etaient deja dans la base : on ne pouvait pas distinguer une
  fonction absente d'un droit manquant. C'est la balise `empty` de la
  boucle qui porte le cas, comme la liste des carnets juste au-dessus.
- **La base creee ne se signalait pas.** La grille est rangee PAR NOM :
  une base nouvelle atterrit a sa place alphabetique, pas sous les yeux
  de qui vient de cliquer « Creer ». Sa carte s'eclaire 2,6 s, et un
  liseré fixe la remplace sous `prefers-reduced-motion` — la retrouver
  ne doit pas dependre du mouvement.

/ Two silent gestures: the add-notebook form vanished without a word,
and a newly created base landed alphabetically with nothing to point at it.

### 9. L'INTERIEUR DE LA CARTE D'EXTRACTION PASSE SUR LE SYSTEME

**Ce n'etait pas une regression** — verifie avant de toucher quoi que ce
soit. La carte elle-meme etait deja portee, et ses styles calcules sont
IDENTIQUES a ceux de l'etalon : bord gauche `3px rgb(153,153,153)`,
bord `0.75px rgb(228,224,216)`, rayon `5px`, fond `rgb(253,252,250)`.
Ce qui restait a l'ancien etat, c'est son CONTENU : ecrit en utilitaires
Tailwind arbitraires (`text-[10px]`, `bg-slate-50`, `text-slate-500`),
sans nom, hors du systeme, ne suivant le theme que par le remappage des
echelles. Le lot « 6 — Drawer et cartes » du cahier des charges
n'apparait nulle part dans l'etat « TERMINE (T4-T10) » : il n'avait
jamais ete livre.

`_card_body.html` sert **SEPT gabarits** — drawer, carte inline, bottom
sheet, resultats, previsualisation, test d'analyseur, wrapper. Le nommer
une fois les corrige tous.

**LES BADGES PASSENT EN CONTOUR.** Ils etaient des pastilles pleines par
un `style="background: …"` inline, que rien ne pouvait surcharger.
L'etalon les veut en contour et notait l'ecart comme « assume » ; le
mainteneur a tranche pour l'etalon. Le gabarit ne pose plus qu'une
`color` — la teinte depend de la FAMILLE, donc du contenu, et ne peut
pas vivre dans une feuille de style —, et le trait s'en deduit par
`currentColor` : une seule source, aucune divergence possible entre le
fond et le trait.

**DEUX ECARTS DE L'ETALON SONT CONSERVES**, parce qu'ils sont assumes et
ecrits dans l'etalon lui-meme :
- la CITATION reste toujours visible (l'etalon la replie au repos) ;
- la TYPOGRAPHIE suit la charte du projet (B612, B612 Mono, Lora) et non
  le `ui-monospace` de l'etalon, qui n'est qu'un substitut pour rester
  autonome. **Ce qui est porte ici, c'est la GEOMETRIE et les COULEURS.**

**UNE TENTATIVE ANNULEE, ecrite ici pour qu'on ne la refasse pas :**
avoir pose `.typo-lecteur-nom` / `.typo-lecteur-corps` (Srisakdi) sur le
commentaire — au nom de « trois polices, trois provenances » — donnait
un nom a 20px dans une carte large de quelques centimetres, illisible.
L'etalon, lui, ecrit `.commentaire .qui` en gras a `.7rem` sans changer
de police, et la seule autre vue qui emploie Srisakdi
(`vue_questionnaire.html`) corrige deja sa taille a la main par un
`style="font-size:14px"`. Ici, la provenance est portee par la FORME :
filet gauche, fond creux, nom en gras au-dessus du corps.

**UN TEST-MENSONGE CORRIGE, et il confirme le choix ci-dessus.**
`test_drawer_contenu_affiche_nom_commentateur` exigeait la classe
utilitaire `font-semibold` ; le gras vient desormais de la feuille de
style, la classe a disparu, le gras est reste. L'assertion figeait donc
un MOYEN quand la decision A.8 porte sur un RESULTAT. Sa docstring
disait deja, mot pour mot, « au lieu de la typo-lecteur-nom (Srisakdi
italique) » : la refonte A.8 avait tranche contre Srisakdi ici bien
avant cette session. Le test verifie maintenant les deux moities de
cette decision — le nom est ecrit, et il n'est pas repasse en Srisakdi.
/ The test pinned a utility class; the bold moved to the stylesheet. Its
own docstring already ruled out Srisakdi here, long before this session.

**Les accroches sont intactes** : `btn-commenter-extraction`,
`btn-ecouter-extraction`, `btn-masquer-drawer`,
`zone-commentaire-deroulable`, `commentaire-hors-filtre`,
`contributeur-actif-highlight`, `typo-machine`, `typo-citation`,
`indicateur-statut` — aucun selecteur JS ne visait les classes de
presentation remplacees.

/ Not a regression: the card's shell already matched the mock exactly;
its contents had never left ad-hoc Tailwind. The badges move to outlined
(the mock's call, previously logged as an accepted departure); the
citation stays visible and typography follows the project charter. A
Srisakdi attempt on comments was reverted — 20px in a centimetres-wide
card. Every JS hook was preserved.

### 10. LA GEOMETRIE PASSE AU PIXEL PRES

Mesures prises dans le MEME onglet, a `zoom=1` et `largeur=1692`, pour
que les deux rendus soient comparables.

| | Etalon | Avant | Apres |
|---|---|---|---|
| barre d'outils | 44px | **48px** | 44px |
| bande du fil d'Ariane | 30px | **32px** | 30px |
| padding de la carte | 8,8 / 10,4px | **8 / 12px** | 8,8 / 10,4px |
| indicateur de statut | 12,5px | **14px** | 12,5px |
| mot-cle (hauteur) | 17px | **15px** | 17px |

**Les 4px de la barre et les 2px de la bande se cumulaient** : le texte
commencait 6px plus bas que dans la maquette, sur tous les ecrans.

**`--barre-fil` n'etait DECLARE nulle part** : chaque usage tombait sur
son repli `var(--barre-fil, 2rem)`, soit 32px pour 30 attendus. Un repli
qui sert de valeur reelle est une valeur par accident.

**LE PIEGE DU BUILD TAILWIND FIGE.** Passer la barre de 48 a 44px
appelait `h-11` — et cette classe **n'existe pas dans le bundle**
(`.h-12` y est, `.h-11` non). Posee, elle est inerte : la barre est
tombee a la hauteur de son contenu, **33px**, mesure au navigateur. La
hauteur vient donc d'une regle nommee, `.barre-outils`, et le token
`--barre-outils` reste la seule source — la barre et le haut du panneau
qui se pose dessous ne peuvent plus diverger.

**LE SURVOL ET L'ETAT ACTIF suivent enfin l'etalon** : au survol, la
carte se LEVE (ombre) au lieu de repeindre son filet ; active, elle
porte un ANNEAU de 2px a 20 % au lieu d'un fond ambre. Ce fond peignait
toute la carte : la couleur du statut y devenait illisible, et deux
cartes actives d'affilee se lisaient comme une zone surlignee.

**`line-height` du mot-cle ECRIT, plus herite** : meme police, meme
taille, meme padding des deux cotes — et pourtant 15,5px dans l'etalon
contre 13,7px ici, parce que l'un herite d'un corps a 1,7 et l'autre du
1,5 de Tailwind. Un heritage qui differe entre deux contextes n'est pas
une valeur, c'est un hasard.

**CE QUI RESTE, ET POURQUOI.** Deux ecarts subsistent, tous deux
TYPOGRAPHIQUES, tous deux tenus par la charte du projet :

| | Etalon | Produit | Effet |
|---|---|---|---|
| badge d'hypostase | mono 8,96px | **B612 12px** | entete 23px au lieu de 20 |
| resume machine | mono 12px | **B612 Mono 14px** | bloc 46px au lieu de 36 |

Les aligner rendrait la carte identique au pixel — au prix de la charte
(« B612 : labels, tags d'hypostase, statuts »), et d'un badge a 9px.
C'est un arbitrage de conception, pas un defaut : il n'est pas tranche
ici.
/ Geometry now matches to the pixel. The toolbar's 4px and the strip's
2px stacked, starting text 6px too low; --barre-fil was never declared
and lived on its fallback. The obvious `h-11` fix is inert — the frozen
Tailwind build has no such class, and the bar collapsed to 33px. The two
remaining gaps are typographic and held by the project charter.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/templates/front/corpus/partials/carte_de_base.html` | 2 commentaires multi-lignes passes en balise `comment` |
| `front/templates/front/{acces_refuse,invitation_erreur,login,register}.html` | idem (bloc « bascule de theme ») |
| `front/templates/front/includes/onboarding_vide.html` | + includes de `_style_maquette.html` ET `_fil_ariane_oob.html` |
| `front/templates/front/corpus/{bases_liste,base_detail,carnets_liste}.html` | + include de `_fil_ariane_oob.html` |
| `front/static/front/css/maquette.css` | `.fil-ariane-conteneur` : `overflow: visible` ; troncature deplacee sur `.courant` |
| `front/templates/front/base.html` | `maquette.css?v=59` → `v=60` |
| `front/templates/front/corpus/partials/_formulaire_de_base.html` | **Nouveau** — le formulaire (creation, edition) + le geste de suppression |
| `front/templates/front/corpus/_style_maquette.html` | + `.formulaire-de-base` (colonne), `.groupe-visibilite`, `.choix-visibilite` (cible ≥24px, WCAG 2.5.8), `.separee-du-formulaire` |
| `front/serializers.py` | + `CreationDeBaseSerializer` ; `EditionDeBaseSerializer` apprend `nom` et `visibilite` |
| `front/views_corpus.py` | `create()` passe par un serializer ; `editer()` ecrit nom et visibilite + toast ; **`destroy()` nouveau** ; `retrieve()` expose `niveaux_de_visibilite` |
| `hypostasis_extractor/services/ingestion_docling.py` | + `LABELS_RECOLLABLES_EN_LIGNE` : un `code` inline rejoint la phrase |
| `front/templates/front/corpus/partials/carte_de_base.html` | + classe `est-nouvelle` sur la carte qui vient d'etre creee |
| `front/tests/test_edition_d_une_base.py` | +32 tests (43 au total) |
| `front/tests/test_effacement_du_fil_d_ariane.py` | **Nouveau** — 7 tests sur l'effacement du fil |
| `hypostasis_extractor/tests/test_ingestion_docling.py` | +4 tests (code inline vs vrai bloc) |
| `front/tests/test_corpus_phase_h.py` | +2 tests (la balise `empty` de l'ajout de carnet) |
| `hypostasis_extractor/templates/.../includes/_card_body.html` | l'interieur de la carte passe sur le systeme ; badges en contour |
| `front/static/front/css/maquette.css` | + section « L'INTERIEUR DE LA CARTE » : `.carte-entete`, `.badges`, `.badge-hypostase`, `.compteur-commentaires`, `.mots-cles`/`.mot-cle`, `.carte-commentaire`/`.qui`/`.quoi` |
| `front/templates/front/base.html` | `maquette.css?v=60` → `v=62` |
| `front/tests/test_phases.py` | `test_drawer_contenu_affiche_nom_commentateur` : verifie le resultat A.8, plus la classe utilitaire |

---

## Comment tester (a la main) / Manual test

### Test 1 — le commentaire n'est plus a l'ecran
1. Ouvrir `/bases/`.
2. Aucun texte commencant par `{#` ne doit paraitre au-dessus des cartes.
3. Meme controle sur `/` → onglet « Bases de connaissances ».

### Test 2 — l'onglet de l'accueil est style
1. Ouvrir `/`, cliquer l'onglet « Bases de connaissances ».
2. Les cartes doivent avoir leur cadre, leur cote teintee et leur pied —
   le meme rendu que sur `/bases/`, pas du texte a la suite.

### Test 3 — le fil d'Ariane
1. Ouvrir un carnet : le fil parait (« Base › Carnet ▾ »).
2. Cliquer le chevron : **le menu doit s'afficher en entier**, par-dessus
   le contenu, et non se couper a la hauteur de la bande.
3. Cliquer « Bases » dans la barre du haut : **le fil doit disparaitre**
   et la bande s'escamoter.
4. Refaire par `/carnets/` et par une base : meme resultat.

### Test 4 — creer une base
1. Sur `/bases/`, soumettre le formulaire VIDE : le navigateur doit
   bloquer (`required`), sans aller-retour serveur.
2. Saisir un nom, creer : la base parait dans la grille.

### Test 5 — renommer, decrire, ouvrir une base
1. Ouvrir SA base, deplier « Gerer cette base ».
2. Les quatre champs doivent s'EMPILER, chaque etiquette au-dessus de
   son champ — et non s'aligner sur un rang.
3. Le champ « Nom » est pre-rempli ; le niveau de visibilite en cours
   est coche.
4. Changer le nom, ecrire une description, choisir « public »,
   televerser une image, Enregistrer.
5. **Un toast doit confirmer** l'enregistrement (2,5 s, en haut a droite).
6. Verifier que **l'URL n'a pas change** et que l'ancien lien fonctionne.
7. Sur une base d'un AUTRE compte, le bloc « Gerer cette base » ne doit
   pas paraitre.

### Test 6 — supprimer une base sans perdre ses carnets
1. Creer une base, y ranger un carnet, lui creer un axe de classement.
2. « Gerer cette base » → « Supprimer cette base » (bouton rouge, sous
   un filet, a distance d'« Enregistrer »).
3. La confirmation doit ANNONCER le sort des carnets ET des axes.
4. Confirmer : retour a `/bases/`, toast de suppression.
5. **Aller dans « Carnets » : le carnet doit y etre, intact.**
6. L'axe de classement, lui, a disparu avec la base.

### Test 7 — l'accueil n'herite pas du fil
1. Ouvrir un carnet (le fil parait).
2. Cliquer le logo « Hypostasia » de la barre.
3. **Le fil doit disparaitre** : c'est un `hx-get`, pas un rechargement.

### Test 8 — un `code` inline ne coupe plus la phrase
1. Importer un markdown contenant :
   ``Le code `ma_fonction` renvoie un `Objet` complet.``
   plus un vrai bloc en triples backticks.
2. Ouvrir la note : **la phrase doit tenir en UN seul bloc**, avec un
   seul numero de gouttiere — et non un bloc par nom cite.
3. Le vrai bloc de code, lui, garde son cadre `<pre>` a part.
4. **Sur une note deja importee, rien ne change** : la correction ne
   vaut que pour les ingestions a venir.

### Test 9 bis — la carte d'extraction sur le systeme
1. Ouvrir une note analysee (`/lire/4/`), panneau des analyses ouvert.
2. **Les badges d'hypostase doivent etre en CONTOUR**, la couleur de la
   famille dans le trait — non plus des pastilles pleines.
3. Les mots-cles : fond creux discret, pas de gris Tailwind.
4. Un commentaire : filet gauche, fond creux, **nom en gras petit**
   (surtout PAS en Srisakdi 20px).
5. Cliquer une pastille du texte : la carte prend le halo ambre et **sa
   citation apparait** en Lora italique.
6. Verifier les MEMES cartes dans les six autres contextes du partial :
   carte inline, bottom sheet mobile, resultats d'analyse,
   previsualisation d'analyseur, test d'analyseur.
7. Verifier que « Commenter », « Ecouter » et « Masquer » fonctionnent
   toujours — leurs classes n'ont pas bouge.

### Test 9 — les deux gestes qui se taisaient
1. Ranger TOUS ses carnets dans une base, puis ouvrir cette base :
   a la place du selecteur, lire « Tous vos carnets sont deja dans
   cette base ».
2. Sur `/bases/`, creer une base dont le nom commence par Z : sa carte
   doit **s'eclairer quelques secondes** a sa place alphabetique.
3. Recharger `/bases/` : plus aucun eclat.

### Verifs DB

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import BaseDeConnaissances
for b in BaseDeConnaissances.objects.all():
    print(b.nom, '|', b.slug, '|', b.visibilite, '|', bool(b.image_de_couverture))
"
```

### Tests automatiques

```bash
make test-suite S=front.tests.test_edition_d_une_base        # 41 tests
make test-suite S=front.tests.test_effacement_du_fil_d_ariane # 7 tests
make test-rapide                                              # non-regression
```

