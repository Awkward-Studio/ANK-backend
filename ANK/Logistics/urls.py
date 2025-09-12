from django.urls import path
from Logistics.views.hotel_views import (
    BulkRoomAvailabilityAPIView,
    EventHotelDetail,
    EventHotelList,
    EventHotelRoomTypeDetail,
    EventHotelRoomTypeList,
    EventHotelsByEventAPIView,
    HotelList,
    HotelDetail,
    HotelRoomTypeDetail,
    HotelRoomTypeList,
    RoomTypeAvailabilityAPIView,
    RoomTypesByEventAPIView,
    RoomTypesByEventHotelAPIView,
)
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
    path("hotels/", HotelList.as_view(), name="hotel-list"),
    path("hotels/<uuid:pk>/", HotelDetail.as_view(), name="hotel-detail"),
    # EventHotel
    path("event-hotels/", EventHotelList.as_view(), name="eventhotel-list"),
    path(
        "event-hotels/<uuid:pk>/", EventHotelDetail.as_view(), name="eventhotel-detail"
    ),
    # EventHotelRoomType
    path(
        "event-hotel-room-types/",
        EventHotelRoomTypeList.as_view(),
        name="eventhotelroomtype-list",
    ),
    path(
        "event-hotel-room-types/<uuid:pk>/",
        EventHotelRoomTypeDetail.as_view(),
        name="eventhotelroomtype-detail",
    ),
    path(
        "event-hotels/by-event/",
        EventHotelsByEventAPIView.as_view(),
        name="event-hotels-by-event",
    ),
    path(
        "event-hotel-room-types/by-event-hotel/",
        RoomTypesByEventHotelAPIView.as_view(),
        name="room-types-by-event-hotel",
    ),
    path(
        "event-hotel-room-types/by-event/",
        RoomTypesByEventAPIView.as_view(),
        name="ehrtypes-by-event",
    ),
    path(
        "event-hotel-room-types/<uuid:event_hotel_id>/<str:room_type>/availability/",
        RoomTypeAvailabilityAPIView.as_view(),
        name="room-type-availability",
    ),
    path(
        "event-hotel-room-types/bulk-update-availability/",
        BulkRoomAvailabilityAPIView.as_view(),
        name="bulk-room-availability",
    ),
    path("hotel-room-types/", HotelRoomTypeList.as_view(), name="hotelroomtype-list"),
    path(
        "hotel-room-types/<uuid:pk>/",
        HotelRoomTypeDetail.as_view(),
        name="hotelroomtype-detail",
    ),
    # ─── Accommodation ───────────────────────────────────────────────
    path("accommodations/", AccommodationList.as_view(), name="accommodation-list"),
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
    path("traveldetails/", TravelDetailList.as_view(), name="traveldetail-list"),
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
