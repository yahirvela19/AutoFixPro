"""API REST en el lenguaje del negocio (ADR-008, Arquitectura §10)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api import esquemas as e
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


@router.get("/ordenes-de-servicio", tags=["Órdenes de servicio"], summary="Listar órdenes visibles para el usuario")
def listar_ordenes(u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return c.listar_ordenes.manejar(u)


@router.post(
    "/ordenes-de-servicio",
    status_code=201,
    tags=["Órdenes de servicio"],
    summary="US-01 Registrar ingreso del vehículo",
)
def registrar_ingreso(
    datos: e.IngresoEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    orden = c.registrar_ingreso.registrar(u, **datos.model_dump())
    return _vista(c, u, orden.id)


@router.get(
    "/ordenes-de-servicio/{orden_id}", tags=["Órdenes de servicio"], summary="US-14 Consultar el estado del vehículo"
)
def consultar_orden(orden_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/evidencias-fotograficas",
    status_code=201,
    tags=["Órdenes de servicio"],
    summary="US-02 / US-20 Registrar evidencia fotográfica",
)
def registrar_evidencia(
    orden_id: str, datos: e.EvidenciaEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    c.registrar_evidencia.registrar(u, orden_id, datos.etapa.value, datos.referencia_archivo)
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/diagnostico",
    tags=["Diagnóstico y cotización"],
    summary="US-03 Registrar diagnóstico",
)
def registrar_diagnostico(
    orden_id: str,
    datos: e.DiagnosticoEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.registrar_diagnostico.registrar(u, orden_id, datos.falla_encontrada)
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/cotizaciones",
    status_code=201,
    tags=["Diagnóstico y cotización"],
    summary="US-04 Generar y enviar la cotización inicial",
)
def generar_cotizacion(
    orden_id: str, datos: e.CotizacionEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    c.generar_cotizacion.generar_y_enviar(u, orden_id, [t.model_dump() for t in datos.trabajos])
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/cotizaciones/{cotizacion_id}/autorizacion-digital",
    tags=["Autorización digital"],
    summary="US-05/06/07/16/21 Autorizar o rechazar trabajos",
)
def autorizacion_digital(
    orden_id: str,
    cotizacion_id: str,
    datos: e.AutorizacionDigitalEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.autorizar_trabajos.autorizar_trabajos(AutorizarTrabajosCommand(u, orden_id, cotizacion_id, **datos.model_dump()))
    return _vista(c, u, orden_id)


@router.get(
    "/ordenes-de-servicio/{orden_id}/trabajos",
    tags=["Ejecución"],
    summary="US-08 Consultar trabajos (opcional: solo ejecutables)",
)
def consultar_trabajos(
    orden_id: str, ejecutables: bool = False, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    vista = _vista(c, u, orden_id)
    trabajos = [t for cot in vista["cotizaciones"] for t in cot["trabajos"]]
    if ejecutables:
        orden = c.repos.ordenes.obtener_por_id(orden_id)
        ids = {t.id for t in orden.trabajos_ejecutables()}
        trabajos = [t for t in trabajos if t["id"] in ids]
    return trabajos


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/inicio",
    tags=["Ejecución"],
    summary="US-08 Iniciar un trabajo autorizado",
)
def iniciar_trabajo(
    orden_id: str, trabajo_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    c.ejecutar_trabajo.iniciar(u, orden_id, trabajo_id)
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/terminacion",
    tags=["Ejecución"],
    summary="US-08 Terminar un trabajo",
)
def terminar_trabajo(
    orden_id: str, trabajo_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    c.ejecutar_trabajo.terminar(u, orden_id, trabajo_id)
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/fallas-adicionales",
    status_code=201,
    tags=["Falla adicional y ampliación"],
    summary="US-09 Reportar una falla adicional",
)
def reportar_falla(
    orden_id: str,
    datos: e.FallaAdicionalEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.reportar_falla_adicional.reportar(ReportarFallaAdicionalCommand(u, orden_id, datos.descripcion))
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/cotizaciones-complementarias",
    status_code=201,
    tags=["Falla adicional y ampliación"],
    summary="US-10 Generar y enviar la cotización complementaria",
)
def cotizacion_complementaria(
    orden_id: str, datos: e.CotizacionEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    c.reportar_falla_adicional.generar_cotizacion_complementaria(u, orden_id, [t.model_dump() for t in datos.trabajos])
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/ampliaciones",
    status_code=201,
    tags=["Falla adicional y ampliación"],
    summary="US-10 Solicitar una ampliación (umbral del 20 %)",
)
def solicitar_ampliacion(
    orden_id: str,
    trabajo_id: str,
    datos: e.AmpliacionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.solicitar_ampliacion.solicitar(u, orden_id, trabajo_id, datos.monto, datos.motivo)
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/ampliaciones/{ampliacion_id}/autorizacion-digital",
    tags=["Falla adicional y ampliación"],
    summary="US-10 Autorizar o rechazar una ampliación",
)
def decidir_ampliacion(
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
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/trabajos/{trabajo_id}/necesidad-de-refaccion",
    tags=["Refacciones"],
    summary="US-11/12 Confirmar refacción sin existencia",
)
def falta_de_existencia(
    orden_id: str,
    trabajo_id: str,
    datos: e.NecesidadDeRefaccionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.marcar_espera_de_refaccion.confirmar_falta_de_existencia(
        u, orden_id, trabajo_id, datos.codigo_refaccion, datos.proveedor
    )
    return _vista(c, u, orden_id)


@router.post(
    "/ordenes-de-servicio/{orden_id}/nueva-fecha-de-entrega",
    tags=["Refacciones"],
    summary="US-13 Notificar nueva fecha de entrega",
)
def nueva_fecha(
    orden_id: str, datos: e.NuevaFechaEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    c.notificar_nueva_fecha.notificar(u, orden_id, datos.nueva_fecha.isoformat(), datos.motivo)
    return _vista(c, u, orden_id)


@router.get("/ordenes-de-compra", tags=["Refacciones"], summary="Listar órdenes de compra")
def listar_ordenes_de_compra(u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return c.listas.ordenes_de_compra(u)


@router.post(
    "/ordenes-de-compra/{orden_de_compra_id}/recepcion-de-refaccion",
    tags=["Refacciones"],
    summary="US-23 Registrar la recepción de una refacción",
)
def recepcion_de_refaccion(
    orden_de_compra_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    orden_de_compra = c.registrar_recepcion.registrar_recepcion(u, orden_de_compra_id)
    return {
        "orden_de_compra": orden_de_compra.id,
        "estado": orden_de_compra.estado.value,
        "orden_de_servicio": _vista(c, u, orden_de_compra.orden_de_servicio_id),
    }


@router.get("/ordenes-de-servicio/{orden_id}/detalle-para-cobro", tags=["Caja"], summary="US-19 Detalle para cobro")
def detalle_para_cobro(orden_id: str, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return c.detalle_para_cobro.manejar(ObtenerDetalleParaCobroQuery(u, orden_id))


@router.post("/ordenes-de-servicio/{orden_id}/cierre-de-caja", tags=["Caja"], summary="US-19/21 Cierre de caja")
def cierre_de_caja(
    orden_id: str,
    datos: e.CierreDeCajaEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(u, orden_id, datos.pago))
    return _vista(c, u, orden_id)


@router.post("/facturaciones-consolidadas", status_code=201, tags=["Caja"], summary="US-17 Facturación consolidada")
def facturacion(datos: e.FacturacionEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    f = c.generar_facturacion.generar(u, datos.cliente_id, datos.periodo)
    return {
        "id": f.id,
        "cliente_id": f.cliente_id,
        "periodo": f.periodo,
        "total": str(f.total),
        "ordenes": [d["folio"] for d in f.detalle],
    }


@router.get("/cola-de-atencion", tags=["Asesor de servicio"], summary="US-18 Cola de atención")
def cola(u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return c.cola_de_atencion.manejar(ConsultarColaDeAtencionQuery(u))


@router.post(
    "/plazos-de-respuesta/procesamiento",
    tags=["Gerente del Taller"],
    summary="US-22 Procesar plazos de respuesta vencidos",
)
def procesar_plazos(u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    escaladas = c.procesar_plazos.procesar(u)
    return {"ordenes_escaladas": [o.folio for o in escaladas]}


@router.post("/disputas", status_code=201, tags=["Disputas"], summary="US-24 Registrar una disputa")
def registrar_disputa(
    datos: e.DisputaEntrada, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)
):
    d = c.registrar_disputa.registrar(u, datos.orden_id, datos.categoria.value, datos.descripcion)
    return {"id": d.id, "estado": d.estado.value, "categoria": d.categoria.value}


@router.get("/disputas", tags=["Disputas"], summary="Listar disputas")
def listar_disputas(u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return c.listas.disputas(u)


@router.post("/disputas/{disputa_id}/resolucion", tags=["Disputas"], summary="US-24 Resolver una disputa")
def resolver_disputa(
    disputa_id: str,
    datos: e.ResolucionEntrada,
    u: Usuario = Depends(usuario_actual),
    c: Contenedor = Depends(contenedor),
):
    d = c.resolver_disputa.resolver(u, disputa_id, datos.resolucion)
    return {"id": d.id, "estado": d.estado.value, "resolucion": d.resolucion}


@router.get("/indicadores", tags=["Gerente del Taller"], summary="US-15 Indicadores del periodo")
def indicadores(desde: date, hasta: date, u: Usuario = Depends(usuario_actual), c: Contenedor = Depends(contenedor)):
    return c.indicadores.manejar(ObtenerIndicadoresQuery(u, desde, hasta))
