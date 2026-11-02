from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent

from .models import IncidentHistory, IncidentStatus

ALLOWED_TRANSITIONS = {
    IncidentStatus.OPEN: {IncidentStatus.IN_PROGRESS, IncidentStatus.RESOLVED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.OPEN, IncidentStatus.RESOLVED},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED, IncidentStatus.REOPENED},
    IncidentStatus.CLOSED: {IncidentStatus.REOPENED},
    IncidentStatus.REOPENED: {IncidentStatus.IN_PROGRESS, IncidentStatus.RESOLVED},
}


def is_dispatcher_or_administrator(user):
    return user.is_superuser or user.groups.filter(
        name__in=("Dispatcher", "Administrador")
    ).exists()


def transition_incident(*, incident, target_status, actor, observation, resolution=""):
    allowed = ALLOWED_TRANSITIONS.get(incident.status, set())
    if target_status not in allowed:
        raise ValidationError("La transición de incidencia no está permitida.")
    if target_status == IncidentStatus.CLOSED and not is_dispatcher_or_administrator(actor):
        raise ValidationError("Solo el Dispatcher o el Administrador pueden cerrar incidencias.")
    if target_status == IncidentStatus.REOPENED and not is_dispatcher_or_administrator(actor):
        raise ValidationError("Solo el Dispatcher o el Administrador pueden reabrir incidencias.")
    if target_status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED) and not resolution.strip():
        raise ValidationError("La resolución es obligatoria para resolver o cerrar.")
    with transaction.atomic():
        previous_status = incident.status
        incident.status = target_status
        if resolution.strip():
            incident.resolution = resolution.strip()
        if target_status == IncidentStatus.RESOLVED:
            incident.resolved_at = timezone.now()
            incident.resolved_by = actor
        if target_status == IncidentStatus.CLOSED:
            incident.closed_at = timezone.now()
            incident.closed_by = actor
        if target_status == IncidentStatus.REOPENED:
            incident.closed_at = None
            incident.closed_by = None
        incident.save()
        IncidentHistory.objects.create(
            incident=incident,
            previous_status=previous_status,
            status=target_status,
            observation=observation.strip(),
            changed_by=actor,
        )
        AuditEvent.objects.create(
            actor=actor,
            order=incident.order,
            action="change_incident_status",
            entity_type="incident",
            entity_id=str(incident.pk),
            metadata={"previous_status": previous_status, "status": target_status},
        )
    return incident


def create_incident(*, form, order, actor):
    with transaction.atomic():
        incident = form.save(commit=False)
        incident.order = order
        incident.created_by = actor
        incident.status = IncidentStatus.OPEN
        incident.save()
        IncidentHistory.objects.create(
            incident=incident,
            status=incident.status,
            changed_by=actor,
            observation="Incidencia creada.",
        )
        AuditEvent.objects.create(
            actor=actor,
            order=order,
            action="create_incident",
            entity_type="incident",
            entity_id=str(incident.pk),
            metadata={"priority": incident.priority.code},
        )
    return incident
