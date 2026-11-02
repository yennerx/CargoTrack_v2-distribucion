from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("<slug:report_type>/", views.report_detail, name="detail"),
]
