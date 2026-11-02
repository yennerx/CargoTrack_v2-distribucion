"""Measure the authenticated order list against an isolated synthetic database."""

import argparse
import concurrent.futures
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.carriers.models import Carrier, CarrierType  # noqa: E402
from apps.catalogs.models import CatalogEntry, CatalogType  # noqa: E402
from apps.customers.models import Customer  # noqa: E402
from apps.orders.models import Order  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Crea órdenes ficticias en una base aislada y mide el listado HTTP con "
            "solicitudes concurrentes."
        )
    )
    parser.add_argument("--base-url", required=True, help="URL del Gunicorn aislado.")
    parser.add_argument("--orders", type=int, default=10_000)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--max-response-seconds", type=float, default=2.0)
    parser.add_argument(
        "--allow-nonproduction",
        action="store_true",
        help="Confirma que el servidor apunta a la base de benchmark aislada.",
    )
    return parser.parse_args()


def check_environment(args):
    database_name = str(settings.DATABASES["default"]["NAME"])
    database_host = str(settings.DATABASES["default"]["HOST"])
    if not args.allow_nonproduction:
        raise SystemExit("Use --allow-nonproduction solo con una base aislada de benchmark.")
    if (
        not settings.DEBUG
        or not database_name.startswith("cargotrack_fase16_benchmark")
        or database_host not in {"db", "localhost", "127.0.0.1"}
    ):
        raise SystemExit(
            "Rechazado: se requiere DEBUG=True y una base local cuyo nombre comience "
            "con cargotrack_fase16_benchmark."
        )
    if args.orders < 1 or args.concurrency < 1:
        raise SystemExit("--orders y --concurrency deben ser valores positivos.")
    parsed_url = urlsplit(args.base_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.hostname not in {"localhost", "127.0.0.1"}
    ):
        raise SystemExit("--base-url debe ser una URL HTTP(S) local del Gunicorn aislado.")
    return parsed_url


def seed_benchmark_data(order_count, token, user_prefix, nit_prefix, number_prefix):
    status = CatalogEntry.objects.get(code="solicitud-recibida")
    cargo_type = CatalogEntry.objects.filter(
        catalog_type=CatalogType.CARGO_TYPE, is_active=True
    ).first()
    equipment_type = CatalogEntry.objects.filter(
        catalog_type=CatalogType.EQUIPMENT_TYPE, is_active=True
    ).first()
    if cargo_type is None or equipment_type is None:
        raise RuntimeError("Faltan catálogos activos de carga o equipo para el benchmark.")

    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username=user_prefix,
        email=f"{user_prefix}@example.invalid",
        password=secrets.token_urlsafe(32),
    )
    customer = Customer.objects.create(
        nit=f"{nit_prefix}C",
        legal_name=f"Cliente ficticio {token}",
        created_by=user,
    )
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit=f"{nit_prefix}T",
        legal_name=f"Transportista ficticio {token}",
        primary_phone="55550000",
        email=f"{user_prefix}@example.invalid",
        created_by=user,
    )
    today = timezone.localdate()
    now = timezone.now()
    Order.objects.bulk_create(
        [
            Order(
                number=f"{number_prefix}{index:05d}",
                status=status,
                customer=customer,
                proposed_carrier=carrier,
                broker=user,
                created_by=user,
                cargo_type=cargo_type,
                equipment_type=equipment_type,
                origin="Origen ficticio",
                destination="Destino ficticio",
                pickup_date=today,
                delivery_date=today + timedelta(days=1),
                customer_rate="100.00",
                carrier_cost="70.00",
                updated_at=now,
            )
            for index in range(order_count)
        ],
        batch_size=500,
    )
    return user


def require_empty_benchmark_database():
    user_model = get_user_model()
    if any(
        model.objects.exists()
        for model in (Order, Customer, Carrier, user_model)
    ):
        raise SystemExit(
            "La base de benchmark debe estar vacía (recién migrada). No se borran "
            "eventos de auditoría ni datos transaccionales."
        )


def authenticated_cookie(user):
    client = Client()
    client.force_login(user)
    cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie is None:
        raise RuntimeError("No se pudo crear la sesión de benchmark.")
    return f"{settings.SESSION_COOKIE_NAME}={cookie.value}", client


def request_order_list(url, cookie, timeout):
    request = urllib.request.Request(
        url,
        headers={"Cookie": cookie, "User-Agent": "CargoTrack-Fase16-Benchmark"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = response.status
            response_url = response.geturl()
    except urllib.error.HTTPError as error:
        body = error.read()
        status = error.code
        response_url = error.geturl()
    elapsed = time.perf_counter() - started
    return status, len(body), elapsed, response_url


def run_requests(args, base_url, cookie):
    url = f"{base_url}/ordenes/"
    warmup = request_order_list(url, cookie, args.request_timeout)
    if warmup[0] != 200 or urlsplit(warmup[3]).path != urlsplit(url).path:
        raise RuntimeError(f"La solicitud de calentamiento devolvió HTTP {warmup[0]}.")

    barrier = threading.Barrier(args.concurrency)

    def synchronized_request(_):
        barrier.wait(timeout=args.request_timeout)
        return request_order_list(url, cookie, args.request_timeout)

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        results = list(executor.map(synchronized_request, range(args.concurrency)))
    wall_seconds = time.perf_counter() - started
    statuses = [status for status, _, _, _ in results]
    order_list_path = urlsplit(url).path
    if any(
        status != 200 or urlsplit(response_url).path != order_list_path
        for status, _, _, response_url in results
    ):
        raise RuntimeError(f"Respuestas HTTP inesperadas en la carga: {statuses}.")

    response_times = sorted(elapsed for _, _, elapsed, _ in results)
    percentile_95 = response_times[min(len(response_times) - 1, int(len(response_times) * 0.95))]
    max_response = response_times[-1]
    print(f"Órdenes sintéticas: {args.orders}")
    print(f"Solicitudes concurrentes: {args.concurrency}")
    print(f"Calentamiento: HTTP {warmup[0]}, {warmup[2]:.3f} s")
    print(f"Tiempo total de la tanda: {wall_seconds:.3f} s")
    print(f"P95 de respuesta: {percentile_95:.3f} s")
    print(f"Máxima respuesta: {max_response:.3f} s")
    print(f"Cuerpo HTTP: {results[0][1]} bytes")
    if max_response >= args.max_response_seconds:
        raise SystemExit(
            f"Falló el umbral: respuesta máxima {max_response:.3f} s >= "
            f"{args.max_response_seconds:.3f} s."
        )


def main():
    args = parse_args()
    parsed_url = check_environment(args)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    require_empty_benchmark_database()
    token = secrets.token_hex(4).upper()
    user_prefix = f"f16-benchmark-{token}"
    nit_prefix = f"F16{token}"
    number_prefix = f"B16{token}"
    user = seed_benchmark_data(args.orders, token, user_prefix, nit_prefix, number_prefix)
    cookie, _client = authenticated_cookie(user)
    run_requests(args, base_url, cookie)
    print(
        "La base conserva datos sintéticos y eventos de auditoría; elimine la base "
        "aislada al terminar."
    )


if __name__ == "__main__":
    main()
