"""
Public views for Client View API - no authentication required.
These views expose only non-sensitive data safe for public access.
"""
import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.serializers.public_serializers import PublicEventSerializer

logger = logging.getLogger(__name__)


class ClientViewThrottle(AnonRateThrottle):
    """Rate limiting for client view endpoint - 100 requests per hour"""
    rate = "100/hour"


class ClientViewAPIView(APIView):
    """
    Public endpoint for client view - no authentication required.
    Returns limited event and guest data safe for public exposure.
    
    GET /api/public/events/{event_id}/client-view/
    
    Response:
    {
        "event": {...},
        "guests": [...],
        "summary": {...}
    }
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # Explicitly disable authentication
    throttle_classes = [ClientViewThrottle]

    def get(self, request, event_id):
        # Log access for monitoring
        logger.info(
            f"Client view accessed for event {event_id} "
            f"from IP {request.META.get('REMOTE_ADDR')}"
        )

        # Fetch event or return 404
        event = get_object_or_404(Event, id=event_id)

        # Fetch registrations with related guest data
        registrations = EventRegistration.objects.filter(
            event_id=event_id
        ).select_related("guest")

        # Build guest list with only safe fields
        guests = []
        for reg in registrations:
            guests.append({
                "id": str(reg.id),
                "name": reg.guest.name if reg.guest else "Unknown",
                "rsvp_status": reg.rsvp_status or "not_sent",
                "estimated_pax": reg.estimated_pax or 1,
            })

        # Calculate summary statistics
        summary = self._calculate_summary(registrations)

        # Build response
        response_data = {
            "event": PublicEventSerializer(event).data,
            "guests": guests,
            "summary": summary,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def _calculate_summary(self, registrations):
        """Calculate aggregate statistics for the event"""

        stats = registrations.aggregate(
            total_invited=Count("id"),
            total_pax=Sum("estimated_pax"),
            confirmed=Count("id", filter=Q(rsvp_status__iexact="yes")),
            confirmed_pax=Sum("estimated_pax", filter=Q(rsvp_status__iexact="yes")),
            declined=Count("id", filter=Q(rsvp_status__iexact="no")),
            maybe=Count("id", filter=Q(rsvp_status__iexact="maybe")),
        )

        # Calculate pending (total - confirmed - declined - maybe)
        confirmed = stats["confirmed"] or 0
        declined = stats["declined"] or 0
        maybe = stats["maybe"] or 0
        total = stats["total_invited"] or 0

        return {
            "total_invited": total,
            "total_pax": stats["total_pax"] or 0,
            "confirmed": confirmed,
            "confirmed_pax": stats["confirmed_pax"] or 0,
            "declined": declined,
            "maybe": maybe,
            "pending": total - confirmed - declined - maybe,
        }
