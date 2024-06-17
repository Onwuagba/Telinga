from django.urls import path
from main.views import Home, TwilioWebhookView, UploadCustomerView


app_name = "main"

urlpatterns = [
    path("", Home.as_view(), name="home"),
    path("upload/", UploadCustomerView.as_view(), name="upload_customer"),
    path("twilio_webhook/", TwilioWebhookView.as_view(), name="twilio_webhook"),
]
