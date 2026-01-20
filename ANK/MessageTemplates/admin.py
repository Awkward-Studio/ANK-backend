from django.contrib import admin
from MessageTemplates.models import (
    QueuedMessage,
    MessageTemplate,
    MessageTemplateVariable,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
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
