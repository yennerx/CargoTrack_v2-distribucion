from django.contrib.auth import get_user_model
from django.db.models import Q

GLOBAL_DATA_ROLES = {
    "Administrador",
    "Dispatcher",
    "Gerente administrativo",
    "Gerente general",
}


def is_broker(user):
    return (
        not has_global_data_access(user)
        and user.groups.filter(name="Broker").exists()
    )


def active_brokers():
    return get_user_model().objects.filter(
        is_active=True, groups__name="Broker"
    ).order_by("username")


def broker_can_access_customer(broker, customer):
    return has_global_data_access(broker) or (
        customer.created_by_id == broker.pk or customer.brokers.filter(pk=broker.pk).exists()
    )


def broker_can_access_carrier(broker, carrier):
    return has_global_data_access(broker) or (
        carrier.created_by_id == broker.pk or carrier.brokers.filter(pk=broker.pk).exists()
    )


def brokers_requiring_master_assignment(orders):
    broker_ids = set(orders.values_list("broker_id", flat=True)) | set(
        orders.values_list("created_by_id", flat=True)
    )
    if not broker_ids:
        return set()
    return set(
        get_user_model()
        .objects.filter(
            pk__in=broker_ids,
            is_active=True,
            groups__name="Broker",
        )
        .exclude(groups__name__in=GLOBAL_DATA_ROLES)
        .values_list("pk", flat=True)
        .distinct()
    )


def has_global_data_access(user):
    return user.is_superuser or user.groups.filter(name__in=GLOBAL_DATA_ROLES).exists()


def scope_customers(queryset, user):
    if has_global_data_access(user):
        return queryset
    return queryset.filter(Q(created_by=user) | Q(brokers=user)).distinct()


def scope_carriers(queryset, user):
    if has_global_data_access(user):
        return queryset
    return queryset.filter(Q(created_by=user) | Q(brokers=user)).distinct()


def scope_orders(queryset, user):
    if has_global_data_access(user):
        return queryset
    return queryset.filter(Q(created_by=user) | Q(broker=user)).distinct()


def scope_assigned_orders(queryset, user):
    if has_global_data_access(user):
        return queryset
    return queryset.filter(broker=user)


def scope_incidents(queryset, user):
    if has_global_data_access(user):
        return queryset
    return queryset.filter(order__broker=user)


def scope_documents(queryset, user):
    if has_global_data_access(user):
        return queryset
    return queryset.filter(
        Q(order__created_by=user)
        | Q(order__broker=user)
        | Q(carrier__created_by=user)
        | Q(carrier__brokers=user)
        | Q(incident__order__broker=user)
    ).distinct()
