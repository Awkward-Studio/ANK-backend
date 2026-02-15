from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from Departments.mixins import DepartmentAccessMixin
from django.contrib.contenttypes.models import ContentType
from contextlib import nullcontext
import re

import csv
import io
from django.db import transaction
from Events.models.session_registration import SessionRegistration
from Events.models import Event, EventRegistration
from Guest.models import Guest

from Events.models.event_registration_model import ExtraAttendee
from Guest.models import Guest, GuestField
from Guest.serializers import GuestSerializer, GuestFieldSerializer
from CustomField.models import CustomFieldDefinition, CustomFieldValue

# Known CSV columns that map to existing Guest/EventRegistration fields
# Any column NOT in this list will be treated as a custom field
KNOWN_CSV_COLUMNS = {
    "UID",
    "Guest Group",
    "Sub Guest Group",
    "Salutation",
    "First Name",
    "Last Name",
    "Pax",
    "Contact",
    "Email",
    "Address",
    "City",
    "Pincode",
    "Country",
    "unique_strings",
}
from utils.swagger import (
    doc_create,
    doc_list,
    doc_retrieve,
    doc_update,
    doc_destroy,
    document_api_view,
    query_param,
)


@document_api_view(
    {
        "get": doc_list(
            response=GuestFieldSerializer(many=True),
            description="List all guest fields",
            tags=["Guest Fields"],
        ),
        "post": doc_create(
            request=GuestFieldSerializer,
            response=GuestFieldSerializer,
            description="Create a new guest field",
            tags=["Guest Fields"],
        ),
    }
)
class GuestFieldList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = GuestField.objects.all()
            return Response(GuestFieldSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching guest fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = GuestFieldSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except (ValidationError, serializers.ValidationError) as ve:
            if hasattr(ve, 'detail'):
                return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
            elif hasattr(ve, 'message_dict'):
                return Response(ve.message_dict, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating guest field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=GuestFieldSerializer,
            description="Retrieve a guest field by ID",
            tags=["Guest Fields"],
        ),
        "put": doc_update(
            request=GuestFieldSerializer,
            response=GuestFieldSerializer,
            description="Update a guest field by ID",
            tags=["Guest Fields"],
        ),
        "delete": doc_destroy(
            description="Delete a guest field by ID", tags=["Guest Fields"]
        ),
    }
)
class GuestFieldDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(GuestField, pk=pk)
            return Response(GuestFieldSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching guest field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(GuestField, pk=pk)
            ser = GuestFieldSerializer(obj, data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except (ValidationError, serializers.ValidationError) as ve:
            if hasattr(ve, 'detail'):
                return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
            elif hasattr(ve, 'message_dict'):
                return Response(ve.message_dict, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating guest field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(GuestField, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting guest field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


#  Guest CRUD
@document_api_view(
    {
        "get": doc_list(
            response=GuestSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter by guest name"),
                query_param("city", "str", False, "Filter by city"),
                query_param("nationality", "str", False, "Filter by nationality"),
            ],
            description="List all guests",
            tags=["Guests"],
        ),
        "post": doc_create(
            request=GuestSerializer,
            response=GuestSerializer,
            description="Create a new guest",
            tags=["Guests"],
        ),
    }
)
class GuestList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return Guest.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            return Response(GuestSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching guests", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = GuestSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except (ValidationError, serializers.ValidationError) as ve:
            if hasattr(ve, 'detail'):
                return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
            elif hasattr(ve, 'message_dict'):
                return Response(ve.message_dict, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating guest", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=GuestSerializer,
            description="Retrieve a guest by ID",
            tags=["Guests"],
        ),
        "put": doc_update(
            request=GuestSerializer,
            response=GuestSerializer,
            description="Update a guest by ID",
            tags=["Guests"],
        ),
        "delete": doc_destroy(description="Delete a guest by ID", tags=["Guests"]),
    }
)
class GuestDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return Guest.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            # Get context with the object so event_department can be found
            context = self.get_serializer_context()
            # Manually set event_department if not found
            if 'event_department' not in context or context['event_department'] is None:
                context['event_department'] = self.get_event_department(request, obj)
            return Response(GuestSerializer(obj, context=context).data)
        except Exception as e:
            from django.http import Http404
            if isinstance(e, Http404):
                raise
            return Response(
                {"detail": "Error fetching guest", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            # Get context with the object so event_department can be found
            context = self.get_serializer_context()
            # Manually set event_department if not found
            if 'event_department' not in context or context['event_department'] is None:
                context['event_department'] = self.get_event_department(request, obj)
            ser = GuestSerializer(obj, data=request.data, partial=True, context=context)
            ser.is_valid(raise_exception=True)
            ser.save()
            # Refresh context after save
            context = self.get_serializer_context()
            if 'event_department' not in context or context['event_department'] is None:
                context['event_department'] = self.get_event_department(request, obj)
            return Response(GuestSerializer(obj, context=context).data)
        except (ValidationError, serializers.ValidationError) as ve:
            if hasattr(ve, 'detail'):
                return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
            elif hasattr(ve, 'message_dict'):
                return Response(ve.message_dict, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            from django.http import Http404
            if isinstance(e, Http404):
                raise
            return Response(
                {"detail": "Error updating guest", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    def patch(self, request, pk):
        """Support PATCH method for partial updates"""
        return self.put(request, pk)

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            from django.http import Http404
            if isinstance(e, Http404):
                raise
            return Response(
                {"detail": "Error deleting guest", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BulkGuestUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    POST /api/guest-list/{event_id}/upload-guests-csv/
    Accepts a CSV file with guest+registration data.
    Query params or form fields:
      - dry_run: bool (if true, do NOT save, just validate & return stats)
      - create_extra_attendees: bool (default true)
    """

    def post(self, request, event_id):
        try:
            event = Event.objects.get(pk=event_id)
            csv_file = request.FILES["file"]
            if not csv_file.name.endswith(".csv"):
                return Response({"detail": "Please upload a CSV file."}, status=400)

            # Parse booleans from form data or query params
            def parse_bool(val, default=False):
                if val is None:
                    return default
                return str(val).lower() in ("1", "true", "yes", "on")

            dry_run = parse_bool(
                request.data.get("dry_run", request.query_params.get("dry_run")), False
            )
            create_extra_attendees = parse_bool(
                request.data.get(
                    "create_extra_attendees",
                    request.query_params.get("create_extra_attendees"),
                ),
                True,
            )

            data = csv_file.read().decode("utf-8-sig")
            csv_reader = csv.DictReader(io.StringIO(data))
            
            # Get CSV headers and detect unknown columns (potential custom fields)
            csv_headers = csv_reader.fieldnames or []
            unknown_columns = [col for col in csv_headers if col not in KNOWN_CSV_COLUMNS]

            # Counters
            guests_created = 0
            guests_updated = 0
            event_regs_created = 0
            event_regs_updated = 0
            extra_attendees_created = 0
            session_regs_created = 0
            session_regs_skipped = 0
            custom_fields_created = 0
            custom_field_values_created = 0
            errors = []
            warnings = []

            # Prepare all sessions for the event, indexed by unique_string
            sessions_by_unique = {
                s.unique_string: s
                for s in event.sessions.all()
                if hasattr(s, "unique_string")
            }

            # Track UIDs and emails seen in this CSV to detect duplicates within the file
            seen_uids_in_csv = set()
            seen_emails_in_csv = set()
            seen_phones_in_csv = set()
            
            # Get ContentType for EventRegistration (needed for custom fields)
            event_registration_ct = ContentType.objects.get_for_model(EventRegistration)
            
            # Dictionary to store custom field definitions (column_name -> CustomFieldDefinition)
            custom_field_definitions = {}

            context_manager = transaction.atomic if not dry_run else nullcontext

            with context_manager():
                # === CREATE CUSTOM FIELD DEFINITIONS FOR UNKNOWN COLUMNS ===
                if unknown_columns:
                    for column_name in unknown_columns:
                        # Sanitize column name for internal use (lowercase, underscores)
                        sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', column_name.lower()).strip('_')
                        sanitized_name = re.sub(r'_+', '_', sanitized_name)  # Remove multiple underscores
                        
                        if not sanitized_name:
                            warnings.append(f"Column '{column_name}' has invalid name, skipping as custom field")
                            continue
                        
                        if not dry_run:
                            # Get or create the custom field definition for this event
                            field_def, created = CustomFieldDefinition.objects.get_or_create(
                                event=event,
                                content_type=event_registration_ct,
                                name=sanitized_name,
                                defaults={
                                    "label": column_name,  # Keep original column name as label
                                    "field_type": "text",  # Default to text type
                                    "help_text": f"Auto-created from CSV column '{column_name}'",
                                },
                            )
                            custom_field_definitions[column_name] = field_def
                            if created:
                                custom_fields_created += 1
                        else:
                            # Dry run - check if it would be created
                            existing = CustomFieldDefinition.objects.filter(
                                event=event,
                                content_type=event_registration_ct,
                                name=sanitized_name,
                            ).exists()
                            if not existing:
                                custom_fields_created += 1
                            # Store a placeholder for dry run tracking
                            custom_field_definitions[column_name] = sanitized_name
                
                for idx, row in enumerate(csv_reader, start=2):  # 2 for header row
                    try:
                        # Extract and clean data
                        uid = row.get("UID", "").strip()
                        group = row.get("Guest Group", "").strip()
                        subgroup = row.get("Sub Guest Group", "").strip()
                        salutation = row.get("Salutation", "").strip()
                        first_name = row.get("First Name", "").strip()
                        last_name = row.get("Last Name", "").strip()
                        pax = int(row.get("Pax", "1").strip() or "1")
                        contact = row.get("Contact", "").strip()
                        email = row.get("Email", "").strip().lower()  # Normalize email
                        address = row.get("Address", "").strip()
                        city = row.get("City", "").strip()
                        pincode = row.get("Pincode", "").strip()
                        country = row.get("Country", "").strip()

                        # === VALIDATION ===
                        if not uid:
                            raise ValueError("UID is required")
                        if not email:
                            raise ValueError("Email is required")
                        if not first_name:
                            raise ValueError("First Name is required")

                        # Check for duplicates within the CSV file itself
                        if uid in seen_uids_in_csv:
                            raise ValueError(f"Duplicate UID '{uid}' found in CSV at row {idx}")
                        if email in seen_emails_in_csv:
                            raise ValueError(f"Duplicate email '{email}' found in CSV at row {idx}")

                        seen_uids_in_csv.add(uid)
                        seen_emails_in_csv.add(email)
                        if contact:
                            if contact in seen_phones_in_csv:
                                warnings.append(f"Row {idx}: Duplicate phone '{contact}' in CSV (not blocking)")
                            seen_phones_in_csv.add(contact)

                        unique_strings_raw = row.get("unique_strings") or ""
                        unique_strings = [
                            s.strip()
                            for s in unique_strings_raw.split(",")
                            if s.strip()
                        ]

                        # Full Name
                        full_name = f"{first_name} {last_name}".strip()

                        # Validate field lengths
                        if len(group) > 20:
                            raise ValueError(
                                f"Guest Group '{group}' exceeds maximum length of 20 characters (current: {len(group)})"
                            )
                        if len(subgroup) > 20:
                            raise ValueError(
                                f"Sub Guest Group '{subgroup}' exceeds maximum length of 20 characters (current: {len(subgroup)})"
                            )
                        if len(salutation) > 20:
                            raise ValueError(
                                f"Salutation/Title '{salutation}' exceeds maximum length of 20 characters (current: {len(salutation)})"
                            )
                        if len(full_name) > 200:
                            raise ValueError(
                                f"Name '{full_name}' exceeds maximum length of 200 characters (current: {len(full_name)})"
                            )

                        # === DUPLICATE DETECTION IN DATABASE ===
                        # Check if UID already exists in this event (UID must be unique per event)
                        uid_conflict = EventRegistration.objects.filter(event=event, uid=uid).first()
                        if uid_conflict:
                            # UID exists in this event - check if it's for a different guest
                            if uid_conflict.guest.email != email:
                                raise ValueError(
                                    f"UID '{uid}' already exists in this event for a different guest: {uid_conflict.guest.email}"
                                )

                        # Check for phone number conflicts (warning only, as phone is not unique in model)
                        if contact:
                            phone_conflicts = Guest.objects.filter(phone=contact).exclude(email=email)
                            if phone_conflicts.exists():
                                conflict_emails = ", ".join([g.email for g in phone_conflicts[:3]])
                                warnings.append(
                                    f"Row {idx}: Phone '{contact}' already used by: {conflict_emails}"
                                )

                        if not dry_run:
                            # === 1) GUEST: Get or Create ===
                            guest, guest_created = Guest.objects.get_or_create(
                                email=email,
                                defaults={
                                    "name": full_name,
                                    "phone": contact,
                                    "address": address,
                                    "city": city,
                                    "nationality": country,
                                },
                            )

                            if guest_created:
                                guests_created += 1
                            else:
                                # Update guest info if it already exists
                                guest.name = full_name
                                guest.phone = contact
                                guest.address = address
                                guest.city = city
                                guest.nationality = country
                                guest.save()
                                guests_updated += 1

                            # === 2) EVENT REGISTRATION: Get or Create ===
                            # Check by (guest, event) unique constraint
                            existing_reg = EventRegistration.objects.filter(
                                guest=guest, event=event
                            ).first()

                            reg_created = False
                            if existing_reg:
                                # Update existing registration (no duplicate)
                                existing_reg.uid = uid
                                existing_reg.guest_group = group
                                existing_reg.sub_guest_group = subgroup
                                existing_reg.title = salutation
                                existing_reg.name_on_message = full_name
                                existing_reg.estimated_pax = pax
                                existing_reg.save()
                                reg = existing_reg
                                event_regs_updated += 1
                            else:
                                # Create new registration
                                reg = EventRegistration.objects.create(
                                    uid=uid,
                                    guest=guest,
                                    event=event,
                                    guest_group=group,
                                    sub_guest_group=subgroup,
                                    title=salutation,
                                    name_on_message=full_name,
                                    estimated_pax=pax,
                                )
                                event_regs_created += 1
                                reg_created = True

                            # === 3) CUSTOM FIELD VALUES: Store unknown column data ===
                            for column_name, field_def in custom_field_definitions.items():
                                value = row.get(column_name, "").strip()
                                if value:  # Only create if there's a value
                                    # Use update_or_create to handle re-uploads
                                    _, cfv_created = CustomFieldValue.objects.update_or_create(
                                        definition=field_def,
                                        content_type=event_registration_ct,
                                        object_id=str(reg.id),
                                        defaults={"value": value},
                                    )
                                    if cfv_created:
                                        custom_field_values_created += 1

                            # === 4) EXTRA ATTENDEES: Handled automatically by signal ===
                            # The sync_extra_guests signal in Events/signals.py automatically
                            # creates/deletes extra attendees based on estimated_pax.
                            # Signal logic: required_extras = max(0, estimated_pax - 1)
                            # Signal fires on post_save of EventRegistration.
                            #
                            # We just need to track what WOULD be created for reporting.
                            if create_extra_attendees:
                                needed_extra = max(pax - 1, 0)
                                if reg_created:
                                    # New registration - signal will create all extras
                                    extra_attendees_created += needed_extra
                                else:
                                    # Existing registration - signal will adjust count
                                    # Check current count to see what changed
                                    existing_extra_count = reg.extra_attendees.count()
                                    # After signal runs, count will match needed_extra
                                    # Track the delta for reporting
                                    if needed_extra > existing_extra_count:
                                        extra_attendees_created += (needed_extra - existing_extra_count)

                            # === 5) SESSION REGISTRATIONS: Create only if not exists ===
                            for unique_str in unique_strings:
                                session = sessions_by_unique.get(unique_str)
                                if session:
                                    # Use get_or_create to leverage unique_together constraint
                                    session_reg, created = SessionRegistration.objects.get_or_create(
                                        guest=guest,
                                        session=session,
                                    )
                                    if created:
                                        session_regs_created += 1
                                    else:
                                        session_regs_skipped += 1
                                else:
                                    warnings.append(
                                        f"Row {idx}: Session '{unique_str}' not found for this event"
                                    )

                        else:
                            # === DRY RUN MODE ===
                            is_new_guest = not Guest.objects.filter(email=email).exists()
                            if is_new_guest:
                                guests_created += 1
                            else:
                                guests_updated += 1

                            # Check if registration exists
                            existing_reg = None
                            guest = Guest.objects.filter(email=email).first()
                            if guest:
                                existing_reg = EventRegistration.objects.filter(
                                    guest=guest, event=event
                                ).first()

                            if not existing_reg:
                                event_regs_created += 1
                                # Count extra attendees only for new registrations
                                if create_extra_attendees:
                                    extra_attendees_created += max(pax - 1, 0)
                            else:
                                event_regs_updated += 1

                            # Count custom field values that would be created
                            for column_name in custom_field_definitions.keys():
                                value = row.get(column_name, "").strip()
                                if value:
                                    # In dry run, we can't check if it exists without the reg
                                    # So we count all values with data as potential creates
                                    custom_field_values_created += 1

                            # Session registrations: count only if not already registered
                            for unique_str in unique_strings:
                                session = sessions_by_unique.get(unique_str)
                                if session:
                                    already_registered = False
                                    if guest:
                                        already_registered = SessionRegistration.objects.filter(
                                            guest=guest, session=session
                                        ).exists()

                                    if not already_registered:
                                        session_regs_created += 1
                                    else:
                                        session_regs_skipped += 1
                                else:
                                    warnings.append(
                                        f"Row {idx}: Session '{unique_str}' not found for this event"
                                    )

                    except Exception as row_e:
                        # Create detailed error message with row context
                        error_context = {
                            "row": idx,
                            "uid": row.get("UID", "N/A"),
                            "name": f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip(),
                            "email": row.get("Email", "N/A"),
                            "error": str(row_e),
                        }
                        detailed_error = (
                            f"Row {idx} [UID: {error_context['uid']}, "
                            f"Name: {error_context['name']}, "
                            f"Email: {error_context['email']}]: {error_context['error']}"
                        )
                        errors.append(detailed_error)

                if dry_run:
                    raise RuntimeError("__dry_run_complete__")

            # Build custom fields summary for message
            custom_fields_msg = ""
            if custom_fields_created > 0 or custom_field_values_created > 0:
                custom_fields_msg = f", {custom_fields_created} custom fields, {custom_field_values_created} custom values"
            
            return Response(
                {
                    "guests_created": guests_created,
                    "guests_updated": guests_updated,
                    "event_registrations_created": event_regs_created,
                    "event_registrations_updated": event_regs_updated,
                    "extra_attendees_created": extra_attendees_created,
                    "session_registrations_created": session_regs_created,
                    "session_registrations_skipped": session_regs_skipped,
                    "custom_fields_created": custom_fields_created,
                    "custom_field_values_created": custom_field_values_created,
                    "unknown_columns_detected": unknown_columns,
                    "errors": errors,
                    "warnings": warnings,
                    "dry_run": dry_run,
                    "create_extra_attendees": create_extra_attendees,
                    "message": (
                        f"{'[DRY RUN] Would create' if dry_run else 'Successfully imported'}: "
                        f"{guests_created} new guests, {guests_updated} updated guests, "
                        f"{event_regs_created} new registrations, {event_regs_updated} updated registrations, "
                        f"{extra_attendees_created} extra attendees, "
                        f"{session_regs_created} session registrations (skipped {session_regs_skipped} duplicates)"
                        f"{custom_fields_msg}"
                    ),
                },
                status=200 if dry_run else 201,
            )

        except RuntimeError as dry_run_marker:
            if str(dry_run_marker) == "__dry_run_complete__":
                # Build custom fields summary for message
                custom_fields_msg = ""
                if custom_fields_created > 0 or custom_field_values_created > 0:
                    custom_fields_msg = f", {custom_fields_created} custom fields, {custom_field_values_created} custom values"
                
                return Response(
                    {
                        "guests_created": guests_created,
                        "guests_updated": guests_updated,
                        "event_registrations_created": event_regs_created,
                        "event_registrations_updated": event_regs_updated,
                        "extra_attendees_created": extra_attendees_created,
                        "session_registrations_created": session_regs_created,
                        "session_registrations_skipped": session_regs_skipped,
                        "custom_fields_created": custom_fields_created,
                        "custom_field_values_created": custom_field_values_created,
                        "unknown_columns_detected": unknown_columns,
                        "errors": errors,
                        "warnings": warnings,
                        "dry_run": True,
                        "message": (
                            f"[DRY RUN] Would create: "
                            f"{guests_created} new guests, {guests_updated} updated guests, "
                            f"{event_regs_created} new registrations, {event_regs_updated} updated registrations, "
                            f"{extra_attendees_created} extra attendees, "
                            f"{session_regs_created} session registrations (skipped {session_regs_skipped} duplicates)"
                            f"{custom_fields_msg}"
                        ),
                    },
                    status=200,
                )
            raise
        except Exception as e:
            return Response({"detail": "Import failed", "error": str(e)}, status=500)


# class BulkGuestUploadAPIView(APIView):
#     """
#     POST /api/guest-list/{event_id}/upload-guests-csv/
#     Accepts a CSV file with guest+registration data.
#     Query params or form fields:
#       - dry_run: bool (if true, do NOT save, just validate & return stats)
#       - create_extra_attendees: bool (default true)
#     """

#     def post(self, request, event_id):
#         try:
#             event = Event.objects.get(pk=event_id)
#             csv_file = request.FILES["file"]
#             if not csv_file.name.endswith(".csv"):
#                 return Response({"detail": "Please upload a CSV file."}, status=400)

#             # Parse booleans from form data or query params
#             def parse_bool(val, default=False):
#                 if val is None:
#                     return default
#                 return str(val).lower() in ("1", "true", "yes", "on")

#             dry_run = parse_bool(
#                 request.data.get("dry_run", request.query_params.get("dry_run")), False
#             )
#             create_extra_attendees = parse_bool(
#                 request.data.get(
#                     "create_extra_attendees",
#                     request.query_params.get("create_extra_attendees"),
#                 ),
#                 True,
#             )

#             data = csv_file.read().decode("utf-8-sig")  # handle BOM if present
#             csv_reader = csv.DictReader(io.StringIO(data))
#             guests_created = 0
#             event_regs_created = 0
#             extra_attendees_created = 0
#             errors = []

#             # Use atomic transaction ONLY if actually saving
#             context_manager = transaction.atomic if not dry_run else nullcontext

#             with context_manager():
#                 for idx, row in enumerate(csv_reader, start=2):  # 2 for header row
#                     try:
#                         group = row.get("Guest Group", "").strip()
#                         subgroup = row.get("Sub Guest Group", "").strip()
#                         salutation = row.get("Salutation", "").strip()
#                         first_name = row.get("First Name", "").strip()
#                         last_name = row.get("Last Name", "").strip()
#                         pax = int(row.get("Pax", "1").strip() or "1")
#                         contact = row.get("Contact", "").strip()
#                         email = row.get("Email", "").strip()
#                         address = row.get("Address", "").strip()
#                         city = row.get("City", "").strip()
#                         pincode = row.get("Pincode", "").strip()
#                         country = row.get("Country", "").strip()

#                         # Full Name
#                         full_name = f"{first_name} {last_name}".strip()

#                         # Will we create a new Guest?
#                         if not Guest.objects.filter(email=email).exists():
#                             guests_created += 1

#                         if not dry_run:
#                             guest, _ = Guest.objects.get_or_create(
#                                 email=email,
#                                 defaults={
#                                     "name": full_name,
#                                     "phone": contact,
#                                     "address": address,
#                                     "city": city,
#                                     "nationality": country,
#                                 },
#                             )
#                             reg = EventRegistration.objects.create(
#                                 guest=guest,
#                                 event=event,
#                                 guest_group=group,
#                                 sub_guest_group=subgroup,
#                                 title=salutation,
#                                 name_on_message=full_name,
#                                 estimated_pax=pax,
#                             )
#                             event_regs_created += 1

#                             if create_extra_attendees:
#                                 for i in range(pax - 1):
#                                     ea_name = f"Guest of {full_name}_{i+1}"
#                                     ExtraAttendee.objects.create(
#                                         registration=reg,
#                                         name=ea_name,
#                                     )
#                                     extra_attendees_created += 1
#                         else:
#                             event_regs_created += 1
#                             if create_extra_attendees:
#                                 extra_attendees_created += max(pax - 1, 0)

#                     except Exception as row_e:
#                         errors.append(f"Row {idx}: {row_e}")

#                 # If dry_run, forcibly rollback (raise exception inside atomic to abort)
#                 if dry_run:
#                     raise RuntimeError("__dry_run_complete__")

#             return Response(
#                 {
#                     "created_guests": guests_created,
#                     "created_event_registrations": event_regs_created,
#                     "created_extra_attendees": extra_attendees_created,
#                     "errors": errors,
#                     "dry_run": dry_run,
#                     "create_extra_attendees": create_extra_attendees,
#                     "message": (
#                         "Dry run successful. Would create " if dry_run else "Imported "
#                     )
#                     + f"{event_regs_created} registrations with {extra_attendees_created} extra attendees.",
#                 },
#                 status=200 if dry_run else 201,
#             )

#         except RuntimeError as dry_run_marker:
#             if str(dry_run_marker) == "__dry_run_complete__":
#                 # dry_run: suppress normal atomic error
#                 return Response(
#                     {
#                         "created_guests": guests_created,
#                         "created_event_registrations": event_regs_created,
#                         "created_extra_attendees": extra_attendees_created,
#                         "errors": errors,
#                         "dry_run": True,
#                         "message": (
#                             f"Dry run successful. Would create {event_regs_created} registrations with {extra_attendees_created} extra attendees."
#                         ),
#                     },
#                     status=200,
#                 )
#             raise
#         except Exception as e:
#             return Response({"detail": "Import failed", "error": str(e)}, status=500)
