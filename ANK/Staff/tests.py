from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from Events.models.event_model import Event, EventField
from Events.models.staff_event_field_permissions import UserEventFieldPermission
from Events.views.staff_event_fields_permissions_views import (
    UserEventAllAllowedFieldsAPIView,
    UserEventEventFieldPermsAPIView,
)
from Staff.views import UserDetail, UserList

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
