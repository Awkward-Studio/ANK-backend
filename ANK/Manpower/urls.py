from django.urls import path
from .views import (
    FreelancerList,
    FreelancerDetail,
    ManpowerRequirementList,
    ManpowerRequirementDetail,
    FreelancerAllocationList,
    FreelancerAllocationDetail,
    confirm_allocation,
    release_allocation,
    generate_mou,
    EventCostSheetList,
    EventCostSheetDetail,
    MoUList,
    MoUDetail,
    PostEventAdjustmentList,
    PostEventAdjustmentDetail,
    FreelancerRatingList,
    FreelancerRatingDetail,
    accounts_summary,
    export_accounts_excel,
)
from .public_views import public_mou_interaction

urlpatterns = [
    # Freelancers
    path("freelancers/", FreelancerList.as_view(), name="freelancer-list"),
    path("freelancers/<uuid:pk>/", FreelancerDetail.as_view(), name="freelancer-detail"),
    
    # Requirements
    path("requirements/", ManpowerRequirementList.as_view(), name="requirement-list"),
    path("requirements/<uuid:pk>/", ManpowerRequirementDetail.as_view(), name="requirement-detail"),
    
    # Allocations
    path("allocations/", FreelancerAllocationList.as_view(), name="allocation-list"),
    path("allocations/<uuid:pk>/", FreelancerAllocationDetail.as_view(), name="allocation-detail"),
    path("allocations/<uuid:pk>/confirm/", confirm_allocation, name="allocation-confirm"),
    path("allocations/<uuid:pk>/release/", release_allocation, name="allocation-release"),
    path("allocations/<uuid:pk>/generate-mou/", generate_mou, name="allocation-generate-mou"),
    
    # Cost Sheets
    path("cost-sheets/", EventCostSheetList.as_view(), name="cost-sheet-list"),
    path("cost-sheets/<uuid:pk>/", EventCostSheetDetail.as_view(), name="cost-sheet-detail"),
    
    # MoUs
    path("mous/", MoUList.as_view(), name="mou-list"),
    path("mous/<uuid:pk>/", MoUDetail.as_view(), name="mou-detail"),
    
    # Adjustments
    path("adjustments/", PostEventAdjustmentList.as_view(), name="adjustment-list"),
    path("adjustments/<uuid:pk>/", PostEventAdjustmentDetail.as_view(), name="adjustment-detail"),
    
    # Ratings
    path("ratings/", FreelancerRatingList.as_view(), name="rating-list"),
    path("ratings/<uuid:pk>/", FreelancerRatingDetail.as_view(), name="rating-detail"),
    
    # Accounts Dashboard
    path("accounts/summary/", accounts_summary, name="accounts-summary"),
    path("accounts/export/", export_accounts_excel, name="accounts-export"),
    
    # Public token-based endpoints for freelancers
    path("public/mou/<uuid:token>/", public_mou_interaction, name="public-mou-interaction"),
]
