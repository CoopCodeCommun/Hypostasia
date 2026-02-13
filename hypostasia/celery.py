"""
Configuration Celery pour Hypostasia.
/ Celery configuration for Hypostasia.

Utilise django-db comme broker et backend (SQLite, pas de Redis).
/ Uses django-db as broker and backend (SQLite, no Redis).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")

# Creation de l'app Celery avec le namespace CELERY_ pour les settings Django
# / Create Celery app with CELERY_ namespace for Django settings
celery_app = Celery("hypostasia")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

# Decouverte automatique des taches dans chaque app Django
# / Auto-discover tasks in every Django app
celery_app.autodiscover_tasks()
