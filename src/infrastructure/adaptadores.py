"""Adaptadores de infraestructura: reloj, notificaciones simuladas y despachador de eventos."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from src.domain.eventos import EventoDeDominio
from src.infrastructure.persistencia import TABLA_NOTIFICACIONES

ZONA_DEL_TALLER = timezone(timedelta(hours=-6), "Monterrey")
DESTINATARIO_GERENTE = "GERENTE"


class RelojDelSistema:
    def ahora(self) -> datetime:
        return datetime.now(ZONA_DEL_TALLER).replace(microsecond=0)


class RelojFijo:
    """Reloj controlable para pruebas y demostraciones del plazo de 24 horas."""

    def __init__(self, momento: datetime) -> None:
        self.momento = momento

    def ahora(self) -> datetime:
        return self.momento

    def avanzar(self, **delta: float) -> None:
        self.momento = self.momento + timedelta(**delta)


class NotificacionSimulada:
    """Registra cada aviso con destinatario y fecha-hora en lugar de enviarlo (ADR-011)."""

    def __init__(self, reloj, motor: Engine | None = None) -> None:
        self.reloj = reloj
        self.motor = motor
        self._memoria: list[dict] = []

    def _registrar(self, destinatario: str, orden_id: str, mensaje: str) -> None:
        aviso = {
            "id": uuid4().hex[:12],
            "destinatario": destinatario,
            "orden_id": orden_id,
            "mensaje": mensaje,
            "fecha_hora": self.reloj.ahora(),
        }
        if self.motor is None:
            self._memoria.append(aviso)
            return
        with self.motor.begin() as conexion:
            conexion.execute(insert(TABLA_NOTIFICACIONES).values(**aviso))

    def notificar_cliente(self, cliente_id: str, orden_id: str, mensaje: str) -> None:
        self._registrar(cliente_id, orden_id, mensaje)

    def notificar_gerente(self, orden_id: str, mensaje: str) -> None:
        self._registrar(DESTINATARIO_GERENTE, orden_id, mensaje)

    def listar(self, destinatario: str | None = None, orden_id: str | None = None) -> list[dict]:
        if self.motor is None:
            avisos = list(self._memoria)
        else:
            with self.motor.connect() as conexion:
                avisos = [dict(fila._mapping) for fila in conexion.execute(select(TABLA_NOTIFICACIONES)).all()]
        avisos = [
            a
            for a in avisos
            if (destinatario is None or a["destinatario"] == destinatario)
            and (orden_id is None or a["orden_id"] == orden_id)
        ]
        for aviso in avisos:
            if aviso["fecha_hora"].tzinfo is None:
                aviso["fecha_hora"] = aviso["fecha_hora"].replace(tzinfo=ZONA_DEL_TALLER)
        return sorted(avisos, key=lambda a: a["fecha_hora"], reverse=True)


class DespachadorEnMemoria:
    """Publica los eventos en el mismo proceso después de guardar (ADR-010, simplificado)."""

    def __init__(self) -> None:
        self._suscriptores: dict[str, list[Callable[[EventoDeDominio], object]]] = defaultdict(list)
        self.publicados: list[EventoDeDominio] = []

    def suscribir(self, tipo: str, manejador: Callable[[EventoDeDominio], object]) -> None:
        self._suscriptores[tipo].append(manejador)

    def publicar(self, eventos: list[EventoDeDominio]) -> None:
        for evento in eventos:
            self.publicados.append(evento)
            for manejador in self._suscriptores.get(evento.tipo, []):
                manejador(evento)
