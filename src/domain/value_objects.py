"""Value Objects del dominio: inmutables y definidos por sus valores."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.domain.errores import DatosIncompletos
from src.domain.estados import EtapaEvidencia, Rol

CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class Monto:
    """Dinero en MXN con precisión decimal (nunca float)."""

    valor: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        try:
            valor = Decimal(str(self.valor)).quantize(CENTAVOS)
        except (InvalidOperation, ValueError) as exc:
            raise DatosIncompletos("El importe no es un número válido.") from exc
        if not valor.is_finite() or valor < 0:
            raise DatosIncompletos("El importe no puede ser negativo.")
        object.__setattr__(self, "valor", valor)

    @classmethod
    def de(cls, valor: str | int | float | Decimal | Monto) -> Monto:
        if isinstance(valor, Monto):
            return valor
        try:
            return cls(Decimal(str(valor).strip() or "0"))
        except (InvalidOperation, ValueError) as exc:
            raise DatosIncompletos("El importe no es un número válido.") from exc

    @classmethod
    def cero(cls) -> Monto:
        return cls(Decimal("0"))

    def __add__(self, otro: Monto) -> Monto:
        return Monto(self.valor + otro.valor)

    def por(self, cantidad: int) -> Monto:
        return Monto(self.valor * cantidad)

    def __lt__(self, otro: Monto) -> bool:
        return self.valor < otro.valor

    def __le__(self, otro: Monto) -> bool:
        return self.valor <= otro.valor

    def __str__(self) -> str:
        return f"${self.valor:,.2f} MXN"


@dataclass(frozen=True)
class Usuario:
    """Persona identificada en el sistema con su rol del glosario (ADR-012)."""

    id: str
    nombre: str
    rol: Rol


@dataclass(frozen=True)
class InspeccionDeIngreso:
    """Captura, en cada ingreso, de kilometraje, combustible, daños visibles y motivo (glosario 30)."""

    kilometraje: int
    nivel_combustible: str
    danos_visibles: str
    motivo_ingreso: str

    def __post_init__(self) -> None:
        if self.kilometraje is None or int(self.kilometraje) < 0:
            raise DatosIncompletos("El kilometraje debe ser un número igual o mayor a cero.")
        faltantes = [
            nombre
            for nombre, valor in (
                ("nivel de combustible", self.nivel_combustible),
                ("motivo de ingreso", self.motivo_ingreso),
            )
            if not str(valor or "").strip()
        ]
        if faltantes:
            raise DatosIncompletos(f"Falta capturar: {', '.join(faltantes)}.")
        object.__setattr__(self, "kilometraje", int(self.kilometraje))
        object.__setattr__(self, "danos_visibles", str(self.danos_visibles or "Sin daños visibles").strip())


@dataclass(frozen=True)
class RegistroDeAutorizacion:
    """Constancia inmutable de una decisión de autorización digital (RN-04)."""

    autorizador_id: str
    autorizador_nombre: str
    rol: Rol
    fecha_hora: datetime
    trabajos_autorizados: tuple[str, ...] = field(default_factory=tuple)
    trabajos_rechazados: tuple[str, ...] = field(default_factory=tuple)
    referencia_evidencia_digital: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "trabajos_autorizados", tuple(self.trabajos_autorizados))
        object.__setattr__(self, "trabajos_rechazados", tuple(self.trabajos_rechazados))


@dataclass(frozen=True)
class EvidenciaFotografica:
    """Fotografía del vehículo asociada a la etapa de ingreso o de entrega (glosario 32)."""

    etapa: EtapaEvidencia
    referencia_archivo: str
    registrada_por: str
    fecha_hora: datetime

    def __post_init__(self) -> None:
        if not str(self.referencia_archivo or "").strip():
            raise DatosIncompletos("Selecciona la fotografía que quieres registrar.")


@dataclass(frozen=True)
class NecesidadDeRefaccion:
    """Pieza que requiere un trabajo autorizado e indica si tiene existencia (glosario 33)."""

    codigo_refaccion: str
    tiene_existencia: bool

    def __post_init__(self) -> None:
        if not str(self.codigo_refaccion or "").strip():
            raise DatosIncompletos("Captura el código de la refacción.")
