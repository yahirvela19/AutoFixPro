"""Adaptador del paquete de pruebas del docente (datos/paquete_docente/*.csv).

Traduce el modelo propuesto por el paquete (operación, recurso, RECIBIDA…ENTREGADA) al dominio del BRD
(Orden de Servicio, Trabajo, estados del glosario) y ejecuta sus casos con los servicios reales.

Las reglas del paquete que NO están en el BRD (actor activo, cliente preferente, promoción) se evalúan aquí
con Specifications propias del paquete; no forman parte del dominio de AutoFix Pro.
Ver docs/testing/Diferencias_paquete_docente.md.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.application.comandos import AutorizarTrabajosCommand, CerrarOrdenDeServicioCommand
from src.application.contenedor import Contenedor, construir_contenedor
from src.domain.cliente import Cliente
from src.domain.errores import ErrorDeDominio
from src.domain.estados import EstadoOrden, EstadoTrabajo, Rol, transicionar_orden
from src.domain.specifications import Specification
from src.domain.value_objects import Monto, Usuario
from src.infrastructure.adaptadores import DespachadorEnMemoria, NotificacionSimulada, RelojDelSistema
from src.infrastructure.persistencia import repositorios_en_memoria

ASESOR = Usuario("ASE-PIA", "Asesor del paquete", Rol.ASESOR_DE_SERVICIO)
TECNICO = Usuario("TEC-PIA", "Técnico del paquete", Rol.TECNICO)
COMPRAS = Usuario("COM-PIA", "Compras del paquete", Rol.COMPRAS)
CAJA = Usuario("CAJ-PIA", "Caja del paquete", Rol.CAJA)

EQUIVALENCIA_DE_ESTADOS = {
    EstadoOrden.RECIBIDO: "RECIBIDA",
    EstadoOrden.DIAGNOSTICADO: "DIAGNOSTICADA",
    EstadoOrden.EN_REPARACION: "EN_REPARACION",
    EstadoOrden.CERRADO: "ENTREGADA",
    EstadoOrden.CERRADA_SIN_REPARACION: "CANCELADA",
}
UMBRAL_BENEFICIO = Monto.de("1500")


# ------------------------------------------------------------------ lectura
def _leer(carpeta: Path, nombre: str) -> list[dict]:
    with open(carpeta / nombre, encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


@dataclass(frozen=True)
class Recurso:
    id: str
    descripcion: str
    precio: Monto
    existencia: int
    habilitado: bool


@dataclass(frozen=True)
class Actor:
    id: str
    nombre: str
    preferente: bool
    activo: bool


@dataclass
class Operacion:
    id: str
    actor: Actor
    autorizado: bool
    promocion_activa: bool
    lineas: list[tuple[Recurso, int]] = field(default_factory=list)

    @property
    def total(self) -> Monto:
        total = Monto.cero()
        for recurso, cantidad in self.lineas:
            total = total + recurso.precio.por(cantidad)
        return total


@dataclass
class PaqueteDocente:
    actores: dict[str, Actor]
    recursos: dict[str, Recurso]
    operaciones: dict[str, Operacion]
    casos: list[dict]
    transiciones: list[dict]


def leer_paquete(carpeta: Path) -> PaqueteDocente:
    actores = {
        a["actor_id"]: Actor(a["actor_id"], a["nombre"], a["es_preferente"] == "1", a["activo"] == "1")
        for a in _leer(carpeta, "actores.csv")
    }
    recursos = {
        r["recurso_id"]: Recurso(
            r["recurso_id"],
            r["descripcion"],
            Monto.de(r["precio_mxn"]),
            int(r["capacidad_o_stock"]),
            r["habilitado"] == "1",
        )
        for r in _leer(carpeta, "catalogo.csv")
    }
    operaciones = {
        o["operacion_id"]: Operacion(
            o["operacion_id"], actores[o["actor_id"]], o["autorizado"] == "1", o["promocion_activa"] == "1"
        )
        for o in _leer(carpeta, "operaciones.csv")
    }
    for linea in _leer(carpeta, "detalle_operaciones.csv"):
        operaciones[linea["operacion_id"]].lineas.append((recursos[linea["recurso_id"]], int(linea["cantidad"])))
    return PaqueteDocente(
        actores, recursos, operaciones, _leer(carpeta, "casos_prueba.csv"), _leer(carpeta, "transiciones_prueba.csv")
    )


# -------------------------------------------- Specifications del paquete docente
class ActorActivoSpecification(Specification):
    """Regla del paquete (sin equivalente en el BRD): el actor está activo."""

    def es_satisfecha_por(self, candidato: Operacion) -> bool:
        return candidato.actor.activo


class DetalleNoVacioSpecification(Specification):
    """Equivale a US-04: la cotización debe incluir al menos un trabajo."""

    def es_satisfecha_por(self, candidato: Operacion) -> bool:
        return bool(candidato.lineas)


class AutorizacionRegistradaSpecification(Specification):
    """Equivale a RN-03: solo lo autorizado se procesa."""

    def es_satisfecha_por(self, candidato: Operacion) -> bool:
        return candidato.autorizado


class ClientePreferenteSpecification(Specification):
    """Regla del paquete (sin equivalente en el BRD)."""

    def es_satisfecha_por(self, candidato: Operacion) -> bool:
        return candidato.actor.preferente


class TotalMinimoSpecification(Specification):
    def __init__(self, minimo: Monto = UMBRAL_BENEFICIO) -> None:
        self.minimo = minimo

    def es_satisfecha_por(self, candidato: Operacion) -> bool:
        return self.minimo <= candidato.total


class PromocionActivaSpecification(Specification):
    def es_satisfecha_por(self, candidato: Operacion) -> bool:
        return candidato.promocion_activa


def puede_procesarse() -> Specification:
    """actor activo AND detalle no vacío AND autorización."""
    return ActorActivoSpecification().y(DetalleNoVacioSpecification()).y(AutorizacionRegistradaSpecification())


def beneficio_de_referencia() -> Specification:
    """cliente preferente AND total >= 1500 MXN AND NOT promoción activa."""
    return ClientePreferenteSpecification().y(TotalMinimoSpecification()).y(PromocionActivaSpecification().no())


# --------------------------------------------- ejecución con el dominio del BRD
def nuevo_contenedor(paquete: PaqueteDocente) -> Contenedor:
    reloj = RelojDelSistema()
    c = construir_contenedor(repositorios_en_memoria(), reloj, NotificacionSimulada(reloj), DespachadorEnMemoria())
    for actor in paquete.actores.values():
        c.repos.clientes.guardar(Cliente(actor.id, actor.nombre))
    return c


def _titular(operacion: Operacion) -> Usuario:
    return Usuario(operacion.actor.id, operacion.actor.nombre, Rol.CLIENTE_TITULAR)


def registrar(c: Contenedor, operacion: Operacion):
    """RECIBIDA del paquete → registro de ingreso (US-01), con vehículo ficticio derivado de la operación."""
    numero = operacion.id.split("-")[-1]
    return c.registrar_ingreso.registrar(
        ASESOR,
        cliente_id=operacion.actor.id,
        placa=f"PIA-{numero}",
        marca="Vehículo",
        modelo=f"del paquete {numero}",
        vin=f"PIA{numero}",
        kilometraje=0,
        nivel_combustible="1/2",
        danos_visibles="",
        motivo_ingreso=f"Operación {operacion.id} del paquete docente",
    )


def cotizar(c: Contenedor, orden_id: str, operacion: Operacion):
    c.registrar_diagnostico.registrar(TECNICO, orden_id, f"Diagnóstico de la operación {operacion.id}")
    lineas = [
        {"descripcion": f"{r.descripcion} ({r.id})", "cantidad": cantidad, "precio_unitario": r.precio.valor}
        for r, cantidad in operacion.lineas
    ]
    return c.generar_cotizacion.generar_y_enviar(ASESOR, orden_id, lineas)


def autorizar(c: Contenedor, orden_id: str, cotizacion, operacion: Operacion):
    return c.autorizar_trabajos.autorizar_trabajos(
        AutorizarTrabajosCommand(
            _titular(operacion),
            orden_id,
            cotizacion.id,
            [t.id for t in cotizacion.trabajos],
            [],
            f"Autorización registrada en la operación {operacion.id}",
        )
    )


def completar(c: Contenedor, orden_id: str, operacion: Operacion) -> None:
    """Ejecuta los trabajos; un recurso no habilitado o sin existencia pasa a «En espera de refacción» (RN-07)."""
    orden = c.repos.ordenes.obtener_por_id(orden_id)
    recursos = {f"{r.descripcion} ({r.id})": (r, cantidad) for r, cantidad in operacion.lineas}
    faltantes = False
    for trabajo in orden.todos_los_trabajos():
        recurso, cantidad = recursos[trabajo.descripcion]
        if not recurso.habilitado or cantidad > recurso.existencia:
            c.marcar_espera_de_refaccion.confirmar_falta_de_existencia(
                COMPRAS, orden_id, trabajo.id, recurso.id, "Proveedor del paquete"
            )
            faltantes = True
    if faltantes:
        return  # La orden queda «En espera de refacción» hasta registrar la recepción (RN-07, RN-08).
    for trabajo in c.repos.ordenes.obtener_por_id(orden_id).todos_los_trabajos():
        if trabajo.estado == EstadoTrabajo.AUTORIZADO:
            c.ejecutar_trabajo.iniciar(TECNICO, orden_id, trabajo.id)
            c.ejecutar_trabajo.terminar(TECNICO, orden_id, trabajo.id)
    total = c.repos.ordenes.obtener_por_id(orden_id).total_cobrable()
    c.cerrar_orden.cerrar(CerrarOrdenDeServicioCommand(CAJA, orden_id, str(total.valor)))


@dataclass
class ResultadoTransicion:
    estado_final: str
    equivalente_paquete: str
    evento_o_excepcion: str
    aceptada: bool


def ejecutar_transicion(paquete: PaqueteDocente, caso: dict) -> ResultadoTransicion:
    operacion = paquete.operaciones[caso["operacion_id"]]
    accion = caso["accion_sugerida"]
    c = nuevo_contenedor(paquete)
    orden = registrar(c, operacion)
    try:
        if accion == "saltar_estado":
            # Recibido → Cotizado sin pasar por Diagnosticado.
            c.generar_cotizacion.generar_y_enviar(ASESOR, orden.id, [{"descripcion": "Salto", "precio_unitario": "1"}])
        elif accion == "cancelar":
            # El BRD no tiene cancelación desde «Recibido»; el rechazo total solo existe tras cotizar.
            transicionar_orden(c.repos.ordenes.obtener_por_id(orden.id).estado, EstadoOrden.CERRADA_SIN_REPARACION)
        else:
            cotizacion = cotizar(c, orden.id, operacion)
            if accion in ("aprobar", "repetir_aprobacion", "completar"):
                if not operacion.autorizado:
                    raise ErrorDeDominio("La operación no tiene autorización del cliente; la orden sigue en espera.")
                autorizar(c, orden.id, cotizacion, operacion)
            if accion == "repetir_aprobacion":
                autorizar(c, orden.id, cotizacion, operacion)
            if accion == "completar":
                completar(c, orden.id, operacion)
        resultado = "Sin excepción"
        aceptada = True
    except ErrorDeDominio as error:
        resultado = f"{type(error).__name__}: {error.mensaje}"
        aceptada = False
    final = c.repos.ordenes.obtener_por_id(orden.id)
    eventos = [e.tipo for e in final.historial]
    if aceptada:
        resultado = f"Evento final: {eventos[-1]}"
    return ResultadoTransicion(
        final.estado.value,
        EQUIVALENCIA_DE_ESTADOS.get(final.estado, "(sin equivalente)"),
        resultado,
        aceptada,
    )


def evaluar_caso(paquete: PaqueteDocente, caso: dict) -> tuple[str, str]:
    operacion = paquete.operaciones[caso["operacion_id"]]
    if caso["tipo_prueba"] == "validar_operacion":
        cumple = puede_procesarse().es_satisfecha_por(operacion)
        fallas = [
            nombre
            for nombre, spec in (
                ("actor inactivo", ActorActivoSpecification()),
                ("detalle vacío", DetalleNoVacioSpecification()),
                ("sin autorización", AutorizacionRegistradaSpecification()),
            )
            if not spec.es_satisfecha_por(operacion)
        ]
        evidencia = f"total {operacion.total}" + (f"; no cumple: {', '.join(fallas)}" if fallas else "")
        return ("PASA" if cumple else "NO PASA"), evidencia
    cumple = beneficio_de_referencia().es_satisfecha_por(operacion)
    evidencia = (
        f"preferente={'sí' if operacion.actor.preferente else 'no'}; total {operacion.total}; "
        f"promoción={'sí' if operacion.promocion_activa else 'no'}"
    )
    return ("APLICA" if cumple else "NO APLICA"), evidencia


def escribir_resultados(paquete: PaqueteDocente, carpeta_salida: Path) -> tuple[Path, Path]:
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    casos = carpeta_salida / "resultados_casos_prueba.csv"
    with open(casos, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            ["caso_id", "operacion_id", "tipo_prueba", "regla_a_verificar", "resultado_alumno", "evidencia"]
        )
        for caso in paquete.casos:
            resultado, evidencia = evaluar_caso(paquete, caso)
            escritor.writerow(
                [
                    caso["caso_id"],
                    caso["operacion_id"],
                    caso["tipo_prueba"],
                    caso["regla_a_verificar"],
                    resultado,
                    evidencia,
                ]
            )
    transiciones = carpeta_salida / "resultados_transiciones.csv"
    with open(transiciones, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            [
                "caso_id",
                "operacion_id",
                "accion_sugerida",
                "estado_inicial",
                "resultado_alumno",
                "estado_final_brd",
                "estado_equivalente_paquete",
                "evento_o_excepcion",
                "precondicion_puede_procesarse",
            ]
        )
        for caso in paquete.transiciones:
            r = ejecutar_transicion(paquete, caso)
            operacion = paquete.operaciones[caso["operacion_id"]]
            escritor.writerow(
                [
                    caso["caso_id"],
                    caso["operacion_id"],
                    caso["accion_sugerida"],
                    caso["estado_inicial"],
                    "ACEPTADA" if r.aceptada else "RECHAZADA",
                    r.estado_final,
                    r.equivalente_paquete,
                    r.evento_o_excepcion,
                    "PASA" if puede_procesarse().es_satisfecha_por(operacion) else "NO PASA",
                ]
            )
    return casos, transiciones
