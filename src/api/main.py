"""Punto de entrada: compone infraestructura, API REST e interfaz web.

Ejecutar con: uvicorn src.api.main:crear_app --factory
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api import mensajes, rutas_api, web
from src.api.configuracion import Configuracion
from src.application.contenedor import construir_contenedor
from src.domain import errores
from src.infrastructure.adaptadores import DespachadorEnMemoria, NotificacionSimulada, RelojDelSistema
from src.infrastructure.datos_demo import cargar_datos_demo
from src.infrastructure.persistencia import crear_motor, repositorios_sql

CODIGOS_HTTP = {
    errores.DatosIncompletos: 422,
    errores.AutorizadorNoValido: 403,
    errores.RolNoPermitido: 403,
    errores.TransicionNoPermitida: 409,
    errores.DecisionYaRegistrada: 409,
    errores.RecursoNoEncontrado: 404,
    rutas_api.NoAutenticado: 401,
}

DESCRIPCION = """
API de **AutoFix Pro** (Equipo 6, PIA de Componentes de Lógica de Negocio).

Identifícate con el botón **Authorize** usando un token de demostración, por ejemplo
`asesor-demo`, `tecnico-demo`, `compras-demo`, `caja-demo`, `gerente-demo`, `cliente-demo` o `flotilla-demo`.
En Swagger las respuestas se muestran como **mensajes de texto** con los identificadores para continuar el flujo
(formato `text/plain`). Para ver el JSON, elige `application/json` en el selector «Media type» de la respuesta.
Los programas que no piden texto reciben JSON; los errores del negocio responden `{"detalle": "mensaje"}`.
"""


def crear_app(configuracion: Configuracion | None = None, reloj=None) -> FastAPI:
    configuracion = configuracion or Configuracion.desde_entorno()
    reloj = reloj or RelojDelSistema()
    motor = crear_motor(configuracion.database_url)
    notificaciones = NotificacionSimulada(reloj, motor)
    contenedor = construir_contenedor(
        repositorios_sql(motor),
        reloj,
        notificaciones,
        DespachadorEnMemoria(),
        plazo_horas=configuracion.plazo_de_respuesta_horas,
    )
    if configuracion.cargar_datos_demo:
        cargar_datos_demo(contenedor)

    app = FastAPI(
        title="AutoFix Pro API",
        version="1.0.0",
        description=DESCRIPCION,
        openapi_url="/api/openapi.json",
        docs_url=None,
        redoc_url=None,
    )
    app.state.configuracion = configuracion
    app.state.contenedor = contenedor
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    app.include_router(rutas_api.router)
    app.include_router(web.router)

    def respuesta_de_error(request: Request, mensaje: str, codigo: int):
        if rutas_api.quiere_texto(request):
            return PlainTextResponse(mensajes.error(mensaje), status_code=codigo)
        return JSONResponse({"detalle": mensaje}, status_code=codigo)

    @app.exception_handler(errores.ErrorDeDominio)
    async def error_de_dominio(request: Request, error: errores.ErrorDeDominio):
        codigo = next((c for tipo, c in CODIGOS_HTTP.items() if isinstance(error, tipo)), 400)
        return respuesta_de_error(request, error.mensaje, codigo)

    @app.exception_handler(RequestValidationError)
    async def error_de_validacion(request: Request, error: RequestValidationError):
        if any(e.get("type") == "json_invalid" for e in error.errors()):
            mensaje = "El cuerpo de la petición no es un JSON válido; revisa las comas, comillas y llaves."
        else:
            campos = ", ".join(str(e["loc"][-1]) for e in error.errors())
            mensaje = f"Revisa los datos enviados: {campos}."
        return respuesta_de_error(request, mensaje, 422)

    def contrato_openapi():
        """Declara «text/plain» como primer formato de cada respuesta para que Swagger muestre mensajes (ADR-015)."""
        if app.openapi_schema:
            return app.openapi_schema
        esquema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        texto = {"text/plain": {"schema": {"type": "string"}}}
        for operaciones in esquema.get("paths", {}).values():
            for operacion in operaciones.values():
                respuestas = operacion.setdefault("responses", {})
                for codigo in ("401", "403", "404", "409", "422"):
                    respuestas.setdefault(codigo, {"description": "Error del negocio"})
                for respuesta in respuestas.values():
                    respuesta["content"] = {**texto, **respuesta.get("content", {})}
        app.openapi_schema = esquema
        return esquema

    app.openapi = contrato_openapi

    @app.exception_handler(web.SinSesion)
    async def sin_sesion(request: Request, error: web.SinSesion):
        return RedirectResponse("/?aviso=Elige%20tu%20rol%20para%20continuar.&tipo=error", status_code=303)

    @app.get("/docs", include_in_schema=False)
    def swagger_ui():
        """Swagger UI que pide mensajes de texto por defecto (ADR-015).

        Al cargar, el selector «Media type» de cada operación se fija en «text/plain». Si aun así llega «*/*», se pide
        «text/plain». Si el usuario elige «application/json», Swagger lo envía tal cual y se muestra el JSON.
        """
        pagina = get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - Swagger UI").body.decode()
        interceptor = (
            "requestInterceptor: (peticion) => {"
            " const formato = peticion.headers['Accept'] || peticion.headers['accept'];"
            " if (!formato || formato === '*/*') { delete peticion.headers['accept'];"
            " peticion.headers['Accept'] = 'text/plain'; }"
            " return peticion; },"
            "onComplete: () => { const rutas = ui.specSelectors.specJson().toJS().paths || {};"
            " Object.entries(rutas).forEach(([ruta, operaciones]) => Object.keys(operaciones).forEach("
            " (metodo) => ui.specActions.changeProducesValue([ruta, metodo], 'text/plain'))); },"
        )
        pagina = pagina.replace("const ui = SwaggerUIBundle({", "const ui = SwaggerUIBundle({\n    " + interceptor, 1)
        return HTMLResponse(pagina)

    @app.get("/salud", include_in_schema=False)
    def salud():
        return {"estado": "ok"}

    return app
