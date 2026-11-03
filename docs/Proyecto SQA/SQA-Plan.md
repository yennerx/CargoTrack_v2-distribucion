# Plan de Aseguramiento de la Calidad — CargoTrack v2

## 1. Propósito y alcance

Aplicar actividades de SQA a CargoTrack, una aplicación Django existente para la
gestión de operaciones y órdenes. El trabajo evalúa una base compartida con el
Proyecto de Graduación; no crea una segunda aplicación. Incluye pruebas,
validación de cambios, métricas, análisis estático, deuda técnica y CI.

El plan toma como referencias los conceptos de calidad de producto de ISO/IEC
25010 y los procesos de prueba de ISO/IEC/IEEE 29119, adaptados al alcance
académico. No afirma certificación ni conformidad formal con esos estándares.

## 2. Responsabilidades y revisiones

El proyecto es individual. Las revisiones manuales se registran como autorrevisión
con alcance, commit, criterios y resultado; no se simula una segunda aprobación
independiente. pytest/pytest-django cubren pruebas unitarias, de integración y
regresión. Ruff es el linter seleccionado. SonarCloud complementa el análisis con
un dashboard de calidad una vez activado.

## 3. Modelo de calidad y métricas

La medición se hace sobre `apps/`, con cobertura separada de líneas/sentencias y
ramas. La línea base registrada el 2026-10-14 es 78,60 % de líneas y 57,84 % de
ramas, con 138 pruebas. Los mínimos se mantienen según la decisión del proyecto.
En el run 41530067001, commit `e62f621`, se obtuvieron 83,91 % de líneas, 64,81 %
de ramas y 176 pruebas aprobadas.

La cobertura no sustituye la revisión de calidad de las pruebas, autorización,
riesgos ni aceptación. Los defectos confirmados y su estado se resumen en el
reporte de mejora.

## 4. Flujo CI actual: tres jobs y cuatro etapas conceptuales

En `CargoTrack_v2-distribucion`, `.github/workflows/quality.yml` se ejecuta en
`push`, `pull_request` y `workflow_dispatch`. Se conserva la estructura de tres
jobs acordada:

| Etapa conceptual | Job/pasos existentes | Evidencia producida |
|---|---|---|
| Analyze | `static-analysis`: Ruff y Django check; SonarCloud se ejecuta en el job de pruebas después de cobertura | Ruff JSON y Quality Gate SonarCloud |
| Test | `tests-and-coverage`: PostgreSQL limpio, migraciones, pytest, cobertura y comparador | JUnit, coverage XML/JSON/HTML |
| Build | `docker-artifact`, dependiente de análisis y pruebas | Imagen Docker `.tar.gz` y SHA-256 |
| Report | Pasos de publicación dentro de los jobs | Artefactos de análisis, pruebas y build en GitHub Actions |

Analyze y Test corren en paralelo; Build depende de ambos. Report se ejecuta como
pasos dentro de esos jobs, no como un cuarto job separado.

## 5. Quality gates y análisis

- Ruff y `manage.py check` deben aprobar.
- Django debe aplicar y validar migraciones, y no debe haber cambios de modelo sin
  migración.
- pytest debe pasar y `scripts/check_coverage.py` debe aceptar las coberturas
  mínimas separadas actuales.
- Docker sólo se empaqueta cuando los jobs de análisis y pruebas aprueban.
- `sonar.qualitygate.wait=true` hace fallar el job si el Quality Gate SonarCloud
  falla. El run inicial aprobó el gate de código nuevo.

Ruff permanece como linter elegido y SonarCloud complementa el dashboard. La
integración usa `SONAR_ENABLED=true`, las variables `SONAR_ORGANIZATION` y
`SONAR_PROJECT_KEY`, y el secret `SONAR_TOKEN` en GitHub Actions; el token no se
incluye en archivos ni se comparte por chat. La primera ejecución CI, run
`41574835164`, analizó `apps/` y aprobó Quality Gate `Sonar way` para código nuevo.
Reportó 0 bugs, 22 vulnerabilidades menores abiertas (`python:S3752`), 0 code
smells, 0,3 % duplicación y 80,1 % coverage Sonar. Los 22 hallazgos requieren
triage; el Quality Gate no significa que no existan problemas abiertos.

## 6. Acceso, protección y privacidad

Durante la revisión pública, `main` requiere PR y los checks de Ruff/Django,
pruebas/cobertura PostgreSQL y construcción Docker. La protección se configuró
sin adquirir un plan de pago; exige PR y CI aprobada, pero no aprobación humana
independiente. Al volver el repo a privado se verificará si el plan disponible
mantiene esas reglas; no se afirmará que sigue protegido si GitHub las desactiva.
El PR de documentación #1 pasó los checks y se fusionó.

Los archivos de acta, implementación y capturas empresariales permanecen fuera
de Git y se entregan únicamente por la plataforma universitaria según las
políticas aplicables. En el repositorio no se incluyen datos personales, de
clientes, secretos ni configuración del servidor productivo.
