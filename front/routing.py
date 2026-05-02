"""
Routes WebSocket de l'app front.
/ WebSocket routes for the front app.

LOCALISATION : front/routing.py
"""
from django.urls import path
from front import consumers

websocket_urlpatterns = [
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
]
