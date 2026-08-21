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
    # La capture web (U4) partage la MEME file dediee : une conversion
    # Docling a la fois sur l'hote 8 Go, fichier ou HTML confondus.
    # / Web capture shares the same dedicated queue: one Docling
    # conversion at a time, file or HTML alike.
    "hypostasis_extractor.tasks_element.ingerer_une_capture_web_avec_docling": {
        "queue": "ingestion_docling",
    },
    # LE SECOND AVIS a sa propre file, consommee par un worker a
    # concurrence 1 et lance sous `nice -n 19` (supervisord, programme
    # celery_worker_juge_local).
    #
    # POURQUOI UNE TROISIEME FILE. Le juge local charge 5,13 Go (les quatre encodeurs residents, mesure du 19 aout) et coute
    # moins d'une demi-seconde de processeur PAR PAIRE ET PAR JUGE. Laisse sur la
    # file par defaut, qui est a concurrence 2, DEUX inferences
    # pourraient tourner ensemble — seize threads sur huit coeurs — et
    # Docling mourrait de faim.
    #
    # POURQUOI `nice` PLUTOT QU'UNE PORTE « attendre que le CPU baisse ».
    # Une porte affame en silence : sur une machine chargee elle ne
    # s'ouvre jamais, et rien ne le dit. `nice` laisse le noyau arbitrer
    # en continu, sans scrutation — le juge local prend ce qui est libre
    # et rend la main des que Docling arrive.
    # / A third queue: the local judge loads 7.7 GB and costs ~20 s of
    # CPU per pair. On the default (concurrency 2) queue, two inferences
    # could run at once and starve Docling. `nice` replaces a "wait for
    # idle CPU" gate, which would starve silently instead.
    "front.tasks.noter_avec_le_juge_local_task": {
        "queue": "verification_locale",
    },
}
