"""Fixtures comunes: contenedor en memoria, reloj controlable y usuarios del glosario."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.application.comandos import AutorizarTrabajosCommand
from src.application.contenedor import Contenedor, construir_contenedor
from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.estados import Rol
from src.domain.value_objects import Usuario
from src.infrastructure.adaptadores import ZONA_DEL_TALLER, DespachadorEnMemoria, NotificacionSimulada, RelojFijo
from src.infrastructure.persistencia import repositorios_en_memoria

ASESOR = Usuario("ASE-001", "Laura Méndez", Rol.ASESOR_DE_SERVICIO)
TECNICO = Usuario("TEC-001", "Jorge Salinas", Rol.TECNICO)
COMPRAS = Usuario("COM-001", "Rosa Treviño", Rol.COMPRAS)
CAJA = Usuario("CAJ-001", "Miguel Garza", Rol.CAJA)
GERENTE = Usuario("GER-001", "Patricia Leal", Rol.GERENTE_DEL_TALLER)
CLIENTE = Usuario("CLI-001", "Ana López", Rol.CLIENTE_TITULAR)
OTRO_CLIENTE = Usuario("CLI-002", "Carlos Ramírez", Rol.CLIENTE_TITULAR)
RESPONSABLE = Usuario("RESP-001", "Daniel Ortiz", Rol.RESPONSABLE_DE_CUENTA)
RESPONSABLE_AJENO = Usuario("RESP-999", "Contacto no registrado", Rol.RESPONSABLE_DE_CUENTA)

INICIO = datetime(2026, 11, 2, 9, 0, tzinfo=ZONA_DEL_TALLER)
EVIDENCIA = "Firma digital de prueba"


@pytest.fixture
def reloj() -> RelojFijo:
    return RelojFijo(INICIO)


@pytest.fixture
def c(reloj) -> Contenedor:
    contenedor = construir_contenedor(
        repositorios_en_memoria(), reloj, NotificacionSimulada(reloj), DespachadorEnMemoria()
    )
    contenedor.repos.clientes.guardar(Cliente("CLI-001", "Ana López"))
    contenedor.repos.clientes.guardar(Cliente("CLI-002", "Carlos Ramírez"))
    contenedor.repos.clientes.guardar(
        ClienteFlotilla(
            "FLO-001", "Transportes del Norte", responsables_de_cuenta=["RESP-001"], prioridad_contractual=True
        )
    )
    contenedor.repos.clientes.guardar(
        ClienteFlotilla("FLO-002", "Logística Regia", responsables_de_cuenta=["RESP-002"])
    )
    return contenedor


def ingreso(
    c: Contenedor,
    cliente_id: str = "CLI-001",
    placa: str = "SMX-482-A",
    cargo: str = "0",
    aceptado: bool = False,
    foto: str | None = None,
):
    return c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id=cliente_id,
        placa=placa,
        marca="Nissan",
        modelo="Versa 2019",
        vin="3N1CN7AD5KL812345",
        kilometraje=68200,
        nivel_combustible="1/2",
        danos_visibles="",
        motivo_ingreso="Ruido al frenar",
        cargo_diagnostico=cargo,
        cargo_diagnostico_aceptado=aceptado,
        foto_ingreso=foto,
    )


def cotizada(
    c: Contenedor,
    cliente_id: str = "CLI-001",
    placa: str = "SMX-482-A",
    precios=("1000", "500"),
    cargo: str = "0",
    aceptado: bool = False,
):
    """Orden «En espera de autorización» con una cotización inicial de uno o más trabajos."""
    orden = ingreso(c, cliente_id, placa, cargo, aceptado)
    c.registrar_diagnostico.registrar(TECNICO, orden.id, "Balatas gastadas")
    cotizacion = c.generar_cotizacion.generar_y_enviar(
        ASESOR,
        orden.id,
        [{"descripcion": f"Trabajo {i + 1}", "cantidad": 1, "precio_unitario": p} for i, p in enumerate(precios)],
    )
    return orden.id, cotizacion


def autorizar_todo(c: Contenedor, orden_id: str, cotizacion, usuario: Usuario = CLIENTE):
    return c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(usuario, orden_id, cotizacion.id, [t.id for t in cotizacion.trabajos], [], EVIDENCIA)
    )


def en_reparacion(c: Contenedor, precios=("1000", "500"), cliente_id: str = "CLI-001", placa: str = "SMX-482-A"):
    usuario = RESPONSABLE if cliente_id == "FLO-001" else CLIENTE
    orden_id, cotizacion = cotizada(c, cliente_id, placa, precios)
    autorizar_todo(c, orden_id, cotizacion, usuario)
    return orden_id, cotizacion


def terminar_todo(c: Contenedor, orden_id: str):
    orden = c.repos.ordenes.obtener_por_id(orden_id)
    for trabajo in orden.todos_los_trabajos():
        if trabajo.estado.value == "Autorizado":
            c.ejecutar_trabajo.iniciar(TECNICO, orden_id, trabajo.id)
            c.ejecutar_trabajo.terminar(TECNICO, orden_id, trabajo.id)
    return c.repos.ordenes.obtener_por_id(orden_id)
