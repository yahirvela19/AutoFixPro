"""Enumeraciones y máquinas de estado (ADR-006).

Los valores son el texto literal del glosario del BRD para que la API, la interfaz y los
reportes muestren exactamente lo mismo que el BRD y el BPMN.
"""

from enum import StrEnum

from src.domain.errores import TransicionNoPermitida


class EstadoOrden(StrEnum):
    RECIBIDO = "Recibido"
    DIAGNOSTICADO = "Diagnosticado"
    COTIZADO = "Cotizado"
    EN_ESPERA_DE_AUTORIZACION = "En espera de autorización"
    EN_ESPERA_DE_CLIENTE = "En espera de cliente"
    EN_REPARACION = "En reparación"
    EN_ESPERA_DE_REFACCION = "En espera de refacción"
    LISTO_PARA_ENTREGA = "Listo para entrega"
    CERRADO = "Cerrado"
    CERRADA_SIN_REPARACION = "Cerrada sin reparación"


class EstadoTrabajo(StrEnum):
    PENDIENTE_DE_AUTORIZACION = "Pendiente de autorización"
    AUTORIZADO = "Autorizado"
    RECHAZADO = "Rechazado"
    EN_ESPERA_DE_REFACCION = "En espera de refacción"
    EN_EJECUCION = "En ejecución"
    TERMINADO = "Terminado"


class EstadoAmpliacion(StrEnum):
    PENDIENTE_DE_AUTORIZACION = "Pendiente de autorización"
    AUTORIZADA = "Autorizada"
    RECHAZADA = "Rechazada"


class EstadoOrdenDeCompra(StrEnum):
    SOLICITADA = "Solicitada"
    RECIBIDA = "Recibida"


class EstadoDisputa(StrEnum):
    ABIERTA = "Abierta"
    RESUELTA = "Resuelta"


class TipoCotizacion(StrEnum):
    INICIAL = "Inicial"
    COMPLEMENTARIA = "Complementaria"


class TipoCliente(StrEnum):
    PARTICULAR = "Particular"
    FLOTILLA = "Flotilla"


class EtapaEvidencia(StrEnum):
    INGRESO = "Ingreso"
    ENTREGA = "Entrega"


class CategoriaDisputa(StrEnum):
    AUTORIZACION = "Autorización"
    COBRO = "Cobro"


class Rol(StrEnum):
    CLIENTE_TITULAR = "Cliente Titular"
    RESPONSABLE_DE_CUENTA = "Responsable de Cuenta"
    ASESOR_DE_SERVICIO = "Asesor de Servicio"
    TECNICO = "Técnico"
    COMPRAS = "Compras"
    CAJA = "Caja"
    GERENTE_DEL_TALLER = "Gerente del Taller"


_EO = EstadoOrden
_ET = EstadoTrabajo

TRANSICIONES_ORDEN: dict[EstadoOrden, frozenset[EstadoOrden]] = {
    _EO.RECIBIDO: frozenset({_EO.DIAGNOSTICADO}),
    _EO.DIAGNOSTICADO: frozenset({_EO.COTIZADO}),
    _EO.COTIZADO: frozenset({_EO.EN_ESPERA_DE_AUTORIZACION}),
    _EO.EN_ESPERA_DE_AUTORIZACION: frozenset({_EO.EN_REPARACION, _EO.EN_ESPERA_DE_CLIENTE, _EO.CERRADA_SIN_REPARACION}),
    _EO.EN_ESPERA_DE_CLIENTE: frozenset({_EO.EN_REPARACION, _EO.CERRADA_SIN_REPARACION}),
    _EO.EN_REPARACION: frozenset({_EO.EN_ESPERA_DE_REFACCION, _EO.EN_ESPERA_DE_AUTORIZACION, _EO.LISTO_PARA_ENTREGA}),
    _EO.EN_ESPERA_DE_REFACCION: frozenset({_EO.EN_REPARACION}),
    _EO.LISTO_PARA_ENTREGA: frozenset({_EO.CERRADO}),
    _EO.CERRADO: frozenset(),
    _EO.CERRADA_SIN_REPARACION: frozenset(),
}

TRANSICIONES_TRABAJO: dict[EstadoTrabajo, frozenset[EstadoTrabajo]] = {
    _ET.PENDIENTE_DE_AUTORIZACION: frozenset({_ET.AUTORIZADO, _ET.RECHAZADO}),
    _ET.AUTORIZADO: frozenset({_ET.EN_ESPERA_DE_REFACCION, _ET.EN_EJECUCION}),
    _ET.EN_ESPERA_DE_REFACCION: frozenset({_ET.AUTORIZADO}),
    _ET.EN_EJECUCION: frozenset({_ET.TERMINADO}),
    _ET.RECHAZADO: frozenset(),
    _ET.TERMINADO: frozenset(),
}

ESTADOS_TERMINALES = frozenset({_EO.CERRADO, _EO.CERRADA_SIN_REPARACION})


def transicionar_orden(origen: EstadoOrden, destino: EstadoOrden) -> EstadoOrden:
    """Devuelve el destino si la transición está permitida; si no, lanza TransicionNoPermitida."""
    if destino not in TRANSICIONES_ORDEN[origen]:
        raise TransicionNoPermitida(f"Una orden en «{origen}» no puede pasar a «{destino}».")
    return destino


def transicionar_trabajo(origen: EstadoTrabajo, destino: EstadoTrabajo) -> EstadoTrabajo:
    if destino not in TRANSICIONES_TRABAJO[origen]:
        raise TransicionNoPermitida(f"Un trabajo en «{origen}» no puede pasar a «{destino}».")
    return destino
