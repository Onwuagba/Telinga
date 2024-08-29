# admin.py
import logging
import secrets
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from main.models import Customer, Feedback, APIKey, MessageFormat, MessageStatus, NylasWebhook
from main.forms import CustomerAdminForm

logger = logging.getLogger("app")
UserModel = get_user_model()


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("business", "key", "created_at", "updated_at")
    readonly_fields = ("key", "created_at")

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.key = self.generate_key()
        super().save_model(request, obj, form, change)
        action = "Updated" if change else "Created"
        self.log_action(
            obj, f"API Key {action}: {obj.business} by {request.user}")

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self.log_action(
            obj, f"API Key Deleted: {obj.business} by {request.user}")

    def generate_key(self):
        return secrets.token_urlsafe(40)

    def has_add_permission(self, request):
        return True if request.user.is_superuser else False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == "business":
            kwargs["queryset"] = UserModel.objects.filter(
                username=request.user.username
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(business=request.user)
        return qs

    def log_action(self, obj, message):
        logger.info(message)

    def change_api_key(self, request, queryset):
        for api_key in queryset:
            api_key.key = self.generate_key()
            api_key.save()
            self.log_action(
                api_key, f"API Key Changed: {api_key.business} by {request.user}"
            )
        self.message_user(
            request, _(
                "API keys successfully changed for selected items.")
        )

    change_api_key.short_description = _("Change API Key")

    actions = [change_api_key]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm

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
    list_filter = ("message_status__status",)

    def delivery_status(self, obj):
        return obj.message_status.status if hasattr(obj, "message_status") else None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(message_format__business=request.user)

    def get_form(self, request, obj=None, **kwargs):
        form = super(CustomerAdmin, self).get_form(
            request, obj, **kwargs)
        form.current_user = request.user
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if obj.message_format and obj.message_format.business:
                obj.message_format.business = request.user
        super(CustomerAdmin, self).save_model(
            request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == "message_format":
            kwargs["queryset"] = MessageFormat.objects.filter(
                business=request.user)
        return super(CustomerAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return self.list_filter + ("message_format__business__username",)
        return super().get_list_filter(request)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("customer", "message", "source",
                    "sentiment", "created_at")
    search_fields = ("customer__first_name",
                     "customer__last_name", "message")
    readonly_fields = ("sentiment", "created_at")
    list_filter = ("sentiment", "source")


@admin.register(MessageFormat)
class MessageFormatAdmin(admin.ModelAdmin):
    list_display = ("message", "business", "created_at")
    search_fields = ("message", "business__username")


@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ("customer", "message_sid", "status",
                    "date_created", "date_updated")
    list_filter = ("status", "date_created", "date_updated")
    search_fields = (
        "customer__email",
        "customer__first_name",
        "customer__phone_number",
    )


@admin.register(NylasWebhook)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ("webhook_id", "secret_key",
                    "trigger_type", "created_at")
    list_filter = ("trigger_type",)
    search_fields = (
        "trigger_type",
        "webhook_id",
        "secret_key",
    )
