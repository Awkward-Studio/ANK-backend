from django.urls import path
from MessageTemplates.whatsapp_views.flush_message import FlushQueuedMessagesView
from MessageTemplates.whatsapp_views.send_template import SendLocalTemplateView
from MessageTemplates.whatsapp_views.phone_number_management import (
    StorePhoneNumberView,
    ListPhoneNumbersView,
    PhoneNumberDetailView,
)
from MessageTemplates.views import (
    EventMessageTemplatesAPIView,
    MessageTemplateList,
    MessageTemplateDetail,
    MessageTemplateVariableList,
    MessageTemplateVariableDetail,
)

urlpatterns = [
    # Message Templates
    path(
        "message-templates/", MessageTemplateList.as_view(), name="messagetemplate-list"
    ),
    path(
        "message-templates/<uuid:pk>/",
        MessageTemplateDetail.as_view(),
        name="messagetemplate-detail",
    ),
    # Message Template Variables
    path(
        "message-template-variables/",
        MessageTemplateVariableList.as_view(),
        name="messagetemplatevariable-list",
    ),
    path(
        "message-template-variables/<uuid:pk>/",
        MessageTemplateVariableDetail.as_view(),
        name="messagetemplatevariable-detail",
    ),
    path(
        "message-templates/event/<uuid:event_pk>/",
        EventMessageTemplatesAPIView.as_view(),
        name="event-message-templates",
    ),
    path(
        "message-templates/events/<uuid:event_id>/registrations/<uuid:registration_id>/send-template/",
        SendLocalTemplateView.as_view(),
        name="mt-send-template",
    ),
    path(
        "message-templates/flush-after-resume/",
        FlushQueuedMessagesView.as_view(),
        name="mt-flush-after-resume",
    ),
    # WhatsApp Phone Number Management
    path(
        "whatsapp/phone-numbers/store/",
        StorePhoneNumberView.as_view(),
        name="whatsapp-store-phone-number",
    ),
    path(
        "whatsapp/phone-numbers/",
        ListPhoneNumbersView.as_view(),
        name="whatsapp-list-phone-numbers",
    ),
    path(
        "whatsapp/phone-numbers/<str:phone_number_id>/",
        PhoneNumberDetailView.as_view(),
        name="whatsapp-phone-number-detail",
    ),
]

# ViewSets
from rest_framework.routers import DefaultRouter
from MessageTemplates.whatsapp_views.campaign_views import BroadcastCampaignViewSet

router = DefaultRouter()
router.register(r'whatsapp/campaigns', BroadcastCampaignViewSet, basename='whatsapp-campaigns')

urlpatterns += router.urls
