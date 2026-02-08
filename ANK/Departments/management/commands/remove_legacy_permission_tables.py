from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Remove legacy permission tables from the database'

    def handle(self, *args, **options):
        legacy_tables = [
            'Events_usereventfieldpermission',
            'Events_usereventguestfieldpermission',
            'Events_usereventsessionfieldpermission',
            'Events_usereventtraveldetailfieldpermission',
            'Events_usereventeventregistrationfieldpermission',
            'Events_usereventaccommodationfieldpermission',
        ]

        with connection.cursor() as cursor:
            for table in legacy_tables:
                try:
                    self.stdout.write(f"Dropping table {table}...")
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    self.stdout.write(self.style.SUCCESS(f"Successfully dropped {table}"))
                except Exception as e:
                    self.stderr.write(f"Error dropping table {table}: {str(e)}")

        self.stdout.write(self.style.SUCCESS("Legacy table removal complete."))
