from django.apps import AppConfig


class DepartmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Departments"

    def ready(self):
        import Departments.signals
