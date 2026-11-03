# CargoTrack v2

[![Aseguramiento de calidad](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/workflows/quality.yml)

Aplicación web para centralizar y dar seguimiento a órdenes de despacho, clientes,
transportistas, documentos, incidencias, movimientos financieros, comisiones y
reportes.

## Tecnologías

- Python 3.12 y Django 5.2
- Django Templates, HTMX y Bootstrap 5
- PostgreSQL
- Docker Compose y Gunicorn
- pytest, pytest-django y Ruff

## Ejecución local

Requisitos: Docker Engine, Docker Compose y Git.

```bash
cp .env.example .env
docker compose up --build
```

La aplicación queda disponible en `http://localhost:8000/`; la comprobación de
salud está en `http://localhost:8000/health/`. Los valores de `.env.example` son
marcadores de desarrollo: reemplázalos por valores locales y no compartas `.env`.

Para cargar datos ficticios de desarrollo:

```bash
docker compose exec web python manage.py load_demo_data --password "SuPasswordDemo"
```

No uses datos reales ni ejecutes esa carga contra una base operativa.

## Comprobaciones locales

```bash
docker compose exec web ruff check .
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate --check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web pytest -q
```

El workflow de GitHub Actions ejecuta análisis estático, migraciones, pruebas y
cobertura sobre PostgreSQL; si los controles pasan, construye un artefacto Docker
sin publicarlo en un registro ni desplegarlo.

## Entrega académica SQA

Los entregables y su matriz de evidencia están en [`docs/Proyecto SQA/README.md`](docs/Proyecto%20SQA/README.md).

## Uso del código

Este repositorio se publica temporalmente para evaluación académica. No contiene
una licencia de código abierto ni concede permiso de reutilización o
redistribución; coordina cualquier otro uso con el titular del proyecto.
