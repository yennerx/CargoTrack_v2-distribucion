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
- GitHub Actions **41560228982** volvió a pasar los tres jobs en `main`, commit
  `147041cd`. JUnit: 176 pruebas, 0 fallos, 0 errores y 0 omitidas; SonarCloud se
  omitió porque aún no hay configuración de cuenta. Su artifact Docker tiene
  SHA-256 `8fdaa6ab2e064eed5f6a1b257c6d2f08688eab55a8111f13f1b31814393cde91`.
- GitHub Actions **41562695269**, commit de distribución `db28962`, volvió a pasar
  Ruff/Django, pruebas/cobertura PostgreSQL y build Docker; SonarCloud se omitió
  porque falta su configuración.
- Artifacts descargados en `/tmp/opencode/cargotrack-sqa-distribution-41562695269/`.
  SHA-256 del Docker: `7a90f49ca8c82b1084d2b0c27150c684b1d6dc195dcc8ab197760992ed1c9955`.
- El [PR #1](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/1) pasó los
  checks requeridos y se fusionó. La regla de `main` exige PR y esos checks durante
  la publicación temporal.
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
