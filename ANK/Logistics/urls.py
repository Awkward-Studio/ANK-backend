from django.urls import path
from Logistics.views.hotel_views import HotelList, HotelDetail
from Logistics.views.accomodation_views import AccommodationList, AccommodationDetail
from Logistics.views.travel_details_views import TravelDetailList, TravelDetailDetail

urlpatterns = [
    # Hotels
    path("hotels/", HotelList.as_view(), name="hotel-list"),  # GET list
    path("hotels/create/", HotelList.as_view(), name="hotel-create"),  # POST create
    path(
        "hotels/<uuid:pk>/", HotelDetail.as_view(), name="hotel-detail"
    ),  # GET retrieve
    path(
        "hotels/<uuid:pk>/update/", HotelDetail.as_view(), name="hotel-update"
    ),  # PUT update
    path(
        "hotels/<uuid:pk>/delete/", HotelDetail.as_view(), name="hotel-delete"
    ),  # DELETE delete
    # Accommodations
    path(
        "accommodations/", AccommodationList.as_view(), name="accommodation-list"
    ),  # GET list
    path(
        "accommodations/create/",
        AccommodationList.as_view(),
        name="accommodation-create",
    ),  # POST create
    path(
        "accommodations/<uuid:pk>/",
        AccommodationDetail.as_view(),
        name="accommodation-detail",
    ),  # GET retrieve
    path(
        "accommodations/<uuid:pk>/update/",
        AccommodationDetail.as_view(),
        name="accommodation-update",
    ),  # PUT update
    path(
        "accommodations/<uuid:pk>/delete/",
        AccommodationDetail.as_view(),
        name="accommodation-delete",
    ),  # DELETE delete
    # Travel Details
    path(
        "traveldetails/", TravelDetailList.as_view(), name="traveldetail-list"
    ),  # GET list
    path(
        "traveldetails/create/", TravelDetailList.as_view(), name="traveldetail-create"
    ),  # POST create
    path(
        "traveldetails/<uuid:pk>/",
        TravelDetailDetail.as_view(),
        name="traveldetail-detail",
    ),  # GET retrieve
    path(
        "traveldetails/<uuid:pk>/update/",
        TravelDetailDetail.as_view(),
        name="traveldetail-update",
    ),  # PUT update
    path(
        "traveldetails/<uuid:pk>/delete/",
        TravelDetailDetail.as_view(),
        name="traveldetail-delete",
    ),  # DELETE delete
]
