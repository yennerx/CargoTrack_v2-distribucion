from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierDocument, CarrierType, CarrierUnit
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer, CustomerContact
from apps.documents.services import upload_document
from apps.finance.models import (
    BrokerDebt,
    Commission,
    CommissionRule,
    CommissionStatus,
    FinancialReview,
    FinancialStatus,
    FinancialTransaction,
    ReviewStatus,
)
from apps.incidents.models import Incident, IncidentStatus
from apps.orders.models import Order, OrderClosureStatus, OrderStatusHistory

DEMO_PREFIX = "DEMO-"
DEMO_USERNAME_PREFIX = "demo_"


class Command(BaseCommand):
    help = "Carga datos ficticios reproducibles para revisión visual y manual."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            required=True,
            help="Contraseña temporal para los usuarios demo; no se almacena en el código.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Cantidad de registros principales por módulo (por defecto: 10).",
        )
        parser.add_argument(
            "--allow-non-debug",
            action="store_true",
            help="Permite la carga fuera de DEBUG; usar solo en una base de pruebas aislada.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_non_debug"]:
            raise CommandError(
                "La carga demo está bloqueada fuera de DEBUG. Use --allow-non-debug "
                "solo en una base de pruebas."
            )
        count = options["count"]
        if count < 1 or count > 100:
            raise CommandError("--count debe estar entre 1 y 100.")

        with transaction.atomic():
            users = self.create_users(options["password"])
            catalogs = self.create_catalogs()
            customers = self.create_customers(count, users["admin"], users["broker"])
            carriers = self.create_carriers(
                count, users["admin"], users["broker"], catalogs
            )
            orders = self.create_orders(count, users, customers, carriers, catalogs)
            self.create_documents(orders, users, catalogs)
            self.create_incidents(count, orders, users, catalogs)
            commissions = self.create_finances_and_commissions(
                orders, users, catalogs
            )
            self.create_debts(commissions, users)
            self.create_audit_events(count, users["admin"])

        self.stdout.write(self.style.SUCCESS("Datos demo cargados correctamente."))
        self.stdout.write(
            "Usuarios: demo_broker_01, demo_dispatcher_01, demo_admin_01, "
            "demo_adminfin_01 y demo_general_01, entre otros."
        )
        self.stdout.write("Identificador de datos: DEMO-")

    def create_users(self, password):
        user_model = get_user_model()
        role_plan = (
            ("broker", "Broker", 3),
            ("dispatcher", "Dispatcher", 2),
            ("admin", "Administrador", 2),
            ("adminfin", "Gerente administrativo", 2),
            ("general", "Gerente general", 1),
        )
        users = {}
        for prefix, role, amount in role_plan:
            group = self.group(role)
            users[prefix] = []
            for index in range(1, amount + 1):
                username = f"{DEMO_USERNAME_PREFIX}{prefix}_{index:02d}"
                user, _created = user_model.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": f"Demo {role}",
                        "last_name": f"{index:02d}",
                        "email": f"{username}@example.test",
                        "is_active": True,
                    },
                )
                user.set_password(password)
                user.first_name = f"Demo {role}"
                user.last_name = f"{index:02d}"
                user.email = f"{username}@example.test"
                user.is_active = True
                user.save()
                user.groups.add(group)
                users[prefix].append(user)
        users["broker_user"] = users["broker"][0]
        users["dispatcher_user"] = users["dispatcher"][0]
        users["admin"] = users["admin"][0]
        users["adminfin"] = users["adminfin"][0]
        users["general"] = users["general"][0]
        return users

    @staticmethod
    def group(name):
        from django.contrib.auth.models import Group

        return Group.objects.get(name=name)

    def create_catalogs(self):
        catalog_plan = (
            (CatalogType.COST_TYPE, "costo"),
            (CatalogType.FINANCIAL_MOVEMENT, "movimiento"),
            (CatalogType.DOCUMENT_TYPE, "documento"),
        )
        entries = {}
        for catalog_type, prefix in catalog_plan:
            for index in range(1, 5 if prefix == "costo" else 4):
                code = f"demo-{prefix}-{index:02d}"
                entry, _created = CatalogEntry.objects.update_or_create(
                    catalog_type=catalog_type,
                    code=code,
                    defaults={
                        "name": f"Demo {prefix.title()} {index:02d}",
                        "description": "Registro ficticio para pruebas manuales.",
                        "sort_order": 900 + index,
                        "is_active": index != 3,
                        "is_system_defined": False,
                    },
                )
                entries[code] = entry
        return entries

    def create_customers(self, count, actor, brokers):
        customers = []
        for index in range(1, count + 1):
            customer, _created = Customer.objects.update_or_create(
                nit=f"DEMOCLI{index:04d}",
                defaults={
                    "legal_name": f"Cliente Demo {index:02d}",
                    "commercial_name": f"Cliente Comercial Demo {index:02d}",
                    "address": f"Avenida Demo {index:02d}",
                    "city": "Ciudad de Guatemala",
                    "country": "Guatemala",
                    "notes": "Registro ficticio para revisión manual.",
                    "is_active": index not in (8, 9),
                    "created_by": actor,
                },
            )
            customer.brokers.set((brokers[(index - 1) % len(brokers)],))
            CustomerContact.objects.update_or_create(
                customer=customer,
                email=f"contacto{index:02d}@example.test",
                defaults={
                    "name": f"Contacto Demo {index:02d}",
                    "position": "Contacto de pruebas",
                    "primary_phone": f"5550{index:04d}",
                    "preferred_contact_method": "Correo",
                    "is_primary": True,
                    "is_active": True,
                },
            )
            customers.append(customer)
        return customers

    def create_carriers(self, count, actor, brokers, catalogs):
        equipment = CatalogEntry.objects.filter(
            catalog_type=CatalogType.EQUIPMENT_TYPE, is_active=True
        ).first()
        document_type = CatalogEntry.objects.get(
            catalog_type=CatalogType.DOCUMENT_TYPE, code="licencia"
        )
        carriers = []
        for index in range(1, count + 1):
            carrier, _created = Carrier.objects.update_or_create(
                nit=f"DEMOCAR{index:04d}",
                defaults={
                    "carrier_type": CarrierType.COMPANY if index % 2 else CarrierType.PERSON,
                    "legal_name": f"Transportista Demo {index:02d}",
                    "commercial_name": f"Trans Demo {index:02d}",
                    "address": f"Ruta Demo {index:02d}",
                    "city": "Ciudad de Guatemala",
                    "country": "Guatemala",
                    "primary_phone": f"5551{index:04d}",
                    "email": f"carrier{index:02d}@example.test",
                    "notes": "Registro ficticio para revisión manual.",
                    "is_active": index not in (9, 10),
                    "is_validated": index <= 7,
                    "created_by": actor,
                },
            )
            carrier.brokers.set((brokers[(index - 1) % len(brokers)],))
            CarrierUnit.objects.update_or_create(
                carrier=carrier,
                unit_identifier=f"DEMO-UNIT-{index:02d}",
                defaults={
                    "equipment_type": equipment,
                    "license_plate": f"DEMO{index:04d}",
                    "brand": "Marca Demo",
                    "model": "Modelo Demo",
                    "is_active": index not in (8, 9),
                },
            )
            CarrierDocument.objects.update_or_create(
                carrier=carrier,
                document_type=document_type,
                document_number=f"DEMO-LIC-{index:04d}",
                defaults={
                    "issued_at": date.today() - timedelta(days=120),
                    "expires_at": date.today() + timedelta(days=30 * (index - 5)),
                    "notes": "Documento ficticio para probar vencimientos.",
                    "is_validated": index <= 7,
                    "validated_by": actor if index <= 7 else None,
                    "validated_at": timezone.now() if index <= 7 else None,
                    "is_active": True,
                },
            )
            carriers.append(carrier)
        return carriers

    def create_orders(self, count, users, customers, carriers, catalogs):
        demo_states = (
            ("solicitud-recibida", OrderClosureStatus.OPEN),
            ("en-negociacion", OrderClosureStatus.OPEN),
            ("en-transito", OrderClosureStatus.OPEN),
            ("entregada", OrderClosureStatus.OPEN),
            ("entregada", OrderClosureStatus.PENDING),
            ("entregada", OrderClosureStatus.CLOSED),
            ("entregada", OrderClosureStatus.REOPENED),
            ("cancelada", OrderClosureStatus.OPEN),
            ("asignada", OrderClosureStatus.OPEN),
            ("validada", OrderClosureStatus.OPEN),
        )
        cargo_types = list(
            CatalogEntry.objects.filter(
                catalog_type=CatalogType.CARGO_TYPE, is_active=True
            )
        )
        equipment_types = list(
            CatalogEntry.objects.filter(
                catalog_type=CatalogType.EQUIPMENT_TYPE, is_active=True
            )
        )
        orders = []
        for index in range(1, count + 1):
            status_code, closure_status = demo_states[(index - 1) % len(demo_states)]
            status = CatalogEntry.objects.get(code=status_code)
            broker = users["broker"][index % len(users["broker"])]
            order, _created = Order.objects.update_or_create(
                number=f"DEMO-ORD-{index:04d}",
                defaults={
                    "status": status,
                    "closure_status": closure_status,
                    "customer": customers[(index - 1) % len(customers)],
                    "proposed_carrier": carriers[(index - 1) % len(carriers)],
                    "confirmed_carrier": carriers[(index - 1) % len(carriers)]
                    if index >= 3
                    else None,
                    "broker": broker,
                    "created_by": broker,
                    "dispatcher": users["dispatcher_user"],
                    "cargo_type": cargo_types[(index - 1) % len(cargo_types)],
                    "equipment_type": equipment_types[(index - 1) % len(equipment_types)],
                    "origin": f"Origen Demo {index:02d}",
                    "destination": f"Destino Demo {index:02d}",
                    "pickup_date": date.today() - timedelta(days=index),
                    "delivery_date": date.today() + timedelta(days=index - 5),
                    "customer_rate": Decimal("1500") + index * Decimal("100"),
                    "carrier_cost": Decimal("950") + index * Decimal("50"),
                    "rate_conditions": "Condiciones ficticias de prueba.",
                    "logistics_notes": "Notas ficticias para revisión manual.",
                },
            )
            OrderStatusHistory.objects.update_or_create(
                order=order,
                status=status,
                defaults={
                    "previous_status": None,
                    "changed_by": users["dispatcher_user"],
                    "observation": "Estado demo inicial.",
                },
            )
            orders.append(order)
        return orders

    def create_documents(self, orders, users, catalogs):
        document_codes = (
            "factura",
            "recibo",
            "constancia-entrega",
            "comprobante-cobro",
            "comprobante-gasto",
        )
        for index, order in enumerate(orders, start=1):
            codes = [document_codes[(index - 1) % 2]]
            if (
                order.status.code == "entregada"
                or order.closure_status != OrderClosureStatus.OPEN
            ):
                codes.extend(("constancia-entrega", "comprobante-cobro", "comprobante-gasto"))
            for code in set(codes):
                document_type = CatalogEntry.objects.get(
                    catalog_type=CatalogType.DOCUMENT_TYPE, code=code
                )
                related_event = f"{DEMO_PREFIX}{order.number}-{code}"
                if order.documents.filter(related_event=related_event).exists():
                    continue
                stage = order.status
                if order.closure_status != OrderClosureStatus.OPEN:
                    closure_code_by_status = {
                        OrderClosureStatus.PENDING: "pendiente-cierre",
                        OrderClosureStatus.CLOSED: "cerrada",
                        OrderClosureStatus.REOPENED: "reabierta",
                    }
                    stage = CatalogEntry.objects.get(
                        code=closure_code_by_status[order.closure_status]
                    )
                upload_document(
                    uploaded_file=ContentFile(
                        b"%PDF-1.4\n% CargoTrack demo document\n", name=f"{related_event}.pdf"
                    ),
                    actor=users["admin"],
                    target=order,
                    document_data={
                        "document_type": document_type,
                        "target_type": "order",
                        "stage": stage,
                        "related_event": related_event,
                    },
                )

    def create_incidents(self, count, orders, users, catalogs):
        incident_types = list(
            CatalogEntry.objects.filter(
                catalog_type=CatalogType.INCIDENT_TYPE, is_active=True
            )
        )
        priorities = list(
            CatalogEntry.objects.filter(
                catalog_type=CatalogType.INCIDENT_PRIORITY, is_active=True
            )
        )
        states = (
            IncidentStatus.OPEN,
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        )
        for index in range(1, count + 1):
            status = states[(index - 1) % len(states)]
            has_resolution = status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}
            Incident.objects.update_or_create(
                order=orders[(index - 1) % len(orders)],
                title=f"{DEMO_PREFIX}Incidencia {index:02d}",
                defaults={
                    "incident_type": incident_types[(index - 1) % len(incident_types)],
                    "priority": priorities[(index - 1) % len(priorities)],
                    "status": status,
                    "description": "Descripción ficticia para pruebas de incidencias.",
                    "assigned_to": users["dispatcher_user"],
                    "resolution": "Resolución ficticia." if has_resolution else "",
                    "resolved_at": timezone.now() if has_resolution else None,
                    "resolved_by": users["dispatcher_user"] if has_resolution else None,
                    "closed_at": timezone.now() if status == IncidentStatus.CLOSED else None,
                    "closed_by": (
                        users["dispatcher_user"] if status == IncidentStatus.CLOSED else None
                    ),
                    "created_by": users["dispatcher_user"],
                },
            )

    def create_finances_and_commissions(self, orders, users, catalogs):
        currency = CatalogEntry.objects.get(
            catalog_type=CatalogType.CURRENCY, code="usd"
        )
        income_type = CatalogEntry.objects.get(code="cobro-cliente")
        expense_type = CatalogEntry.objects.get(code="pago-transportista")
        cost_type = CatalogEntry.objects.get(
            catalog_type=CatalogType.COST_TYPE, code="costo-transportista"
        )
        commissions = []
        for index, order in enumerate(orders, start=1):
            income_status = (
                FinancialStatus.PENDING if index in (2, 7) else FinancialStatus.CONFIRMED
            )
            expense_status = FinancialStatus.VOIDED if index == 8 else FinancialStatus.CONFIRMED
            FinancialTransaction.objects.update_or_create(
                order=order,
                movement_type=income_type,
                reference=f"{DEMO_PREFIX}COBRO-{index:04d}",
                defaults={
                    "currency": currency,
                    "amount": Decimal("1500") + index * Decimal("100"),
                    "exchange_rate_to_usd": Decimal("1"),
                    "status": income_status,
                    "transaction_date": date.today() - timedelta(days=index),
                    "description": "Cobro ficticio para reportes.",
                    "created_by": users["dispatcher_user"],
                },
            )
            FinancialTransaction.objects.update_or_create(
                order=order,
                movement_type=expense_type,
                reference=f"{DEMO_PREFIX}PAGO-{index:04d}",
                defaults={
                    "cost_type": cost_type,
                    "currency": currency,
                    "amount": Decimal("950") + index * Decimal("50"),
                    "exchange_rate_to_usd": Decimal("1"),
                    "status": expense_status,
                    "transaction_date": date.today() - timedelta(days=index),
                    "description": "Pago ficticio para reportes.",
                    "created_by": users["dispatcher_user"],
                },
            )
            review, _created = FinancialReview.objects.update_or_create(
                order=order,
                defaults={
                    "status": ReviewStatus.VALIDATED if index <= 8 else ReviewStatus.PENDING,
                    "observation": "Validación demo." if index <= 8 else "Pendiente demo.",
                    "reviewed_by": users["adminfin"] if index <= 8 else None,
                    "reviewed_at": timezone.now() if index <= 8 else None,
                },
            )
            rule, _created = CommissionRule.objects.get_or_create(
                broker=order.broker,
                valid_from=date(2026, 1, 1),
                defaults={
                    "percentage": Decimal("10") + index % 3,
                    "valid_to": None,
                    "is_active": True,
                    "created_by": users["adminfin"],
                },
            )
            income = Decimal("1500") + index * Decimal("100")
            expense = Decimal("950") + index * Decimal("50")
            profit = income - expense
            commission, _created = Commission.objects.update_or_create(
                order=order,
                defaults={
                    "broker": order.broker,
                    "rule": rule,
                    "gross_profit_usd": profit,
                    "commission_rate": rule.percentage,
                    "gross_commission_usd": (
                        profit * rule.percentage / 100
                    ).quantize(Decimal("0.01")),
                    "commission_amount_usd": (
                        profit * rule.percentage / 100
                    ).quantize(Decimal("0.01")),
                    "status": (
                        CommissionStatus.PAID
                        if index in (1, 4)
                        else CommissionStatus.AUTHORIZED
                        if index in (3, 6)
                        else CommissionStatus.CALCULATED
                    ),
                    "calculated_by": users["adminfin"],
                    "authorized_by": users["general"] if index in (1, 3, 4, 6) else None,
                    "authorized_at": timezone.now() if index in (1, 3, 4, 6) else None,
                    "paid_by": users["general"] if index in (1, 4) else None,
                    "paid_at": timezone.now() if index in (1, 4) else None,
                    "payment_method": "Transferencia demo" if index in (1, 4) else "",
                    "payment_reference": (
                        f"{DEMO_PREFIX}PAGO-COM-{index:04d}" if index in (1, 4) else ""
                    ),
                },
            )
            commissions.append(commission)
        return commissions

    def create_debts(self, commissions, users):
        for index, commission in enumerate(commissions[:2], start=1):
            amount = Decimal("75") + index * Decimal("25")
            commission.loss_amount_usd = amount
            commission.company_covered_loss_usd = Decimal("25")
            commission.agreed_broker_debt_usd = amount - Decimal("25")
            commission.loss_report = "Informe ficticio de pérdida demo."
            commission.negotiation_agreement = "Acuerdo ficticio con broker demo."
            commission.save(
                update_fields=(
                    "loss_amount_usd",
                    "company_covered_loss_usd",
                    "agreed_broker_debt_usd",
                    "loss_report",
                    "negotiation_agreement",
                    "updated_at",
                )
            )
            BrokerDebt.objects.update_or_create(
                origin_commission=commission,
                defaults={
                    "broker": commission.broker,
                    "loss_report": commission.loss_report,
                    "negotiation_agreement": commission.negotiation_agreement,
                    "loss_amount_usd": amount,
                    "company_covered_loss_usd": Decimal("25"),
                    "agreed_amount_usd": amount - Decimal("25"),
                    "balance_usd": amount - Decimal("25"),
                    "responsibility_percentage": Decimal("50"),
                    "approved_by": users["general"],
                },
            )

    def create_audit_events(self, count, actor):
        for index in range(1, count + 1):
            AuditEvent.objects.get_or_create(
                actor=actor,
                action="load_demo_data",
                entity_type="demo_dataset",
                entity_id=f"{DEMO_PREFIX}{index:04d}",
                defaults={"metadata": {"source": "load_demo_data"}},
            )
