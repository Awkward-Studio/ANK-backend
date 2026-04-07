from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from Events.models.event_model import Event
from Departments.models import Department, EventDepartment, EventDepartmentStaffAssignment, BudgetFieldPermission
from Departments.views import UserEventScopedDepartmentFieldAccessAPIView
from Departments.serializers import BUDGET_FIELD_KEYS

User = get_user_model()

class BudgetVisibilityTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        
        # Create an event
        self.event = Event.objects.create(
            name="Grand Wedding",
            start_date="2026-06-01",
            end_date="2026-06-05"
        )
        
        # Create departments
        self.dept1 = Department.objects.create(name="Hospitality", slug="hospitality")
        self.dept2 = Department.objects.create(name="Logistics", slug="logistics")
        
        # Create an EventDepartment
        self.ed1 = EventDepartment.objects.create(
            event=self.event,
            department=self.dept1
        )
        self.ed2 = EventDepartment.objects.create(
            event=self.event,
            department=self.dept2
        )
        
        # Create users
        self.super_admin = User.objects.create_user(
            email="super@example.com", password="password", name="Super Admin", role="super_admin"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="password", name="Admin", role="admin"
        )
        self.staff = User.objects.create_user(
            email="staff@example.com", password="password", name="Staff", role="staff"
        )
        self.dept_head = User.objects.create_user(
            email="head@example.com", password="password", name="Dept Head", role="department_head",
            department=self.dept1
        )

    def test_super_admin_visibility(self):
        view = UserEventScopedDepartmentFieldAccessAPIView.as_view()
        request = self.factory.get(f'/api/users/{self.super_admin.id}/events/{self.event.id}/departments/field-access/')
        force_authenticate(request, user=self.super_admin)
        
        response = view(request, user_pk=self.super_admin.id, event_pk=self.event.id)
        self.assertEqual(response.status_code, 200)
        
        # Super admin should see ALL departments (2) with ALL field keys
        self.assertEqual(len(response.data), 2)
        for row in response.data:
            self.assertEqual(len(row['field_keys']), len(BUDGET_FIELD_KEYS))

    def test_admin_visibility(self):
        view = UserEventScopedDepartmentFieldAccessAPIView.as_view()
        request = self.factory.get(f'/api/users/{self.admin.id}/events/{self.event.id}/departments/field-access/')
        force_authenticate(request, user=self.admin)
        
        response = view(request, user_pk=self.admin.id, event_pk=self.event.id)
        self.assertEqual(response.status_code, 200)
        
        # Admin should also see ALL departments
        self.assertEqual(len(response.data), 2)

    def test_dept_head_visibility(self):
        view = UserEventScopedDepartmentFieldAccessAPIView.as_view()
        request = self.factory.get(f'/api/users/{self.dept_head.id}/events/{self.event.id}/departments/field-access/')
        force_authenticate(request, user=self.dept_head)
        
        response = view(request, user_pk=self.dept_head.id, event_pk=self.event.id)
        self.assertEqual(response.status_code, 200)
        
        # Dept head should only see their own department (Hospitality)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['event_department']['department']['name'], "Hospitality")
        self.assertEqual(len(response.data[0]['field_keys']), len(BUDGET_FIELD_KEYS))

    def test_staff_visibility_with_assignments(self):
        # Assign staff to ed1 with specific permissions
        EventDepartmentStaffAssignment.objects.create(
            event_department=self.ed1,
            user=self.staff,
            role="coordinator"
        )
        BudgetFieldPermission.objects.create(
            user=self.staff,
            event_department=self.ed1,
            field_key="unit_rate"
        )
        
        view = UserEventScopedDepartmentFieldAccessAPIView.as_view()
        request = self.factory.get(f'/api/users/{self.staff.id}/events/{self.event.id}/departments/field-access/')
        force_authenticate(request, user=self.staff)
        
        response = view(request, user_pk=self.staff.id, event_pk=self.event.id)
        self.assertEqual(response.status_code, 200)
        
        # Staff should only see the assigned department with the specific field key
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['event_department']['id'], str(self.ed1.id))
        self.assertEqual(response.data[0]['field_keys'], ["unit_rate"])
