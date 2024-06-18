# admin.py
import logging
import secrets
from django.contrib import admin
from main.models import Customer, Feedback, APIKey, MessageFormat, MessageStatus

logger = logging.getLogger("app")


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("business", "key", "created_at")
    readonly_fields = ("key", "created_at")

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.key = self.generate_key()
        super().save_model(request, obj, form, change)
        action = "Updated" if change else "Created"
        logger.info(f"API Key {action}: {obj.business} by {request.user}")

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        logger.info(f"API Key Deleted: {obj.business} by {request.user}")

    def generate_key(self):
        return secrets.token_urlsafe(40)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "phone_number",
        "email",
        "first_name",
        "last_name",
        "message_format",
        "delivery_status",
        "date_uploaded",
    )
    search_fields = (
        "phone_number",
        "email",
        "first_name",
        "last_name",
        "message_format__business__username",
    )
    list_filter = ("message_format__business__username", "message_status__status")

    def delivery_status(self, obj):
        return obj.message_status.status if hasattr(obj, "message_status") else None


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("customer", "message", "sentiment", "created_at")
    search_fields = ("customer__first_name", "customer__last_name", "message")
    readonly_fields = ("sentiment", "created_at")
    list_filter = ("sentiment",)


@admin.register(MessageFormat)
class MessageFormatAdmin(admin.ModelAdmin):
    list_display = ("message", "business", "created_at")
    search_fields = ("message", "business__username")


@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ("customer", "message_sid", "status", "date_created", "date_updated")
    list_filter = ("status", "date_created", "date_updated")
    search_fields = (
        "customer__email",
        "customer__first_name",
        "customer__phone_number",
    )
