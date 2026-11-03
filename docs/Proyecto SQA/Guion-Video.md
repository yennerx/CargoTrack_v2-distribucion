# Guion del video de demostración SQA (4–5 minutos)

| Tiempo | Contenido |
|---|---|
| 0:00–0:35 | Presentar CargoTrack, objetivo SQA, alcance y commit evaluado. |
| 0:35–1:15 | Mostrar repositorio de distribución, workflow actual de tres jobs y su mapeo a Analyze/Test/Build/Report. |
| 1:15–2:20 | Mostrar run Actions: Ruff, Django, PostgreSQL/migraciones, pytest, coverage gate y build Docker. |
| 2:20–3:20 | Mostrar el dashboard SonarCloud actual: 0 bugs y vulnerabilidades abiertas, Quality Gate aprobado y coverage. Explicar la línea base de 22 hallazgos `python:S3752`, la corrección con `require_GET` y el análisis que confirmó su cierre; aclarar scope `apps/`. |
| 3:20–4:05 | Comparar línea base y final; mencionar correcciones y deuda pendiente. |
| 4:05–4:40 | Exponer limitaciones documentadas: protección de rama según visibilidad/plan y auditoría LAN restringida. |
| 4:40–5:00 | Conclusiones y lecciones aprendidas. |

Subir el MP4 final a la plataforma universitaria. No mostrar tokens, `.env`, datos
de clientes, nombres/firmas del acta ni configuración empresarial restringida.
