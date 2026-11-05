# Plan y evidencia de pruebas — AutoFix Pro

**Equipo 6 · Componentes de Lógica de Negocio · PIA**

## 1. Estrategia

| Nivel | Carpeta | Qué prueba | Dobles de prueba |
|---|---|---|---|
| Unitarias de reglas | `tests/unit/test_reglas_del_dominio.py` | Specifications y combinadores `y/o/no`, umbral del 20 % (19.99 %, 20 %, 20.01 %), políticas de autorización, autorizador polimórfico, **todas** las transiciones permitidas y prohibidas de las dos máquinas de estado, `Monto` decimal y Value Objects | Ninguno |
| Aceptación por historia | `tests/unit/test_historias.py` | Los escenarios Gherkin de US-01 a US-24 a través de los Application Services, con repositorios en memoria y un reloj controlable (23 h 59 min / 24 h) | `RepositorioEnMemoria`, `RelojFijo`, `NotificacionSimulada` |
| Integración API | `tests/integration/test_api.py` | Flujo completo por HTTP, códigos 401/403/404/409/422, flotilla con refacción y facturación, ampliación, falla adicional, plazos, disputas, indicadores y OpenAPI | SQLite en memoria o PostgreSQL (`TEST_DATABASE_URL`) |
| Integración web | `tests/integration/test_web.py` | Flujo por roles en la interfaz, acciones visibles por rol y estado, mensajes del negocio y que la interfaz **no muestre código** (ADR-014) | SQLite en memoria |
| Persistencia | `tests/integration/test_persistencia.py` | Guardar y recuperar el Aggregate completo sin perder tipos (enums, `Decimal`, fechas, Value Objects) | SQLite o PostgreSQL |
| Transacciones y servicio externo | `tests/integration/test_transacciones_y_mocks.py`, `tests/unit/test_calculos_de_cotizacion.py` | Commit y rollback con SQLAlchemy; aviso al cliente con `unittest.mock.Mock` (llamada exacta y falla del proveedor); cálculo de totales | `Mock` |
| Paquete docente | `tests/paquete_docente/test_paquete_docente.py` | Importación de los CSV, totales con `Decimal`, 120 casos y 20 transiciones ejecutados con el dominio del BRD | Adaptador `src/infrastructure/paquete_docente.py` |

Los nombres de las pruebas por historia coinciden con la columna *Prueba de aceptación* de `docs/architecture/Trazabilidad.md`.

## 2. Cómo ejecutar

```bash
ruff check src tests scripts
python -m pytest --cov --cov-report=term --cov-fail-under=80
TEST_DATABASE_URL=postgresql+psycopg://autofix:autofix@localhost:5432/autofixpro_pruebas python -m pytest tests/integration
docker compose --profile test run --rm tests
python -m scripts.ejecutar_paquete_docente
```

## 3. Resultados registrados

Ejecución local del **05/11/2026** con Python 3.14.6 y SQLite en memoria:

| Verificación | Resultado | Evidencia |
|---|---|---|
| Ruff | Sin errores | `evidencias/ruff.txt` |
| Suite completa | **363 pruebas aprobadas**, 0 fallidas | `evidencias/pytest_cobertura.txt`, `evidencias/pytest_detalle.txt` |
| Cobertura de `src` | **93.40 %** (mínimo exigido: 80 %) | `evidencias/pytest_cobertura.txt` |
| Paquete docente | 120 casos y 20 transiciones con resultado | `resultados_casos_prueba.csv`, `resultados_transiciones.csv` |

**Pendiente de verificar (no ejecutado en esta máquina):** las pruebas contra PostgreSQL, Docker Compose y GitHub Actions. Docker no está instalado en el equipo donde se generó esta evidencia; el workflow `ci.yml` las ejecuta al subir el repositorio.

## 4. Evidencia 9 (Unidad 5)

- Matriz: `E9_matriz_casos_prueba.csv` (24 casos de 8 reglas del BRD, 24 en PASS en la corrida del 05/11/2026 con 369 pruebas aprobadas y 93.40 % de cobertura).
- Documento: `Evidencia_9_Unidad_5_AutoFixPro.docx`.
- Reporte de cobertura HTML: `cobertura_html/index.html`.

## 5. Defectos encontrados por las pruebas y corregidos

| Prueba | Defecto | Corrección |
|---|---|---|
| `test_us04_cotizacion_sin_diagnostico_se_rechaza` | Una cantidad de 0 se convertía en 1 y la cotización se aceptaba. | Solo se usa 1 cuando la cantidad viene vacía. |
| `test_us23_recepcion_reanuda_reparacion` | La orden emitía un evento con el mismo nombre que el de la orden de compra y el manejador se ejecutaba dos veces. | La orden emite `ReparacionReanudada`. |
| `test_us10_ampliacion_rechazada_continua_con_monto_autorizado` | Repetir la decisión mostraba «la orden no está esperando autorización» en lugar de «ya fue decidida». | Se revisa primero si la decisión ya existe. |
| `test_web_flujo_completo_por_roles_sin_mostrar_codigo` | La foto de ingreso no se guardaba desde la interfaz. | Se valida el archivo con la clase de Starlette. |
