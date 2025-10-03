import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

print(
    "🛠️  ASGI module loaded, DJANGO_SETTINGS_MODULE =",
    os.environ.get("DJANGO_SETTINGS_MODULE"),
    os.environ.get("DJANGO_RSVP_SECRET"),
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ANK.settings")

django_asgi_app = get_asgi_application()

from ANK.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,  # normal Django views
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)  # our WS routes
        ),
    }
)
