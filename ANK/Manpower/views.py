from rest_framework import status, filters
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, F, Avg
from django.db import transaction
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font
from django_filters.rest_framework import DjangoFilterBackend
from Departments.mixins import DepartmentAccessMixin
from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)
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


@document_api_view(
    {
        "get": doc_list(
            response=FreelancerSerializer(many=True),
            parameters=[
                query_param("skill_category", "str", False, "Filter by skill category"),
                query_param("city", "str", False, "Filter by city"),
                query_param("search", "str", False, "Search by name, email, or phone"),
            ],
            description="List all active freelancers",
            tags=["Manpower: Freelancers"],
        ),
        "post": doc_create(
            request=FreelancerSerializer,
            response=FreelancerSerializer,
            description="Create a new freelancer",
            tags=["Manpower: Freelancers"],
        ),
    }
)
class FreelancerList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = Freelancer.objects.filter(is_active=True)
            
            # Filtering
            skill = request.query_params.get("skill_category")
            city = request.query_params.get("city")
            search = request.query_params.get("search")
            
            if skill:
                qs = qs.filter(skill_category=skill)
            if city:
                qs = qs.filter(city=city)
            if search:
                qs = qs.filter(
                    F("name").icontains(search) | 
                    F("email").icontains(search) | 
                    F("contact_phone").icontains(search)
                )
            
            # Ordering
            ordering = request.query_params.get("ordering")
            if ordering:
                qs = qs.order_by(ordering)
            else:
                qs = qs.order_by("name")

            return Response(FreelancerSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching freelancers", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = FreelancerSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=FreelancerSerializer,
            description="Retrieve a freelancer by ID",
            tags=["Manpower: Freelancers"],
        ),
        "put": doc_update(
            request=FreelancerSerializer,
            response=FreelancerSerializer,
            description="Update a freelancer by ID",
            tags=["Manpower: Freelancers"],
        ),
        "delete": doc_destroy(description="Deactivate a freelancer", tags=["Manpower: Freelancers"]),
    }
)
class FreelancerDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(Freelancer, pk=pk)
            return Response(FreelancerSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(Freelancer, pk=pk)
            ser = FreelancerSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(Freelancer, pk=pk)
            obj.is_active = False
            obj.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deactivating freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=ManpowerRequirementSerializer(many=True),
            parameters=[
                query_param("event_department", "uuid", False, "Filter by event department ID"),
                query_param("status", "str", False, "Filter by status"),
                query_param("skill_category", "str", False, "Filter by skill category"),
            ],
            description="List manpower requirements",
            tags=["Manpower: Requirements"],
        ),
        "post": doc_create(
            request=ManpowerRequirementSerializer,
            response=ManpowerRequirementSerializer,
            description="Create a manpower requirement",
            tags=["Manpower: Requirements"],
        ),
    }
)
class ManpowerRequirementList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return ManpowerRequirement.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            
            ed = request.query_params.get("event_department")
            stat = request.query_params.get("status")
            skill = request.query_params.get("skill_category")
            
            if ed:
                qs = qs.filter(event_department_id=ed)
            if stat:
                qs = qs.filter(status=stat)
            if skill:
                qs = qs.filter(skill_category=skill)
                
            return Response(ManpowerRequirementSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching requirements", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = ManpowerRequirementSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=ManpowerRequirementSerializer,
            description="Retrieve a manpower requirement by ID",
            tags=["Manpower: Requirements"],
        ),
        "put": doc_update(
            request=ManpowerRequirementSerializer,
            response=ManpowerRequirementSerializer,
            description="Update a manpower requirement by ID",
            tags=["Manpower: Requirements"],
        ),
        "delete": doc_destroy(description="Delete a manpower requirement", tags=["Manpower: Requirements"]),
    }
)
class ManpowerRequirementDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return ManpowerRequirement.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(ManpowerRequirementSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = ManpowerRequirementSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=FreelancerAllocationSerializer(many=True),
            parameters=[
                query_param("event_department", "uuid", False, "Filter by event department ID"),
                query_param("freelancer", "uuid", False, "Filter by freelancer ID"),
                query_param("status", "str", False, "Filter by status"),
            ],
            description="List freelancer allocations",
            tags=["Manpower: Allocations"],
        ),
        "post": doc_create(
            request=FreelancerAllocationSerializer,
            response=FreelancerAllocationSerializer,
            description="Create a freelancer allocation",
            tags=["Manpower: Allocations"],
        ),
    }
)
class FreelancerAllocationList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerAllocation.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            
            ed = request.query_params.get("event_department")
            free = request.query_params.get("freelancer")
            stat = request.query_params.get("status")
            
            if ed:
                qs = qs.filter(event_department_id=ed)
            if free:
                qs = qs.filter(freelancer_id=free)
            if stat:
                qs = qs.filter(status=stat)
                
            return Response(FreelancerAllocationSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching allocations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = FreelancerAllocationSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=FreelancerAllocationSerializer,
            description="Retrieve a freelancer allocation by ID",
            tags=["Manpower: Allocations"],
        ),
        "put": doc_update(
            request=FreelancerAllocationSerializer,
            response=FreelancerAllocationSerializer,
            description="Update a freelancer allocation by ID",
            tags=["Manpower: Allocations"],
        ),
        "delete": doc_destroy(description="Delete a freelancer allocation", tags=["Manpower: Allocations"]),
    }
)
class FreelancerAllocationDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerAllocation.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(FreelancerAllocationSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = FreelancerAllocationSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_allocation(request, pk):
    """Confirm a freelancer allocation."""
    try:
        allocation = get_object_or_404(FreelancerAllocation, pk=pk)
        allocation.status = "confirmed"
        allocation.save()
        return Response({"status": "confirmed"})
    except Exception as e:
        return Response(
            {"detail": "Error confirming allocation", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def release_allocation(request, pk):
    """Release a freelancer allocation."""
    try:
        allocation = get_object_or_404(FreelancerAllocation, pk=pk)
        allocation.status = "released"
        allocation.save()
        return Response({"status": "released"})
    except Exception as e:
        return Response(
            {"detail": "Error releasing allocation", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_mou(request, pk):
    """Generate or update MoU for an allocation and transition it to sent."""
    try:
        allocation = get_object_or_404(FreelancerAllocation, pk=pk)
        mou, created = MoU.objects.get_or_create(
            allocation=allocation,
            defaults={"status": "draft", "template_data": {"terms": "Standard MoU terms..."}}
        )
        if mou.status == "draft":
            mou.status = "sent"
            mou.save()
            # TODO: Notification - Send the secure token link via Email/WhatsApp to the freelancer
            
        return Response({
            "status": "mou_sent",
            "mou_id": mou.id,
            "secure_link": f"/mou/{mou.secure_token}"
        })
    except Exception as e:
        return Response(
            {"detail": "Error generating MoU", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_api_view(
    {
        "get": doc_list(
            response=EventCostSheetSerializer(many=True),
            parameters=[
                query_param("allocation", "uuid", False, "Filter by allocation ID"),
                query_param("budget_item", "uuid", False, "Filter by budget item ID"),
            ],
            description="List cost sheets",
            tags=["Manpower: Cost Sheets"],
        ),
        "post": doc_create(
            request=EventCostSheetSerializer,
            response=EventCostSheetSerializer,
            description="Create a cost sheet",
            tags=["Manpower: Cost Sheets"],
        ),
    }
)
class EventCostSheetList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return EventCostSheet.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            
            alloc = request.query_params.get("allocation")
            budget = request.query_params.get("budget_item")
            
            if alloc:
                qs = qs.filter(allocation_id=alloc)
            if budget:
                qs = qs.filter(budget_item_id=budget)
                
            return Response(EventCostSheetSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching cost sheets", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventCostSheetSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventCostSheetSerializer,
            description="Retrieve a cost sheet by ID",
            tags=["Manpower: Cost Sheets"],
        ),
        "put": doc_update(
            request=EventCostSheetSerializer,
            response=EventCostSheetSerializer,
            description="Update a cost sheet by ID",
            tags=["Manpower: Cost Sheets"],
        ),
        "delete": doc_destroy(description="Delete a cost sheet", tags=["Manpower: Cost Sheets"]),
    }
)
class EventCostSheetDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return EventCostSheet.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(EventCostSheetSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = EventCostSheetSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=MoUSerializer(many=True),
            parameters=[
                query_param("allocation", "uuid", False, "Filter by allocation ID"),
                query_param("status", "str", False, "Filter by status"),
            ],
            description="List MoUs",
            tags=["Manpower: MoUs"],
        ),
        "post": doc_create(
            request=MoUSerializer,
            response=MoUSerializer,
            description="Create an MoU",
            tags=["Manpower: MoUs"],
        ),
    }
)
class MoUList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return MoU.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            
            alloc = request.query_params.get("allocation")
            stat = request.query_params.get("status")
            
            if alloc:
                qs = qs.filter(allocation_id=alloc)
            if stat:
                qs = qs.filter(status=stat)
                
            return Response(MoUSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching MoUs", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = MoUSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=MoUSerializer,
            description="Retrieve an MoU by ID",
            tags=["Manpower: MoUs"],
        ),
        "put": doc_update(
            request=MoUSerializer,
            response=MoUSerializer,
            description="Update an MoU by ID",
            tags=["Manpower: MoUs"],
        ),
        "delete": doc_destroy(description="Delete an MoU", tags=["Manpower: MoUs"]),
    }
)
class MoUDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return MoU.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(MoUSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = MoUSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=PostEventAdjustmentSerializer(many=True),
            parameters=[
                query_param("allocation", "uuid", False, "Filter by allocation ID"),
                query_param("admin_approval_status", "str", False, "Filter by approval status"),
            ],
            description="List post-event adjustments",
            tags=["Manpower: Adjustments"],
        ),
        "post": doc_create(
            request=PostEventAdjustmentSerializer,
            response=PostEventAdjustmentSerializer,
            description="Create a post-event adjustment",
            tags=["Manpower: Adjustments"],
        ),
    }
)
class PostEventAdjustmentList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return PostEventAdjustment.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            
            alloc = request.query_params.get("allocation")
            stat = request.query_params.get("admin_approval_status")
            
            if alloc:
                qs = qs.filter(allocation_id=alloc)
            if stat:
                qs = qs.filter(admin_approval_status=stat)
                
            return Response(PostEventAdjustmentSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching adjustments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = PostEventAdjustmentSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=PostEventAdjustmentSerializer,
            description="Retrieve a post-event adjustment by ID",
            tags=["Manpower: Adjustments"],
        ),
        "put": doc_update(
            request=PostEventAdjustmentSerializer,
            response=PostEventAdjustmentSerializer,
            description="Update a post-event adjustment by ID",
            tags=["Manpower: Adjustments"],
        ),
        "delete": doc_destroy(description="Delete a post-event adjustment", tags=["Manpower: Adjustments"]),
    }
)
class PostEventAdjustmentDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return PostEventAdjustment.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(PostEventAdjustmentSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = PostEventAdjustmentSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=FreelancerRatingSerializer(many=True),
            parameters=[
                query_param("freelancer", "uuid", False, "Filter by freelancer ID"),
                query_param("event", "uuid", False, "Filter by event ID"),
                query_param("score", "int", False, "Filter by score"),
            ],
            description="List freelancer ratings",
            tags=["Manpower: Ratings"],
        ),
        "post": doc_create(
            request=FreelancerRatingSerializer,
            response=FreelancerRatingSerializer,
            description="Create a freelancer rating",
            tags=["Manpower: Ratings"],
        ),
    }
)
class FreelancerRatingList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerRating.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            
            free = request.query_params.get("freelancer")
            ev = request.query_params.get("event")
            score = request.query_params.get("score")
            
            if free:
                qs = qs.filter(freelancer_id=free)
            if ev:
                qs = qs.filter(event_id=ev)
            if score:
                qs = qs.filter(score=score)
                
            return Response(FreelancerRatingSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching ratings", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = FreelancerRatingSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": "Error creating rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=FreelancerRatingSerializer,
            description="Retrieve a freelancer rating by ID",
            tags=["Manpower: Ratings"],
        ),
        "put": doc_update(
            request=FreelancerRatingSerializer,
            response=FreelancerRatingSerializer,
            description="Update a freelancer rating by ID",
            tags=["Manpower: Ratings"],
        ),
        "delete": doc_destroy(description="Delete a freelancer rating", tags=["Manpower: Ratings"]),
    }
)
class FreelancerRatingDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerRating.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(FreelancerRatingSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = FreelancerRatingSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Exception as e:
            return Response(
                {"detail": "Error updating rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def accounts_summary(request):
    try:
        pending_payments = PostEventAdjustment.objects.filter(
            admin_approval_status="approved"
        ).select_related("allocation__freelancer", "allocation__event_department__event")

        event_totals = pending_payments.values(
            event_name=F("allocation__event_department__event__name")
        ).annotate(
            total_liability=Sum("revised_total"),
            freelancer_count=Count("id")
        )

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
    except Exception as e:
        return Response(
            {"detail": "Error fetching accounts summary", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_accounts_excel(request):
    """
    Export all approved vendor liabilities to an Excel file.
    """
    try:
        # Fetch approved adjustments
        pending_payments = PostEventAdjustment.objects.filter(
            admin_approval_status="approved"
        ).select_related(
            "allocation__freelancer",
            "allocation__event_department__event",
            "allocation__event_department__department"
        ).order_by("allocation__event_department__event__name")

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Vendor Liabilities"

        # Headers
        headers = [
            "Event Name", "Department", "Freelancer Name", 
            "Actual Days Worked", "Negotiated Rate", "Total Liability"
        ]
        ws.append(headers)
        
        # Style headers
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Data rows
        for adj in pending_payments:
            alloc = adj.allocation
            ws.append([
                alloc.event_department.event.name,
                alloc.event_department.department.name,
                alloc.freelancer.name,
                float(adj.actual_days_worked),
                float(alloc.cost_sheet.negotiated_rate),
                float(adj.revised_total)
            ])

        # Create response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="VendorLiabilities.xlsx"'
        wb.save(response)
        return response

    except Exception as e:
        return Response(
            {"detail": "Error generating Excel report", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
