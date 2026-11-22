from django.contrib import admin
from MessageTemplates.models import (
    QueuedMessage,
    MessageTemplate,
    MessageTemplateVariable,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    FlowBlueprint,
    FlowSession,
    QrTemplateConfig,
    QrTicket,
    QrScanEvent,
)


@admin.register(QueuedMessage)
class QueuedMessageAdmin(admin.ModelAdmin):
    list_display = ("registration", "sent", "created_at", "sent_at")
    list_filter = ("sent",)
    search_fields = ("registration__id",)


@admin.register(WhatsAppBusinessAccount)
class WhatsAppBusinessAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "waba_id", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "waba_id")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    
    fieldsets = (
        (None, {
            "fields": ("id", "name", "waba_id", "is_active")
        }),
        ("Token (Encrypted)", {
            "fields": ("_encrypted_token",),
            "classes": ("collapse",),
            "description": "Warning: This field contains encrypted token data. Do not modify directly."
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(WhatsAppPhoneNumber)
class WhatsAppPhoneNumberAdmin(admin.ModelAdmin):
    list_display = (
        "display_phone_number",
        "verified_name",
        "phone_number_id",
        "quality_rating",
        "messaging_limit_tier",
        "is_active",
        "is_default",
        "last_used_at",
    )
    list_filter = ("is_active", "is_default", "quality_rating", "messaging_limit_tier")
    search_fields = ("display_phone_number", "verified_name", "phone_number_id", "waba_id")
    readonly_fields = ("id", "created_at", "updated_at", "last_used_at")
    ordering = ("-is_default", "-last_used_at", "display_phone_number")
    raw_id_fields = ("business_account",)
    
    fieldsets = (
        ("Phone Number Info", {
            "fields": ("id", "display_phone_number", "verified_name", "phone_number_id")
        }),
        ("Business Account", {
            "fields": ("business_account", "waba_id", "asset_id")
        }),
        ("Status & Quality", {
            "fields": ("is_active", "is_default", "quality_rating", "messaging_limit_tier")
        }),
        ("Token (Encrypted)", {
            "fields": ("_encrypted_user_token", "token_expires_at"),
            "classes": ("collapse",),
            "description": "Warning: Token field contains encrypted data. Do not modify directly."
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "last_used_at"),
            "classes": ("collapse",),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("business_account")


admin.site.register(MessageTemplate)
admin.site.register(MessageTemplateVariable)


@admin.register(QrTemplateConfig)
class QrTemplateConfigAdmin(admin.ModelAdmin):
    list_display = ("template_name", "phone_number_id", "language", "is_qr_template", "updated_at")
    list_filter = ("is_qr_template", "language")
    search_fields = ("template_name", "phone_number_id")


@admin.register(QrTicket)
class QrTicketAdmin(admin.ModelAdmin):
    list_display = ("recipient_name", "recipient_phone", "template_name", "event", "scan_count", "message_wamid", "generated_at")
    list_filter = ("template_name",)
    search_fields = ("recipient_name", "recipient_phone", "token_digest", "message_wamid")
    readonly_fields = ("id", "token_digest", "generated_at", "last_scanned_at", "scan_count")
    raw_id_fields = ("event", "event_registration", "session_registration", "campaign", "campaign_recipient")


@admin.register(QrScanEvent)
class QrScanEventAdmin(admin.ModelAdmin):
    list_display = ("scanned_at", "action", "ticket", "event", "security_user", "error_message")
    list_filter = ("action", "scanned_at")
    search_fields = ("token_digest", "error_message")
    readonly_fields = ("id", "scanned_at")


@admin.register(FlowBlueprint)
class FlowBlueprintAdmin(admin.ModelAdmin):
    list_display = ("name", "trigger_keyword", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "trigger_keyword")


@admin.register(FlowSession)
class FlowSessionAdmin(admin.ModelAdmin):
    list_display = ("registration", "flow", "status", "current_node_id", "last_interaction")
    list_filter = ("status", "flow")
    search_fields = ("registration__id", "current_node_id")
    raw_id_fields = ("registration", "flow")

