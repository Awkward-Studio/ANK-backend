from django.urls import path
from Logistics.views.hotel_views import HotelList, HotelDetail
from Logistics.views.accomodation_views import (
    AccommodationFieldDetail,
    AccommodationFieldList,
    AccommodationList,
    AccommodationDetail,
)
from Logistics.views.travel_details_views import (
    TravelDetailFieldDetail,
    TravelDetailFieldList,
    TravelDetailList,
    TravelDetailDetail,
)

urlpatterns = [
    # ─── Hotel ────────────────────────────────────────────────────────
    # GET  list,  POST create
    path("hotels/", HotelList.as_view(), name="hotel-list"),
    # GET retrieve, PUT update, DELETE destroy
    path("hotels/<uuid:pk>/", HotelDetail.as_view(), name="hotel-detail"),
    # ─── Accommodation ───────────────────────────────────────────────
    # GET  list,  POST create
    path("accommodations/", AccommodationList.as_view(), name="accommodation-list"),
    # GET retrieve, PUT update, DELETE destroy
    path(
        "accommodations/<uuid:pk>/",
        AccommodationDetail.as_view(),
        name="accommodation-detail",
    ),
    # AccommodationField
    path(
        "accommodation-fields/",
        AccommodationFieldList.as_view(),
        name="accommodationfield-list",
    ),
    path(
        "accommodation-fields/<uuid:pk>/",
        AccommodationFieldDetail.as_view(),
        name="accommodationfield-detail",
    ),
    # ─── TravelDetail ─────────────────────────────────────────────────
    # GET  list,  POST create
    path("traveldetails/", TravelDetailList.as_view(), name="traveldetail-list"),
    # GET retrieve, PUT update, DELETE destroy
    path(
        "traveldetails/<uuid:pk>/",
        TravelDetailDetail.as_view(),
        name="traveldetail-detail",
    ),
    # TravelDetailField
    path(
        "traveldetail-fields/",
        TravelDetailFieldList.as_view(),
        name="traveldetailfield-list",
    ),
    path(
        "traveldetail-fields/<uuid:pk>/",
        TravelDetailFieldDetail.as_view(),
        name="traveldetailfield-detail",
    ),
]
