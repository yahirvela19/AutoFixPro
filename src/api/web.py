"""Interfaz web orientada a la usabilidad (ADR-014).

- Todo texto visible usa el glosario; nunca se muestran JSON ni mensajes técnicos.
- Solo aparecen las acciones que el rol actual puede hacer en el estado actual.
- Cada acción termina con un mensaje de confirmación o un aviso comprensible.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile

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
from src.domain.estados import (
    CategoriaDisputa,
    EstadoAmpliacion,
    EstadoOrden,
    EstadoOrdenDeCompra,
    EstadoTrabajo,
    Rol,
)
from src.domain.orden_de_servicio import OrdenDeServicio
from src.domain.value_objects import Monto, Usuario

plantillas = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
plantillas.env.trim_blocks = True
plantillas.env.lstrip_blocks = True
router = APIRouter(include_in_schema=False)
COOKIE = "token_demo"

ESTILO_ESTADO = {
    "Recibido": "gris",
    "Diagnosticado": "azul",
    "Cotizado": "azul",
    "En espera de autorización": "ambar",
    "En espera de cliente": "rojo",
    "En reparación": "morado",
    "En espera de refacción": "ambar",
    "Listo para entrega": "verde",
    "Cerrado": "gris-oscuro",
    "Cerrada sin reparación": "gris-oscuro",
    "Pendiente de autorización": "ambar",
    "Autorizado": "verde",
    "Rechazado": "rojo",
    "En ejecución": "morado",
    "Terminado": "gris-oscuro",
    "Autorizada": "verde",
    "Rechazada": "rojo",
    "Solicitada": "ambar",
    "Recibida": "verde",
    "Abierta": "ambar",
    "Resuelta": "verde",
}
plantillas.env.filters["estilo"] = lambda estado: ESTILO_ESTADO.get(str(estado), "gris")

NAVEGACION = {
    Rol.ASESOR_DE_SERVICIO: [("Órdenes", "/"), ("Nueva orden", "/ordenes/nueva"), ("Cola de atención", "/cola")],
    Rol.TECNICO: [("Órdenes", "/"), ("Cola de atención", "/cola")],
    Rol.COMPRAS: [("Órdenes", "/"), ("Órdenes de compra", "/compras")],
    Rol.CAJA: [("Órdenes", "/"), ("Facturación consolidada", "/caja")],
    Rol.GERENTE_DEL_TALLER: [("Órdenes", "/"), ("Indicadores y avisos", "/gerente"), ("Disputas", "/disputas")],
    Rol.CLIENTE_TITULAR: [("Mis órdenes", "/"), ("Mis disputas", "/disputas")],
    Rol.RESPONSABLE_DE_CUENTA: [("Órdenes de mi flotilla", "/"), ("Mis disputas", "/disputas")],
}


def _contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


def _usuario(request: Request) -> Usuario | None:
    return request.app.state.configuracion.tokens.get(request.cookies.get(COOKIE, ""))


class SinSesion(Exception):
    """El navegador no tiene un rol de demostración elegido."""


def _u(request: Request) -> Usuario:
    usuario = _usuario(request)
    if usuario is None:
        raise SinSesion()
    return usuario


def _ir(url: str, aviso: str, tipo: str = "exito") -> RedirectResponse:
    separador = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{separador}aviso={quote(aviso)}&tipo={tipo}", status_code=303)


def _pagina(request: Request, plantilla: str, **contexto) -> HTMLResponse:
    usuario = _usuario(request)
    return plantillas.TemplateResponse(
        request,
        plantilla,
        {
            "usuario": usuario,
            "navegacion": NAVEGACION.get(usuario.rol, []) if usuario else [],
            "aviso": request.query_params.get("aviso"),
            "tipo_aviso": request.query_params.get("tipo", "exito"),
            **contexto,
        },
    )


async def _formulario(request: Request) -> dict:
    return dict(await request.form())


def _lineas(formulario: dict) -> list[dict]:
    lineas = []
    for i in range(1, 6):
        descripcion = str(formulario.get(f"descripcion_{i}", "")).strip()
        if descripcion:
            lineas.append(
                {
                    "descripcion": descripcion,
                    "cantidad": formulario.get(f"cantidad_{i}") or 1,
                    "precio_unitario": formulario.get(f"precio_{i}") or 0,
                }
            )
    return lineas


def _evidencia_digital(usuario: Usuario, formulario: dict) -> str:
    if formulario.get("confirmo") != "si":
        return ""
    return f"Autorización digital de {usuario.nombre} ({usuario.rol}) confirmada en el portal"


# ------------------------------------------------------------------- sesión
@router.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    usuario = _usuario(request)
    if usuario is None:
        usuarios = [{"token": t, "usuario": u} for t, u in request.app.state.configuracion.tokens.items()]
        return _pagina(request, "elegir_rol.html", usuarios=usuarios)
    c = _contenedor(request)
    ordenes = c.listar_ordenes.manejar(usuario)
    activas = [o for o in ordenes if o["estado"] not in ("Cerrado", "Cerrada sin reparación")]
    cerradas = [o for o in ordenes if o not in activas]
    return _pagina(request, "inicio.html", activas=activas, cerradas=cerradas)


@router.post("/sesion")
async def iniciar_sesion(request: Request):
    formulario = await _formulario(request)
    token = str(formulario.get("token", ""))
    usuario = request.app.state.configuracion.tokens.get(token)
    if usuario is None:
        return _ir("/", "Elige un usuario de la lista.", "error")
    respuesta = _ir("/", f"Bienvenido, {usuario.nombre}. Estás trabajando como {usuario.rol}.")
    respuesta.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return respuesta


@router.get("/salir")
def salir():
    respuesta = RedirectResponse("/", status_code=303)
    respuesta.delete_cookie(COOKIE)
    return respuesta


# -------------------------------------------------------------- nueva orden
@router.get("/ordenes/nueva", response_class=HTMLResponse)
def nueva_orden(request: Request):
    usuario = _usuario(request)
    if usuario is None or usuario.rol != Rol.ASESOR_DE_SERVICIO:
        return _ir("/", "El registro de ingreso lo realiza el Asesor de Servicio.", "error")
    return _pagina(request, "nueva_orden.html", clientes=_contenedor(request).listas.clientes())


@router.post("/ordenes")
async def registrar_ingreso(request: Request):
    usuario = _u(request)
    formulario = await request.form()
    foto = formulario.get("foto")
    nombre_foto = foto.filename if isinstance(foto, UploadFile) and foto.filename else None
    try:
        orden = _contenedor(request).registrar_ingreso.registrar(
            usuario,
            cliente_id=str(formulario.get("cliente_id", "")),
            placa=str(formulario.get("placa", "")),
            marca=str(formulario.get("marca", "")),
            modelo=str(formulario.get("modelo", "")),
            vin=str(formulario.get("vin", "")),
            kilometraje=formulario.get("kilometraje") or 0,
            nivel_combustible=str(formulario.get("nivel_combustible", "")),
            danos_visibles=str(formulario.get("danos_visibles", "")),
            motivo_ingreso=str(formulario.get("motivo_ingreso", "")),
            cargo_diagnostico=str(formulario.get("cargo_diagnostico") or "0"),
            cargo_diagnostico_aceptado=formulario.get("cargo_diagnostico_aceptado") == "si",
            foto_ingreso=nombre_foto,
        )
    except ErrorDeDominio as error:
        return _ir("/ordenes/nueva", error.mensaje, "error")
    return _ir(f"/ordenes/{orden.id}", f"Se registró el ingreso. La orden {orden.folio} quedó en «Recibido».")


# ------------------------------------------------------------ detalle orden
def _acciones(usuario: Usuario, orden: OrdenDeServicio, c: Contenedor) -> dict:
    cliente = c.repos.clientes.obtener_por_id(orden.cliente_id)
    rol, estado = usuario.rol, orden.estado
    es_autorizador = cliente.validar_autorizador(usuario)
    espera = estado in (EstadoOrden.EN_ESPERA_DE_AUTORIZACION, EstadoOrden.EN_ESPERA_DE_CLIENTE)
    en_reparacion = estado == EstadoOrden.EN_REPARACION
    trabajos = orden.todos_los_trabajos()
    cotizacion_pendiente = next((x for x in orden.cotizaciones if not x.esta_decidida), None)
    ampliaciones = [
        {"trabajo": t, "ampliacion": a}
        for t in trabajos
        for a in t.ampliaciones
        if a.estado == EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION
    ]
    ordenes_de_compra = [
        oc
        for oc in c.repos.ordenes_de_compra.listar()
        if oc.orden_de_servicio_id == orden.id and oc.estado == EstadoOrdenDeCompra.SOLICITADA
    ]
    return {
        "diagnosticar": rol == Rol.TECNICO and estado == EstadoOrden.RECIBIDO,
        "cotizar": rol == Rol.ASESOR_DE_SERVICIO and estado == EstadoOrden.DIAGNOSTICADO,
        "decidir_cotizacion": cotizacion_pendiente if es_autorizador and espera and cotizacion_pendiente else None,
        "decidir_ampliaciones": ampliaciones if es_autorizador and espera else [],
        "iniciar": [t for t in orden.trabajos_ejecutables()] if rol == Rol.TECNICO else [],
        "terminar": [
            t for t in trabajos if t.estado == EstadoTrabajo.EN_EJECUCION and not t.tiene_ampliacion_pendiente()
        ]
        if rol == Rol.TECNICO and en_reparacion
        else [],
        "reportar_falla": rol == Rol.TECNICO and en_reparacion,
        "cotizacion_complementaria": rol == Rol.ASESOR_DE_SERVICIO
        and en_reparacion
        and bool(orden.fallas_adicionales_por_cotizar),
        "ampliar": [t for t in trabajos if t.estado in (EstadoTrabajo.AUTORIZADO, EstadoTrabajo.EN_EJECUCION)]
        if rol == Rol.ASESOR_DE_SERVICIO and en_reparacion
        else [],
        "falta_de_refaccion": [t for t in trabajos if t.estado == EstadoTrabajo.AUTORIZADO]
        if rol == Rol.COMPRAS and estado in (EstadoOrden.EN_REPARACION, EstadoOrden.EN_ESPERA_DE_REFACCION)
        else [],
        "recepciones": ordenes_de_compra if rol == Rol.COMPRAS else [],
        "nueva_fecha": rol == Rol.ASESOR_DE_SERVICIO and estado == EstadoOrden.EN_ESPERA_DE_REFACCION,
        "evidencia_ingreso": rol == Rol.ASESOR_DE_SERVICIO
        and estado in (EstadoOrden.RECIBIDO, EstadoOrden.DIAGNOSTICADO),
        "evidencia_entrega": rol == Rol.ASESOR_DE_SERVICIO and estado == EstadoOrden.LISTO_PARA_ENTREGA,
        "cobrar": rol == Rol.CAJA
        and (estado == EstadoOrden.LISTO_PARA_ENTREGA or orden.rechazo_total_pendiente_de_cobro),
        "disputa": es_autorizador,
        "umbral": {
            "total_autorizado": str(orden.total_autorizado_inicial()),
            "acumulado": str(orden.ampliaciones_acumuladas()),
            "limite": str(Monto(orden.total_autorizado_inicial().valor * Decimal("0.20"))),
        },
    }


def _siguiente_paso(orden: OrdenDeServicio) -> str:
    if orden.rechazo_total_pendiente_de_cobro:
        return "El cliente rechazó la cotización. Caja debe cobrar el diagnóstico para cerrar la orden."
    pasos = {
        EstadoOrden.RECIBIDO: "El Técnico debe registrar el diagnóstico.",
        EstadoOrden.DIAGNOSTICADO: "El Asesor de Servicio debe generar y enviar la cotización.",
        EstadoOrden.EN_ESPERA_DE_AUTORIZACION: "El cliente debe autorizar o rechazar la solicitud enviada.",
        EstadoOrden.EN_ESPERA_DE_CLIENTE: "Pasaron 24 horas sin respuesta; el Gerente del Taller fue avisado. "
        "El cliente aún puede responder.",
        EstadoOrden.EN_REPARACION: "El Técnico ejecuta los trabajos autorizados.",
        EstadoOrden.EN_ESPERA_DE_REFACCION: "Compras espera la refacción. El Asesor debe avisar la nueva fecha.",
        EstadoOrden.LISTO_PARA_ENTREGA: "El Asesor registra las fotos de entrega y Caja cobra y cierra la orden.",
        EstadoOrden.CERRADO: "La orden está cerrada.",
        EstadoOrden.CERRADA_SIN_REPARACION: "La orden se cerró sin reparación.",
    }
    return pasos[orden.estado]


@router.get("/ordenes/{orden_id}", response_class=HTMLResponse)
def ver_orden(request: Request, orden_id: str):
    usuario = _usuario(request)
    if usuario is None:
        return _ir("/", "Elige tu rol para continuar.", "error")
    c = _contenedor(request)
    try:
        vista = c.consultar_estado.manejar(ConsultarEstadoVehiculoQuery(usuario, orden_id))
    except ErrorDeDominio as error:
        return _ir("/", error.mensaje, "error")
    orden = c.repos.ordenes.obtener_por_id(orden_id)
    cobro = None
    acciones = _acciones(usuario, orden, c)
    if acciones["cobrar"]:
        cobro = c.detalle_para_cobro.manejar(ObtenerDetalleParaCobroQuery(usuario, orden_id))
    return _pagina(
        request,
        "orden.html",
        orden=vista,
        acciones=acciones,
        cobro=cobro,
        siguiente_paso=_siguiente_paso(orden),
        hoy=date.today().isoformat(),
        categorias=[c.value for c in CategoriaDisputa],
    )


def _accion(request: Request, orden_id: str, funcion, exito: str):
    try:
        funcion()
    except ErrorDeDominio as error:
        return _ir(f"/ordenes/{orden_id}", error.mensaje, "error")
    return _ir(f"/ordenes/{orden_id}", exito)


@router.post("/ordenes/{orden_id}/diagnostico")
async def diagnostico(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.registrar_diagnostico.registrar(u, orden_id, f.get("falla", "")),
        "Diagnóstico registrado. La orden pasó a «Diagnosticado».",
    )


@router.post("/ordenes/{orden_id}/cotizacion")
async def cotizacion(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.generar_cotizacion.generar_y_enviar(u, orden_id, _lineas(f)),
        "Cotización enviada al cliente. La orden quedó «En espera de autorización».",
    )


@router.post("/ordenes/{orden_id}/cotizaciones/{cotizacion_id}/autorizacion")
async def autorizacion(request: Request, orden_id: str, cotizacion_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    autorizados = [k.removeprefix("decision_") for k, v in f.items() if k.startswith("decision_") and v == "autorizar"]
    rechazados = [k.removeprefix("decision_") for k, v in f.items() if k.startswith("decision_") and v == "rechazar"]
    comando = AutorizarTrabajosCommand(u, orden_id, cotizacion_id, autorizados, rechazados, _evidencia_digital(u, f))
    return _accion(
        request,
        orden_id,
        lambda: c.autorizar_trabajos.autorizar_trabajos(comando),
        "Tu decisión quedó registrada con evidencia digital.",
    )


@router.post("/ordenes/{orden_id}/trabajos/{trabajo_id}/iniciar")
def iniciar(request: Request, orden_id: str, trabajo_id: str):
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.ejecutar_trabajo.iniciar(u, orden_id, trabajo_id),
        "El trabajo pasó a «En ejecución».",
    )


@router.post("/ordenes/{orden_id}/trabajos/{trabajo_id}/terminar")
def terminar(request: Request, orden_id: str, trabajo_id: str):
    c, u = _contenedor(request), _u(request)
    return _accion(
        request, orden_id, lambda: c.ejecutar_trabajo.terminar(u, orden_id, trabajo_id), "El trabajo quedó «Terminado»."
    )


@router.post("/ordenes/{orden_id}/falla-adicional")
async def falla_adicional(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    comando = ReportarFallaAdicionalCommand(u, orden_id, f.get("descripcion", ""))
    return _accion(
        request,
        orden_id,
        lambda: c.reportar_falla_adicional.reportar(comando),
        "Falla adicional reportada. El Asesor de Servicio generará la cotización complementaria.",
    )


@router.post("/ordenes/{orden_id}/cotizacion-complementaria")
async def cotizacion_complementaria(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.reportar_falla_adicional.generar_cotizacion_complementaria(u, orden_id, _lineas(f)),
        "Cotización complementaria enviada. La orden quedó «En espera de autorización».",
    )


@router.post("/ordenes/{orden_id}/ampliacion")
async def ampliacion(request: Request, orden_id: str):
    f = await _formulario(request)
    trabajo_id = str(f.get("trabajo", ""))
    c, u = _contenedor(request), _u(request)
    resultado: dict = {}

    def solicitar():
        resultado["ampliacion"] = c.solicitar_ampliacion.solicitar(
            u, orden_id, trabajo_id, f.get("monto", "0"), f.get("motivo", "")
        )

    respuesta = _accion(request, orden_id, solicitar, "")
    if "ampliacion" in resultado:
        a = resultado["ampliacion"]
        mensaje = (
            "La ampliación supera el 20 % y se envió al cliente para su autorización."
            if a.estado == EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION
            else "La ampliación no supera el 20 % del total autorizado y se aplicó."
        )
        return _ir(f"/ordenes/{orden_id}", mensaje)
    return respuesta


@router.post("/ordenes/{orden_id}/trabajos/{trabajo_id}/ampliaciones/{ampliacion_id}/decision")
async def decision_ampliacion(request: Request, orden_id: str, trabajo_id: str, ampliacion_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    autoriza = f.get("decision") == "autorizar"
    return _accion(
        request,
        orden_id,
        lambda: c.autorizar_trabajos.decidir_ampliacion(
            u, orden_id, trabajo_id, ampliacion_id, autoriza, _evidencia_digital(u, f)
        ),
        "Tu decisión sobre la ampliación quedó registrada.",
    )


@router.post("/ordenes/{orden_id}/trabajos/{trabajo_id}/falta-de-refaccion")
async def falta_de_refaccion(request: Request, orden_id: str, trabajo_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.marcar_espera_de_refaccion.confirmar_falta_de_existencia(
            u, orden_id, trabajo_id, f.get("codigo", ""), f.get("proveedor", "")
        ),
        "Se generó la orden de compra. La orden quedó «En espera de refacción».",
    )


@router.post("/ordenes/{orden_id}/nueva-fecha")
async def nueva_fecha(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.notificar_nueva_fecha.notificar(u, orden_id, f.get("fecha", ""), f.get("motivo", "")),
        "Se avisó al cliente la nueva fecha de entrega.",
    )


@router.post("/ordenes-de-compra/{orden_de_compra_id}/recepcion")
async def recepcion(request: Request, orden_de_compra_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    destino = f.get("volver", "/compras")
    try:
        c.registrar_recepcion.registrar_recepcion(u, orden_de_compra_id)
    except ErrorDeDominio as error:
        return _ir(destino, error.mensaje, "error")
    return _ir(destino, "Refacción recibida. El trabajo vuelve a «Autorizado» y la reparación continúa.")


@router.post("/ordenes/{orden_id}/evidencia")
async def evidencia(request: Request, orden_id: str):
    formulario = await request.form()
    foto = formulario.get("foto")
    nombre = foto.filename if isinstance(foto, UploadFile) and foto.filename else ""
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.registrar_evidencia.registrar(u, orden_id, str(formulario.get("etapa", "")), nombre),
        "Evidencia fotográfica registrada.",
    )


@router.post("/ordenes/{orden_id}/cierre")
async def cierre(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    comando = CerrarOrdenDeServicioCommand(u, orden_id, f.get("pago") or "0")
    return _accion(request, orden_id, lambda: c.cerrar_orden.cerrar(comando), "Cobro registrado. La orden se cerró.")


@router.post("/ordenes/{orden_id}/disputa")
async def disputa(request: Request, orden_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    return _accion(
        request,
        orden_id,
        lambda: c.registrar_disputa.registrar(u, orden_id, f.get("categoria", ""), f.get("descripcion", "")),
        "Tu disputa quedó registrada. El Gerente del Taller la revisará.",
    )


# ----------------------------------------------------------- vistas por rol
@router.get("/cola", response_class=HTMLResponse)
def cola(request: Request):
    usuario = _u(request)
    try:
        ordenes = _contenedor(request).cola_de_atencion.manejar(ConsultarColaDeAtencionQuery(usuario))
    except ErrorDeDominio:
        return _ir("/", "La cola de atención la consultan el Asesor de Servicio y el Técnico.", "error")
    return _pagina(request, "cola.html", ordenes=ordenes)


@router.get("/compras", response_class=HTMLResponse)
def compras(request: Request):
    usuario = _u(request)
    try:
        ordenes_de_compra = _contenedor(request).listas.ordenes_de_compra(usuario)
    except ErrorDeDominio:
        return _ir("/", "Esta pantalla es para Compras.", "error")
    return _pagina(request, "compras.html", ordenes_de_compra=ordenes_de_compra)


@router.get("/caja", response_class=HTMLResponse)
def caja(request: Request):
    usuario = _u(request)
    c = _contenedor(request)
    try:
        facturaciones = c.listas.facturaciones(usuario)
    except ErrorDeDominio:
        return _ir("/", "Esta pantalla es para Caja.", "error")
    flotillas = [x for x in c.listas.clientes() if x["tipo"] == "Flotilla"]
    return _pagina(
        request,
        "caja.html",
        facturaciones=facturaciones,
        flotillas=flotillas,
        periodo=c.reloj.ahora().strftime("%Y-%m"),
    )


@router.post("/caja/facturacion")
async def facturacion(request: Request):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    try:
        resultado = c.generar_facturacion.generar(u, f.get("cliente_id", ""), f.get("periodo", ""))
    except ErrorDeDominio as error:
        return _ir("/caja", error.mensaje, "error")
    return _ir(
        "/caja",
        f"Facturación consolidada generada por {resultado.total} ({len(resultado.ordenes_de_servicio)} órdenes).",
    )


@router.get("/gerente", response_class=HTMLResponse)
def gerente(request: Request):
    usuario = _u(request)
    c = _contenedor(request)
    hoy = c.reloj.ahora().date()
    desde = request.query_params.get("desde") or (hoy - timedelta(days=30)).isoformat()
    hasta = request.query_params.get("hasta") or hoy.isoformat()
    try:
        indicadores = c.indicadores.manejar(
            ObtenerIndicadoresQuery(usuario, date.fromisoformat(desde), date.fromisoformat(hasta))
        )
        avisos = c.listas.avisos_al_gerente(usuario)
    except ValueError:
        return _ir("/gerente", "Selecciona fechas válidas.", "error")
    except ErrorDeDominio as error:
        return _ir("/", error.mensaje, "error")
    return _pagina(request, "gerente.html", indicadores=indicadores, avisos=avisos, desde=desde, hasta=hasta)


@router.post("/gerente/plazos")
def plazos(request: Request):
    c, u = _contenedor(request), _u(request)
    try:
        escaladas = c.procesar_plazos.procesar(u)
    except ErrorDeDominio as error:
        return _ir("/gerente", error.mensaje, "error")
    if not escaladas:
        return _ir("/gerente", "No hay solicitudes con 24 horas o más sin respuesta.")
    return _ir("/gerente", "Pasaron a «En espera de cliente»: " + ", ".join(o.folio for o in escaladas) + ".")


@router.get("/disputas", response_class=HTMLResponse)
def disputas(request: Request):
    usuario = _usuario(request)
    if usuario is None:
        return _ir("/", "Elige tu rol para continuar.", "error")
    return _pagina(request, "disputas.html", disputas=_contenedor(request).listas.disputas(usuario))


@router.post("/disputas/{disputa_id}/resolucion")
async def resolver(request: Request, disputa_id: str):
    f = await _formulario(request)
    c, u = _contenedor(request), _u(request)
    try:
        c.resolver_disputa.resolver(u, disputa_id, f.get("resolucion", ""))
    except ErrorDeDominio as error:
        return _ir("/disputas", error.mensaje, "error")
    return _ir("/disputas", "La disputa quedó «Resuelta».")
