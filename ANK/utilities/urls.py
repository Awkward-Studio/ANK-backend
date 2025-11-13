from django.urls import path
from utilities.views.tax_slab_views import TaxSlabList, TaxSlabDetail

urlpatterns = [
    path("taxslabs/", TaxSlabList.as_view(), name="taxslab-list"),
    path("taxslabs/<uuid:pk>/", TaxSlabDetail.as_view(), name="taxslab-detail"),
]
