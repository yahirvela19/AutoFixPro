"""API REST en el lenguaje del negocio (ADR-008, Arquitectura §10)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api import esquemas as e
from src.api import mensajes as m
from src.application.comandos import (
    AutorizarTrabajosCommand,
    CerrarOrdenDeServicioCommand,
    ReportarFallaAdicionalCommand,
)
from src.application.consultas import (
    ConsultarColaDeAtencionQuery,
    ConsultarEstadoVehiculoQuery,
    ObtenerDetalleParaCobroQuery,
    ObtenerIndicadoresQuery,
)
from src.application.contenedor import Contenedor
from src.domain.errores import ErrorDeDominio
from src.domain.value_objects import Usuario

esquema_bearer = HTTPBearer(auto_error=False, description="Token de demostración, por ejemplo «asesor-demo».")
router = APIRouter(prefix="/api/v1")


class NoAutenticado(ErrorDeDominio):
    """Falta el token de demostración o no es válido."""


def contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


def usuario_actual(
    request: Request, credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)
) -> Usuario:
    usuario = request.app.state.configuracion.tokens.get(credenciales.credentials if credenciales else "")
    if usuario is None:
        raise NoAutenticado("Identifícate con un token de demostración válido.")
    return usuario


def _vista(c: Contenedor, usuario: Usuario, orden_id: str) -> dict:
    return c.consultar_estado.manejar(ConsultarEstadoVehiculoQuery(usuario, orden_id))


def quiere_texto(request: Request) -> bool:
    """Swagger pide «text/plain» por defecto (ADR-015); programas y pruebas reciben JSON."""
    aceptado = request.headers.get("accept", "").lower()
    return "text/plain" in aceptado and "application/json" not in aceptado


def responder(request: Request, datos, mensaje: Callable[[], str], status_code: int = 200):
    if quiere_texto(request):
        return PlainTextResponse(mensaje(), status_code=status_code)
    return datos


@router.get("/ordenes-de-servicio", tags=["Órdenes de servicio"], summary="Listar órdenes visibles para el usuario")
def listar_ordenes(request: Request, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    datos = c.listar_ordenes.manejar(u)
    return responder(request, datos, lambda: m.lista_de_ordenes(datos))


@router.post(
    "/ordenes-de-servicio",
    status_code=201,
    tags=["Órdenes de servicio"],
    summary="US-01 Registrar ingreso del vehículo",
)
def registrar_ingreso(
    request: Request, datos: e.IngresoEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    orden = c.registrar_ingreso.registrar(u, **datos.model_dump())
    vista = _vista(c, u, orden.id)
    return responder(request, vista, lambda: m.ingreso(vista), 201)


@router.get(
    "/ordenes-de-servicio/{orden_id}", tags=["Órdenes de servicio"], summary="US-14 Consultar el estado del vehículo"
)
def consultar_orden(
    request: Request, orden_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.estado_de_orden(vista))


@router.post(
    "/ordenes-de-servicio/{orden_id}/evidencias-fotograficas",
    status_code=201,
    tags=["Órdenes de servicio"],
    summary="US-02 / US-20 Registrar evidencia fotográfica",
)
def registrar_evidencia(
    request: Request,
    orden_id: str,
    datos: e.EvidenciaEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.registrar_evidencia.registrar(u, orden_id, datos.etapa.value, datos.referencia_archivo)
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.evidencia(vista), 201)


@router.post(
    "/ordenes-de-servicio/{orden_id}/diagnostico",
    tags=["Diagnóstico y cotización"],
    summary="US-03 Registrar diagnóstico",
)
def registrar_diagnostico(
    request: Request,
    orden_id: str,
    datos: e.DiagnosticoEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.registrar_diagnostico.registrar(u, orden_id, datos.falla_encontrada)
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.diagnostico(vista))


@router.post(
    "/ordenes-de-servicio/{orden_id}/cotizaciones",
    status_code=201,
    tags=["Diagnóstico y cotización"],
    summary="US-04 Generar y enviar la cotización inicial",
)
def generar_cotizacion(
    request: Request,
    orden_id: str,
    datos: e.CotizacionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.generar_cotizacion.generar_y_enviar(u, orden_id, [t.model_dump() for t in datos.trabajos])
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.cotizacion(vista), 201)


@router.post(
    "/ordenes-de-servicio/{orden_id}/cotizaciones/{cotizacion_id}/autorizacion-digital",
    tags=["Autorización digital"],
    summary="US-05/06/07/16/21 Autorizar o rechazar trabajos",
)
def autorizacion_digital(
    request: Request,
    orden_id: str,
    cotizacion_id: str,
    datos: e.AutorizacionDigitalEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.autorizar_trabajos.autorizar_trabajos(AutorizarTrabajosCommand(u, orden_id, cotizacion_id, **datos.model_dump()))
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.decision(vista, cotizacion_id))


@router.get(
    "/ordenes-de-servicio/{orden_id}/trabajos",
    tags=["Ejecución"],
    summary="US-08 Consultar trabajos (opcional: solo ejecutables)",
)
def consultar_trabajos(
    request: Request,
    orden_id: str,
    ejecutables: bool = False,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    vista = _vista(c, u, orden_id)
    trabajos = [t for cot in vista["cotizaciones"] for t in cot["trabajos"]]
    if ejecutables:
        orden = c.repos.ordenes.obtener_por_id(orden_id)
        ids = {t.id for t in orden.trabajos_ejecutables()}
        trabajos = [t for t in trabajos if t["id"] in ids]
    return responder(request, trabajos, lambda: m.trabajos(vista, trabajos, ejecutables))


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/inicio",
    tags=["Ejecución"],
    summary="US-08 Iniciar un trabajo autorizado",
)
def iniciar_trabajo(
    request: Request,
    orden_id: str,
    trabajo_id: str,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.ejecutar_trabajo.iniciar(u, orden_id, trabajo_id)
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.trabajo(vista, trabajo_id, "Inició"))


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/terminacion",
    tags=["Ejecución"],
    summary="US-08 Terminar un trabajo",
)
def terminar_trabajo(
    request: Request,
    orden_id: str,
    trabajo_id: str,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.ejecutar_trabajo.terminar(u, orden_id, trabajo_id)
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.trabajo(vista, trabajo_id, "Terminó"))


@router.post(
    "/ordenes-de-servicio/{orden_id}/fallas-adicionales",
    status_code=201,
    tags=["Falla adicional y ampliación"],
    summary="US-09 Reportar una falla adicional",
)
def reportar_falla(
    request: Request,
    orden_id: str,
    datos: e.FallaAdicionalEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.reportar_falla_adicional.reportar(ReportarFallaAdicionalCommand(u, orden_id, datos.descripcion))
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.falla_adicional(vista), 201)


@router.post(
    "/ordenes-de-servicio/{orden_id}/cotizaciones-complementarias",
    status_code=201,
    tags=["Falla adicional y ampliación"],
    summary="US-10 Generar y enviar la cotización complementaria",
)
def cotizacion_complementaria(
    request: Request,
    orden_id: str,
    datos: e.CotizacionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.reportar_falla_adicional.generar_cotizacion_complementaria(u, orden_id, [t.model_dump() for t in datos.trabajos])
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.cotizacion(vista), 201)


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/ampliaciones",
    status_code=201,
    tags=["Falla adicional y ampliación"],
    summary="US-10 Solicitar una ampliación (umbral del 20 %)",
)
def solicitar_ampliacion(
    request: Request,
    orden_id: str,
    trabajo_id: str,
    datos: e.AmpliacionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    ampliacion = c.solicitar_ampliacion.solicitar(u, orden_id, trabajo_id, datos.monto, datos.motivo)
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.ampliacion(vista, trabajo_id, ampliacion.id), 201)


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/ampliaciones/{ampliacion_id}/autorizacion-digital",
    tags=["Falla adicional y ampliación"],
    summary="US-10 Autorizar o rechazar una ampliación",
)
def decidir_ampliacion(
    request: Request,
    orden_id: str,
    trabajo_id: str,
    ampliacion_id: str,
    datos: e.DecisionDeAmpliacionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.autorizar_trabajos.decidir_ampliacion(
        u, orden_id, trabajo_id, ampliacion_id, datos.autoriza, datos.referencia_evidencia_digital
    )
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.decision_de_ampliacion(vista, trabajo_id, ampliacion_id))


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/necesidad-de-refaccion",
    tags=["Refacciones"],
    summary="US-11/12 Confirmar refacción sin existencia",
)
def falta_de_existencia(
    request: Request,
    orden_id: str,
    trabajo_id: str,
    datos: e.NecesidadDeRefaccionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.marcar_espera_de_refaccion.confirmar_falta_de_existencia(
        u, orden_id, trabajo_id, datos.codigo_refaccion, datos.proveedor
    )
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.falta_de_existencia(vista, trabajo_id))


@router.post(
    "/ordenes-de-servicio/{orden_id}/nueva-fecha-de-entrega",
    tags=["Refacciones"],
    summary="US-13 Notificar nueva fecha de entrega",
)
def nueva_fecha(
    request: Request,
    orden_id: str,
    datos: e.NuevaFechaEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.notificar_nueva_fecha.notificar(u, orden_id, datos.nueva_fecha.isoformat(), datos.motivo)
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.nueva_fecha(vista))


@router.get("/ordenes-de-compra", tags=["Refacciones"], summary="Listar órdenes de compra")
def listar_ordenes_de_compra(
    request: Request, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    datos = c.listas.ordenes_de_compra(u)
    return responder(request, datos, lambda: m.ordenes_de_compra(datos))


@router.post(
    "/ordenes-de-compra/{orden_de_compra_id}/recepcion-de-refaccion",
    tags=["Refacciones"],
    summary="US-23 Registrar la recepción de una refacción",
)
def recepcion_de_refaccion(
    request: Request, orden_de_compra_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    orden_de_compra = c.registrar_recepcion.registrar_recepcion(u, orden_de_compra_id)
    vista = _vista(c, u, orden_de_compra.orden_de_servicio_id)
    datos = {"orden_de_compra": orden_de_compra.id, "estado": orden_de_compra.estado.value, "orden_de_servicio": vista}
    return responder(request, datos, lambda: m.recepcion(vista, orden_de_compra.id))


@router.get("/ordenes-de-servicio/{orden_id}/detalle-para-cobro", tags=["Caja"], summary="US-19 Detalle para cobro")
def detalle_para_cobro(
    request: Request, orden_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    datos = c.detalle_para_cobro.manejar(ObtenerDetalleParaCobroQuery(u, orden_id))
    return responder(request, datos, lambda: m.detalle_para_cobro(datos))


@router.post("/ordenes-de-servicio/{orden_id}/cierre-de-caja", tags=["Caja"], summary="US-19/21 Cierre de caja")
def cierre_de_caja(
    request: Request,
    orden_id: str,
    datos: e.CierreDeCajaEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(u, orden_id, datos.pago))
    vista = _vista(c, u, orden_id)
    return responder(request, vista, lambda: m.cierre(vista))


@router.post("/facturaciones-consolidadas", status_code=201, tags=["Caja"], summary="US-17 Facturación consolidada")
def facturacion(
    request: Request,
    datos: e.FacturacionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    f = c.generar_facturacion.generar(u, datos.cliente_id, datos.periodo)
    resultado = {
        "id": f.id,
        "cliente_id": f.cliente_id,
        "periodo": f.periodo,
        "total": str(f.total),
        "ordenes": [d["folio"] for d in f.detalle],
    }
    return responder(request, resultado, lambda: m.facturacion(resultado), 201)


@router.get("/cola-de-atencion", tags=["Asesor de servicio"], summary="US-18 Cola de atención")
def cola(request: Request, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    datos = c.cola_de_atencion.manejar(ConsultarColaDeAtencionQuery(u))
    return responder(request, datos, lambda: m.cola(datos))


@router.post(
    "/plazos-de-respuesta/procesamiento",
    tags=["Gerente del Taller"],
    summary="US-22 Procesar plazos de respuesta vencidos",
)
def procesar_plazos(request: Request, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    folios = [o.folio for o in c.procesar_plazos.procesar(u)]
    return responder(request, {"ordenes_escaladas": folios}, lambda: m.plazos(folios))


@router.post("/disputas", status_code=201, tags=["Disputas"], summary="US-24 Registrar una disputa")
def registrar_disputa(
    request: Request, datos: e.DisputaEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    d = c.registrar_disputa.registrar(u, datos.orden_id, datos.categoria.value, datos.descripcion)
    resultado = {"id": d.id, "estado": d.estado.value, "categoria": d.categoria.value}
    return responder(request, resultado, lambda: m.disputa_registrada(resultado, datos.orden_id), 201)


@router.get("/disputas", tags=["Disputas"], summary="Listar disputas")
def listar_disputas(request: Request, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    datos = c.listas.disputas(u)
    return responder(request, datos, lambda: m.lista_de_disputas(datos))


@router.post("/disputas/{disputa_id}/resolucion", tags=["Disputas"], summary="US-24 Resolver una disputa")
def resolver_disputa(
    request: Request,
    disputa_id: str,
    datos: e.ResolucionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    d = c.resolver_disputa.resolver(u, disputa_id, datos.resolucion)
    resultado = {"id": d.id, "estado": d.estado.value, "resolucion": d.resolucion}
    return responder(request, resultado, lambda: m.disputa_resuelta(resultado))


@router.get("/indicadores", tags=["Gerente del Taller"], summary="US-15 Indicadores del periodo")
def indicadores(
    request: Request,
    desde: date,
    hasta: date,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    datos = c.indicadores.manejar(ObtenerIndicadoresQuery(u, desde, hasta))
    return responder(request, datos, lambda: m.indicadores(datos))
