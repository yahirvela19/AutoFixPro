"""Paquete de pruebas del docente: 120 casos y 20 transiciones ejecutados con el dominio del BRD."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.domain.value_objects import Monto
from src.infrastructure.paquete_docente import (
    Operacion,
    autorizar,
    beneficio_de_referencia,
    completar,
    cotizar,
    ejecutar_transicion,
    escribir_resultados,
    evaluar_caso,
    leer_paquete,
    nuevo_contenedor,
    puede_procesarse,
    registrar,
)

CARPETA = Path(__file__).resolve().parents[2] / "datos" / "paquete_docente"
PAQUETE = leer_paquete(CARPETA)


def test_paquete_se_importa_con_claves_foraneas():
    assert len(PAQUETE.actores) == 40 and len(PAQUETE.recursos) == 20 and len(PAQUETE.operaciones) == 60
    assert len(PAQUETE.casos) == 120 and len(PAQUETE.transiciones) == 20
    assert sum(len(o.lineas) for o in PAQUETE.operaciones.values()) == 117


def test_total_con_decimal():
    # AUT-O001: AUT-P009 927.00 × 3 + AUT-P014 1282.00 × 4
    assert PAQUETE.operaciones["AUT-O001"].total == Monto.de("7909.00")
    assert PAQUETE.operaciones["AUT-O013"].total == Monto.cero()


@pytest.mark.parametrize("caso", PAQUETE.casos, ids=lambda c: c["caso_id"])
def test_casos_de_prueba_del_paquete(caso):
    resultado, evidencia = evaluar_caso(PAQUETE, caso)
    operacion: Operacion = PAQUETE.operaciones[caso["operacion_id"]]
    if caso["tipo_prueba"] == "validar_operacion":
        esperado = operacion.actor.activo and bool(operacion.lineas) and operacion.autorizado
        assert resultado == ("PASA" if esperado else "NO PASA")
    else:
        esperado = operacion.actor.preferente and operacion.total.valor >= 1500 and not operacion.promocion_activa
        assert resultado == ("APLICA" if esperado else "NO APLICA")
    assert "total" in evidencia


@pytest.mark.parametrize("caso", PAQUETE.transiciones, ids=lambda c: c["caso_id"])
def test_transiciones_del_paquete(caso):
    r = ejecutar_transicion(PAQUETE, caso)
    operacion = PAQUETE.operaciones[caso["operacion_id"]]
    accion = caso["accion_sugerida"]
    if accion in ("saltar_estado", "cancelar"):
        assert not r.aceptada and "TransicionNoPermitida" in r.evento_o_excepcion
        assert r.estado_final == "Recibido"
    elif not operacion.lineas:
        assert not r.aceptada and "al menos un trabajo" in r.evento_o_excepcion
    elif not operacion.autorizado:
        assert not r.aceptada and r.estado_final == "En espera de autorización"
    elif accion == "repetir_aprobacion":
        assert not r.aceptada and "DecisionYaRegistrada" in r.evento_o_excepcion
    elif accion == "aprobar":
        assert r.aceptada and r.equivalente_paquete == "EN_REPARACION"
    elif accion == "completar":
        assert r.aceptada and r.equivalente_paquete == "ENTREGADA"


def test_recurso_no_habilitado_deja_la_orden_en_espera_de_refaccion():
    operacion = PAQUETE.operaciones["AUT-O005"]  # incluye AUT-P011, no habilitado en el catálogo
    assert any(not r.habilitado for r, _ in operacion.lineas)
    c = nuevo_contenedor(PAQUETE)
    orden = registrar(c, operacion)
    cotizacion = cotizar(c, orden.id, operacion)
    autorizar(c, orden.id, cotizacion, operacion)
    completar(c, orden.id, operacion)
    assert c.repos.ordenes.obtener_por_id(orden.id).estado.value == "En espera de refacción"
    assert len(c.repos.ordenes_de_compra.listar()) == 1


def test_composicion_de_specifications_del_paquete():
    preferente_con_promocion = PAQUETE.operaciones["AUT-O009"]  # AUT-C030 preferente, promoción activa
    assert preferente_con_promocion.actor.preferente and preferente_con_promocion.promocion_activa
    assert not beneficio_de_referencia().es_satisfecha_por(preferente_con_promocion)
    assert puede_procesarse().no().es_satisfecha_por(PAQUETE.operaciones["AUT-O008"])  # sin autorización


def test_resultados_se_escriben_en_csv(tmp_path):
    casos, transiciones = escribir_resultados(PAQUETE, tmp_path)
    with open(casos, encoding="utf-8-sig") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 120 and all(f["resultado_alumno"] != "PENDIENTE" for f in filas)
    with open(transiciones, encoding="utf-8-sig") as archivo:
        assert len(list(csv.DictReader(archivo))) == 20
