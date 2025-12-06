# Documentation de l'API (FALC)

Cette documentation explique comment utiliser l'API du projet pour les humains.

## 1. Les Pages (`/api/pages/`)

Une **Page** est l'enregistrement d'une URL analysée.

### Voir toutes les pages
- **URL :** `/api/pages/`
- **Méthode :** `GET`
- **Réponse :** Une liste des pages avec leur URL et date de création.

### Créer une nouvelle page
- **URL :** `/api/pages/`
- **Méthode :** `POST`
- **Corps (JSON) :**
  ```json
  {
    "url": "https://exemple.fr/article",
    "html_original": "<html>...</html>",
    "html_readability": "<p>Contenu...</p>",
    "text_readability": "Contenu brut...",
    "blocks": [
        {
            "selector": "p:nth-child(1)",
            "text": "Paragraphe 1...",
            "start_offset": 0,
            "end_offset": 100
        }
    ]
  }
  ```

### Lancer une analyse IA
- **URL :** `/api/pages/{id}/analyze/`
- **Méthode :** `POST`
- **Corps :** `{"prompt_id": 1}`
- **Effet :** Lance l'intelligence artificielle pour trouver des arguments.

### Voir les arguments d'une page
- **URL :** `/api/pages/{id}/arguments/`
- **Méthode :** `GET`
- **Réponse :** La liste complète des arguments trouvés sur cette page.

## 2. Les Arguments (`/api/arguments/`)

Un **Argument** est une phrase ou un paragraphe identifié comme "Pour" ou "Contre".

### Modifier un argument
- **URL :** `/api/arguments/{id}/`
- **Méthode :** `PATCH`
- **Corps :**
  ```json
  {
    "summary": "Nouveau résumé corrigé par l'humain",
    "stance": "contre"
  }
  ```
- **Note :** Cela marque automatiquement l'argument comme "modifié par un humain".

## 3. Les Prompts (`/api/prompts/`)

Un **Prompt** est la recette utilisée par l'IA.

- **URL :** `/api/prompts/`
- **Méthode :** `GET` (Liste) ou `POST` (Créer)
- **Détail :** `/api/prompts/{id}/` permet de voir les "briques" (texte d'instruction, contexte, format attendu).
