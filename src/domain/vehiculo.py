"""Aggregate Root Vehiculo: datos que no cambian entre ingresos."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.errores import DatosIncompletos


def normalizar_placa(texto: str) -> str:
    """Mayúsculas y guiones entre letras y números: «smx482a» → «SMX-482-A».

    Los guiones que ya escribió el usuario se respetan; espacios, puntos y guiones repetidos se limpian.
    """
    grupos: list[str] = []
    for segmento in re.split(r"[\s._-]+", str(texto or "").upper()):
        grupos.extend(re.findall(r"[A-ZÑ]+|\d+", segmento))
    return "-".join(grupos)


@dataclass
class Vehiculo:
    id: str
    cliente_id: str
    placa: str
    marca: str
    modelo: str
    vin: str

    def __post_init__(self) -> None:
        self.placa = normalizar_placa(self.placa)
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
        self.vin = self.vin.strip().upper()

    def descripcion(self) -> str:
        return f"{self.marca} {self.modelo} · {self.placa}"
