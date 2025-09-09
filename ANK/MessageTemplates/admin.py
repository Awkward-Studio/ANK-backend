from django.contrib import admin
from MessageTemplates.models import QueuedMessage


@admin.register(QueuedMessage)
class QueuedMessageAdmin(admin.ModelAdmin):
    list_display = ("registration", "sent", "created_at", "sent_at")
    list_filter = ("sent",)
    search_fields = ("registration__id",)
