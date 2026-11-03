# Entregables del Proyecto Final SQA — CargoTrack v2

Este paquete organiza los entregables académicos conforme a las directrices del
Proyecto Final SQA 2026. El documento original del curso se conserva en el
repositorio privado de desarrollo y no se distribuye con el código. CargoTrack es
una aplicación existente del Proyecto de Graduación; SQA comparte su código y sus
pruebas, sin crear una segunda aplicación.

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
- Ruff es el linter elegido. SonarCloud se configuró para el panel de bugs, code
  smells, duplicación y cobertura; su ejecución se activa cuando el proyecto y el
  secreto se configuren en GitHub.
- Se conservan los umbrales actuales de líneas y ramas. La medición final supera
  60 % en ambas métricas.
- La protección de `main` se verificará durante la publicación temporal pública.
  Si no está disponible al regresar el repositorio a privado, se documentará como
  limitación; no se afirmará que existe una regla que no esté activa.

## Privacidad

La carpeta no incluye actas firmadas, capturas de personal, datos de clientes,
configuraciones de servidores, secretos ni `.env`. Los originales de aceptación e
implementación se comparten sólo por la plataforma universitaria de acuerdo con
los permisos y políticas aplicables.
