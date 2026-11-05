"""Persistencia con SQLAlchemy: una tabla por Aggregate Root (ADR-009, simplificado)."""

from __future__ import annotations

import copy
from typing import Any, Generic, TypeVar

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, delete, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from src.application.puertos import Repositorios
from src.infrastructure.serializacion import a_json, desde_json

A = TypeVar("A")

metadata = MetaData()

NOMBRES_DE_TABLA = (
    "ordenes_de_servicio",
    "clientes",
    "vehiculos",
    "ordenes_de_compra",
    "facturaciones_consolidadas",
    "disputas",
)
TABLAS = {
    nombre: Table(nombre, metadata, Column("id", String(40), primary_key=True), Column("datos", Text, nullable=False))
    for nombre in NOMBRES_DE_TABLA
}
TABLA_NOTIFICACIONES = Table(
    "notificaciones",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("destinatario", String(60), nullable=False),
    Column("orden_id", String(40), nullable=False),
    Column("mensaje", Text, nullable=False),
    Column("fecha_hora", DateTime(timezone=True), nullable=False),
)


def crear_motor(url: str) -> Engine:
    if url.startswith("sqlite"):
        argumentos: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            argumentos["poolclass"] = StaticPool
        motor = create_engine(url, **argumentos)
    else:
        motor = create_engine(url, pool_pre_ping=True)
    metadata.create_all(motor)
    return motor


class RepositorioSql(Generic[A]):
    """Guarda cada Aggregate como un documento JSON; cada `guardar` es una transacción."""

    def __init__(self, motor: Engine, tabla: str) -> None:
        self.motor = motor
        self.tabla = TABLAS[tabla]

    def obtener_por_id(self, id: str) -> A | None:
        with self.motor.connect() as conexion:
            fila = conexion.execute(select(self.tabla.c.datos).where(self.tabla.c.id == id)).first()
        return None if fila is None else desde_json(fila[0])

    def listar(self) -> list[A]:
        with self.motor.connect() as conexion:
            filas = conexion.execute(select(self.tabla.c.datos)).all()
        return [desde_json(fila[0]) for fila in filas]

    def guardar(self, agregado: A) -> None:
        identificador = agregado.id  # type: ignore[attr-defined]
        with self.motor.begin() as conexion:
            conexion.execute(delete(self.tabla).where(self.tabla.c.id == identificador))
            conexion.execute(insert(self.tabla).values(id=identificador, datos=a_json(agregado)))


class RepositorioEnMemoria(Generic[A]):
    """Repositorio de pruebas que cumple el mismo contrato (Liskov) y copia los objetos como lo haría la BD."""

    def __init__(self) -> None:
        self._datos: dict[str, A] = {}

    def obtener_por_id(self, id: str) -> A | None:
        agregado = self._datos.get(id)
        return copy.deepcopy(agregado) if agregado is not None else None

    def listar(self) -> list[A]:
        return [copy.deepcopy(a) for a in self._datos.values()]

    def guardar(self, agregado: A) -> None:
        self._datos[agregado.id] = copy.deepcopy(agregado)  # type: ignore[attr-defined]


def repositorios_sql(motor: Engine) -> Repositorios:
    return Repositorios(
        ordenes=RepositorioSql(motor, "ordenes_de_servicio"),
        clientes=RepositorioSql(motor, "clientes"),
        vehiculos=RepositorioSql(motor, "vehiculos"),
        ordenes_de_compra=RepositorioSql(motor, "ordenes_de_compra"),
        facturaciones=RepositorioSql(motor, "facturaciones_consolidadas"),
        disputas=RepositorioSql(motor, "disputas"),
    )


def repositorios_en_memoria() -> Repositorios:
    return Repositorios(*(RepositorioEnMemoria() for _ in NOMBRES_DE_TABLA))
