from django.urls import re_path
from Events.consumers import EventRegistrationConsumer

# WebSocket: ws://<host>/ws/events/<event_uuid>/
websocket_urlpatterns = [
    re_path(
        r"^ws/events/(?P<event_id>[0-9a-f-]{36})/$", EventRegistrationConsumer.as_asgi()
    ),
]
