from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
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
from .serializers import FreelancerSerializer

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
            base_daily_rate=Decimal("5000.00")
        )

    def test_manpower_requirement_creation(self):
        requirement = ManpowerRequirement.objects.create(
            event_department=self.event_department,
            name="Coordinator Lead",
            skill_category="Coordinator",
            quantity_required=2,
            estimated_days=Decimal("3.0"),
            max_unit_rate=Decimal("6000.00")
        )
        self.assertEqual(requirement.status, "pending")
        self.assertEqual(str(requirement), "2x Coordinator Lead for " + str(self.event_department))

    def test_freelancer_serializer_allows_missing_email(self):
        serializer = FreelancerSerializer(data={
            "name": "No Email Freelancer",
            "skill_category": "Crew",
            "city": "Mumbai",
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        freelancer = serializer.save()

        self.assertIsNone(freelancer.email)

    def test_freelancer_serializer_normalizes_blank_email_to_null(self):
        serializer = FreelancerSerializer(data={
            "name": "Blank Email Freelancer",
            "skill_category": "Crew",
            "city": "Delhi",
            "email": "   ",
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        freelancer = serializer.save()

        self.assertIsNone(freelancer.email)

    def test_multiple_freelancers_without_email_do_not_conflict(self):
        first = FreelancerSerializer(data={
            "name": "No Email One",
            "skill_category": "Crew",
            "city": "Mumbai",
            "email": "",
        })
        second = FreelancerSerializer(data={
            "name": "No Email Two",
            "skill_category": "Crew",
            "city": "Delhi",
        })

        self.assertTrue(first.is_valid(), first.errors)
        self.assertTrue(second.is_valid(), second.errors)
        first.save()
        second.save()

        self.assertEqual(
            Freelancer.objects.filter(name__startswith="No Email").count(),
            2,
        )

    def test_freelancer_serializer_rejects_invalid_non_empty_email(self):
        serializer = FreelancerSerializer(data={
            "name": "Invalid Email Freelancer",
            "skill_category": "Crew",
            "city": "Mumbai",
            "email": "not-an-email",
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

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
            travel_costs=Decimal("1000.00")
        )
        self.assertEqual(cost_sheet.total_estimated_cost, Decimal("19000.00"))

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
            travel_costs=Decimal("1000.00")
        )

        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            actual_days_worked=Decimal("3.0"),
            total_engagement_days=Decimal("3.0"),
            other_adjustments=Decimal("200.00")
        )
        self.assertEqual(adjustment.revised_total, Decimal("16200.00"))

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
        self.assertIn("signed_pdf_url", response.data)
        self.assertTrue(response.data["signed_pdf_url"])

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

    def test_reissuing_adjustment_link_does_not_mutate_existing_adjustment(self):
        from .views import issue_adjustment_secure_link
        from rest_framework.test import APIRequestFactory, force_authenticate

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            start_date="2026-06-01",
            end_date="2026-06-03",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
            travel_costs=Decimal("1000.00"),
        )

        factory = APIRequestFactory()

        first_request = factory.post(
            f"/api/manpower/allocations/{allocation.id}/issue-adjustment-link/"
        )
        force_authenticate(first_request, user=self.user)
        first_response = issue_adjustment_secure_link(first_request, allocation_id=allocation.id)

        self.assertEqual(first_response.status_code, 200)

        adjustment = PostEventAdjustment.objects.get(allocation=allocation)
        adjustment.actual_days_worked = Decimal("4.0")
        adjustment.total_engagement_days = Decimal("4.5")
        adjustment.engagement_periods = [
            {"start": "2026-06-01", "end": "2026-06-02", "days": 2.0},
            {"start": "2026-06-05", "end": "2026-06-07", "days": 2.5},
        ]
        adjustment.travel_adjustments = Decimal("321.00")
        adjustment.other_adjustments = Decimal("654.00")
        adjustment.override_negotiated_rate = Decimal("7200.00")
        adjustment.freelancer_comments = "Saved draft comments"
        adjustment.save()

        snapshot = {
            "actual_days_worked": adjustment.actual_days_worked,
            "total_engagement_days": adjustment.total_engagement_days,
            "engagement_periods": adjustment.engagement_periods,
            "travel_adjustments": adjustment.travel_adjustments,
            "other_adjustments": adjustment.other_adjustments,
            "override_negotiated_rate": adjustment.override_negotiated_rate,
            "freelancer_comments": adjustment.freelancer_comments,
            "revised_total": adjustment.revised_total,
            "secure_token": adjustment.secure_token,
            "revision_count": adjustment.revisions.count(),
        }

        second_request = factory.post(
            f"/api/manpower/allocations/{allocation.id}/issue-adjustment-link/"
        )
        force_authenticate(second_request, user=self.user)
        second_response = issue_adjustment_secure_link(second_request, allocation_id=allocation.id)

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(str(second_response.data["adjustment_id"]), str(adjustment.id))
        self.assertEqual(str(second_response.data["secure_token"]), str(snapshot["secure_token"]))
        self.assertEqual(
            second_response.data["secure_link"],
            f"/adjustment/{snapshot['secure_token']}",
        )

        adjustment.refresh_from_db()
        self.assertEqual(adjustment.actual_days_worked, snapshot["actual_days_worked"])
        self.assertEqual(adjustment.total_engagement_days, snapshot["total_engagement_days"])
        self.assertEqual(adjustment.engagement_periods, snapshot["engagement_periods"])
        self.assertEqual(adjustment.travel_adjustments, snapshot["travel_adjustments"])
        self.assertEqual(adjustment.other_adjustments, snapshot["other_adjustments"])
        self.assertEqual(adjustment.override_negotiated_rate, snapshot["override_negotiated_rate"])
        self.assertEqual(adjustment.freelancer_comments, snapshot["freelancer_comments"])
        self.assertEqual(adjustment.revised_total, snapshot["revised_total"])
        self.assertEqual(adjustment.revisions.count(), snapshot["revision_count"])
