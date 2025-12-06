# 📘 Document préparatoire — Plateforme d’analyse argumentative augmentée

## 1. Objectif du projet

Créer une plateforme complète permettant :

* l’extraction de contenu web via une **extension navigateur**,

* l’analyse du texte extrait pour sortir les arguments par **IA (LLM)**,

* la **réinjection visuelle des arguments** directement sur la page web d’origine,

* le **suivi, l’annotation, la correction et l’enrichissement humain** des arguments,

* la **capitalisation des pages et des analyses** dans une interface Django.

## 2. Vue d’ensemble de l’architecture

```javascript
[Extension Navigateur]
  ├─ Extraction DOM
  ├─ Readability.js
  ├─ Envoi vers Django (HTML + texte + blocs)
  ├─ Réception des arguments
  └─ Injection sur la page originale (menu latéral + scroll)

                ↓

[Django API + Front]
  ├─ Stockage HTML original
  ├─ Stockage HTML Readability
  ├─ Analyse par IA via Prompts composables
  ├─ Gestion des arguments
  ├─ Commentaires et corrections utilisateurs
  └─ Front HTMX + Bootstrap
```

## 3. Flux de données principal

1. L’utilisateur clique sur l’extension.

2. L’extension :

   * clone le DOM,

   * applique Readability (extraction du texte utile),

   * extrait des blocs textuels avec leurs sélecteurs ( pour pouvoir positionner les arguments sur le site original ).

3. L’extension envoie à Django :

   * l’URL,

   * le HTML original,

   * le HTML Readability,

   * les blocs de texte avec leurs positions DOM.

4. Django construit un Prompt à partir de plusieurs TextInput et documents

   * Vue admin avec manipulation des prompts et de document à envoyer au LLM

5. Django envoie le prompt au LLM.

6. Le LLM retourne :

   * les arguments,

   * leur résumé,

   * leur position (pour / contre / neutre).

7. Django stocke les résultats.

8. Django renvoie les arguments à l’extension.

9. L’extension :

   * affiche un menu latéral listant les arguments,

   * permet le scroll vers la position exacte,

   * surligne le texte concerné.

10. L’utilisateur peut commenter ou modifier les arguments.

## 4. Modélisation Django (proposition)

### 4.1 Page

```python
class Page(models.Model):
    url = models.URLField(unique=True)
    html_original = models.TextField()
    html_readability = models.TextField()
    text_readability = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 4.2 Bloc de texte extrait

```python
class TextBlock(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    selector = models.CharField(max_length=500)
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    text = models.TextField()
```

### 4.3 Argument

```python
class Argument(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    text_block = models.ForeignKey(TextBlock, on_delete=models.SET_NULL, null=True)
    selector = models.CharField(max_length=500)
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()

    text_original = models.TextField()
    summary = models.TextField()

    stance = models.CharField(
        max_length=10,
        choices=[("pour", "Pour"), ("contre", "Contre"), ("neutre", "Neutre")]
    )

    user_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 4.4 Commentaire utilisateur sur un argument

```python
class ArgumentComment(models.Model):
    argument = models.ForeignKey(Argument, on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

## 5. Modèle de Prompt IA (composable)

### 5.1 Prompt

```python
class Prompt(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 5.2 TextInput (brique de prompt)

```python
class TextInput(models.Model):
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name="inputs")

    name = models.CharField(max_length=200)
    role = models.CharField(
        max_length=50,
        choices=[
            ("context", "Contexte sémantique"),
            ("instruction", "Instruction"),
            ("format", "Format de sortie")
        ]
    )

    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
```

### 5.3 Exemple de Prompt composable

* TextInput 1 (context)

  * « Le nucléaire est une source d’énergie bas carbone. »

* TextInput 2 (instruction)

  * « Extrais les arguments »

* TextInput 3 (format)

  * « Réponds en JSON structuré de cette façon : »

## 6. Guidelines Backend Django

### 6.1 Django + DRF

* Tous les modèles exposés via **serializers DRF**.

* Validation stricte des champs.

* Aucune logique métier dans les serializers.

### 6.2 Controllers via `viewsets.ViewSet`

* `PageViewSet`

* `TextBlockViewSet`

* `ArgumentViewSet`

* `PromptViewSet`

* `ArgumentCommentViewSet`

* Chaque ViewSet doit pouvoir :

  * rendre du JSON,

  * rendre des templates HTML.

### 6.3 Rendu Template Django

* Le rendu HTML côté serveur reste la source officielle.

* HTMX gère toutes les mises à jour dynamiques.

## 7. Front Django : HTMX + Bootstrap

### Objectifs

* Aucune SPA lourde.

* 100 % HTML-first.

* Responsive mobile et desktop.

### Pages principales

* Liste des pages analysées

* Détail d’une page

* Vue Readability + arguments

* Édition collaborative des arguments

* Gestion des prompts

## 8. Extension Navigateur (WebExtension)

### Rôles principaux

* Extraire le HTML original

* Extraire le texte Readability

* Découper en blocs avec sélecteurs

* Envoyer l’analyse à Django

* Recevoir les arguments

* Injecter l’interface front Django sur la page via un menu lateral collapsable

### Menu latéral

Fonctions :

* Liste des arguments

* Code couleur selon la position d'un tableau d'arguments

* Scroll automatique vers le texte concerné

* Surlignage du passage

* Affichage du résumé en tooltip

## 9. Interaction utilisateur avec les arguments

Chaque hypostase peut :

* être commenté,

* être corrigé,

* être reformulé,

* être réassigné

Un argument modifié passe en statut :

* `user_edited = True`

L’historique reste traçable.

## 10. Sécurité & intégrité

* Sanitization systématique du HTML reçu.

* Hash du contenu pour détecter les changements de page.

* Invalidation automatique des arguments si la page change.

* Journalisation de toutes les analyses IA.

## 11. Objectifs long terme

* Cartographie 3D des arguments via Polyèdre

* Export vers Markdown, PDF, OpenData

* Plateforme d'alimentation de débat collaborative

## 12. Finalité du document

Ce document est à la fois :

* un **cahier des charges fonctionnel**,

* un **socle d’architecture logicielle**,

* une **base de connaissances exploitable par des agents IA de développement**.
