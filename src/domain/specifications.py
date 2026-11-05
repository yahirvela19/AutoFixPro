"""Specifications del negocio (ADR-005, Arquitectura §4).

Cada regla responde `es_satisfecha_por(candidato)` y se combina con `y()`, `o()` y `no()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from src.domain.estados import EstadoAmpliacion, EstadoOrden, EstadoTrabajo, TipoCliente
from src.domain.value_objects import Monto, Usuario

if TYPE_CHECKING:
    from src.domain.cliente import Cliente
    from src.domain.orden_de_servicio import Cotizacion, OrdenDeServicio, Trabajo

UMBRAL_AMPLIACION = Decimal("0.20")


class Specification(ABC):
    @abstractmethod
    def es_satisfecha_por(self, candidato: Any) -> bool: ...

    def y(self, otra: Specification) -> Specification:
        return _Y(self, otra)

    def o(self, otra: Specification) -> Specification:
        return _O(self, otra)

    def no(self) -> Specification:
        return _No(self)


@dataclass(frozen=True)
class _Y(Specification):
    izquierda: Specification
    derecha: Specification

    def es_satisfecha_por(self, candidato: Any) -> bool:
        return self.izquierda.es_satisfecha_por(candidato) and self.derecha.es_satisfecha_por(candidato)


@dataclass(frozen=True)
class _O(Specification):
    izquierda: Specification
    derecha: Specification

    def es_satisfecha_por(self, candidato: Any) -> bool:
        return self.izquierda.es_satisfecha_por(candidato) or self.derecha.es_satisfecha_por(candidato)


@dataclass(frozen=True)
class _No(Specification):
    interna: Specification

    def es_satisfecha_por(self, candidato: Any) -> bool:
        return not self.interna.es_satisfecha_por(candidato)


class OrdenCotizableSpecification(Specification):
    """RN-01: no hay cotización sin diagnóstico registrado."""

    def es_satisfecha_por(self, candidato: OrdenDeServicio) -> bool:
        return (
            candidato.estado == EstadoOrden.DIAGNOSTICADO
            and candidato.diagnostico is not None
            and bool(candidato.diagnostico.falla_encontrada.strip())
        )


@dataclass(frozen=True)
class CandidatoAutorizador:
    usuario: Usuario
    cliente: Cliente


class AutorizadorValidoSpecification(Specification):
    """RN-02: solo el cliente titular o un responsable de cuenta registrado (ADR-003)."""

    def es_satisfecha_por(self, candidato: CandidatoAutorizador) -> bool:
        return candidato.cliente.validar_autorizador(candidato.usuario)


@dataclass(frozen=True)
class CandidatoDecision:
    cotizacion: Cotizacion
    trabajos_autorizados: frozenset[str]
    trabajos_rechazados: frozenset[str]
    referencia_evidencia_digital: str


class DecisionCompletaSpecification(Specification):
    """RN-03/RN-04: la decisión cubre todos los trabajos pendientes, sin repetir, con evidencia."""

    def es_satisfecha_por(self, candidato: CandidatoDecision) -> bool:
        pendientes = {t.id for t in candidato.cotizacion.trabajos_pendientes()}
        autorizados, rechazados = candidato.trabajos_autorizados, candidato.trabajos_rechazados
        return (
            bool(pendientes)
            and not (autorizados & rechazados)
            and (autorizados | rechazados) == pendientes
            and bool(candidato.referencia_evidencia_digital.strip())
        )


class TrabajoEjecutableSpecification(Specification):
    """RN-03/RN-06/RN-07: autorizado, con refacciones y sin ampliación pendiente."""

    def es_satisfecha_por(self, candidato: Trabajo) -> bool:
        return (
            candidato.estado == EstadoTrabajo.AUTORIZADO
            and all(n.tiene_existencia for n in candidato.necesidades_de_refaccion)
            and not candidato.tiene_ampliacion_pendiente()
        )


@dataclass(frozen=True)
class CandidatoAmpliacion:
    total_autorizado_inicial: Monto
    ampliaciones_acumuladas: Monto


class AmpliacionSuperaUmbralSpecification(Specification):
    """RN-06: el acumulado supera el 20% del total autorizado; exactamente 20% no lo supera."""

    def es_satisfecha_por(self, candidato: CandidatoAmpliacion) -> bool:
        base = candidato.total_autorizado_inicial.valor
        if base <= 0:
            return candidato.ampliaciones_acumuladas.valor > 0
        return candidato.ampliaciones_acumuladas.valor / base > UMBRAL_AMPLIACION


@dataclass(frozen=True)
class CandidatoPlazo:
    orden: OrdenDeServicio
    ahora: datetime
    plazo: timedelta = timedelta(hours=24)


class PlazoDeRespuestaVencidoSpecification(Specification):
    """RN-09: 24 horas o más desde el envío de una solicitud aún sin respuesta."""

    def es_satisfecha_por(self, candidato: CandidatoPlazo) -> bool:
        orden = candidato.orden
        if orden.estado != EstadoOrden.EN_ESPERA_DE_AUTORIZACION:
            return False
        envios = [s.fecha_hora_envio for s in orden.solicitudes_pendientes() if s.fecha_hora_envio]
        return bool(envios) and candidato.ahora - min(envios) >= candidato.plazo


class OrdenListaParaEntregaSpecification(Specification):
    """D1: todo lo autorizado está terminado y no queda nada pendiente."""

    def es_satisfecha_por(self, candidato: OrdenDeServicio) -> bool:
        trabajos = candidato.todos_los_trabajos()
        en_curso = {
            EstadoTrabajo.PENDIENTE_DE_AUTORIZACION,
            EstadoTrabajo.AUTORIZADO,
            EstadoTrabajo.EN_ESPERA_DE_REFACCION,
            EstadoTrabajo.EN_EJECUCION,
        }
        sin_ampliaciones_pendientes = all(
            a.estado != EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION for t in trabajos for a in t.ampliaciones
        )
        return (
            any(t.estado == EstadoTrabajo.TERMINADO for t in trabajos)
            and not any(t.estado in en_curso for t in trabajos)
            and sin_ampliaciones_pendientes
        )


class TrabajoCobrableSpecification(Specification):
    """RN-11: solo se cobra lo terminado."""

    def es_satisfecha_por(self, candidato: Trabajo) -> bool:
        return candidato.estado == EstadoTrabajo.TERMINADO


@dataclass(frozen=True)
class CandidatoFacturable:
    orden: OrdenDeServicio
    cliente: Cliente
    periodo: str
    ordenes_ya_facturadas: frozenset[str]


class OrdenFacturableSpecification(Specification):
    """RN-13: orden Cerrado de la flotilla, cerrada en el periodo y no facturada antes."""

    def es_satisfecha_por(self, candidato: CandidatoFacturable) -> bool:
        orden = candidato.orden
        return (
            candidato.cliente.tipo == TipoCliente.FLOTILLA
            and orden.cliente_id == candidato.cliente.id
            and orden.estado == EstadoOrden.CERRADO
            and orden.fecha_hora_cierre is not None
            and orden.fecha_hora_cierre.strftime("%Y-%m") == candidato.periodo
            and orden.id not in candidato.ordenes_ya_facturadas
        )
