from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .sessions import idle_timeout_seconds
from .views import AuditedPasswordChangeView, AuditedPasswordResetConfirmView

app_name = "accounts"


@require_POST
def activity(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False}, status=401)
    timeout_seconds = idle_timeout_seconds()
    last_activity = request.session["cargotrack_last_user_activity"]
    return JsonResponse(
        {
            "authenticated": True,
            "timeout_seconds": timeout_seconds,
            "deadline_ms": int((last_activity + timeout_seconds) * 1000),
        }
    )

urlpatterns = [
    path("activity/", activity, name="activity"),
    path(
        "login/",
        never_cache(
            auth_views.LoginView.as_view(
                template_name="accounts/login.html",
                redirect_authenticated_user=True,
            )
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "password-change/",
        AuditedPasswordChangeView.as_view(
            template_name="accounts/password_change_form.html",
            success_url="/accounts/password-change/done/",
        ),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url="/accounts/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        AuditedPasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/accounts/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
