"""Puertos de la capa de aplicación (interfaces que implementa la infraestructura)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.eventos import EventoDeDominio
from src.domain.repositorios import (
    IClienteRepository,
    IDisputaRepository,
    IFacturacionConsolidadaRepository,
    IOrdenDeCompraRepository,
    IOrdenDeServicioRepository,
    IVehiculoRepository,
)


class IReloj(Protocol):
    def ahora(self) -> datetime: ...


class INotificacionCliente(Protocol):
    def notificar_cliente(self, cliente_id: str, orden_id: str, mensaje: str) -> None: ...


class INotificacionGerente(Protocol):
    def notificar_gerente(self, orden_id: str, mensaje: str) -> None: ...


class IDespachadorDeEventos(Protocol):
    def publicar(self, eventos: list[EventoDeDominio]) -> None: ...


@dataclass
class Repositorios:
    ordenes: IOrdenDeServicioRepository
    clientes: IClienteRepository
    vehiculos: IVehiculoRepository
    ordenes_de_compra: IOrdenDeCompraRepository
    facturaciones: IFacturacionConsolidadaRepository
    disputas: IDisputaRepository
