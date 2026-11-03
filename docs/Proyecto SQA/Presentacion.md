# Presentación de resultados — Proyecto SQA CargoTrack v2

> Versión Markdown para revisión y posterior traslado a PowerPoint/Google Slides.
> Propuesta de 10 diapositivas. Las notas entre corchetes son indicaciones de
> diseño/captura, no texto que deba quedar en la diapositiva final.

---

## Diapositiva 1 — Portada

# Aseguramiento de calidad integrado al flujo de CargoTrack v2

**Curso:** Aseguramiento de la Calidad del Software (SQA)

**Estudiante:** Yenner Américo Hernández Pérez

**Universidad:** Universidad Mariano Gálvez de Guatemala

**Fecha:** 2026

**Idea clave:** aplicar pruebas, análisis estático, cobertura y quality gates a
una aplicación existente.

[Diseño: título grande, nombre del proyecto y un diagrama sencillo de CI; usar
estilo visual sobrio y no colocar logos empresariales no autorizados.]

---

## Diapositiva 2 — Objetivo y alcance

### Objetivo

Integrar verificaciones repetibles de calidad a CargoTrack para detectar
regresiones antes de incorporar cambios a `main`.

### Alcance SQA

- Pruebas unitarias, de integración y regresión sobre Django y PostgreSQL.
- Análisis estático con Ruff y SonarCloud.
- Cobertura de líneas y ramas con umbrales independientes.
- Integración continua, revisión por pull request y artefacto Docker.
- Registro de resultados, deuda técnica y evidencia.

**Fuera de alcance de esta entrega:** despliegue automático a producción.

[Nota del presentador: CargoTrack es la aplicación del Proyecto de Graduación;
SQA comparte su código y sus pruebas, no crea otra aplicación.]

---

## Diapositiva 3 — Aplicación y herramientas

| Área | Herramientas utilizadas |
|---|---|
| Aplicación | Python 3.12, Django 5.2 y PostgreSQL |
| Pruebas | pytest, pytest-django y pytest-cov |
| Calidad estática | Ruff y SonarCloud |
| Integración continua | GitHub Actions |
| Empaquetado | Docker; artefacto no publicado en un registry |

### Separación de responsabilidades

CargoTrack valida autorización y reglas de negocio en el servidor. La CI repite
controles en un PostgreSQL efímero y no usa datos de la empresa.

[Visual: flujo simple `Código → Pruebas/Análisis → Artefacto`, no un despliegue
productivo.]

---

## Diapositiva 4 — Flujo CI y quality gates

```text
Push / Pull request / Ejecución manual
             ├── Analyze: Ruff + Django check
             └── Test: PostgreSQL 16 + migraciones + pytest + cobertura
                       + SonarCloud y Quality Gate
                         ↓
              Build: imagen Docker como artefacto
              Report: JUnit, Ruff y cobertura como artefactos
```

- Workflow: `.github/workflows/quality.yml`.
- Tres jobs; Analyze y Test corren en paralelo, Build depende de ambos.
- Quality gates: Ruff/Django, migraciones, suite y mínimos independientes de
  cobertura. SonarCloud hace fallar el job cuando su gate no aprueba.
- `main` requiere pull request y checks automáticos; el proyecto es individual y
  no exige una aprobación humana independiente.

[Captura sugerida: vista del workflow y sus tres jobs completados. Ocultar
cualquier configuración de secretos.]

---

## Diapositiva 5 — Pruebas y cobertura

La matriz relaciona casos automatizados con autenticación, permisos, órdenes,
documentos, finanzas, reportes y quality gates.

| Medición | Pruebas aprobadas | Cobertura de líneas/sentencias | Cobertura de ramas |
|---|---:|---:|---:|
| Línea base (2026-10-14) | 138 | 78,60 % (2.862/3.641) | 57,84 % (509/880) |
| CI posterior a DT-SQA-015 (run 41580904162) | 198 | 84,01 % (3.341/3.977) | 64,81 % (639/986) |
| Variación | +60 | +5,41 puntos | +6,97 puntos |

**Resultado del run 41580904162:** 198 aprobadas, 0 fallidas, 0 errores y 0
omitidas. Los artefactos JUnit y coverage están asociados al run.

[Visual sugerido: barras comparativas de cobertura de líneas y ramas; mostrar
por separado cantidad de pruebas.]

---

## Diapositiva 6 — Resultado antes/después

| Indicador | Línea base | Estado posterior | Cambio observado |
|---|---:|---:|---:|
| Pruebas aprobadas | 138 | 198 | +60 |
| Cobertura de líneas/sentencias | 78,60 % | 84,01 % | +5,41 pp |
| Cobertura de ramas | 57,84 % | 64,81 % | +6,97 pp |
| Ruff | Validación local registrada | 0 diagnósticos en CI | Gate automatizado |

El mínimo configurado de cobertura se conserva en 78,60 % de líneas y 57,84 % de
ramas; no se redujo para aprobar la ejecución.

**Lectura:** la cobertura es una medida de ejecución de código, no una garantía
de ausencia de defectos ni sustituto de revisar calidad y relevancia de las pruebas.

---

## Diapositiva 7 — SonarCloud y corrección verificada

### Estado inicial — run 41574835164

- Quality Gate `Sonar way`: **OK** para código nuevo.
- 22 hallazgos `python:S3752` en vistas sin métodos HTTP explícitos.
- 0 bugs, 0 code smells, 0,3 % de duplicación y 80,1 % de coverage Sonar.

### Corrección y estado posterior

- Las 22 vistas de lectura/descarga declaran `require_GET`.
- Prueba parametrizada: POST a cada ruta devuelve HTTP 405.
- PR #6 y CI posterior: **0 hallazgos `python:S3752` abiertos**.
- Dashboard actual: 0 bugs, 0 vulnerabilidades, 0 code smells, 0,3 % de
  duplicación y 80,2 % de coverage Sonar.

[Captura sugerida: dashboard SonarCloud del proyecto y resultado del análisis del
PR #6 o run 41580904162. Confirmar que se vea el proyecto correcto.]

---

## Diapositiva 8 — Demostración del flujo y evidencia

### Cambio inspeccionable

El PR [#6](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/6) añadió
`require_GET` a las vistas señaladas, agregó pruebas de método HTTP y actualizó la
documentación SQA. Se fusionó en `main` como `abd6932`.

### CI del cambio

- [Run del PR 41580576891](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580576891): Ruff/Django, PostgreSQL, pytest/cobertura, SonarCloud y Docker pasaron.
- [Run de `main` 41580904162](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580904162): mismos controles aprobados tras el merge.

[Captura sugerida: PR #6 mostrando título/branch y checks exitosos. Añadir otra
captura de los jobs del run. Son capturas del repositorio/código de prueba.]

---

## Diapositiva 9 — Deuda restante y límites

- **DT-SQA-006:** faltan medir otros reportes y carga sostenida.
- **DT-SQA-007:** respaldo productivo automatizado, cifrado, rotación y restauración
  operativa no están demostrados.
- **DT-SQA-008:** el comando de datos demo carece de pruebas específicas.
- No se registró suite E2E de navegador, prueba de penetración ni análisis
  separado de dependencias.
- La restauración local manual se probó con datos ficticios; no representa una
  auditoría de la instalación productiva.

Las limitaciones se muestran para delimitar lo verificado, no para presentar como
terminadas actividades que no se ejecutaron.

---

## Diapositiva 10 — Conclusiones y referencias

### Conclusiones

1. La CI ejecuta controles reales con PostgreSQL, publica resultados y empaqueta
   Docker sin desplegarlo.
2. Las pruebas y coberturas superan los mínimos definidos.
3. Los 22 hallazgos HTTP se corrigieron y SonarCloud confirmó que ya no están abiertos.
4. Los riesgos y actividades no verificadas quedan registrados como deuda SQA.

### Evidencia principal

- [Reporte de mejora](Reporte-Mejora.md) · [Matriz de pruebas](Matriz-Pruebas.md)
- [Plan SQA](SQA-Plan.md) · [Manual técnico](Manual-Tecnico.md)
- [CI post-corrección](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580904162)
- [CI más reciente](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41581916656)
- [Dashboard SonarCloud](https://sonarcloud.io/project/overview?id=yennerx_CargoTrack_v2-distribucion)

[Capturas de desarrollo permitidas: PR #6, checks de Actions, dashboard y gráfico
de cobertura. Insertarlas como evidencia propia antes de exportar.]

[Al pasar a PowerPoint: revisar la fecha y la URL del dashboard. No incluir actas,
datos de clientes, `.env`, tokens ni infraestructura productiva.]
