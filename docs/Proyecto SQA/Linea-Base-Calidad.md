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

## Medición posterior

GitHub Actions run 41530067001 sobre `e62f621` produjo estos resultados:

| Indicador final | Resultado | Variación |
|---|---:|---:|
| Cobertura de líneas/sentencias | 83,91 % (3.316/3.952) | +5,31 puntos porcentuales |
| Cobertura de ramas | 64,81 % (639/986) | +6,97 puntos porcentuales |
| Pruebas aprobadas | 176 | +38 casos automatizados |
| Ruff | 0 diagnósticos en el reporte JSON de CI | Linter aprobado |

La medición final supera el 60 % en líneas y ramas. Los mínimos configurados se
mantienen en 78,60 % y 57,84 % conforme a la decisión del proyecto. La comparativa
es de dos mediciones, no evidencia de una tendencia sostenida.

## Evidencia

- Baseline/umbrales: `coverage-thresholds.json`, commit `1b47425`.
- Resultado posterior: [GitHub Actions run 41530067001](https://github.com/yennerx/CargoTrack_v2/actions/runs/41530067001), commit `e62f621`.
- Regresión adicional de 176 pruebas: registro local del 2026-10-30, commit `31494ca`.
