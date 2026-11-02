from django.contrib.auth import views as auth_views

from apps.audit.models import AuditEvent


class AuditedPasswordChangeView(auth_views.PasswordChangeView):
    def form_valid(self, form):
        response = super().form_valid(form)
        AuditEvent.objects.create(
            actor=self.request.user,
            action="change_password",
            entity_type="user",
            entity_id=str(self.request.user.pk),
            metadata={},
        )
        return response


class AuditedPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    def form_valid(self, form):
        reset_user = form.user
        response = super().form_valid(form)
        AuditEvent.objects.create(
            actor=None,
            action="reset_password",
            entity_type="user",
            entity_id=str(reset_user.pk),
            metadata={},
        )
        return response
