# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.serializers.event_serializers import (
    EventSerializer,
    EventRegistrationSerializer,
)


class EventListCreateView(APIView):
    def get(self, request):
        try:
            qs = Event.objects.all()
            return Response(EventSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing events", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ev = ser.save()
            return Response(EventSerializer(ev).data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EventDetailView(APIView):
    def get(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            return Response(EventSerializer(ev).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            ser = EventSerializer(ev, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ev = ser.save()
            return Response(EventSerializer(ev).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            ev.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EventRegistrationListCreateView(APIView):
    def get(self, request):
        try:
            qs = EventRegistration.objects.all()
            return Response(EventRegistrationSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventRegistrationSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(
                EventRegistrationSerializer(reg).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EventRegistrationDetailView(APIView):
    def get(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            return Response(EventRegistrationSerializer(reg).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            ser = EventRegistrationSerializer(reg, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(EventRegistrationSerializer(reg).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            reg.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
