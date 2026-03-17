"""
ASGI config for hypostasia project.
Gere HTTP (Django classique) + WebSocket (Channels).
/ Handles HTTP (standard Django) + WebSocket (Channels).
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')

# Initialise Django AVANT d'importer les consumers
# / Initialize Django BEFORE importing consumers
django_asgi_application = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from front.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_application,
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
