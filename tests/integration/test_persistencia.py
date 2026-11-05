"""Repositorios SQL: los Aggregates se guardan y recuperan sin perder tipos del dominio (ADR-009)."""

from __future__ import annotations

import os

from src.application.comandos import AutorizarTrabajosCommand
from src.application.contenedor import construir_contenedor
from src.domain.estados import EstadoOrden, EstadoTrabajo
from src.domain.orden_de_servicio import OrdenDeServicio
from src.domain.value_objects import Monto
from src.infrastructure.adaptadores import DespachadorEnMemoria, NotificacionSimulada, RelojFijo
from src.infrastructure.datos_demo import CLIENTES
from src.infrastructure.persistencia import crear_motor, metadata, repositorios_sql
from tests.conftest import ASESOR, CLIENTE, EVIDENCIA, INICIO, TECNICO

URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


def test_persistencia_de_la_orden_completa_y_notificaciones():
    motor = crear_motor(URL)
    try:
        reloj = RelojFijo(INICIO)
        c = construir_contenedor(
            repositorios_sql(motor), reloj, NotificacionSimulada(reloj, motor), DespachadorEnMemoria()
        )
        for cliente in CLIENTES:
            c.repos.clientes.guardar(cliente)
        orden = c.registrar_ingreso.registrar(
            ASESOR,
            cliente_id="CLI-001",
            placa="SQL-1",
            marca="VW",
            modelo="Jetta",
            vin="3VW1",
            kilometraje=10,
            nivel_combustible="1/2",
            danos_visibles="",
            motivo_ingreso="Revisión",
            cargo_diagnostico="250",
            cargo_diagnostico_aceptado=True,
            foto_ingreso="f.jpg",
        )
        c.registrar_diagnostico.registrar(TECNICO, orden.id, "Falla")
        cotizacion = c.generar_cotizacion.generar_y_enviar(
            ASESOR,
            orden.id,
            [{"descripcion": "A", "precio_unitario": "100.10"}, {"descripcion": "B", "precio_unitario": "5"}],
        )
        c.autorizar_trabajos.autorizar_trabajos(
            AutorizarTrabajosCommand(
                CLIENTE, orden.id, cotizacion.id, [cotizacion.trabajos[0].id], [cotizacion.trabajos[1].id], EVIDENCIA
            )
        )

        recuperada = repositorios_sql(motor).ordenes.obtener_por_id(orden.id)
        assert isinstance(recuperada, OrdenDeServicio)
        assert recuperada.estado == EstadoOrden.EN_REPARACION
        assert recuperada.cargo_diagnostico == Monto.de("250")
        assert recuperada.fecha_hora_ingreso == INICIO
        assert [t.estado for t in recuperada.todos_los_trabajos()] == [
            EstadoTrabajo.AUTORIZADO,
            EstadoTrabajo.RECHAZADO,
        ]
        assert recuperada.cotizaciones[0].registros[0].trabajos_autorizados == (cotizacion.trabajos[0].id,)
        assert recuperada.eventos_pendientes == [] and len(recuperada.historial) >= 5
        assert c.repos.ordenes.obtener_por_id("no-existe") is None
        assert len(c.repos.clientes.listar()) == len(CLIENTES)
        assert c.notificaciones.listar(destinatario="CLI-001")[0]["orden_id"] == orden.id
    finally:
        if not URL.startswith("sqlite"):
            metadata.drop_all(motor)
