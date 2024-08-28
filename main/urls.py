from django.urls import path
from main.views import (
    APIKeyView,
    AnalyzeEmailThreadView,
    ChangeAPIKeyView,
    GetEmailThreadsView,
    Home,
    ScheduleMeetingView,
    TwilioWebhookView,
    UpdatePasswordView,
    UploadCustomerView,
    UserRegistrationView,
)


app_name = "main"

urlpatterns = [
    path("", Home.as_view(), name="home"),
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("get_api_key/", APIKeyView.as_view(), name="create_api"),
    path("change_api_key/", ChangeAPIKeyView.as_view(),
         name="change_api_key"),
    path("update-password/", UpdatePasswordView.as_view(),
         name="update-password"),
    path("upload/", UploadCustomerView.as_view(), name="upload_customer"),
    path("twilio_webhook/", TwilioWebhookView.as_view(),
         name="twilio_webhook"),
    path('email-threads/', GetEmailThreadsView.as_view(),
         name='get_email_threads'),
    path('analyze-email-thread/', AnalyzeEmailThreadView.as_view(),
         name='analyze_email_thread'),
    path('schedule-meeting/', ScheduleMeetingView.as_view(),
         name='schedule_meeting'),

]
