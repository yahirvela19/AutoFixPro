"""Persistencia transaccional (commit y rollback) y servicio externo de avisos simulado con Mock."""

from __future__ import annotations

from unittest.mock import ANY, Mock

import pytest
from sqlalchemy import insert, select

from src.application.contenedor import construir_contenedor
from src.domain.cliente import Cliente
from src.domain.estados import EstadoOrden
from src.infrastructure.adaptadores import DespachadorEnMemoria, RelojFijo
from src.infrastructure.persistencia import TABLAS, crear_motor, repositorios_sql
from src.infrastructure.serializacion import a_json
from tests.conftest import ASESOR, INICIO, TECNICO


@pytest.fixture
def contenedor_sql():
    motor = crear_motor("sqlite://")
    reloj = RelojFijo(INICIO)
    c = construir_contenedor(repositorios_sql(motor), reloj, Mock(), DespachadorEnMemoria())
    c.repos.clientes.guardar(Cliente("CLI-001", "Ana López"))
    return c, motor


def _ingreso(c, placa="E4-250"):
    return c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id="CLI-001",
        placa=placa,
        marca="Kia",
        modelo="Rio",
        vin="KNA1",
        kilometraje=250,
        nivel_combustible="1/2",
        danos_visibles="",
        motivo_ingreso="Servicio",
    )


# ----------------------------------------------------- commit y rollback
def test_commit_persiste_la_orden(contenedor_sql):
    c, motor = contenedor_sql
    orden = _ingreso(c)  # guardar() abre la transacción y hace commit
    recuperada = repositorios_sql(motor).ordenes.obtener_por_id(orden.id)
    assert recuperada.id == orden.id
    assert recuperada.folio == "OS-0001"
    assert recuperada.inspeccion.kilometraje == 250
    assert recuperada.estado == EstadoOrden.RECIBIDO


def test_rollback_descarta_la_orden(contenedor_sql):
    c, motor = contenedor_sql
    orden = _ingreso(c, placa="E4-RB")
    tabla = TABLAS["ordenes_de_servicio"]
    orden.id = "orden-con-rollback"
    with pytest.raises(RuntimeError), motor.begin() as conexion:
        conexion.execute(insert(tabla).values(id=orden.id, datos=a_json(orden)))
        raise RuntimeError("falla a mitad de la transacción")  # provoca el rollback
    with motor.connect() as conexion:
        assert conexion.execute(select(tabla.c.id).where(tabla.c.id == orden.id)).first() is None
    assert repositorios_sql(motor).ordenes.obtener_por_id("orden-con-rollback") is None


# ------------------------------------------------- servicio externo (Mock)
def test_aviso_al_cliente_con_mock_sin_envio_real(contenedor_sql):
    c, _ = contenedor_sql
    orden = _ingreso(c)
    c.registrar_diagnostico.registrar(TECNICO, orden.id, "Balatas gastadas")
    c.generar_cotizacion.generar_y_enviar(ASESOR, orden.id, [{"descripcion": "Balatas", "precio_unitario": "1200"}])
    c.notificaciones.notificar_cliente.assert_called_once_with("CLI-001", orden.id, ANY)
    mensaje = c.notificaciones.notificar_cliente.call_args.args[2]
    assert "$1,200.00 MXN" in mensaje
    assert c.repos.ordenes.obtener_por_id(orden.id).estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION


def test_falla_del_proveedor_de_avisos(contenedor_sql):
    c, _ = contenedor_sql
    c.notificaciones.notificar_cliente.side_effect = RuntimeError("proveedor de mensajes no disponible")
    orden = _ingreso(c)
    c.registrar_diagnostico.registrar(TECNICO, orden.id, "Balatas gastadas")
    with pytest.raises(RuntimeError, match="no disponible"):
        c.generar_cotizacion.generar_y_enviar(ASESOR, orden.id, [{"descripcion": "Balatas", "precio_unitario": "1200"}])
    c.notificaciones.notificar_cliente.assert_called_once()
    # Riesgo documentado (ADR-011): la cotización se guarda antes del aviso; la orden queda enviada sin aviso.
    assert c.repos.ordenes.obtener_por_id(orden.id).estado == EstadoOrden.EN_ESPERA_DE_AUTORIZACION
