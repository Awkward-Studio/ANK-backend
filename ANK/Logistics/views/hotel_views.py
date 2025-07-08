from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from Logistics.models.accomodation_models import Hotel
from Logistics.serializers.hotel_serializers import HotelSerializer

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
            response=HotelSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter by hotel name"),
            ],
            description="List all hotels",
            tags=["Hotels"],
        ),
        "post": doc_create(
            request=HotelSerializer,
            response=HotelSerializer,
            description="Create a new hotel",
            tags=["Hotels"],
        ),
    }
)
class HotelList(APIView):
    def get(self, request):
        try:
            qs = Hotel.objects.all()
            return Response(HotelSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching hotels", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = HotelSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            hotel = ser.save()
            return Response(HotelSerializer(hotel).data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=HotelSerializer,
            description="Retrieve a hotel by ID",
            tags=["Hotels"],
        ),
        "put": doc_update(
            request=HotelSerializer,
            response=HotelSerializer,
            description="Update a hotel by ID",
            tags=["Hotels"],
        ),
        "delete": doc_destroy(description="Delete a hotel by ID", tags=["Hotels"]),
    }
)
class HotelDetail(APIView):
    def get(self, request, pk):
        try:
            hotel = get_object_or_404(Hotel, pk=pk)
            return Response(HotelSerializer(hotel).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            hotel = get_object_or_404(Hotel, pk=pk)
            ser = HotelSerializer(hotel, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            hotel = ser.save()
            return Response(HotelSerializer(hotel).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hotel = get_object_or_404(Hotel, pk=pk)
            hotel.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
