"""Políticas de autorización intercambiables (ADR-004)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.specifications import AmpliacionSuperaUmbralSpecification, CandidatoAmpliacion
from src.domain.value_objects import Monto


@dataclass(frozen=True)
class ContextoDeAutorizacion:
    es_trabajo_nuevo: bool
    total_autorizado_inicial: Monto = Monto.cero()
    ampliaciones_acumuladas: Monto = Monto.cero()


class IPoliticaDeAutorizacion(ABC):
    @abstractmethod
    def requiere_nueva_autorizacion(self, contexto: ContextoDeAutorizacion) -> bool: ...


class PoliticaAutorizacionEstandar(IPoliticaDeAutorizacion):
    """RN-05: todo trabajo nuevo (inicial o de falla adicional) requiere autorización, sin importar el monto."""

    def requiere_nueva_autorizacion(self, contexto: ContextoDeAutorizacion) -> bool:
        return contexto.es_trabajo_nuevo


class PoliticaAutorizacionAmpliacion(IPoliticaDeAutorizacion):
    """RN-06: una ampliación requiere autorización si el acumulado supera el 20%."""

    def __init__(self) -> None:
        self._umbral = AmpliacionSuperaUmbralSpecification()

    def requiere_nueva_autorizacion(self, contexto: ContextoDeAutorizacion) -> bool:
        return self._umbral.es_satisfecha_por(
            CandidatoAmpliacion(contexto.total_autorizado_inicial, contexto.ampliaciones_acumuladas)
        )
