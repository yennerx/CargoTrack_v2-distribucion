# Línea base de calidad — CargoTrack v2

## Línea base

La medición inicial registrada el **2026-10-14** usó el commit `1b47425`, 138
pruebas aprobadas y la cobertura sobre `apps/` (sin migraciones ni archivos de
prueba).

| Indicador inicial | Resultado |
|---|---:|
| Cobertura de líneas/sentencias | 78,60 % (2.862/3.641) |
| Cobertura de ramas | 57,84 % (509/880) |
| Pruebas aprobadas | 138 |
| Análisis estático | Ruff y Django check aprobados según registro |

Los porcentajes se conservaron en `coverage-thresholds.json`; el JSON completo
de la línea base no se archivó. No se reconstruyen resultados retrospectivos.

## Mediciones posteriores

La primera medición posterior fue GitHub Actions run 41530067001 sobre `e62f621`
(176 pruebas). La ejecución de `main` run 41580904162, posterior a corregir DT-SQA-015,
es la medición final que se presenta a continuación. La reejecución 41563792328
sigue siendo evidencia de la versión anterior, no reemplaza la medición final.

| Indicador final | Resultado | Variación |
|---|---:|---:|
| Cobertura de líneas/sentencias | 84,01 % (3.341/3.977) | +5,41 puntos porcentuales |
| Cobertura de ramas | 64,81 % (639/986) | +6,97 puntos porcentuales |
| Pruebas aprobadas | 198 | +60 casos automatizados |
| Ruff | 0 diagnósticos en el reporte JSON de CI | Linter aprobado |

La medición final supera el 60 % en líneas y ramas. Los mínimos configurados se
mantienen en 78,60 % y 57,84 % conforme a la decisión del proyecto. La comparativa
es de dos mediciones, no evidencia de una tendencia sostenida.

## Evidencia

- Baseline/umbrales: `coverage-thresholds.json`, commit `1b47425`.
- Primera ejecución posterior: [GitHub Actions run 41530067001](https://github.com/yennerx/CargoTrack_v2/actions/runs/41530067001), commit `e62f621` (176 pruebas).
- Medición final: [GitHub Actions run 41580904162](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580904162), commit `abd6932` (198 pruebas).
- Reejecución de distribución: [GitHub Actions run 41563792328](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41563792328), commit `f722db4`.
- Regresión adicional de 176 pruebas: registro local del 2026-10-30, commit `31494ca`.
