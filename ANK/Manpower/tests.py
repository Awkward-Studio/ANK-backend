from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile
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
    FreelancerRating,
    InvoiceWorkflow,
    ManpowerSettings,
)
from .serializers import (
    FreelancerSerializer,
    FreelancerAllocationSerializer,
    ManpowerRequirementSerializer,
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
            end_date="2026-06-05",
            location="Goa",
        )
        
        # Create a department
        self.department = Department.objects.create(name="Hospitality", slug="hospitality")
        
        # Create an EventDepartment
        self.event_department = EventDepartment.objects.create(
            event=self.event,
            department=self.department,
            display_name="Event Hospitality",
        )
        
        # Create a freelancer
        self.freelancer = Freelancer.objects.create(
            name="John Doe",
            title="Mr",
            first_name="John",
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

    def test_requirement_serializer_includes_frontend_fulfillment_columns(self):
        requirement = ManpowerRequirement.objects.create(
            event_department=self.event_department,
            name="Hospitality Team",
            teams="Hospitality Team",
            profile="Coordinator",
            skill_category="Coordinator",
            location="Beach Lawn",
            quantity_required=2,
            estimated_days=Decimal("3.0"),
            max_unit_rate=Decimal("6000.00"),
        )

        data = ManpowerRequirementSerializer(requirement).data

        self.assertEqual(data["teams"], "Hospitality Team")
        self.assertEqual(data["team"], "Hospitality Team")
        self.assertEqual(data["profile"], "Coordinator")
        self.assertEqual(data["location"], "Beach Lawn")
        self.assertEqual(data["event_department"]["display_name"], "Event Hospitality")
        self.assertEqual(data["event_department"]["department_name"], "Hospitality")

    def test_allocation_serializer_includes_flat_fulfillment_columns(self):
        requirement = ManpowerRequirement.objects.create(
            event_department=self.event_department,
            name="Hospitality Team",
            teams="Hospitality Team",
            profile="Coordinator",
            skill_category="Coordinator",
            location="Poolside",
            quantity_required=1,
            estimated_days=Decimal("2.0"),
            max_unit_rate=Decimal("6000.00"),
        )
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            requirement=requirement,
            teams="Hospitality Team",
            profile="Coordinator",
            location="Poolside",
            title="Mr",
            first_name="John",
            status="soft_blocked",
            assigned_by=self.user,
        )

        data = FreelancerAllocationSerializer(allocation).data

        self.assertEqual(data["teams"], "Hospitality Team")
        self.assertEqual(data["team"], "Hospitality Team")
        self.assertEqual(data["profile"], "Coordinator")
        self.assertEqual(data["location"], "Poolside")
        self.assertEqual(data["title"], "Mr")
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["event_department"]["display_name"], "Event Hospitality")
        self.assertEqual(data["event_department"]["department_name"], "Hospitality")

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

    def test_expired_mou_can_be_resent_with_fresh_token_and_expiry(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import generate_mou

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4500.00"),
            days_planned=Decimal("4.0"),
        )
        old_expiry = timezone.now() - timedelta(hours=1)
        mou = MoU.objects.create(
            allocation=allocation,
            status="sent",
            expires_at=old_expiry,
            access_code="482913",
            template_data={"terms": "Keep these agreed commercial terms."},
        )
        old_token = mou.secure_token

        serialized = FreelancerAllocationSerializer(allocation).data
        self.assertTrue(serialized["mou_is_expired"])
        self.assertIsNotNone(serialized["mou_expires_at"])

        request = APIRequestFactory().post(
            f"/api/manpower/allocations/{allocation.id}/generate-mou/"
        )
        force_authenticate(request, user=self.user)
        response = generate_mou(request, pk=allocation.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["resent"])
        mou.refresh_from_db()
        self.assertEqual(mou.status, "sent")
        self.assertEqual(mou.allocation_id, allocation.id)
        self.assertEqual(mou.access_code, "482913")
        self.assertEqual(mou.template_data, {"terms": "Keep these agreed commercial terms."})
        self.assertNotEqual(mou.secure_token, old_token)
        self.assertGreater(mou.expires_at, timezone.now() + timedelta(days=6))
        self.assertFalse(FreelancerAllocationSerializer(allocation).data["mou_is_expired"])

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
        from .public_views import public_mou_interaction, public_mou_pdf_download
        from rest_framework.test import APIRequestFactory, force_authenticate
        
        factory = APIRequestFactory()
        details_response = public_mou_interaction(
            factory.get(f'/api/manpower/public/mou/{mou.secure_token}/'),
            token=mou.secure_token,
        )
        self.assertEqual(details_response.status_code, 200)
        self.assertEqual(details_response.data["cost_sheet"]["negotiated_rate"], Decimal("5000.00"))
        self.assertEqual(details_response.data["cost_sheet"]["total_estimated_cost"], Decimal("10000.00"))

        signature = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        request = factory.post(
            f'/api/manpower/public/mou/{mou.secure_token}/respond/',
            {
                'action': 'accept',
                'id_type': 'PAN',
                'id_number': 'ABCDE1234F',
                'digital_signature': signature,
            },
            format='json',
        )
        response = public_mou_interaction(request, token=mou.secure_token)
        
        self.assertEqual(response.status_code, 200)
        mou.refresh_from_db()
        self.assertEqual(mou.status, "accepted")
        self.assertEqual(mou.freelancer_digital_signature, signature)
        snapshot = mou.template_data["acceptance_snapshot"]
        self.assertEqual(snapshot["freelancer_name"], "John Doe")
        self.assertEqual(snapshot["id_number"], "ABCDE1234F")
        self.assertEqual(snapshot["event_name"], "Test Wedding")
        self.assertEqual(snapshot["days_planned"], "2.0")
        self.assertEqual(snapshot["negotiated_rate"], "5000.00")
        self.assertIn("signed_pdf_url", response.data)
        self.assertTrue(response.data["signed_pdf_url"])
        pdf_response = public_mou_pdf_download(
            factory.get(f'/api/manpower/public/mou/{mou.secure_token}/pdf/'),
            token=mou.secure_token,
        )
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")

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
        MoU.objects.create(allocation=allocation, status="accepted")

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

    def test_admin_actuals_revision_reopens_freelancer_confirmation(self):
        from django.utils import timezone
        from django.urls import resolve
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import PostEventAdjustmentDetail

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            start_date="2026-06-01",
            end_date="2026-06-01",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("0.00"),
            days_planned=Decimal("1.0"),
        )
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            freelancer_submitted_at=timezone.now(),
            freelancer_digital_signature="John Doe",
        )
        request_path = f"/api/manpower/adjustments/{adjustment.id}/"
        request = APIRequestFactory().put(
            request_path,
            {
                "actual_days_worked": "2.0",
                "total_engagement_days": "2.0",
                "engagement_periods": [
                    {"start": "2026-06-01", "end": "2026-06-02", "days": 2},
                ],
                "override_negotiated_rate": "4000.00",
            },
            format="json",
        )
        request.resolver_match = resolve(request_path)
        force_authenticate(request, user=self.user)

        response = PostEventAdjustmentDetail.as_view()(request, pk=adjustment.id)

        self.assertEqual(response.status_code, 200, response.data)
        adjustment.refresh_from_db()
        self.assertIsNone(adjustment.freelancer_submitted_at)
        self.assertEqual(adjustment.freelancer_digital_signature, "")
        self.assertEqual(adjustment.admin_approval_status, "pending")
        self.assertEqual(adjustment.total_engagement_days, Decimal("2.0"))
        self.assertEqual(adjustment.revised_total, Decimal("8000.00"))

    def test_public_adjustment_returns_authoritative_revised_total_and_actual_dates(self):
        from rest_framework.test import APIRequestFactory
        from .views import public_adjustment_interaction

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            start_date="2026-06-01",
            end_date="2026-06-02",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("0.00"),
            days_planned=Decimal("1.0"),
        )
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            actual_days_worked=Decimal("2.0"),
            total_engagement_days=Decimal("2.0"),
            engagement_periods=[
                {"start": "2026-06-01", "end": "2026-06-02", "days": 2},
            ],
            override_negotiated_rate=Decimal("4000.00"),
        )

        response = public_adjustment_interaction(
            APIRequestFactory().get(f"/api/manpower/public/adjustment/{adjustment.secure_token}/"),
            token=adjustment.secure_token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_engagement_days"], Decimal("2.0"))
        self.assertEqual(response.data["revised_total"], Decimal("8000.00"))
        self.assertEqual(response.data["engagement_periods"], adjustment.engagement_periods)

    def test_public_adjustment_can_confirm_complete_saved_details(self):
        from rest_framework.test import APIRequestFactory
        from .views import public_adjustment_interaction

        saved_values = {
            "address": "Mahim, Mumbai",
            "pan_number": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "bank_account_name": "John Doe",
            "bank_name": "HDFC Bank",
            "bank_account_number": "1234567890",
            "bank_branch": "Lower Parel",
            "bank_ifsc": "HDFC0001234",
        }
        for field, value in saved_values.items():
            setattr(self.freelancer, field, value)
        self.freelancer.save(update_fields=list(saved_values))
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("1.0"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)
        factory = APIRequestFactory()
        details_response = public_adjustment_interaction(
            factory.get(f"/api/manpower/public/adjustment/{adjustment.secure_token}/"),
            token=adjustment.secure_token,
        )
        self.assertTrue(details_response.data["has_complete_saved_details"])

        response = public_adjustment_interaction(
            factory.post(
                f"/api/manpower/public/adjustment/{adjustment.secure_token}/",
                {
                    "confirm_existing_details": True,
                    "digital_signature": "John Doe",
                },
                format="json",
            ),
            token=adjustment.secure_token,
        )

        self.assertEqual(response.status_code, 200)
        self.freelancer.refresh_from_db()
        self.assertEqual(self.freelancer.pan_number, saved_values["pan_number"])
        self.assertEqual(self.freelancer.bank_account_number, saved_values["bank_account_number"])

    def test_public_dispute_does_not_require_bank_or_identity_details(self):
        from rest_framework.test import APIRequestFactory
        from .views import public_adjustment_interaction

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("1.0"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)
        request = APIRequestFactory().post(
            f"/api/manpower/public/adjustment/{adjustment.secure_token}/",
            {"status": "Disputed", "freelancer_comments": "The dates are incorrect."},
            format="json",
        )

        response = public_adjustment_interaction(request, token=adjustment.secure_token)

        self.assertEqual(response.status_code, 200)
        adjustment.refresh_from_db()
        self.assertEqual(adjustment.admin_approval_status, "disputed")
        self.assertIsNotNone(adjustment.freelancer_submitted_at)

    def test_locked_public_adjustment_ignores_tampered_commercial_values(self):
        from rest_framework.test import APIRequestFactory
        from .views import public_adjustment_interaction

        saved_values = {
            "address": "Mahim, Mumbai",
            "pan_number": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "bank_account_name": "John Doe",
            "bank_name": "HDFC Bank",
            "bank_account_number": "1234567890",
            "bank_branch": "Lower Parel",
            "bank_ifsc": "HDFC0001234",
        }
        for field, value in saved_values.items():
            setattr(self.freelancer, field, value)
        self.freelancer.save(update_fields=list(saved_values))
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            is_adjustment_editable=False,
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            total_engagement_days=Decimal("2.0"),
            override_negotiated_rate=Decimal("4000.00"),
        )
        request = APIRequestFactory().post(
            f"/api/manpower/public/adjustment/{adjustment.secure_token}/",
            {
                "confirm_existing_details": True,
                "digital_signature": "John Doe",
                "total_engagement_days": "99",
                "override_negotiated_rate": "999999",
                "other_adjustments": "999999",
            },
            format="json",
        )

        response = public_adjustment_interaction(request, token=adjustment.secure_token)

        self.assertEqual(response.status_code, 200)
        adjustment.refresh_from_db()
        self.assertEqual(adjustment.total_engagement_days, Decimal("2.0"))
        self.assertEqual(adjustment.override_negotiated_rate, Decimal("4000.00"))
        self.assertEqual(adjustment.other_adjustments, Decimal("0.00"))

    def test_actuals_link_requires_confirmed_allocation_and_accepted_mou(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import issue_adjustment_secure_link

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        factory = APIRequestFactory()
        request = factory.post(f"/api/manpower/allocations/{allocation.id}/issue-adjustment-link/")
        force_authenticate(request, user=self.user)

        response = issue_adjustment_secure_link(request, allocation_id=allocation.id)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(PostEventAdjustment.objects.filter(allocation=allocation).exists())

        MoU.objects.create(allocation=allocation, status="accepted")
        request = factory.post(f"/api/manpower/allocations/{allocation.id}/issue-adjustment-link/")
        force_authenticate(request, user=self.user)
        response = issue_adjustment_secure_link(request, allocation_id=allocation.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PostEventAdjustment.objects.filter(allocation=allocation).exists())

    def test_signed_allocation_cannot_be_deleted_and_released_link_expires(self):
        from django.urls import resolve
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .public_views import public_mou_interaction
        from .views import FreelancerAllocationDetail, release_allocation

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        mou = MoU.objects.create(allocation=allocation, status="accepted")
        delete_path = f"/api/manpower/allocations/{allocation.id}/"
        delete_request = APIRequestFactory().delete(delete_path)
        delete_request.resolver_match = resolve(delete_path)
        force_authenticate(delete_request, user=self.user)

        delete_response = FreelancerAllocationDetail.as_view()(delete_request, pk=allocation.id)

        self.assertEqual(delete_response.status_code, 409)
        self.assertTrue(FreelancerAllocation.objects.filter(pk=allocation.id).exists())

        release_request = APIRequestFactory().post(f"/api/manpower/allocations/{allocation.id}/release/")
        force_authenticate(release_request, user=self.user)
        release_response = release_allocation(release_request, pk=allocation.id)
        self.assertEqual(release_response.status_code, 200)

        public_response = public_mou_interaction(
            APIRequestFactory().get(f"/api/manpower/public/mou/{mou.secure_token}/"),
            token=mou.secure_token,
        )
        self.assertEqual(public_response.status_code, 410)

    def test_submitted_actuals_prevent_allocation_release(self):
        from django.utils import timezone
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import release_allocation

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        PostEventAdjustment.objects.create(
            allocation=allocation,
            freelancer_submitted_at=timezone.now(),
            freelancer_digital_signature="John Doe",
        )
        request = APIRequestFactory().post(f"/api/manpower/allocations/{allocation.id}/release/")
        force_authenticate(request, user=self.user)

        response = release_allocation(request, pk=allocation.id)

        self.assertEqual(response.status_code, 409)
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, "confirmed")

    def test_accepted_mou_locks_requirement_allocation_cost_sheet_and_mou_terms(self):
        from django.urls import resolve
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import (
            EventCostSheetDetail,
            FreelancerAllocationDetail,
            ManpowerRequirementDetail,
            MoUDetail,
        )

        requirement = ManpowerRequirement.objects.create(
            event_department=self.event_department,
            name="Coordinator",
            quantity_required=1,
            start_date="2026-06-01",
            end_date="2026-06-02",
        )
        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            requirement=requirement,
            status="confirmed",
            assigned_by=self.user,
        )
        cost_sheet = EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        mou = MoU.objects.create(allocation=allocation, status="accepted")
        factory = APIRequestFactory()

        cases = [
            (ManpowerRequirementDetail, requirement.id, "requirements", {"name": "Changed"}),
            (FreelancerAllocationDetail, allocation.id, "allocations", {"start_date": "2026-06-03"}),
            (EventCostSheetDetail, cost_sheet.id, "cost-sheets", {"negotiated_rate": "1.00"}),
            (MoUDetail, mou.id, "mous", {"template_data": {"terms": "changed"}}),
        ]
        for view, object_id, route, payload in cases:
            path = f"/api/manpower/{route}/{object_id}/"
            request = factory.put(path, payload, format="json")
            request.resolver_match = resolve(path)
            force_authenticate(request, user=self.user)
            response = view.as_view()(request, pk=object_id)
            self.assertEqual(response.status_code, 409, (route, response.data))

        # The single post-signature control remains independently editable.
        path = f"/api/manpower/allocations/{allocation.id}/"
        request = factory.put(path, {"is_adjustment_editable": True}, format="json")
        request.resolver_match = resolve(path)
        force_authenticate(request, user=self.user)
        response = FreelancerAllocationDetail.as_view()(request, pk=allocation.id)
        self.assertEqual(response.status_code, 200, response.data)

    def test_actuals_approval_requires_signature_and_atomically_creates_invoice(self):
        from django.urls import resolve
        from django.utils import timezone
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import PostEventAdjustmentDetail

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            total_engagement_days=Decimal("2.0"),
            freelancer_submitted_at=timezone.now(),
        )
        request_path = f"/api/manpower/adjustments/{adjustment.id}/"

        def approval_request():
            request = APIRequestFactory().put(
                request_path,
                {"admin_approval_status": "approved"},
                format="json",
            )
            request.resolver_match = resolve(request_path)
            force_authenticate(request, user=self.user)
            return request

        response = PostEventAdjustmentDetail.as_view()(approval_request(), pk=adjustment.id)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(InvoiceWorkflow.objects.filter(adjustment=adjustment).exists())

        adjustment.freelancer_digital_signature = "John Doe"
        adjustment.save()
        response = PostEventAdjustmentDetail.as_view()(approval_request(), pk=adjustment.id)

        self.assertEqual(response.status_code, 200, response.data)
        adjustment.refresh_from_db()
        invoice = InvoiceWorkflow.objects.get(adjustment=adjustment)
        self.assertEqual(adjustment.admin_approval_status, "approved")
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.payable_amount, adjustment.revised_total)

    def test_invoice_detail_cannot_bypass_amount_or_status_transitions(self):
        from django.urls import resolve
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import InvoiceWorkflowDetail

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("4000.00"),
            days_planned=Decimal("2.0"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)
        invoice = InvoiceWorkflow.objects.create(
            adjustment=adjustment,
            event=self.event,
            event_department=self.event_department,
            freelancer=self.freelancer,
            invoice_number="INV-PROTECTED-FIELDS",
            payable_amount=Decimal("8000.00"),
        )
        request_path = f"/api/manpower/invoices/{invoice.id}/"
        request = APIRequestFactory().put(
            request_path,
            {"status": "paid", "payable_amount": "1.00", "notes": "Reviewed"},
            format="json",
        )
        request.resolver_match = resolve(request_path)
        force_authenticate(request, user=self.user)

        response = InvoiceWorkflowDetail.as_view()(request, pk=invoice.id)

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.payable_amount, Decimal("8000.00"))
        self.assertEqual(invoice.notes, "Reviewed")

        # Once an invoice exists, actuals cannot be changed behind its back.
        from .views import PostEventAdjustmentDetail
        adjustment_path = f"/api/manpower/adjustments/{adjustment.id}/"
        adjustment_request = APIRequestFactory().put(
            adjustment_path,
            {"total_engagement_days": "3.0"},
            format="json",
        )
        adjustment_request.resolver_match = resolve(adjustment_path)
        force_authenticate(adjustment_request, user=self.user)
        adjustment_response = PostEventAdjustmentDetail.as_view()(
            adjustment_request,
            pk=adjustment.id,
        )
        self.assertEqual(adjustment_response.status_code, 409)

    def test_public_adjustment_requires_profile_id_signature_and_bank_details(self):
        from .views import public_adjustment_interaction
        from rest_framework.test import APIRequestFactory

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
            travel_costs=Decimal("1000.00"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/manpower/public/adjustment/{adjustment.secure_token}/",
            {
                "actual_days_worked": "3.0",
                "total_engagement_days": "3.0",
                "travel_adjustments": "0.00",
                "other_adjustments": "0.00",
                "bank_account_name": "John Doe",
                "bank_name": "HDFC Bank",
                "bank_account_number": "1234567890",
                "bank_branch": "Lower Parel",
                "bank_ifsc": "HDFC0001234",
            },
            format="json",
        )

        response = public_adjustment_interaction(request, token=adjustment.secure_token)

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data["missing_fields"])
        self.assertIn("address", response.data["missing_fields"])
        self.assertIn("pan_number", response.data["missing_fields"])
        self.assertIn("aadhaar_number", response.data["missing_fields"])
        self.assertIn("digital_signature", response.data["missing_fields"])

    def test_public_adjustment_saves_profile_id_signature_and_bank_details(self):
        from .views import public_adjustment_interaction
        from rest_framework.test import APIRequestFactory

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
            travel_costs=Decimal("1000.00"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/manpower/public/adjustment/{adjustment.secure_token}/",
            {
                "actual_days_worked": "3.0",
                "total_engagement_days": "3.0",
                "travel_adjustments": "0.00",
                "other_adjustments": "0.00",
                "email": "freelancer@example.com",
                "address": "Mahim, Mumbai",
                "pan_number": "ABCDE1234F",
                "aadhaar_number": "123456789012",
                "digital_signature": "John Doe",
                "bank_account_name": "John Doe",
                "bank_name": "HDFC Bank",
                "bank_account_number": "1234567890",
                "bank_branch": "Lower Parel",
                "bank_ifsc": "HDFC0001234",
            },
            format="json",
        )

        response = public_adjustment_interaction(request, token=adjustment.secure_token)

        self.assertEqual(response.status_code, 200)
        adjustment.refresh_from_db()
        self.freelancer.refresh_from_db()
        self.assertIsNotNone(adjustment.freelancer_submitted_at)
        self.assertEqual(adjustment.freelancer_digital_signature, "John Doe")
        self.assertEqual(self.freelancer.email, "freelancer@example.com")
        self.assertEqual(self.freelancer.address, "Mahim, Mumbai")
        self.assertEqual(self.freelancer.id_type, "PAN")
        self.assertEqual(self.freelancer.id_number, "ABCDE1234F")
        self.assertEqual(self.freelancer.pan_number, "ABCDE1234F")
        self.assertEqual(self.freelancer.aadhaar_number, "123456789012")
        self.assertEqual(self.freelancer.bank_ifsc, "HDFC0001234")

    def test_public_adjustment_uploads_pan_and_aadhaar_documents(self):
        from .views import public_adjustment_interaction
        from rest_framework.test import APIRequestFactory

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            is_adjustment_editable=True,
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
            travel_costs=Decimal("1000.00"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)

        pan_document = SimpleUploadedFile(
            "pan.jpg",
            b"\xff\xd8\xff\xe0test-pan",
            content_type="image/jpeg",
        )
        aadhaar_document = SimpleUploadedFile(
            "aadhaar.png",
            b"\x89PNG\r\n\x1a\ntest-aadhaar",
            content_type="image/png",
        )

        factory = APIRequestFactory()
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            request = factory.post(
                f"/api/manpower/public/adjustment/{adjustment.secure_token}/",
                {
                    "actual_days_worked": "3.0",
                    "total_engagement_days": "3.0",
                    "engagement_periods": '[{"start":"2026-06-01","end":"2026-06-03","days":3}]',
                    "travel_adjustments": "0.00",
                    "other_adjustments": "0.00",
                    "email": "freelancer-upload@example.com",
                    "address": "Mahim, Mumbai",
                    "pan_number": "ABCDE1234F",
                    "aadhaar_number": "123456789012",
                    "digital_signature": "John Doe",
                    "bank_account_name": "John Doe",
                    "bank_name": "HDFC Bank",
                    "bank_account_number": "1234567890",
                    "bank_branch": "Lower Parel",
                    "bank_ifsc": "HDFC0001234",
                    "pan_document": pan_document,
                    "aadhaar_document": aadhaar_document,
                },
                format="multipart",
            )

            response = public_adjustment_interaction(request, token=adjustment.secure_token)

            self.assertEqual(response.status_code, 200)
            self.freelancer.refresh_from_db()
            adjustment.refresh_from_db()
            self.assertTrue(self.freelancer.pan_document.name.startswith("freelancer_documents/pan/"))
            self.assertTrue(self.freelancer.aadhaar_document.name.startswith("freelancer_documents/aadhaar/"))
            self.assertEqual(
                adjustment.engagement_periods,
                [{"start": "2026-06-01", "end": "2026-06-03", "days": 3}],
            )

    def test_invoice_approval_records_approved_timestamp_without_signature_upload(self):
        from .views import invoice_transition
        from rest_framework.test import APIRequestFactory, force_authenticate

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
            travel_costs=Decimal("1000.00"),
        )
        adjustment = PostEventAdjustment.objects.create(allocation=allocation)
        invoice = InvoiceWorkflow.objects.create(
            adjustment=adjustment,
            event=self.event,
            event_department=self.event_department,
            freelancer=self.freelancer,
            invoice_number="INV-SIGN-OK",
            payable_amount=Decimal("15000.00"),
            status="submitted",
        )

        factory = APIRequestFactory()
        request = factory.patch(
            f"/api/manpower/invoices/{invoice.id}/status/",
            {"status": "approved"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = invoice_transition(request, pk=invoice.id)

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "approved")
        self.assertIsNotNone(invoice.approved_at)

    def test_actuals_approval_authorizes_invoice_signature(self):
        from .public_views import get_invoice_approval_details

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
        )
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            admin_approval_status="approved",
        )
        invoice = InvoiceWorkflow.objects.create(
            adjustment=adjustment,
            event=self.event,
            event_department=self.event_department,
            freelancer=self.freelancer,
            invoice_number="INV-ACTUALS-SIGNED",
            status="draft",
        )

        approval_text, approval_at = get_invoice_approval_details(invoice)

        self.assertEqual(
            approval_text,
            "Digitally Signed by Divya Jain - Manager People & Strategy",
        )
        self.assertEqual(approval_at, adjustment.updated_at)

    def test_invoice_signatory_uses_backend_fallback_for_blank_settings(self):
        from .public_views import get_invoice_approval_details

        allocation = FreelancerAllocation.objects.create(
            freelancer=self.freelancer,
            event_department=self.event_department,
            status="confirmed",
            assigned_by=self.user,
        )
        EventCostSheet.objects.create(
            allocation=allocation,
            negotiated_rate=Decimal("5000.00"),
            days_planned=Decimal("3.0"),
        )
        adjustment = PostEventAdjustment.objects.create(
            allocation=allocation,
            admin_approval_status="approved",
        )
        invoice = InvoiceWorkflow.objects.create(
            adjustment=adjustment,
            event=self.event,
            event_department=self.event_department,
            freelancer=self.freelancer,
            invoice_number="INV-SIGNATORY-FALLBACK",
            status="draft",
        )
        settings = ManpowerSettings.get_settings()
        settings.invoice_authorised_signatory_name = "   "
        settings.invoice_authorised_signatory_title = "   "
        settings.save()

        approval_text, _ = get_invoice_approval_details(invoice)

        self.assertEqual(
            approval_text,
            "Digitally Signed by Divya Jain - Manager People & Strategy",
        )
