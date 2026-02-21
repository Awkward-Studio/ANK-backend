from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid
from Events.models.event_model import Event
from Departments.models import Department, EventDepartment
from .models import (
    Freelancer,
    ManpowerRequirement,
    FreelancerAllocation,
    EventCostSheet,
    MoU,
    PostEventAdjustment,
    FreelancerRating
)

User = get_user_model()

class ManpowerTestCase(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(email="test@example.com", password="password", name="Test User", role="admin")
        
        # Create an event
        self.event = Event.objects.create(
            name="Test Wedding",
            start_date="2026-06-01",
            end_date="2026-06-05"
        )
        
        # Create a department
        self.department = Department.objects.create(name="Hospitality", slug="hospitality")
        
        # Create an EventDepartment
        self.event_department = EventDepartment.objects.create(
            event=self.event,
            department=self.department
        )
        
        # Create a freelancer
        self.freelancer = Freelancer.objects.create(
            name="John Doe",
            skill_category="Coordinator",
            city="Mumbai",
            email="john@example.com",
            base_daily_rate=Decimal("5000.00"),
            standard_allowance=Decimal("500.00")
        )

    def test_manpower_requirement_creation(self):
        requirement = ManpowerRequirement.objects.create(
            event_department=self.event_department,
            skill_category="Coordinator",
            quantity_required=2,
            estimated_days=Decimal("3.0"),
            max_unit_rate=Decimal("6000.00")
        )
        self.assertEqual(requirement.status, "pending")
        self.assertEqual(str(requirement), "2x Coordinator for " + str(self.event_department))

    def test_freelancer_allocation_and_cost_sheet(self):
        # Test Allocation
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="soft_blocked",
            assigned_by=self.user
        )
        self.assertEqual(allocation.status, "soft_blocked")
        
        # Test Cost Sheet
        cost_sheet = EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4500.00"),
            days_planned=Decimal("4.0"),
            daily_allowance=Decimal("400.00"),
            travel_costs=Decimal("1000.00")
        )
        # (4500 * 4) + (400 * 4) + 1000 = 18000 + 1600 + 1000 = 20600
        self.assertEqual(cost_sheet.total_estimated_cost, Decimal("20600.00"))

    def test_allocation_overlap_validation(self):
        # First confirmed allocation
        FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user
        )
        
        # Create another event with overlapping dates
        overlapping_event = Event.objects.create(
            name="Overlapping Wedding",
            start_date="2026-06-02",
            end_date="2026-06-04"
        )
        overlapping_event_department = EventDepartment.objects.create(
            event=overlapping_event,
            department=self.department
        )
        
        # Second allocation for overlapping event should fail when confirming
        with self.assertRaises(Exception): # Django ValidationError
            FreelancerAllocation.objects.create(
                freelancer=self.freelancer,
                event_department=overlapping_event_department,
                status="confirmed",
                assigned_by=self.user
            )

    def test_post_event_adjustment(self):
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user
        )
        cost_sheet = EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("2.0"),
            daily_allowance=Decimal("500.00"),
            travel_costs=Decimal("1000.00")
        )
        # Estimated: (5000*2) + (500*2) + 1000 = 12000
        
        # Adjustment
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            actual_days_worked=Decimal("3.0"),
            extra_allowances=Decimal("200.00")
        )
        # Revised: (5000*3) + (500*3) + 1000 + 200 = 15000 + 1500 + 1000 + 200 = 17700
        self.assertEqual(adjustment.revised_total, Decimal("17700.00"))

    def test_rating_computation(self):
        # Initial rating is 0
        self.assertEqual(self.freelancer.average_rating, Decimal("0.00"))
        
        # Add a rating
        FreelancerRating.objects.create(
            freelancer=self.freelancer,
            event=self.event,
            score=4,
            rated_by=self.user
        )
        self.freelancer.refresh_from_db()
        self.assertEqual(self.freelancer.average_rating, Decimal("4.00"))
        
        # Add another rating for a different event
        another_event = Event.objects.create(name="Another Event")
        FreelancerRating.objects.create(
            freelancer=self.freelancer,
            event=another_event,
            score=5,
            rated_by=self.user
        )
        self.freelancer.refresh_from_db()
        # Average of 4 and 5 is 4.5
        self.assertEqual(self.freelancer.average_rating, Decimal("4.50"))

    def test_mou_acceptance_and_pdf_generation(self):
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("2.0")
        )
        mou = MoU.objects.create(allocation=allocation, template_data={"terms": "Test terms"})
        
        # Respond to MoU
        from .public_views import public_mou_interaction
        from rest_framework.test import APIRequestFactory, force_authenticate
        
        factory = APIRequestFactory()
        request = factory.post(f'/api/manpower/public/mou/{mou.secure_token}/respond/', {'action': 'accept'}, format='json')
        response = public_mou_interaction(request, token=mou.secure_token)
        
        self.assertEqual(response.status_code, 200)
        mou.refresh_from_db()
        self.assertEqual(mou.status, "accepted")
        # Check if PDF exists and has content
        self.assertTrue(mou.signed_pdf)
        self.assertTrue(mou.signed_pdf.size > 0)

    def test_excel_export(self):
        # Create an approved adjustment
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("2.0")
        )
        PostEventAdjustment.objects.create(
            allocation=allocation,
            actual_days_worked=Decimal("2.0"),
            admin_approval_status="approved"
        )
        
        from .views import export_accounts_excel
        from rest_framework.test import APIRequestFactory, force_authenticate
        
        factory = APIRequestFactory()
        request = factory.get('/api/manpower/accounts/export/')
        force_authenticate(request, user=self.user)
        
        response = export_accounts_excel(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(len(response.content) > 0)
