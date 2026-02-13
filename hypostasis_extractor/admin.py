"""
Admin configuration pour Hypostasis Extractor.
Configuration de l'interface d'administration Django.
"""

from django.contrib import admin
from .models import (
    ExtractionJob, ExtractedEntity, ExtractionExample, JobExampleMapping,
    AnalyseurSyntaxique, PromptPiece, AnalyseurExample, ExampleExtraction, ExtractionAttribute,
    AnalyseurTestRun, TestRunExtraction,
    QuestionnairePrompt, QuestionnairePromptPiece,
)


class ExtractedEntityInline(admin.TabularInline):
    """
    Inline admin pour afficher les entites extraites directement dans le job.
    / Inline admin to display extracted entities directly in the job.

    Pourquoi un inline ? / Why an inline?
    - Permet de voir/modifier les entites SANS quitter la page du job
    - Allows viewing/editing entities WITHOUT leaving the job page
    - Evite de naviguer entre plusieurs pages admin
    - Prevents navigation between multiple admin pages
    """

    model = ExtractedEntity
    extra = 0  # Pas de lignes vides par defaut / No empty rows by default
    fields = ("extraction_class", "extraction_text", "hypostasis_tag", "user_validated")
    readonly_fields = (
        "start_char",
        "end_char",
    )  # Positions auto-calculees par LangExtract


class JobExampleMappingInline(admin.TabularInline):
    """
    Inline admin pour gerer les exemples few-shot associes a un job.
    / Inline admin to manage few-shot examples associated with a job.

    Pourquoi une table de liaison separee ? / Why a separate junction table?
    - Un job peut utiliser PLUSIEURS exemples (relation many-to-many)
    - A job can use MULTIPLE examples (many-to-many relationship)
    - Les exemples sont REUTILISABLES entre differents jobs
    - Examples are REUSABLE across different jobs
    - On peut controler l'ORDRE des exemples (champ 'order')
    - We can control the ORDER of examples ('order' field)
    """

    model = JobExampleMapping
    extra = 1  # Une ligne vide pour ajouter facilement / One empty row for easy adding
    autocomplete_fields = ["example"]  # Recherche rapide si beaucoup d'exemples


@admin.register(ExtractionJob)
class ExtractionJobAdmin(admin.ModelAdmin):
    """
    Admin principal pour les jobs d'extraction LangExtract.
    / Main admin for LangExtract extraction jobs.

    ARCHITECTURE EXPLIQUEE / ARCHITECTURE EXPLAINED:
    ================================================

    Ce n'est pas juste "un objet" - c'est un workflow complet:
    / It's not just "one object" - it's a complete workflow:

    1. ExtractionJob (le conteneur principal / the main container)
       - Represente UNE analyse LangExtract sur une Page
       - Represents ONE LangExtract analysis on a Page
       - Contient: config (model AI, prompt), statut, resultats JSON
       - Contains: config (AI model, prompt), status, JSON results

    2. ExtractedEntity (les resultats / the results)
       - Chaque entite extraite cree un objet separe
       - Each extracted entity creates a separate object
       - Ex: "probleme: changement climatique", "axiome: loi de Moore"
       - Ex: "problem: climate change", "axiom: Moore's law"
       - Ces entites sont affichees en INLINE ci-dessous
       - These entities are displayed INLINE below

    3. ExtractionExample (les exemples few-shot / few-shot examples)
       - Objets REUTILISABLES stockes separement
       - REUSABLE objects stored separately
       - Servent a guider le LLM (comme l'apprentissage par l'exemple)
       - Used to guide the LLM (like learning by example)
       - Associes via JobExampleMapping (table de liaison)
       - Associated via JobExampleMapping (junction table)

    Pourquoi autant d'objets ? / Why so many objects?
    - Separation des responsabilites (SRP)
    - Separation of concerns (SRP)
    - Reutilisabilite des exemples entre jobs
    - Reusability of examples across jobs
    - Traçabilite complete (quel job a produit quelle entite)
    - Complete traceability (which job produced which entity)
    """

    list_display = (
        "name",
        "page",
        "ai_model",
        "status",
        "entities_count",
        "created_at",
    )
    list_filter = ("status", "ai_model__provider", "created_at")
    search_fields = ("name", "prompt_description", "page__url")
    readonly_fields = ("created_at", "updated_at", "processing_time_seconds")
    inlines = [JobExampleMappingInline, ExtractedEntityInline]

    fieldsets = (
        (
            "Configuration",
            {"fields": ("name", "page", "ai_model", "prompt_description")},
        ),
        (
            "Resultats",
            {"fields": ("status", "entities_count", "raw_result", "error_message")},
        ),
        (
            "Metriques",
            {"fields": ("processing_time_seconds",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ExtractedEntity)
class ExtractedEntityAdmin(admin.ModelAdmin):
    """
    Admin pour les entites extraites individuellement.
    / Admin for individually extracted entities.

    Pourquoi un admin separe en PLUS de l'inline ?
    / Why a separate admin IN ADDITION to the inline?

    - Recherche globale: trouver TOUTES les entites "probleme" ou "axiome"
    - Global search: find ALL "problem" or "axiom" entities
    - Validation en masse: valider plusieurs entites a la fois
    - Bulk validation: validate multiple entities at once
    - Filtrage avance: par classe, tag hypostasis, validation user
    - Advanced filtering: by class, hypostasis tag, user validation
    - Acces direct sans passer par le job parent
    - Direct access without going through parent job
    """

    list_display = (
        "extraction_class",
        "extraction_text_short",
        "job",
        "hypostasis_tag",
        "user_validated",
    )
    list_filter = ("extraction_class", "user_validated", "hypostasis_tag")
    search_fields = ("extraction_text", "attributes")
    autocomplete_fields = ["job", "hypostasis_tag"]

    def extraction_text_short(self, obj):
        """
        Tronque le texte pour l'affichage dans la liste.
        / Truncates text for display in the list.
        """
        return (
            obj.extraction_text[:50] + "..."
            if len(obj.extraction_text) > 50
            else obj.extraction_text
        )

    extraction_text_short.short_description = "Texte extrait"


@admin.register(ExtractionExample)
class ExtractionExampleAdmin(admin.ModelAdmin):
    """
    Admin pour les exemples few-shot reutilisables.
    / Admin for reusable few-shot examples.

    C'est la LIBRAIRIE d'exemples pour LangExtract.
    / This is the EXAMPLE LIBRARY for LangExtract.

    Pourquoi separe des jobs ? / Why separate from jobs?
    - On cree les exemples UNE FOIS, on les reutilise PARTOUT
    - Create examples ONCE, reuse them EVERYWHERE
    - Bibliotheque centralisee de patterns d'extraction
    - Centralized library of extraction patterns
    - Un exemple peut etre utilise dans 10 jobs differents
    - One example can be used in 10 different jobs
    - Activation/desactivation simple (is_active)
    - Simple enable/disable (is_active)
    """

    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description", "example_text")

    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        ("Contenu Exemple", {"fields": ("example_text", "example_extractions")}),
    )


# =============================================================================
# Admin pour les Analyseurs Syntaxiques
# =============================================================================

class PromptPieceInline(admin.TabularInline):
    model = PromptPiece
    extra = 1
    fields = ("name", "role", "content", "order")


class AnalyseurExampleInline(admin.TabularInline):
    model = AnalyseurExample
    extra = 0
    fields = ("name", "example_text", "order")


@admin.register(AnalyseurSyntaxique)
class AnalyseurSyntaxiqueAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    inlines = [PromptPieceInline, AnalyseurExampleInline]


class ExtractionAttributeInline(admin.TabularInline):
    model = ExtractionAttribute
    extra = 1
    fields = ("key", "value")


class ExampleExtractionInline(admin.TabularInline):
    model = ExampleExtraction
    extra = 0
    fields = ("extraction_class", "extraction_text", "order")


@admin.register(AnalyseurExample)
class AnalyseurExampleAdmin(admin.ModelAdmin):
    list_display = ("name", "analyseur", "order")
    list_filter = ("analyseur",)
    search_fields = ("name", "example_text")
    inlines = [ExampleExtractionInline]


@admin.register(ExampleExtraction)
class ExampleExtractionAdmin(admin.ModelAdmin):
    list_display = ("extraction_class", "extraction_text_short", "example")
    search_fields = ("extraction_class", "extraction_text")
    inlines = [ExtractionAttributeInline]

    def extraction_text_short(self, obj):
        return obj.extraction_text[:50] + "..." if len(obj.extraction_text) > 50 else obj.extraction_text
    extraction_text_short.short_description = "Texte"


# =============================================================================
# Admin pour les Test Runs
# =============================================================================

class TestRunExtractionInline(admin.TabularInline):
    """
    Inline pour voir les extractions obtenues dans un test run.
    Tous les champs en lecture seule — c'est un resultat, pas editable.
    / Inline to view extractions obtained in a test run.
    All fields read-only — it's a result, not editable.
    """
    model = TestRunExtraction
    extra = 0
    fields = ("order", "extraction_class", "extraction_text", "start_pos", "end_pos", "attributes", "human_annotation", "annotation_note")
    readonly_fields = ("order", "extraction_class", "extraction_text", "start_pos", "end_pos", "attributes")


@admin.register(AnalyseurTestRun)
class AnalyseurTestRunAdmin(admin.ModelAdmin):
    """
    Admin pour explorer les test runs LLM.
    Chaque test run = un appel LangExtract sur un exemple avec un modele donne.
    / Admin to explore LLM test runs.
    Each test run = one LangExtract call on an example with a given model.
    """
    list_display = (
        "id",
        "ai_model_display_name",
        "analyseur",
        "example_name",
        "status",
        "extractions_count",
        "processing_time_display",
        "created_at",
    )
    list_filter = ("status", "analyseur", "ai_model_display_name", "created_at")
    search_fields = ("ai_model_display_name", "example__name", "analyseur__name")
    readonly_fields = (
        "created_at",
        "processing_time_seconds",
        "extractions_count",
        "prompt_snapshot",
        "raw_result",
        "error_message",
        "ai_model_display_name",
    )
    list_select_related = ("analyseur", "example", "ai_model")
    inlines = [TestRunExtractionInline]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Test", {
            "fields": ("analyseur", "example", "ai_model", "ai_model_display_name", "status"),
        }),
        ("Resultats", {
            "fields": ("extractions_count", "processing_time_seconds", "raw_result", "error_message"),
        }),
        ("Prompt snapshot", {
            "fields": ("prompt_snapshot",),
            "classes": ("collapse",),
            "description": "Le prompt complet tel qu'envoye au LLM au moment du test.",
        }),
        ("Timestamps", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def example_name(self, obj):
        return obj.example.name if obj.example else "—"
    example_name.short_description = "Exemple"
    example_name.admin_order_field = "example__name"

    def processing_time_display(self, obj):
        if obj.processing_time_seconds is not None:
            return f"{obj.processing_time_seconds:.1f}s"
        return "—"
    processing_time_display.short_description = "Duree"
    processing_time_display.admin_order_field = "processing_time_seconds"


@admin.register(TestRunExtraction)
class TestRunExtractionAdmin(admin.ModelAdmin):
    """
    Admin pour explorer les extractions individuelles obtenues lors des tests.
    Permet de chercher/filtrer par classe, par test run, etc.
    / Admin to explore individual extractions obtained during tests.
    """
    list_display = (
        "id",
        "extraction_class",
        "extraction_text_short",
        "human_annotation",
        "test_run_model",
        "test_run_example",
        "start_pos",
        "end_pos",
        "order",
    )
    list_filter = ("extraction_class", "human_annotation", "test_run__ai_model_display_name", "test_run__analyseur")
    search_fields = ("extraction_class", "extraction_text", "test_run__ai_model_display_name", "annotation_note")
    readonly_fields = ("test_run", "extraction_class", "extraction_text", "start_pos", "end_pos", "attributes", "order", "promoted_to_extraction")
    list_select_related = ("test_run", "test_run__example")

    fieldsets = (
        ("Extraction", {
            "fields": ("test_run", "extraction_class", "extraction_text", "order"),
        }),
        ("Position (grounding)", {
            "fields": ("start_pos", "end_pos"),
        }),
        ("Attributs", {
            "fields": ("attributes",),
            "description": "Attributs extraits par le LLM au format JSON.",
        }),
        ("Annotation humaine", {
            "fields": ("human_annotation", "annotation_note", "promoted_to_extraction"),
            "description": "Annotation humaine : validee (copiee en extraction attendue) ou rejetee.",
        }),
    )

    def extraction_text_short(self, obj):
        return obj.extraction_text[:60] + "..." if len(obj.extraction_text) > 60 else obj.extraction_text
    extraction_text_short.short_description = "Texte extrait"

    def test_run_model(self, obj):
        return obj.test_run.ai_model_display_name
    test_run_model.short_description = "Modele"
    test_run_model.admin_order_field = "test_run__ai_model_display_name"

    def test_run_example(self, obj):
        return obj.test_run.example.name if obj.test_run.example else "—"
    test_run_example.short_description = "Exemple"
    test_run_example.admin_order_field = "test_run__example__name"


# =============================================================================
# Admin pour les Questionnaire Prompts
# =============================================================================

class QuestionnairePromptPieceInline(admin.TabularInline):
    model = QuestionnairePromptPiece
    extra = 1
    fields = ("name", "role", "content", "order")


@admin.register(QuestionnairePrompt)
class QuestionnairePromptAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "inclure_extractions", "inclure_texte_original", "created_at", "updated_at")
    list_filter = ("is_active", "inclure_extractions", "inclure_texte_original")
    search_fields = ("name", "description")
    inlines = [QuestionnairePromptPieceInline]


# Note: JobExampleMapping n'a pas besoin d'un @admin.register separe
# car c'est une table de liaison pure (through table)
# On la gere uniquement via l'inline dans ExtractionJobAdmin
# / Note: JobExampleMapping doesn't need a separate @admin.register
# because it's a pure junction table (through table)
# We only manage it via the inline in ExtractionJobAdmin
