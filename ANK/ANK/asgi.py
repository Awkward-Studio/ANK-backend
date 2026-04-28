import logging
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

logger = logging.getLogger(__name__)
logger.info("ASGI module loaded; DJANGO_SETTINGS_MODULE=%s", os.environ.get("DJANGO_SETTINGS_MODULE"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ANK.settings")

django_asgi_app = get_asgi_application()

from ANK.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
