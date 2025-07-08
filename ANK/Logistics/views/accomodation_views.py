from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from Logistics.models.accomodation_models import Accommodation
from Logistics.serializers.accomodation_serializers import AccommodationSerializer
from utils.swagger import (
    doc_create,
    doc_list,
    doc_retrieve,
    doc_update,
    doc_destroy,
    document_api_view,
    query_param,
)


@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            parameters=[
                query_param(
                    "event_registration", "uuid", False, "Filter by event registration"
                ),
                query_param(
                    "session_registration",
                    "uuid",
                    False,
                    "Filter by session registration",
                ),
                query_param("hotel", "uuid", False, "Filter by hotel ID"),
            ],
            description="List all accommodations",
            tags=["Accommodations"],
        ),
        "post": doc_create(
            request=AccommodationSerializer,
            response=AccommodationSerializer,
            description="Create a new accommodation",
            tags=["Accommodations"],
        ),
    }
)
class AccommodationList(APIView):
    def get(self, request):
        try:
            qs = Accommodation.objects.all()
            return Response(AccommodationSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching accommodations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = AccommodationSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            acc = ser.save()
            return Response(
                AccommodationSerializer(acc).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating accommodation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=AccommodationSerializer,
            description="Retrieve an accommodation by ID",
            tags=["Accommodations"],
        ),
        "put": doc_update(
            request=AccommodationSerializer,
            response=AccommodationSerializer,
            description="Update an accommodation by ID",
            tags=["Accommodations"],
        ),
        "delete": doc_destroy(
            description="Delete an accommodation by ID",
            tags=["Accommodations"],
        ),
    }
)
class AccommodationDetail(APIView):
    def get(self, request, pk):
        try:
            acc = get_object_or_404(Accommodation, pk=pk)
            return Response(AccommodationSerializer(acc).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching accommodation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            acc = get_object_or_404(Accommodation, pk=pk)
            ser = AccommodationSerializer(acc, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            acc = ser.save()
            return Response(AccommodationSerializer(acc).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating accommodation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            acc = get_object_or_404(Accommodation, pk=pk)
            acc.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting accommodation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
