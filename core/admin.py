from django.contrib import admin
from solo.admin import SingletonModelAdmin
from .models import (
    Page,
    Argument,
    ArgumentComment,
    Configuration,
    Prompt,
    TextInput,
    TextBlock,
    AIModel,
    Theme,
    Reformulation,
    HypostasisTag,
    Dossier,
    TranscriptionConfig,
    TranscriptionJob,
)


@admin.register(HypostasisTag)
class HypostasisTagAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(Configuration)
class ConfigurationAdmin(SingletonModelAdmin):
    """
    Admin singleton pour la configuration globale IA.
    Singleton admin for global AI configuration.
    """
    fields = ("ai_active", "ai_model")


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    """
    Admin pour les modèles AI avec sélection unifiée.
    """

    list_display = ("get_display_name", "model_choice", "provider", "is_active")
    list_filter = ("is_active", "provider")
    fields = ("name", "model_choice", "api_key", "temperature", "is_active")
    readonly_fields = ("provider", "model_name")

    def get_display_name(self, obj):
        return obj.get_display_name()

    get_display_name.short_description = "Nom du modèle"


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("name",)


class TextBlockInline(admin.TabularInline):
    model = TextBlock
    extra = 0
    fields = ("selector", "modes", "significant_extract", "text")
    show_change_link = True


class ArgumentInline(admin.TabularInline):
    model = Argument
    extra = 0
    fk_name = "page"


class ReformulationInline(admin.TabularInline):
    model = Reformulation
    extra = 0


class ArgumentBlockInline(admin.StackedInline):
    model = Argument
    extra = 0
    fk_name = "text_block"
    verbose_name = "Argument lié au bloc"
    verbose_name_plural = "Arguments liés au bloc"


@admin.register(Dossier)
class DossierAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("url", "dossier", "status", "created_at", "updated_at")
    search_fields = ("url", "title")
    list_filter = ("status", "dossier")
    inlines = [TextBlockInline, ArgumentInline]


@admin.register(TextBlock)
class TextBlockAdmin(admin.ModelAdmin):
    list_display = ("page", "selector", "modes", "start_offset", "end_offset")
    list_filter = ("page", "hypostases", "modes", "themes")
    search_fields = ("text", "significant_extract")
    filter_horizontal = ("themes", "hypostases")
    inlines = [ArgumentBlockInline, ReformulationInline]

    fieldsets = (
        ("Ancrage", {"fields": ("page", "selector", "start_offset", "end_offset")}),
        ("Contenu", {"fields": ("text", "significant_extract")}),
        ("Analyse", {"fields": ("hypostases", "modes", "themes")}),
    )


@admin.register(Argument)
class ArgumentAdmin(admin.ModelAdmin):
    list_display = ("summary", "page", "text_block", "user_edited", "created_at")
    list_filter = ("user_edited", "page")
    search_fields = ("summary", "text_original")
    autocomplete_fields = ["page", "text_block"]


@admin.register(ArgumentComment)
class ArgumentCommentAdmin(admin.ModelAdmin):
    list_display = ("author", "argument", "created_at")


class TextInputInline(admin.TabularInline):
    model = TextInput
    extra = 1


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    inlines = [TextInputInline]


@admin.register(TextInput)
class TextInputAdmin(admin.ModelAdmin):
    list_display = ("name", "prompt", "role", "order")
    list_filter = ("prompt", "role")
    ordering = ("prompt", "order")


@admin.register(TranscriptionConfig)
class TranscriptionConfigAdmin(admin.ModelAdmin):
    """
    Admin pour la configuration des outils de transcription audio.
    / Admin for audio transcription tool configuration.
    """
    list_display = ("name", "model_choice", "provider", "language", "diarization_enabled", "is_active")
    list_filter = ("provider", "is_active", "diarization_enabled")
    fields = ("name", "model_choice", "api_key", "language", "diarization_enabled", "max_speakers", "is_active", "provider", "model_name")
    readonly_fields = ("provider", "model_name")


@admin.register(TranscriptionJob)
class TranscriptionJobAdmin(admin.ModelAdmin):
    """
    Admin pour les jobs de transcription audio.
    / Admin for audio transcription jobs.
    """
    list_display = ("pk", "page", "status", "audio_filename", "processing_time_seconds", "created_at")
    list_filter = ("status",)
    readonly_fields = ("celery_task_id", "raw_result", "processing_time_seconds", "created_at", "updated_at")
    fields = (
        "page", "transcription_config", "celery_task_id", "status",
        "audio_filename", "error_message", "raw_result",
        "processing_time_seconds", "created_at", "updated_at",
    )
