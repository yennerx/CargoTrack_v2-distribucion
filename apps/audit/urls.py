from django.urls import path

from . import views

app_name = "audit"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("ordenes/<int:order_pk>/", views.order_history, name="order_history"),
]
