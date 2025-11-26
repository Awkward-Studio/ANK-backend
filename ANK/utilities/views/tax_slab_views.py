from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)
from utilities.models.tax_slab_model import TaxSlab
from utilities.serializers.tax_slab_serializer import TaxSlabSerializer


# ─────────────────────────────────────────────────────────────
# TaxSlab
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=TaxSlabSerializer(many=True),
            parameters=[
                query_param(
                    "financial_year", "str", False, "Filter by financial year (exact)"
                ),
                query_param(
                    "regime",
                    "str",
                    False,
                    "Filter by tax regime type (e.g. 'new', 'old')",
                ),
                query_param(
                    "name", "str", False, "Filter by slab set name (icontains)"
                ),
            ],
            description="List all tax slabs with optional filters (financial_year, regime, name)",
            tags=["Tax Slabs"],
        ),
        "post": doc_create(
            request=TaxSlabSerializer,
            response=TaxSlabSerializer,
            description="Create a new tax slab entry",
            tags=["Tax Slabs"],
        ),
    }
)
class TaxSlabList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = TaxSlab.objects.all().order_by("financial_year", "lower_limit")

            fy = request.query_params.get("financial_year")
            regime = request.query_params.get("regime")
            name = request.query_params.get("name")

            if fy:
                qs = qs.filter(financial_year=fy)
            if regime:
                qs = qs.filter(regime__iexact=regime)
            if name:
                qs = qs.filter(name__icontains=name)

            return Response(TaxSlabSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching tax slabs", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = TaxSlabSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating tax slab", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=TaxSlabSerializer,
            description="Retrieve a tax slab by ID",
            tags=["Tax Slabs"],
        ),
        "put": doc_update(
            request=TaxSlabSerializer,
            response=TaxSlabSerializer,
            description="Update an existing tax slab by ID",
            tags=["Tax Slabs"],
        ),
        "delete": doc_destroy(
            description="Delete a tax slab by ID",
            tags=["Tax Slabs"],
        ),
    }
)
class TaxSlabDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(TaxSlab, pk=pk)
            return Response(TaxSlabSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching tax slab", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(TaxSlab, pk=pk)
            ser = TaxSlabSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(TaxSlabSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating tax slab", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(TaxSlab, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting tax slab", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
