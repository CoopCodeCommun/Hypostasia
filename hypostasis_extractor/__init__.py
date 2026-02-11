import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')

import django
try:
    django.setup()
except RuntimeError:
    pass
