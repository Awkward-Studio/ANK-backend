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
    lock_event_manpower,
    unlock_event_manpower,
    event_lock_status,
    InvoiceWorkflowList,
    InvoiceWorkflowDetail,
    invoice_transition,
    issue_adjustment_secure_link,
    public_adjustment_interaction,
    ManpowerAuditLogList,
    ManpowerSettingsDetail,
)
from .public_views import public_mou_interaction, public_mou_pdf_download

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
    path("allocations/<uuid:pk>/bulk-update-meals/", FreelancerAllocationDetail.as_view(), name="allocation-bulk-update-meals"),
    path("allocations/<uuid:pk>/toggle-work-day/", FreelancerAllocationDetail.as_view(), name="allocation-toggle-work-day"),
    path("allocations/<uuid:pk>/update-meal/", FreelancerAllocationDetail.as_view(), name="allocation-update-meal"),
    
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

    # Event lock controls
    path("events/<uuid:event_id>/lock/", lock_event_manpower, name="manpower-event-lock"),
    path("events/<uuid:event_id>/unlock/", unlock_event_manpower, name="manpower-event-unlock"),
    path("events/<uuid:event_id>/lock-status/", event_lock_status, name="manpower-event-lock-status"),

    # Invoices
    path("invoices/", InvoiceWorkflowList.as_view(), name="invoice-list"),
    path("invoices/<uuid:pk>/", InvoiceWorkflowDetail.as_view(), name="invoice-detail"),
    path("invoices/<uuid:pk>/status/", invoice_transition, name="invoice-transition"),

    # Adjustment secure links
    path("allocations/<uuid:allocation_id>/issue-adjustment-link/", issue_adjustment_secure_link, name="allocation-issue-adjustment-link"),
    path("public/adjustment/<uuid:token>/", public_adjustment_interaction, name="public-adjustment-interaction"),

    # Audit logs
    path("audit-logs/", ManpowerAuditLogList.as_view(), name="manpower-audit-logs"),
    
    # Settings
    path("settings/", ManpowerSettingsDetail.as_view(), name="manpower-settings"),
    
    # Public token-based endpoints for freelancers
    path("public/mou/<uuid:token>/", public_mou_interaction, name="public-mou-interaction"),
    path("public/mou/<uuid:token>/pdf/", public_mou_pdf_download, name="public-mou-pdf-download"),
]
