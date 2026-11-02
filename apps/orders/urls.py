from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("nuevo/", views.order_create, name="create"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/editar/", views.order_update, name="update"),
    path("<int:pk>/confirmar-transportista/", views.order_confirm_carrier, name="confirm_carrier"),
    path("<int:pk>/estado/", views.order_change_status, name="change_status"),
]
