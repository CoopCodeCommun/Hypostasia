# Publier l'extension sur le Chrome Web Store / Publishing on the Chrome Web Store

**Date :** 2026-08-27
**Migration :** Non

## Resume / Summary

**Quoi / What :** un paquet dedie a Chrome (`make extension-zip-chrome`), les
visuels au format impose par Google, et le texte de la fiche, champ par champ.
/ A Chrome-specific package, the store assets at Google's required sizes, and the
listing copy field by field.

**Pourquoi / Why :** la version Firefox a ete acceptee le 26 aout 2026. Chrome
demande trois choses qu'AMO ne demandait pas — des dimensions d'image exactes,
une tuile promotionnelle obligatoire, une justification ecrite par permission —
et **ne peut pas etre pilote par automatisation**.

### CE QUI NE MARCHE PAS, ET NE MARCHERA PAS

**Le Chrome Web Store refuse d'etre pilote par une extension.** Les deux
domaines de la console repondent la meme chose :

```
Error capturing screenshot: The extensions gallery cannot be scripted.
```

`chrome.google.com/webstore/devconsole` et `chromewebstore.google.com/devconsole`
sont tous deux dans la liste des origines protegees de Chrome : **aucune
extension ne peut y lire le DOM, y cliquer, ni y prendre de capture** — celle qui
sert d'yeux a un agent pas plus qu'une autre. Ce n'est pas un reglage a changer,
c'est une protection du navigateur contre les extensions qui s'auto-installeraient
ou s'auto-noteraient.

**Consequence pratique : la fiche Chrome se remplit a la main.** Ce fichier
existe pour que ce soit du copier-coller et non de la redaction.

> Il existe une autre voie, la **Chrome Web Store API** : elle televerse et publie
> par `curl`. Elle demande un projet Google Cloud, un identifiant OAuth, un secret
> client et un jeton de rafraichissement — trois secrets a fabriquer et a garder,
> pour une soumission qu'on fait deux fois par an. Le rapport n'y est pas.

### Ce qui a ete fait

| Fichier / File | Changement / Change |
|---|---|
| `bin/paqueter_l_extension.sh` | accepte `chrome` : meme paquet, **sans** `browser_specific_settings` |
| `Makefile` | cible `extension-zip-chrome` |
| `extension/screen/chrome/` | **neuf** — 4 captures en 1280x800, la tuile 440x280, l'icone de boutique |

**Le paquet Chrome zippe une COPIE, jamais la source.** Retirer la cle
directement dans `extension/manifest.json` casserait la version Firefox du depot,
et le ferait **en silence** : le manifest resterait un JSON valide. Verifie apres
fabrication — la cle est absente du zip et presente dans la source.

**Pourquoi retirer `browser_specific_settings`** : elle ne porte que des notions
de Firefox (identifiant gecko, `strict_min_version: 140.0`,
`data_collection_permissions`). Chrome les ignore, donc elle n'est pas
dangereuse ; mais un relecteur qui ouvre le manifest y lirait une version
minimale de Firefox et une declaration de collecte au format de Mozilla.

### Les visuels, et pourquoi ils ont du etre refaits

Google impose des dimensions **exactes**, la ou Mozilla acceptait n'importe quoi :

| Exigence | Ce qu'on avait |
|---|---|
| Captures **1280x800** ou **640x400**, bord a bord, sans marge | ratios 1,71 · 0,78 · 1,69 · 1,69 — aucune a 1,6 |
| Petite tuile promotionnelle **440x280**, obligatoire | rien |
| Icone de boutique 128x128, dessin 96x96, marge transparente | icone en RGB **sans canal alpha** |

Les quatre captures sont des **recadrages** des originaux, qui restent intacts
dans `extension/screen/`. Celle du carnet est rognee **par la gauche** et non
au centre : un recadrage centre lui coupait le mot « Hypostasia » de l'en-tete.

**La tuile est composee en HTML**, pas a la main : `chromium --headless
--window-size=880,560` rend la page, puis la reduction de moitie donne le
440x280. Le double permet au trait de l'icosaedre et aux petites capitales de
rester nets apres reduction. Une sonde dans la page mesure le debordement au
lieu de le juger a l'oeil (763 px de contenu pour 824 disponibles).

**Une seule ligne d'accroche, et grosse.** La tuile s'affiche a 440x280 : tout
ce qui y est ecrit est lu a la **moitie** de la taille de composition. Une
deuxieme ligne y devient illisible.

> **La capture de la popup montre Firefox** — barre d'onglets, « Navigation
> privee », barre d'adresse. Choix du mainteneur, le 26 aout : la garder plutot
> que de reinstaller l'extension dans Chrome pour la refaire. A savoir si un
> relecteur le releve.

---

## La fiche, champ par champ

Console : **https://chrome.google.com/webstore/devconsole/**
Paquet a televerser : **`dist/hypostasia-extension-1.0.0-chrome.zip`**

### Informations sur le produit

**Nom**

```
Hypostasia Extractor
```

**Description courte** — 131 caracteres, la limite est a 132. Ne pas la rallonger
sans recompter.

```
Récoltez la page que vous lisez et rangez-la dans un carnet Hypostasia. Le texte est extrait proprement, rien ne part sans un clic.
```

**Description detaillee**

```
Hypostasia Extractor sauvegarde proprement les pages que vous lisez, pour les relire et les analyser plus tard.

CE QU'ELLE FAIT

Elle extrait le texte principal de la page avec Readability, la bibliothèque qui fait le mode lecture de Firefox : plus de publicités, plus de menus, plus de bandeaux de cookies.

Elle vous laisse choisir le carnet de destination AVANT la capture, parmi ceux où vous avez le droit d'écrire — les vôtres, ceux qu'on vous a partagés, et ceux partagés à un groupe dont vous êtes membre.

Elle vous prévient si la page a déjà été enregistrée, et elle vous avertit quand le carnet choisi est public — au moment du geste, pas dans une page d'aide.

CE QU'ELLE NE FAIT PAS

Elle ne lit aucune page tant que vous ne cliquez pas sur « Récolter ». Elle n'a pas de tâche de fond, ne suit pas votre navigation, et n'envoie rien à personne d'autre qu'au serveur Hypostasia que vous avez choisi.

Aucun traceur, aucune mesure d'audience, aucune revente de données.

IL VOUS FAUT UN SERVEUR HYPOSTASIA

Par défaut, l'extension pointe vers https://beta.hypostasia.org/ — notre instance ouverte, où un compte gratuit suffit. Vous pouvez aussi indiquer votre propre instance : Hypostasia est un logiciel libre sous licence AGPL v3, et il s'héberge.

Code source : https://github.com/CoopCodeCommun/Hypostasia
```

**Categorie** — la liste de Chrome n'a pas de « Marque-pages ». Prendre
**Workflow et planification** ; a defaut **Outils**.

**Langue** : Francais

### Visuels — `extension/screen/chrome/`

| Champ | Fichier | Legende (si le champ existe) |
|---|---|---|
| Capture 1 | `1-popup.png` | Sur n'importe quel article : choisissez le carnet, cliquez Récolter. |
| Capture 2 | `2-notes.png` | La page arrive sans ses publicités ni ses menus, puis chaque passage clé est extrait et typé. |
| Capture 3 | `3-carnet.png` | Vos captures se rangent dans le carnet choisi, à côté de vos PDF, audio et notes. |
| Capture 4 | `4-wiki.png` | Hypostasia en tire des articles vivants, où chaque affirmation reste reliée à sa source. |
| Petite tuile promo | `promo-440x280.png` | — |
| Icone de boutique | `icone-boutique-128.png` | — |

### Liens

| Champ | Valeur |
|---|---|
| Site web du developpeur | `https://hypostasia.org/` |
| Assistance | `https://github.com/CoopCodeCommun/Hypostasia/issues` |
| **Politique de confidentialite** | `https://hypostasia.org/confidentialite/` |

> **Chrome veut une URL, la ou AMO voulait le texte.** La page `/confidentialite/`
> sert donc directement ici. C'est ce qui la justifie : sans elle, il aurait fallu
> l'heberger quelque part dans l'urgence.

### Objectif unique (« single purpose »)

```
Extraire le contenu principal de la page web que l'utilisateur consulte et l'enregistrer, sur son ordre explicite, dans un carnet de l'instance Hypostasia qu'il a choisie.
```

### Justification de chaque permission

**`activeTab`**

```
L'extension lit le contenu de l'onglet actif uniquement quand l'utilisateur clique sur « Récolter » dans la popup. activeTab limite cet accès à cet onglet-là et à ce moment-là : elle n'accorde aucun accès permanent ni aucun accès aux autres onglets.
```

**`scripting`**

```
Sert à injecter lib/Readability.js dans l'onglet actif pour en extraire le texte principal. L'injection n'a lieu qu'au clic sur « Récolter » (popup.js, chrome.scripting.executeScript). Aucun content script n'est déclaré dans le manifest : rien n'est injecté au chargement des pages.
```

**`storage`**

```
Conserve trois valeurs sur la machine de l'utilisateur : l'adresse de son serveur Hypostasia, son jeton d'authentification, et le dernier carnet choisi. Rien d'autre n'est stocké, et rien n'est envoyé ailleurs que vers le serveur qu'il a configuré.
```

**Permissions d'hote — `https://hypostasia.org/*` et `https://beta.hypostasia.org/*`**

```
Ce sont les deux instances officielles d'Hypostasia. L'extension y envoie la note par un POST sur l'API de l'instance, et y lit la liste des carnets de l'utilisateur. Sans cette permission, ces requêtes échouent sur une erreur de même origine.
```

**Permission d'hote optionnelle — `*://*/*`**

```
Hypostasia est un logiciel libre qui s'auto-héberge. Un utilisateur qui fait tourner sa propre instance saisit l'adresse de son serveur dans la popup ; l'autorisation lui est alors demandée à l'exécution, pour cette seule origine, au moment où il clique sur OK (popup.js, fonction demanderLAutorisationDuServeur). Elle n'est jamais demandée à l'installation ni accordée d'office.
```

### Utilisation des donnees

Cocher :

- **Contenu du site web** — le titre, l'adresse et le texte principal de la page
  que l'utilisateur choisit de recolter.
- **Informations d'authentification** — le jeton d'API, transmis au serveur que
  l'utilisateur a configure, et a lui seul.

> **Le jeton est un cas limite, et on le declare exprès.** C'est le credential de
> l'utilisateur vers son propre serveur, jamais vers nous. Sous-declarer coute
> plus cher que sur-declarer : la politique de confidentialite le mentionne deja,
> une omission ici la contredirait.

Ne PAS cocher : informations personnelles identifiables, sante, finances,
messages personnels, localisation, **historique de navigation**.

> **Pas l'historique de navigation** : l'extension ne voit que la page qu'on lui
> designe, au moment ou on la lui designe. Elle n'a ni tache de fond, ni content
> script declare, ni acces aux autres onglets.

Puis les trois attestations, qui sont vraies toutes les trois :

- je ne vends ni ne transfere les donnees a des tiers, hors usages approuves ;
- je n'utilise ni ne transfere les donnees a des fins etrangeres a l'objectif
  unique ci-dessus ;
- je n'utilise ni ne transfere les donnees pour evaluer une solvabilite ou pour
  du credit.

---

## Comment tester (a la main) / Manual test

### Avant de televerser

```bash
make extension-zip-chrome      # -> dist/hypostasia-extension-1.0.0-chrome.zip
```

Puis dans Chrome : `chrome://extensions/` -> **Mode developpeur** ->
**Charger l'extension non empaquetee** -> dossier `extension/`.

> Charger le **dossier**, pas le zip. Et c'est bien le dossier `extension/` du
> depot : celui-la porte encore `browser_specific_settings`, que Chrome ignore.

### Test 1 — le chemin nominal

1. Ouvrir la popup sur un article. Le champ serveur doit afficher
   `https://beta.hypostasia.org/`.
2. « Connecter cette extension », choisir un carnet, « Recolter ».
3. Attendu : « Enregistree dans « … » », **sans aucune fenetre de permission**.

### Test 2 — une instance auto-hebergee

1. Remplacer l'adresse par une autre instance, cliquer **OK**.
2. Attendu : Chrome demande l'autorisation pour cette adresse.
3. Refuser -> « Sans autorisation, l'extension ne peut pas joindre ce serveur. »,
   et l'adresse n'est **pas** enregistree.

> C'est le seul chemin qui differe vraiment entre les deux navigateurs :
> `permissions.request()` doit partir directement du clic. Si aucune fenetre
> n'apparait, c'est qu'un `await` s'est glisse avant l'appel et a perdu le geste.

### Test 3 — le paquet lui-meme

`chrome://extensions/` -> **Empaqueter l'extension** n'est PAS necessaire : le
Chrome Web Store attend un `.zip`, pas un `.crx`.
