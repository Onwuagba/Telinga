"""
URL configuration for telinga project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import path, include

from main.views import AdminRegistrationView, CustomAdminLoginView

admin.site.site_header = "Telinga Admin Site"
admin.site.site_title = "Telinga Admin Portal"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path('admin/register/', AdminRegistrationView.as_view(),
         name='admin_register'),
    path('admin/login/', CustomAdminLoginView.as_view(),
         name='login'),
    path("admin/", admin.site.urls),
    path("api/", include("main.urls")),
    path("", RedirectView.as_view(url='/admin/', permanent=True)),
]
