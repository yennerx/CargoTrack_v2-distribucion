# Manual técnico de CI/SQA — CargoTrack v2

## Componentes del workflow

El pipeline de la copia de distribución vive en `.github/workflows/quality.yml`,
se ejecuta en push, pull request y `workflow_dispatch`, y conserva los tres jobs
acordados:

| Job | Función | Evidencia |
|---|---|---|
| `static-analysis` | Ruff y Django check | JSON de Ruff y salida de Django |
| `tests-and-coverage` | PostgreSQL 16, migraciones, pytest, cobertura y gate | JUnit, XML/JSON/HTML de coverage |
| `docker-artifact` | Build y empaquetado de imagen si los dos jobs previos pasan | `.tar.gz` y SHA-256 |

Para la rúbrica, esos jobs cubren cuatro etapas conceptuales: Analyze, Test,
Build y Report. Report son los pasos de publicación de artifacts dentro de los
jobs; no se crea un cuarto job.

## Quality gates

1. Ruff y `manage.py check` deben pasar.
2. Migraciones a base vacía, `migrate --check` y
   `makemigrations --check --dry-run` deben aprobar.
3. pytest debe aprobar y `scripts/check_coverage.py` debe aceptar líneas y ramas
   separadas contra `coverage-thresholds.json`.
4. Docker sólo se construye cuando análisis y pruebas pasan.
5. El scanner SonarCloud espera el Quality Gate mediante
   `sonar.qualitygate.wait=true`; si no aprueba, falla el job de pruebas. El run
   `41574835164` confirmó su ejecución.

## SonarCloud: configuración y uso

El proyecto está enlazado a SonarQube Cloud y el repositorio tiene las variables
`SONAR_ENABLED=true`, `SONAR_ORGANIZATION`, `SONAR_PROJECT_KEY` y el secret
`SONAR_TOKEN`. El token sólo se gestiona en GitHub Actions Secrets; no se comparte
por chat ni se escribe en archivos. Si se rota, actualizar el secret de GitHub sin
cambiar el workflow.

La ejecución CI `41574835164` importó `sqa-artifacts/coverage.xml`, escaneó
`apps/`, mostró el Quality Gate `Sonar way` y publicó el dashboard. El scanner se
omite si `SONAR_ENABLED` no está activo. PRs de forks no reciben el token y no
ejecutan el scanner.

La primera medición reportó 22 hallazgos MINOR `python:S3752` sobre métodos HTTP
permitidos. Deben triagearse con los contratos de cada vista; no cerrar como falsos
positivos sin justificación. El gate OK corresponde a condiciones de código nuevo.

SonarQube Cloud analiza el código fuente en el servicio del proveedor. La
autorización para este proyecto se basa en la decisión del responsable de
publicar temporalmente esta copia de distribución para revisión académica. La
información de la empresa (actas, datos, adjuntos y configuración productiva) no
se encuentra en esta copia. La información oficial de planes indica una opción
gratuita para proyectos privados de hasta 50.000 líneas; se debe verificar el
conteo y las condiciones de la cuenta al enlazar el proyecto
([planes de SonarQube Cloud](https://www.sonarsource.com/plans-and-pricing/sonarqube-cloud/)).

## Comandos locales

```bash
cp .env.example .env
docker compose up --build
docker compose exec web ruff check .
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate --check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web pytest -q
```

## Protección de la rama

Mientras el repositorio está público, la rama `main` tiene protección activa:
requiere un PR, los checks nombrados de Ruff/Django, PostgreSQL/pytest y build
Docker, y resolución de conversaciones. Está configurada con cero aprobaciones
humanas porque el proyecto es individual; la revisión automática de CI es el gate.
Al devolver el repositorio a privado, comprobar si GitHub conserva estas reglas
con el plan disponible. El PR #1 pasó los checks requeridos y se fusionó.

## Artifact y privacidad

GitHub Actions conserva los artifacts por 30 días. Descargar JUnit, coverage,
Ruff JSON y Docker con SHA-256 y subirlos a la plataforma de la universidad. No
subir `.env`, bases de datos, `Adjuntos`, acta firmada, capturas empresariales ni
configuración LAN restringida al repositorio.
