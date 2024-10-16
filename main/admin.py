# admin.py
import logging
import secrets
from django import forms
from django.urls import path, reverse
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from main.forms import CustomerAdminForm
from main.models import Customer, Feedback, APIKey, MessageFormat, MessageStatus, NylasWebhook
from main.utils import message_manager, nylas_client
from main.manager import nylas_grant

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
        "updated_at",
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
        form = super().get_form(request, obj, **kwargs)
        form.current_user = request.user
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if obj.message_format and obj.message_format.business:
                obj.message_format.business = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == "message_format":
            kwargs["queryset"] = MessageFormat.objects.filter(
                business=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return self.list_filter + ("message_format__business__username",)
        return super().get_list_filter(request)

    # Custom URLs for the new tabs
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('get-email-threads/', self.admin_site.admin_view(
                self.get_email_threads), name='get-email-threads'),
            path('analyze-email-thread/', self.admin_site.admin_view(
                self.analyze_email_thread), name='analyze-email-thread'),
            path('schedule-meeting/', self.admin_site.admin_view(
                self.schedule_meeting), name='schedule-meeting'),
        ]
        return custom_urls + urls

    # Inject buttons into the change view
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_tabs'] = [
            {
                'name': 'Get Email Threads',
                'url': reverse('admin:get-email-threads'),
            },
            {
                'name': 'Analyze Email Thread',
                'url': reverse('admin:analyze-email-thread'),
            },
            {
                'name': 'Schedule Meeting',
                'url': reverse('admin:schedule-meeting'),
            },
        ]
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    # Render buttons in the list view
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_tabs'] = [
            {
                'name': 'Get Email Threads',
                'url': reverse('admin:get-email-threads'),
            },
            {
                'name': 'Analyze Email Thread',
                'url': reverse('admin:analyze-email-thread'),
            },
            {
                'name': 'Schedule Meeting',
                'url': reverse('admin:schedule-meeting'),
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)

    def get_email_threads(self, request):
        threads = nylas_client.threads.list(nylas_grant)
        data = []
        for thread in threads:
            if hasattr(thread[0], 'subject') and hasattr(thread[0], 'id'):
                data.append({
                    "id": thread[0].id,
                    "subject": thread[0].subject
                })

        context = {
            'threads': data,
            'opts': self.model._meta,
        }
        return render(request, 'admin/email_threads.html', context)

    def analyze_email_thread(self, request):
        if request.method == 'POST':
            form = EmailThreadForm(request.POST)
            if form.is_valid():
                thread_id = form.cleaned_data['thread_id']
                summary = message_manager.analyze_email_thread(
                    thread_id)
                context = {
                    'summary': summary,
                    'opts': self.model._meta,
                }
                return render(request, 'admin/email_thread_analysis.html', context)
        else:
            form = EmailThreadForm()

        context = {
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/analyze_email_thread_form.html', context)

    def schedule_meeting(self, request):
        if request.method == 'POST':
            form = ScheduleMeetingForm(request.POST)
            if form.is_valid():
                customer = form.cleaned_data['customer']
                suggested_time = form.cleaned_data['suggested_time']
                title = form.cleaned_data['title'] or "Review Meeting"
                message_manager.schedule_meeting(
                    customer, suggested_time, title)
                self.message_user(
                    request, "Meeting scheduled successfully")
                return HttpResponseRedirect("../")
        else:
            form = ScheduleMeetingForm()

        context = {
            'form': form,
        }

        # Add opts to context only if self.model is not None
        if hasattr(self, 'model') and self.model is not None:
            context['opts'] = self.model._meta
        else:
            # Fallback for when self.model is None
            from django.apps import apps
            context['opts'] = apps.get_model('main', 'Customer')._meta

        return render(request, 'admin/schedule_meeting_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_tabs'] = [
            {
                'name': 'Get Email Threads',
                'url': reverse('admin:get-email-threads'),
            },
            {
                'name': 'Analyze Email Thread',
                'url': reverse('admin:analyze-email-thread'),
            },
            {
                'name': 'Schedule Meeting',
                'url': reverse('admin:schedule-meeting'),
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("customer", "message", "source",
                    "sentiment", "created_at")
    search_fields = ("customer__first_name",
                     "customer__last_name", "message")
    readonly_fields = ("sentiment", "created_at")
    list_filter = ("sentiment", "source")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(customer__message_format__business=request.user)


@admin.register(MessageFormat)
class MessageFormatAdmin(admin.ModelAdmin):
    list_display = ("message", "business", "created_at")
    search_fields = ("message", "business__username")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(business=request.user)


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(customer__message_format__business=request.user)


@admin.register(NylasWebhook)
class NylasWebhookAdmin(admin.ModelAdmin):
    list_display = ("webhook_id", "secret_key",
                    "trigger_type", "created_at")
    list_filter = ("trigger_type",)
    search_fields = (
        "trigger_type",
        "webhook_id",
        "secret_key",
    )


class EmailThreadForm(forms.Form):
    thread_id = forms.CharField(label="Thread ID")


class ScheduleMeetingForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        label="Customer",
        widget=admin.widgets.AutocompleteSelect(
            Customer._meta.get_field('id'),
            admin.site,
            attrs={'data-placeholder': 'Search for a customer...'}
        )
    )
    suggested_time = forms.DateTimeField(
        label="Suggested Time",
        widget=admin.widgets.AdminDateWidget()
    )
    title = forms.CharField(label="Meeting Title", required=False)
