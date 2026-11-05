"""Datos ficticios de demostración: clientes y órdenes en distintos estados."""

from __future__ import annotations

from src.application.comandos import AutorizarTrabajosCommand
from src.application.contenedor import Contenedor
from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.estados import Rol
from src.domain.value_objects import Usuario

ASESOR = Usuario("ASE-001", "Laura Méndez", Rol.ASESOR_DE_SERVICIO)
TECNICO = Usuario("TEC-001", "Jorge Salinas", Rol.TECNICO)
RESPONSABLE_FLOTILLA = Usuario("RESP-001", "Daniel Ortiz", Rol.RESPONSABLE_DE_CUENTA)

CLIENTES = [
    Cliente("CLI-001", "Ana López", "81 1234 5678"),
    Cliente("CLI-002", "Carlos Ramírez", "81 8765 4321"),
    ClienteFlotilla(
        "FLO-001",
        "Transportes del Norte",
        "81 5555 0101",
        responsables_de_cuenta=["RESP-001"],
        prioridad_contractual=True,
    ),
    ClienteFlotilla(
        "FLO-002", "Logística Regia", "81 5555 0202", responsables_de_cuenta=["RESP-002"], prioridad_contractual=False
    ),
]


def cargar_datos_demo(c: Contenedor) -> bool:
    """Carga los datos solo si la base está vacía. Devuelve True si cargó algo."""
    if c.repos.clientes.listar():
        return False
    for cliente in CLIENTES:
        c.repos.clientes.guardar(cliente)

    c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id="CLI-001",
        placa="SMX-482-A",
        marca="Nissan",
        modelo="Versa 2019",
        vin="3N1CN7AD5KL812345",
        kilometraje=68200,
        nivel_combustible="1/2",
        danos_visibles="Rayón en defensa trasera",
        motivo_ingreso="Ruido al frenar",
        cargo_diagnostico="350",
        cargo_diagnostico_aceptado=True,
        foto_ingreso="versa_ingreso.jpg",
    )
    c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id="CLI-002",
        placa="RTA-913-B",
        marca="Chevrolet",
        modelo="Aveo 2021",
        vin="3G1TA5AF9ML123456",
        kilometraje=35400,
        nivel_combustible="3/4",
        danos_visibles="",
        motivo_ingreso="Servicio de afinación",
        cargo_diagnostico="0",
        cargo_diagnostico_aceptado=False,
    )
    flotilla = c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id="FLO-001",
        placa="NLE-207-C",
        marca="Ford",
        modelo="Transit 2022",
        vin="1FTBR1C82NKA12345",
        kilometraje=121500,
        nivel_combustible="1/4",
        danos_visibles="Golpe leve en puerta lateral",
        motivo_ingreso="Testigo de motor encendido",
        cargo_diagnostico="450",
        cargo_diagnostico_aceptado=True,
        foto_ingreso="transit_ingreso.jpg",
    )
    c.registrar_diagnostico.registrar(TECNICO, flotilla.id, "Sensor de oxígeno dañado y balatas delanteras gastadas.")
    cotizacion = c.generar_cotizacion.generar_y_enviar(
        ASESOR,
        flotilla.id,
        [
            {"descripcion": "Cambio de sensor de oxígeno", "cantidad": 1, "precio_unitario": "1850"},
            {"descripcion": "Cambio de balatas delanteras", "cantidad": 1, "precio_unitario": "1200"},
        ],
    )
    en_reparacion = c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id="FLO-001",
        placa="NLE-118-D",
        marca="Toyota",
        modelo="Hilux 2020",
        vin="MR0EX3DD4L0123456",
        kilometraje=98700,
        nivel_combustible="1/2",
        danos_visibles="",
        motivo_ingreso="Mantenimiento preventivo",
        cargo_diagnostico="0",
        cargo_diagnostico_aceptado=False,
    )
    c.registrar_diagnostico.registrar(TECNICO, en_reparacion.id, "Requiere cambio de aceite y filtro de aire.")
    otra = c.generar_cotizacion.generar_y_enviar(
        ASESOR,
        en_reparacion.id,
        [
            {"descripcion": "Cambio de aceite sintético", "cantidad": 1, "precio_unitario": "980"},
            {"descripcion": "Cambio de filtro de aire", "cantidad": 1, "precio_unitario": "420"},
        ],
    )
    c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(
            RESPONSABLE_FLOTILLA,
            en_reparacion.id,
            otra.id,
            trabajos_autorizados=[t.id for t in otra.trabajos],
            referencia_evidencia_digital="Autorización digital de Daniel Ortiz (datos de demostración)",
        )
    )
    del cotizacion
    return True
