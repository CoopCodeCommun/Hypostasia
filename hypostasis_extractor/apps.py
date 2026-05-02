from django.apps import AppConfig


class HypostasisExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hypostasis_extractor'
    verbose_name = 'Hypostasis Extractor (LangExtract)'

    def ready(self):
        # Import des signals pour les enregistrer / Import signals to register them
        from . import signals  # noqa: F401
