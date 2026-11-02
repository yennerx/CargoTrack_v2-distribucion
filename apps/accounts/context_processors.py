from django.utils import timezone

from .sessions import LAST_ACTIVITY_SESSION_KEY, idle_timeout_seconds


def session_timeout(request):
    if not request.user.is_authenticated:
        return {}

    timeout_seconds = getattr(request, "session_idle_timeout_seconds", None)
    if timeout_seconds is None:
        timeout_seconds = idle_timeout_seconds()
    deadline_ms = getattr(request, "session_idle_deadline_ms", None)
    last_activity = request.session.get(LAST_ACTIVITY_SESSION_KEY)
    if deadline_ms is None and last_activity is None:
        last_activity = timezone.now().timestamp()
    if deadline_ms is None:
        try:
            deadline_ms = int((float(last_activity) + timeout_seconds) * 1000)
        except (TypeError, ValueError):
            deadline_ms = int((timezone.now().timestamp() + timeout_seconds) * 1000)
    return {
        "session_idle_timeout_seconds": timeout_seconds,
        "session_idle_deadline_ms": deadline_ms,
    }
