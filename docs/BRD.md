# BRD — AutoFix Pro

**Equipo 6 · Componentes de Lógica de Negocio · PIA**
Josue Yahir Vela Hernandez (2142881) · Osweld Omar Lozano Martínez (2142366) · Sylvia Yadira González Parra (2142962)

> **Origen y vigencia.** Este documento refina el BRD de la Unidad 2 (`Unidad 2 AutoFixPro/AutoFixPro copy.pdf`, 04/09/2026) e incorpora los hallazgos de la Unidad 3 (`Unidad 3 AutoFixPro/docs/InformeDeArquitectura.pdf`, 17/10/2026). Las decisiones D1–D10 (sección 11) son **supuestos del caso**: AutoFix Pro es una empresa ficticia y el stakeholder fue simulado. Cada regla indica su origen: `P#` = pregunta del levantamiento de la U2, `US-##` = historia de la U2, `H#` = hallazgo de la U3, `D#` = decisión del equipo registrada en este documento.

---

## 1. Contexto del negocio y problema principal

AutoFix Pro es un taller mecánico que genera ingresos por diagnóstico, mano de obra y venta de refacciones, y atiende tanto a clientes particulares como a flotillas empresariales. Recibe entre 15 y 20 vehículos por día; un diagnóstico toma entre 30 y 60 minutos (P5).

El proceso actual de autorización y seguimiento es manual y telefónico (P1). Esto provoca:

- disputas sobre si un trabajo fue autorizado o no, por falta de evidencia (P2);
- poca visibilidad del estado del vehículo para el cliente, que debe llamar para saber en qué va (P2);
- retrasos por refacciones que no se comunican oportunamente.

**Oportunidad:** digitalizar y dejar trazabilidad de cada autorización, mostrar el estado del vehículo en tiempo real y estandarizar el manejo de excepciones (fallas adicionales, refacciones sin existencia, cambios de fecha, rechazo de cotización y falta de respuesta del cliente).

## 2. Stakeholders

| Stakeholder | Rol en el proceso | Interés principal |
|---|---|---|
| Cliente particular | Autoriza o rechaza trabajos y paga el servicio | Transparencia, rapidez y confianza en lo cotizado |
| Cliente de flotilla | Autoriza a través de un responsable de cuenta | Continuidad operativa de su flotilla, facturación consolidada |
| Asesor de servicio | Recibe el vehículo, genera y envía cotizaciones, comunica fechas | Evidencia clara de cada autorización, menos llamadas repetidas |
| Técnico | Diagnostica, ejecuta trabajos autorizados y reporta fallas adicionales | Instrucciones claras de qué está autorizado a trabajar |
| Compras | Gestiona refacciones sin existencia y su recepción | Visibilidad temprana de necesidades de refacciones |
| Caja | Cobra y cierra la orden; genera la facturación de flotillas | Información correcta y completa de lo que se debe cobrar |
| Gerente del taller | Recibe escalamientos, revisa disputas y consulta indicadores | Reportes confiables e indicadores de desempeño |

## 3. Alcance

### 3.1 Incluye

1. Registro de ingreso del vehículo, evidencia fotográfica y diagnóstico.
2. Generación y envío digital de cotizaciones inicial y complementaria.
3. Autorización digital total, parcial o rechazo total, decidida por trabajo.
4. Registro inmutable de cada decisión de autorización.
5. Gestión de fallas adicionales y de ampliaciones sobre trabajos autorizados (umbral del 20%).
6. Gestión de refacciones sin existencia: orden de compra, espera, recepción y reanudación.
7. Escalamiento al gerente cuando el cliente no responde en 24 horas.
8. Notificaciones al cliente sobre cotizaciones, estado y cambios de fecha.
9. Consulta del estado del vehículo por el cliente.
10. Registro de disputas y reportes/indicadores para el gerente.
11. Cobro y cierre de la orden; facturación mensual consolidada y prioridad contractual para flotillas.

### 3.2 No incluye

| Elemento | Motivo / origen |
|---|---|
| Nómina del personal | Fuera del proceso de servicio (P19) |
| Contabilidad general / fiscal | Fuera del proceso de servicio (P19) |
| Marketing o campañas a clientes | BRD U2 |
| Cargo por custodia de vehículos no recogidos | Política no definida por el negocio (P14, H2); se excluye de esta versión (D9) |
| Operación sin conexión y sincronización posterior | La versión requiere conexión para registrar cambios (D9, H3) |
| Medición de satisfacción por encuestas | Sin origen en el levantamiento ni datos asociados (D8) |

## 4. Necesidades del negocio

| ID | Necesidad | Origen |
|---|---|---|
| BN-01 | Reducir disputas por trabajos autorizados mediante evidencia digital de cada autorización. | Problema observado (P2) |
| BN-02 | Aumentar la visibilidad del estado del vehículo para clientes y asesores en tiempo real. | Problema observado (P2) |
| BN-03 | Comunicar oportunamente al cliente los retrasos causados por falta de refacciones. | Problema observado |
| BN-04 | Registrar formalmente las fallas adicionales detectadas durante la reparación y su autorización. | Levantamiento (P10, P12) |
| BN-05 | Permitir la gestión de flotillas con reglas de autorización y facturación diferenciadas. | Levantamiento (P8, P16) |
| BN-06 | Estandarizar el proceso de cotización y aprobación total, parcial o rechazo de trabajos. | Levantamiento (P4, P11) |

## 5. Restricciones

1. El personal utilizará el sistema desde tablets o iPads dentro del taller.
2. La conexión a internet puede no ser estable. **Consecuencia (D9):** si no hay conexión, el sistema no registra autorizaciones ni cambios de estado; el usuario debe reintentar al recuperar la conexión.
3. En las primeras fases la adquisición de hardware puede ser limitada.

## 6. Criterios de éxito

| # | Criterio | Origen | Cómo se mide en el sistema |
|---|---|---|---|
| CE-1 | Reducción medible de disputas por autorizaciones no documentadas dentro de los primeros 3 meses de uso. | P17, P18 | Número de disputas registradas por periodo (US-24, US-15). |
| CE-2 | Comunicación de retrasos por falta de refacción en menos de 2 horas desde que se detecta la falta de existencia. | P18 | Diferencia entre la hora de registro de la falta y la hora del aviso al cliente (US-13, US-15). |
| CE-3 | 100% de las autorizaciones registradas con evidencia digital. | P18 | El sistema no acepta decisiones sin registro de autorización (RN-04); el reporte muestra el porcentaje (US-15). |

El criterio de satisfacción por encuestas de la U2 queda fuera de alcance (D8).

## 7. Reglas de negocio

| ID | Regla | Origen |
|---|---|---|
| RN-01 | No se genera una cotización sin un diagnóstico registrado para la orden de servicio. | P4, US-03 |
| RN-02 | Solo el cliente titular o el responsable de cuenta registrado de una flotilla puede autorizar o rechazar trabajos. El técnico y el asesor no autorizan trabajos ni montos; el asesor envía la cotización y da seguimiento. | P8, P15, US-16, D7 |
| RN-03 | La decisión se toma por trabajo. Solo los trabajos en estado `Autorizado` pueden ejecutarse; los rechazados quedan documentados y no se ejecutan. | P11, US-05, US-06, US-08 |
| RN-04 | Cada decisión (autorización o rechazo) genera un registro de autorización inmutable con autorizador, fecha, hora, trabajos decididos y evidencia digital. Una decisión registrada no se modifica. | US-07, P18 |
| RN-05 | Una falla adicional se reporta al asesor, genera una cotización complementaria y sus trabajos quedan `Pendiente de autorización` hasta que el cliente los autorice, sin importar su monto. | P10, US-09, US-10, D4 |
| RN-06 | Una ampliación sobre trabajos ya autorizados requiere autorización explícita adicional cuando el monto acumulado de ampliaciones supera el 20% del total autorizado de la cotización inicial. Exactamente 20% no supera el umbral. | P12, H4, D4 |
| RN-07 | Si una refacción requerida no tiene existencia, Compras genera una orden de compra a proveedor; el trabajo y la orden pasan a `En espera de refacción` y se notifica al cliente una nueva fecha estimada. | P9, US-11, US-12, US-13 |
| RN-08 | Al recibir la refacción, Compras registra la recepción; el trabajo vuelve a `Autorizado` y la orden regresa a `En reparación` cuando ya no quedan refacciones pendientes. | D6 |
| RN-09 | Si pasan 24 horas desde el envío de una cotización sin respuesta del cliente, la orden pasa a `En espera de cliente` y se notifica al gerente del taller. | P13, D5 |
| RN-10 | Si el cliente rechaza todos los trabajos de la cotización inicial, no se realiza ninguna reparación. El diagnóstico se cobra solo si el cliente aceptó su cargo al ingreso; tras resolver ese cobro, la orden termina en `Cerrada sin reparación`. | US-05/06, D3 |
| RN-11 | Caja solo cobra trabajos en estado `Terminado` (más el diagnóstico aceptado, si aplica). Trabajos rechazados, pendientes o no realizados no se cobran. | US-19, D2 |
| RN-12 | Los clientes de flotilla tienen un responsable de cuenta con autorización delegada, facturación mensual consolidada y prioridad de atención cuando su contrato la establece. | P16, US-16, US-17, US-18 |
| RN-13 | La facturación consolidada agrupa, por cliente de flotilla y mes, las órdenes en estado `Cerrado`; una orden no puede incluirse en dos facturaciones. | US-17, U3 §4.3 |
| RN-14 | Una orden en `Cerrado` o `Cerrada sin reparación` es terminal y no puede reabrirse. | D1 |
| RN-15 | Una disputa es un caso registrado por el cliente o el gerente que cuestiona una autorización o un cobro de una orden; se registra con categoría, descripción, fecha y resolución. | Glosario U2 (19), D8 |
| RN-16 | La evidencia fotográfica de ingreso y de entrega se registra en la orden; en esta versión es recomendada, no obligatoria. | P7, US-02, US-20 |

## 8. Ciclo de vida

### 8.1 Estados de la orden de servicio (D1)

| Estado | Se entra cuando… | Salidas permitidas |
|---|---|---|
| Recibido | El asesor registra el ingreso del vehículo. | Diagnosticado |
| Diagnosticado | El técnico guarda el diagnóstico. | Cotizado |
| Cotizado | El asesor genera la cotización inicial. | En espera de autorización |
| En espera de autorización | La cotización (inicial o complementaria) se envía al cliente. | En reparación; En espera de cliente; Cerrada sin reparación |
| En espera de cliente | Pasan 24 horas sin respuesta (RN-09). | En reparación; Cerrada sin reparación |
| En reparación | Existe al menos un trabajo autorizado. | En espera de refacción; En espera de autorización (cotización complementaria); Listo para entrega |
| En espera de refacción | Falta una refacción para un trabajo autorizado (RN-07). | En reparación (RN-08) |
| Listo para entrega | Todos los trabajos autorizados están `Terminado` y no hay trabajos pendientes de autorización ni refacciones pendientes. | Cerrado |
| Cerrado | Caja confirma el pago, o la orden de flotilla queda lista para su facturación consolidada. | — (terminal) |
| Cerrada sin reparación | Rechazo total de la cotización inicial y cobro del diagnóstico resuelto (RN-10). | — (terminal) |

Notas:

- Si el cliente rechaza toda una **cotización complementaria**, la orden regresa a `En reparación` y continúa con los trabajos ya autorizados.
- Una respuesta tardía del cliente (desde `En espera de cliente`) se procesa igual que una respuesta a tiempo.
- La transición a `Listo para entrega` se deriva de D1/D2: ocurre cuando se cumple la condición de la tabla.

### 8.2 Estados del trabajo (D2)

| Estado | Significado | Salidas permitidas |
|---|---|---|
| Pendiente de autorización | Trabajo cotizado sin decisión del cliente. | Autorizado; Rechazado |
| Autorizado | El cliente lo aprobó; puede iniciarse si tiene refacciones. | En ejecución; En espera de refacción |
| Rechazado | El cliente no lo aprobó; queda documentado y no se ejecuta ni se cobra. | — (terminal) |
| En espera de refacción | Autorizado, pero falta una pieza. | Autorizado (al recibir la pieza) |
| En ejecución | El técnico lo inició. | Terminado |
| Terminado | El técnico lo concluyó; es el único estado cobrable. | — (terminal) |

## 9. Historias de usuario y criterios de aceptación

Las historias US-01 a US-20 conservan la numeración de la U2. US-21 a US-24 se agregan por las decisiones D3, D5, D6 y D8.

| ID | Rol | Quiero | Para | BN | RN |
|---|---|---|---|---|---|
| US-01 | Asesor de servicio | registrar los datos del cliente y del vehículo | dejar constancia formal del estado en que se recibió el vehículo | BN-06 | — |
| US-02 | Asesor de servicio | adjuntar evidencia fotográfica del vehículo al ingreso | contar con respaldo del estado inicial y evitar disputas | BN-01 | RN-16 |
| US-03 | Técnico | registrar el diagnóstico asociado a la orden | que el asesor pueda generar la cotización | BN-06 | RN-01 |
| US-04 | Asesor de servicio | generar una cotización a partir del diagnóstico | presentarla al cliente para su autorización | BN-06 | RN-01 |
| US-05 | Cliente | recibir y revisar la cotización de forma digital | decidir si autorizo, rechazo o autorizo parcialmente los trabajos | BN-06 | RN-02, RN-03 |
| US-06 | Cliente | autorizar únicamente algunos de los trabajos cotizados | controlar el gasto y posponer o rechazar lo que no me interesa | BN-06 | RN-03 |
| US-07 | Asesor de servicio | que cada decisión del cliente quede registrada digitalmente con fecha, hora y detalle | contar con evidencia verificable ante cualquier disputa | BN-01 | RN-04 |
| US-08 | Técnico | ver y ejecutar únicamente los trabajos autorizados | evitar reparaciones no aprobadas | BN-06 | RN-03 |
| US-09 | Técnico | reportar una falla adicional detectada durante la reparación | que el asesor genere una cotización complementaria | BN-04 | RN-05 |
| US-10 | Asesor de servicio | generar una cotización complementaria o solicitar reautorización de una ampliación | obtener la autorización antes de continuar con esa parte del trabajo | BN-04 | RN-05, RN-06 |
| US-11 | Compras | generar una orden de compra a proveedor cuando una refacción no tenga existencia | continuar la reparación en cuanto la pieza esté disponible | BN-03 | RN-07 |
| US-12 | Compras | marcar el vehículo como "En espera de refacción" | que el estado sea visible para el asesor y el cliente | BN-03 | RN-07 |
| US-13 | Asesor de servicio | notificar al cliente una nueva fecha estimada de entrega | mantenerlo informado oportunamente | BN-03 | RN-07 |
| US-14 | Cliente | consultar en tiempo real el estado de mi vehículo | no depender de llamadas telefónicas | BN-02 | — |
| US-15 | Gerente del taller | visualizar reportes e indicadores del proceso | dar seguimiento a los criterios de éxito | BN-02 | RN-15 |
| US-16 | Responsable de Cuenta | autorizar cotizaciones de los vehículos de mi cuenta | agilizar la operación sin depender de cada conductor | BN-05 | RN-02, RN-12 |
| US-17 | Caja | generar la facturación consolidada mensual de flotillas | cumplir con el esquema de cobro pactado en contrato | BN-05 | RN-12, RN-13 |
| US-18 | Asesor de servicio | identificar y priorizar vehículos de flotilla con prioridad contractual | cumplir los acuerdos de servicio | BN-05 | RN-12 |
| US-19 | Caja | consultar el detalle de lo autorizado y realizado | cobrar correctamente al cliente al momento de la entrega | BN-06 | RN-11 |
| US-20 | Asesor de servicio | registrar evidencia fotográfica a la entrega | dejar constancia del estado final y evitar disputas | BN-01 | RN-16 |
| US-21 | Cliente | rechazar toda la cotización | no pagar reparaciones que no quiero, solo el diagnóstico que acepté | BN-06 | RN-10 |
| US-22 | Gerente del taller | recibir un aviso cuando un cliente no responde en 24 horas | dar seguimiento a las autorizaciones detenidas | BN-02 | RN-09 |
| US-23 | Compras | registrar la recepción de una refacción | que el trabajo se reanude y el cliente sepa que continúa | BN-03 | RN-08 |
| US-24 | Cliente | registrar una disputa sobre una autorización o un cobro | que el taller la revise y la resuelva con evidencia | BN-01 | RN-15 |

### Criterios de aceptación (Gherkin)

```gherkin
Característica: US-01 Registro de ingreso del vehículo
  Escenario: ingreso con datos completos
    Dado que un vehículo llega físicamente al taller
    Cuando el asesor captura cliente, placa, marca, modelo, VIN, kilometraje, nivel de combustible, daños visibles y motivo de ingreso
    Entonces el sistema crea una orden de servicio en estado "Recibido"
    Y registra la fecha y hora de ingreso

  Escenario: ingreso con datos incompletos
    Dado que el asesor está registrando un ingreso
    Cuando omite un dato obligatorio del vehículo
    Entonces el sistema no crea la orden e indica el dato faltante
```

```gherkin
Característica: US-02 Evidencia fotográfica al ingreso
  Escenario: fotografías adjuntas al ingreso
    Dado una orden de servicio en estado "Recibido"
    Cuando el asesor adjunta una o más fotografías del vehículo
    Entonces las fotografías quedan asociadas a la orden con etapa "Ingreso"
    Y son consultables por el cliente y el gerente
```

```gherkin
Característica: US-03 Registro de diagnóstico
  Escenario: diagnóstico registrado
    Dado una orden de servicio en estado "Recibido"
    Cuando el técnico guarda el diagnóstico con la falla encontrada
    Entonces la orden cambia a estado "Diagnosticado"

  Escenario: diagnóstico vacío
    Dado una orden de servicio en estado "Recibido"
    Cuando el técnico intenta guardar un diagnóstico sin falla descrita
    Entonces el sistema rechaza el registro y la orden permanece en "Recibido"
```

```gherkin
Característica: US-04 Generación de cotización
  Escenario: cotización a partir del diagnóstico
    Dado una orden en estado "Diagnosticado"
    Cuando el asesor genera la cotización con uno o más trabajos y sus montos
    Entonces la orden cambia a "Cotizado"
    Y cada trabajo queda en estado "Pendiente de autorización"
    Y al enviarse al cliente la orden pasa a "En espera de autorización"

  Escenario: cotización sin diagnóstico
    Dado una orden en estado "Recibido" sin diagnóstico
    Cuando el asesor intenta generar una cotización
    Entonces el sistema rechaza la operación (RN-01)
```

```gherkin
Característica: US-05 / US-06 Autorización total o parcial
  Escenario: autorización parcial
    Dado una cotización con varios trabajos en "Pendiente de autorización"
    Y el usuario es el cliente titular de la orden
    Cuando autoriza algunos trabajos y rechaza los demás
    Entonces los autorizados pasan a "Autorizado" y los demás a "Rechazado"
    Y la orden cambia a "En reparación"

  Escenario: autorización total
    Dado una cotización con trabajos en "Pendiente de autorización"
    Cuando el cliente titular autoriza todos los trabajos
    Entonces todos los trabajos pasan a "Autorizado"
    Y la orden cambia a "En reparación"

  Escenario: autorizador no válido
    Dado una cotización en espera de autorización
    Cuando un usuario que no es titular ni responsable de cuenta registrado intenta decidirla
    Entonces el sistema rechaza la operación sin cambiar el estado de los trabajos

  Escenario: el técnico intenta autorizar
    Dado una cotización en espera de autorización
    Cuando un técnico intenta autorizar un trabajo
    Entonces el sistema rechaza la operación (RN-02)
```

```gherkin
Característica: US-07 Registro inmutable de la decisión
  Escenario: decisión registrada
    Dado que el cliente decide uno o más trabajos
    Cuando se confirma la decisión
    Entonces el sistema crea un registro de autorización con autorizador, fecha, hora, trabajos autorizados, trabajos rechazados y evidencia digital

  Escenario: intento de modificar una decisión
    Dado una cotización ya decidida
    Cuando alguien intenta registrar otra decisión sobre los mismos trabajos
    Entonces el sistema la rechaza y conserva el registro original
```

```gherkin
Característica: US-08 Ejecución solo de trabajos autorizados
  Escenario: consulta del técnico
    Dado una orden con trabajos "Autorizado", "Pendiente de autorización" y "Rechazado"
    Cuando el técnico consulta la orden
    Entonces solo los trabajos "Autorizado" aparecen como ejecutables

  Escenario: inicio y término de un trabajo autorizado
    Dado un trabajo en estado "Autorizado" con sus refacciones disponibles
    Cuando el técnico lo inicia
    Entonces el trabajo pasa a "En ejecución"
    Cuando el técnico lo concluye
    Entonces el trabajo pasa a "Terminado"

  Escenario: intento de ejecutar un trabajo no autorizado
    Dado un trabajo en "Pendiente de autorización" o "Rechazado"
    Cuando el técnico intenta iniciarlo
    Entonces el sistema rechaza la operación (RN-03)

  Escenario: orden lista para entrega
    Dado una orden "En reparación"
    Cuando el último trabajo autorizado pasa a "Terminado" y no hay trabajos pendientes de autorización ni refacciones pendientes
    Entonces la orden cambia a "Listo para entrega"
```

```gherkin
Característica: US-09 / US-10 Falla adicional y cotización complementaria
  Escenario: falla adicional
    Dado una orden "En reparación"
    Cuando el técnico reporta una falla no incluida en el diagnóstico original
    Entonces el asesor genera una cotización complementaria vinculada a la orden
    Y sus trabajos quedan en "Pendiente de autorización" sin importar su monto (RN-05)
    Y la orden cambia a "En espera de autorización"

  Escenario: rechazo de la cotización complementaria
    Dado una cotización complementaria en espera de autorización
    Cuando el cliente rechaza todos sus trabajos
    Entonces esos trabajos quedan "Rechazado"
    Y la orden regresa a "En reparación" con los trabajos ya autorizados
```

```gherkin
Característica: US-10 Ampliación sobre trabajos autorizados (umbral del 20%)
  Escenario: ampliación igual al umbral
    Dado una cotización inicial con $10,000.00 autorizados
    Cuando la ampliación acumulada llega a $2,000.00 (20%)
    Entonces no se requiere autorización adicional

  Escenario: ampliación mayor al umbral
    Dado una cotización inicial con $10,000.00 autorizados
    Cuando la ampliación acumulada llega a $2,000.01
    Entonces la ampliación queda pendiente de autorización explícita del cliente
    Y el trabajo ampliado no puede continuar hasta obtenerla (RN-06)
```

```gherkin
Característica: US-11 / US-12 Refacción sin existencia
  Escenario: falta de existencia
    Dado un trabajo "Autorizado" que requiere una refacción
    Cuando Compras confirma que la refacción no tiene existencia
    Entonces el sistema genera una orden de compra a proveedor
    Y el trabajo pasa a "En espera de refacción"
    Y la orden cambia a "En espera de refacción"
```

```gherkin
Característica: US-13 Notificación de nueva fecha de entrega
  Escenario: aviso de retraso
    Dado una orden en "En espera de refacción"
    Cuando el asesor registra una nueva fecha estimada de entrega y el motivo
    Entonces el sistema notifica al cliente la nueva fecha
    Y guarda la hora de la falta detectada y la hora del aviso (CE-2)

  Escenario: nueva fecha inválida
    Dado una orden en "En espera de refacción"
    Cuando el asesor registra una fecha anterior a la fecha actual
    Entonces el sistema rechaza la fecha
```

```gherkin
Característica: US-14 Consulta del estado del vehículo
  Escenario: cliente consulta su orden
    Dado un cliente con una orden de servicio activa
    Cuando consulta el estado de su vehículo
    Entonces el sistema muestra el estado actual, los trabajos y su estado, y la fecha estimada de entrega

  Escenario: cliente consulta una orden ajena
    Dado un cliente autenticado
    Cuando intenta consultar una orden de otro cliente
    Entonces el sistema niega el acceso
```

```gherkin
Característica: US-15 Reportes e indicadores
  Escenario: indicadores del periodo
    Dado que el gerente accede al módulo de reportes
    Cuando selecciona un periodo
    Entonces el sistema muestra el número de disputas registradas
    Y el tiempo promedio entre la falta de refacción detectada y el aviso al cliente
    Y el porcentaje de decisiones de autorización con evidencia digital

  Escenario: usuario sin permiso
    Dado un usuario que no es gerente
    Cuando intenta consultar los reportes
    Entonces el sistema niega el acceso
```

```gherkin
Característica: US-16 Autorización delegada en flotillas
  Escenario: responsable de cuenta autoriza
    Dado un vehículo registrado bajo una cuenta de flotilla
    Cuando el responsable de cuenta registrado autoriza la cotización
    Entonces el sistema acepta la autorización
    Y la registra con el rol "Responsable de Cuenta"

  Escenario: contacto no registrado
    Dado un vehículo de flotilla
    Cuando un usuario no registrado como responsable de esa cuenta intenta autorizar
    Entonces el sistema rechaza la operación
```

```gherkin
Característica: US-17 Facturación consolidada mensual
  Escenario: consolidación del mes
    Dado un cliente de flotilla con órdenes en "Cerrado" durante el mes
    Cuando Caja genera la facturación del periodo
    Entonces el sistema consolida esas órdenes en un solo documento de cobro

  Escenario: orden ya facturada
    Dado una orden incluida en una facturación consolidada
    Cuando Caja genera de nuevo la facturación del mismo periodo
    Entonces la orden no se incluye dos veces (RN-13)
```

```gherkin
Característica: US-18 Prioridad contractual de flotillas
  Escenario: vehículo con prioridad pactada
    Dado un vehículo de una flotilla cuyo contrato establece prioridad
    Cuando el asesor consulta la cola de atención
    Entonces el sistema señala visiblemente la prioridad contractual
    Y lo ubica antes que los vehículos sin prioridad cuya atención aún no inicia
```

```gherkin
Característica: US-19 Cobro y cierre
  Escenario: cobro de lo realizado
    Dado una orden en "Listo para entrega"
    Cuando Caja abre la orden para cobro
    Entonces el sistema muestra solo los trabajos "Terminado" y el diagnóstico aceptado, si aplica
    Y no muestra trabajos rechazados ni pendientes (RN-11)
    Y al confirmarse el pago la orden cambia a "Cerrado"
```

```gherkin
Característica: US-20 Evidencia fotográfica a la entrega
  Escenario: fotografías de entrega
    Dado una orden en "Listo para entrega"
    Cuando el asesor adjunta fotografías del vehículo
    Entonces quedan asociadas a la orden con etapa "Entrega"
```

```gherkin
Característica: US-21 Rechazo total de la cotización
  Escenario: rechazo total con diagnóstico aceptado
    Dado una cotización inicial en espera de autorización
    Y el cliente aceptó al ingreso el cargo de diagnóstico
    Cuando el cliente rechaza todos los trabajos
    Entonces todos los trabajos quedan "Rechazado" y no se inicia ninguna reparación
    Y Caja cobra únicamente el diagnóstico
    Y al confirmarse el pago la orden cambia a "Cerrada sin reparación"

  Escenario: rechazo total sin cargo de diagnóstico
    Dado una cotización inicial en espera de autorización
    Y el cliente no aceptó cargo de diagnóstico
    Cuando el cliente rechaza todos los trabajos
    Entonces la orden cambia a "Cerrada sin reparación" sin cobro
```

```gherkin
Característica: US-22 Escalamiento por falta de respuesta
  Escenario: antes de 24 horas
    Dado una cotización enviada hace 23 horas y 59 minutos sin respuesta
    Cuando el sistema revisa los plazos
    Entonces la orden permanece en "En espera de autorización"

  Escenario: 24 horas sin respuesta
    Dado una cotización enviada hace 24 horas sin respuesta
    Cuando el sistema revisa los plazos
    Entonces la orden cambia a "En espera de cliente"
    Y el gerente recibe una notificación una sola vez

  Escenario: respuesta tardía
    Dado una orden en "En espera de cliente"
    Cuando el cliente autoriza al menos un trabajo
    Entonces la orden cambia a "En reparación"
```

```gherkin
Característica: US-23 Recepción de refacción
  Escenario: refacción recibida
    Dado una orden en "En espera de refacción" con una orden de compra abierta
    Cuando Compras registra la recepción de la refacción
    Entonces el trabajo vuelve a "Autorizado"
    Y si no quedan refacciones pendientes la orden cambia a "En reparación"
    Y el cliente es notificado de que el trabajo continúa

  Escenario: recepción duplicada
    Dado una orden de compra ya recibida
    Cuando Compras intenta registrar de nuevo su recepción
    Entonces el sistema rechaza la operación
```

```gherkin
Característica: US-24 Registro de disputas
  Escenario: cliente registra una disputa
    Dado un cliente con acceso a su orden
    Cuando registra una disputa con categoría "Autorización" o "Cobro" y una descripción
    Entonces la disputa queda registrada con fecha y en estado "Abierta"

  Escenario: gerente resuelve la disputa
    Dado una disputa "Abierta"
    Cuando el gerente registra la resolución
    Entonces la disputa cambia a "Resuelta" con la fecha y el texto de la resolución
```

## 10. Glosario de dominio

| # | Término | Definición |
|---|---|---|
| 1 | Orden de Servicio (OS) | Registro central que da seguimiento al vehículo desde su ingreso hasta su cierre. |
| 2 | Asesor de Servicio | Rol que recibe al cliente, captura el ingreso, genera y envía cotizaciones y comunica cambios. |
| 3 | Técnico | Rol que diagnostica el vehículo, ejecuta los trabajos autorizados y reporta fallas adicionales. |
| 4 | Diagnóstico | Registro del técnico con las fallas encontradas; es requisito para cotizar. |
| 5 | Trabajo | Unidad de reparación cotizada con descripción y monto; recibe una decisión individual del cliente. |
| 6 | Cotización Inicial | Propuesta económica emitida tras el diagnóstico, que requiere decisión del cliente antes de iniciar cualquier trabajo. |
| 7 | Cotización Complementaria | Propuesta económica generada por una falla adicional detectada durante la reparación. |
| 8 | Ampliación | Aumento del monto de trabajos ya autorizados; si el acumulado supera el 20% del total autorizado de la cotización inicial, requiere autorización adicional. |
| 9 | Autorización Digital | Decisión formal del cliente, por medio electrónico, que aprueba o rechaza trabajos cotizados. |
| 10 | Registro de Autorización | Constancia inmutable de una decisión: autorizador, fecha, hora, trabajos decididos y evidencia. |
| 11 | Aprobación Parcial | Decisión en la que el cliente autoriza solo una parte de los trabajos cotizados. |
| 12 | Rechazo Total | Decisión en la que el cliente rechaza todos los trabajos de la cotización inicial. |
| 13 | Evidencia Digital | Fotografías o registros electrónicos que respaldan el estado del vehículo o las decisiones del cliente. |
| 14 | Falla Adicional | Avería no detectada en el diagnóstico inicial y descubierta durante la reparación. |
| 15 | Refacción sin Existencia | Pieza necesaria para un trabajo autorizado que no se encuentra en el inventario. |
| 16 | Orden de Compra (OC) | Documento que Compras emite a un proveedor para adquirir una refacción sin existencia. |
| 17 | Recepción de Refacción | Registro de Compras que confirma la llegada de la pieza y libera el trabajo en espera. |
| 18 | Cliente Particular | Propietario individual de un vehículo que solicita servicio directamente. |
| 19 | Cliente de Flotilla | Empresa con varios vehículos registrados y condiciones especiales de autorización y facturación. |
| 20 | Responsable de Cuenta | Persona registrada por un cliente de flotilla con autorización delegada para decidir cotizaciones. |
| 21 | Prioridad Contractual | Condición del contrato de una flotilla que adelanta la atención de sus vehículos aún no iniciados. |
| 22 | En Espera de Refacción | Estado en el que la reparación se detiene por falta de una pieza. |
| 23 | En Espera de Cliente | Estado de la orden cuando pasan 24 horas sin respuesta a una cotización. |
| 24 | Listo para Entrega | Estado de la orden cuando todos los trabajos autorizados están terminados y no hay pendientes. |
| 25 | Cerrada sin Reparación | Estado terminal de una orden cuyo cliente rechazó toda la cotización inicial. |
| 26 | Facturación Consolidada | Documento de cobro mensual que agrupa las órdenes cerradas de una misma flotilla. |
| 27 | Cierre de Caja | Subproceso donde se liquida el saldo de la orden y se genera la comprobación de pago. |
| 28 | Tiempo de Comunicación de Retraso | Tiempo entre la detección de una falta de refacción y el aviso al cliente (meta: menos de 2 horas). |
| 29 | Disputa | Caso registrado que cuestiona una autorización o un cobro de una orden. |
| 30 | Inspección de Ingreso | Captura, en cada ingreso, de kilometraje, nivel de combustible, daños visibles y motivo de ingreso. |
| 31 | Cliente Titular | Cliente propietario de la orden de servicio; puede autorizar o rechazar sus trabajos. |
| 32 | Evidencia Fotográfica | Fotografías del vehículo asociadas a la orden en la etapa de ingreso o de entrega. |
| 33 | Necesidad de Refacción | Pieza que requiere un trabajo autorizado; indica si tiene existencia o no. |
| 34 | Plazo de Respuesta | Las 24 horas que tiene el cliente para decidir una cotización enviada antes de escalar al gerente. |
| 35 | Cola de Atención | Lista de órdenes cuya atención aún no inicia, ordenada por prioridad contractual y fecha de ingreso. |
| 36 | Compras | Rol que confirma la falta de existencia, emite órdenes de compra y registra la recepción de refacciones. |
| 37 | Caja | Rol que cobra las órdenes, las cierra y genera la facturación consolidada. |
| 38 | Gerente del Taller | Rol que recibe escalamientos, resuelve disputas y consulta indicadores. |

## 11. Registro de decisiones del caso

| ID | Decisión | Sustituye o resuelve |
|---|---|---|
| D1 | Estados de la orden según la sección 8.1, incluido `Cerrada sin reparación`. | Indefinición de transiciones (U2 US-14 con 8 estados vs. modelo con 9; U3 §3 vs. ADR-001). |
| D2 | Estados del trabajo según la sección 8.2; solo `Terminado` es cobrable. | US-19 cobraba lo "ejecutado" sin estado que lo representara. |
| D3 | Rechazo total: no se repara; diagnóstico cobrable solo si se aceptó al ingreso; cierre como `Cerrada sin reparación` (RN-10, US-21). | Criterio US-05/06 sin desenlace para "ninguno". |
| D4 | Umbral del 20% acumulado sobre el total autorizado de la cotización inicial; exactamente 20% no lo supera; toda falla adicional requiere autorización (RN-05, RN-06). | P12 (monto de cotización) vs. U3 (por trabajo); hallazgo H4 y supuesto pendiente de U3 §4.5-6. |
| D5 | Escalamiento a las 24 horas: `En espera de cliente` y aviso al gerente (RN-09, US-22). | P13 sin historia, sin BPMN y sin carril de Gerente (H1). |
| D6 | Recepción de refacción y reanudación (RN-08, US-23). | Ruta de regreso a reparación ausente en U2 y U3. |
| D7 | Solo el cliente titular o el responsable de cuenta autoriza; el asesor envía y da seguimiento (RN-02). | P15 ("aprobación del asesor y del cliente") vs. US-05 y BPMN. |
| D8 | Registro de disputas (RN-15, US-24); encuestas de satisfacción fuera de alcance. | US-15 pedía contar disputas sin forma de registrarlas; criterio de éxito 4 sin origen. |
| D9 | Custodia y operación sin conexión fuera de alcance. | P14 y H2 (custodia); H3 (conexión inestable). |
| D10 | Tecnología: Python, FastAPI, SQLAlchemy, PostgreSQL con Docker Compose, pytest, GitHub Actions y despliegue en Render. Se documenta como ADR en `docs/architecture/`. | U3 implementada en React/JS; el PIA requiere Docker, CI/CD y despliegue. |

## 12. Trazabilidad necesidad → historia → regla

| BN | Historias | Reglas | Criterio de éxito |
|---|---|---|---|
| BN-01 | US-02, US-07, US-20, US-24 | RN-04, RN-15, RN-16 | CE-1, CE-3 |
| BN-02 | US-14, US-15, US-22 | RN-09 | CE-1, CE-2, CE-3 |
| BN-03 | US-11, US-12, US-13, US-23 | RN-07, RN-08 | CE-2 |
| BN-04 | US-09, US-10 | RN-05, RN-06 | CE-3 |
| BN-05 | US-16, US-17, US-18 | RN-02, RN-12, RN-13 | — |
| BN-06 | US-01, US-03, US-04, US-05, US-06, US-08, US-19, US-21 | RN-01, RN-02, RN-03, RN-10, RN-11, RN-14 | CE-1 |

La trazabilidad completa hasta BPMN, modelo de dominio, API y pruebas se documenta en `docs/architecture/`.
