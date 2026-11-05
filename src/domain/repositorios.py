"""Interfaces de Repository definidas en el dominio (inversión de dependencias, Arquitectura C6)."""

from __future__ import annotations

from typing import Protocol, TypeVar

from src.domain.cliente import Cliente
from src.domain.disputa import Disputa
from src.domain.facturacion_consolidada import FacturacionConsolidada
from src.domain.orden_de_compra import OrdenDeCompra
from src.domain.orden_de_servicio import OrdenDeServicio
from src.domain.vehiculo import Vehiculo

A = TypeVar("A")


class IRepository(Protocol[A]):
    def obtener_por_id(self, id: str) -> A | None: ...

    def listar(self) -> list[A]: ...

    def guardar(self, agregado: A) -> None: ...


class IOrdenDeServicioRepository(IRepository[OrdenDeServicio], Protocol): ...


class IClienteRepository(IRepository[Cliente], Protocol): ...


class IVehiculoRepository(IRepository[Vehiculo], Protocol): ...


class IOrdenDeCompraRepository(IRepository[OrdenDeCompra], Protocol): ...


class IFacturacionConsolidadaRepository(IRepository[FacturacionConsolidada], Protocol): ...


class IDisputaRepository(IRepository[Disputa], Protocol): ...
