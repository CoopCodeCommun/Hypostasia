"""
Configuration Celery pour Hypostasia.
/ Celery configuration for Hypostasia.

Utilise Redis comme broker partout (dev, prod, boitier offline).
/ Uses Redis as broker everywhere (dev, prod, offline box).
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

# L'ingestion Docling part sur une file DEDIEE, consommee par un worker
# a concurrence 1 (supervisord.conf, programme celery_worker_docling) :
# une conversion charge des modeles lourds, et le serveur (8 Go) est
# partage avec la production. Jamais deux conversions en meme temps.
# / Docling ingestion goes to a dedicated queue with a concurrency-1
# worker: never two conversions at once on the shared 8 GB host.
celery_app.conf.task_routes = {
    "hypostasis_extractor.tasks_element.ingerer_un_fichier_avec_docling": {
        "queue": "ingestion_docling",
    },
}
