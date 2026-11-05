"""Commands del CQRS básico (Arquitectura §7.1)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.value_objects import Usuario


@dataclass(frozen=True)
class AutorizarTrabajosCommand:
    usuario: Usuario
    orden_id: str
    cotizacion_id: str
    trabajos_autorizados: list[str] = field(default_factory=list)
    trabajos_rechazados: list[str] = field(default_factory=list)
    referencia_evidencia_digital: str = ""


@dataclass(frozen=True)
class ReportarFallaAdicionalCommand:
    usuario: Usuario
    orden_id: str
    descripcion: str


@dataclass(frozen=True)
class CerrarOrdenDeServicioCommand:
    usuario: Usuario
    orden_id: str
    pago: str = "0"
