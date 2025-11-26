from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from utilities.models.vendor_model import Vendor
from utilities.serializers.vendor_serializer import VendorSerializer
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
            response=VendorSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter vendors by name (icontains)"),
                query_param(
                    "service_category", "str", False, "Filter by service category"
                ),
                query_param("city", "str", False, "Filter by city"),
            ],
            description="List all vendors, with optional filters for name, service category, or city.",
            tags=["Vendors"],
        ),
        "post": doc_create(
            request=VendorSerializer,
            response=VendorSerializer,
            description="Create a new vendor",
            tags=["Vendors"],
        ),
    }
)
class VendorList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = Vendor.objects.all()
            name = request.query_params.get("name")
            service_category = request.query_params.get("service_category")
            city = request.query_params.get("city")

            if name:
                qs = qs.filter(name__icontains=name)
            if service_category:
                qs = qs.filter(service_category__icontains=service_category)
            if city:
                qs = qs.filter(city__icontains=city)

            return Response(VendorSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching vendors", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = VendorSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating vendor", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=VendorSerializer,
            description="Retrieve a vendor by ID",
            tags=["Vendors"],
        ),
        "put": doc_update(
            request=VendorSerializer,
            response=VendorSerializer,
            description="Update an existing vendor",
            tags=["Vendors"],
        ),
        "delete": doc_destroy(
            description="Delete a vendor by ID",
            tags=["Vendors"],
        ),
    }
)
class VendorDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(Vendor, pk=pk)
            return Response(VendorSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching vendor", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(Vendor, pk=pk)
            ser = VendorSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating vendor", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(Vendor, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting vendor", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
