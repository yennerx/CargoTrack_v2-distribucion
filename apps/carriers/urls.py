from django.urls import path

from . import views

app_name = "carriers"

urlpatterns = [
    path("", views.carrier_list, name="list"),
    path("nuevo/", views.carrier_create, name="create"),
    path("<int:pk>/", views.carrier_detail, name="detail"),
    path("<int:pk>/editar/", views.carrier_update, name="update"),
    path("<int:pk>/validar/", views.carrier_validate, name="validate"),
    path("<int:pk>/desactivar/", views.carrier_deactivate, name="deactivate"),
]
