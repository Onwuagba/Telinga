from django.urls import path
from main.views import Home, UploadCustomerView


app_name = "main"

urlpatterns = [
    path("", Home.as_view(), name="home"),
    path("upload/", UploadCustomerView.as_view(), name="upload_customer"),
]
