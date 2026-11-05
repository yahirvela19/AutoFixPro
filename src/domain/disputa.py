"""Aggregate Root Disputa (RN-15, US-24)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from src.domain.errores import DatosIncompletos, DecisionYaRegistrada
from src.domain.estados import CategoriaDisputa, EstadoDisputa


@dataclass
class Disputa:
    id: str
    orden_de_servicio_id: str
    cliente_id: str
    categoria: CategoriaDisputa
    descripcion: str
    fecha_hora: datetime
    estado: EstadoDisputa = EstadoDisputa.ABIERTA
    resolucion: str = ""
    fecha_hora_resolucion: datetime | None = None

    @classmethod
    def registrar(
        cls,
        *,
        orden_de_servicio_id: str,
        cliente_id: str,
        categoria: CategoriaDisputa,
        descripcion: str,
        ahora: datetime,
    ) -> Disputa:
        if not str(descripcion or "").strip():
            raise DatosIncompletos("Describe el motivo de la disputa.")
        return cls(
            uuid4().hex[:12], orden_de_servicio_id, cliente_id, CategoriaDisputa(categoria), descripcion.strip(), ahora
        )

    def resolver(self, resolucion: str, ahora: datetime) -> None:
        if self.estado == EstadoDisputa.RESUELTA:
            raise DecisionYaRegistrada("Esta disputa ya fue resuelta.")
        if not str(resolucion or "").strip():
            raise DatosIncompletos("Escribe la resolución de la disputa.")
        self.estado = EstadoDisputa.RESUELTA
        self.resolucion = resolucion.strip()
        self.fecha_hora_resolucion = ahora
