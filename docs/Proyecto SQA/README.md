# Entregables del Proyecto Final SQA — CargoTrack v2

Este paquete organiza los entregables académicos conforme a las directrices del
Proyecto Final SQA 2026. El enunciado original se conserva como referencia local y
no forma parte del paquete de distribución. CargoTrack es una aplicación existente
del Proyecto de Graduación; SQA comparte su código y sus pruebas, sin crear una
segunda aplicación.

## Entregables y estado

| Entregable | Documento/archivo | Estado |
|---|---|---|
| Plan de Aseguramiento de Calidad | [`SQA-Plan.md`](SQA-Plan.md) | Preparado y aplicado al proyecto |
| Matriz de pruebas | [`Matriz-Pruebas.md`](Matriz-Pruebas.md) | Casos representativos trazados a las pruebas automatizadas |
| Línea base | [`Linea-Base-Calidad.md`](Linea-Base-Calidad.md) | Métricas previas y comparación con la medición final |
| Reporte de mejora | [`Reporte-Mejora.md`](Reporte-Mejora.md) | Resultados antes/después, CI y límites documentados |
| Manual técnico SQA | [`Manual-Tecnico.md`](Manual-Tecnico.md) | Pipeline, quality gates y mantenimiento |
| Evidencias | [`evidencia/README.md`](evidencia/README.md) | Enlaces a CI y artefactos; evidencia empresarial va por el canal universitario autorizado |
| Video (4–5 min) | [`Guion-Video.md`](Guion-Video.md) | Guion listo; falta grabar MP4 |
| Presentación (8–10 diapositivas) | [`Presentacion.md`](Presentacion.md) | Estructura lista; falta producir/exportar el PDF |

## Cumplimiento y excepciones registradas

- El pipeline conserva sus tres jobs. La documentación identifica Analyze, Test,
  Build y Report como etapas conceptuales; Report ocurre en los pasos de
  publicación de artefactos dentro de los jobs existentes.
- Ruff es el linter elegido y SonarCloud está activo en `apps/`. La medición
  inicial reportó 22 hallazgos menores `python:S3752`; se corrigieron con métodos
  GET explícitos, pruebas y análisis posterior. `main` quedó con 0 vulnerabilidades
  abiertas y Quality Gate aprobado.
- Se conservan los umbrales actuales de líneas y ramas. La medición final supera
  60 % en ambas métricas.
- Durante la revisión pública, `main` requiere PR y aprobación de los checks de
  Ruff/Django, pruebas/cobertura y Docker. La regla no exige aprobación humana;
  documenta el gate automático para el proyecto individual. Al volver el repo a
  privado se verificará si el plan disponible mantiene la protección.
- La regla está activa: el PR de documentación #1 pasó los tres checks requeridos
  y se fusionó.

## Privacidad

La carpeta no incluye actas firmadas, capturas de personal, datos de clientes,
configuraciones de servidores, secretos ni `.env`. Los originales de aceptación e
implementación se comparten sólo por la plataforma universitaria de acuerdo con
los permisos y políticas aplicables.
