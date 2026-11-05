"""Domain Services (Arquitectura §3.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.estados import EstadoOrden
from src.domain.orden_de_servicio import OrdenDeServicio
from src.domain.specifications import CandidatoPlazo, PlazoDeRespuestaVencidoSpecification


class ServicioDeEscalamiento:
    """RN-09: pasa a «En espera de cliente» las órdenes cuyo plazo de respuesta venció."""

    def __init__(self, plazo: timedelta = timedelta(hours=24)) -> None:
        self.plazo = plazo
        self._vencido = PlazoDeRespuestaVencidoSpecification()

    def procesar(self, ordenes: list[OrdenDeServicio], ahora: datetime) -> list[OrdenDeServicio]:
        escaladas = []
        for orden in ordenes:
            if self._vencido.es_satisfecha_por(CandidatoPlazo(orden, ahora, self.plazo)):
                orden.marcar_en_espera_de_cliente(ahora)
                escaladas.append(orden)
        return escaladas


class ServicioDePriorizacion:
    """RN-12: la cola de atención (órdenes «Recibido», aún sin diagnóstico) pone primero la prioridad contractual."""

    def ordenar(self, ordenes: list[OrdenDeServicio], clientes: dict[str, Cliente]) -> list[OrdenDeServicio]:
        def tiene_prioridad(orden: OrdenDeServicio) -> bool:
            cliente = clientes.get(orden.cliente_id)
            return isinstance(cliente, ClienteFlotilla) and cliente.prioridad_contractual

        en_cola = [o for o in ordenes if o.estado == EstadoOrden.RECIBIDO]
        return sorted(en_cola, key=lambda o: (not tiene_prioridad(o), o.fecha_hora_ingreso))
