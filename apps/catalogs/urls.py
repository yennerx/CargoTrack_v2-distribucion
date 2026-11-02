from django.urls import path

from .views import dashboard

app_name = "catalogs"

urlpatterns = [
    path("", dashboard, name="dashboard"),
]
