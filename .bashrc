# Aliases pour le conteneur Hypostasia
# Dev : un seul runserver ASGI (daphne remplace runserver, gere HTTP + WS)
# / Dev: single ASGI runserver (daphne replaces runserver, handles HTTP + WS)
alias rsp='uv run python manage.py runserver 0.0.0.0:8000'

# Prod-like : deux moteurs separes (miroir de supervisord.conf)
# / Prod-like: two separate engines (mirrors supervisord.conf)
alias guni='uv run gunicorn hypostasia.wsgi:application --bind 0.0.0.0:8001 --workers 4 --capture-output'
alias daphne='uv run daphne -b 0.0.0.0 -p 8000 hypostasia.asgi:application'

alias cel='uv run celery -A hypostasia worker --loglevel=info'
