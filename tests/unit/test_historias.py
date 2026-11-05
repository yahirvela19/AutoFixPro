"""Pruebas de aceptación por historia de usuario (nombres de docs/architecture/Trazabilidad.md)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

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
from src.domain import eventos as ev
from src.domain.errores import (
    AutorizadorNoValido,
    DatosIncompletos,
    DecisionYaRegistrada,
    RolNoPermitido,
    TransicionNoPermitida,
)
from src.domain.estados import (
    EstadoAmpliacion,
    EstadoOrden,
    EstadoOrdenDeCompra,
    EstadoTrabajo,
    EtapaEvidencia,
    transicionar_orden,
)
from tests.conftest import (
    ASESOR,
    CAJA,
    CLIENTE,
    COMPRAS,
    EVIDENCIA,
    GERENTE,
    OTRO_CLIENTE,
    RESPONSABLE,
    RESPONSABLE_AJENO,
    TECNICO,
    autorizar_todo,
    cotizada,
    en_reparacion,
    ingreso,
    terminar_todo,
)


def orden(c, orden_id):
    return c.repos.ordenes.obtener_por_id(orden_id)


# --------------------------------------------------------------------- US-01
def test_us01_registro_de_ingreso_crea_orden_recibido(c, reloj):
    nueva = ingreso(c)
    guardada = orden(c, nueva.id)
    assert guardada.estado == EstadoOrden.RECIBIDO
    assert guardada.fecha_hora_ingreso == reloj.ahora()
    assert guardada.folio == "OS-0001"
    assert guardada.historial[0].tipo == ev.VEHICULO_RECIBIDO


def test_us01_ingreso_con_datos_incompletos_se_rechaza(c):
    with pytest.raises(DatosIncompletos, match="motivo de ingreso"):
        c.registrar_ingreso.registrar(
            ASESOR,
            cliente_id="CLI-001",
            placa="ABC",
            marca="Ford",
            modelo="Ka",
            vin="X1",
            kilometraje=10,
            nivel_combustible="1/2",
            danos_visibles="",
            motivo_ingreso="",
        )
    with pytest.raises(DatosIncompletos, match="placa"):
        c.registrar_ingreso.registrar(
            ASESOR,
            cliente_id="CLI-001",
            placa="",
            marca="Ford",
            modelo="Ka",
            vin="X1",
            kilometraje=10,
            nivel_combustible="1/2",
            danos_visibles="",
            motivo_ingreso="Ruido",
        )
    with pytest.raises(RolNoPermitido):
        c.registrar_ingreso.registrar(
            TECNICO,
            cliente_id="CLI-001",
            placa="ABC",
            marca="Ford",
            modelo="Ka",
            vin="X1",
            kilometraje=10,
            nivel_combustible="1/2",
            danos_visibles="",
            motivo_ingreso="Ruido",
        )
    assert c.repos.ordenes.listar() == []


def test_us01_placa_de_otro_cliente_se_rechaza(c):
    ingreso(c, "CLI-001", "SMX-482-A")
    with pytest.raises(DatosIncompletos, match="otro cliente"):
        ingreso(c, "CLI-002", "SMX-482-A")


# --------------------------------------------------------------------- US-02
def test_us02_evidencia_fotografica_de_ingreso(c):
    nueva = ingreso(c, foto="frente.jpg")
    c.registrar_evidencia.registrar(ASESOR, nueva.id, "Ingreso", "lateral.jpg")
    evidencias = orden(c, nueva.id).evidencias
    assert [e.referencia_archivo for e in evidencias] == ["frente.jpg", "lateral.jpg"]
    assert all(e.etapa == EtapaEvidencia.INGRESO for e in evidencias)
    with pytest.raises(DatosIncompletos):
        c.registrar_evidencia.registrar(ASESOR, nueva.id, "Ingreso", "")
    with pytest.raises(TransicionNoPermitida):
        c.registrar_evidencia.registrar(ASESOR, nueva.id, "Entrega", "salida.jpg")


# --------------------------------------------------------------------- US-03
def test_us03_diagnostico_cambia_a_diagnosticado(c):
    nueva = ingreso(c)
    c.registrar_diagnostico.registrar(TECNICO, nueva.id, "Balatas gastadas")
    guardada = orden(c, nueva.id)
    assert guardada.estado == EstadoOrden.DIAGNOSTICADO
    assert guardada.diagnostico.tecnico_nombre == "Jorge Salinas"


def test_us03_diagnostico_vacio_se_rechaza(c):
    nueva = ingreso(c)
    with pytest.raises(DatosIncompletos):
        c.registrar_diagnostico.registrar(TECNICO, nueva.id, "   ")
    with pytest.raises(RolNoPermitido):
        c.registrar_diagnostico.registrar(ASESOR, nueva.id, "Falla")
    assert orden(c, nueva.id).estado == EstadoOrden.RECIBIDO


# --------------------------------------------------------------------- US-04
def test_us04_cotizacion_inicial_deja_trabajos_pendientes(c):
    orden_id, cotizacion = cotizada(c)
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION
    assert all(t.estado == EstadoTrabajo.PENDIENTE_DE_AUTORIZACION for t in guardada.todos_los_trabajos())
    assert str(cotizacion.total) == "$1,500.00 MXN"
    assert c.notificaciones.listar(destinatario="CLI-001", orden_id=orden_id)


def test_us04_cotizacion_sin_diagnostico_se_rechaza(c):
    nueva = ingreso(c)
    with pytest.raises(TransicionNoPermitida):
        c.generar_cotizacion.generar_y_enviar(ASESOR, nueva.id, [{"descripcion": "X", "precio_unitario": "10"}])
    c.registrar_diagnostico.registrar(TECNICO, nueva.id, "Falla")
    with pytest.raises(DatosIncompletos, match="al menos un trabajo"):
        c.generar_cotizacion.generar_y_enviar(ASESOR, nueva.id, [])
    with pytest.raises(DatosIncompletos, match="mayor a cero"):
        c.generar_cotizacion.generar_y_enviar(
            ASESOR, nueva.id, [{"descripcion": "X", "cantidad": 0, "precio_unitario": "10"}]
        )


# --------------------------------------------------------------- US-05 / 06
def test_us05_autorizacion_total(c):
    orden_id, cotizacion = cotizada(c)
    autorizar_todo(c, orden_id, cotizacion)
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.EN_REPARACION
    assert all(t.estado == EstadoTrabajo.AUTORIZADO for t in guardada.todos_los_trabajos())


def test_us05_autorizador_no_valido_se_rechaza(c):
    orden_id, cotizacion = cotizada(c)
    with pytest.raises(AutorizadorNoValido):
        autorizar_todo(c, orden_id, cotizacion, OTRO_CLIENTE)
    assert orden(c, orden_id).estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION


def test_us05_tecnico_no_puede_autorizar(c):
    orden_id, cotizacion = cotizada(c)
    for usuario in (TECNICO, ASESOR):
        with pytest.raises(AutorizadorNoValido):
            autorizar_todo(c, orden_id, cotizacion, usuario)
    assert all(t.estado == EstadoTrabajo.PENDIENTE_DE_AUTORIZACION for t in orden(c, orden_id).todos_los_trabajos())


def test_us06_autorizacion_parcial(c):
    orden_id, cotizacion = cotizada(c)
    a, b = cotizacion.trabajos
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, [a.id], [b.id], EVIDENCIA)
    )
    guardada = orden(c, orden_id)
    assert guardada.trabajo(a.id).estado == EstadoTrabajo.AUTORIZADO
    assert guardada.trabajo(b.id).estado == EstadoTrabajo.RECHAZADO
    assert [t.id for t in guardada.trabajos_ejecutables()] == [a.id]


# --------------------------------------------------------------------- US-07
def test_us07_registro_de_autorizacion_completo(c, reloj):
    orden_id, cotizacion = cotizada(c)
    registro = autorizar_todo(c, orden_id, cotizacion)
    guardado = orden(c, orden_id).cotizacion(cotizacion.id).registros[0]
    assert guardado == registro
    assert guardado.autorizador_id == "CLI-001" and guardado.rol.value == "Cliente Titular"
    assert guardado.fecha_hora == reloj.ahora()
    assert set(guardado.trabajos_autorizados) == {t.id for t in cotizacion.trabajos}
    assert guardado.referencia_evidencia_digital == EVIDENCIA


def test_us07_decision_ya_registrada_no_se_modifica(c):
    orden_id, cotizacion = cotizada(c)
    autorizar_todo(c, orden_id, cotizacion)
    with pytest.raises((DecisionYaRegistrada, TransicionNoPermitida)):
        c.autorizar_trabajos.autorizar_trabajos(
            AutorizarTrabajosCommand(
                CLIENTE, orden_id, cotizacion.id, [], [t.id for t in cotizacion.trabajos], EVIDENCIA
            )
        )
    assert len(orden(c, orden_id).cotizacion(cotizacion.id).registros) == 1


def test_us07_decision_incompleta_o_sin_evidencia_se_rechaza(c):
    orden_id, cotizacion = cotizada(c)
    a, b = cotizacion.trabajos
    for autorizados, rechazados, evidencia in (
        ([a.id], [], EVIDENCIA),
        ([a.id, b.id], [], " "),
        ([a.id], [a.id, b.id], EVIDENCIA),
    ):
        with pytest.raises(DatosIncompletos):
            c.autorizar_trabajos.autorizar_trabajos(
                AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, autorizados, rechazados, evidencia)
            )


# --------------------------------------------------------------------- US-08
def test_us08_solo_trabajos_autorizados_son_ejecutables(c):
    orden_id, cotizacion = cotizada(c)
    assert orden(c, orden_id).trabajos_ejecutables() == []
    autorizar_todo(c, orden_id, cotizacion)
    assert len(orden(c, orden_id).trabajos_ejecutables()) == 2


def test_us08_trabajo_no_autorizado_no_inicia(c):
    orden_id, cotizacion = cotizada(c)
    a, b = cotizacion.trabajos
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, [a.id], [b.id], EVIDENCIA)
    )
    with pytest.raises(TransicionNoPermitida):
        c.ejecutar_trabajo.iniciar(TECNICO, orden_id, b.id)
    with pytest.raises(TransicionNoPermitida):
        c.ejecutar_trabajo.terminar(TECNICO, orden_id, a.id)
    with pytest.raises(RolNoPermitido):
        c.ejecutar_trabajo.iniciar(ASESOR, orden_id, a.id)


def test_us08_ultimo_trabajo_terminado_deja_listo_para_entrega(c):
    orden_id, cotizacion = en_reparacion(c)
    a, b = cotizacion.trabajos
    c.ejecutar_trabajo.iniciar(TECNICO, orden_id, a.id)
    c.ejecutar_trabajo.terminar(TECNICO, orden_id, a.id)
    assert orden(c, orden_id).estado == EstadoOrden.EN_REPARACION
    c.ejecutar_trabajo.iniciar(TECNICO, orden_id, b.id)
    c.ejecutar_trabajo.terminar(TECNICO, orden_id, b.id)
    assert orden(c, orden_id).estado == EstadoOrden.LISTO_PARA_ENTREGA


# --------------------------------------------------------------------- US-09
def test_us09_falla_adicional_crea_cotizacion_complementaria(c):
    orden_id, _ = en_reparacion(c)
    c.reportar_falla_adicional.reportar(ReportarFallaAdicionalCommand(TECNICO, orden_id, "Fuga en radiador"))
    assert orden(c, orden_id).fallas_adicionales_por_cotizar == ["Fuga en radiador"]
    complementaria = c.reportar_falla_adicional.generar_cotizacion_complementaria(
        ASESOR, orden_id, [{"descripcion": "Cambio de manguera", "precio_unitario": "50"}]
    )
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION
    assert complementaria.tipo.value == "Complementaria"
    assert complementaria.trabajos[0].estado == EstadoTrabajo.PENDIENTE_DE_AUTORIZACION
    assert complementaria.descripcion_falla_adicional == "Fuga en radiador"
    with pytest.raises(TransicionNoPermitida):
        c.ejecutar_trabajo.iniciar(TECNICO, orden_id, complementaria.trabajos[0].id)


def test_us09_rechazo_complementaria_regresa_a_en_reparacion(c):
    orden_id, _ = en_reparacion(c)
    c.reportar_falla_adicional.reportar(ReportarFallaAdicionalCommand(TECNICO, orden_id, "Fuga"))
    complementaria = c.reportar_falla_adicional.generar_cotizacion_complementaria(
        ASESOR, orden_id, [{"descripcion": "Manguera", "precio_unitario": "50"}]
    )
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, complementaria.id, [], [complementaria.trabajos[0].id], EVIDENCIA)
    )
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.EN_REPARACION
    assert guardada.trabajo(complementaria.trabajos[0].id).estado == EstadoTrabajo.RECHAZADO


def test_us09_falla_adicional_requiere_reparacion_en_curso(c):
    nueva = ingreso(c)
    with pytest.raises(TransicionNoPermitida):
        c.reportar_falla_adicional.reportar(ReportarFallaAdicionalCommand(TECNICO, nueva.id, "Fuga"))
    orden_id, _ = en_reparacion(c, placa="OTRA-1")
    with pytest.raises(TransicionNoPermitida):
        c.reportar_falla_adicional.generar_cotizacion_complementaria(
            ASESOR, orden_id, [{"descripcion": "Manguera", "precio_unitario": "50"}]
        )


# --------------------------------------------------------------------- US-10
def test_us10_ampliacion_20_por_ciento_no_requiere_autorizacion(c):
    orden_id, cotizacion = en_reparacion(c, precios=("10000",))
    ampliacion = c.solicitar_ampliacion.solicitar(ASESOR, orden_id, cotizacion.trabajos[0].id, "2000.00", "Tornillería")
    assert ampliacion.estado == EstadoAmpliacion.AUTORIZADA
    assert orden(c, orden_id).estado == EstadoOrden.EN_REPARACION


def test_us10_ampliacion_mayor_20_por_ciento_bloquea_trabajo(c):
    orden_id, cotizacion = en_reparacion(c, precios=("10000",))
    trabajo_id = cotizacion.trabajos[0].id
    c.solicitar_ampliacion.solicitar(ASESOR, orden_id, trabajo_id, "1999.99", "Primera")
    segunda = c.solicitar_ampliacion.solicitar(ASESOR, orden_id, trabajo_id, "0.02", "Acumulada")
    assert segunda.estado == EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION
    assert orden(c, orden_id).estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION
    with pytest.raises(TransicionNoPermitida):
        c.ejecutar_trabajo.iniciar(TECNICO, orden_id, trabajo_id)
    with pytest.raises(AutorizadorNoValido):
        c.autorizar_trabajos.decidir_ampliacion(TECNICO, orden_id, trabajo_id, segunda.id, True, EVIDENCIA)
    with pytest.raises(DatosIncompletos):
        c.autorizar_trabajos.decidir_ampliacion(CLIENTE, orden_id, trabajo_id, segunda.id, True, "")
    c.autorizar_trabajos.decidir_ampliacion(CLIENTE, orden_id, trabajo_id, segunda.id, True, EVIDENCIA)
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.EN_REPARACION
    c.ejecutar_trabajo.iniciar(TECNICO, orden_id, trabajo_id)
    c.ejecutar_trabajo.terminar(TECNICO, orden_id, trabajo_id)
    assert str(orden(c, orden_id).total_cobrable()) == "$12,000.01 MXN"


def test_us10_ampliacion_rechazada_continua_con_monto_autorizado(c):
    orden_id, cotizacion = en_reparacion(c, precios=("1000",))
    trabajo_id = cotizacion.trabajos[0].id
    ampliacion = c.solicitar_ampliacion.solicitar(ASESOR, orden_id, trabajo_id, "500", "Pieza extra")
    c.autorizar_trabajos.decidir_ampliacion(CLIENTE, orden_id, trabajo_id, ampliacion.id, False, EVIDENCIA)
    with pytest.raises(DecisionYaRegistrada):
        c.autorizar_trabajos.decidir_ampliacion(CLIENTE, orden_id, trabajo_id, ampliacion.id, True, EVIDENCIA)
    final = terminar_todo(c, orden_id)
    assert str(final.total_cobrable()) == "$1,000.00 MXN"


# ----------------------------------------------------------- US-11/12/13/23
def _falta_de_refaccion(c):
    orden_id, cotizacion = en_reparacion(c)
    trabajo_id = cotizacion.trabajos[0].id
    c.marcar_espera_de_refaccion.confirmar_falta_de_existencia(
        COMPRAS, orden_id, trabajo_id, "BAL-4410", "Refacciones del Norte"
    )
    return orden_id, trabajo_id


def test_us11_falta_de_existencia_genera_orden_de_compra(c):
    orden_id, trabajo_id = _falta_de_refaccion(c)
    [orden_de_compra] = c.repos.ordenes_de_compra.listar()
    assert orden_de_compra.trabajo_id == trabajo_id and orden_de_compra.estado == EstadoOrdenDeCompra.SOLICITADA
    assert orden_de_compra.proveedor == "Refacciones del Norte"


def test_us11_orden_de_compra_no_se_duplica(c):
    orden_id, trabajo_id = _falta_de_refaccion(c)
    evento = next(e for e in c.despachador.publicados if e.tipo == ev.REFACCION_SIN_EXISTENCIA_DETECTADA)
    assert c.solicitar_refaccion.al_detectar_refaccion_sin_existencia(evento) is None
    assert len(c.repos.ordenes_de_compra.listar()) == 1


def test_us12_orden_en_espera_de_refaccion(c):
    orden_id, trabajo_id = _falta_de_refaccion(c)
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.EN_ESPERA_DE_REFACCION
    assert guardada.trabajo(trabajo_id).estado == EstadoTrabajo.EN_ESPERA_DE_REFACCION
    with pytest.raises(TransicionNoPermitida):
        c.ejecutar_trabajo.iniciar(TECNICO, orden_id, trabajo_id)
    with pytest.raises(RolNoPermitido):
        c.marcar_espera_de_refaccion.confirmar_falta_de_existencia(ASESOR, orden_id, trabajo_id, "X", "Y")


def test_us13_nueva_fecha_notifica_al_cliente(c, reloj):
    orden_id, _ = _falta_de_refaccion(c)
    reloj.avanzar(minutes=40)
    fecha = (reloj.ahora().date() + timedelta(days=3)).isoformat()
    c.notificar_nueva_fecha.notificar(ASESOR, orden_id, fecha, "El proveedor entrega el lunes")
    guardada = orden(c, orden_id)
    assert guardada.nueva_fecha_estimada == date.fromisoformat(fecha)
    avisos = c.notificaciones.listar(destinatario="CLI-001", orden_id=orden_id)
    assert "Nueva fecha estimada" in avisos[0]["mensaje"]
    indicadores = c.indicadores.manejar(ObtenerIndicadoresQuery(GERENTE, reloj.ahora().date(), reloj.ahora().date()))
    assert indicadores["tiempo_promedio_comunicacion_retraso_minutos"] == "40"
    assert indicadores["porcentaje_avisos_menos_de_2_horas"] == "100.0 %"


def test_us13_fecha_anterior_a_hoy_se_rechaza(c, reloj):
    orden_id, _ = _falta_de_refaccion(c)
    ayer = (reloj.ahora().date() - timedelta(days=1)).isoformat()
    with pytest.raises(DatosIncompletos):
        c.notificar_nueva_fecha.notificar(ASESOR, orden_id, ayer, "Retraso")
    with pytest.raises(DatosIncompletos):
        c.notificar_nueva_fecha.notificar(ASESOR, orden_id, "no-es-fecha", "Retraso")


def test_us23_recepcion_reanuda_reparacion(c):
    orden_id, trabajo_id = _falta_de_refaccion(c)
    [orden_de_compra] = c.repos.ordenes_de_compra.listar()
    c.registrar_recepcion.registrar_recepcion(COMPRAS, orden_de_compra.id)
    guardada = orden(c, orden_id)
    assert c.repos.ordenes_de_compra.obtener_por_id(orden_de_compra.id).estado == EstadoOrdenDeCompra.RECIBIDA
    assert guardada.estado == EstadoOrden.EN_REPARACION
    assert guardada.trabajo(trabajo_id).estado == EstadoTrabajo.AUTORIZADO
    assert any("continúa" in a["mensaje"] for a in c.notificaciones.listar(destinatario="CLI-001"))
    c.ejecutar_trabajo.iniciar(TECNICO, orden_id, trabajo_id)


def test_us23_recepcion_duplicada_se_rechaza(c):
    _falta_de_refaccion(c)
    [orden_de_compra] = c.repos.ordenes_de_compra.listar()
    c.registrar_recepcion.registrar_recepcion(COMPRAS, orden_de_compra.id)
    with pytest.raises(DecisionYaRegistrada):
        c.registrar_recepcion.registrar_recepcion(COMPRAS, orden_de_compra.id)


# --------------------------------------------------------------------- US-14
def test_us14_cliente_consulta_su_orden(c):
    orden_id, _ = cotizada(c)
    vista = c.consultar_estado.manejar(ConsultarEstadoVehiculoQuery(CLIENTE, orden_id))
    assert vista["estado"] == "En espera de autorización"
    assert vista["cotizaciones"][0]["trabajos"][0]["estado"] == "Pendiente de autorización"


def test_us14_orden_ajena_acceso_negado(c):
    orden_id, _ = cotizada(c)
    with pytest.raises(AutorizadorNoValido):
        c.consultar_estado.manejar(ConsultarEstadoVehiculoQuery(OTRO_CLIENTE, orden_id))
    assert [o["id"] for o in c.listar_ordenes.manejar(OTRO_CLIENTE)] == []


# --------------------------------------------------------------------- US-15
def test_us15_indicadores_del_periodo(c, reloj):
    orden_id, cotizacion = en_reparacion(c)
    terminar_todo(c, orden_id)
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, "1500"))
    c.registrar_disputa.registrar(CLIENTE, orden_id, "Cobro", "No reconozco un cargo")
    hoy = reloj.ahora().date()
    indicadores = c.indicadores.manejar(ObtenerIndicadoresQuery(GERENTE, hoy, hoy))
    assert indicadores["ordenes_cerradas"] == 1
    assert indicadores["disputas_registradas"] == 1
    assert indicadores["porcentaje_con_evidencia_digital"] == "100.0 %"
    with pytest.raises(DatosIncompletos):
        c.indicadores.manejar(ObtenerIndicadoresQuery(GERENTE, hoy, hoy - timedelta(days=1)))


def test_us15_solo_gerente_consulta_indicadores(c, reloj):
    hoy = reloj.ahora().date()
    with pytest.raises(RolNoPermitido):
        c.indicadores.manejar(ObtenerIndicadoresQuery(ASESOR, hoy, hoy))


# --------------------------------------------------------------------- US-16
def test_us16_responsable_de_cuenta_autoriza(c):
    orden_id, cotizacion = cotizada(c, "FLO-001", "NLE-207-C")
    registro = autorizar_todo(c, orden_id, cotizacion, RESPONSABLE)
    assert registro.rol.value == "Responsable de Cuenta"
    assert orden(c, orden_id).estado == EstadoOrden.EN_REPARACION


def test_us16_contacto_no_registrado_se_rechaza(c):
    orden_id, cotizacion = cotizada(c, "FLO-001", "NLE-207-C")
    for usuario in (RESPONSABLE_AJENO, CLIENTE):
        with pytest.raises(AutorizadorNoValido):
            autorizar_todo(c, orden_id, cotizacion, usuario)


# --------------------------------------------------------------------- US-17
def test_us17_consolida_ordenes_cerradas_del_mes(c):
    for placa in ("NLE-1", "NLE-2"):
        orden_id, _ = en_reparacion(c, precios=("1000",), cliente_id="FLO-001", placa=placa)
        terminar_todo(c, orden_id)
        c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id))
    facturacion = c.generar_facturacion.generar(CAJA, "FLO-001", "2026-11")
    assert len(facturacion.ordenes_de_servicio) == 2
    assert str(facturacion.total) == "$2,000.00 MXN"
    with pytest.raises(DatosIncompletos):
        c.generar_facturacion.generar(CAJA, "FLO-001", "noviembre")
    with pytest.raises(DatosIncompletos):
        c.generar_facturacion.generar(CAJA, "CLI-001", "2026-11")


def test_us17_orden_no_se_factura_dos_veces(c):
    orden_id, _ = en_reparacion(c, precios=("1000",), cliente_id="FLO-001", placa="NLE-1")
    terminar_todo(c, orden_id)
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id))
    c.generar_facturacion.generar(CAJA, "FLO-001", "2026-11")
    with pytest.raises(DatosIncompletos, match="sin facturar"):
        c.generar_facturacion.generar(CAJA, "FLO-001", "2026-11")


# --------------------------------------------------------------------- US-18
def test_us18_prioridad_contractual_primero_en_cola_de_atencion(c, reloj):
    particular = ingreso(c, "CLI-001", "AAA-1")
    reloj.avanzar(minutes=5)
    sin_prioridad = ingreso(c, "FLO-002", "BBB-2")
    reloj.avanzar(minutes=5)
    con_prioridad = ingreso(c, "FLO-001", "CCC-3")
    cola = c.cola_de_atencion.manejar(ConsultarColaDeAtencionQuery(ASESOR))
    assert [o["id"] for o in cola] == [con_prioridad.id, particular.id, sin_prioridad.id]
    assert cola[0]["prioridad_contractual"] is True
    with pytest.raises(RolNoPermitido):
        c.cola_de_atencion.manejar(ConsultarColaDeAtencionQuery(CAJA))


# --------------------------------------------------------------------- US-19
def test_us19_solo_se_cobran_trabajos_terminados(c):
    orden_id, cotizacion = cotizada(c, cargo="350", aceptado=True)
    a, b = cotizacion.trabajos
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, [a.id], [b.id], EVIDENCIA)
    )
    terminar_todo(c, orden_id)
    detalle = c.detalle_para_cobro.manejar(ObtenerDetalleParaCobroQuery(CAJA, orden_id))
    assert [x["concepto"] for x in detalle["conceptos"]] == ["Diagnóstico", "Trabajo 1 (x1)"]
    assert detalle["total"] == "$1,350.00 MXN"


def test_us19_pago_cierra_la_orden(c):
    orden_id, _ = en_reparacion(c)
    terminar_todo(c, orden_id)
    with pytest.raises(DatosIncompletos, match="insuficiente"):
        c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, "100"))
    with pytest.raises(RolNoPermitido):
        c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(ASESOR, orden_id, "1500"))
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, "1500"))
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.CERRADO
    assert str(guardada.monto_pagado) == "$1,500.00 MXN"


def test_us19_no_se_cierra_antes_de_listo_para_entrega(c):
    orden_id, _ = en_reparacion(c)
    with pytest.raises(TransicionNoPermitida):
        c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, "1500"))


# --------------------------------------------------------------------- US-20
def test_us20_evidencia_fotografica_de_entrega(c):
    orden_id, _ = en_reparacion(c)
    terminar_todo(c, orden_id)
    c.registrar_evidencia.registrar(ASESOR, orden_id, "Entrega", "salida.jpg")
    assert orden(c, orden_id).evidencias[-1].etapa == EtapaEvidencia.ENTREGA


# --------------------------------------------------------------------- US-21
def test_us21_rechazo_total_con_diagnostico_aceptado(c):
    orden_id, cotizacion = cotizada(c, cargo="350", aceptado=True)
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, [], [t.id for t in cotizacion.trabajos], EVIDENCIA)
    )
    guardada = orden(c, orden_id)
    assert guardada.rechazo_total_pendiente_de_cobro
    assert guardada.estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION
    detalle = c.detalle_para_cobro.manejar(ObtenerDetalleParaCobroQuery(CAJA, orden_id))
    assert detalle["total"] == "$350.00 MXN" and detalle["rechazo_total"]
    with pytest.raises(DatosIncompletos):
        c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, "100"))
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, "350"))
    assert orden(c, orden_id).estado == EstadoOrden.CERRADA_SIN_REPARACION


def test_us21_rechazo_total_sin_cargo(c):
    orden_id, cotizacion = cotizada(c)
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, [], [t.id for t in cotizacion.trabajos], EVIDENCIA)
    )
    guardada = orden(c, orden_id)
    assert guardada.estado == EstadoOrden.CERRADA_SIN_REPARACION
    assert guardada.total_cobrable().valor == 0


def test_rn14_orden_cerrada_no_se_reabre(c):
    orden_id, cotizacion = cotizada(c)
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(CLIENTE, orden_id, cotizacion.id, [], [t.id for t in cotizacion.trabajos], EVIDENCIA)
    )
    for destino in EstadoOrden:
        with pytest.raises(TransicionNoPermitida):
            transicionar_orden(EstadoOrden.CERRADA_SIN_REPARACION, destino)
    with pytest.raises(TransicionNoPermitida):
        c.registrar_evidencia.registrar(ASESOR, orden_id, "Ingreso", "tarde.jpg")


# --------------------------------------------------------------------- US-22
def test_us22_23h59_no_escala(c, reloj):
    orden_id, _ = cotizada(c)
    reloj.avanzar(hours=23, minutes=59)
    assert c.procesar_plazos.procesar(GERENTE) == []
    assert orden(c, orden_id).estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION


def test_us22_24h_escala_y_notifica_una_vez(c, reloj):
    orden_id, _ = cotizada(c)
    reloj.avanzar(hours=24)
    assert [o.id for o in c.procesar_plazos.procesar(GERENTE)] == [orden_id]
    assert orden(c, orden_id).estado == EstadoOrden.EN_ESPERA_DE_CLIENTE
    assert c.procesar_plazos.procesar(GERENTE) == []
    assert len(c.notificaciones.listar(destinatario="GERENTE")) == 1
    with pytest.raises(RolNoPermitido):
        c.procesar_plazos.procesar(ASESOR)


def test_us22_respuesta_tardia_pasa_a_en_reparacion(c, reloj):
    orden_id, cotizacion = cotizada(c)
    reloj.avanzar(hours=30)
    c.procesar_plazos.procesar(GERENTE)
    autorizar_todo(c, orden_id, cotizacion)
    assert orden(c, orden_id).estado == EstadoOrden.EN_REPARACION


# --------------------------------------------------------------------- US-24
def test_us24_cliente_registra_disputa(c):
    orden_id, _ = cotizada(c)
    disputa = c.registrar_disputa.registrar(CLIENTE, orden_id, "Autorización", "No autoricé ese trabajo")
    assert disputa.estado.value == "Abierta"
    with pytest.raises(AutorizadorNoValido):
        c.registrar_disputa.registrar(OTRO_CLIENTE, orden_id, "Cobro", "No es mía")
    with pytest.raises(DatosIncompletos):
        c.registrar_disputa.registrar(CLIENTE, orden_id, "Otra", "Categoría inválida")
    assert c.notificaciones.listar(destinatario="GERENTE")


def test_us24_gerente_resuelve_disputa(c):
    orden_id, _ = cotizada(c)
    disputa = c.registrar_disputa.registrar(CLIENTE, orden_id, "Cobro", "Cobro duplicado")
    with pytest.raises(RolNoPermitido):
        c.resolver_disputa.resolver(CLIENTE, disputa.id, "Yo misma")
    resuelta = c.resolver_disputa.resolver(GERENTE, disputa.id, "Se verificó el registro de autorización")
    assert resuelta.estado.value == "Resuelta"
    with pytest.raises(DecisionYaRegistrada):
        c.resolver_disputa.resolver(GERENTE, disputa.id, "Otra vez")
    assert c.listas.disputas(CLIENTE)[0]["estado"] == "Resuelta"
    assert c.listas.disputas(OTRO_CLIENTE) == []
