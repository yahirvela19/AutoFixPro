"""Punto de entrada: compone infraestructura, API REST e interfaz web.

Ejecutar con: uvicorn src.api.main:crear_app --factory
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api import rutas_api, web
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
Los errores del negocio responden con `{"detalle": "mensaje"}`.
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
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.configuracion = configuracion
    app.state.contenedor = contenedor
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    app.include_router(rutas_api.router)
    app.include_router(web.router)

    @app.exception_handler(errores.ErrorDeDominio)
    async def error_de_dominio(request: Request, error: errores.ErrorDeDominio):
        codigo = next((c for tipo, c in CODIGOS_HTTP.items() if isinstance(error, tipo)), 400)
        return JSONResponse({"detalle": error.mensaje}, status_code=codigo)

    @app.exception_handler(RequestValidationError)
    async def error_de_validacion(request: Request, error: RequestValidationError):
        campos = ", ".join(str(e["loc"][-1]) for e in error.errors())
        return JSONResponse({"detalle": f"Revisa los datos enviados: {campos}."}, status_code=422)

    @app.exception_handler(web.SinSesion)
    async def sin_sesion(request: Request, error: web.SinSesion):
        return RedirectResponse("/?aviso=Elige%20tu%20rol%20para%20continuar.&tipo=error", status_code=303)

    @app.get("/salud", include_in_schema=False)
    def salud():
        return {"estado": "ok"}

    return app
