# Publier l'extension navigateur sur Firefox / Publishing the browser extension on Firefox

**Date :** 2026-08-21
**Migration :** Non

## Resume / Summary

**Quoi / What :** l'extension `extension/` est mise en etat d'etre soumise a
addons.mozilla.org. Sept fichiers morts retires, permissions reduites aux deux
instances officielles, defaut serveur passe de `127.0.0.1:8000` a
`beta.hypostasia.org`, cible `make extension-zip`, et une politique de
confidentialite servie a `/confidentialite/`.
/ The browser extension is made ready for addons.mozilla.org: dead code removed,
permissions narrowed, server default changed, packaging target, privacy policy.

**Pourquoi / Why :** `web-ext lint`, la validation que Mozilla fait tourner a la
soumission, refusait de passer au vert. Trois causes, dont aucune ne se
signalait a l'usage.
/ web-ext lint, the validation Mozilla runs at submission, would not come out
clean. Three causes, none of which showed up in normal use.

### Ce qui n'allait pas

**Une chaine de code mort de 420 lignes et 164 Ko.** `background.js` n'etait
declare nulle part dans le manifest — aucune cle `background`. Il etait donc
orphelin, et il entrainait tout ce qu'il appelait : `content.js` (injecte par
personne), `sidebar.html` et `sidebar.js` (inatteignables), `lib/htmx.min.js`
(reference par la seule sidebar), `lib/sweetalert2.all.min.js` (reference nulle
part) et `lib/sweetalert2.min.css` (reference par le seul `background.js`).

Le poids n'etait pas le probleme. **AMO fait relire la source par un humain**, et
`background.js` portait des commentaires de session du genre « Actually, previous
content.js was likely injected via manifest or popup. Let's assume… ». Surtout :
ces trois bibliotheques minifiees declenchent l'exigence de soumission du code
source non minifie. Une fois parties, il ne reste dans le paquet **aucun code
minifie**, et cette exigence tombe.

**`host_permissions: ["<all_urls>"]`.** Depuis Firefox 127, les permissions d'hote
sont affichees a l'installation puis accordees — `<all_urls>` faisait donc
promettre a l'utilisateur un acces a « toutes ses donnees, sur tous les sites »
pour une extension qui ne parle qu'a un seul serveur.

**Le defaut serveur etait `http://127.0.0.1:8000/`**, une adresse de
developpement. Quelqu'un installant depuis le store tombait sur un champ pointant
vers sa propre machine, ou rien ne repond.

### Ce qui a ete fait

| Fichier / File | Changement / Change |
|---|---|
| `extension/background.js` | **supprime** — orphelin, aucune cle `background` au manifest |
| `extension/content.js` | **supprime** — n'etait injecte par personne |
| `extension/sidebar.html`, `sidebar.js` | **supprimes** — inatteignables |
| `extension/lib/htmx.min.js` | **supprime** — utilise par la seule sidebar |
| `extension/lib/sweetalert2.all.min.js` | **supprime** — reference nulle part |
| `extension/lib/sweetalert2.min.css` | **supprime** — utilise par le seul `background.js` |
| `extension/manifest.json` | version `1.0.0` ; `host_permissions` reduit aux deux instances ; `optional_host_permissions` ajoute ; `web_accessible_resources` retire ; `strict_min_version` 109 -> 140 ; `gecko_android` 142 ; description en francais |
| `extension/popup.js` | defaut serveur -> `beta.hypostasia.org` ; `demanderLAutorisationDuServeur()` avant l'enregistrement d'une URL |
| `extension/options.js` | idem, cote page d'options |
| `extension/popup.html`, `options.html` | placeholders alignes sur le nouveau defaut |
| `bin/paqueter_l_extension.sh` | **neuf** — fabrique `dist/hypostasia-extension-<version>.zip`, en excluant `extension/screen/` |
| `Makefile` | cible `extension-zip` |
| `front/views_accueil.py` | `ConfidentialiteViewSet` |
| `front/urls.py` | route `confidentialite` |
| `front/templates/front/includes/confidentialite.html` | **neuf** — le texte de la politique |
| `front/templates/front/includes/confidentialite_ecran.html` | **neuf** — l'ecran, sur le modele du manifeste |
| `front/templates/front/base.html` | titre + branche `confidentialite_preloaded` |
| `front/templates/front/includes/onboarding_vide.html` | lien vers la politique au bas de l'ecran d'aide |
| `front/templates/front/includes/manifeste.html` | lien discret dans le pied, sous la ligne AGPLv3 |

### Ce que `web-ext lint` en dit

Avant : **4 avertissements**. Apres : **0 erreur, 2 avertissements**, tous deux
`UNSAFE_VAR_ASSIGNMENT` aux lignes 1549 et 1928 de `lib/Readability.js`.

Cette copie a ete comparee a l'amont : son empreinte SHA-256 est **identique,
octet pour octet, a `mozilla/readability` 0.6.0**
(`34dcab3d0832d0019f02990eed6b6124e029e8c32b9f0c6f2550544ff8dff174`). Les deux
avertissements sont donc dans du code de Mozilla, celui qui fait le mode lecture
de Firefox. C'est a dire aux relecteurs, pas a corriger.

### Ce qui a ete verifie, et comment

**`web-ext lint`** : 0 erreur, 2 avertissements (les deux dans Readability, voir
plus haut). C'est la validation que Mozilla fait tourner a la soumission.

**La page `/confidentialite/`, au navigateur, en clair ET en sombre.** Contrastes
WCAG **calcules** sur les couleurs reellement rendues, pas estimes :

| | clair | sombre |
|---|---|---|
| titre, sections, corps, listes | 16,79 | 15,10 |
| sous-titre et date | 5,42 | 6,18 |
| bandeau d'alerte | 15,53 | 13,91 |
| lien | 7,71 | 9,11 |

Tout passe AA (seuil 4,5). Aucun debordement horizontal dans les deux themes.

> **Une mesure intermediaire a affiche 2,30 pour le lien en sombre.** Elle etait
> fausse : `getComputedStyle` rend la valeur **interpolee** pendant une
> transition CSS, et `.confidentialite-lien` porte `transition: color .15s`. La
> lecture avait attrape la couleur claire sur le fond deja sombre. Mesurer un
> contraste juste apres une bascule de theme demande d'attendre la fin de la
> transition — sinon on corrige un defaut qui n'existe pas.

**Le chemin HTMX** : `/confidentialite/` avec l'en-tete `HX-Request` rend le
partial seul (aucune balise `<html>`) et depose bien les deux conteneurs OOB, du
fil d'Ariane et du lecteur audio. Verifie aussi **au clic**, depuis l'aide :
l'URL est poussee, et les deux conteneurs OOB ressortent vides.

**Les deux liens**, mesures dans les deux themes : 7,71 en clair et 9,11 en
sombre pour le lien lui-meme, 5,42 et 6,18 pour le texte qui l'entoure. Tout
passe AA.

**Readability est deja a jour.** 0.6.0 est la **derniere version publiee**
(mars 2025), et les deux lignes que le linter signale — `page.innerHTML =
pageCacheHtml` et `tmp.innerHTML = noscript.innerHTML` — sont **toujours
presentes sur la branche `main`**, aux lignes 1575 et 1954. Aucune mise a jour
ne les fait disparaitre : c'est ainsi que Readability fonctionne. La note aux
relecteurs est la seule reponse.

**Non-regression** : `/`, `/manifeste/`, `/aide/`, `/carnets/` repondent toujours
apres l'ajout de la branche dans `base.html`.

**Ce qui n'a PAS ete verifie** : le flux de permission de l'extension, dans
Firefox. Charger un module temporaire passe par une boite de dialogue systeme
qu'aucune automatisation de navigateur ne pilote. Les tests 2 et 3 ci-dessous
restent donc a faire a la main.

### Le detail qui coince, si on y revient un jour

**`optional_host_permissions` exige Firefox 128**, et
`browser_specific_settings.gecko.data_collection_permissions` — deja present
avant ce chantier — **exige Firefox 140**. Le manifest annoncait `109.0`, ce qui
faisait sortir deux avertissements au lint. `strict_min_version` est donc passe a
`140.0`, et `gecko_android` a `142.0` (mesure : sans cette derniere cle,
l'avertissement Android survit).

**Le defaut serveur ne vaut que pour une installation neuve.**
`storage.sync.get({serverUrl: …})` ne rend le defaut que si rien n'est
enregistre. Le jour ou l'on voudra basculer les gens de `beta` vers la prod, il
faudra une migration explicite : changer le defaut ne deplacera personne qui a
deja ouvert la popup une fois.

---

## Comment tester (a la main) / Manual test

### Prealable

```bash
make extension-zip      # -> dist/hypostasia-extension-1.0.0.zip
```

Puis, dans Firefox : `about:debugging#/runtime/this-firefox` ->
**Charger un module complementaire temporaire** -> choisir
`extension/manifest.json`.

> Il faut **Firefox 140 ou plus** : en dessous, `about:debugging` refusera le
> chargement, et le message ne dira pas que c'est `strict_min_version` qui parle.

### Test 1 — le chemin nominal, sans aucune permission a accorder

1. Epingler l'extension, ouvrir la popup sur un article quelconque.
2. Le champ serveur doit afficher **`https://beta.hypostasia.org/`** — pas
   `127.0.0.1`.
3. Cliquer **Connecter cette extension** apres s'etre connecte a beta dans le
   meme navigateur.
4. Choisir un carnet, cliquer **Recolter**.
5. Attendu : « Enregistree dans « … » », **et aucune fenetre de permission** —
   `beta.hypostasia.org` est dans `host_permissions`, donc deja accordee a
   l'installation.

### Test 2 — une instance auto-hebergee, la permission a la demande

1. Dans la popup, remplacer l'adresse par une autre instance
   (`http://127.0.0.1:8000/` fait l'affaire si le serveur de dev tourne).
2. Cliquer **OK**.
3. Attendu : **Firefox demande l'autorisation** pour cette adresse.
4. **Accepter** -> l'adresse s'enregistre, les carnets se chargent.
5. Refaire l'operation et **refuser** -> le message
   « Sans autorisation, l'extension ne peut pas joindre ce serveur. » s'affiche,
   et l'adresse n'est **pas** enregistree.

> C'est le seul chemin vraiment neuf de ce chantier, et le plus fragile :
> `permissions.request()` doit partir directement du clic. Si la fenetre
> n'apparait pas du tout, c'est qu'un `await` s'est glisse avant l'appel et a
> perdu le geste utilisateur.

### Test 3 — la meme chose depuis la page d'options

Clic droit sur l'icone -> **Gerer l'extension** -> onglet **Options**. Meme
scenario que le test 2.

### Test 4 — la politique de confidentialite

1. Ouvrir `/confidentialite/` **directement** (pas par un lien HTMX) :
   la page entiere doit se rendre, sans etre connecte.
2. Y aller ensuite depuis un lien interne : le fil d'Ariane de la note
   precedente doit **disparaitre**, et la barre du lecteur audio aussi.
3. Verifier en clair **et en sombre**.
4. La section « Qui edite Hypostasia » porte le SIREN, le siege et
   `contact@tibillet.re`. Plus aucun emplacement vide.

### Test 5 — on peut TROUVER la politique

1. Depuis `/aide/`, descendre tout en bas : un lien
   « Politique de confidentialite » sous un filet. Cliquer : la page
   s'affiche par HTMX, l'URL devient `/confidentialite/`, et le fil
   d'Ariane de la note precedente disparait.
2. Depuis `/manifeste/`, le pied porte le meme lien sous la ligne
   « Code source d'Hypostasia : AGPLv3 ».

> **Il n'y a PAS de lien sur tous les ecrans.** `#zone-lecture` est la
> cible des swaps HTMX (`hx-swap="innerHTML"`) : un pied place dedans
> serait efface a chaque navigation. Le placer dehors demanderait de
> toucher a la grille `.plateau`, qui porte des variantes en media query
> a 1400px. Les deux ecrans d'information portent donc le lien, et pas
> le reste.

### Verification automatique

```bash
npx --yes web-ext@latest lint --source-dir extension
```

Attendu : **0 erreur**, 2 avertissements, tous deux dans `lib/Readability.js`.

---

## La soumission a addons.mozilla.org

### Ce qu'il faut avoir sous la main

| | |
|---|---|
| Compte | un compte Mozilla (gratuit, aucun frais d'inscription) |
| Paquet | `dist/hypostasia-extension-1.0.0.zip` |
| Politique | `https://hypostasia.org/confidentialite/` — **l'adresse de contact reste a renseigner** |
| Licence | GNU AGPL v3 |
| Code source | `https://github.com/CoopCodeCommun/Hypostasia` |
| Captures | les 4 fichiers de `extension/screen/`, dans l'ordre donne plus bas |
| Compte de test | a saisir **dans le formulaire AMO uniquement** — voir l'avertissement |

> ⚠️ **Le compte de test ne s'ecrit pas dans ce depot.** Le depot est public. Le
> champ « Notes for reviewers » d'AMO, lui, n'est lu que par Mozilla : c'est la,
> et seulement la, que l'identifiant et le mot de passe se saisissent.

### Les captures, et leurs legendes

Elles vivent dans **`extension/screen/`**. AMO accepte une legende par capture,
et il faut les saisir : trois des quatre montrent le serveur, pas l'extension.
Sans legende, la fiche a l'air de faire la promotion d'un autre produit que
celui qu'on installe.

**L'ordre compte.** La premiere est souvent la seule qu'on regarde, et c'est la
seule ou l'on voit l'extension elle-meme.

| # | Fichier | Legende a saisir |
|---|---|---|
| 1 | `screen extension depuis article externe.png` | Sur n'importe quel article : choisissez le carnet, cliquez Recolter. L'extension previent si le carnet est public. |
| 2 | `screen notes.png` | La page arrive sans ses publicites ni ses menus, puis chaque passage cle est extrait et type. |
| 3 | `screen carnet.png` | Vos captures se rangent dans le carnet choisi, a cote de vos PDF, audio et notes. |
| 4 | `screen wiki.png` | Hypostasia en tire des articles vivants, ou chaque affirmation reste reliee a sa source. |

Les deux premieres se suivent : la popup capture un article du *Monde
diplomatique*, et la note montree juste apres vient du meme journal, rangee dans
le meme carnet « Philo / Politique / Societe ». La continuite se lit sans qu'on
ait a l'expliquer.

> **`screen/` ne part pas dans le paquet.** `bin/paqueter_l_extension.sh`
> l'exclut : 1,7 Mo que le navigateur n'ouvre jamais, et qui faisaient passer le
> paquet de 68 Ko a 1,9 Mo. Le dossier vit dans le depot parce que c'est la
> qu'on le retrouve au moment de remplir la fiche, pas parce qu'il s'installe.

### Le texte de la fiche

**Nom :** Hypostasia Extractor

**Resume** (250 caracteres au plus) :

> Recolte la page que vous lisez et la range dans un carnet de votre instance
> Hypostasia. Le texte principal est extrait avec Readability, sans publicites
> ni menus. Rien n'est envoye tant que vous n'avez pas clique.

**Description :**

> Hypostasia Extractor sauvegarde proprement les pages que vous lisez, pour les
> relire et les analyser plus tard.
>
> **Ce qu'elle fait**
>
> — Extrait le texte principal de la page avec Readability, la bibliotheque qui
> fait le mode lecture de Firefox : plus de publicites, plus de menus, plus de
> bandeaux de cookies.
> — Vous laisse choisir le carnet de destination **avant** la capture, parmi
> ceux ou vous avez le droit d'ecrire.
> — Vous previent si la page a deja ete enregistree.
> — Vous avertit quand le carnet choisi est public, au moment du geste.
>
> **Ce qu'elle ne fait pas**
>
> Elle ne lit aucune page tant que vous ne cliquez pas sur « Recolter ». Elle
> n'a pas de tache de fond, ne suit pas votre navigation, et n'envoie rien a
> personne d'autre qu'au serveur Hypostasia que vous avez choisi.
>
> **Il vous faut un serveur Hypostasia**
>
> Par defaut, l'extension pointe vers https://beta.hypostasia.org/ — notre
> instance ouverte, ou un compte gratuit suffit. Vous pouvez aussi indiquer
> votre propre instance : Hypostasia est un logiciel libre sous licence AGPL v3,
> et s'heberge.
>
> Code source : https://github.com/CoopCodeCommun/Hypostasia

**Categories :** Signets *(Bookmarks)* et Autre *(Other)*.

**Etiquettes :** lecture, annotation, archivage, recherche, readability.

### Notes pour les relecteurs (champ « Notes for reviewers »)

> Cette extension envoie le contenu d'une page vers une instance Hypostasia
> (Django, AGPL v3), au choix de l'utilisateur. Elle n'agit que sur un clic
> explicite.
>
> **Compte de test** sur https://beta.hypostasia.org/ :
> identifiant `…`, mot de passe `…`.
>
> **Pour reproduire :** se connecter au site ci-dessus, ouvrir la popup de
> l'extension, cliquer « Connecter cette extension » (elle recupere le jeton
> d'API depuis la session), choisir un carnet, puis « Recolter » sur n'importe
> quel article.
>
> **`lib/Readability.js`** est une copie **non modifiee** de
> https://github.com/mozilla/readability version 0.6.0. Son empreinte SHA-256
> est `34dcab3d0832d0019f02990eed6b6124e029e8c32b9f0c6f2550544ff8dff174`,
> identique au fichier `Readability.js` du tag 0.6.0. Les deux avertissements
> `UNSAFE_VAR_ASSIGNMENT` du linter portent sur ce fichier.
>
> **Aucun code minifie ou genere** dans ce paquet.
>
> **Permissions :** `host_permissions` ne couvre que nos deux instances.
> `optional_host_permissions` sert aux utilisateurs qui hebergent Hypostasia
> eux-memes : l'autorisation leur est demandee au moment ou ils saisissent
> l'adresse de leur serveur (`popup.js`, `demanderLAutorisationDuServeur`).

### Ce qui s'est reellement passe, le 21 aout 2026

**Ce n'etait pas une premiere soumission.** « Hypostasia Extractor » existait sur
AMO depuis le **6 decembre 2025**, version 1.0, approuvee. Le premier
televersement a echoue sur « Un identifiant identique a ete trouve » : c'etait
notre propre `hypostasia@hypostasia.org`.

**Et ce module n'a jamais ete public.** Sa page publique rendait 404, l'API 401,
avec `is_disabled_by_developer: false` et `is_disabled_by_mozilla: false` — ni
retire, ni bloque.

**La cause : le canal de distribution.** La soumission de decembre avait choisi
« A vous de jouer » (*self-distribution*), qui fait signer le `.xpi` par Mozilla
pour qu'on le distribue soi-meme et **ne publie rien sur addons.mozilla.org**.

Ce choix explique tout ce qui paraissait incoherent :

| Symptome | Cause |
|---|---|
| Page publique en 404, API en 401 | un module non liste n'a pas de fiche publique |
| Aucun champ de televersement d'image sur la page produit | la section « Images » n'existe que pour un module liste |
| Ligne « Licence » vide, sans selecteur | idem — la licence est un champ de fiche |
| Aucune categorie nulle part | idem |
| `submit/details` redirigeait vers `submit/source-unlisted` | le parcours restait dans le canal *unlisted* |

**Le geste qui debloque** : sur `versions/submit/`, l'encart « Hebergement de
cette version » porte un lien **« Changement »**. Il ramene au choix du canal.
Passe sur « Gestion via le site », tout l'ecran manquant apparait d'un coup.

### L'etat de la fiche apres coup

| | |
|---|---|
| Adresse | `addons.mozilla.org/fr/firefox/addon/hypostasia/` |
| Version en attente | **1.0.0**, canal **AMO**, « En attente de validation », 0 erreur / 2 avertissements |
| Ancienne version | 1.0, canal **Self**, approuvee le 6 decembre 2025 |
| Visibilite | Visible |
| Categorie | Marque-pages |
| Licence | GNU Affero General Public License v3.0 |
| Politique de confidentialite | 3 941 caracteres, saisis **dans AMO** |
| Captures | les 4, avec leurs legendes, plus l'icone |
| Assistance | `contact@tibillet.re` et les issues GitHub |

> **L'adresse a resiste deux fois.** Posee a `hypostasia` sur la page produit,
> elle etait revenue a `hypostasia-extractor` apres la bascule de canal. Verifier
> ce champ apres tout changement de canal.

### Le compte de test n'existe pas, et c'est voulu

Les notes aux relecteurs ne portent **aucun identifiant partage**. Elles pointent
vers `https://beta.hypostasia.org/auth/register/` : l'inscription y est libre,
sans validation par courriel, et la vue connecte la personne dans la foulee
(`front/views_auth.py`, `page_register`). Un relecteur se cree un compte en
trente secondes.

C'est mieux qu'un compte commun : rien a faire tourner, rien qui fuite, rien a
reecrire le jour ou le mot de passe change. **Ne pas remettre d'identifiants
dans ce fichier** — le depot est public.

### Ce que la politique de confidentialite devient

**AMO ne stocke pas une URL, il stocke le texte.** Le champ `privacy_policy_fr`
est un `textarea`. La politique vit donc **dans AMO**, sans dependre de la
disponibilite de hypostasia.org.

La page `/confidentialite/` garde son role : elle est lisible **dans** le produit
(liee depuis l'aide et le pied du manifeste), et le texte AMO la cite comme
version en ligne. Les deux doivent rester d'accord — modifier l'une sans l'autre
les fait diverger en silence.

### Ce qui reste

Attendre. Mozilla annonce **jusqu'a 24 heures**, davantage si le module part en
revue manuelle, et previent par courriel. La page publique n'existera qu'a
l'approbation de la version 1.0.0 : la version 1.0 approuvee en decembre ne
compte pas, elle est dans l'autre canal.
