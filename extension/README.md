# Hypostasia Extractor

Extension de navigateur pour extraire le contenu des pages web et l'envoyer vers une instance **Hypostasia** (backend
Django). Elle permet de sauvegarder proprement des articles pour une lecture ou une analyse ultérieure.

Une instance de test (bac à sable) est disponible à l'adresse : **https://beta.hypostasia.org/**

## Fonctionnalités

- **Extraction propre** : Utilise `Readability.js` (la technologie derrière le mode lecture de Firefox) pour extraire le
  contenu principal de la page en supprimant les publicités et menus inutiles.
- **Choix du carnet avant la capture** : un menu liste les carnets dans lesquels vous avez le droit d'écrire — les
  vôtres, ceux qu'on vous a partagés directement, et ceux partagés à un groupe dont vous êtes membre. Le dernier carnet
  choisi est retenu, séparément pour chaque serveur et chaque compte.
- **Avertissement sur les carnets publics** : ranger une note dans un carnet public la rend publique, avec ses
  extractions et ses commentaires. L'extension le dit au moment où vous choisissez, pas dans une page d'aide.
- **Intégration Django** : Communique directement avec l'API de votre instance Hypostasia.
- **Vérification automatique** : L'extension vous indique si la page a déjà été enregistrée — dans votre périmètre, ou
  par quelqu'un d'autre sur la même instance.
- **Connexion en un clic** : un bouton récupère votre token depuis le site. Aucun copier-coller.
- **Interface simple** : Une popup rapide pour configurer l'URL du serveur, choisir le carnet et lancer l'extraction.

## Installation en mode développeur

Pour utiliser cette extension sans passer par un store officiel, vous devez l'installer en mode développeur.

### Pour Google Chrome (et Chromium : Edge, Brave, Opera)

1. **Téléchargez** ou clonez le code source du projet sur votre ordinateur.
2. Ouvrez Chrome et tapez `chrome://extensions/` dans la barre d'adresse.
3. En haut à droite, activez l'interrupteur **Mode développeur**.
4. Cliquez sur le bouton **Charger l'extension non empaquetée** qui vient d'apparaître en haut à gauche.
5. Sélectionnez le dossier `extension` de ce dépôt.
6. L'extension "Hypostasia Extractor" est maintenant installée. Pour l'avoir toujours à portée de clic :
   - Cliquez sur l'icône **Extensions** (le puzzle) en haut à droite de Chrome.
   - Cliquez sur l'icône de la **punaise** à côté de "Hypostasia Extractor" pour l'épingler à la barre d'outils.

### Pour Mozilla Firefox

1. **Téléchargez** ou clonez le code source du projet sur votre ordinateur.
2. Ouvrez Firefox et tapez `about:debugging#/runtime/this-firefox` dans la barre d'adresse.
3. Cliquez sur le bouton **Charger un module complémentaire temporaire...**.
4. Naviguez dans le dossier `extension` du projet et sélectionnez le fichier `manifest.json`.
5. L'extension est maintenant active.
   *Note : Les extensions chargées ainsi dans Firefox sont temporaires et disparaissent à la fermeture du navigateur.*
6. Pour l'épingler à la barre d'outils :
   - Cliquez sur l'icône **Extensions** (le puzzle) en haut à droite.
   - Cliquez sur la **roue dentée** à côté de "Hypostasia Extractor".
   - Sélectionnez **Épingler à la barre d'outils**.

## Configuration

Avant la première utilisation, vous devez indiquer à l'extension où se trouve votre serveur Hypostasia :

1. Cliquez sur l'icône de l'extension dans votre navigateur.
2. Saisissez l'URL de votre serveur :
   - Pour un usage local : `http://127.0.0.1:8000/`
   - Pour l'instance de test : `https://beta.hypostasia.org/`
3. Cliquez sur **OK** ou enregistrez.

## Connecter l'extension

L'extension s'authentifie par un **token** propre à votre compte. Vous n'avez pas à le manipuler :

1. Connectez-vous à votre instance Hypostasia dans ce navigateur.
2. Ouvrez la popup de l'extension et cliquez sur **« Connecter cette extension »**.

C'est tout. L'extension récupère votre token et affiche « Connecté : *votre nom* ».

> **Pourquoi un token et pas simplement votre session ?** Parce qu'une extension ne peut pas *écrire* avec votre session.
> Firefox donne à chaque installation d'extension une adresse interne aléatoire (`moz-extension://<uuid>`), différente sur
> chaque machine, et Django refuse toute écriture venant d'une origine qu'il ne connaît pas. Le token, lui, marche
> partout et de la même façon. La session sert donc une seule fois : à aller le chercher.
>
> Un token se révoque seul, sans vous déconnecter de nulle part : bouton **Régénérer** sur `/auth/token/`. Après quoi la
> popup affiche « Token invalide — reconnectez l'extension », et un clic suffit.

**Connecter une seconde machine ne déconnecte pas la première** : le token n'est jamais régénéré par ce bouton.

### À la main, si besoin

Le token reste visible sur **`/auth/token/`** (lien « Mon token API » dans le menu utilisateur) et se colle dans les
options de l'extension (clic droit sur l'icône → **Options**).

## Utilisation

1. Naviguez sur un article ou une page web que vous souhaitez sauvegarder.
2. Ouvrez la popup de l'extension.
3. Choisissez le **carnet** de destination dans le menu « Ranger dans ». Par défaut, la note va dans votre fourre-tout
   « À ranger », qui est créé automatiquement à la première capture qui en a besoin.
4. Cliquez sur le bouton **Recolter**.
5. Le message vous dit dans quel carnet la note a été enregistrée.

### Les messages que vous pouvez voir

| Message | Ce qu'il veut dire |
|---|---|
| *Enregistrée dans « … »* | c'est fait, la note est dans ce carnet |
| *Déjà enregistrée (note N)* | vous aviez déjà capturé cette page ; rien n'a été créé |
| *Cette page est déjà capturée sur ce serveur, dans un carnet auquel vous n'avez pas accès* | quelqu'un d'autre l'a prise. Une même URL ne peut exister qu'une fois par instance |
| *Token manquant ou invalide* | cliquez sur « Connecter cette extension » — voir ci-dessus |
