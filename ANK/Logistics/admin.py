from django.contrib import admin
from Logistics.models.travel_detail_capture_session import TravelCaptureSession
from Logistics.models.travel_details_models import TravelDetail, TravelDetailField


admin.site.register(TravelCaptureSession)
admin.site.register(TravelDetail)
admin.site.register(TravelDetailField)
