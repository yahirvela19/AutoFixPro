# Architecture Decision Records — AutoFix Pro

**Equipo 6 · Componentes de Lógica de Negocio · PIA**

ADR-001 a ADR-004 provienen de la Unidad 3 (`Unidad 3 AutoFixPro/docs/ADR.pdf`) y se conservan **aceptados**; solo se agrega una nota de actualización cuando una decisión del BRD vigente (D1–D10) los afecta. ADR-005 en adelante se agregan para el PIA. Los términos del negocio siguen el glosario de `docs/BRD.md` y la correspondencia de `Arquitectura.md` §1.

| ADR | Título | Estado |
|---|---|---|
| ADR-001 | Selección del patrón de lógica de negocio | Aceptada (U3) |
| ADR-002 | Separar la gestión de refacción sin existencia en dos servicios | Aceptada (U3), actualizada |
| ADR-003 | Autorización polimórfica en Cliente/ClienteFlotilla | Aceptada (U3) |
| ADR-004 | Política intercambiable para el umbral de autorización (20%) | Aceptada (U3), actualizada |
| ADR-005 | Specification para las reglas de negocio | Aceptada |
| ADR-006 | Máquinas de estado explícitas para la orden y el trabajo | Aceptada |
| ADR-007 | Plataforma tecnológica y despliegue | Aceptada (D10) |
| ADR-008 | API REST documentada con OpenAPI | Aceptada |
| ADR-009 | Persistencia con PostgreSQL, Repository y Unit of Work | Aceptada, simplificada |
| ADR-010 | Despacho de Domain Events y consistencia eventual | Aceptada, simplificada |
| ADR-011 | Notificaciones simuladas detrás de interfaces | Aceptada |
| ADR-012 | Identidad y roles de demostración | Aceptada |
| ADR-013 | Procesamiento programado del plazo de respuesta | Aceptada |
| ADR-014 | Interfaz web orientada a la usabilidad | Aceptada |

---

## ADR-001 — Selección del patrón de lógica de negocio

- **Estado:** Aceptada (U3).
- **Contexto:** `OrdenDeServicio` tiene múltiples estados con transiciones condicionadas y más de 10 conceptos relacionados. El levantamiento documenta reglas transversales: umbral del 20% en ampliaciones (P12), escalamiento a 24 h sin respuesta (P13), autorización parcial por trabajo (US-05/06) y trato diferenciado por tipo de cliente (BN-05).
- **Alternativas:** Transaction Script (rápido, pero repite cada regla en cada script); Table Module (resuelve consultas sobre conjuntos, pero no protege invariantes por instancia); Domain Model.
- **Decisión:** Domain Model como patrón principal para todo el flujo de servicio. Table Module ligero, como excepción delimitada, solo para los indicadores (US-15).
- **Consecuencias:** Las invariantes y reglas de autorización quedan en un solo lugar. Costo: mayor diseño inicial. Riesgo: reducir las entidades a contenedores de datos.
- **Actualización PIA:** con D1 la orden tiene 10 estados (se agrega `Cerrada sin reparación`), lo que refuerza la decisión.
- **Trazabilidad:** BN-06, US-03, US-04, US-08, US-15, P12.

## ADR-002 — Separar la gestión de refacción sin existencia en dos servicios

- **Estado:** Aceptada (U3), actualizada.
- **Contexto:** Un solo servicio coordinaba dos Aggregates (`OrdenDeCompra` y `OrdenDeServicio`), violando SRP.
- **Alternativas:** Un servicio único con transacción que abarque ambos Aggregates; dos servicios coordinados por evento.
- **Decisión:** `MarcarEsperaDeRefaccionService` modifica `OrdenDeServicio` y emite `RefaccionSinExistenciaDetectada`; `SolicitarRefaccionAProveedorService` reacciona y crea la `OrdenDeCompra`.
- **Consecuencias:** Independencia entre Compras y el seguimiento del vehículo. La consistencia entre ambos es eventual. Riesgo: que el evento falle y el vehículo quede en espera sin orden de compra.
- **Actualización PIA:**
  1. El evento lo emite la raíz `OrdenDeServicio`, no el Value Object `NecesidadDeRefaccion` (Arquitectura C4).
  2. Se aplica el mismo patrón a la recepción (D6): `RegistrarRecepcionDeRefaccionService` modifica `OrdenDeCompra` y emite `RefaccionRecibida`; `ReanudarReparacionService` actualiza la `OrdenDeServicio`.
  3. El "trabajo posterior" de reintento y reconciliación se resuelve en ADR-010.
- **Trazabilidad:** BN-03, US-11, US-12, US-13, US-23, P9, RN-07, RN-08.

## ADR-003 — Autorización polimórfica en Cliente/ClienteFlotilla

- **Estado:** Aceptada (U3).
- **Contexto:** Un servicio aparte para flotillas duplicaba la lógica de `AutorizarTrabajosService` y violaba Liskov.
- **Alternativas:** Servicios separados por tipo de cliente; un servicio con un método polimórfico.
- **Decisión:** Un solo `AutorizarTrabajosService` que delega "quién puede autorizar" a `validar_autorizador(usuario)`: `Cliente` valida al cliente titular y `ClienteFlotilla` a sus responsables de cuenta registrados.
- **Consecuencias:** Un solo punto de entrada para la autorización digital en CU-01, CU-02 y CU-05. Si aparece un tercer tipo de cliente, se revisará si basta el polimorfismo.
- **Actualización PIA:** `AutorizadorValidoSpecification` envuelve la llamada polimórfica para poder combinarla con otras reglas (ADR-005). D7 confirma que el asesor no autoriza.
- **Trazabilidad:** BN-05, US-05, US-16, P8, P15, RN-02.

## ADR-004 — Política intercambiable para el umbral de autorización (20%)

- **Estado:** Aceptada (U3), actualizada.
- **Contexto:** Un único servicio de autorización acumularía un condicional por cada regla nueva, violando Open/Closed.
- **Alternativas:** Un método con condicionales crecientes; una interfaz con una implementación por regla.
- **Decisión:** Interfaz `IPoliticaDeAutorizacion` con `PoliticaAutorizacionEstandar` y `PoliticaAutorizacionAmpliacion`.
- **Consecuencias:** Una regla nueva se agrega como clase nueva. Costo: más clases pequeñas.
- **Actualización PIA:** el pendiente con el stakeholder quedó resuelto por D4 (RN-05, RN-06):
  - toda falla adicional requiere autorización sin importar el monto (`PoliticaAutorizacionEstandar`);
  - una ampliación requiere autorización explícita cuando el acumulado supera el 20% del total autorizado de la cotización inicial; exactamente 20% no lo supera (`PoliticaAutorizacionAmpliacion` con `AmpliacionSuperaUmbralSpecification`).
  - El cálculo es sobre la cotización inicial y no por trabajo, como decía P12.
- **Trazabilidad:** P12, H4, D4, US-10, RN-05, RN-06.

## ADR-005 — Specification para las reglas de negocio

- **Estado:** Aceptada.
- **Contexto:** El PIA exige el patrón Specification. Varias reglas del BRD se evalúan en más de un caso de uso y deben probarse sin base de datos: RN-01, RN-02, RN-03, RN-06, RN-09, RN-11 y RN-13.
- **Alternativas:** Condiciones dentro de cada método del Aggregate; un motor de reglas externo; Specifications combinables.
- **Decisión:** Cada regla es una clase `…Specification` con `es_satisfecha_por()` y combinadores `y()`, `o()`, `no()` (Arquitectura §4). Las políticas de ADR-004 usan Specifications en su interior; no las sustituyen.
- **Consecuencias:** Las fronteras exactas (20.00% / 20.01%, 23:59 / 24:00) se prueban de forma aislada. Costo: más clases. Las Specifications no modifican estado; solo responden.
- **Trazabilidad:** RN-01, RN-02, RN-03, RN-06, RN-09, RN-11, RN-13.

## ADR-006 — Máquinas de estado explícitas para la orden y el trabajo

- **Estado:** Aceptada.
- **Contexto:** El PIA exige State Machine. La U2 y la U3 no definían transiciones; el BRD vigente las define en D1 y D2.
- **Alternativas:** Cadenas libres con validaciones dispersas; patrón State con una clase por estado; enumeración con una tabla de transiciones permitidas.
- **Decisión:** Enumeraciones `EstadoOrden` y `EstadoTrabajo` cuyos valores son el texto literal del glosario, más una tabla `TRANSICIONES_PERMITIDAS` y una función `transicionar(origen, destino)` que lanza `TransicionNoPermitida`. Las guardias (condiciones) se expresan con Specifications.
- **Consecuencias:** Toda la máquina cabe en una tabla legible y verificable con pruebas parametrizadas. Si los estados llegaran a tener mucho comportamiento propio, se evaluaría el patrón State.
- **Trazabilidad:** D1, D2, RN-14, BRD §8.

## ADR-007 — Plataforma tecnológica y despliegue

- **Estado:** Aceptada (D10).
- **Contexto:** La U3 se implementó en React/JS. El PIA exige API REST con OpenAPI, base de datos, Docker Compose (DB + App + Tests), variables de entorno, CI/CD y despliegue.
- **Alternativas:** Node/Express; Java/Spring Boot; Python/Django; Python/FastAPI.
- **Decisión:**
  - Python 3.12, FastAPI y Pydantic para la API; Jinja2 para la interfaz web (ADR-014); SQLAlchemy 2 para la persistencia; PostgreSQL 16; pytest y pytest-cov; Ruff.
  - Docker Compose con servicios `db`, `app` y `tests`.
  - GitHub Actions para CI (lint, pruebas y cobertura ≥ 80%).
  - Despliegue en Render, con la configuración en variables de entorno (12-Factor).
- **Consecuencias:** FastAPI genera OpenAPI y Swagger UI sin trabajo adicional. Las pruebas del dominio no dependen de FastAPI ni de SQLAlchemy. El código React de la U3 queda solo como antecedente.
- **Trazabilidad:** Requisitos del PIA (Producción, Calidad), D10.

## ADR-008 — API REST documentada con OpenAPI

- **Estado:** Aceptada.
- **Contexto:** La API debe exponer los casos de uso con el lenguaje del negocio y estar documentada en producción.
- **Alternativas:** Endpoints CRUD por tabla; endpoints orientados a comandos del negocio.
- **Decisión:** Recursos en español según el glosario (`/ordenes-de-servicio`, `/autorizacion-digital`, `/cierre-de-caja`), con verbos HTTP para consultas y POST para comandos del negocio (Arquitectura §10). Errores del dominio traducidos a códigos HTTP con mensajes del negocio. El contrato se exporta a `docs/api/openapi.json` y Swagger UI queda activo en `/docs`.
- **Consecuencias:** Las rutas se leen como el BPMN y las historias. No hay endpoints de edición directa de estados ni de registros de autorización (RN-04, RN-14).
- **Trazabilidad:** US-01 a US-24.

## ADR-009 — Persistencia con PostgreSQL, Repository y Unit of Work

- **Estado:** Aceptada.
- **Contexto:** El dominio no debe conocer SQL (U3 §6) y cada comando debe ser una transacción (U3 §7).
- **Alternativas:** ORM con las clases del dominio mapeadas directamente; consultas SQL en los servicios; repositorios que traducen entre filas y objetos del dominio.
- **Decisión:**
  - Una tabla por Aggregate Root y tablas hijas para sus entidades, con SQLAlchemy 2 en `src/infrastructure`.
  - Un repositorio SQL por cada interfaz `I…Repository` del dominio y una `UnidadDeTrabajoSql` por comando.
  - La conexión se toma de `DATABASE_URL`: PostgreSQL en Compose, CI y Render; SQLite en memoria para las pruebas locales rápidas.
- **Consecuencias:** El dominio se prueba con repositorios en memoria. Los registros de autorización solo se insertan, nunca se actualizan (RN-04). El esquema se crea al arrancar.
- **Simplificación (proyecto escolar):** no se implementa control de versión optimista ni migraciones; se asume un uso de demostración sin escrituras concurrentes sobre la misma orden.
- **Trazabilidad:** RN-04, U3 §6 y §7.

## ADR-010 — Despacho de Domain Events y consistencia eventual

- **Estado:** Aceptada.
- **Contexto:** ADR-002 dejó pendiente qué hacer si falla el evento entre `OrdenDeServicio` y `OrdenDeCompra`.
- **Alternativas:** Broker de mensajes externo; patrón Outbox con un trabajador; despachador en el mismo proceso con manejadores idempotentes.
- **Decisión:**
  - Los eventos se guardan con su Aggregate y se publican en el mismo proceso **después** de confirmar la transacción.
  - Cada manejador corre en su propia Unit of Work y es idempotente: `SolicitarRefaccionAProveedorService` no crea una segunda orden de compra para el mismo trabajo, y `ReanudarReparacionService` no repite una reanudación.
  - Si un manejador falla, el comando de Compras se puede repetir sin efectos duplicados.
- **Consecuencias:** No hay infraestructura extra. Existe una ventana en la que el vehículo está en espera sin orden de compra; se cierra repitiendo el comando.
- **Simplificación (proyecto escolar):** el despachador vive en memoria y no hay reintentos automáticos ni Outbox.
- **Trazabilidad:** ADR-002, RN-07, RN-08.

## ADR-011 — Notificaciones simuladas detrás de interfaces

- **Estado:** Aceptada.
- **Contexto:** El BRD incluye avisos al cliente (US-04, US-13, US-23) y al gerente (US-22), pero no define canal. La U3 usaba `NotificacionSmsWhatsapp`, sin origen en la U2.
- **Alternativas:** Integrar un proveedor real de SMS/WhatsApp/correo; registrar los avisos en el sistema y consultarlos en la orden.
- **Decisión:** `INotificacionCliente` e `INotificacionGerente` (un método cada una). La implementación `NotificacionSimulada` registra cada aviso con destinatario, mensaje y fecha-hora; el cliente lo ve al consultar su orden (US-14).
- **Consecuencias:** Los indicadores pueden medir el tiempo de comunicación de retraso (CE-2) con la fecha-hora del aviso. Un canal real se agrega después como otra implementación sin tocar el dominio.
- **Trazabilidad:** US-04, US-13, US-14, US-22, US-23, CE-2.

## ADR-012 — Identidad y roles de demostración

- **Estado:** Aceptada.
- **Contexto:** RN-02 y US-14 dependen de quién es el usuario y su rol. Un proveedor de identidad real está fuera del alcance del PIA.
- **Alternativas:** Aceptar el usuario en el cuerpo de la petición; OAuth/OIDC; tokens de demostración configurados por variables de entorno.
- **Decisión:** Cada petición trae un token de demostración que la API traduce a (usuario, `Rol`) desde variables de entorno. El usuario nunca se toma del cuerpo. Los roles son los del glosario.
- **Consecuencias:** Basta para demostrar RN-02, US-14 y US-16. No es seguro para producción; `.env.example` no contiene secretos reales.
- **Trazabilidad:** RN-02, US-05, US-14, US-16.

## ADR-013 — Procesamiento programado del plazo de respuesta

- **Estado:** Aceptada.
- **Contexto:** RN-09 exige reaccionar cuando pasan 24 horas sin respuesta, aunque nadie use el sistema en ese momento.
- **Alternativas:** Revisar el plazo solo cuando alguien consulta la orden; un trabajador en segundo plano dentro de la app; un endpoint idempotente invocado por una tarea programada.
- **Decisión:** `ProcesarPlazosDeRespuestaService` se expone en `POST /api/v1/plazos-de-respuesta/procesamiento` y lo invoca cada 15 minutos un workflow programado de GitHub Actions (`schedule`), que no tiene costo. Es idempotente: cada orden escala y notifica al gerente una sola vez.
- **Consecuencias:** El escalamiento puede ocurrir algunos minutos después de las 24 h (GitHub no garantiza la hora exacta); se documenta como tolerancia. Las pruebas invocan el servicio con una hora controlada.
- **Trazabilidad:** RN-09, US-22, D5.

## ADR-014 — Interfaz web orientada a la usabilidad

- **Estado:** Aceptada.
- **Contexto:** El profesor pidió priorizar la usabilidad y la funcionalidad: la aplicación debe ser predecible para el usuario y la interfaz no debe mostrar código (JSON, identificadores técnicos ni trazas de error). Swagger UI cumple el requisito de documentar la API, pero no es una interfaz para el personal del taller ni para el cliente.
- **Alternativas:** Usar solo Swagger UI para la demostración; una aplicación de página única con un framework de JavaScript; páginas HTML generadas por el servidor con plantillas.
- **Decisión:** Interfaz web con plantillas Jinja2 servidas por la misma aplicación FastAPI, que llama a los mismos Application Services que la API REST. Reglas de diseño:
  1. Todo texto visible usa el glosario del BRD; nunca se muestran JSON, UUID completos ni mensajes técnicos.
  2. Cada pantalla muestra el estado actual de la orden y de cada trabajo con su nombre literal (`En espera de autorización`).
  3. Solo se muestran los botones de las acciones que el rol actual puede hacer en el estado actual, según la máquina de estados (ADR-006); lo que no se puede hacer no aparece.
  4. Cada acción termina con un mensaje de confirmación en lenguaje del negocio; los errores del dominio se muestran como avisos comprensibles.
  5. El usuario elige su rol de demostración en un selector visible (ADR-012).
- **Consecuencias:** La demostración se hace desde la interfaz; Swagger UI queda en `/docs` para la defensa técnica. No se agregan dependencias de JavaScript. El riesgo es duplicar validaciones: se evita porque la interfaz solo llama a los servicios.
- **Trazabilidad:** US-01 a US-24; requisito de demostración en vivo del PIA.

