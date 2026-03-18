"""
Routes WebSocket de l'app front.
/ WebSocket routes for the front app.
"""
from django.urls import path
from front import consumers

websocket_urlpatterns = [
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
    path('ws/tache/<str:tache_id>/', consumers.ProgressionTacheConsumer.as_asgi()),
]
