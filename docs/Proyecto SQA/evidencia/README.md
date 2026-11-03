# Evidencias SQA y entrega académica

## Evidencia automatizada disponible

- GitHub Actions **41530067001**, commit `e62f621`: 176 pruebas aprobadas, 83,91 %
  de líneas y 64,81 % de ramas; Ruff, Django, migraciones, coverage gate y build
  Docker pasaron.
- SHA-256 de la imagen Docker de ese run:
  `980891cf64950354d89734a824d93cc5f5e92eddfed8b95d5f4f4dce8c9c0ba2`.
- GitHub Actions **41537327313** ejecutó correctamente el workflow tras la
  actualización documental.
- GitHub Actions **41559042431** pasó Ruff/Django, pruebas/cobertura y build para
  el paquete SQA distribuido. SonarCloud se omitió porque aún no se configuraron
  las variables/secret de la cuenta; no hay métricas Sonar que reportar todavía.
- GitHub Actions **41563792328**, commit de distribución `f722db4`, pasó
  Ruff/Django, migraciones, quality gate de cobertura, 176 pruebas y build Docker.
  SonarCloud se omitió porque faltan sus variables y el secreto.
- Los artifacts de ese run se descargaron a
  `/tmp/opencode/cargotrack-sqa-distribution-41563792328/`. El SHA-256 de Docker es
  `cfc8516d1cae930b72bd9cbf5c4e985ce869eaeba488ffc564b6b40744a93199`; el paquete
  de entrega preparado localmente tiene SHA-256
  `5fe5784e9e2ef13d56154c1eb80dfea1b1406399766b36a7a3a29ed74cc7663d`.
- El [PR #1](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/1) pasó los
  checks requeridos y se fusionó; documentó la regla de protección. El [PR
  #3](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/3) pasó los mismos
  checks y actualizó el manifiesto de artefactos. `main` exige PR y checks durante
  la publicación temporal, sin aprobación humana independiente.
- La última ejecución del repositorio de distribución está enlazada en
  [Actions](https://github.com/yennerx/CargoTrack_v2-distribucion/actions).

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
