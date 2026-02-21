from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, F
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Freelancer,
    ManpowerRequirement,
    FreelancerAllocation,
    EventCostSheet,
    MoU,
    PostEventAdjustment,
    FreelancerRating,
)
from .serializers import (
    FreelancerSerializer,
    ManpowerRequirementSerializer,
    FreelancerAllocationSerializer,
    EventCostSheetSerializer,
    MoUSerializer,
    PostEventAdjustmentSerializer,
    FreelancerRatingSerializer,
)


class FreelancerViewSet(viewsets.ModelViewSet):
    queryset = Freelancer.objects.filter(is_active=True)
    serializer_class = FreelancerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["skill_category", "city"]
    search_fields = ["name", "email", "contact_phone"]
    ordering_fields = ["name", "average_rating", "base_daily_rate"]


class ManpowerRequirementViewSet(viewsets.ModelViewSet):
    queryset = ManpowerRequirement.objects.all()
    serializer_class = ManpowerRequirementSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["event_department", "status", "skill_category"]


class FreelancerAllocationViewSet(viewsets.ModelViewSet):
    queryset = FreelancerAllocation.objects.all()
    serializer_class = FreelancerAllocationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["event_department", "freelancer", "status"]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        allocation = self.get_object()
        allocation.status = "confirmed"
        allocation.save()
        return Response({"status": "confirmed"})

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        allocation = self.get_object()
        allocation.status = "released"
        allocation.save()
        return Response({"status": "released"})

    @action(detail=True, methods=["post"])
    def generate_mou(self, request, pk=None):
        allocation = self.get_object()
        # Create or update MoU
        mou, created = MoU.objects.get_or_create(
            allocation=allocation,
            defaults={"status": "draft", "template_data": {"terms": "Standard MoU terms..."}}
        )
        # Transition status to 'sent' if it was draft
        if mou.status == "draft":
            mou.status = "sent"
            mou.save()
            
        return Response({
            "status": "mou_sent",
            "mou_id": mou.id,
            "secure_link": f"/mou/{mou.secure_token}" # Frontend link
        })


class EventCostSheetViewSet(viewsets.ModelViewSet):
    queryset = EventCostSheet.objects.all()
    serializer_class = EventCostSheetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["allocation", "budget_item"]


class MoUViewSet(viewsets.ModelViewSet):
    queryset = MoU.objects.all()
    serializer_class = MoUSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["allocation", "status"]


class PostEventAdjustmentViewSet(viewsets.ModelViewSet):
    queryset = PostEventAdjustment.objects.all()
    serializer_class = PostEventAdjustmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["allocation", "admin_approval_status"]


class FreelancerRatingViewSet(viewsets.ModelViewSet):
    queryset = FreelancerRating.objects.all()
    serializer_class = FreelancerRatingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["freelancer", "event", "score"]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def accounts_summary(request):
    """
    Central view for Accounts team showing:
    - All approved invoices pending payment
    - Event-wise totals
    - Vendor-wise liabilities
    """
    # 1. Pending Payments (Approved adjustments not yet fully paid)
    # Note: Using PostEventAdjustment for finalized invoices
    pending_payments = PostEventAdjustment.objects.filter(
        admin_approval_status="approved"
    ).select_related("allocation__freelancer", "allocation__event_department__event")

    # 2. Event-wise Totals
    event_totals = pending_payments.values(
        event_name=F("allocation__event_department__event__name")
    ).annotate(
        total_liability=Sum("revised_total"),
        freelancer_count=Count("id")
    )

    # 3. Vendor-wise Liabilities
    vendor_liabilities = pending_payments.values(
        vendor_name=F("allocation__freelancer__name")
    ).annotate(
        total_amount=Sum("revised_total"),
        event_count=Count("allocation__event_department__event", distinct=True)
    )

    return Response({
        "pending_payments_count": pending_payments.count(),
        "total_liability": pending_payments.aggregate(Sum("revised_total"))["revised_total__sum"] or 0,
        "event_summaries": list(event_totals),
        "vendor_liabilities": list(vendor_liabilities),
    })
