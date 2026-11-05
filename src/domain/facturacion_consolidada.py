"""Aggregate Root FacturacionConsolidada (RN-13)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from src.domain.cliente import Cliente
from src.domain.errores import DatosIncompletos
from src.domain.orden_de_servicio import OrdenDeServicio
from src.domain.specifications import CandidatoFacturable, OrdenFacturableSpecification
from src.domain.value_objects import Monto


@dataclass
class FacturacionConsolidada:
    id: str
    cliente_id: str
    periodo: str
    ordenes_de_servicio: list[str]
    total: Monto
    fecha_hora: datetime
    detalle: list[dict] = field(default_factory=list)

    @classmethod
    def generar(
        cls,
        *,
        cliente: Cliente,
        periodo: str,
        ordenes: list[OrdenDeServicio],
        ordenes_ya_facturadas: frozenset[str],
        ahora: datetime,
    ) -> FacturacionConsolidada:
        try:
            datetime.strptime(periodo, "%Y-%m")
        except ValueError as exc:
            raise DatosIncompletos("El periodo debe tener el formato año-mes, por ejemplo 2026-11.") from exc
        especificacion = OrdenFacturableSpecification()
        incluidas = [
            o
            for o in ordenes
            if especificacion.es_satisfecha_por(CandidatoFacturable(o, cliente, periodo, ordenes_ya_facturadas))
        ]
        if not incluidas:
            raise DatosIncompletos("No hay órdenes cerradas sin facturar de esta flotilla en ese periodo.")
        total = Monto.cero()
        detalle = []
        for orden in incluidas:
            total = total + orden.total_cobrable()
            detalle.append({"folio": orden.folio, "importe": str(orden.total_cobrable().valor)})
        return cls(uuid4().hex[:12], cliente.id, periodo, [o.id for o in incluidas], total, ahora, detalle)
