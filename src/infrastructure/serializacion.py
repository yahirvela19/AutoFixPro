"""Convierte Aggregates a JSON y de regreso, conservando tipos del dominio (ADR-009)."""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from src.domain import estados
from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.disputa import Disputa
from src.domain.eventos import EventoDeDominio
from src.domain.facturacion_consolidada import FacturacionConsolidada
from src.domain.orden_de_compra import OrdenDeCompra
from src.domain.orden_de_servicio import Ampliacion, Cotizacion, Diagnostico, OrdenDeServicio, Trabajo
from src.domain.value_objects import (
    EvidenciaFotografica,
    InspeccionDeIngreso,
    Monto,
    NecesidadDeRefaccion,
    RegistroDeAutorizacion,
)
from src.domain.vehiculo import Vehiculo

_CLASES = {
    c.__name__: c
    for c in (
        OrdenDeServicio,
        Diagnostico,
        Cotizacion,
        Trabajo,
        Ampliacion,
        RegistroDeAutorizacion,
        EvidenciaFotografica,
        NecesidadDeRefaccion,
        InspeccionDeIngreso,
        Monto,
        EventoDeDominio,
        Cliente,
        ClienteFlotilla,
        Vehiculo,
        OrdenDeCompra,
        FacturacionConsolidada,
        Disputa,
    )
}
_ENUMS = {
    e.__name__: e
    for e in (
        estados.EstadoOrden,
        estados.EstadoTrabajo,
        estados.EstadoAmpliacion,
        estados.EstadoOrdenDeCompra,
        estados.EstadoDisputa,
        estados.TipoCotizacion,
        estados.TipoCliente,
        estados.EtapaEvidencia,
        estados.CategoriaDisputa,
        estados.Rol,
    )
}
_NO_PERSISTIR = {"eventos_pendientes"}


def a_primitivo(valor: Any) -> Any:
    if isinstance(valor, Enum):
        return {"__enum__": type(valor).__name__, "valor": valor.value}
    if isinstance(valor, Decimal):
        return {"__decimal__": str(valor)}
    if isinstance(valor, datetime):
        return {"__fecha_hora__": valor.isoformat()}
    if isinstance(valor, date):
        return {"__fecha__": valor.isoformat()}
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        datos = {
            f.name: a_primitivo(getattr(valor, f.name))
            for f in dataclasses.fields(valor)
            if f.name not in _NO_PERSISTIR
        }
        datos["__clase__"] = type(valor).__name__
        return datos
    if isinstance(valor, (list, tuple)):
        return [a_primitivo(v) for v in valor]
    if isinstance(valor, dict):
        return {k: a_primitivo(v) for k, v in valor.items()}
    return valor


def desde_primitivo(valor: Any) -> Any:
    if isinstance(valor, list):
        return [desde_primitivo(v) for v in valor]
    if not isinstance(valor, dict):
        return valor
    if "__enum__" in valor:
        return _ENUMS[valor["__enum__"]](valor["valor"])
    if "__decimal__" in valor:
        return Decimal(valor["__decimal__"])
    if "__fecha_hora__" in valor:
        return datetime.fromisoformat(valor["__fecha_hora__"])
    if "__fecha__" in valor:
        return date.fromisoformat(valor["__fecha__"])
    if "__clase__" in valor:
        clase = _CLASES[valor["__clase__"]]
        argumentos = {k: desde_primitivo(v) for k, v in valor.items() if k != "__clase__"}
        return clase(**argumentos)
    return {k: desde_primitivo(v) for k, v in valor.items()}


def a_json(agregado: Any) -> str:
    return json.dumps(a_primitivo(agregado), ensure_ascii=False)


def desde_json(texto: str) -> Any:
    return desde_primitivo(json.loads(texto))
