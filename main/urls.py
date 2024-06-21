from django.urls import path
from main.views import (
    APIKeyView,
    Home,
    TwilioWebhookView,
    UploadCustomerView,
    UserRegistrationView,
)


app_name = "main"

urlpatterns = [
    path("", Home.as_view(), name="home"),
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("get_api_key/", APIKeyView.as_view(), name="create_api"),
    path("upload/", UploadCustomerView.as_view(), name="upload_customer"),
    path("twilio_webhook/", TwilioWebhookView.as_view(), name="twilio_webhook"),
]
