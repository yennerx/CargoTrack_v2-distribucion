import time
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import logout

from apps.audit.models import AuditEvent

from .sessions import LAST_ACTIVITY_SESSION_KEY, idle_timeout_seconds


class IdleSessionTimeoutMiddleware:
    """Expires authenticated sessions after configured user inactivity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            timeout_seconds = idle_timeout_seconds()
            request.session_idle_timeout_seconds = timeout_seconds
            current_time = time.time()
            last_activity = request.session.get(LAST_ACTIVITY_SESSION_KEY)
            if last_activity is not None:
                try:
                    expired = current_time - float(last_activity) >= timeout_seconds
                except (TypeError, ValueError):
                    expired = True
                if expired:
                    self._expire_session(request, user, timeout_seconds)
                elif not is_non_user_activity(request):
                    self._record_activity(request, current_time)
            else:
                self._record_activity(request, current_time)
            request.session_idle_deadline_ms = int(
                (float(request.session.get(LAST_ACTIVITY_SESSION_KEY, current_time))
                 + timeout_seconds)
                * 1000
            )

        return self.get_response(request)

    @staticmethod
    def _record_activity(request, current_time):
        request.session[LAST_ACTIVITY_SESSION_KEY] = current_time

    @staticmethod
    def _expire_session(request, user, timeout_seconds):
        actor_id = user.pk
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        logout(request)
        AuditEvent.objects.create(
            actor_id=actor_id,
            action="session_idle_timeout",
            entity_type="authentication",
            metadata={"timeout_seconds": timeout_seconds},
            ip_address=ip_address,
            user_agent=user_agent,
        )


def is_non_user_activity(request):
    if request.headers.get("X-CargoTrack-Automated") == "true":
        return True
    static_path = urlsplit(settings.STATIC_URL).path.strip("/")
    static_prefix = f"/{static_path}/" if static_path else ""
    return bool(static_prefix and request.path_info.startswith(static_prefix))
