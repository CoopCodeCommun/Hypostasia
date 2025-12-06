# 📘 SPÉCIFICATION ULTRA-STRICTE POUR IA CODER — Plateforme d’Analyse Argumentative Augmentée

> Document normatif destiné à des **agents IA de génération de code**. Toute implémentation doit respecter **strictement** les contrats, schémas, endpoints, flux et contraintes ci-dessous.

---

## 0. Principes directeurs (OBLIGATOIRES)

- Architecture **monolithique Django + DRF + Templates**.
- Aucune SPA. **HTMX uniquement** pour l’interactivité.
- CSS **Bootstrap 5 uniquement**.
- Extension navigateur en **WebExtension Manifest V3**.
- LLM **stateless** : tout l’historique est stocké côté Django.
- Tout échange réseau utilise **JSON strict typé**.
- Toute entité IA est **traçable, versionnée et modifiable par l’utilisateur**.
- Utilisation de **`uv`** pour la gestion de l'environnement et le lancement de commandes (ex: `uv run python manage.py runserver`).

---

## 1. Schéma des entités (CONTRATS DE DONNÉES)

### 1.1 Page (IMMUTABLE SUR L’HTML ORIGINAL)

```json
{
  "id": int,
  "url": string,
  "html_original": string,
  "html_readability": string,
  "text_readability": string,
  "content_hash": string,
  "created_at": datetime,
  "updated_at": datetime
}
```

Règles :
- `html_original` ne doit **jamais être modifié** après création.
- `content_hash` = SHA256 du `text_readability`.

---

### 1.2 TextBlock (ANCRAGE DOM)

```json
{
  "id": int,
  "page": int,
  "selector": string,
  "start_offset": int,
  "end_offset": int,
  "text": string
}
```

Règles :
- `selector` doit être un **querySelector valide**.
- Offsets relatifs à `textContent`.

---

### 1.3 Argument

```json
{
  "id": int,
  "page": int,
  "text_block": int|null,
  "selector": string,
  "start_offset": int,
  "end_offset": int,
  "text_original": string,
  "summary": string,
  "stance": "pour" | "contre" | "neutre",
  "user_edited": boolean,
  "created_at": datetime
}
```

Règles :
- `summary` est toujours généré par IA.
- `user_edited = true` dès qu’un champ est modifié par un humain.

---

### 1.4 Commentaire Argument

```json
{
  "id": int,
  "argument": int,
  "author": int,
  "comment": string,
  "created_at": datetime
}
```

---

### 1.5 Prompt

```json
{
  "id": int,
  "name": string,
  "description": string,
  "created_at": datetime
}
```

---

### 1.6 TextInput (BRIQUE DE PROMPT)

```json
{
  "id": int,
  "prompt": int,
  "name": string,
  "role": "context" | "instruction" | "format",
  "content": string,
  "order": int
}
```

---

## 2. API REST STRICTE (DRF)

### 2.1 Création d’une Page (POST UNIQUE)

`POST /api/pages/`

```json
{
  "url": "https://site.fr/article",
  "html_original": "<html>...</html>",
  "html_readability": "<article>...</article>",
  "text_readability": "texte brut",
  "blocks": [
    {
      "selector": "article p:nth-of-type(3)",
      "start_offset": 0,
      "end_offset": 120,
      "text": "bloc de texte"
    }
  ]
}
```

Règles serveur :
- Si `url` existe déjà → **HTTP 409**.
- Création atomique Page + TextBlocks.

---

### 2.2 Lancement analyse IA

`POST /api/pages/{id}/analyze/`

```json
{
  "prompt_id": 3
}
```

Retour attendu :

```json
{
  "status": "processing"
}
```

---

### 2.3 Résultat d’analyse

`GET /api/pages/{id}/arguments/`

```json
[
  {
    "id": 12,
    "selector": "article p:nth-of-type(3)",
    "start_offset": 12,
    "end_offset": 54,
    "summary": "Argument en faveur du nucléaire",
    "stance": "pour"
  }
]
```

---

## 3. Pipeline IA OBLIGATOIRE

1. Concaténation ordonnée des `TextInput` du Prompt.
2. Insertion du `text_readability` comme variable.
3. Appel LLM.
4. Parsing **JSON strict**.
5. Création des `Argument`.

Aucun Argument ne peut exister sans Passage IA.

---

## 4. Front Django (HTMX STRICT)

### 4.1 Pages obligatoires

- `/pages/`
- `/pages/{id}/`
- `/pages/{id}/readability/` (View interne)
- `/pages/{id}/arguments/`
- `/prompts/`

### 4.2 Architecture API DRF
- Utilisation de `ViewSets` pour standardiser les CRUD.
- Actions explicites : `@action(detail=True, methods=['post']) def analyze(...)` au lieu de créer des vues séparées.
- Sérialiseurs dédiés (ex: `ArgumentUpdateSerializer` pour limiter les champs modifiables par l'utilisateur).

Toute interaction POST/PUT/PATCH doit être faite via **HTMX**.

---

## 5. Extension Navigateur (OBLIGATOIRE)

### 5.1 Capacités minimales

- Bouton d’activation
- Extraction DOM
- Extraction Readability
- Envoi POST `/api/pages/`
- Polling `/api/pages/{id}/arguments/`

---

### 5.2 Menu latéral injecté

Structure DOM minimale :

```html
<div id="argument-sidebar">
  <ul>
    <li data-selector="..." data-start="12">
      Résumé argument
    </li>
  </ul>
</div>
```

Fonctions obligatoires :
- Scroll fluide
- Surlignage du texte
- Tooltip résumé

---

## 6. Modification utilisateur d’un Argument

`PATCH /api/arguments/{id}/`

```json
{
  "summary": "Nouvelle formulation utilisateur",
  "stance": "contre"
}
```

Règle serveur :
- Met automatiquement `user_edited = true`.

---

## 7. Invalidation automatique

Si :
`hash(nouveau text_readability) != content_hash`

Alors :
- Tous les arguments passent au statut `invalidated = true` (champ à ajouter).

---

## 8. Règles de Conformité IA

Un agent IA de développement :
- N’a pas le droit d’introduire de SPA.
- N’a pas le droit d’enlever HTMX.
- N’a pas le droit de supprimer les offsets DOM.
- N’a pas le droit d’approximer les schémas JSON.

Toute violation = implémentation NON CONFORME.

---

✅ FIN DE LA SPÉCIFICATION ULTRA-STRICTE

