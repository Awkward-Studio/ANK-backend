from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from Logistics.models.travel_details_models import TravelDetail, TravelDetailField
from Logistics.serializers.travel_details_serializers import (
    TravelDetailFieldSerializer,
    TravelDetailSerializer,
)
from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)


@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            parameters=[
                query_param(
                    "event_registration",
                    "uuid",
                    False,
                    "Filter by EventRegistration ID",
                ),
                query_param(
                    "extra_attendee", "uuid", False, "Filter by ExtraAttendee ID"
                ),
                query_param("arrival", "str", False, "Filter by arrival method"),
                query_param(
                    "return_travel", "bool", False, "Filter by return travel flag"
                ),
            ],
            description="List all travel details. Filter by event_registration, extra_attendee, arrival, or return_travel.",
            tags=["Travel Details"],
        ),
        "post": doc_create(
            request=TravelDetailSerializer,
            response=TravelDetailSerializer,
            description="Create a new travel detail (assigning multiple participants is supported).",
            tags=["Travel Details"],
        ),
    }
)
class TravelDetailList(APIView):
    def get(self, request):
        try:
            qs = TravelDetail.objects.all()
            event_registration_id = request.GET.get("event_registration")
            extra_attendee_id = request.GET.get("extra_attendee")
            arrival = request.GET.get("arrival")
            return_travel = request.GET.get("return_travel")

            if event_registration_id:
                qs = qs.filter(event_registrations__id=event_registration_id)
            if extra_attendee_id:
                qs = qs.filter(extra_attendees__id=extra_attendee_id)
            if arrival:
                qs = qs.filter(arrival=arrival)
            if return_travel is not None:
                if return_travel.lower() in ("true", "1"):
                    qs = qs.filter(return_travel=True)
                elif return_travel.lower() in ("false", "0"):
                    qs = qs.filter(return_travel=False)

            return Response(TravelDetailSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching travel details", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = TravelDetailSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            td = ser.save()
            return Response(
                TravelDetailSerializer(td).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating travel detail", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=TravelDetailSerializer,
            description="Retrieve a travel detail by ID",
            tags=["Travel Details"],
        ),
        "put": doc_update(
            request=TravelDetailSerializer,
            response=TravelDetailSerializer,
            description="Update a travel detail by ID (re-assign participants as needed).",
            tags=["Travel Details"],
        ),
        "delete": doc_destroy(
            description="Delete a travel detail by ID", tags=["Travel Details"]
        ),
    }
)
class TravelDetailDetail(APIView):
    def get(self, request, pk):
        try:
            td = get_object_or_404(TravelDetail, pk=pk)
            return Response(TravelDetailSerializer(td).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching travel detail", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            td = get_object_or_404(TravelDetail, pk=pk)
            ser = TravelDetailSerializer(td, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            td = ser.save()
            return Response(TravelDetailSerializer(td).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating travel detail", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            td = get_object_or_404(TravelDetail, pk=pk)
            td.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting travel detail", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailFieldSerializer(many=True),
            description="List all travel detail fields",
            tags=["Travel Detail Fields"],
        ),
        "post": doc_create(
            request=TravelDetailFieldSerializer,
            response=TravelDetailFieldSerializer,
            description="Create a new travel detail field",
            tags=["Travel Detail Fields"],
        ),
    }
)
class TravelDetailFieldList(APIView):
    def get(self, request):
        try:
            qs = TravelDetailField.objects.all()
            return Response(TravelDetailFieldSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching travel detail fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = TravelDetailFieldSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating travel detail field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=TravelDetailFieldSerializer,
            description="Retrieve a travel detail field by ID",
            tags=["Travel Detail Fields"],
        ),
        "put": doc_update(
            request=TravelDetailFieldSerializer,
            response=TravelDetailFieldSerializer,
            description="Update a travel detail field by ID",
            tags=["Travel Detail Fields"],
        ),
        "delete": doc_destroy(
            description="Delete a travel detail field by ID",
            tags=["Travel Detail Fields"],
        ),
    }
)
class TravelDetailFieldDetail(APIView):
    def get(self, request, pk):
        try:
            obj = get_object_or_404(TravelDetailField, pk=pk)
            return Response(TravelDetailFieldSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching travel detail field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(TravelDetailField, pk=pk)
            ser = TravelDetailFieldSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating travel detail field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(TravelDetailField, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting travel detail field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
