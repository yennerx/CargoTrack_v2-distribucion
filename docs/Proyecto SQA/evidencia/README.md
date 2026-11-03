# Evidencias SQA y entrega académica

## Evidencia automatizada disponible

- GitHub Actions **41565119050**, commit `ad1c2def`: Ruff/Django, migraciones,
  coverage gate, 176 pruebas (0 fallos/errores/omitidas) y build Docker pasaron.
  pytest-cov registró 83,91 % de líneas y 64,81 % de ramas; Ruff JSON fue `[]`.
- SHA-256 de la imagen Docker de ese run:
  `82c6f5437acdc125593750ea6d94c80eed8a61a7f9fddd801ebea12b07c55fbd`.
- GitHub Actions **41574835164**, mismo commit, ejecutó SonarCloud. Quality Gate
  Sonar way: `OK` para código nuevo. En scope `apps/`: 0 bugs, 22 vulnerabilidades
  menores abiertas, 0 code smells, 0,3 % de duplicación y 80,1 % de coverage Sonar.
  En el dashboard inicial había 22 vulnerabilidades `python:S3752`. El PR #6
  añadió `require_GET` a las vistas identificadas y prueba rechazo POST; el
  análisis posterior de `main` cerró los 22 hallazgos. El run **41580904162** pasó
  Ruff/Django, pruebas/cobertura PostgreSQL, SonarCloud y build Docker. Dashboard:
  [SonarQube Cloud](https://sonarcloud.io/project/overview?id=yennerx_CargoTrack_v2-distribucion).
- Los artifacts CI del run 415651 se descargaron a
  `/tmp/opencode/cargotrack-sqa-distribution-41565119050/`; el paquete agrupado
  para la universidad está en
  `/tmp/opencode/CargoTrack_SQA_artifacts_run41565119050_ad1c2def.tar.gz` y su
  SHA-256 es `7738e26e0367cf25b680eb62e4ab09f389b1b5274b5f1b3406b58d93536cef38`.
  Estos archivos no se versionan.
- El [PR #1](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/1) pasó los
  checks requeridos y se fusionó; documentó la regla de protección. El [PR
  #4](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/4) pasó los mismos
  checks y actualizó el manifiesto de artefactos. `main` exige PR y checks durante
  la publicación temporal, sin aprobación humana independiente.
- La última ejecución del repositorio de distribución está enlazada en
  [Actions](https://github.com/yennerx/CargoTrack_v2-distribucion/actions).
- El [PR #6](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/6) corrigió
  los hallazgos de métodos HTTP y se fusionó en `abd6932`; el análisis de `main`
  quedó registrado en [run 41580904162](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580904162).

La descarga local de coverage, JUnit, Ruff JSON e imagen Docker se prepara fuera
del repositorio para cargarla en la plataforma universitaria antes de la
expiración de Actions.

## Evidencia empresarial

El acta de aceptación y el informe de implementación existen como originales
protegidos fuera del seguimiento de Git. El acta documenta aceptación con
observaciones; la oferta de soporte es cortesía fuera del alcance inicial. Por
política de TI no se reproduce la configuración productiva ni capturas adicionales
del servidor. Entregar los originales sólo en la plataforma autorizada y conforme
a las políticas de la empresa; no copiarlos a este directorio.

## Entregables multimedia

- MP4 de 4–5 minutos: usar [`Guion-Video.md`](../Guion-Video.md); falta grabar.
- PDF de 8–10 diapositivas: usar [`Presentacion.md`](../Presentacion.md); falta
  producir/exportar.
