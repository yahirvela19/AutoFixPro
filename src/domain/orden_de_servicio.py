"""Aggregate Root OrdenDeServicio y sus entidades internas (Arquitectura §3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import uuid4

from src.domain import eventos as ev
from src.domain.errores import DatosIncompletos, DecisionYaRegistrada, RecursoNoEncontrado, TransicionNoPermitida
from src.domain.estados import (
    EstadoAmpliacion,
    EstadoOrden,
    EstadoTrabajo,
    EtapaEvidencia,
    TipoCotizacion,
    transicionar_orden,
    transicionar_trabajo,
)
from src.domain.eventos import EmisorDeEventos, EventoDeDominio
from src.domain.politicas import ContextoDeAutorizacion, IPoliticaDeAutorizacion
from src.domain.specifications import (
    CandidatoDecision,
    DecisionCompletaSpecification,
    OrdenCotizableSpecification,
    OrdenListaParaEntregaSpecification,
    TrabajoCobrableSpecification,
    TrabajoEjecutableSpecification,
)
from src.domain.value_objects import (
    EvidenciaFotografica,
    InspeccionDeIngreso,
    Monto,
    NecesidadDeRefaccion,
    RegistroDeAutorizacion,
)


def _nuevo_id() -> str:
    return uuid4().hex[:12]


@dataclass
class Diagnostico:
    tecnico_id: str
    tecnico_nombre: str
    falla_encontrada: str
    fecha_hora: datetime


@dataclass
class Ampliacion:
    id: str
    monto: Monto
    motivo: str
    estado: EstadoAmpliacion
    fecha_hora_envio: datetime | None = None
    registro: RegistroDeAutorizacion | None = None


@dataclass
class Trabajo:
    id: str
    descripcion: str
    cantidad: int
    precio_unitario: Monto
    estado: EstadoTrabajo = EstadoTrabajo.PENDIENTE_DE_AUTORIZACION
    ampliaciones: list[Ampliacion] = field(default_factory=list)
    necesidades_de_refaccion: list[NecesidadDeRefaccion] = field(default_factory=list)

    @property
    def monto(self) -> Monto:
        return self.precio_unitario.por(self.cantidad)

    @property
    def monto_ampliaciones_autorizadas(self) -> Monto:
        total = Monto.cero()
        for ampliacion in self.ampliaciones:
            if ampliacion.estado == EstadoAmpliacion.AUTORIZADA:
                total = total + ampliacion.monto
        return total

    @property
    def monto_cobrable(self) -> Monto:
        return self.monto + self.monto_ampliaciones_autorizadas

    def tiene_ampliacion_pendiente(self) -> bool:
        return any(a.estado == EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION for a in self.ampliaciones)

    def cambiar_estado(self, destino: EstadoTrabajo) -> None:
        self.estado = transicionar_trabajo(self.estado, destino)


@dataclass
class Cotizacion:
    id: str
    tipo: TipoCotizacion
    trabajos: list[Trabajo]
    fecha_hora_creacion: datetime
    fecha_hora_envio: datetime | None = None
    descripcion_falla_adicional: str = ""
    registros: list[RegistroDeAutorizacion] = field(default_factory=list)

    def trabajos_pendientes(self) -> list[Trabajo]:
        return [t for t in self.trabajos if t.estado == EstadoTrabajo.PENDIENTE_DE_AUTORIZACION]

    @property
    def esta_decidida(self) -> bool:
        return not self.trabajos_pendientes()

    @property
    def total(self) -> Monto:
        total = Monto.cero()
        for trabajo in self.trabajos:
            total = total + trabajo.monto
        return total


def _crear_trabajos(lineas: list[dict]) -> list[Trabajo]:
    trabajos: list[Trabajo] = []
    for linea in lineas:
        descripcion = str(linea.get("descripcion") or "").strip()
        if not descripcion:
            continue
        try:
            valor = linea.get("cantidad")
            cantidad = 1 if valor in (None, "") else int(valor)
        except (TypeError, ValueError) as exc:
            raise DatosIncompletos(f"La cantidad de «{descripcion}» debe ser un número entero.") from exc
        if cantidad <= 0:
            raise DatosIncompletos(f"La cantidad de «{descripcion}» debe ser mayor a cero.")
        precio = Monto.de(linea.get("precio_unitario") or 0)
        if precio.valor <= 0:
            raise DatosIncompletos(f"El precio de «{descripcion}» debe ser mayor a cero.")
        trabajos.append(Trabajo(_nuevo_id(), descripcion, cantidad, precio))
    if not trabajos:
        raise DatosIncompletos("La cotización debe incluir al menos un trabajo.")
    return trabajos


@dataclass
class OrdenDeServicio(EmisorDeEventos):
    id: str
    folio: str
    cliente_id: str
    vehiculo_id: str
    inspeccion: InspeccionDeIngreso
    fecha_hora_ingreso: datetime
    cargo_diagnostico: Monto = field(default_factory=Monto.cero)
    cargo_diagnostico_aceptado: bool = False
    estado: EstadoOrden = EstadoOrden.RECIBIDO
    diagnostico: Diagnostico | None = None
    cotizaciones: list[Cotizacion] = field(default_factory=list)
    evidencias: list[EvidenciaFotografica] = field(default_factory=list)
    fallas_adicionales_por_cotizar: list[str] = field(default_factory=list)
    nueva_fecha_estimada: date | None = None
    motivo_retraso: str = ""
    fecha_hora_cierre: datetime | None = None
    monto_pagado: Monto | None = None
    historial: list[EventoDeDominio] = field(default_factory=list)
    eventos_pendientes: list[EventoDeDominio] = field(default_factory=list)

    # ------------------------------------------------------------------ ingreso
    @classmethod
    def registrar_ingreso(
        cls,
        *,
        folio: str,
        cliente_id: str,
        vehiculo_id: str,
        inspeccion: InspeccionDeIngreso,
        cargo_diagnostico: Monto,
        cargo_diagnostico_aceptado: bool,
        ahora: datetime,
    ) -> OrdenDeServicio:
        orden = cls(
            id=_nuevo_id(),
            folio=folio,
            cliente_id=cliente_id,
            vehiculo_id=vehiculo_id,
            inspeccion=inspeccion,
            fecha_hora_ingreso=ahora,
            cargo_diagnostico=cargo_diagnostico,
            cargo_diagnostico_aceptado=cargo_diagnostico_aceptado and cargo_diagnostico.valor > 0,
        )
        orden._emitir(ev.VEHICULO_RECIBIDO, orden.id, ahora, "Se registró el ingreso del vehículo.")
        return orden

    def _cambiar_estado(self, destino: EstadoOrden) -> None:
        self.estado = transicionar_orden(self.estado, destino)

    # -------------------------------------------------------------- diagnóstico
    def registrar_diagnostico(
        self, *, tecnico_id: str, tecnico_nombre: str, falla_encontrada: str, ahora: datetime
    ) -> None:
        if self.estado != EstadoOrden.RECIBIDO:
            raise TransicionNoPermitida("El diagnóstico solo se registra en una orden «Recibido».")
        if not str(falla_encontrada or "").strip():
            raise DatosIncompletos("Describe la falla encontrada para registrar el diagnóstico.")
        self.diagnostico = Diagnostico(tecnico_id, tecnico_nombre, falla_encontrada.strip(), ahora)
        self._cambiar_estado(EstadoOrden.DIAGNOSTICADO)
        self._emitir(ev.DIAGNOSTICO_REGISTRADO, self.id, ahora, "El técnico registró el diagnóstico.")

    # --------------------------------------------------------------- cotización
    def generar_cotizacion(self, *, lineas: list[dict], ahora: datetime) -> Cotizacion:
        if not OrdenCotizableSpecification().es_satisfecha_por(self):
            raise TransicionNoPermitida("Solo se cotiza una orden «Diagnosticado» con diagnóstico registrado.")
        cotizacion = Cotizacion(_nuevo_id(), TipoCotizacion.INICIAL, _crear_trabajos(lineas), ahora)
        self.cotizaciones.append(cotizacion)
        self._cambiar_estado(EstadoOrden.COTIZADO)
        self._emitir(
            ev.COTIZACION_GENERADA,
            self.id,
            ahora,
            f"Se generó la cotización inicial por {cotizacion.total}.",
            cotizacion_id=cotizacion.id,
        )
        return cotizacion

    def enviar_cotizacion(self, cotizacion_id: str, ahora: datetime) -> None:
        cotizacion = self.cotizacion(cotizacion_id)
        if cotizacion.fecha_hora_envio is not None:
            raise DecisionYaRegistrada("Esta cotización ya fue enviada al cliente.")
        cotizacion.fecha_hora_envio = ahora
        self._cambiar_estado(EstadoOrden.EN_ESPERA_DE_AUTORIZACION)

    def reportar_falla_adicional(self, *, descripcion: str, ahora: datetime) -> None:
        if self.estado != EstadoOrden.EN_REPARACION:
            raise TransicionNoPermitida("Una falla adicional solo se reporta con la orden «En reparación».")
        if not str(descripcion or "").strip():
            raise DatosIncompletos("Describe la falla adicional encontrada.")
        self.fallas_adicionales_por_cotizar.append(descripcion.strip())
        self._emitir(
            ev.FALLA_ADICIONAL_REPORTADA,
            self.id,
            ahora,
            f"El técnico reportó una falla adicional: {descripcion.strip()}.",
        )

    def generar_cotizacion_complementaria(
        self, *, lineas: list[dict], politica: IPoliticaDeAutorizacion, ahora: datetime
    ) -> Cotizacion:
        if self.estado != EstadoOrden.EN_REPARACION or not self.fallas_adicionales_por_cotizar:
            raise TransicionNoPermitida("No hay una falla adicional reportada por cotizar.")
        trabajos = _crear_trabajos(lineas)
        if not politica.requiere_nueva_autorizacion(ContextoDeAutorizacion(es_trabajo_nuevo=True)):
            raise TransicionNoPermitida("La política vigente no permite trabajos sin autorización.")
        falla = self.fallas_adicionales_por_cotizar.pop(0)
        cotizacion = Cotizacion(
            _nuevo_id(), TipoCotizacion.COMPLEMENTARIA, trabajos, ahora, descripcion_falla_adicional=falla
        )
        self.cotizaciones.append(cotizacion)
        cotizacion.fecha_hora_envio = ahora
        self._cambiar_estado(EstadoOrden.EN_ESPERA_DE_AUTORIZACION)
        self._emitir(
            ev.COTIZACION_GENERADA,
            self.id,
            ahora,
            f"Se generó una cotización complementaria por {cotizacion.total}.",
            cotizacion_id=cotizacion.id,
        )
        return cotizacion

    # -------------------------------------------------------- autorización digital
    def registrar_decision(self, *, cotizacion_id: str, registro: RegistroDeAutorizacion) -> None:
        cotizacion = self.cotizacion(cotizacion_id)
        if cotizacion.esta_decidida:
            raise DecisionYaRegistrada("Esta cotización ya fue decidida; la decisión no se puede modificar.")
        if self.estado not in (EstadoOrden.EN_ESPERA_DE_AUTORIZACION, EstadoOrden.EN_ESPERA_DE_CLIENTE):
            raise TransicionNoPermitida("La orden no está esperando una autorización.")
        candidato = CandidatoDecision(
            cotizacion,
            frozenset(registro.trabajos_autorizados),
            frozenset(registro.trabajos_rechazados),
            registro.referencia_evidencia_digital,
        )
        if not DecisionCompletaSpecification().es_satisfecha_por(candidato):
            raise DatosIncompletos("Indica si autorizas o rechazas cada trabajo y confirma tu decisión.")
        ahora = registro.fecha_hora
        for trabajo in cotizacion.trabajos:
            if trabajo.id in candidato.trabajos_autorizados:
                trabajo.cambiar_estado(EstadoTrabajo.AUTORIZADO)
                self._emitir(
                    ev.TRABAJO_AUTORIZADO,
                    self.id,
                    ahora,
                    f"Trabajo autorizado: {trabajo.descripcion}.",
                    trabajo_id=trabajo.id,
                )
            elif trabajo.id in candidato.trabajos_rechazados:
                trabajo.cambiar_estado(EstadoTrabajo.RECHAZADO)
                self._emitir(
                    ev.TRABAJO_RECHAZADO,
                    self.id,
                    ahora,
                    f"Trabajo rechazado: {trabajo.descripcion}.",
                    trabajo_id=trabajo.id,
                )
        cotizacion.registros.append(registro)

        if candidato.trabajos_autorizados:
            self._continuar_reparacion(ahora)
        elif cotizacion.tipo == TipoCotizacion.INICIAL:
            self._emitir(ev.RECHAZO_TOTAL_REGISTRADO, self.id, ahora, "El cliente rechazó toda la cotización inicial.")
            if not self.cargo_diagnostico_aceptado:
                self._cerrar_sin_reparacion(ahora)
        else:
            self._continuar_reparacion(ahora)

    @property
    def rechazo_total_pendiente_de_cobro(self) -> bool:
        inicial = self.cotizacion_inicial
        return (
            self.estado in (EstadoOrden.EN_ESPERA_DE_AUTORIZACION, EstadoOrden.EN_ESPERA_DE_CLIENTE)
            and inicial is not None
            and inicial.esta_decidida
            and all(t.estado == EstadoTrabajo.RECHAZADO for t in inicial.trabajos)
            and self.cargo_diagnostico_aceptado
        )

    def _continuar_reparacion(self, ahora: datetime) -> None:
        if self.estado in (EstadoOrden.EN_ESPERA_DE_AUTORIZACION, EstadoOrden.EN_ESPERA_DE_CLIENTE):
            self._cambiar_estado(EstadoOrden.EN_REPARACION)
        if self.estado == EstadoOrden.EN_REPARACION and OrdenListaParaEntregaSpecification().es_satisfecha_por(self):
            self._cambiar_estado(EstadoOrden.LISTO_PARA_ENTREGA)
            self._emitir(ev.ORDEN_LISTA_PARA_ENTREGA, self.id, ahora, "La orden está lista para entrega.")

    def _cerrar_sin_reparacion(self, ahora: datetime) -> None:
        self._cambiar_estado(EstadoOrden.CERRADA_SIN_REPARACION)
        self.fecha_hora_cierre = ahora
        self._emitir(ev.ORDEN_CERRADA_SIN_REPARACION, self.id, ahora, "La orden se cerró sin reparación.")

    # ----------------------------------------------------------------- ampliación
    def total_autorizado_inicial(self) -> Monto:
        inicial = self.cotizacion_inicial
        total = Monto.cero()
        if inicial is None:
            return total
        for trabajo in inicial.trabajos:
            if trabajo.estado not in (EstadoTrabajo.PENDIENTE_DE_AUTORIZACION, EstadoTrabajo.RECHAZADO):
                total = total + trabajo.monto
        return total

    def ampliaciones_acumuladas(self) -> Monto:
        total = Monto.cero()
        for trabajo in self.todos_los_trabajos():
            for ampliacion in trabajo.ampliaciones:
                if ampliacion.estado != EstadoAmpliacion.RECHAZADA:
                    total = total + ampliacion.monto
        return total

    def solicitar_ampliacion(
        self, *, trabajo_id: str, monto: Monto, motivo: str, politica: IPoliticaDeAutorizacion, ahora: datetime
    ) -> Ampliacion:
        if self.estado != EstadoOrden.EN_REPARACION:
            raise TransicionNoPermitida("Una ampliación solo se solicita con la orden «En reparación».")
        trabajo = self.trabajo(trabajo_id)
        if trabajo.estado not in (EstadoTrabajo.AUTORIZADO, EstadoTrabajo.EN_EJECUCION):
            raise TransicionNoPermitida("Solo se amplía un trabajo «Autorizado» o «En ejecución».")
        if monto.valor <= 0:
            raise DatosIncompletos("El monto de la ampliación debe ser mayor a cero.")
        if not str(motivo or "").strip():
            raise DatosIncompletos("Describe el motivo de la ampliación.")
        contexto = ContextoDeAutorizacion(
            es_trabajo_nuevo=False,
            total_autorizado_inicial=self.total_autorizado_inicial(),
            ampliaciones_acumuladas=self.ampliaciones_acumuladas() + monto,
        )
        requiere = politica.requiere_nueva_autorizacion(contexto)
        ampliacion = Ampliacion(
            _nuevo_id(),
            monto,
            motivo.strip(),
            EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION if requiere else EstadoAmpliacion.AUTORIZADA,
            fecha_hora_envio=ahora if requiere else None,
        )
        trabajo.ampliaciones.append(ampliacion)
        if requiere:
            self._cambiar_estado(EstadoOrden.EN_ESPERA_DE_AUTORIZACION)
            self._emitir(
                ev.AMPLIACION_SOLICITADA,
                self.id,
                ahora,
                f"Ampliación de {monto} en «{trabajo.descripcion}»: supera el 20 % y requiere autorización.",
                trabajo_id=trabajo.id,
                ampliacion_id=ampliacion.id,
            )
        else:
            self._emitir(
                ev.AMPLIACION_DECIDIDA,
                self.id,
                ahora,
                f"Ampliación de {monto} en «{trabajo.descripcion}»: no supera el 20 %, se aplica.",
                trabajo_id=trabajo.id,
                ampliacion_id=ampliacion.id,
            )
        return ampliacion

    def registrar_decision_de_ampliacion(
        self, *, trabajo_id: str, ampliacion_id: str, autoriza: bool, registro: RegistroDeAutorizacion
    ) -> None:
        trabajo = self.trabajo(trabajo_id)
        ampliacion = next((a for a in trabajo.ampliaciones if a.id == ampliacion_id), None)
        if ampliacion is None:
            raise RecursoNoEncontrado("No se encontró la ampliación.")
        if ampliacion.estado != EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION:
            raise DecisionYaRegistrada("Esta ampliación ya fue decidida.")
        if self.estado not in (EstadoOrden.EN_ESPERA_DE_AUTORIZACION, EstadoOrden.EN_ESPERA_DE_CLIENTE):
            raise TransicionNoPermitida("La orden no está esperando una autorización.")
        if not registro.referencia_evidencia_digital.strip():
            raise DatosIncompletos("Confirma tu decisión para registrar la evidencia digital.")
        ampliacion.estado = EstadoAmpliacion.AUTORIZADA if autoriza else EstadoAmpliacion.RECHAZADA
        ampliacion.registro = registro
        self._emitir(
            ev.AMPLIACION_DECIDIDA,
            self.id,
            registro.fecha_hora,
            f"Ampliación de «{trabajo.descripcion}» {ampliacion.estado.lower()}.",
            trabajo_id=trabajo.id,
            ampliacion_id=ampliacion.id,
        )
        self._continuar_reparacion(registro.fecha_hora)

    # ----------------------------------------------------------------- refacciones
    def confirmar_falta_de_existencia(
        self, *, trabajo_id: str, codigo_refaccion: str, proveedor: str, ahora: datetime
    ) -> None:
        if self.estado not in (EstadoOrden.EN_REPARACION, EstadoOrden.EN_ESPERA_DE_REFACCION):
            raise TransicionNoPermitida("La falta de existencia se registra con la orden «En reparación».")
        if not str(proveedor or "").strip():
            raise DatosIncompletos("Captura el proveedor al que se pedirá la refacción.")
        trabajo = self.trabajo(trabajo_id)
        if trabajo.estado != EstadoTrabajo.AUTORIZADO:
            raise TransicionNoPermitida("Solo se registra la falta de refacción de un trabajo «Autorizado».")
        necesidad = NecesidadDeRefaccion(codigo_refaccion.strip(), tiene_existencia=False)
        trabajo.necesidades_de_refaccion.append(necesidad)
        trabajo.cambiar_estado(EstadoTrabajo.EN_ESPERA_DE_REFACCION)
        if self.estado == EstadoOrden.EN_REPARACION:
            self._cambiar_estado(EstadoOrden.EN_ESPERA_DE_REFACCION)
        self._emitir(
            ev.REFACCION_SIN_EXISTENCIA_DETECTADA,
            self.id,
            ahora,
            f"Refacción {necesidad.codigo_refaccion} sin existencia para «{trabajo.descripcion}».",
            trabajo_id=trabajo.id,
            codigo_refaccion=necesidad.codigo_refaccion,
            proveedor=proveedor.strip(),
        )

    def reanudar_reparacion(self, *, trabajo_id: str, codigo_refaccion: str, ahora: datetime) -> bool:
        """Libera el trabajo al recibir la refacción (RN-08). Es idempotente."""
        trabajo = self.trabajo(trabajo_id)
        if trabajo.estado != EstadoTrabajo.EN_ESPERA_DE_REFACCION:
            return False
        trabajo.necesidades_de_refaccion = [
            NecesidadDeRefaccion(n.codigo_refaccion, True) if n.codigo_refaccion == codigo_refaccion else n
            for n in trabajo.necesidades_de_refaccion
        ]
        if all(n.tiene_existencia for n in trabajo.necesidades_de_refaccion):
            trabajo.cambiar_estado(EstadoTrabajo.AUTORIZADO)
        if self.estado == EstadoOrden.EN_ESPERA_DE_REFACCION and not any(
            t.estado == EstadoTrabajo.EN_ESPERA_DE_REFACCION for t in self.todos_los_trabajos()
        ):
            self._cambiar_estado(EstadoOrden.EN_REPARACION)
        self._emitir(
            ev.REPARACION_REANUDADA,
            self.id,
            ahora,
            f"Llegó la refacción {codigo_refaccion}; el trabajo «{trabajo.descripcion}» continúa.",
            trabajo_id=trabajo.id,
        )
        return True

    def notificar_nueva_fecha(self, *, nueva_fecha: date, motivo: str, hoy: date, ahora: datetime) -> None:
        if self.estado != EstadoOrden.EN_ESPERA_DE_REFACCION:
            raise TransicionNoPermitida("La nueva fecha se registra con la orden «En espera de refacción».")
        if nueva_fecha < hoy:
            raise DatosIncompletos("La nueva fecha de entrega no puede ser anterior a hoy.")
        if not str(motivo or "").strip():
            raise DatosIncompletos("Indica el motivo del cambio de fecha.")
        self.nueva_fecha_estimada = nueva_fecha
        self.motivo_retraso = motivo.strip()
        self._emitir(
            ev.NUEVA_FECHA_ENTREGA_NOTIFICADA,
            self.id,
            ahora,
            f"Nueva fecha estimada de entrega: {nueva_fecha:%d/%m/%Y}. Motivo: {motivo.strip()}.",
        )

    # ------------------------------------------------------------------ ejecución
    def iniciar_trabajo(self, *, trabajo_id: str, ahora: datetime) -> None:
        if self.estado != EstadoOrden.EN_REPARACION:
            raise TransicionNoPermitida("Los trabajos se inician con la orden «En reparación».")
        trabajo = self.trabajo(trabajo_id)
        if not TrabajoEjecutableSpecification().es_satisfecha_por(trabajo):
            raise TransicionNoPermitida(
                "Solo se inicia un trabajo «Autorizado», con refacciones disponibles y sin ampliación pendiente."
            )
        trabajo.cambiar_estado(EstadoTrabajo.EN_EJECUCION)
        self._emitir(
            ev.TRABAJO_INICIADO, self.id, ahora, f"Inició el trabajo «{trabajo.descripcion}».", trabajo_id=trabajo.id
        )

    def terminar_trabajo(self, *, trabajo_id: str, ahora: datetime) -> None:
        if self.estado != EstadoOrden.EN_REPARACION:
            raise TransicionNoPermitida("Los trabajos se terminan con la orden «En reparación».")
        trabajo = self.trabajo(trabajo_id)
        if trabajo.tiene_ampliacion_pendiente():
            raise TransicionNoPermitida("El trabajo tiene una ampliación pendiente de autorización.")
        trabajo.cambiar_estado(EstadoTrabajo.TERMINADO)
        self._emitir(
            ev.TRABAJO_TERMINADO, self.id, ahora, f"Terminó el trabajo «{trabajo.descripcion}».", trabajo_id=trabajo.id
        )
        self._continuar_reparacion(ahora)

    def trabajos_ejecutables(self) -> list[Trabajo]:
        if self.estado != EstadoOrden.EN_REPARACION:
            return []
        especificacion = TrabajoEjecutableSpecification()
        return [t for t in self.todos_los_trabajos() if especificacion.es_satisfecha_por(t)]

    # ----------------------------------------------------------------- evidencias
    def registrar_evidencia_fotografica(self, evidencia: EvidenciaFotografica) -> None:
        if self.estado in (EstadoOrden.CERRADO, EstadoOrden.CERRADA_SIN_REPARACION):
            raise TransicionNoPermitida("La orden ya está cerrada.")
        if evidencia.etapa == EtapaEvidencia.ENTREGA and self.estado != EstadoOrden.LISTO_PARA_ENTREGA:
            raise TransicionNoPermitida("La evidencia de entrega se registra con la orden «Listo para entrega».")
        if evidencia.etapa == EtapaEvidencia.INGRESO and self.estado not in (
            EstadoOrden.RECIBIDO,
            EstadoOrden.DIAGNOSTICADO,
        ):
            raise TransicionNoPermitida("La evidencia de ingreso se registra antes de cotizar.")
        self.evidencias.append(evidencia)
        self._emitir(
            ev.EVIDENCIA_FOTOGRAFICA_REGISTRADA,
            self.id,
            evidencia.fecha_hora,
            f"Se registró evidencia fotográfica de {evidencia.etapa.lower()}.",
        )

    # ------------------------------------------------------------- plazo y cierre
    def marcar_en_espera_de_cliente(self, ahora: datetime) -> None:
        self._cambiar_estado(EstadoOrden.EN_ESPERA_DE_CLIENTE)
        self._emitir(
            ev.PLAZO_DE_RESPUESTA_VENCIDO,
            self.id,
            ahora,
            "Pasaron 24 horas sin respuesta del cliente; se avisó al Gerente del Taller.",
        )

    def total_cobrable(self) -> Monto:
        total = self.cargo_diagnostico if self.cargo_diagnostico_aceptado else Monto.cero()
        especificacion = TrabajoCobrableSpecification()
        for trabajo in self.todos_los_trabajos():
            if especificacion.es_satisfecha_por(trabajo):
                total = total + trabajo.monto_cobrable
        return total

    def cerrar(self, *, pago: Monto, es_flotilla: bool, ahora: datetime) -> None:
        if self.rechazo_total_pendiente_de_cobro:
            if pago < self.cargo_diagnostico:
                raise DatosIncompletos(f"El pago debe cubrir el diagnóstico: {self.cargo_diagnostico}.")
            self.monto_pagado = pago
            self._cerrar_sin_reparacion(ahora)
            return
        if self.estado != EstadoOrden.LISTO_PARA_ENTREGA:
            raise TransicionNoPermitida("Solo se cierra una orden «Listo para entrega».")
        total = self.total_cobrable()
        if not es_flotilla and pago < total:
            raise DatosIncompletos(f"El pago es insuficiente: el total a cobrar es {total}.")
        self.monto_pagado = None if es_flotilla else pago
        self._cambiar_estado(EstadoOrden.CERRADO)
        self.fecha_hora_cierre = ahora
        descripcion = (
            "La orden se cerró y queda para la facturación consolidada del mes."
            if es_flotilla
            else f"Caja cobró {total} y cerró la orden."
        )
        self._emitir(ev.ORDEN_DE_SERVICIO_CERRADA, self.id, ahora, descripcion)

    # ------------------------------------------------------------------ consultas
    @property
    def cotizacion_inicial(self) -> Cotizacion | None:
        return next((c for c in self.cotizaciones if c.tipo == TipoCotizacion.INICIAL), None)

    def cotizacion(self, cotizacion_id: str) -> Cotizacion:
        cotizacion = next((c for c in self.cotizaciones if c.id == cotizacion_id), None)
        if cotizacion is None:
            raise RecursoNoEncontrado("No se encontró la cotización.")
        return cotizacion

    def todos_los_trabajos(self) -> list[Trabajo]:
        return [t for c in self.cotizaciones for t in c.trabajos]

    def trabajo(self, trabajo_id: str) -> Trabajo:
        trabajo = next((t for t in self.todos_los_trabajos() if t.id == trabajo_id), None)
        if trabajo is None:
            raise RecursoNoEncontrado("No se encontró el trabajo.")
        return trabajo

    def solicitudes_pendientes(self) -> list[Cotizacion | Ampliacion]:
        pendientes: list[Cotizacion | Ampliacion] = [c for c in self.cotizaciones if not c.esta_decidida]
        pendientes += [
            a
            for t in self.todos_los_trabajos()
            for a in t.ampliaciones
            if a.estado == EstadoAmpliacion.PENDIENTE_DE_AUTORIZACION
        ]
        return pendientes
