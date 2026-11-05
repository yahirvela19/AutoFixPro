"""Specifications, máquinas de estado y Value Objects probados de forma aislada (ADR-005, ADR-006)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.errores import DatosIncompletos, TransicionNoPermitida
from src.domain.estados import (
    TRANSICIONES_ORDEN,
    TRANSICIONES_TRABAJO,
    EstadoOrden,
    EstadoTrabajo,
    Rol,
    transicionar_orden,
    transicionar_trabajo,
)
from src.domain.politicas import ContextoDeAutorizacion, PoliticaAutorizacionAmpliacion, PoliticaAutorizacionEstandar
from src.domain.specifications import (
    AmpliacionSuperaUmbralSpecification,
    AutorizadorValidoSpecification,
    CandidatoAmpliacion,
    CandidatoAutorizador,
    Specification,
)
from src.domain.value_objects import InspeccionDeIngreso, Monto, NecesidadDeRefaccion, Usuario


class _Siempre(Specification):
    def __init__(self, valor: bool) -> None:
        self.valor = valor

    def es_satisfecha_por(self, candidato) -> bool:
        return self.valor


@pytest.mark.parametrize(("izquierda", "derecha"), [(True, True), (True, False), (False, True), (False, False)])
def test_specification_combinadores_y_o_no(izquierda, derecha):
    a, b = _Siempre(izquierda), _Siempre(derecha)
    assert a.y(b).es_satisfecha_por(None) is (izquierda and derecha)
    assert a.o(b).es_satisfecha_por(None) is (izquierda or derecha)
    assert a.no().es_satisfecha_por(None) is (not izquierda)
    assert a.y(b.no()).es_satisfecha_por(None) is (izquierda and not derecha)


@pytest.mark.parametrize(
    ("ampliacion", "requiere"),
    [
        ("1999.99", False),
        ("2000.00", False),
        ("2000.01", True),
        ("0", False),
    ],
)
def test_rn06_umbral_del_20_por_ciento(ampliacion, requiere):
    candidato = CandidatoAmpliacion(Monto.de("10000"), Monto.de(ampliacion))
    assert AmpliacionSuperaUmbralSpecification().es_satisfecha_por(candidato) is requiere
    contexto = ContextoDeAutorizacion(False, Monto.de("10000"), Monto.de(ampliacion))
    assert PoliticaAutorizacionAmpliacion().requiere_nueva_autorizacion(contexto) is requiere


def test_rn06_sin_base_autorizada_cualquier_ampliacion_requiere_autorizacion():
    spec = AmpliacionSuperaUmbralSpecification()
    assert spec.es_satisfecha_por(CandidatoAmpliacion(Monto.cero(), Monto.de("1")))
    assert not spec.es_satisfecha_por(CandidatoAmpliacion(Monto.cero(), Monto.cero()))


def test_rn05_todo_trabajo_nuevo_requiere_autorizacion():
    politica = PoliticaAutorizacionEstandar()
    assert politica.requiere_nueva_autorizacion(ContextoDeAutorizacion(es_trabajo_nuevo=True))
    assert not politica.requiere_nueva_autorizacion(ContextoDeAutorizacion(es_trabajo_nuevo=False))


@pytest.mark.parametrize(
    ("usuario", "cliente", "esperado"),
    [
        (Usuario("CLI-1", "A", Rol.CLIENTE_TITULAR), Cliente("CLI-1", "A"), True),
        (Usuario("CLI-2", "B", Rol.CLIENTE_TITULAR), Cliente("CLI-1", "A"), False),
        (Usuario("CLI-1", "A", Rol.TECNICO), Cliente("CLI-1", "A"), False),
        (
            Usuario("R-1", "R", Rol.RESPONSABLE_DE_CUENTA),
            ClienteFlotilla("F-1", "F", responsables_de_cuenta=["R-1"]),
            True,
        ),
        (
            Usuario("R-2", "R", Rol.RESPONSABLE_DE_CUENTA),
            ClienteFlotilla("F-1", "F", responsables_de_cuenta=["R-1"]),
            False,
        ),
        (Usuario("F-1", "F", Rol.CLIENTE_TITULAR), ClienteFlotilla("F-1", "F", responsables_de_cuenta=["R-1"]), False),
    ],
)
def test_rn02_autorizador_valido_polimorfico(usuario, cliente, esperado):
    assert AutorizadorValidoSpecification().es_satisfecha_por(CandidatoAutorizador(usuario, cliente)) is esperado


ORDEN_PERMITIDAS = [(o, d) for o, destinos in TRANSICIONES_ORDEN.items() for d in destinos]
ORDEN_PROHIBIDAS = [(o, d) for o in EstadoOrden for d in EstadoOrden if d not in TRANSICIONES_ORDEN[o]]


@pytest.mark.parametrize(("origen", "destino"), ORDEN_PERMITIDAS)
def test_maquina_de_estados_orden_transiciones_permitidas(origen, destino):
    assert transicionar_orden(origen, destino) == destino


@pytest.mark.parametrize(("origen", "destino"), ORDEN_PROHIBIDAS)
def test_maquina_de_estados_orden_transiciones_prohibidas(origen, destino):
    with pytest.raises(TransicionNoPermitida):
        transicionar_orden(origen, destino)


@pytest.mark.parametrize(("origen", "destino"), [(o, d) for o in EstadoTrabajo for d in EstadoTrabajo])
def test_maquina_de_estados_trabajo(origen, destino):
    if destino in TRANSICIONES_TRABAJO[origen]:
        assert transicionar_trabajo(origen, destino) == destino
    else:
        with pytest.raises(TransicionNoPermitida):
            transicionar_trabajo(origen, destino)


def test_estados_usan_el_texto_del_glosario():
    assert [e.value for e in EstadoOrden] == [
        "Recibido",
        "Diagnosticado",
        "Cotizado",
        "En espera de autorización",
        "En espera de cliente",
        "En reparación",
        "En espera de refacción",
        "Listo para entrega",
        "Cerrado",
        "Cerrada sin reparación",
    ]
    assert EstadoTrabajo.PENDIENTE_DE_AUTORIZACION.value == "Pendiente de autorización"


def test_monto_usa_decimal_y_rechaza_negativos():
    assert Monto.de("0.1") + Monto.de("0.2") == Monto(Decimal("0.30"))
    assert Monto.de(Monto.de("5")).valor == Decimal("5.00")
    assert Monto.de("10").por(3).valor == Decimal("30.00")
    assert str(Monto.de("1234.5")) == "$1,234.50 MXN"
    with pytest.raises(DatosIncompletos):
        Monto.de("-1")
    with pytest.raises(DatosIncompletos):
        Monto.de("abc")


def test_value_objects_validan_datos():
    with pytest.raises(DatosIncompletos):
        InspeccionDeIngreso(-5, "1/2", "", "Ruido")
    with pytest.raises(DatosIncompletos):
        InspeccionDeIngreso(10, "", "", "Ruido")
    assert InspeccionDeIngreso(10, "1/2", "", "Ruido").danos_visibles == "Sin daños visibles"
    with pytest.raises(DatosIncompletos):
        NecesidadDeRefaccion(" ", False)


def test_plazo_de_respuesta_configurable():
    from src.domain.servicios import ServicioDeEscalamiento

    assert ServicioDeEscalamiento(timedelta(hours=2)).plazo == timedelta(hours=2)
