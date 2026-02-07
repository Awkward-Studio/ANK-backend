from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction
from django.db import connection


class Command(BaseCommand):
    help = "WIPE ALL DATA - Fast direct database deletion"

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        
        if not options['noinput']:
            self.stdout.write(self.style.ERROR('\n' + '=' * 60))
            self.stdout.write(self.style.ERROR('WARNING: This will DELETE ALL DATA!'))
            self.stdout.write(self.style.ERROR('=' * 60 + '\n'))
            confirm = input('Type "WIPE ALL" to continue: ')
            if confirm != "WIPE ALL":
                self.stdout.write('Cancelled.')
                return

        with transaction.atomic():
            # Get all models
            all_models = apps.get_models()
            
            # Exclude Django system models
            excluded_apps = {'admin', 'auth', 'contenttypes', 'sessions', 'authtoken'}
            excluded_models = set()
            
            project_models = []
            for model in all_models:
                if model._meta.app_label in excluded_apps:
                    continue
                if model._meta.abstract or model._meta.proxy:
                    continue
                project_models.append(model)
            
            self.stdout.write(f'\nDeleting from {len(project_models)} models...\n')
            
            total_deleted = 0
            for model in project_models:
                try:
                    count = model.objects.count()
                    if count > 0:
                        model.objects.all().delete()
                        total_deleted += count
                        self.stdout.write(self.style.SUCCESS(f'✓ {model._meta.label}: {count}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'✗ {model._meta.label}: {str(e)}'))
            
            # Delete non-superuser users
            non_superusers = User.objects.filter(is_superuser=False)
            user_count = non_superusers.count()
            if user_count > 0:
                non_superusers.delete()
                total_deleted += user_count
                self.stdout.write(self.style.SUCCESS(f'✓ {User._meta.label}: {user_count}'))
            
            self.stdout.write(f'\n✅ Deleted {total_deleted} total records')
