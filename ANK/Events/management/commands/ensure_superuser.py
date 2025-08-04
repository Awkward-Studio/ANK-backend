from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Ensures a superuser exists for the project."

    def handle(self, *args, **options):
        User = get_user_model()
        email = getattr(settings, "DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = getattr(settings, "DJANGO_SUPERUSER_PASSWORD", "changeme")

        # If you want to set role explicitly:
        extra_fields = {"role": "admin"}

        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                email=email, password=password, **extra_fields
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser created: {email}"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser already exists: {email}"))
