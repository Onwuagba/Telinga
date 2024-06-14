from django.urls import path
from main.views import Home


app_name = "main"

urlpatterns = [
    path("", Home.as_view(), name="home"),
]
