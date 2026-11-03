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

El pipeline incluye una ejecución SonarCloud opcional, configurada para producir
bugs, code smells, duplicación y Quality Gate. Estas métricas **no se consideran
obtenidas** hasta crear el proyecto, agregar sus variables/secretos de GitHub y
completar una ejecución exitosa. No se atribuyen métricas Sonar al run de baseline
o al run de coverage.

## Limitaciones al corte

- Ruff es el linter elegido y el reporte del run no tuvo diagnósticos.
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
- No se registró una suite E2E automatizada ni análisis de dependencias.

## Referencias

- [CI del código evaluado, run 41530067001](https://github.com/yennerx/CargoTrack_v2/actions/runs/41530067001).
- [CI del paquete SQA en `main`, run 41563792328](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41563792328); SonarCloud se omitió hasta configurar variables y secreto.
- [`Linea-Base-Calidad.md`](Linea-Base-Calidad.md).
