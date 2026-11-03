# Manual técnico de CI/SQA — CargoTrack v2

## Componentes del workflow

El pipeline vive en `.github/workflows/quality.yml`, se ejecuta en push, pull
request y `workflow_dispatch`, y conserva los tres jobs acordados:

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
5. Con SonarCloud activo, `sonar.qualitygate.wait=true` hace fallar el job de
   pruebas si el Quality Gate no aprueba.

## Activar SonarCloud

1. Crear/enlazar el proyecto CargoTrack en SonarQube Cloud (GitHub Actions).
2. Registrar como variables del repositorio `SONAR_ENABLED=true`,
   `SONAR_ORGANIZATION` y `SONAR_PROJECT_KEY` usando los valores que proporciona
   SonarCloud.
3. Guardar `SONAR_TOKEN` sólo en GitHub Actions Secrets.
4. Confirmar que `sqa-artifacts/coverage.xml` aparece en el dashboard y revisar
   Quality Gate, bugs, code smells y duplicación.
5. No compartir el token en archivos, commits, capturas o mensajes.

El paso Sonar se omite cuando `SONAR_ENABLED` no está activo. No se debe indicar
que el dashboard está funcionando hasta que la ejecución aparezca en SonarCloud.
Los PRs de forks no reciben el token y no ejecutan el scanner.

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

## Artifact y privacidad

GitHub Actions conserva los artifacts por 30 días. Descargar JUnit, coverage,
Ruff JSON y Docker con SHA-256 y subirlos a la plataforma de la universidad. No
subir `.env`, bases de datos, `Adjuntos`, acta firmada, capturas empresariales ni
configuración LAN restringida al repositorio.
