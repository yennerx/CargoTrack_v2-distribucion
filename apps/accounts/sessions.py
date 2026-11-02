from apps.catalogs.models import SystemConfiguration

IDLE_TIMEOUT_CONFIGURATION_KEY = "session-idle-timeout-minutes"
DEFAULT_IDLE_TIMEOUT_MINUTES = 5
MIN_IDLE_TIMEOUT_MINUTES = 1
MAX_IDLE_TIMEOUT_MINUTES = 1440
LAST_ACTIVITY_SESSION_KEY = "cargotrack_last_user_activity"


def idle_timeout_minutes():
    configured = SystemConfiguration.objects.filter(
        key=IDLE_TIMEOUT_CONFIGURATION_KEY, is_active=True
    ).values_list("value", flat=True).first()
    try:
        minutes = int(configured) if configured else DEFAULT_IDLE_TIMEOUT_MINUTES
    except (TypeError, ValueError):
        return DEFAULT_IDLE_TIMEOUT_MINUTES
    if not MIN_IDLE_TIMEOUT_MINUTES <= minutes <= MAX_IDLE_TIMEOUT_MINUTES:
        return DEFAULT_IDLE_TIMEOUT_MINUTES
    return minutes


def idle_timeout_seconds():
    return idle_timeout_minutes() * 60
