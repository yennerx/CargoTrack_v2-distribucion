from django.conf import settings
from django.db import models


class UserNavigationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="navigation_preference",
    )
    collapsed_sections = models.JSONField(default=list, blank=True)
    sidebar_collapsed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferencias de navegación de {self.user}"


class UserDashboardPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_preference",
    )
    widget_order = models.JSONField(default=list, blank=True)
    visible_widgets = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferencias del panel de {self.user}"
