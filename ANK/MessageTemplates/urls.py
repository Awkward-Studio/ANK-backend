from django.urls import path
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
]
