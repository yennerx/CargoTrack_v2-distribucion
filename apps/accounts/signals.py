from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def assign_initial_permissions(sender, **kwargs):
    if sender.name not in (
        "apps.accounts",
        "apps.audit",
        "apps.catalogs",
        "apps.customers",
        "apps.carriers",
        "apps.orders",
        "apps.documents",
        "apps.incidents",
        "apps.finance",
    ):
        return

    administrator = Group.objects.get(name="Administrador")
    auth_permissions = Permission.objects.filter(
        content_type__app_label="auth",
        content_type__model__in=("user", "group"),
    )
    permission_assignment_permissions = Permission.objects.filter(
        content_type__app_label="accounts",
        content_type__model="userpermissionassignment",
        codename__in=(
            "add_userpermissionassignment",
            "change_userpermissionassignment",
            "view_userpermissionassignment",
        ),
    )
    audit_permissions = Permission.objects.filter(
        content_type__app_label="audit",
        content_type__model="auditevent",
    )
    catalog_permissions = Permission.objects.filter(
        content_type__app_label="catalogs",
        content_type__model__in=("catalogentry", "systemconfiguration"),
    )
    customer_permissions = Permission.objects.filter(
        content_type__app_label="customers",
        content_type__model__in=("customer", "customercontact"),
    )
    carrier_permissions = Permission.objects.filter(
        content_type__app_label="carriers",
        content_type__model__in=("carrier", "carrierunit", "carrierdocument"),
    )
    order_permissions = Permission.objects.filter(
        content_type__app_label="orders",
        content_type__model__in=("order", "ordernumbersequence"),
    )
    document_permissions = Permission.objects.filter(
        content_type__app_label="documents",
        content_type__model__in=("document", "documentversion"),
    )
    incident_permissions = Permission.objects.filter(
        content_type__app_label="incidents",
        content_type__model__in=("incident", "incidenthistory"),
    )
    finance_permissions = Permission.objects.filter(
        content_type__app_label="finance",
        content_type__model__in=(
            "financialtransaction",
            "financialreview",
            "commissionrule",
            "commission",
            "brokerdebt",
            "commissiondebtapplication",
            "commercialadjustment",
        ),
    )
    administrator.permissions.add(
        *auth_permissions,
        *permission_assignment_permissions,
        *audit_permissions,
        *catalog_permissions,
        *customer_permissions,
        *carrier_permissions,
        *order_permissions,
        *document_permissions,
        *incident_permissions,
        *finance_permissions,
    )

    customer_view = customer_permissions.filter(codename__startswith="view_")
    customer_create = customer_permissions.filter(codename__startswith="add_")
    customer_change = customer_permissions.filter(codename__startswith="change_")
    Group.objects.get(name="Broker").permissions.add(*customer_view, *customer_create)
    Group.objects.get(name="Dispatcher").permissions.add(*customer_view, *customer_change)
    Group.objects.get(name="Gerente administrativo").permissions.add(
        *customer_view,
        *customer_change,
        *customer_create,
    )
    Group.objects.get(name="Gerente general").permissions.add(*customer_view)

    carrier_view = carrier_permissions.filter(codename__startswith="view_")
    carrier_change = carrier_permissions.filter(codename__startswith="change_")
    carrier_create = carrier_permissions.filter(codename__startswith="add_")
    Group.objects.get(name="Broker").permissions.add(*carrier_view)
    Group.objects.get(name="Dispatcher").permissions.add(*carrier_view, *carrier_change)
    Group.objects.get(name="Gerente administrativo").permissions.add(*carrier_view)
    Group.objects.get(name="Gerente general").permissions.add(*carrier_view)
    Group.objects.get(name="Administrador").permissions.add(*carrier_create)

    order_view = order_permissions.filter(codename="view_order")
    order_add = order_permissions.filter(codename="add_order")
    order_change = order_permissions.filter(codename="change_order")
    Group.objects.get(name="Broker").permissions.add(*order_view, *order_add, *order_change)
    Group.objects.get(name="Dispatcher").permissions.add(*order_view, *order_change)
    Group.objects.get(name="Gerente administrativo").permissions.add(*order_view)
    Group.objects.get(name="Gerente general").permissions.add(*order_view)

    document_view = document_permissions.filter(codename__startswith="view_")
    document_add = document_permissions.filter(codename__startswith="add_")
    document_change = document_permissions.filter(codename__startswith="change_")
    Group.objects.get(name="Broker").permissions.add(*document_view, *document_add)
    Group.objects.get(name="Dispatcher").permissions.add(
        *document_view, *document_add, *document_change
    )
    Group.objects.get(name="Gerente administrativo").permissions.add(*document_view)
    Group.objects.get(name="Gerente general").permissions.add(*document_view)

    incident_view = incident_permissions.filter(codename="view_incident")
    incident_add = incident_permissions.filter(codename="add_incident")
    incident_change = incident_permissions.filter(codename="change_incident")
    Group.objects.get(name="Broker").permissions.add(*incident_view, *incident_add)
    Group.objects.get(name="Dispatcher").permissions.add(
        *incident_view, *incident_add, *incident_change
    )
    Group.objects.get(name="Gerente administrativo").permissions.add(*incident_view)
    Group.objects.get(name="Gerente general").permissions.add(*incident_view)

    finance_view = finance_permissions.filter(codename="view_financialtransaction")
    finance_add = finance_permissions.filter(codename="add_financialtransaction")
    finance_change = finance_permissions.filter(codename="change_financialtransaction")
    Group.objects.get(name="Broker").permissions.add(*finance_view, *finance_add)
    Group.objects.get(name="Dispatcher").permissions.add(
        *finance_view,
        *finance_add,
        *finance_change,
        *finance_permissions.filter(
            codename__in=("view_commercialadjustment", "add_commercialadjustment")
        ),
    )
    Group.objects.get(name="Gerente administrativo").permissions.add(*finance_view)
    Group.objects.get(name="Gerente general").permissions.add(*finance_view)
    Group.objects.get(name="Gerente administrativo").permissions.add(
        *finance_permissions.filter(codename="view_financialreview"),
        *finance_permissions.filter(codename="change_financialreview"),
        *finance_permissions.filter(
            codename__in=("view_commissionrule", "add_commissionrule", "change_commissionrule")
        ),
        *finance_permissions.filter(
            codename__in=("view_commission", "add_commission", "change_commission")
        ),
        *finance_permissions.filter(
            codename__in=("view_brokerdebt", "view_commissiondebtapplication")
        ),
        *finance_permissions.filter(
            codename__in=("view_commercialadjustment", "change_commercialadjustment")
        ),
    )
    Group.objects.get(name="Gerente general").permissions.add(
        *finance_permissions.filter(
            codename__in=("view_commissionrule", "add_commissionrule", "change_commissionrule")
        ),
        *finance_permissions.filter(
            codename__in=("view_commission", "add_commission", "change_commission")
        ),
        *finance_permissions.filter(
            codename__in=("view_brokerdebt", "view_commissiondebtapplication")
        ),
        *finance_permissions.filter(codename="view_commercialadjustment"),
    )

    audit_view = audit_permissions.filter(codename="view_auditevent")
    for role_name in ("Gerente administrativo", "Gerente general"):
        Group.objects.get(name=role_name).permissions.add(*audit_view)
