# Matriz de pruebas — CargoTrack v2

La suite automatizada contiene 176 pruebas; esta matriz muestra casos
representativos y enlaza con sus archivos fuente. El resultado observado agregado
corresponde al JUnit del run 41530067001, commit `e62f621`: 176 pasaron, 0 fallaron,
0 errores y 0 omitidas.

| ID | Tipo | Módulo/prueba fuente | Entrada y precondición | Resultado esperado | Resultado observado |
|---|---|---|---|---|---|
| TC-ACC-01 | Integración/regresión | `apps/accounts/tests.py` | Cuenta demo activa con credenciales válidas | Se inicia sesión y se accede a páginas protegidas; respuesta privada no se cachea | Pasó en CI |
| TC-ACC-02 | Autorización/auditoría | `test_staff_administrator_can_manage_individual_permission_assignments` | Administrador `is_staff`, no superusuario, modifica permiso individual | Cambio permitido según regla y evento auditado | Pasó en CI |
| TC-ORD-01 | Regresión/autorización | `test_order_cannot_be_assigned_until_dispatcher_confirms_proposed_carrier` | Orden con transportista propuesto sin confirmación Dispatcher | El servidor bloquea `Asignada` | Pasó en CI |
| TC-ORD-02 | Regresión | `test_invalid_order_status_transition_is_rejected` | Orden recibe una transición no permitida | Transición rechazada sin alterar el estado | Pasó en CI |
| TC-DOC-01 | Autorización/integración | `test_broker_cannot_open_or_download_documents_of_unassigned_carriers` | Broker intenta abrir/descargar expediente fuera de su ámbito | Acceso y descarga denegados | Pasó en CI |
| TC-DOC-02 | Validación | `apps/documents/tests.py` | Archivo con extensión, firma o contenido no permitido | Carga rechazada sin crear versión parcial | Pasó en CI |
| TC-FIN-01 | Autorización | `test_only_dispatcher_confirms_financial_transaction` | Usuario que no es Dispatcher intenta confirmar movimiento | Acción rechazada y estado sin cambios | Pasó en CI |
| TC-FIN-02 | Autorización/auditoría | `test_only_administrative_manager_validates_summary` | Gerencia no administrativa valida resumen financiero | Acción denegada; validación autorizada queda auditada | Pasó en CI |
| TC-FIN-03 | Integración/regresión | `test_commission_views_calculate_list_detail_authorize_and_pay` | Comisión elegible y resumen validado | Cálculo, autorización y registro de pago respetan rol y estado | Pasó en CI |
| TC-REP-01 | Autorización/regresión | `test_broker_reports_are_scoped_before_filtering_and_rendering` | Broker filtra reporte que podría incluir registros de otro ámbito | Sólo aparecen registros autorizados antes de filtrar/renderizar | Pasó en CI |
| TC-REP-02 | Seguridad/regresión | `test_customer_report_exports_are_audited_and_csv_formula_values_are_safe` | CSV incluye valores con caracteres de fórmula | Exportación neutraliza fórmulas y queda auditada | Pasó en CI |
| TC-SQA-01 | Unitario/quality gate | `scripts/test_check_coverage.py` | Cobertura sintética debajo y encima de mínimos | El comparador rechaza incumplimiento y acepta cumplimiento | Pasaron sus 4 pruebas |

## Distribución de los 176 casos

| Módulo | Casos | Módulo | Casos |
|---|---:|---|---:|
| Cuentas | 28 | Auditoría | 10 |
| Catálogos | 6 | Core | 15 |
| Clientes | 13 | Transportistas | 12 |
| Órdenes | 24 | Documentos | 6 |
| Incidencias | 6 | Finanzas | 29 |
| Reportes | 23 | Comparador de cobertura | 4 |
| **Total** | **176** |  |  |

Las sesiones manuales por rol y el acta firmada son evidencia de aceptación
separada de esta matriz automatizada. Sus originales se entregan por la
plataforma universitaria, no en este repositorio.
