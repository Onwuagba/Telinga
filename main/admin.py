# admin.py
import logging
import secrets
from django.contrib import admin
from .models import APIKey

logger = logging.getLogger("main")


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "key", "created_at")
    readonly_fields = ("key", "created_at")

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.key = self.generate_key()
        super().save_model(request, obj, form, change)
        action = "Updated" if change else "Created"
        logger.info(f"API Key {action}: {obj.user} by {request.user}")

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        logger.info(f"API Key Deleted: {obj.user} by {request.user}")

    def generate_key(self):
        return secrets.token_urlsafe(40)
