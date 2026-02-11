---
name: django-htmx-readable
description: Django + HTMX development with explicit, readable code patterns. Use when working on Django projects with HTMX for server-rendered UIs, especially when writing ViewSets, templates with HTMX interactions, or form handling. Prioritizes code readability over cleverness - verbose variable names, explicit methods, no magic abstractions.
---

# Django + HTMX — Readable Patterns

Guidelines for building Django applications with HTMX, focused on explicit, readable code that any developer can understand.

## Core Philosophy: Readability First

- **Verbose variable names** — length is not a problem
- **Explicit over implicit** — avoid magic, decorators that hide logic, metaclasses
- **Simple for loops** over complex comprehensions
- **Bilingual comments FR/EN** — explain the *why* AND the *what*
- **Code reads top-to-bottom** — no need to jump across 5 files to understand flow

## ViewSet Pattern (DRF)

Use `viewsets.ViewSet`, **never** `ModelViewSet`. Write explicit methods.

```python
from rest_framework import viewsets, permissions, serializers
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


class BookViewSet(viewsets.ViewSet):
    """
    ViewSet explicite pour la gestion des livres.
    Explicit ViewSet for book management.
    """
    # Pas de queryset magique — on ecrit explicitement chaque requete
    # No magic queryset — we write explicit queries
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def list(self, request):
        # Requete explicite, pas de get_queryset() cache
        # Explicit query, no hidden get_queryset()
        books = Book.objects.select_related('author').all()
        
        # Nom de variable verbeux qui explique ce qu'on filtre
        # Verbose variable name explaining what we filter
        books_published_only = books.filter(is_published=True)
        
        return render(request, "books/list.html", {
            'books': books_published_only
        })
    
    def retrieve(self, request, pk=None):
        # get_object_or_404 explicite
        # Explicit get_object_or_404
        book = get_object_or_404(Book, uuid=pk)
        
        return render(request, "books/detail.html", {
            'book': book
        })
    
    @method_decorator(login_required)
    def create(self, request):
        # Validation via Serializer DRF, jamais Django Forms
        # Validation via DRF Serializer, never Django Forms
        serializer = BookCreateSerializer(data=request.POST)
        
        if serializer.is_valid():
            book = serializer.save(created_by=request.user)
            
            # Redirection apres creation (POST-redirect-GET pattern)
            # Redirect after creation (POST-redirect-GET pattern)
            return redirect('book-detail', pk=book.uuid)
        
        # Retour du formulaire avec erreurs
        # Return form with errors
        return render(request, "books/form.html", {
            'form_errors': serializer.errors,
            'data': request.POST
        })
```

## Validation: DRF Serializers Only

**Never use Django Forms.** Always use `serializers.Serializer` or `serializers.ModelSerializer` for validation.

```python
from rest_framework import serializers


class BookCreateSerializer(serializers.Serializer):
    """
    Validation explicite des donnees du formulaire.
    Explicit form data validation.
    """
    title = serializers.CharField(
        max_length=200,
        error_messages={
            'required': 'Le titre est obligatoire / Title is required',
            'max_length': 'Titre trop long (max 200) / Title too long (max 200)'
        }
    )
    description = serializers.CharField(required=False, allow_blank=True)
    publication_date = serializers.DateField(required=False)
    
    def validate_title(self, value):
        # Validation personnalisee avec nom explicite
        # Custom validation with explicit name
        title_cleaned = value.strip()
        
        if Book.objects.filter(title__iexact=title_cleaned).exists():
            raise serializers.ValidationError(
                'Un livre avec ce titre existe deja / A book with this title already exists'
            )
        
        return title_cleaned
    
    def create(self, validated_data):
        # Creation explicite, pas de magic save()
        # Explicit creation, no magic save()
        book = Book.objects.create(
            title=validated_data['title'],
            description=validated_data.get('description', ''),
            publication_date=validated_data.get('publication_date'),
            created_by=self.context['request'].user
        )
        return book
```

## HTMX Integration

Server-rendered HTML only. No JSON for UI. HTMX handles dynamic interactions.

### Basic HTMX Attributes

```html
<!-- Chargement dynamique d'un contenu -->
<!-- Dynamic content loading -->
<button 
    hx-get="{% url 'book-partial-detail' pk=book.uuid %}"
    hx-target="#book-detail-container"
    hx-swap="innerHTML"
>
    Voir details
</button>

<div id="book-detail-container">
    <!-- Le contenu sera injecte ici -->
    <!-- Content will be injected here -->
</div>

<!-- Formulaire avec mise a jour partielle -->
<!-- Form with partial update -->
<form 
    hx-post="{% url 'book-create' %}"
    hx-target="#book-list"
    hx-swap="beforeend"
>
    {% csrf_token %}
    <input type="text" name="title" placeholder="Titre du livre">
    <button type="submit">Ajouter</button>
</form>
```

### Anti-Blink Navigation

Pour naviguer liste/detail sans rechargement de page ni clignotement :

```html
<!-- Dans la liste -->
<!-- In the list -->
<a 
    href="{% url 'book-detail' pk=book.uuid %}"
    hx-get="{% url 'book-detail' pk=book.uuid %}"
    hx-target="body"
    hx-swap="innerHTML"
    hx-push-url="true"
>
    {{ book.title }}
</a>

<!-- Le href est conserve pour le fallback sans JS -->
<!-- href is kept for no-JS fallback -->
```

### CSRF Token

Toujours inclure le token CSRF dans les requetes HTMX :

```html
<!-- Dans le template de base -->
<!-- In base template -->
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
    ...
</body>
```

## Toasts/Notifications with HTMX

Pattern pour afficher des messages apres une action :

**Controller:**
```python
import json
from django.contrib import messages
from django.contrib.messages import get_messages


class BookViewSet(viewsets.ViewSet):
    
    def delete(self, request, pk=None):
        book = get_object_or_404(Book, uuid=pk)
        book_title_for_message = book.title  # Variable explicite avant suppression
        book.delete()
        
        # Message pour l'utilisateur
        # Message for the user
        messages.add_message(
            request, 
            messages.SUCCESS, 
            f'"{book_title_for_message}" a ete supprime / has been deleted'
        )
        
        # Recupere tous les messages pour le toast
        # Get all messages for toast
        messages_list = get_messages(request)
        toast_payload = [
            {"level": msg.level_tag, "text": str(msg)} 
            for msg in messages_list
        ]
        
        response = render(request, "books/partials/empty.html")
        response["HX-Trigger"] = json.dumps({"toast": {"items": toast_payload}})
        return response
```

**Template (JavaScript minimal pour les toasts):**
```html
<!-- Dans le template de base -->
<!-- In base template -->
<script>
    document.body.addEventListener('toast', function(evt) {
        const items = evt.detail.items;
        items.forEach(function(item) {
            // Afficher le toast avec SweetAlert2 ou autre
            // Display toast with SweetAlert2 or other
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: item.level,
                title: item.text,
                showConfirmButton: false,
                timer: 3000
            });
        });
    });
</script>
```

## Custom Actions with @action

Pour les actions supplementaires sur un objet :

```python
from rest_framework.decorators import action


class BookViewSet(viewsets.ViewSet):
    
    @action(detail=True, methods=["POST"])
    def publish(self, request, pk=None):
        """
        Publier un livre (action personnalisee).
        Publish a book (custom action).
        """
        book = get_object_or_404(Book, uuid=pk)
        
        # Logique explicite, pas de magic
        # Explicit logic, no magic
        if book.is_published:
            return render(request, "books/partials/already_published.html", {
                'book': book
            })
        
        book.is_published = True
        book.published_at = timezone.now()
        book.save(update_fields=['is_published', 'published_at'])
        
        # Retourne un partiel HTMX
        # Returns HTMX partial
        return render(request, "books/partials/publish_button.html", {
            'book': book
        })
    
    @action(detail=False, methods=["GET"])
    def search(self, request):
        """
        Recherche de livres (action sur la collection).
        Search books (collection action).
        """
        search_query_from_user = request.GET.get('q', '').strip()
        
        if len(search_query_from_user) < 3:
            books_found = Book.objects.none()
        else:
            books_found = Book.objects.filter(
                title__icontains=search_query_from_user
            )[:20]
        
        return render(request, "books/partials/search_results.html", {
            'books': books_found,
            'query': search_query_from_user
        })
```

## Template Structure

Organisation des templates :

```
templates/
├── base.html              # Template de base avec HTMX, CSRF
├── books/
│   ├── list.html          # Page complete liste
│   ├── detail.html        # Page complete detail
│   └── partials/          # Partiels HTMX
│       ├── _book_card.html
│       ├── _search_results.html
│       └── _publish_button.html
```

## URL Routing

```python
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'books', BookViewSet, basename='book')

urlpatterns = [
    # Les URLs sont generees par le router
    # URLs are generated by the router
    path('', include(router.urls)),
]
```

Generated URLs:
- `GET /books/` → `list()`
- `GET /books/<pk>/` → `retrieve()`
- `POST /books/` → `create()`
- `POST /books/<pk>/publish/` → `publish()` (custom action)

## Complete Examples

See references for complete working examples:
- `references/viewset-patterns.md` — Full ViewSet implementations
- `references/htmx-patterns.md` — Common HTMX interaction patterns

## Anti-Patterns to Avoid

| Don't | Do Instead |
|-------|------------|
| `ModelViewSet` with `get_queryset()` magic | Explicit `ViewSet` with explicit queries |
| Django Forms | DRF Serializers |
| JSON responses for UI | HTML partials with HTMX |
| `hx-swap="outerHTML"` on `<html>` or `<head>` | `hx-target="body" hx-swap="innerHTML"` |
| Complex one-liner comprehensions | Simple for loops with verbose names |
| Decorators hiding business logic | Explicit method calls |
| `@action` that returns JSON for UI | `@action` that returns HTML partials |


## Evaluation

You can find evals on 
- `evals/evals.json` — Full evaluation file - french version
- `evals/evals_en.json` — Full evaluation file - english version
- `evals/guide_evaluation.md` — Guide to understand evaluation needed - french version
- `evals/evaluation_guide_en.md` — Guide to understand evaluation needed - english version
