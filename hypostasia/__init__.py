import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')

# Auto-setup Django pour les imports hors manage.py (scripts, python -c, etc.)
# / Auto-setup Django for imports outside manage.py (scripts, python -c, etc.)
# On utilise un try/except car populate() leve RuntimeError si deja en cours
# / We use try/except because populate() raises RuntimeError if already running
import django
try:
    django.setup()
except RuntimeError:
    # Django est deja en train de se charger (reentrance) → on laisse faire
    # / Django is already loading (reentrant call) → let it proceed
    pass
