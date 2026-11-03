# Reporte de mejora — CargoTrack v2

## Resultado antes/después

| Métrica | Antes | Después | Cambio |
|---|---:|---:|---:|
| Pruebas automatizadas aprobadas | 138 | 176 | +38 |
| Cobertura de líneas | 78,60 % | 83,91 % | +5,31 puntos porcentuales |
| Cobertura de ramas | 57,84 % | 64,81 % | +6,97 puntos porcentuales |
| Ruff | Ejecución local registrada | 0 diagnósticos en CI | Análisis automatizado |

La medición final corresponde al run 41530067001 sobre `e62f621`. JUnit registró
176 pruebas aprobadas, sin fallos, errores ni omisiones. Pasaron Ruff, Django,
migraciones y el comparador de cobertura; se construyó un artefacto Docker con
SHA-256.

## Defectos corregidos

Entre los hallazgos validados constan la administración de permisos individuales
por un usuario staff no superusuario (DT-SQA-011), la visibilidad de datos de
autorización/pago de comisiones (DT-SQA-012), contactos adicionales en clientes
(DT-SQA-013) y la renovación de sesión causada por recursos estáticos
(DT-SQA-014). Los commits y pruebas se registran en `docs/DEUDA_TECNICA_SQA.md`
del repositorio privado de desarrollo.

## Métricas SonarCloud

La primera ejecución SonarCloud CI fue el run `41574835164` sobre el commit
`ad1c2def`, con el proyecto escaneado bajo scope `apps/` (7.825 NCLOC). El Quality
Gate `Sonar way` quedó **OK para código nuevo**. El resumen actual reporta:

| Métrica SonarCloud | Resultado |
|---|---:|
| Bugs abiertos | 0 |
| Vulnerabilidades abiertas | 22, todas severidad MINOR/impacto bajo |
| Code smells abiertos | 0 |
| Duplicación | 0,3 % |
| Coverage Sonar | 80,1 % |

Los 22 hallazgos de la regla `python:S3752` se revisaron uno por uno: las vistas
afectadas son exclusivamente de consulta/descarga, incluidos los reportes CSV por
GET. Se añadió `require_GET` a las 22 vistas y una prueba parametrizada confirma
que POST responde HTTP 405 en todas ellas. La regresión local posterior aprobó 198
pruebas. La resolución queda pendiente de confirmación por un nuevo análisis
SonarCloud de esta rama. El scope `apps/` no incluye `templates/`, `static/`,
Dockerfile ni workflows. Coverage Sonar es una métrica agregada, distinta de
pytest-cov (83,91 % líneas y 64,81 % ramas, medición anterior).

## Limitaciones al corte

- Ruff es el linter elegido y el reporte CI no tuvo diagnósticos.
- El Quality Gate de cobertura conserva los mínimos de baseline; la medición final
  los supera. No se cambian umbrales.
- Durante la publicación temporal, `main` exige PR y los tres checks CI. La regla
  no requiere aprobación humana independiente. Al volver el repositorio a privado,
  verificar si GitHub mantiene la protección con el plan disponible. El PR de
  documentación #1 pasó los checks requeridos y se fusionó.
- No se hizo auditoría independiente de la infraestructura LAN, configuración de
  servidor ni respaldos productivos debido a la política de TI.
- El acta documenta aceptación con observaciones. El soporte adicional ofrecido es
  una cortesía fuera del alcance inicial, no un defecto ni criterio SQA pendiente.
- No se registró una suite E2E automatizada ni prueba de penetración. El workflow
  no tiene un job separado de análisis de dependencias.

## Referencias

- [CI del código evaluado, run 41530067001](https://github.com/yennerx/CargoTrack_v2/actions/runs/41530067001).
- [CI del paquete SQA en `main`, run 41563792328](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41563792328).
- [SonarCloud CI run 41574835164](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41574835164) y [dashboard del proyecto](https://sonarcloud.io/project/overview?id=yennerx_CargoTrack_v2-distribucion).
- [`Linea-Base-Calidad.md`](Linea-Base-Calidad.md).
