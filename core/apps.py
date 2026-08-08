from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Import des signals pour les enregistrer (validation des
        # categories d'appartenance, SPEC-corpus § 3.4).
        # / Import signals to register them (membership category
        # validation).
        from . import signals  # noqa: F401
