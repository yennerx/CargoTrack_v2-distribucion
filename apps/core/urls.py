from django.urls import path

from .views import (
    health_check,
    home,
    module_placeholder,
    save_dashboard_preference,
    save_navigation_preference,
)

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("health/", health_check, name="health-check"),
    path("modulos/<slug:module_slug>/", module_placeholder, name="module-placeholder"),
    path("preferencias/navegacion/", save_navigation_preference, name="save-navigation-preference"),
    path("preferencias/panel/", save_dashboard_preference, name="save-dashboard-preference"),
]
