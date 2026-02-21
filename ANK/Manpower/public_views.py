import uuid
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import MoU, FreelancerAllocation
from .serializers import MoUSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def get_mou_by_token(request, token):
    """Fetch MoU details using the secure token."""
    try:
        mou = MoU.objects.get(secure_token=token)
    except (MoU.DoesNotExist, ValueError):
        return Response(
            {"error": "Invalid or expired token"}, status=status.HTTP_404_NOT_FOUND
        )

    # Return only necessary information for the freelancer
    data = {
        "id": mou.id,
        "status": mou.status,
        "template_data": mou.template_data,
        "freelancer_name": mou.allocation.freelancer.name,
        "event_name": mou.allocation.event_department.event.name,
        "department_name": mou.allocation.event_department.department.name,
        "negotiated_rate": mou.allocation.cost_sheet.negotiated_rate,
        "days_planned": mou.allocation.cost_sheet.days_planned,
        "total_estimated_cost": mou.allocation.cost_sheet.total_estimated_cost,
    }
    return Response(data)


@api_view(["POST"])
@permission_classes([AllowAny])
def respond_to_mou(request, token):
    """Accept or reject an MoU."""
    try:
        mou = MoU.objects.get(secure_token=token)
    except (MoU.DoesNotExist, ValueError):
        return Response(
            {"error": "Invalid or expired token"}, status=status.HTTP_404_NOT_FOUND
        )

    if mou.status in ["accepted", "rejected"]:
        return Response(
            {"error": "MoU has already been responded to"}, status=status.HTTP_400_BAD_REQUEST
        )

    action = request.data.get("action")
    if action not in ["accept", "reject"]:
        return Response(
            {"error": "Invalid action. Use 'accept' or 'reject'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if action == "accept":
        mou.status = "accepted"
        mou.accepted_at = timezone.now()
        # You could also auto-confirm the allocation if needed
        # mou.allocation.status = 'confirmed'
        # mou.allocation.save()
    else:
        mou.status = "rejected"

    mou.save()
    return Response({"status": mou.status})
