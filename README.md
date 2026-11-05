# AutoFix Pro — Órdenes de servicio de un taller automotriz

**Equipo 6 · Componentes de Lógica de Negocio · PIA**
Josue Yahir Vela Hernandez · Osweld Omar Lozano Martínez · Sylvia Yadira González Parra

**Demo en línea:** <https://autofixpro-m04z.onrender.com> · **Repositorio:** <https://github.com/yahirvela19/AutoFixPro>

Aplicación que digitaliza el proceso de servicio de AutoFix Pro: registro de ingreso, diagnóstico, cotización, **autorización digital por trabajo**, reparación, refacciones, entrega, cobro y facturación consolidada de flotillas. Todo el lenguaje de la aplicación sigue el glosario del BRD. Los datos son ficticios.

| Documento | Contenido |
|---|---|
| [docs/BRD.md](docs/BRD.md) | BRD, 16 reglas de negocio, 24 historias con Gherkin, estados, glosario y trazabilidad |
| [docs/bpmn/BPMN_AutoFixPro_v2.drawio](docs/bpmn/BPMN_AutoFixPro_v2.drawio) | Proceso de servicio en BPMN (abrir con app.diagrams.net) |
| [docs/architecture/Arquitectura.md](docs/architecture/Arquitectura.md) | Lenguaje ubicuo, DDD, UML, Specifications, máquinas de estado, API y SOLID |
| [docs/architecture/ADRs.md](docs/architecture/ADRs.md) | ADR-001 a ADR-014 |
| [docs/architecture/Trazabilidad.md](docs/architecture/Trazabilidad.md) | Historia → regla → BPMN → dominio → API → prueba |
| [docs/api/](docs/api/) | Contrato OpenAPI exportado |
| [docs/testing/](docs/testing/) | Plan de pruebas, evidencias, resultados del paquete docente y sus diferencias |

## Estructura

```text
src/
  domain/          Aggregates, Value Objects, Specifications, máquinas de estado, eventos e interfaces de Repository
  application/     Application Services (casos de uso), Commands, Queries y puertos
  infrastructure/  SQLAlchemy, notificaciones simuladas, eventos, datos demo y adaptador del paquete docente
  api/             API REST (FastAPI), interfaz web (Jinja2) y configuración
tests/             Unitarias, integración y paquete docente
datos/             CSV del paquete de pruebas del docente
.github/workflows/ CI/CD y procesamiento programado del plazo de 24 horas
```

## Ejecutar localmente

Requiere Python 3.12 o superior.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn src.api.main:crear_app --factory --reload
```

- Interfaz web: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs> · OpenAPI: <http://localhost:8000/api/openapi.json>

La primera ejecución crea `autofixpro.db` (SQLite) y carga datos de demostración.

## Ejecutar con Docker Compose (DB + App + Tests)

```bash
docker compose up --build -d db app
docker compose --profile test run --rm tests
```

La aplicación queda en <http://localhost:8000> con PostgreSQL. El servicio `tests` corre la suite contra una base de PostgreSQL separada (`autofixpro_pruebas`).

## Pruebas y calidad

```bash
ruff check src tests scripts
python -m pytest --cov --cov-report=term --cov-fail-under=80
python -m scripts.ejecutar_paquete_docente      # resultados de los 120 casos y 20 transiciones
python -m scripts.exportar_openapi              # actualiza docs/api/openapi.json
```

## Configuración (12-Factor)

Todas las variables están en [.env.example](.env.example): `DATABASE_URL`, `CARGAR_DATOS_DEMO`, `TOKENS_DEMO` y `PLAZO_DE_RESPUESTA_HORAS`. No hay secretos reales en el repositorio.

## Usuarios de demostración

En la interfaz se elige el rol en la pantalla de inicio. En la API se usa el token en **Authorize** de Swagger.

| Token | Usuario | Rol |
|---|---|---|
| `asesor-demo` | Laura Méndez | Asesor de Servicio |
| `tecnico-demo` | Jorge Salinas | Técnico |
| `compras-demo` | Rosa Treviño | Compras |
| `caja-demo` | Miguel Garza | Caja |
| `gerente-demo` | Patricia Leal | Gerente del Taller |
| `cliente-demo` | Ana López | Cliente Titular |
| `cliente2-demo` | Carlos Ramírez | Cliente Titular |
| `flotilla-demo` | Daniel Ortiz | Responsable de Cuenta (Transportes del Norte) |

## Guion de demostración (10 minutos)

1. **Asesor de Servicio** → *Registrar ingreso* (cliente Ana López, foto opcional). La orden queda **Recibido**.
2. **Técnico** → abre la orden → *Registrar diagnóstico* → **Diagnosticado**.
3. **Asesor** → *Enviar cotización* con dos trabajos → **En espera de autorización**; el cliente recibe un aviso.
4. **Ana López (Cliente Titular)** → autoriza un trabajo y rechaza otro, confirma la decisión → **En reparación**. Queda el *Registro de autorización*.
5. **Carlos Ramírez** intenta abrir la orden de Ana: acceso negado (US-14).
6. **Compras** → en la orden OS-0004 confirma *refacción sin existencia* → **En espera de refacción**; se crea la orden de compra.
7. **Asesor** → *Avisar nueva fecha de entrega*. **Compras** → *Registrar recepción* → la reparación continúa.
8. **Asesor** → *Solicitar ampliación* mayor al 20 % → la orden vuelve a **En espera de autorización** y el trabajo queda bloqueado hasta que el cliente decida.
9. **Técnico** → inicia y termina los trabajos autorizados → **Listo para entrega**.
10. **Caja** → solo ve conceptos terminados → cobra → **Cerrado**. En flotillas, *Facturación consolidada* del mes.
11. **Gerente del Taller** → indicadores, avisos, *Revisar plazos de respuesta* y resolución de disputas.

## Despliegue

- **Render:** el archivo [render.yaml](render.yaml) crea la aplicación Docker y una base PostgreSQL. Al conectar el repositorio, Render usa `DATABASE_URL` automáticamente.
- **CD:** el job `despliegue` del workflow llama al *deploy hook* de Render si existe el secreto `RENDER_DEPLOY_HOOK`.
- **Plazo de 24 horas (ADR-013):** el workflow `plazos-de-respuesta.yml` corre cada 15 minutos. Requiere los secretos `URL_APP` (URL pública) y `TOKEN_GERENTE` (`gerente-demo` o el token configurado).
- **Sistema desplegado:** <https://autofixpro-m04z.onrender.com> · Swagger UI: <https://autofixpro-m04z.onrender.com/docs>
- En el plan gratuito de Render la app se suspende sin uso; la primera visita puede tardar alrededor de un minuto.

## Alcance y limitaciones

- Notificaciones simuladas: se registran y se ven en la orden (ADR-011).
- Las fotografías se guardan como referencia (nombre del archivo), no como imagen.
- Identidad de demostración con tokens (ADR-012); no es autenticación de producción.
- Fuera de alcance según el BRD: custodia, operación sin conexión, encuestas, nómina y contabilidad.
