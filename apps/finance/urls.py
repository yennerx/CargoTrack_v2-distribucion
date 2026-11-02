from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.finance_list, name="list"),
    path("orden/<int:order_pk>/", views.order_finance, name="order"),
    path("orden/<int:order_pk>/nuevo/", views.transaction_create, name="create"),
    path(
        "orden/<int:order_pk>/ajuste-comercial/nuevo/",
        views.commercial_adjustment_create,
        name="commercial-adjustment-create",
    ),
    path(
        "ajuste-comercial/<int:pk>/revisar/",
        views.commercial_adjustment_review,
        name="commercial-adjustment-review",
    ),
    path("movimiento/<int:pk>/confirmar/", views.transaction_confirm, name="confirm"),
    path("movimiento/<int:pk>/ajuste/", views.adjustment_create, name="adjustment"),
    path("orden/<int:order_pk>/validar/", views.summary_validate, name="validate"),
    path("comisiones/", views.commission_list, name="commission-list"),
    path("comisiones/reglas/", views.commission_rules, name="commission-rules"),
    path("comisiones/reglas/nueva/", views.commission_rule_form, name="commission-rule-create"),
    path(
        "comisiones/reglas/<int:pk>/editar/",
        views.commission_rule_form,
        name="commission-rule-edit",
    ),
    path(
        "orden/<int:order_pk>/comision/nueva/",
        views.commission_calculate,
        name="commission-calculate",
    ),
    path("comision/<int:pk>/", views.commission_detail, name="commission-detail"),
    path("comision/<int:pk>/perdida/", views.commission_loss, name="commission-loss"),
    path("comision/<int:pk>/autorizar/", views.commission_authorize, name="commission-authorize"),
    path("comision/<int:pk>/pagar/", views.commission_pay, name="commission-pay"),
    path("comision/<int:pk>/aplicar-deuda/", views.debt_apply, name="debt-apply"),
]
