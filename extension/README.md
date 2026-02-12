# Hypostasia Extractor

Extension de navigateur pour extraire le contenu des pages web et l'envoyer vers une instance **Hypostasia** (backend
Django). Elle permet de sauvegarder proprement des articles pour une lecture ou une analyse ultérieure.

Une instance de test (bac à sable) est disponible à l'adresse : **https://beta.hypostasia.org/**

## Fonctionnalités

- **Extraction propre** : Utilise `Readability.js` (la technologie derrière le mode lecture de Firefox) pour extraire le
  contenu principal de la page en supprimant les publicités et menus inutiles.
- **Intégration Django** : Communique directement avec l'API de votre instance Hypostasia.
- **Vérification automatique** : L'extension vous indique si la page a déjà été enregistrée dans votre base de données.
- **Interface simple** : Une popup rapide pour configurer l'URL du serveur et lancer l'extraction.

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

## Utilisation

1. Naviguez sur un article ou une page web que vous souhaitez sauvegarder.
2. Ouvrez la popup de l'extension.
3. Cliquez sur le bouton **Recolter**.
4. Une notification vous confirmera si l'envoi vers Hypostasia a réussi.
