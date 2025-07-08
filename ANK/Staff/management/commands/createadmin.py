from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = "Create a superuser non-interactively using environment variables"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
        role = os.getenv(
            "DJANGO_SUPERUSER_ROLE", "staff"
        )  # Default to 'staff' if not set
        name = os.getenv("DJANGO_SUPERUSER_NAME", "")
        phone = os.getenv("DJANGO_SUPERUSER_PHONE", "")

        if not all([email, password]):
            self.stderr.write("Missing required environment variables.")
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(f"User with email {email} already exists.")
            return

        user = User.objects.create_superuser(
            email=email,
            password=password,
            role=role,
            name=name,
            contact_phone=phone,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Superuser {email} created successfully.")
        )
