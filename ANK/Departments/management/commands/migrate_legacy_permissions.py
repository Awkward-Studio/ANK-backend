from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from Events.models.staff_event_field_permissions import (
    UserEventFieldPermission,
    UserEventGuestFieldPermission,
    UserEventSessionFieldPermission,
    UserEventTravelDetailFieldPermission,
    UserEventEventRegistrationFieldPermission,
    UserEventAccommodationFieldPermission,
)
from Departments.models import (
    EventDepartment,
    EventDepartmentStaffAssignment,
    ModelPermission,
    Department,
    DepartmentModelAccess,
)
from Events.models.event_model import Event, EventField
from Guest.models import Guest, GuestField
from Events.models.session_model import Session, SessionField
from Logistics.models.travel_details_models import TravelDetail, TravelDetailField
from Events.models.event_registration_model import EventRegistration, EventRegistrationField
from Logistics.models.accomodation_models import Accommodation, AccommodationField

class Command(BaseCommand):
    help = 'Migrate legacy field permissions to the new consolidated ModelPermission model'

    def handle(self, *args, **options):
        self.stdout.write("Starting migration of legacy permissions...")
        
        legacy_models = [
            (UserEventFieldPermission, Event, 'event_field'),
            (UserEventGuestFieldPermission, Guest, 'guest_field'),
            (UserEventSessionFieldPermission, Session, 'session_field'),
            (UserEventTravelDetailFieldPermission, TravelDetail, 'traveldetail_field'),
            (UserEventEventRegistrationFieldPermission, EventRegistration, 'eventregistration_field'),
            (UserEventAccommodationFieldPermission, Accommodation, 'accommodation_field'),
        ]

        # Ensure a default department exists for migration if none found
        default_dept, _ = Department.objects.get_or_create(
            name="Migration Default",
            slug="migration-default"
        )

        total_migrated = 0
        total_errors = 0

        with transaction.atomic():
            for legacy_model, model_class, field_attr in legacy_models:
                self.stdout.write(f"Processing {legacy_model.__name__}...")
                content_type = ContentType.objects.get_for_model(model_class)
                
                # Also ensure DepartmentModelAccess exists for this department and model
                DepartmentModelAccess.objects.get_or_create(
                    department=default_dept,
                    content_type=content_type,
                    defaults={'can_read': True, 'can_write': True}
                )

                perms = legacy_model.objects.all()
                for perm in perms:
                    try:
                        # 1. Find EventDepartment for this user and event
                        # Legacy models have 'user' and 'event' fields
                        event_dept = EventDepartment.objects.filter(
                            event=perm.event,
                            staff_assignments__user=perm.user
                        ).first()

                        if not event_dept:
                            # Create an assignment to the default department if none exists
                            event_dept, _ = EventDepartment.objects.get_or_create(
                                event=perm.event,
                                department=default_dept
                            )
                            EventDepartmentStaffAssignment.objects.get_or_create(
                                event_department=event_dept,
                                user=perm.user,
                                defaults={'role': 'editor'}
                            )

                        # 2. Get field name from the linked field object
                        field_obj = getattr(perm, field_attr)
                        field_name = field_obj.name

                        # 3. Create new ModelPermission
                        ModelPermission.objects.get_or_create(
                            user=perm.user,
                            event_department=event_dept,
                            content_type=content_type,
                            field_name=field_name,
                            defaults={'permission_type': 'read_write'}
                        )
                        total_migrated += 1
                    except Exception as e:
                        self.stderr.write(f"Error migrating permission {perm.id}: {str(e)}")
                        total_errors += 1

        self.stdout.write(self.style.SUCCESS(
            f"Migration complete. Migrated: {total_migrated}, Errors: {total_errors}"
        ))
