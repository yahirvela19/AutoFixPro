"""Aggregate Root OrdenDeCompra: refacción sin existencia pedida al proveedor (ADR-002)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from src.domain import eventos as ev
from src.domain.errores import DecisionYaRegistrada
from src.domain.estados import EstadoOrdenDeCompra
from src.domain.eventos import EmisorDeEventos, EventoDeDominio


@dataclass
class OrdenDeCompra(EmisorDeEventos):
    id: str
    orden_de_servicio_id: str
    trabajo_id: str
    codigo_refaccion: str
    proveedor: str
    fecha_hora_solicitud: datetime
    estado: EstadoOrdenDeCompra = EstadoOrdenDeCompra.SOLICITADA
    fecha_hora_recepcion: datetime | None = None
    eventos_pendientes: list[EventoDeDominio] = field(default_factory=list)

    @classmethod
    def solicitar(
        cls, *, orden_de_servicio_id: str, trabajo_id: str, codigo_refaccion: str, proveedor: str, ahora: datetime
    ) -> OrdenDeCompra:
        return cls(uuid4().hex[:12], orden_de_servicio_id, trabajo_id, codigo_refaccion, proveedor, ahora)

    def registrar_recepcion(self, ahora: datetime) -> None:
        if self.estado == EstadoOrdenDeCompra.RECIBIDA:
            raise DecisionYaRegistrada("Esta refacción ya fue recibida.")
        self.estado = EstadoOrdenDeCompra.RECIBIDA
        self.fecha_hora_recepcion = ahora
        self._emitir(
            ev.REFACCION_RECIBIDA,
            self.id,
            ahora,
            f"Se recibió la refacción {self.codigo_refaccion}.",
            orden_de_servicio_id=self.orden_de_servicio_id,
            trabajo_id=self.trabajo_id,
            codigo_refaccion=self.codigo_refaccion,
        )
