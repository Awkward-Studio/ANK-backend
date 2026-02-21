from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FreelancerViewSet,
    ManpowerRequirementViewSet,
    FreelancerAllocationViewSet,
    EventCostSheetViewSet,
    MoUViewSet,
    PostEventAdjustmentViewSet,
    FreelancerRatingViewSet,
    accounts_summary,
)
from .public_views import get_mou_by_token, respond_to_mou

router = DefaultRouter()
router.register(r"freelancers", FreelancerViewSet, basename="freelancer")
router.register(r"requirements", ManpowerRequirementViewSet, basename="requirement")
router.register(r"allocations", FreelancerAllocationViewSet, basename="allocation")
router.register(r"cost-sheets", EventCostSheetViewSet, basename="cost-sheet")
router.register(r"mous", MoUViewSet, basename="mou")
router.register(r"adjustments", PostEventAdjustmentViewSet, basename="adjustment")
router.register(r"ratings", FreelancerRatingViewSet, basename="rating")

urlpatterns = [
    # Router-based viewsets
    path("", include(router.urls)),
    
    # Accounts Dashboard
    path("accounts/summary/", accounts_summary, name="accounts-summary"),
    
    # Public token-based endpoints for freelancers
    path("public/mou/<uuid:token>/", get_mou_by_token, name="public-mou-detail"),
    path("public/mou/<uuid:token>/respond/", respond_to_mou, name="public-mou-respond"),
]
