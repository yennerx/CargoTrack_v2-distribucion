from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AuditEvent


def request_metadata(request):
    if request is None:
        return {}
    return {
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
    }


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user,
        action="login",
        entity_type="authentication",
        metadata={},
        **request_metadata(request),
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user,
        action="logout",
        entity_type="authentication",
        metadata={},
        **request_metadata(request),
    )


@receiver(user_login_failed)
def audit_login_failed(sender, request, credentials, **kwargs):
    AuditEvent.objects.create(
        action="login_failed",
        entity_type="authentication",
        metadata={},
        **request_metadata(request),
    )
