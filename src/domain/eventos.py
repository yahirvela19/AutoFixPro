"""Domain Events: hechos del negocio ya ocurridos (Arquitectura §3.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

VEHICULO_RECIBIDO = "VehiculoRecibido"
DIAGNOSTICO_REGISTRADO = "DiagnosticoRegistrado"
COTIZACION_GENERADA = "CotizacionGenerada"
TRABAJO_AUTORIZADO = "TrabajoAutorizado"
TRABAJO_RECHAZADO = "TrabajoRechazado"
RECHAZO_TOTAL_REGISTRADO = "RechazoTotalRegistrado"
FALLA_ADICIONAL_REPORTADA = "FallaAdicionalReportada"
AMPLIACION_SOLICITADA = "AmpliacionSolicitada"
AMPLIACION_DECIDIDA = "AmpliacionDecidida"
REFACCION_SIN_EXISTENCIA_DETECTADA = "RefaccionSinExistenciaDetectada"
REFACCION_RECIBIDA = "RefaccionRecibida"
REPARACION_REANUDADA = "ReparacionReanudada"
NUEVA_FECHA_ENTREGA_NOTIFICADA = "NuevaFechaEntregaNotificada"
PLAZO_DE_RESPUESTA_VENCIDO = "PlazoDeRespuestaVencido"
TRABAJO_INICIADO = "TrabajoIniciado"
TRABAJO_TERMINADO = "TrabajoTerminado"
EVIDENCIA_FOTOGRAFICA_REGISTRADA = "EvidenciaFotograficaRegistrada"
ORDEN_LISTA_PARA_ENTREGA = "OrdenListaParaEntrega"
ORDEN_DE_SERVICIO_CERRADA = "OrdenDeServicioCerrada"
ORDEN_CERRADA_SIN_REPARACION = "OrdenCerradaSinReparacion"
DISPUTA_REGISTRADA = "DisputaRegistrada"
DISPUTA_RESUELTA = "DisputaResuelta"
FACTURACION_CONSOLIDADA_GENERADA = "FacturacionConsolidadaGenerada"


@dataclass(frozen=True)
class EventoDeDominio:
    tipo: str
    agregado_id: str
    fecha_hora: datetime
    descripcion: str
    datos: dict[str, Any] = field(default_factory=dict)


class EmisorDeEventos:
    """Mezcla para Aggregate Roots: acumula eventos y conserva el historial de la orden."""

    eventos_pendientes: list[EventoDeDominio]

    def _emitir(self, tipo: str, agregado_id: str, fecha_hora: datetime, descripcion: str, **datos: Any) -> None:
        evento = EventoDeDominio(tipo, agregado_id, fecha_hora, descripcion, datos)
        self.eventos_pendientes.append(evento)
        historial = getattr(self, "historial", None)
        if historial is not None:
            historial.append(evento)

    def extraer_eventos(self) -> list[EventoDeDominio]:
        eventos, self.eventos_pendientes = self.eventos_pendientes, []
        return eventos
