# Hypostasia

> **Plateforme d'analyse argumentative augmentée par Intelligence Artificielle.**

Hypostasia est un écosystème logiciel visant à extraire, analyser et réinjecter visuellement la couche argumentative du web. Grâce à une extension navigateur et un backend puissant, elle permet de révéler les structures logiques ("Hypostases") sous-jacentes à n'importe quelle page web.

---

## 🎯 Objectifs

Le projet répond à un besoin de décryptage de l'information en ligne :
1.  **Extraction** : Capturer le contenu pertinent d'une page web sans le bruit visuel (via *Readability*).
2.  **Analyse** : Utiliser des LLMs pour identifier, résumer et classifier les arguments (Pour / Contre / Neutre).
3.  **Visualisation** : Réinjecter ces arguments directement sur la page d'origine via une surcouche graphique (Extension).
4.  **Collaboration** : Permettre aux humains de corriger, affiner et valider les analyses de l'IA.

## 🏗 Architecture Technique

Hypostasia suit une architecture **monolithique moderne**, privilégiant la robustesse et la simplicité de maintenance (pas de SPA complexe).

### 🔙 Backend (Django)
*   **Framework** : Django + Django REST Framework (DRF).
*   **Frontend** : HTML-first avec **HTMX** pour l'interactivité et **Bootstrap 5** pour le style.
*   **Base de données** : SQLite (Dev) / PostgreSQL (Prod).
*   **Pipeline IA** : Gestionnaire de Prompts composables (Contexte + Instruction + Format) et analyse asynchrone.

### 🧩 Extension Navigateur
*   **Format** : WebExtension Manifest V3.
*   **Rôle** :
    *   Clonage du DOM et extraction du texte.
    *   Affichage d'une *Sidebar* latérale pour la navigation argumentative.
    *   **Linking Mechanism** : Algorithme robuste de recherche textuelle (`window.find`) pour surligner les citations exactes même dans un DOM complexe.

## 📚 Documentation

Pour une compréhension approfondie du projet, référez-vous aux documents suivants :

*   **[GUIDELINES.md](./GUIDELINES.md)** : 🛑 **Lecture obligatoire pour les développeurs**. Contient les règles strictes d'architecture, les schémas de données et les contraintes techniques (No-SPA, règles JSON, etc.).
*   **[IDEA.md](./IDEA.md)** : La vision globale du projet, les flux de données détaillés et la feuille de route.
*   **[API_DOC.md](./API_DOC.md)** : Documentation simplifiée de l'API REST pour les consommateurs (FALC).
*   **[LINKING_MECHANISM.md](./LINKING_MECHANISM.md)** : Explication technique du défi de la synchronisation entre le texte analysé (Readability) et le DOM affiché (Extension).

## 🚀 Installation et Démarrage

Le projet utilise `uv` pour la gestion des dépendances Python.

### Prérequis
*   Python 3.10+
*   [uv](https://github.com/astral-sh/uv)

### Setup Backend

```bash
# Installation des dépendances
uv sync

# Migrations de la base de données
uv run python manage.py migrate

# Lancer le serveur de développement
uv run python manage.py runserver
```

L'interface d'administration est accessible sur `http://localhost:8000/admin/`.

## 🤝 Contribution

Toute modification de code doit impérativement respecter les **[Guidelines](./GUIDELINES.md)**.
Les agents IA travaillant sur ce repo doivent vérifier la conformité de leurs modifications avec les contrats d'interface définis (JSON Schemas, Endpoints HTMX).
