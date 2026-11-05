"""Queries del CQRS básico: lecturas que no modifican Aggregates (Arquitectura §7.1).

Las vistas usan solo texto del negocio para que la interfaz y la API muestren lo mismo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from src.application.puertos import Repositorios
from src.application.servicios import ROLES_DEL_TALLER, puede_ver_orden, requerir_rol
from src.domain import eventos as ev
from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.errores import AutorizadorNoValido, DatosIncompletos, RecursoNoEncontrado
from src.domain.estados import EstadoOrden, Rol
from src.domain.orden_de_servicio import OrdenDeServicio
from src.domain.servicios import ServicioDePriorizacion
from src.domain.specifications import TrabajoCobrableSpecification
from src.domain.value_objects import Monto, Usuario


def fecha_hora(valor: datetime | None) -> str:
    return valor.strftime("%d/%m/%Y %H:%M") if valor else ""


def importe(monto: Monto) -> str:
    return str(monto)


@dataclass(frozen=True)
class ConsultarEstadoVehiculoQuery:
    usuario: Usuario
    orden_id: str


@dataclass(frozen=True)
class ObtenerDetalleParaCobroQuery:
    usuario: Usuario
    orden_id: str


@dataclass(frozen=True)
class ObtenerIndicadoresQuery:
    usuario: Usuario
    desde: date
    hasta: date


@dataclass(frozen=True)
class ConsultarColaDeAtencionQuery:
    usuario: Usuario


class _Consulta:
    def __init__(self, repos: Repositorios, notificaciones: Any = None) -> None:
        self.repos = repos
        self.notificaciones = notificaciones

    def _cliente(self, cliente_id: str) -> Cliente:
        cliente = self.repos.clientes.obtener_por_id(cliente_id)
        if cliente is None:
            raise RecursoNoEncontrado("No se encontró el cliente.")
        return cliente

    def resumen(self, orden: OrdenDeServicio) -> dict:
        cliente = self._cliente(orden.cliente_id)
        vehiculo = self.repos.vehiculos.obtener_por_id(orden.vehiculo_id)
        return {
            "id": orden.id,
            "folio": orden.folio,
            "estado": orden.estado.value,
            "cliente": cliente.nombre,
            "tipo_cliente": cliente.tipo.value,
            "prioridad_contractual": isinstance(cliente, ClienteFlotilla) and cliente.prioridad_contractual,
            "vehiculo": vehiculo.descripcion() if vehiculo else "",
            "fecha_ingreso": fecha_hora(orden.fecha_hora_ingreso),
        }


class ListarOrdenesHandler(_Consulta):
    def manejar(self, usuario: Usuario) -> list[dict]:
        ordenes = sorted(self.repos.ordenes.listar(), key=lambda o: o.fecha_hora_ingreso, reverse=True)
        visibles = [o for o in ordenes if puede_ver_orden(usuario, self._cliente(o.cliente_id))]
        return [self.resumen(o) for o in visibles]


class ConsultarEstadoVehiculoHandler(_Consulta):
    """US-14: el cliente ve el estado de su vehículo; un cliente ajeno recibe acceso negado."""

    def manejar(self, consulta: ConsultarEstadoVehiculoQuery) -> dict:
        orden = self.repos.ordenes.obtener_por_id(consulta.orden_id)
        if orden is None:
            raise RecursoNoEncontrado("No se encontró la orden de servicio.")
        cliente = self._cliente(orden.cliente_id)
        if not puede_ver_orden(consulta.usuario, cliente):
            raise AutorizadorNoValido("No tienes acceso a esta orden de servicio.")
        return self.vista(orden, cliente)

    def vista(self, orden: OrdenDeServicio, cliente: Cliente) -> dict:
        vehiculo = self.repos.vehiculos.obtener_por_id(orden.vehiculo_id)
        descripciones = {t.id: t.descripcion for t in orden.todos_los_trabajos()}
        cotizaciones = []
        for c in orden.cotizaciones:
            cotizaciones.append(
                {
                    "id": c.id,
                    "tipo": c.tipo.value,
                    "total": importe(c.total),
                    "pendiente": not c.esta_decidida,
                    "falla_adicional": c.descripcion_falla_adicional,
                    "fecha_envio": fecha_hora(c.fecha_hora_envio),
                    "trabajos": [
                        {
                            "id": t.id,
                            "descripcion": t.descripcion,
                            "cantidad": t.cantidad,
                            "precio_unitario": importe(t.precio_unitario),
                            "monto": importe(t.monto),
                            "estado": t.estado.value,
                            "ampliaciones": [
                                {
                                    "id": a.id,
                                    "monto": importe(a.monto),
                                    "motivo": a.motivo,
                                    "estado": a.estado.value,
                                }
                                for a in t.ampliaciones
                            ],
                            "refacciones": [
                                {
                                    "codigo": n.codigo_refaccion,
                                    "existencia": "Con existencia" if n.tiene_existencia else "Sin existencia",
                                }
                                for n in t.necesidades_de_refaccion
                            ],
                        }
                        for t in c.trabajos
                    ],
                    "registros": [
                        {
                            "autorizador": r.autorizador_nombre,
                            "rol": r.rol.value,
                            "fecha": fecha_hora(r.fecha_hora),
                            "autorizados": [descripciones.get(i, i) for i in r.trabajos_autorizados],
                            "rechazados": [descripciones.get(i, i) for i in r.trabajos_rechazados],
                            "evidencia": r.referencia_evidencia_digital,
                        }
                        for r in c.registros
                    ],
                }
            )
        ordenes_de_compra = [
            {
                "id": oc.id,
                "trabajo": descripciones.get(oc.trabajo_id, ""),
                "codigo": oc.codigo_refaccion,
                "proveedor": oc.proveedor,
                "estado": oc.estado.value,
                "fecha": fecha_hora(oc.fecha_hora_solicitud),
            }
            for oc in self.repos.ordenes_de_compra.listar()
            if oc.orden_de_servicio_id == orden.id
        ]
        avisos = []
        if self.notificaciones is not None:
            avisos = [
                {"fecha": fecha_hora(n["fecha_hora"]), "mensaje": n["mensaje"]}
                for n in self.notificaciones.listar(orden_id=orden.id, destinatario=orden.cliente_id)
            ]
        return {
            "id": orden.id,
            "folio": orden.folio,
            "estado": orden.estado.value,
            "cliente": {
                "id": cliente.id,
                "nombre": cliente.nombre,
                "tipo": cliente.tipo.value,
                "telefono": cliente.telefono,
            },
            "vehiculo": {
                "descripcion": vehiculo.descripcion() if vehiculo else "",
                "placa": vehiculo.placa if vehiculo else "",
                "marca": vehiculo.marca if vehiculo else "",
                "modelo": vehiculo.modelo if vehiculo else "",
                "vin": vehiculo.vin if vehiculo else "",
            },
            "inspeccion": {
                "kilometraje": orden.inspeccion.kilometraje,
                "nivel_combustible": orden.inspeccion.nivel_combustible,
                "danos_visibles": orden.inspeccion.danos_visibles,
                "motivo_ingreso": orden.inspeccion.motivo_ingreso,
            },
            "fecha_ingreso": fecha_hora(orden.fecha_hora_ingreso),
            "cargo_diagnostico": importe(orden.cargo_diagnostico),
            "cargo_diagnostico_aceptado": orden.cargo_diagnostico_aceptado,
            "diagnostico": None
            if orden.diagnostico is None
            else {
                "falla_encontrada": orden.diagnostico.falla_encontrada,
                "tecnico": orden.diagnostico.tecnico_nombre,
                "fecha": fecha_hora(orden.diagnostico.fecha_hora),
            },
            "cotizaciones": cotizaciones,
            "fallas_por_cotizar": list(orden.fallas_adicionales_por_cotizar),
            "nueva_fecha_estimada": orden.nueva_fecha_estimada.strftime("%d/%m/%Y")
            if orden.nueva_fecha_estimada
            else "",
            "motivo_retraso": orden.motivo_retraso,
            "evidencias": [
                {
                    "etapa": e.etapa.value,
                    "archivo": e.referencia_archivo,
                    "registrada_por": e.registrada_por,
                    "fecha": fecha_hora(e.fecha_hora),
                }
                for e in orden.evidencias
            ],
            "ordenes_de_compra": ordenes_de_compra,
            "total_cobrable": importe(orden.total_cobrable()),
            "rechazo_total_pendiente_de_cobro": orden.rechazo_total_pendiente_de_cobro,
            "fecha_cierre": fecha_hora(orden.fecha_hora_cierre),
            "historial": [
                {"fecha": fecha_hora(e.fecha_hora), "descripcion": e.descripcion} for e in reversed(orden.historial)
            ],
            "avisos_al_cliente": avisos,
        }


class ObtenerDetalleParaCobroHandler(_Consulta):
    """US-19: Caja ve solo trabajos «Terminado» y el diagnóstico aceptado."""

    def manejar(self, consulta: ObtenerDetalleParaCobroQuery) -> dict:
        requerir_rol(consulta.usuario, Rol.CAJA)
        orden = self.repos.ordenes.obtener_por_id(consulta.orden_id)
        if orden is None:
            raise RecursoNoEncontrado("No se encontró la orden de servicio.")
        cliente = self._cliente(orden.cliente_id)
        cobrable = TrabajoCobrableSpecification()
        conceptos = []
        if orden.cargo_diagnostico_aceptado:
            conceptos.append({"concepto": "Diagnóstico", "importe": importe(orden.cargo_diagnostico)})
        if not orden.rechazo_total_pendiente_de_cobro:
            for t in orden.todos_los_trabajos():
                if cobrable.es_satisfecha_por(t):
                    conceptos.append({"concepto": f"{t.descripcion} (x{t.cantidad})", "importe": importe(t.monto)})
                    if t.monto_ampliaciones_autorizadas.valor > 0:
                        conceptos.append(
                            {
                                "concepto": f"Ampliación: {t.descripcion}",
                                "importe": importe(t.monto_ampliaciones_autorizadas),
                            }
                        )
        total = orden.cargo_diagnostico if orden.rechazo_total_pendiente_de_cobro else orden.total_cobrable()
        return {
            "folio": orden.folio,
            "estado": orden.estado.value,
            "cliente": cliente.nombre,
            "es_flotilla": isinstance(cliente, ClienteFlotilla),
            "conceptos": conceptos,
            "total": importe(total),
            "total_valor": str(total.valor),
            "rechazo_total": orden.rechazo_total_pendiente_de_cobro,
            "puede_cerrarse": orden.estado == EstadoOrden.LISTO_PARA_ENTREGA or orden.rechazo_total_pendiente_de_cobro,
        }


class ObtenerIndicadoresHandler(_Consulta):
    """US-15 (Table Module ligero, ADR-001): agrega datos sin proteger invariantes."""

    def __init__(self, repos: Repositorios, notificaciones: Any = None) -> None:
        super().__init__(repos, notificaciones)

    def manejar(self, consulta: ObtenerIndicadoresQuery) -> dict:
        requerir_rol(consulta.usuario, Rol.GERENTE_DEL_TALLER)
        if consulta.hasta < consulta.desde:
            raise DatosIncompletos("La fecha final no puede ser anterior a la inicial.")

        def en_periodo(momento: datetime | None) -> bool:
            return momento is not None and consulta.desde <= momento.date() <= consulta.hasta

        ordenes = self.repos.ordenes.listar()
        cerradas = [
            o
            for o in ordenes
            if o.estado in (EstadoOrden.CERRADO, EstadoOrden.CERRADA_SIN_REPARACION) and en_periodo(o.fecha_hora_cierre)
        ]
        disputas = [d for d in self.repos.disputas.listar() if en_periodo(d.fecha_hora)]
        registros = [r for o in ordenes for c in o.cotizaciones for r in c.registros if en_periodo(r.fecha_hora)]
        con_evidencia = [r for r in registros if r.referencia_evidencia_digital.strip()]
        tiempos: list[Decimal] = []
        for orden in ordenes:
            pendiente: datetime | None = None
            for evento in orden.historial:
                if evento.tipo == ev.REFACCION_SIN_EXISTENCIA_DETECTADA and pendiente is None:
                    pendiente = evento.fecha_hora
                elif evento.tipo == ev.NUEVA_FECHA_ENTREGA_NOTIFICADA and pendiente is not None:
                    if en_periodo(evento.fecha_hora):
                        minutos = Decimal((evento.fecha_hora - pendiente).total_seconds()) / 60
                        tiempos.append(minutos)
                    pendiente = None
        dentro_de_2_horas = [t for t in tiempos if t < 120]
        return {
            "periodo": f"{consulta.desde:%d/%m/%Y} – {consulta.hasta:%d/%m/%Y}",
            "ordenes_cerradas": len(cerradas),
            "disputas_registradas": len(disputas),
            "disputas_abiertas": sum(1 for d in disputas if d.estado.value == "Abierta"),
            "decisiones_de_autorizacion": len(registros),
            "porcentaje_con_evidencia_digital": _porcentaje(len(con_evidencia), len(registros)),
            "avisos_de_retraso": len(tiempos),
            "tiempo_promedio_comunicacion_retraso_minutos": f"{(sum(tiempos) / len(tiempos)):.0f}"
            if tiempos
            else "Sin avisos",
            "porcentaje_avisos_menos_de_2_horas": _porcentaje(len(dentro_de_2_horas), len(tiempos)),
        }


def _porcentaje(parte: int, total: int) -> str:
    if total == 0:
        return "Sin datos"
    return f"{Decimal(parte * 100) / Decimal(total):.1f} %"


class ConsultarColaDeAtencionHandler(_Consulta):
    """US-18: la prioridad contractual aparece primero entre las órdenes cuya atención aún no inicia."""

    def manejar(self, consulta: ConsultarColaDeAtencionQuery) -> list[dict]:
        requerir_rol(consulta.usuario, Rol.ASESOR_DE_SERVICIO, Rol.TECNICO, Rol.GERENTE_DEL_TALLER)
        clientes = {c.id: c for c in self.repos.clientes.listar()}
        ordenadas = ServicioDePriorizacion().ordenar(self.repos.ordenes.listar(), clientes)
        return [self.resumen(o) for o in ordenadas]


class ListasDelTallerHandler(_Consulta):
    """Listas de apoyo para las pantallas de Compras, Caja y Gerente del Taller."""

    def ordenes_de_compra(self, usuario: Usuario) -> list[dict]:
        requerir_rol(usuario, Rol.COMPRAS)
        folios = {o.id: o.folio for o in self.repos.ordenes.listar()}
        return [
            {
                "id": oc.id,
                "orden_id": oc.orden_de_servicio_id,
                "folio": folios.get(oc.orden_de_servicio_id, ""),
                "codigo": oc.codigo_refaccion,
                "proveedor": oc.proveedor,
                "estado": oc.estado.value,
                "fecha": fecha_hora(oc.fecha_hora_solicitud),
                "recibida": fecha_hora(oc.fecha_hora_recepcion),
            }
            for oc in sorted(self.repos.ordenes_de_compra.listar(), key=lambda x: x.fecha_hora_solicitud, reverse=True)
        ]

    def disputas(self, usuario: Usuario) -> list[dict]:
        if usuario.rol not in ROLES_DEL_TALLER and usuario.rol not in (Rol.CLIENTE_TITULAR, Rol.RESPONSABLE_DE_CUENTA):
            return []
        folios = {o.id: o.folio for o in self.repos.ordenes.listar()}
        resultado = []
        for d in sorted(self.repos.disputas.listar(), key=lambda x: x.fecha_hora, reverse=True):
            if usuario.rol not in ROLES_DEL_TALLER and not self._cliente(d.cliente_id).validar_autorizador(usuario):
                continue
            resultado.append(
                {
                    "id": d.id,
                    "orden_id": d.orden_de_servicio_id,
                    "folio": folios.get(d.orden_de_servicio_id, ""),
                    "cliente": self._cliente(d.cliente_id).nombre,
                    "categoria": d.categoria.value,
                    "descripcion": d.descripcion,
                    "estado": d.estado.value,
                    "fecha": fecha_hora(d.fecha_hora),
                    "resolucion": d.resolucion,
                }
            )
        return resultado

    def facturaciones(self, usuario: Usuario) -> list[dict]:
        requerir_rol(usuario, Rol.CAJA, Rol.GERENTE_DEL_TALLER)
        return [
            {
                "cliente": self._cliente(f.cliente_id).nombre,
                "periodo": f.periodo,
                "total": importe(f.total),
                "ordenes": [d["folio"] for d in f.detalle],
                "fecha": fecha_hora(f.fecha_hora),
            }
            for f in sorted(self.repos.facturaciones.listar(), key=lambda x: x.fecha_hora, reverse=True)
        ]

    def clientes(self) -> list[dict]:
        return [
            {
                "id": c.id,
                "nombre": c.nombre,
                "tipo": c.tipo.value,
                "prioridad_contractual": isinstance(c, ClienteFlotilla) and c.prioridad_contractual,
            }
            for c in sorted(self.repos.clientes.listar(), key=lambda x: x.nombre)
        ]

    def avisos_al_gerente(self, usuario: Usuario) -> list[dict]:
        requerir_rol(usuario, Rol.GERENTE_DEL_TALLER)
        if self.notificaciones is None:
            return []
        return [
            {"fecha": fecha_hora(n["fecha_hora"]), "mensaje": n["mensaje"]}
            for n in self.notificaciones.listar(destinatario="GERENTE")
        ]
