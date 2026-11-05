# Matriz de trazabilidad — AutoFix Pro

**Equipo 6 · Componentes de Lógica de Negocio · PIA**

Cada fila sigue una historia desde la necesidad del negocio hasta su verificación. Fuentes: `docs/BRD.md` (BN, US, RN, CE), `docs/bpmn/BPMN_AutoFixPro_v2.drawio` (tareas BPMN), `docs/architecture/Arquitectura.md` (dominio, casos de uso, API) y `docs/architecture/ADRs.md`.

La columna **Prueba de aceptación** contiene el nombre de la prueba automatizada en `tests/unit/test_historias.py`. **Resultado registrado el 05/11/2026:** todas aprobadas (363 pruebas en total, cobertura 93.40 %; evidencia en `docs/testing/evidencias/`).

## 1. Necesidad → criterio de éxito

| BN | Necesidad | Historias | Criterio de éxito | Indicador (US-15) |
|---|---|---|---|---|
| BN-01 | Reducir disputas con evidencia digital | US-02, US-07, US-20, US-24 | CE-1, CE-3 | Disputas por periodo; % de decisiones con evidencia digital |
| BN-02 | Visibilidad del estado del vehículo | US-14, US-15, US-22 | CE-1, CE-2, CE-3 | — |
| BN-03 | Comunicar retrasos por refacciones | US-11, US-12, US-13, US-23 | CE-2 | Tiempo de comunicación de retraso |
| BN-04 | Registrar fallas adicionales y su autorización | US-09, US-10 | CE-3 | % de decisiones con evidencia digital |
| BN-05 | Gestión de flotillas | US-16, US-17, US-18 | — | — |
| BN-06 | Estandarizar cotización y aprobación | US-01, US-03, US-04, US-05, US-06, US-08, US-19, US-21 | CE-1 | — |

## 2. Historia → regla → proceso → dominio → caso de uso → API → prueba

| US | RN | Tarea BPMN v2 | Dominio (Aggregate · Specification · estado) | Caso de uso · Service | API | Prueba de aceptación (aprobada) |
|---|---|---|---|---|---|---|
| US-01 | — | Registrar ingreso del vehículo y fotos de ingreso | `OrdenDeServicio`, `InspeccionDeIngreso`, `Vehiculo` · → `Recibido` · `VehiculoRecibido` | CU-01 · `RegistrarIngresoService` | `POST /ordenes-de-servicio` | `test_us01_registro_de_ingreso_crea_orden_recibido`, `test_us01_ingreso_con_datos_incompletos_se_rechaza` |
| US-02 | RN-16 | Registrar ingreso del vehículo y fotos de ingreso | `EvidenciaFotografica` (etapa Ingreso) | CU-04 · `RegistrarEvidenciaFotograficaService` | `POST .../evidencias-fotograficas` | `test_us02_evidencia_fotografica_de_ingreso` |
| US-03 | RN-01 | Registrar diagnóstico | `Diagnostico` · → `Diagnosticado` · `DiagnosticoRegistrado` | CU-01 · `RegistrarDiagnosticoService` | `POST .../diagnostico` | `test_us03_diagnostico_cambia_a_diagnosticado`, `test_us03_diagnostico_vacio_se_rechaza` |
| US-04 | RN-01 | Generar y enviar cotización inicial | `Cotizacion` (Inicial) · `OrdenCotizableSpecification` · → `Cotizado` → `En espera de autorización` | CU-01 · `GenerarCotizacionService` | `POST .../cotizaciones` (genera y envía) | `test_us04_cotizacion_inicial_deja_trabajos_pendientes`, `test_us04_cotizacion_sin_diagnostico_se_rechaza` |
| US-05 | RN-02, RN-03 | Autorización digital: decidir cotización por trabajo | `AutorizadorValidoSpecification` · `DecisionCompletaSpecification` · → `En reparación` | CU-01 · `AutorizarTrabajosService` | `POST .../autorizacion-digital` | `test_us05_autorizacion_total`, `test_us05_autorizador_no_valido_se_rechaza`, `test_us05_tecnico_no_puede_autorizar` |
| US-06 | RN-03 | Autorización digital: decidir cotización por trabajo | `Trabajo` → `Autorizado` / `Rechazado` | CU-01 · `AutorizarTrabajosService` | `POST .../autorizacion-digital` | `test_us06_autorizacion_parcial` |
| US-07 | RN-04 | Autorización digital: decidir cotización por trabajo (objeto de datos: Registro de autorización) | `RegistroDeAutorizacion` (inmutable) | CU-01 · `AutorizarTrabajosService` | `POST .../autorizacion-digital` | `test_us07_registro_de_autorizacion_completo`, `test_us07_decision_ya_registrada_no_se_modifica` |
| US-08 | RN-03 | Ejecutar trabajo autorizado; ¿Quedan trabajos autorizados sin terminar? | `TrabajoEjecutableSpecification` · `OrdenListaParaEntregaSpecification` · `Trabajo` → `En ejecución` → `Terminado` · orden → `Listo para entrega` | CU-04 · `EjecutarTrabajoService` | `GET .../trabajos?ejecutables=true`, `POST .../inicio`, `POST .../terminacion` | `test_us08_solo_trabajos_autorizados_son_ejecutables`, `test_us08_trabajo_no_autorizado_no_inicia`, `test_us08_ultimo_trabajo_terminado_deja_listo_para_entrega` |
| US-09 | RN-05 | Reportar falla adicional → Generar cotización complementaria | `Cotizacion` (Complementaria) · `PoliticaAutorizacionEstandar` · → `En espera de autorización` · `FallaAdicionalReportada` | CU-02 · `ReportarFallaAdicionalService` | `POST .../fallas-adicionales`, `POST .../cotizaciones-complementarias` | `test_us09_falla_adicional_crea_cotizacion_complementaria`, `test_us09_rechazo_complementaria_regresa_a_en_reparacion` |
| US-10 | RN-05, RN-06 | Solicitar reautorización de ampliación; Autorización digital: decidir cotización complementaria o ampliación | `Ampliacion` · `AmpliacionSuperaUmbralSpecification` · `PoliticaAutorizacionAmpliacion` | CU-02 · `SolicitarReautorizacionDeAmpliacionService` | `POST .../ampliaciones`, `POST .../ampliaciones/{id}/autorizacion-digital` | `test_us10_ampliacion_20_por_ciento_no_requiere_autorizacion`, `test_us10_ampliacion_mayor_20_por_ciento_bloquea_trabajo` |
| US-11 | RN-07 | ¿Refacciones con existencia? → Generar orden de compra | `NecesidadDeRefaccion` · `RefaccionSinExistenciaDetectada` · `OrdenDeCompra` (Solicitada) | CU-03 · `MarcarEsperaDeRefaccionService` + `SolicitarRefaccionAProveedorService` | `POST .../necesidad-de-refaccion` | `test_us11_falta_de_existencia_genera_orden_de_compra`, `test_us11_orden_de_compra_no_se_duplica` |
| US-12 | RN-07 | Generar orden de compra y marcar En espera de refacción | `Trabajo` y orden → `En espera de refacción` | CU-03 · `MarcarEsperaDeRefaccionService` | `POST .../necesidad-de-refaccion` | `test_us12_orden_en_espera_de_refaccion` |
| US-13 | RN-07 | Notificar nueva fecha de entrega al cliente | `OrdenDeServicio.nueva_fecha_estimada` · `NuevaFechaEntregaNotificada` · `INotificacionCliente` | CU-03 · `NotificarNuevaFechaEntregaService` | `POST .../nueva-fecha-de-entrega` | `test_us13_nueva_fecha_notifica_al_cliente`, `test_us13_fecha_anterior_a_hoy_se_rechaza` |
| US-14 | — | (anotación) | `ConsultarEstadoVehiculoQuery` | Query | `GET /ordenes-de-servicio/{id}` | `test_us14_cliente_consulta_su_orden`, `test_us14_orden_ajena_acceso_negado` |
| US-15 | RN-15 | (anotación) | `ObtenerIndicadoresQuery` (Table Module) | Query | `GET /indicadores` | `test_us15_indicadores_del_periodo`, `test_us15_solo_gerente_consulta_indicadores` |
| US-16 | RN-02, RN-12 | Autorización digital: decidir cotización por trabajo | `ClienteFlotilla.validar_autorizador()` · rol `Responsable de Cuenta` | CU-05 · `AutorizarTrabajosService` | `POST .../autorizacion-digital` | `test_us16_responsable_de_cuenta_autoriza`, `test_us16_contacto_no_registrado_se_rechaza` |
| US-17 | RN-12, RN-13 | Cerrar orden e incluirla en la facturación consolidada | `FacturacionConsolidada` · `OrdenFacturableSpecification` | CU-05 · `GenerarFacturacionConsolidadaService` | `POST /facturaciones-consolidadas` | `test_us17_consolida_ordenes_cerradas_del_mes`, `test_us17_orden_no_se_factura_dos_veces` |
| US-18 | RN-12 | (anotación) | `ServicioDePriorizacion` · `ConsultarColaDeAtencionQuery` | Query | `GET /cola-de-atencion` | `test_us18_prioridad_contractual_primero_en_cola_de_atencion` |
| US-19 | RN-11 | Cobrar trabajos terminados y cerrar orden | `TrabajoCobrableSpecification` · → `Cerrado` · `OrdenDeServicioCerrada` | CU-04 · `CerrarOrdenDeServicioService`, `ObtenerDetalleParaCobroQuery` | `GET .../detalle-para-cobro`, `POST .../cierre-de-caja` | `test_us19_solo_se_cobran_trabajos_terminados`, `test_us19_pago_cierra_la_orden` |
| US-20 | RN-16 | Registrar fotos de entrega; orden Listo para entrega | `EvidenciaFotografica` (etapa Entrega) | CU-04 · `RegistrarEvidenciaFotograficaService` | `POST .../evidencias-fotograficas` | `test_us20_evidencia_fotografica_de_entrega` |
| US-21 | RN-10, RN-14 | ¿Diagnóstico aceptado al ingreso? → Cobrar solo el diagnóstico → Orden Cerrada sin reparación | `RechazoTotalRegistrado` · → `Cerrada sin reparación` | CU-04 · `AutorizarTrabajosService`, `CerrarOrdenDeServicioService` | `POST .../autorizacion-digital`, `POST .../cierre-de-caja` | `test_us21_rechazo_total_con_diagnostico_aceptado`, `test_us21_rechazo_total_sin_cargo`, `test_rn14_orden_cerrada_no_se_reabre` |
| US-22 | RN-09 | Temporizador 24 h sin respuesta → Recibir aviso: orden En espera de cliente | `PlazoDeRespuestaVencidoSpecification` · `ServicioDeEscalamiento` · → `En espera de cliente` · `PlazoDeRespuestaVencido` | CU-06 · `ProcesarPlazosDeRespuestaService` | `POST /plazos-de-respuesta/procesamiento` | `test_us22_23h59_no_escala`, `test_us22_24h_escala_y_notifica_una_vez`, `test_us22_respuesta_tardia_pasa_a_en_reparacion` |
| US-23 | RN-08 | Llega la refacción → Registrar recepción de refacción | `OrdenDeCompra` → `Recibida` · `RefaccionRecibida` → `ReparacionReanudada` · trabajo → `Autorizado` · orden → `En reparación` | CU-03 · `RegistrarRecepcionDeRefaccionService` + `ReanudarReparacionService` | `POST /ordenes-de-compra/{id}/recepcion-de-refaccion` | `test_us23_recepcion_reanuda_reparacion`, `test_us23_recepcion_duplicada_se_rechaza` |
| US-24 | RN-15 | Cliente registra disputa → Revisar evidencia y resolver disputa | `Disputa` (`Abierta` → `Resuelta`) | CU-07 · `RegistrarDisputaService`, `ResolverDisputaService` | `POST /disputas`, `POST /disputas/{id}/resolucion` | `test_us24_cliente_registra_disputa`, `test_us24_gerente_resuelve_disputa` |

## 3. Regla → dónde se garantiza

| RN | Specification / invariante | Aggregate | ADR |
|---|---|---|---|
| RN-01 | `OrdenCotizableSpecification` | `OrdenDeServicio` | ADR-005 |
| RN-02 | `AutorizadorValidoSpecification` → `validar_autorizador()` | `Cliente` / `ClienteFlotilla` | ADR-003, ADR-005 |
| RN-03 | `DecisionCompletaSpecification`, `TrabajoEjecutableSpecification` | `OrdenDeServicio` | ADR-005, ADR-006 |
| RN-04 | `RegistroDeAutorizacion` inmutable; solo inserción | `OrdenDeServicio` | ADR-009 |
| RN-05 | `PoliticaAutorizacionEstandar` | `OrdenDeServicio` | ADR-004 |
| RN-06 | `AmpliacionSuperaUmbralSpecification` en `PoliticaAutorizacionAmpliacion` | `OrdenDeServicio` | ADR-004, ADR-005 |
| RN-07 | `RefaccionSinExistenciaDetectada` | `OrdenDeServicio`, `OrdenDeCompra` | ADR-002, ADR-010 |
| RN-08 | `RefaccionRecibida` | `OrdenDeCompra`, `OrdenDeServicio` | ADR-002, ADR-010 |
| RN-09 | `PlazoDeRespuestaVencidoSpecification`, `ServicioDeEscalamiento` | `OrdenDeServicio` | ADR-005, ADR-013 |
| RN-10 | Transición a `Cerrada sin reparación` | `OrdenDeServicio` | ADR-006 |
| RN-11 | `TrabajoCobrableSpecification` | `OrdenDeServicio` | ADR-005 |
| RN-12 | `ClienteFlotilla`, `ServicioDePriorizacion` | `Cliente` | ADR-003 |
| RN-13 | `OrdenFacturableSpecification` | `FacturacionConsolidada` | ADR-005 |
| RN-14 | Estados terminales en `TRANSICIONES_PERMITIDAS` | `OrdenDeServicio` | ADR-006 |
| RN-15 | `Disputa` y su ciclo `Abierta` → `Resuelta` | `Disputa` | — |
| RN-16 | `EvidenciaFotografica` | `OrdenDeServicio` | — |

## 4. Cobertura

- Las 24 historias tienen regla o indicador, tarea BPMN o anotación, elemento de dominio, caso de uso, endpoint y al menos una prueba automatizada aprobada.
- Las 16 reglas están garantizadas en al menos un Aggregate o Specification.
- Ningún componente de la arquitectura queda sin historia o regla que lo justifique.
