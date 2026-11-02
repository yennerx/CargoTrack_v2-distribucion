from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import models


class UserPermissionAssignment(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="permission_assignment"
    )
    permissions = models.ManyToManyField(Permission, blank=True, related_name="user_assignments")
    updated_at = models.DateTimeField(auto_now=True)

    def sync_user_permissions(self):
        self.user.user_permissions.set(self.permissions.all())
        self.user.__dict__.pop("_perm_cache", None)
        self.user.__dict__.pop("_user_perm_cache", None)

    def __str__(self):
        return f"Permisos de {self.user.get_username()}"
