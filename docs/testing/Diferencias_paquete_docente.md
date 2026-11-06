# Diferencias entre el paquete docente y el BRD de AutoFix Pro

El paquete (`datos/paquete_docente/`) propone un **modelo de pruebas** y pide no reemplazar los requisitos propios: «Si difieren, documentar las diferencias y adaptar fixtures y oráculos». Este documento registra cómo se adaptó. El adaptador está en `src/infrastructure/paquete_docente.py`; los resultados, en `resultados_casos_prueba.csv` y `resultados_transiciones.csv`.

## 1. Equivalencias

| Paquete docente | AutoFix Pro (BRD) | Cómo se adapta |
|---|---|---|
| Actor / propietario (`actores.csv`) | Cliente Titular (Cliente Particular) | Cada actor se registra como `Cliente`; su usuario tiene rol Cliente Titular. |
| Recurso del catálogo (`catalogo.csv`) | Trabajo de una cotización | Cada línea del detalle es un trabajo con su descripción, cantidad y precio. |
| Operación (`operaciones.csv`) | Orden de Servicio | Se registra el ingreso con un vehículo ficticio derivado de la operación. |
| Detalle de operación | Cotización inicial | Total = Σ(precio × cantidad) con `Decimal` (`Monto`). |
| `autorizado = 1` | Autorización digital del cliente titular | El cliente autoriza todos los trabajos; con `0`, la orden queda en espera. |
| `capacidad_o_stock`, `habilitado = 0` | Necesidad de Refacción sin existencia (RN-07) | Si el recurso no está habilitado o la cantidad excede la existencia, Compras confirma la falta y la orden pasa a «En espera de refacción». |
| RECIBIDA | Recibido | — |
| DIAGNOSTICADA | Diagnosticado | — |
| EN_REPARACION | En reparación | — |
| ENTREGADA | Cerrado | El BRD llama «Cerrado» a la orden entregada y cobrada. |
| CANCELADA | Cerrada sin reparación | Solo existe tras un rechazo total (RN-10). |

## 2. Reglas del paquete sin equivalente en el BRD

| Regla del paquete | Situación en el BRD | Tratamiento |
|---|---|---|
| Actor activo (`activo`) | No existe el concepto de cliente inactivo. | `ActorActivoSpecification` en el adaptador. La columna `precondicion_puede_procesarse` lo reporta, pero el dominio no lo exige. |
| Cliente preferente, promoción y beneficio ≥ 1500 MXN | No existe en el BRD. | `beneficio_de_referencia()` = `ClientePreferente` **y** `TotalMinimo(1500)` **y no** `PromocionActiva`, solo en el adaptador. |
| `puede_procesarse` | Equivale en parte a US-04 (al menos un trabajo) y RN-03 (solo lo autorizado). | `ActorActivo` **y** `DetalleNoVacio` **y** `AutorizacionRegistrada`. |
| Cancelación desde RECIBIDA | El BRD no la contempla; el rechazo total ocurre después de cotizar. | La máquina de estados la rechaza con `TransicionNoPermitida`. |

## 3. Interpretación de las acciones de `transiciones_prueba.csv`

| Acción | Ejecución en AutoFix Pro | Resultado esperado según el BRD |
|---|---|---|
| `aprobar` | Diagnóstico → cotización → autorización digital del titular | «En reparación» |
| `completar` | Lo anterior, más ejecución de trabajos y cierre de caja por el total cobrable | «Cerrado» (ENTREGADA); «En espera de refacción» si falta una pieza; en espera si la operación no tiene autorización |
| `repetir_aprobacion` | Dos autorizaciones de la misma cotización | `DecisionYaRegistrada` (RN-04) |
| `saltar_estado` | Cotizar sin diagnóstico (Recibido → Cotizado) | `TransicionNoPermitida` (RN-01) |
| `cancelar` | Recibido → Cerrada sin reparación | `TransicionNoPermitida` |

## 4. Resultados obtenidos (05/11/2026)

- **Casos (`casos_prueba.csv`):** 60 de `validar_operacion` (43 PASA, 17 NO PASA) y 60 de `evaluar_beneficio` (9 APLICA, 51 NO APLICA). La columna `evidencia` indica el total y la condición que no se cumple.
- **Transiciones:** aprobar 4/4 aceptadas; completar 3 aceptadas y 1 rechazada (AUT-O016 sin autorización); repetir_aprobacion, saltar_estado y cancelar, 12/12 rechazadas con su excepción.

### Diferencias a considerar al comparar con el oráculo del docente

1. **AUT-S001 (AUT-O001):** la orden se completa en el sistema, pero el actor AUT-C014 está inactivo y `puede_procesarse` da NO PASA. El BRD no bloquea clientes inactivos.
2. **AUT-S003 (AUT-O003):** el actor está inactivo; aun así el sistema rechaza la segunda aprobación por RN-04.
3. **AUT-S013 (AUT-O013):** la operación no tiene detalle; la cotización se rechaza porque debe incluir al menos un trabajo y la orden queda «Diagnosticado».
4. **Cancelar:** el paquete espera RECIBIDA → CANCELADA; el BRD no permite cancelar desde Recibido.
