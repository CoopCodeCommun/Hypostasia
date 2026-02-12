# Guidelines — Hypostasia V3

> Regles d'architecture, conventions de code et patterns obligatoires.
> Ce document complete `CLAUDE.md` (specification stricte) avec les details pratiques d'implementation.

---

## 1. Architecture des apps Django

Le projet est organise en 3 apps avec des responsabilites distinctes :

| App | Responsabilite | Type de reponse |
|-----|----------------|-----------------|
| `core` | API JSON pour l'extension navigateur + modeles de donnees | JSON uniquement |
| `front` | Interface de lecture 3 colonnes (HTMX partials) | HTML uniquement |
| `hypostasis_extractor` | Pipeline LangExtract, analyseurs, tests LLM | HTML + JSON |

### Separation des responsabilites

- **`core/views.py`** ne sert que l'extension navigateur : `list()` et `create()` sur `PageViewSet`, plus `test_sidebar_view`. Aucun template de page complete.
- **`front/views.py`** gere toute l'interface utilisateur web : arbre de dossiers, lecture, extractions manuelles/IA, configuration IA.
- Les deux apps partagent les **modeles** de `core` mais jamais les **vues**.

### Routing

```
/                          → front:bibliotheque (page racine 3 colonnes)
/arbre/                    → front:ArbreViewSet (arbre de dossiers HTMX)
/lire/{id}/                → front:LectureViewSet (zone de lecture)
/lire/{id}/analyser/       → front:LectureViewSet.analyser (extraction IA)
/dossiers/                 → front:DossierViewSet (CRUD dossiers)
/pages/{id}/classer/       → front:PageViewSet.classer (classer une page)
/extractions/manuelle/     → front:ExtractionViewSet.manuelle
/extractions/creer_manuelle/ → front:ExtractionViewSet.creer_manuelle
/extractions/editer/       → front:ExtractionViewSet.editer
/extractions/modifier/     → front:ExtractionViewSet.modifier
/config-ia/status/         → front:ConfigurationIAViewSet.status
/config-ia/toggle/         → front:ConfigurationIAViewSet.toggle

/api/pages/                → core:PageViewSet (extension navigateur)
/api/test-sidebar/         → core:test_sidebar_view (extension sidebar)
/api/analyseurs/           → hypostasis_extractor (analyseurs)
```

---

## 2. Skill obligatoire : django-htmx-readable

Tout le code Django de ce projet suit le skill **`django-htmx-readable`** (voir `.claude/skills/django-htmx-readable/SKILL.md`). Ce skill impose des conventions strictes de lisibilite.

### 2.1 ViewSets explicites

```python
# OUI — ViewSet explicite avec requetes ecrites a la main
# YES — Explicit ViewSet with hand-written queries
class MonViewSet(viewsets.ViewSet):
    def list(self, request):
        tous_les_objets = MonModele.objects.all()
        return render(request, "mon_template.html", {"objets": tous_les_objets})

# NON — ModelViewSet avec magie cachee
# NO — ModelViewSet with hidden magic
class MonViewSet(viewsets.ModelViewSet):  # INTERDIT / FORBIDDEN
    queryset = MonModele.objects.all()
```

**Regle** : `viewsets.ViewSet` toujours, `ModelViewSet` jamais. Chaque requete ORM est ecrite explicitement dans la methode.

### 2.2 Validation par DRF Serializers

```python
# OUI — Serializer DRF pour la validation
# YES — DRF Serializer for validation
serializer = MonSerializer(data=request.data)
serializer.is_valid(raise_exception=True)
donnees = serializer.validated_data

# NON — Django Forms
# NO — Django Forms
form = MonForm(request.POST)  # INTERDIT / FORBIDDEN
```

**Regle** : Jamais de `forms.Form` ou `forms.ModelForm`. Toute validation passe par `serializers.Serializer`.

### 2.3 Noms de variables verbeux

```python
# OUI — on comprend ce que c'est en lisant le nom
# YES — you understand what it is just by reading the name
toutes_les_entites_du_job = job_extraction.entities.all()
html_panneau_analyse = render_to_string("front/includes/panneau_analyse.html", contexte)
dernier_job_termine = ExtractionJob.objects.filter(page=page, status="completed").first()

# NON — abbreviations cryptiques
# NO — cryptic abbreviations
ents = job.entities.all()
html = render_to_string("t.html", ctx)
j = ExtractionJob.objects.filter(page=p, status="completed").first()
```

### 2.4 Commentaires bilingues FR/EN

Chaque bloc de logique a un commentaire en francais suivi de sa traduction anglaise :

```python
# Recupere le dernier job d'extraction termine pour cette page
# / Retrieve the last completed extraction job for this page
dernier_job_termine = ExtractionJob.objects.filter(
    page=page, status="completed",
).order_by("-created_at").first()
```

### 2.5 HTMX pour toute interactivite

- Les ViewSets du front renvoient des **partials HTML**, jamais du JSON pour l'UI.
- Les actions custom (`@action`) renvoient du HTML via `render()` ou `HttpResponse()`.
- Les mises a jour multi-zones utilisent le pattern **OOB swap** (`hx-swap-oob`).
- Le CSRF token est transmis via `hx-headers` sur le `<body>`.

```html
<!-- Pattern OOB : mise a jour de 2 zones en une seule reponse HTMX -->
<!-- OOB pattern: update 2 zones in a single HTMX response -->
<div id="zone-principale">contenu principal</div>
<div id="zone-secondaire" hx-swap-oob="innerHTML:#zone-secondaire">
    contenu secondaire mis a jour en meme temps
</div>
```

### 2.6 Anti-patterns a eviter

| Interdit | Faire a la place |
|----------|------------------|
| `ModelViewSet` + `get_queryset()` | `ViewSet` + requetes explicites |
| Django Forms | DRF Serializers |
| Reponses JSON pour l'UI | Partials HTML + HTMX |
| Comprehensions complexes | Boucles for avec noms verbeux |
| Decorateurs cachant la logique metier | Appels de methodes explicites |
| `@action` qui renvoie du JSON pour l'UI | `@action` qui renvoie du HTML |

---

## 3. Routing DRF avec DefaultRouter

Toutes les URLs sont generees par `DefaultRouter`. Jamais de `path()` manuel pour des vues DRF.

```python
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"lire", LectureViewSet, basename="lire")
router.register(r"dossiers", DossierViewSet, basename="dossier")

urlpatterns = [
    path("", include(router.urls)),
]
```

Les actions custom (`@action`) generent automatiquement leurs URLs :
- `@action(detail=True)` → `/lire/{pk}/analyser/`
- `@action(detail=False)` → `/extractions/manuelle/`

---

## 4. Templates front

```
front/templates/front/
├── bibliotheque.html              # Page complete 3 colonnes (shell)
├── base.html                      # Page complete pour acces direct (F5)
└── includes/                      # Partials HTMX
    ├── arbre_dossiers.html        # Arbre de navigation
    ├── lecture_principale.html     # Zone de lecture
    ├── panneau_analyse.html       # Panneau droit (extractions)
    ├── extraction_results.html    # Cartes d'extraction
    ├── extraction_manuelle_form.html  # Formulaire extraction manuelle
    └── config_ia_toggle.html      # Toggle IA on/off
```

Les templates de `core/` ne servent que l'extension navigateur (sidebar).

---

## 5. Commandes

Toutes les commandes Django se lancent via `uv run` :

```bash
uv run python manage.py runserver
uv run python manage.py migrate
uv run python manage.py check
```

---

## 6. CSS

Le front utilise **Tailwind CSS** (via CDN). La specification `CLAUDE.md` mentionne Bootstrap 5, mais le code actuel utilise Tailwind partout. Continuer avec Tailwind pour la coherence.

---

## 7. Resume des regles

1. `viewsets.ViewSet` explicite, jamais `ModelViewSet`
2. `DefaultRouter` DRF, jamais `path()` manuel pour DRF
3. `serializers.Serializer` DRF, jamais Django Forms
4. HTMX pour toute interactivite, jamais de SPA
5. Noms de variables verbeux et explicites
6. Commentaires bilingues FR/EN
7. `core` = API JSON extension, `front` = interface HTML HTMX
8. `uv run` pour toutes les commandes
