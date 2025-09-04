from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Events"

    def ready(self):
        # Ensures signal handlers are registered
        import Events.signals  # noqa: F401
