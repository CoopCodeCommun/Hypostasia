# La preuve dans son contexte / The evidence, in context

**Date :** 2026-08-20
**Migration :** Non

## Resume / Summary

**Quoi / What :** la fiche de preuve se lit desormais comme une **carte
d'extraction** — indicateur de statut, badges d'hypostase, resume machine,
citation en Lora. La citation est montree **dans son contexte** : un peu du
texte d'avant et d'apres, en gris, et **cliquer la citation ouvre le passage
long**. La source passe **sous le texte**. Toute la verification — degre,
seuil, cinq juges — tient dans un **pli dont le resume est l'etat** (« Faible ▸ »).
/ The proof card now reads like an extraction card, shows the quote in its
document context with a click-to-expand passage, and files all verification
behind a fold whose summary is the verdict itself.

**Et surtout :** le tiroir est mort. Les preuves sont **toutes rendues, dans
l'ordre du texte, dans une colonne de la page** — plus de `position: fixed` pose
sur un voile qui grisait l'article. Le renvoi `[N]` est une **ancre** vers sa
fiche, et le lien va dans les deux sens : cliquer un renvoi amene sa fiche en
tete de colonne, cliquer une fiche ramene au passage qu'elle prouve.
/ The drawer is gone: every card is rendered in a column of the page, and the
link works both ways.

**Pourquoi / Why :** le panneau n'avait aucune des marques qui font reconnaitre
une extraction ailleurs dans le produit, et il empilait douze lignes de
verification **a la meme taille et dans la meme couleur que la citation**.
Surtout, **ouvrir une preuve rendait illisible la phrase qu'on verifiait** — or
verifier, c'est comparer l'affirmation et sa source, donc les avoir sous les
yeux en meme temps.
/ Above all, opening a piece of evidence made the sentence being checked
unreadable — yet checking means having claim and source in view together.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/contexte_de_citation.py` | **Neuf.** Le texte qui entoure la citation, en deux longueurs (apercu / deplie), avec repli sur l'element voisin |
| `core/models.py` | `AvisDeVerification.version` et `.libelle` — decoupe le nom du juge |
| `core/services/verification.py` | `accord_des_juges_locaux(lien, seuil=None)` — le seuil se passe au lieu de se relire |
| `core/services/nouveautes_du_perimetre.py` | **Neuf.** Ce qui est apparu dans le perimetre depuis un acte, et la date du dernier verdict |
| `front/static/front/js/theme.js` | **Refonte.** Deux etats, clair par defaut, `aria-pressed` |
| `front/static/front/js/spinner_au_clic.js` | **Neuf.** Le spinner au point de clic, pour toute requete HTMX |
| `front/static/front/css/spinner_au_clic.css` | **Neuf.** Deux anneaux, delai, `prefers-reduced-motion` |
| `front/templates/front/base.html` | clair par defaut sur `<html>`, bascule a deux etats |
| `front/static/front/css/maquette.css` | la bascule de theme visible sous 640px ; `--panneau: var(--preuve)` sur un article ; pas de voile sur un article |
| `front/static/front/js/drawer_vue_liste.js` | le controle bascule ; un article n'exige pas de `page_id` et ne recharge pas le tiroir |
| `front/templates/front/includes/drawer_vue_liste.html` | la bande de contexte du panneau |
| `front/views_corpus.py` | `nombre_de_commentaires` sur la ligne de note |
| `front/templates/front/corpus/partials/notes_du_carnet.html` | le compte de commentaires, le bouton d'epinglage |
| `front/templates/front/corpus/carnet_detail.html` | retrait des deux boutons de creation |
| `front/templates/front/corpus/liste_wikis.html`, `liste_syntheses.html` | l'article s'ouvre en plein ecran |
| `front/templates/front/corpus/partials/ecartees.html` | **Refonte.** Groupees par document, chacun depliant |
| `front/views_synthese.py` | `contexte_d_une_preuve`, `_version_commune_des_avis`, le renvoi devient une ancre, l'article porte la liste de ses preuves |
| `front/templates/front/corpus/partials/preuve.html` | **Refonte.** La carte, le contexte depliant, le pli de verification |
| `front/templates/front/corpus/partials/_verification_detaillee.html` | **Neuf.** Le contenu du pli, sorti de `preuve.html` |
| `front/templates/front/corpus/_style_maquette.html` | la carte, la typographie de la charte, `.explication`, **la grille a deux colonnes** |
| `front/templates/front/corpus/article.html` | **la colonne des preuves** et le script de liaison dans les deux sens ; l'aide « ? » dit la nouvelle geographie |
| `core/tests/test_contexte_de_citation.py` | **Neuf**, 14 tests |
| `front/tests/test_la_preuve_en_contexte.py` | **Neuf**, 41 tests |
| `front/tests/test_une_extraction_citee_deux_fois.py` | le releve des renvois suit l'ancre, plus le `hx-get` |

### Les mesures qui ont decide de la forme / The measurements behind the design

**Au navigateur** (Chromium, `getComputedStyle`, formule WCAG) :

| mesure | resultat | ce qu'elle a decide |
|---|---|---|
| `.explication` dans le panneau | **13,6px en `--encre`** — la taille ET la couleur de la citation | la regle est `.zone-corpus .ecarte .explication`, le panneau est **hors** de ce scope : la classe etait **inerte**. C'etait LE defaut de lisibilite |
| police de la citation du panneau | **Georgia** | `.panneau-preuve` impose `font-family:Georgia`. La carte de lecture rend son resume en **B612 Mono 14px** et sa citation en **Lora 16px** — trois polices = trois provenances ne s'appliquait pas ici |
| `.carte-preuve` | stylee dans `_style_maquette.html:296`, **utilisee par aucun gabarit** | l'etalon prescrit cette carte pour ce panneau depuis le debut |
| filet separant la reference des locaux, en `--filet` | **1,19:1** clair · **1,31:1** sombre | present dans le DOM, **invisible a l'ecran** — un test l'aurait atteste sans qu'il fasse rien. Repose sur `--encre-douce` mele au fond : **3,36:1** et **4,15:1**, au-dessus des 3:1 de WCAG 1.4.11 |
| renvoi en tension (`--faible`) | **4,90:1** clair · **10,88:1** sombre | *la verification en retard du 20 aout — elle passe* |
| renvoi normal (`--info`) | 7,71:1 · 9,11:1 | — |

**Sur les donnees reelles** (225 citations) :

| mesure | resultat | ce qu'elle a decide |
|---|---|---|
| citations portant hypostases + resume | **225/225**, exactement **2 badges** chacune | aucune carte ne sera depareillee |
| longueur du resume | 34 a 102 signes, mediane 64 | il tient sur deux lignes de 416px |
| contexte pris dans le SEUL element d'ancrage | **94/225 sans rien avant**, **116/225 sans rien apres** | le repli sur l'element voisin n'est pas un raffinement : sans lui le contexte serait vide **une fois sur deux** |
| contexte avec repli sur le voisin | **2 sans avant**, **4 sans apres** | c'est ce qui rend la fonction utile |
| fiches rendues apres refonte | **225/225**, dont **206** avec l'accordeon et **16** sans pli de verification | les 16 sont celles sans aucun avis ni degre |

### La colonne, et ce qu'elle a coute / The column, and what it cost

| mesure | avant | apres |
|---|---|---|
| requetes pour rendre l'article de demonstration (63 citations, 6 notes) | **213** | **32** |
| duree de rendu cote serveur | **0,91 s** | **0,40 s** |

Trois N+1 s'y cachaient, et **aucun ne se voyait a la lecture du code** :

- `.order_by()` sur un manager lie **construit un nouveau queryset** et ignore le
  cache du `prefetch_related` — 64 requetes d'ancrages. Seul `.all()` rend le cache ;
- l'element voisin etait cherche en base **pour chaque fiche** — 65 requetes pour
  6 notes. Une memoire creee et jetee par l'appelant suffit ;
- `accord_des_juges_locaux` relisait la `Configuration` **a chaque appel** —
  59 requetes pour une valeur qui ne peut pas changer pendant un rendu.

Verrouille par `test_le_nombre_de_requetes_ne_croit_pas_avec_les_citations` :
passer de 2 a 12 citations ne doit pas coûter 10 requetes de plus.

### La disposition, mesuree au navigateur

| largeur | mode | article | colonne |
|---|---|---|---|
| 1600px | grille | 976px | 416px |
| 1280px | grille | 728px | 416px |
| 1279px | une colonne | 976px | sous l'article |
| 390px | une colonne | 310px | sous l'article |

Aucun debordement horizontal a aucune de ces largeurs. Le seuil est **1280px** et
non les 1400px du panneau des notes : la colonne de lecture d'un article est plus
etroite, il reste 728px de texte a 1280px.

**Contrastes de la colonne** — numero de renvoi, provenance, compte des preuves,
entete, lien source et filet de la fiche marquee : **12 mesures, deux themes,
toutes au-dessus du seuil**, minimum **4,91:1** (la provenance, en clair).

**Contrastes de la fiche refondue** — 13 elements, deux themes, 26 mesures,
**toutes au-dessus du seuil**. Le minimum est l'etat « Faible » a **4,73:1** en
clair (seuil 4,5:1 pour un texte de 9,3px). Les huit familles d'hypostases vont
de **6,31:1 a 7,71:1** en clair et de **9,11:1 a 12,53:1** en sombre sur le fond
de la carte.

### La deuxieme salve : l'ecran d'article, et ce qui l'entoure

| Demande | Ce qui a ete fait |
|---|---|
| clair par defaut, meme si le systeme est sombre | deux etats au lieu de trois ; le defaut est ecrit **dans le HTML** (`<html data-theme="light">`), pas seulement dans `theme.js` — sans lui, le `@media (prefers-color-scheme: dark)` s'appliquait avant que le script ne tourne, et sans lui s'il est bloque |
| le bouton de theme visible sur mobile | il etait `display:none` sous 640px. **26 × 26 px**, contraste **16,79:1**. Les pixels viennent des liens « Bases / Carnets », repris par le fil d'Ariane juste dessous |
| la legende dans l'aide « ? » | elle etait a plat au-dessus du texte : sept etats a parenthese imposes avant la premiere phrase. Elle devient la premiere section du depliant, **en liste** — en rangee, elle cassait n'importe ou et le libelle se separait de son trait |
| les gestes couteux en lignes d'en-tete | les deux boutons pleins disparaissent. L'en-tete devient le tableau de bord complet : Ecartees · Couverture · Verifier. **Seule l'exception est coloree** — la valeur passe en bleu gras quand relancer a une raison d'etre |
| une boite de dialogue conditionnee | cliquable dans **tous** les cas : griser un geste sans dire pourquoi n'apprend rien. Sans nouveaute, le bouton « Rien a relancer » est desactive et la phrase au-dessus donne le motif |
| les ecartees par document | la liste etait plate : jusqu'a 200 lignes ou chaque citation redisait le nom de sa note. Groupees, **le plus ecarte en tete** — 33 · 17 · 16 · 5 · 4 sur l'article de demonstration |
| l'article en plein ecran | il etait injecte dans **l'onglet du carnet** : on lisait la synthese sous l'en-tete du carnet, ses onglets et ses formulaires. Il vise desormais `#zone-lecture`, et le bouton de retour aussi — il pointait sur un conteneur qui n'existait plus une fois l'article ouvert |
| retirer « Nouveau wiki / Nouvelle synthese » | ces deux boutons n'ouvraient aucun chemin : ils activaient l'onglet portant deja le formulaire |
| le compte de commentaires sur la ligne de note | il n'existait que sur la **carte** de chaque extraction : une note tres commentee ne se distinguait en rien d'une note que personne n'a lue. Affiche seulement quand le debat a commence |
| l'epinglage d'une note | **le geste manquait, l'ordre l'attendait deja** : le champ `epinglee`, le tri `-epinglee`, la marque « ✱ » et la route `POST /notes/{id}/carnets/{id}/epingler/` existaient tous — aucun bouton ne les appelait, donc rien ne pouvait jamais etre epingle |
| un spinner au point de clic | `front/static/front/{css,js}/spinner_au_clic.*` — **aucun gabarit a modifier** : toute requete HTMX en herite. Delai de 220 ms pour ne pas clignoter, un spinner par requete reconnu a son `xhr`, et les ecrans qui ont deja leur `hx-indicator` gardent le leur. Mesure : requete rapide → **aucun spinner cree** ; requete lente → il apparait puis disparait a la reponse |
| le panneau colle a droite, comme celui des extractions | il flottait de **92 px** a 1600. Il passe par `#drawer-overlay`, en OOB swap : `right == innerWidth` aux 4 largeurs, dans les 2 themes, sur l'article comme sur la note |
| la croix du panneau devient un toggle | visible ouvert **et** ferme, sur les deux ecrans ; `aria-expanded` tenu a jour |

**LE PANNEAU DE PREUVE PASSE PAR LE MECANISME DU PANNEAU DES NOTES.** Il etait
une colonne de `.zone-corpus`, laquelle est centree avec un `max-width` : il
**flottait** au lieu d'etre colle au bord droit. Mesure avant, sur
`/syntheses/8/` — `right` 1508 pour une fenetre de 1600 (**92 px d'ecart**), 1344
pour 1400 (56 px) ; la reference `/lire/1/` etait a 1600 et 1400 pile.

Il rejoint donc `#drawer-overlay`, par **OOB swap** — le chemin qu'empruntent
deja `_fil_ariane_oob.html` et `_lecteur_audio_oob.html`. Un seul panneau a
maintenir, une seule bascule, et le regime tiroir en dessous du seuil vient avec.

Mesure apres, **verifiee independamment** : `right == innerWidth` aux quatre
largeurs (1600, 1400, 1279, 390), **dans les deux themes**, sur l'article **et**
sur la note — les deux panneaux rendent exactement les memes chiffres. Aucun
debordement horizontal. Le voile est en `display: none` sur un article a toute
largeur : le texte reste lisible a cote (824 px a 1399, 704 px a 1279).

⚠️ **Le seuil des preuves passe de 1280 px a 1400 px**, celui du panneau des
notes. C'est la consequence directe de « le meme code » : le seuil ne peut pas
etre a deux endroits a la fois. A 1400 px, la colonne de texte garde 984 px.

**LA CROIX DU PANNEAU DEVIENT UN INTERRUPTEUR**, visible qu'il soit ouvert ou
ferme, sur l'article comme sur la note. Fermer sans pouvoir rouvrir n'est pas
une bascule : c'est une porte a sens unique. `aria-expanded` verifie dans les
deux sens ; contraste du glyphe **5,01:1** en clair, **5,69:1** en sombre.

**Un piege de Django trouve en chemin, et il ne leve aucune erreur.** Une balise
`{% … %}` doit tenir sur **UNE SEULE LIGNE** : le `tag_re` du moteur n'a pas
`re.DOTALL`, donc une balise qui enjambe deux lignes **n'est pas reconnue** et
sort telle quelle **en texte dans la page**. `get_template()` ne le voit pas non
plus — rien n'a echoue, ce n'etait simplement plus une balise. Les 63 fiches de
preuve s'affichaient en code source.

### Le code mort retire

- `contexte_autour_de_la_citation()` — fonction publique **sans aucun appelant**
  depuis que la colonne rend deux longueurs ; ses tests sont reportes sur
  `passage_en_apercu_et_deplie` ;
- **le predicat « un second avis tourne-t-il ? » existait en TROIS exemplaires** —
  le verrou de re-clic, la fiche, la colonne. Le commentaire disait deja « la meme
  borne de deux heures que le verrou » : unifies dans `un_second_avis_est_en_cours()` ;
- `.voile-preuve`, `.panneau-preuve .entete button`, `.est-ouvert`, `.est-visible` :
  le CSS du tiroir mort ;
- le double scope `.zone-corpus .carte-preuve, .panneau-preuve .carte-preuve` — le
  panneau est desormais **dans** `.zone-corpus`, les deux moities designaient les
  memes elements ;
- l'en-tete d'`article.html` annoncait `operations_appliquees`, que ce gabarit ne
  lit pas.

Balayage automatique : **0 classe orpheline sur 150** dans `_style_maquette.html`,
aucune fonction privee sans appelant dans `views_synthese.py`, aucun import inutile.

### La verification s'enchaine, et ne rejuge que ce qui a bouge

Verifier etait un GESTE : un bouton, un clic, et rien avant. Un article produit
restait donc **sans aucun verdict** tant que personne n'y pensait — et le lecteur
decouvrait un texte dont pas une phrase n'etait qualifiee, sans savoir que
c'etait a lui de le demander. `_lancer_une_verification` n'avait que **deux
appelants**, les deux endpoints `verifier`.

Le jugement s'accroche desormais a `_ecrire_le_corps_d_un_article`, **le seul
endroit ou un corps d'article s'ecrit et ou ses citations s'indexent** : la
production comme la mise a jour appliquee y passent. Un point, deux moments.

**IL NE JUGE QUE LES CITATIONS SANS VERDICT, et c'est ce qui le rend tenable.**
Une mise a jour qui touche un paragraphe ne repaie pas le jugement des soixante
autres citations. « Non verifie » suffit a dire « modifiee » : l'indexation y
remet toute citation dont l'affirmation a bouge, et les neuves y naissent. Tenir
en plus une liste des liens touches serait une seconde source de verite, qui
divergerait de l'etat qu'elle decrit.

Le filtre s'applique sur la **sortie** de `preparer_les_paires_a_juger`, jamais
dedans : cette fonction sert aussi le gel de l'etalon des juges, qui doit poser
EXACTEMENT la meme question que la fois d'avant.

⚠️ **C'EST UNE FACTURE.** Le juge de production est un vrai modele : un article
produit est un article juge. Le regime incremental est ce qui borne la depense.
Sans juge affecte au role, **rien n'est mis en file** — un job voue a echouer
ferait un bandeau d'erreur a chaque production.

Le bouton devient « **Revérifier** » : il rejuge TOUT, ce qui n'a d'interet
qu'apres un changement de juge ou de seuil. Verrouille par
`core/tests/test_verification_enchainee.py`, **8 tests**.

### La tournee au navigateur : ce qu'elle a trouve

8 ecrans × 2 largeurs : aucun debordement horizontal, aucune balise brute,
aucune erreur JS, aucun titre vide. Parcours complet note → carnet → onglet →
article → retour → wiki → precedent/suivant : URL juste, **un** article, **une**
zone de lecture, titre du panneau exact a chaque etape.

**Trois defauts reels, corriges :**

| defaut | mesure | correction |
|---|---|---|
| la bascule du panneau | **18 × 18 px** — sous les 24 de WCAG 2.5.8, et c'est le SEUL moyen de rouvrir le panneau | 24 × 24 |
| les lignes de l'en-tete | **16 px** (depliant) et **23 px** (action) de haut | 24 px, ligne comprise |
| l'article s'imbriquait dans lui-meme | le `<div>` de sondage fait `hx-swap="outerHTML"` **sans cible** : a la fin d'une tache, `/etat/?apres=article` repond par l'article ENTIER, qui venait se loger DANS `#synthese-zone-maj` — deux articles, deux colonnes de preuves | `hx_target="#zone-lecture"` quand la reponse est un article |

Plus une marque de focus manquante sur le depliant des juges — le seul des trois
de la fiche a n'en avoir aucune. Au vrai Tab, **45 elements traverses, tous
marques**.

**Trois fausses alertes, ecartees par la mesure**, et elles disent ce que vaut un
audit automatique : les puces de categorie rendues « a 1,87:1 » mesurent en fait
**12,89 a 16,79:1** (le marcheur de fond de la sonde se trompait de couche) ; et
les « boutons sans nom accessible » sont des `<summary>` dans un `<details>`
FERME, dont `innerText` rend une chaine vide.

### La troisieme salve : trois bugs, quatre allegements

| defaut | mesure | correction |
|---|---|---|
| le corps de l'article n'etait pas centre | **136 px hors centre**, panneau ouvert ET ferme, quand une note tombe a 0 | `.article-synthese` fait 44rem dans une zone de 64 : sans `margin:auto`, elle se collait a gauche. **0 px** dans les quatre cas |
| le spinner survivait au retour arriere | il vit sur `<body>`, hors de la zone echangee ; un retour ne produit aucune reponse, donc rien ne le retirait | `popstate`, `pageshow` et `htmx:historyRestore` l'effacent sans condition |
| les deux panneaux n'avaient pas la meme largeur | analyses **368 px**, preuves **416 px** — le bord de la zone de lecture sautait de 48 px en passant d'une note a un article | `--panneau: var(--preuve)` : **416 px** des deux cotes, et l'override par article devient inutile, retire |

**Les quatre allegements**, valides par le mainteneur :

- **le bandeau d'attente apprend la fin par le WebSocket.** Il sondait toutes les
  3 s pendant 5 minutes — **jusqu'a cent requetes** pour une production — puis
  renoncait sur une echeance arbitraire. `hypostasia.js` rediffuse
  `tache_terminee` en evenement DOM, le bandeau porte
  `hx-trigger="tacheTerminee from:body, load delay:25s"`. Le sondage lent qui
  reste n'est plus qu'un filet pour un socket coupe ;
- **le titre du document sort de la barre sous 640px** : il n'y affichait plus
  que deux lettres — « Ba » pour « Badgeons la Normandie » — et le fil d'Ariane,
  juste dessous, le donne en entier ;
- **le voile disparait des DEUX panneaux, a toute largeur.** Il ne visait que
  l'article ; les analyses le gardaient sous 1400px, alors que les deux panneaux
  partagent desormais une place, un interrupteur et une largeur. Deux
  comportements pour un meme objet, c'est un objet qu'on n'apprend pas ;
- **un carnet ne charge plus les analyses d'une note qu'on ne lit pas.**
  `getPageId()` interrogeait `#zone-lecture [data-page-id]` — or un ecran de
  carnet LISTE ses notes, et chaque ligne porte cet attribut : le panneau
  chargeait donc **126 cartes** pour la premiere ligne. La portee devient le
  conteneur de lecture. Mesure : **0 requete** `drawer_contenu` sur un carnet.

**Un bug que j'ai introduit en corrigeant le precedent, et qu'il faut dire.**
Poser `hx-target="#zone-lecture"` en gardant `hx-swap="outerHTML"` **detruit le
`<main>` lui-meme** : la grille du plateau perd sa colonne, et les swaps OOB qui
suivent visent des conteneurs disparus — la colonne des preuves revenait **vide**
apres un rafraichissement. Le swap suit desormais la cible (`innerHTML` des qu'il
y en a une). Verifie : 1 zone de lecture, 1 article, **63 fiches**, panneau colle.

Balayage final — 7 ecrans × 2 largeurs × 2 themes : aucun debordement, aucune
balise brute, une seule zone de lecture, un seul article, aucune erreur JS.

### La fiche au repos : la citation, et rien d'autre

Le contexte s'affichait par defaut, en gris, de part et d'autre de la citation :
**trois blocs de texte pour une citation, sur soixante fiches**. La citation — la
seule chose qui PROUVE quelque chose — s'y perdait. Elle est desormais seule au
repos ; le passage vient au clic, et largement : puisqu'il faut le demander, ce
qu'on ouvre doit valoir le geste.

Le service perd donc sa double longueur : `passage_en_apercu_et_deplie` (quatre
chaines, un drapeau « il y a plus a voir ») devient
**`passage_autour_de_la_citation`** — `avant`, `apres`, et `il_y_a_un_passage`,
qui dit seulement s'il y a de quoi ouvrir. La borne d'apercu (90 signes) et sa
constante disparaissent.

### Un seul geste sur une preuve, deux effets ensemble

Activer une preuve, c'est **ouvrir son passage ET surligner son ancre** dans le
texte. C'etaient deux gestes distincts — cliquer la citation ouvrait le passage,
cliquer ailleurs sur la fiche ramenait au texte — et **rien ne disait laquelle
des deux moities on allait obtenir**.

**Et les passages precedents se replient.** Sans cela, parcourir dix preuves
laissait dix passages ouverts : la colonne devenait un mur, et la fiche qu'on
venait d'activer se retrouvait poussee hors de vue par celles d'avant.

Re-cliquer la fiche ACTIVE replie son passage — c'est la seule facon de le
refermer sans en activer une autre. Le `<summary>` du passage passe par le meme
chemin que le reste de la fiche : c'est tout le propos de n'avoir qu'un geste.
Les depliants de la VERIFICATION, eux, gardent leur bascule native — ils ne
parlent pas du passage.

Mesure au navigateur, sur les 63 fiches de l'article de demonstration :

| geste | contextes visibles | passages ouverts | fiches actives | renvois marques |
|---|---|---|---|---|
| au repos | **0** | 0 | 0 | 0 |
| clic sur une fiche | 2 | **1** | **1** | **1** |
| clic sur une autre | 2 | **1** | **1** | **1** |
| clic sur un renvoi `[N]` | 2 | **1** | **1** | **1** |
| re-clic sur la fiche active | 0 | **0** | 1 | 1 |

### La carte d'extraction recoit le meme geste

Le panneau des analyses n'ouvrait que la CITATION sur sa carte active
(`maquette.css`, « la citation ne s'affiche QUE sur la carte choisie »). Elle
ouvre desormais le PASSAGE avec elle — un peu du document de part et d'autre,
en gris, exactement comme la fiche de preuve. Un lecteur apprend un geste, pas
deux.

`entity.passage` n'est pose **que par le panneau des analyses**. Ce gabarit sert
**sept ecrans**, et les six autres n'ont pas de document a lire autour d'une
citation — un test d'analyseur juge un texte colle a la main. Le `{% if %}` n'est
donc pas une precaution, c'est la regle.

Mesure sur la note de demonstration, **69 cartes** :

| | cartes actives | citations visibles | contextes visibles |
|---|---|---|---|
| au repos | 0 | **0** | **0** |
| clic sur une carte | 1 | 1 | **2** |
| clic sur une autre | **1** | 1 | **2** |

Cout : **42 requetes en 0,15 s**, dont **2 seulement** pour les elements — la
memoire par note tient, la ou 69 cartes auraient fait 138 requetes.

### L'installation depuis zero, et ce qu'elle a revele

`docker compose down -v` → `up` → `make install`, sur une base vide. Les TROIS
workers Celery repartent. Etat final : 6 notes, 1 carnet, 1 wiki, 1 synthese,
149 extractions — et **83 citations, toutes avec un verdict** (50 faible ·
30 verifie · 3 introuvable), posees par **deux jobs de verification apparus
tout seuls**. Avant ce chantier, un article fraichement installe restait sans
un seul verdict jusqu'a ce que quelqu'un y pense.

**UN TROU QUE SEULE L'INSTALLATION REELLE POUVAIT MONTRER : zero avis local.**
L'enchainement lancait le juge de production mais **pas les quatre juges
locaux**, alors que le geste manuel lance les deux. Conséquence : sur un article
neuf, le renvoi `[N]` ne pouvait **jamais** s'ambrer et la fiche annoncait
« comparaison impossible ». Tout le signal de tension pose le 20 aout etait mort
sur les seuls articles qu'on vient de lire.

Les quatre juges partent desormais avec la verification. Ils ne coutent rien a
la facture — machine locale, worker dedie a concurrence 1, sous `nice -n 19`.

⚠️ **LE FAN-OUT RESTE HORS DE `verifier_les_citations_task`.** C'est la
contrainte a ne pas defaire : `bin/install.sh` appelle cette tache DIRECTEMENT
a chaque demarrage de conteneur, et un fan-out place dedans remettrait l'etalon
entier en file a chaque fois. L'accroche est sur l'ECRITURE d'un article, qui
n'arrive qu'une fois par production.

Mesure sur un wiki produit apres correction, base fraiche — **54 citations** :

| | resultat |
|---|---|
| verdicts | 17 verifiees · 25 faibles · 8 introuvables · **4 sans verdict** |
| avis locaux crees | **184**, sur 46 des 54 citations |
| tension calculee | **10 tensions** · 32 accords · 12 incalculables |
| jobs enchaines | production → verification → second avis, **3 jobs, tous `completed`** |

Le bilan du job porte `regime: "seulement les non jugees"` : le compte se relit
apres coup en sachant ce qu'il couvre. Les **4 sans verdict** sont le cas
documente — le juge n'a pas rendu de note pour ces paires, et leur etat
precedent est conserve tel quel : un echec technique n'est pas un resultat.

### La suite complete

**2523 tests · 1 erreur · 15 sautes**, contre 13 echecs au premier passage.

La derniere n'est pas une regression : un **deadlock PostgreSQL** dans le `flush`
de fin d'un `StaticLiveServerTestCase`, ou le thread du serveur de test tient
encore un verrou pendant que le thread de test tronque les tables. Il a frappe
**un test DIFFERENT a chaque passage** — `test_20_tracabilite` puis
`test_13_auth` — et les deux passent en isolation. A porter dans
`CHANGELOG/DEFAUTS-DIFFERES.md` : sur une suite complete, un e2e tombe au
hasard, et quelqu'un finira par le prendre pour une vraie regression.

### Ce que la relecture adverse a change / What the adversarial review changed

Quatre propositions ont ete **modifiees ou abandonnees avant d'etre codees** :

- **masquer l'indicateur de statut quand il vaut « nouveau »** (225/225 le sont) —
  **abandonne.** « Ne signaler que l'exception » parle de **couleur** ; le cercle
  est gris et code par la **forme**, le principe etait deja respecte. Et la
  commande etait la ressemblance : une troisieme grammaire l'aurait contredite.
  Verifie a l'ecran : des qu'une extraction porte un commentaire, le triangle
  ambre apparait et porte une vraie information ;
- **une etiquette de nom au-dessus de chaque barre** — **allege** : le nom passe
  en tete de la phrase existante, en gras. Zero pixel ajoute, meme gain. Motif
  qui manquait : les avis sont tries **par score decroissant**, donc l'ordre des
  barres change d'une citation a l'autre et la position ne dit rien ;
- **les mots-cles** — **retires.** L'etalon de cet ecran enumere ce qu'une carte
  de preuve contient et n'y met aucun hashtag. Arbitrage du mainteneur ;
- **un fond colore sur la ligne de reference** — **remplace par un filet.**
  Marquer fort la reference dans un bloc dont le resume est l'ACCORD recreerait
  l'argument d'autorite que le § 7.2 tient a distance.

⚠️ **Aucun invariant n'est revoque** : aucun chiffre n'entre dans le corps de
l'article, le renvoi ne s'ambre que sur la tension, chaque juge garde son propre
seuil, et les avis locaux se lisent toujours **a cote** du juge de production.
Les **49 tests** du 20 aout passent sans modification.

### Deux defauts trouves en chemin, et corriges

- **Un `aria-label` sur le `<summary>` du passage.** Il REMPLACE le nom
  accessible — et le nom accessible, ici, c'est la CITATION. Un lecteur d'ecran
  n'aurait jamais entendu la citation, dans un panneau dont elle est l'objet.
  Retire : `<details>` annonce deja son etat plie/deplie nativement. Verifie au
  navigateur — le nom accessible du depliant est bien le contexte suivi de la
  citation.
- **« Pas encore verifie » sur une citation INTROUVABLE.** Deux cas tombent dans
  la branche « rien a plier » — aucun degre, aucun avis — et un seul est non
  verifie : le degre est absent pour tout verdict pose **sans juge** (citation
  introuvable, contestation humaine). Proposer « utilisez Verifier les
  citations » a une citation deja jugee ferait relancer un juge qui a repondu.
  Verrouille par `test_une_citation_INTROUVABLE_n_est_pas_dite_non_verifiee`.

### Ce qui n'a pas ete fait, et pourquoi

- **La cible de clic du renvoi `[N]` reste a 25,9 × 19,5 px.** Ce n'est pas une
  non-conformite : WCAG 2.2 SC 2.5.8 a une exception *inline* explicite pour une
  cible prise dans une phrase. Elle serait portee a 24px de haut par un
  `padding: .45rem .35rem` avec une marge negative assortie — l'interligne et la
  taille du texte ne bougeraient pas. **Hors du perimetre de ce chantier** ; a la
  main du mainteneur.
- **Les deux phrases didactiques permanentes** (« le seuil est un reglage
  d'affichage… », « ces juges tournent sur cette machine… ») sont conservees.
  Elles reculent d'elles-memes maintenant que `.explication` est stylee, et les
  deplacer dans l'aide retirerait une garantie de lecture, pas un defaut.
- **`ruff` n'est pas installe** dans ce depot (`make check` n'appelle que
  `manage.py check`) : rien a lancer.

---

## Comment tester (a la main) / Manual test

### Test 1 — les tests automatiques
```bash
docker compose exec -T web python manage.py test \
    core.tests.test_contexte_de_citation \
    front.tests.test_la_preuve_en_contexte \
    front.tests.test_une_extraction_citee_deux_fois \
    core.tests.test_degre_agrege front.tests.test_tension_sur_le_renvoi \
    front.tests.test_les_cinq_juges_en_un_clic \
    front.tests.test_degre_a_l_ecran front.tests.test_second_avis_a_l_ecran
```
Attendu : **104 tests OK** (55 neufs + les 49 du 20 aout, inchanges).

Les trois qui protegent le plus :
- `test_une_ancre_DETACHEE_ne_rend_aucun_contexte` — sans lui, un document
  edite ferait afficher un decor **decoupe sur des positions perimees**, presente
  comme une preuve, dans le panneau dont c'est tout le propos ;
- `test_des_versions_DIFFERENTES_restent_sur_chaque_ligne` — factoriser une
  version qui n'est pas commune mentirait sur trois juges sur quatre ;
- `test_le_html_de_l_article_ne_contient_pas_le_degre` (existant) — aucun chiffre
  dans le corps de l'article, § 3.6.

### Test 2 — a l'oeil, dans l'article
Ouvrir « Etat des lieux du carnet de demonstration », sur un ecran large.

Attendu : **l'article a gauche, ses 63 preuves a droite**, cote a cote. Aucun
voile, aucun grisage : les deux se lisent en meme temps.

Chaque fiche, de haut en bas :
1. `[N]`, un cercle creux gris, deux badges d'hypostase **en couleur et en
   contour**, le titre de la note, et un compteur `✎N` s'il y a un debat ;
2. le resume de l'extraction, **en B612 Mono** ;
3. un peu du texte d'avant, **en gris et en Lora italique**, puis la citation
   **en Lora a pleine encre et plus grosse**, puis un peu du texte d'apres ;
4. « ▸ voir le passage dans la source » ;
5. « Voir la source[, N commentaires] ↗ » — elle s'ouvre dans un **nouvel
   onglet** ;
6. « **FAIBLE** · detail de la verification ▸ », **dans** la carte.

**Cliquer un renvoi `[N]` dans le texte** : sa fiche vient **en tete de la
colonne**, marquee d'un filet bleu — et **la page ne bouge pas**.
**Cliquer une fiche** : le texte defile jusqu'au passage qu'elle prouve, et le
renvoi s'y surligne.

**Cliquer la citation elle-meme** (pas le chevron) : le passage s'allonge des
deux cotes, l'invite devient « ▾ replier le passage ».

**Cliquer « detail de la verification »** : la barre de degre, puis les cinq
juges, chacun **nomme au-dessus de sa barre** — REFERENCE en tete, un **filet**,
puis les quatre locaux. La version du protocole n'apparait **qu'une fois**, en
pied : « Tous par xnli-directe v1, le … ».

### Test 2 bis — la largeur
Retrecir la fenetre sous **1280px** : la colonne des preuves repasse **SOUS**
l'article, pleine largeur. Jamais par-dessus, jamais de voile. Verifier qu'aucune
barre de defilement horizontale n'apparait, jusqu'a 390px.

### Test 3 — le clavier
Tab jusqu'a la citation, Entree : le passage s'ouvre. Tab jusqu'a « detail de la
verification », Entree : il s'ouvre. Les deux montrent un **anneau de focus de
2px**. Verifie : les deux repondent a Entree seule.

### Test 4 — les deux themes
Basculer clair / sombre. Rien ne doit devenir illisible. Mesure faite :
26 contrastes, minimum 4,73:1.

### Verifs DB / etats limites
```bash
# Les 225 fiches reelles se rendent-elles toutes ?
docker compose exec -T web python manage.py shell -c "
from django.test import Client
from django.contrib.auth import get_user_model
from core.models import SourceLink, TypeLien
c = Client(SERVER_NAME='localhost')
c.force_login(get_user_model().objects.get(username='jonas'))
mauvaises = [l.pk for l in SourceLink.objects.filter(type_lien=TypeLien.CITE)
             if c.get(f'/citations/{l.pk}/preuve/').status_code != 200]
print('en echec :', mauvaises)
"
```
Attendu : `en echec : []`.

Le CSS touche vit dans un **template** (`_style_maquette.html`), pas dans
`maquette.css` : ni `collectstatic` ni bump `?v=` ne sont necessaires.
