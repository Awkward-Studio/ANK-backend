from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from Events.models.event_model import Event, EventField
from Events.models.staff_event_field_permissions import UserEventFieldPermission
from Events.views.staff_event_fields_permissions_views import (
    UserEventAllAllowedFieldsAPIView,
    UserEventEventFieldPermsAPIView,
)
from Staff.serializers import UserSerializer
from Staff.views import UserDetail, UserList
from Departments.models import Department
from Departments.permissions import PermissionChecker

User = get_user_model()


class RoleAuthorizationTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.super_admin = User.objects.create_user(
            email="super@example.com",
            password="password",
            name="Super Admin",
            role="super_admin",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="password",
            name="Admin",
            role="admin",
        )
        self.dept_head = User.objects.create_user(
            email="head@example.com",
            password="password",
            name="Department Head",
            role="department_head",
        )
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="password",
            name="Staff",
            role="staff",
        )
        self.other_staff = User.objects.create_user(
            email="other@example.com",
            password="password",
            name="Other Staff",
            role="staff",
        )
        self.event = Event.objects.create(
            name="Role Test Event",
            start_date="2026-06-01",
            end_date="2026-06-02",
        )
        self.event_field, _ = EventField.objects.get_or_create(
            name="venue",
            defaults={"label": "Venue"},
        )
        self.department = Department.objects.create(
            name="Hospitality",
            slug="hospitality",
        )

    def test_staff_cannot_list_users(self):
        request = self.factory.get("/api/users/")
        force_authenticate(request, user=self.staff)

        response = UserList.as_view()(request)

        self.assertEqual(response.status_code, 403)

    def test_department_head_can_list_users_for_assignment_workflows(self):
        request = self.factory.get("/api/users/")
        force_authenticate(request, user=self.dept_head)

        response = UserList.as_view()(request)

        self.assertEqual(response.status_code, 200)

    def test_staff_can_view_self_but_not_other_user(self):
        view = UserDetail.as_view()

        own_request = self.factory.get(f"/api/users/{self.staff.id}/")
        force_authenticate(own_request, user=self.staff)
        own_response = view(own_request, pk=self.staff.id)

        other_request = self.factory.get(f"/api/users/{self.other_staff.id}/")
        force_authenticate(other_request, user=self.staff)
        other_response = view(other_request, pk=self.other_staff.id)

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 403)

    def test_admin_can_create_user_but_staff_cannot(self):
        payload = {
            "email": "created@example.com",
            "password": "password123",
            "name": "Created User",
            "role": "staff",
        }

        admin_request = self.factory.post("/api/users/", payload, format="json")
        force_authenticate(admin_request, user=self.admin)
        admin_response = UserList.as_view()(admin_request)

        staff_request = self.factory.post(
            "/api/users/",
            {**payload, "email": "blocked@example.com"},
            format="json",
        )
        force_authenticate(staff_request, user=self.staff)
        staff_response = UserList.as_view()(staff_request)

        self.assertEqual(admin_response.status_code, 201)
        self.assertEqual(staff_response.status_code, 403)

    def test_department_head_requires_department_on_create(self):
        serializer = UserSerializer(data={
            "email": "new-head@example.com",
            "password": "password123",
            "name": "New Department Head",
            "role": "department_head",
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("department", serializer.errors)

    def test_department_head_accepts_department_on_create(self):
        serializer = UserSerializer(data={
            "email": "valid-head@example.com",
            "password": "password123",
            "name": "Valid Department Head",
            "role": "department_head",
            "department": str(self.department.id),
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_staff_cannot_be_promoted_to_department_head_without_department(self):
        serializer = UserSerializer(
            self.staff,
            data={"role": "department_head", "department": None},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("department", serializer.errors)

    def test_department_head_allowed_fields_returns_full_model_access(self):
        """A department_head must get full model_access from the
        allowed-fields endpoint even without DepartmentModelAccess rows,
        so the frontend can render every event tab."""
        head = User.objects.create_user(
            email="dept-head-perms@example.com",
            password="password",
            name="Dept Head Perms",
            role="department_head",
            department=self.department,
        )

        request = self.factory.get(
            f"/api/events/{self.event.id}/users/{head.id}/allowed-fields/"
        )
        force_authenticate(request, user=head)
        response = UserEventAllAllowedFieldsAPIView.as_view()(
            request, event_pk=self.event.id, user_pk=head.id
        )

        self.assertEqual(response.status_code, 200)
        model_access = response.data.get("model_access", {})
        self.assertTrue(model_access, "model_access should not be empty for dept head")
        for model_name in [
            "event",
            "guest",
            "session",
            "traveldetail",
            "accommodation",
            "eventregistration",
        ]:
            access = model_access.get(model_name, {})
            self.assertTrue(
                access.get("can_read"),
                f"department_head should be able to read {model_name}",
            )
            self.assertTrue(
                access.get("can_write"),
                f"department_head should be able to write {model_name}",
            )

    def test_department_head_permission_checker_returns_all_fields(self):
        """PermissionChecker.get_user_allowed_fields must treat
        department_head as full-field access without per-field config."""
        head = User.objects.create_user(
            email="dept-head-checker@example.com",
            password="password",
            name="Dept Head Checker",
            role="department_head",
            department=self.department,
        )

        from Events.models.event_model import Event as EventModel

        allowed = PermissionChecker.get_user_allowed_fields(
            head, self.event, EventModel
        )
        self.assertIsNone(
            allowed,
            "Department heads should not be restricted to a subset of fields",
        )

    def test_department_head_sees_all_events(self):
        head = User.objects.create_user(
            email="dept-head-events@example.com",
            password="password",
            name="Dept Head Events",
            role="department_head",
            department=self.department,
        )

        accessible = PermissionChecker.get_user_accessible_events(head)
        self.assertTrue(accessible.filter(id=self.event.id).exists())

    def test_staff_can_read_only_their_own_legacy_allowed_fields(self):
        view = UserEventAllAllowedFieldsAPIView.as_view()

        own_request = self.factory.get(
            f"/api/events/{self.event.id}/users/{self.staff.id}/allowed-fields/"
        )
        force_authenticate(own_request, user=self.staff)
        own_response = view(own_request, event_pk=self.event.id, user_pk=self.staff.id)

        other_request = self.factory.get(
            f"/api/events/{self.event.id}/users/{self.other_staff.id}/allowed-fields/"
        )
        force_authenticate(other_request, user=self.staff)
        other_response = view(
            other_request,
            event_pk=self.event.id,
            user_pk=self.other_staff.id,
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 403)

    def test_legacy_event_field_permissions_require_manager_role_to_mutate(self):
        view = UserEventEventFieldPermsAPIView.as_view()
        payload = {"eventfield_ids": [str(self.event_field.id)]}

        staff_request = self.factory.put(
            f"/api/events/{self.event.id}/users/{self.staff.id}/event-fields/",
            payload,
            format="json",
        )
        force_authenticate(staff_request, user=self.staff)
        staff_response = view(staff_request, event_pk=self.event.id, user_pk=self.staff.id)

        admin_request = self.factory.put(
            f"/api/events/{self.event.id}/users/{self.staff.id}/event-fields/",
            payload,
            format="json",
        )
        force_authenticate(admin_request, user=self.admin)
        admin_response = view(admin_request, event_pk=self.event.id, user_pk=self.staff.id)

        self.assertEqual(staff_response.status_code, 403)
        self.assertEqual(admin_response.status_code, 200)
        self.assertTrue(
            UserEventFieldPermission.objects.filter(
                user=self.staff,
                event=self.event,
                event_field=self.event_field,
            ).exists()
        )
