from django.urls import path
from utilities.views.tax_slab_views import TaxSlabList, TaxSlabDetail
from utilities.views.vendor_views import VendorList, VendorDetail

urlpatterns = [
    path("taxslabs/", TaxSlabList.as_view(), name="taxslab-list"),
    path("taxslabs/<uuid:pk>/", TaxSlabDetail.as_view(), name="taxslab-detail"),
    path("vendors/", VendorList.as_view(), name="vendor-list"),
    path("vendors/<uuid:pk>/", VendorDetail.as_view(), name="vendor-detail"),
]
