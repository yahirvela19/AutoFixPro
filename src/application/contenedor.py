"""Raíz de composición: conecta servicios, consultas y manejadores de eventos."""

from __future__ import annotations

from dataclasses import dataclass

from src.application import consultas as q
from src.application import servicios as s
from src.application.puertos import IReloj, Repositorios
from src.domain import eventos as ev


@dataclass
class Contenedor:
    repos: Repositorios
    reloj: IReloj
    notificaciones: object
    despachador: object
    registrar_ingreso: s.RegistrarIngresoService
    registrar_diagnostico: s.RegistrarDiagnosticoService
    generar_cotizacion: s.GenerarCotizacionService
    autorizar_trabajos: s.AutorizarTrabajosService
    reportar_falla_adicional: s.ReportarFallaAdicionalService
    solicitar_ampliacion: s.SolicitarReautorizacionDeAmpliacionService
    marcar_espera_de_refaccion: s.MarcarEsperaDeRefaccionService
    solicitar_refaccion: s.SolicitarRefaccionAProveedorService
    notificar_nueva_fecha: s.NotificarNuevaFechaEntregaService
    registrar_recepcion: s.RegistrarRecepcionDeRefaccionService
    reanudar_reparacion: s.ReanudarReparacionService
    ejecutar_trabajo: s.EjecutarTrabajoService
    registrar_evidencia: s.RegistrarEvidenciaFotograficaService
    cerrar_orden: s.CerrarOrdenDeServicioService
    generar_facturacion: s.GenerarFacturacionConsolidadaService
    procesar_plazos: s.ProcesarPlazosDeRespuestaService
    registrar_disputa: s.RegistrarDisputaService
    resolver_disputa: s.ResolverDisputaService
    listar_ordenes: q.ListarOrdenesHandler
    consultar_estado: q.ConsultarEstadoVehiculoHandler
    detalle_para_cobro: q.ObtenerDetalleParaCobroHandler
    indicadores: q.ObtenerIndicadoresHandler
    cola_de_atencion: q.ConsultarColaDeAtencionHandler
    listas: q.ListasDelTallerHandler


def construir_contenedor(
    repos: Repositorios, reloj: IReloj, notificaciones, despachador, plazo_horas: int = 24
) -> Contenedor:
    base = (repos, reloj, despachador, notificaciones, notificaciones)
    contenedor = Contenedor(
        repos=repos,
        reloj=reloj,
        notificaciones=notificaciones,
        despachador=despachador,
        registrar_ingreso=s.RegistrarIngresoService(*base),
        registrar_diagnostico=s.RegistrarDiagnosticoService(*base),
        generar_cotizacion=s.GenerarCotizacionService(*base),
        autorizar_trabajos=s.AutorizarTrabajosService(*base),
        reportar_falla_adicional=s.ReportarFallaAdicionalService(*base),
        solicitar_ampliacion=s.SolicitarReautorizacionDeAmpliacionService(*base),
        marcar_espera_de_refaccion=s.MarcarEsperaDeRefaccionService(*base),
        solicitar_refaccion=s.SolicitarRefaccionAProveedorService(*base),
        notificar_nueva_fecha=s.NotificarNuevaFechaEntregaService(*base),
        registrar_recepcion=s.RegistrarRecepcionDeRefaccionService(*base),
        reanudar_reparacion=s.ReanudarReparacionService(*base),
        ejecutar_trabajo=s.EjecutarTrabajoService(*base),
        registrar_evidencia=s.RegistrarEvidenciaFotograficaService(*base),
        cerrar_orden=s.CerrarOrdenDeServicioService(*base),
        generar_facturacion=s.GenerarFacturacionConsolidadaService(*base),
        procesar_plazos=s.ProcesarPlazosDeRespuestaService(*base, plazo_horas=plazo_horas),
        registrar_disputa=s.RegistrarDisputaService(*base),
        resolver_disputa=s.ResolverDisputaService(*base),
        listar_ordenes=q.ListarOrdenesHandler(repos, notificaciones),
        consultar_estado=q.ConsultarEstadoVehiculoHandler(repos, notificaciones),
        detalle_para_cobro=q.ObtenerDetalleParaCobroHandler(repos, notificaciones),
        indicadores=q.ObtenerIndicadoresHandler(repos, notificaciones),
        cola_de_atencion=q.ConsultarColaDeAtencionHandler(repos, notificaciones),
        listas=q.ListasDelTallerHandler(repos, notificaciones),
    )
    despachador.suscribir(
        ev.REFACCION_SIN_EXISTENCIA_DETECTADA, contenedor.solicitar_refaccion.al_detectar_refaccion_sin_existencia
    )
    despachador.suscribir(ev.REFACCION_RECIBIDA, contenedor.reanudar_reparacion.al_recibir_refaccion)
    return contenedor
