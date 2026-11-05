"""Esquemas de entrada de la API REST (Pydantic)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from src.domain.estados import CategoriaDisputa, EtapaEvidencia


class IngresoEntrada(BaseModel):
    cliente_id: str = Field(examples=["CLI-001"])
    placa: str = Field(examples=["SMX-482-A"])
    marca: str = Field(examples=["Nissan"])
    modelo: str = Field(examples=["Versa 2019"])
    vin: str = Field(examples=["3N1CN7AD5KL812345"])
    kilometraje: int = Field(ge=0, examples=[68200])
    nivel_combustible: str = Field(examples=["1/2"])
    danos_visibles: str = Field(default="", examples=["Rayón en defensa trasera"])
    motivo_ingreso: str = Field(examples=["Ruido al frenar"])
    cargo_diagnostico: str = Field(default="0", examples=["350"])
    cargo_diagnostico_aceptado: bool = False
    foto_ingreso: str | None = Field(default=None, examples=["versa_ingreso.jpg"])


class DiagnosticoEntrada(BaseModel):
    falla_encontrada: str = Field(examples=["Balatas delanteras gastadas"])


class LineaDeTrabajo(BaseModel):
    descripcion: str = Field(examples=["Cambio de balatas delanteras"])
    cantidad: int = Field(default=1, examples=[1])
    precio_unitario: str = Field(examples=["1200.00"])


class CotizacionEntrada(BaseModel):
    trabajos: list[LineaDeTrabajo]


class AutorizacionDigitalEntrada(BaseModel):
    trabajos_autorizados: list[str] = Field(default_factory=list)
    trabajos_rechazados: list[str] = Field(default_factory=list)
    referencia_evidencia_digital: str = Field(examples=["Firma digital del cliente"])


class FallaAdicionalEntrada(BaseModel):
    descripcion: str = Field(examples=["Fuga en manguera de radiador"])


class AmpliacionEntrada(BaseModel):
    monto: str = Field(examples=["450.00"])
    motivo: str = Field(examples=["Se requiere un segundo juego de tornillería"])


class DecisionDeAmpliacionEntrada(BaseModel):
    autoriza: bool
    referencia_evidencia_digital: str


class NecesidadDeRefaccionEntrada(BaseModel):
    codigo_refaccion: str = Field(examples=["BAL-4410"])
    proveedor: str = Field(examples=["Refacciones del Norte"])


class NuevaFechaEntrada(BaseModel):
    nueva_fecha: date
    motivo: str = Field(examples=["El proveedor entrega la refacción el lunes"])


class EvidenciaEntrada(BaseModel):
    etapa: EtapaEvidencia
    referencia_archivo: str = Field(examples=["entrega_frente.jpg"])


class CierreDeCajaEntrada(BaseModel):
    pago: str = Field(default="0", examples=["1550.00"])


class FacturacionEntrada(BaseModel):
    cliente_id: str = Field(examples=["FLO-001"])
    periodo: str = Field(examples=["2026-11"])


class DisputaEntrada(BaseModel):
    orden_id: str
    categoria: CategoriaDisputa
    descripcion: str


class ResolucionEntrada(BaseModel):
    resolucion: str
