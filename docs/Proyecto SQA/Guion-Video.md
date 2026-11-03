# Guion de grabación — demostración del Proyecto SQA

**Duración objetivo:** 4:25 minutos. Mantener entre 4:00 y 5:00.

**Formato de entrega:** MP4, mínimo 720p, narración clara.

**Estilo:** grabación de pantalla con voz; el guion hablado se puede repetir
literalmente o adaptar manteniendo las cifras y el alcance comprobados.

## Preparación antes de grabar

1. Abrir estas páginas en pestañas separadas:
   - PR [#6 — restricción de métodos HTTP](https://github.com/yennerx/CargoTrack_v2-distribucion/pull/6).
   - [CI del PR, run 41580576891](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580576891).
   - [CI de `main`, run 41580904162](https://github.com/yennerx/CargoTrack_v2-distribucion/actions/runs/41580904162).
   - [Dashboard SonarCloud](https://sonarcloud.io/project/overview?id=yennerx_CargoTrack_v2-distribucion).
2. Iniciar sesión previamente en GitHub/SonarCloud y comprobar que el dashboard
   enseña 0 vulnerabilidades abiertas, coverage 80,2 %, 0 bugs y 0 code smells.
3. Preparar el PR #6 en la vista **Files changed**: enfocar un ejemplo de
   `require_GET` y la prueba parametrizada de 22 rutas; no desplazarse por todo el diff.
4. En la vista **Checks** del PR, dejar visibles los resultados exitosos de Ruff/
   Django, pruebas PostgreSQL y SonarCloud. En el run de `main`, dejar listos los
   tres jobs: análisis, pruebas y build Docker.
5. Preparar una diapositiva o imagen comparativa: línea base 138 / 78,60 % / 57,84 %;
   estado posterior 198 / 84,01 % / 64,81 %.
6. Cerrar pestañas que no se mostrarán. No abrir secretos, configuración de cuenta,
   `.env`, datos reales ni pantallas de administración productiva.

Las capturas del repositorio, del código de prueba, de GitHub Actions y del
dashboard pueden incluirse: corresponden a desarrollo/SQA y datos de prueba. Si
se usa información visual de CargoTrack, emplear únicamente registros `DEMO-` o
datos ficticios.

## Comandos opcionales para abrir evidencia

Se pueden ejecutar antes de grabar para abrir las páginas en el navegador; no
modifican ramas ni crean nuevos pull requests:

```bash
gh pr view 6 --repo yennerx/CargoTrack_v2-distribucion --web
gh run view 41580576891 --repo yennerx/CargoTrack_v2-distribucion --web
gh run view 41580904162 --repo yennerx/CargoTrack_v2-distribucion --web
```

El video muestra el flujo real ya ejecutado en el PR #6; no se debe fingir que se
está creando un PR nuevo ni presentar una grabación como ejecución en vivo.

## Secuencia y texto para narrar

### 0:00–0:30 — Introducción (30 s)

**En pantalla:** portada con CargoTrack v2, curso SQA, estudiante y objetivo.

**Narración sugerida:**

> Hola, soy Yenner Américo Hernández Pérez. En esta presentación explico el
> aseguramiento de calidad integrado a CargoTrack v2, una aplicación existente
> desarrollada con Django y PostgreSQL. El objetivo fue automatizar pruebas,
> análisis estático y controles de cobertura en cada cambio, y conservar evidencia
> verificable de sus resultados.

### 0:30–2:10 — Cambio y flujo del pipeline (100 s)

**En pantalla, en este orden:** PR #6 → resumen y rama → *Files changed* → *Checks*;
después, abrir el run 41580904162 y mostrar los tres jobs terminados.

**Narración sugerida:**

> Este es el pull request número 6, trabajado en la rama `fix/sonar-http-methods`.
> Se originó al revisar 22 hallazgos de SonarCloud que pedían declarar los métodos
> HTTP aceptados. Al revisar los contratos, confirmé que esas vistas eran de
> consulta o descarga. Por eso añadí `require_GET`; las acciones que modifican
> información conservaron sus métodos existentes.
>
> También añadí una prueba parametrizada para las 22 rutas. La prueba comprueba que
> cada endpoint responda HTTP 405 ante POST. Aquí se ve un ejemplo del cambio y el
> conjunto de casos. El pull request ejecutó Ruff y las comprobaciones Django,
> pruebas y cobertura en PostgreSQL, y análisis SonarCloud. Todos los checks
> pasaron. El PR se integró en `main` como `abd6932`.
>
> Después del merge, el run 41580904162 volvió a ejecutar el flujo en `main`.
> Analyze ejecuta Ruff y Django check; Test prepara PostgreSQL, aplica y verifica
> migraciones, corre pytest y cobertura y espera el Quality Gate de SonarCloud.
> Build empaqueta la imagen Docker como artefacto, sin publicarla ni desplegarla.
> Los reportes JUnit, cobertura y Ruff se publican como artefactos de Actions.

**Acciones/clics:** mostrar claramente los estados `success`; expandir brevemente
los nombres de los jobs. Evitar dejar la vista detenida en logs extensos.

### 2:10–3:00 — Dashboard SonarCloud (50 s)

**En pantalla:** dashboard actual; luego, si el sitio lo permite, abrir la vista de
issues `python:S3752` o el análisis del PR #6.

**Narración sugerida:**

> En la medición inicial, SonarCloud reportó 22 vulnerabilidades menores de la
> regla `python:S3752`. El análisis posterior del pull request y de `main` confirmó
> que quedaron cerradas: actualmente hay cero vulnerabilidades abiertas. El
> dashboard muestra además cero bugs, cero code smells, 0,3 por ciento de
> duplicación y 80,2 por ciento de cobertura Sonar. Sonar analiza el código fuente
> del scope `apps/`; su cobertura es distinta a la medición de líneas y ramas de
> pytest-cov.

### 3:00–3:40 — Comparación cuantitativa (40 s)

**En pantalla:** tabla o gráfico antes/después; señalar líneas y ramas por separado.

**Narración sugerida:**

> La línea base del 14 de octubre registró 138 pruebas, 78,60 por ciento de
> cobertura de líneas y 57,84 por ciento de ramas. En la ejecución de `main` tras
> la corrección, JUnit registró 198 pruebas aprobadas, sin fallos, errores ni
> omisiones. La cobertura fue 84,01 por ciento de líneas y 64,81 por ciento de
> ramas. Son mejoras de 5,41 y 6,97 puntos porcentuales respectivamente. La
> cobertura mide ejecución y no garantiza por sí sola ausencia de defectos.

### 3:40–4:25 — Conclusiones y límites (45 s)

**En pantalla:** 3 conclusiones y, al final, enlaces a CI y documentación.

**Narración sugerida:**

> Como resultado, CargoTrack cuenta con una CI repetible sobre PostgreSQL, checks
> de calidad y artefactos asociados al commit. La corrección de los métodos HTTP
> quedó cubierta por pruebas y verificada por un nuevo análisis SonarCloud.
> Permanecen actividades registradas como deuda: ampliar las mediciones de carga,
> automatizar respaldos y cubrir el comando de datos demo. No se afirma una prueba
> de penetración ni una auditoría de infraestructura productiva. Gracias.

## Lista de capturas recomendadas

| Archivo sugerido | Pantalla | Uso |
|---|---|---|
| `sqa-pr-06-checks.png` | PR #6 con checks aprobados | Mostrar revisión automática del cambio |
| `sqa-pr-06-diff.png` | `require_GET` y prueba parametrizada | Explicar la corrección concreta |
| `sqa-actions-main-41580904162.png` | Los tres jobs de `main` en verde | Evidenciar el flujo completo |
| `sqa-sonarcloud-actual.png` | Dashboard actual y vulnerabilidades 0 | Exponer el resultado SonarCloud |
| `sqa-coverage-comparativa.png` | Línea base frente a run 41580904162 | Comunicar las métricas |

Las imágenes se pueden insertar en la presentación Markdown con `![Descripción](ruta)`
cuando se hayan capturado. No se han creado capturas nuevas ni se presentan
marcadores como si fueran evidencia.

## Control final antes de exportar

- Duración entre 4 y 5 minutos; MP4 de al menos 720p.
- Se ven rama/PR, cambio, checks y resultado posterior al merge.
- Se muestran métricas actuales y baseline con sus ejecuciones asociadas.
- La narración distingue cobertura pytest-cov de coverage Sonar.
- No aparecen secretos, `.env`, datos empresariales, firmas ni configuración LAN.
- Verificar audio, legibilidad de capturas, enlaces y reproducción completa.
