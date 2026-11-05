"""Cálculo de importes de la cotización y del cobro (Arrange–Act–Assert)."""

from __future__ import annotations

from src.application.comandos import AutorizarTrabajosCommand
from src.domain.estados import EstadoOrden
from tests.conftest import ASESOR, CLIENTE, EVIDENCIA, TECNICO, ingreso, terminar_todo


def test_total_de_cotizacion_con_cantidades(c):
    # Arrange: orden diagnosticada
    orden = ingreso(c)
    c.registrar_diagnostico.registrar(TECNICO, orden.id, "Bujías desgastadas")
    # Act: 4 bujías de $150 y una limpieza de $800
    cotizacion = c.generar_cotizacion.generar_y_enviar(
        ASESOR,
        orden.id,
        [
            {"descripcion": "Cambio de bujías", "cantidad": 4, "precio_unitario": "150"},
            {"descripcion": "Limpieza de inyectores", "cantidad": 1, "precio_unitario": "800"},
        ],
    )
    # Assert: total = 4 × 150 + 1 × 800 y la orden espera autorización
    assert str(cotizacion.total) == "$1,400.00 MXN"
    assert c.repos.ordenes.obtener_por_id(orden.id).estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION


def test_cobro_incluye_diagnostico_solo_si_fue_aceptado(c):
    totales = {}
    for placa, aceptado in (("ACEP-1", True), ("NOAC-1", False)):
        # Arrange: orden con cargo de diagnóstico de $350, aceptado o no al ingreso
        orden = ingreso(c, placa=placa, cargo="350", aceptado=aceptado)
        c.registrar_diagnostico.registrar(TECNICO, orden.id, "Falla")
        cotizacion = c.generar_cotizacion.generar_y_enviar(
            ASESOR, orden.id, [{"descripcion": "Trabajo", "cantidad": 1, "precio_unitario": "1000"}]
        )
        c.autorizar_trabajos.autorizar_trabajos(
            AutorizarTrabajosCommand(CLIENTE, orden.id, cotizacion.id, [cotizacion.trabajos[0].id], [], EVIDENCIA)
        )
        # Act: el técnico termina el trabajo
        totales[aceptado] = terminar_todo(c, orden.id).total_cobrable()
    # Assert: RN-10 / RN-11
    assert str(totales[True]) == "$1,350.00 MXN"
    assert str(totales[False]) == "$1,000.00 MXN"
