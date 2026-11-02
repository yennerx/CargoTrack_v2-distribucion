from django.urls import path

from . import views

app_name = "incidents"

urlpatterns = [
    path("", views.incident_list, name="list"),
    path("orden/<int:order_pk>/nueva/", views.incident_create, name="create"),
    path("<int:pk>/", views.incident_detail, name="detail"),
    path("<int:pk>/estado/", views.incident_transition, name="transition"),
    path("<int:pk>/evidencia/", views.incident_document_upload, name="upload_document"),
]
