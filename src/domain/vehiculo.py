"""Aggregate Root Vehiculo: datos que no cambian entre ingresos."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.errores import DatosIncompletos


@dataclass
class Vehiculo:
    id: str
    cliente_id: str
    placa: str
    marca: str
    modelo: str
    vin: str

    def __post_init__(self) -> None:
        faltantes = [
            nombre
            for nombre, valor in (
                ("placa", self.placa),
                ("marca", self.marca),
                ("modelo", self.modelo),
                ("VIN", self.vin),
            )
            if not str(valor or "").strip()
        ]
        if faltantes:
            raise DatosIncompletos(f"Falta capturar: {', '.join(faltantes)}.")
        self.placa = self.placa.strip().upper()
        self.vin = self.vin.strip().upper()

    def descripcion(self) -> str:
        return f"{self.marca} {self.modelo} · {self.placa}"
