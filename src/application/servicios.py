"""Application Services: coordinan casos de uso sin contener reglas de negocio (Arquitectura §7)."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from src.application.comandos import (
    AutorizarTrabajosCommand,
    CerrarOrdenDeServicioCommand,
    ReportarFallaAdicionalCommand,
)
from src.application.puertos import (
    IDespachadorDeEventos,
    INotificacionCliente,
    INotificacionGerente,
    IReloj,
    Repositorios,
)
from src.domain.cliente import Cliente, ClienteFlotilla
from src.domain.disputa import Disputa
from src.domain.errores import AutorizadorNoValido, DatosIncompletos, RecursoNoEncontrado, RolNoPermitido
from src.domain.estados import (
    CategoriaDisputa,
    EstadoOrden,
    EstadoOrdenDeCompra,
    EtapaEvidencia,
    Rol,
    TipoCliente,
)
from src.domain.eventos import EventoDeDominio
from src.domain.facturacion_consolidada import FacturacionConsolidada
from src.domain.orden_de_compra import OrdenDeCompra
from src.domain.orden_de_servicio import Cotizacion, OrdenDeServicio
from src.domain.politicas import PoliticaAutorizacionAmpliacion, PoliticaAutorizacionEstandar
from src.domain.servicios import ServicioDeEscalamiento
from src.domain.specifications import AutorizadorValidoSpecification, CandidatoAutorizador
from src.domain.value_objects import (
    EvidenciaFotografica,
    InspeccionDeIngreso,
    Monto,
    RegistroDeAutorizacion,
    Usuario,
)
from src.domain.vehiculo import Vehiculo

ROLES_DEL_TALLER = frozenset(
    {
        Rol.ASESOR_DE_SERVICIO,
        Rol.TECNICO,
        Rol.COMPRAS,
        Rol.CAJA,
        Rol.GERENTE_DEL_TALLER,
    }
)


def requerir_rol(usuario: Usuario, *roles: Rol) -> None:
    if usuario.rol not in roles:
        nombres = " o ".join(roles)
        raise RolNoPermitido(f"Esta acción la realiza el rol {nombres}.")


def puede_ver_orden(usuario: Usuario, cliente: Cliente) -> bool:
    if usuario.rol in ROLES_DEL_TALLER:
        return True
    return cliente.validar_autorizador(usuario)


class _ServicioBase:
    def __init__(
        self,
        repos: Repositorios,
        reloj: IReloj,
        despachador: IDespachadorDeEventos,
        notificacion_cliente: INotificacionCliente | None = None,
        notificacion_gerente: INotificacionGerente | None = None,
    ) -> None:
        self.repos = repos
        self.reloj = reloj
        self.despachador = despachador
        self.notificacion_cliente = notificacion_cliente
        self.notificacion_gerente = notificacion_gerente

    def _orden(self, orden_id: str) -> OrdenDeServicio:
        orden = self.repos.ordenes.obtener_por_id(orden_id)
        if orden is None:
            raise RecursoNoEncontrado("No se encontró la orden de servicio.")
        return orden

    def _cliente(self, cliente_id: str) -> Cliente:
        cliente = self.repos.clientes.obtener_por_id(cliente_id)
        if cliente is None:
            raise RecursoNoEncontrado("No se encontró el cliente.")
        return cliente

    def _guardar(self, orden: OrdenDeServicio) -> None:
        """Unit of Work: una transacción por Aggregate; los eventos se publican después de guardar."""
        eventos = orden.extraer_eventos()
        self.repos.ordenes.guardar(orden)
        self.despachador.publicar(eventos)

    def _avisar_cliente(self, orden: OrdenDeServicio, mensaje: str) -> None:
        if self.notificacion_cliente is not None:
            self.notificacion_cliente.notificar_cliente(orden.cliente_id, orden.id, mensaje)

    def _registro(
        self, usuario: Usuario, autorizados: list[str], rechazados: list[str], referencia: str
    ) -> RegistroDeAutorizacion:
        return RegistroDeAutorizacion(
            autorizador_id=usuario.id,
            autorizador_nombre=usuario.nombre,
            rol=usuario.rol,
            fecha_hora=self.reloj.ahora(),
            trabajos_autorizados=tuple(autorizados),
            trabajos_rechazados=tuple(rechazados),
            referencia_evidencia_digital=referencia or "",
        )


# ---------------------------------------------------------------------- CU-01
class RegistrarIngresoService(_ServicioBase):
    def registrar(
        self,
        usuario: Usuario,
        *,
        cliente_id: str,
        placa: str,
        marca: str,
        modelo: str,
        vin: str,
        kilometraje: int,
        nivel_combustible: str,
        danos_visibles: str,
        motivo_ingreso: str,
        cargo_diagnostico: str = "0",
        cargo_diagnostico_aceptado: bool = False,
        foto_ingreso: str | None = None,
    ) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.ASESOR_DE_SERVICIO)
        cliente = self._cliente(cliente_id)
        placa_normalizada = str(placa or "").strip().upper()
        vehiculo = next((v for v in self.repos.vehiculos.listar() if v.placa == placa_normalizada), None)
        if vehiculo is None:
            vehiculo = Vehiculo(uuid4().hex[:12], cliente.id, placa, marca, modelo, vin)
            self.repos.vehiculos.guardar(vehiculo)
        elif vehiculo.cliente_id != cliente.id:
            raise DatosIncompletos("Esa placa ya está registrada a nombre de otro cliente.")
        try:
            km = int(kilometraje)
        except (TypeError, ValueError) as exc:
            raise DatosIncompletos("El kilometraje debe ser un número entero.") from exc
        inspeccion = InspeccionDeIngreso(km, nivel_combustible, danos_visibles, motivo_ingreso)
        ahora = self.reloj.ahora()
        folio = f"OS-{len(self.repos.ordenes.listar()) + 1:04d}"
        orden = OrdenDeServicio.registrar_ingreso(
            folio=folio,
            cliente_id=cliente.id,
            vehiculo_id=vehiculo.id,
            inspeccion=inspeccion,
            cargo_diagnostico=Monto.de(cargo_diagnostico or 0),
            cargo_diagnostico_aceptado=bool(cargo_diagnostico_aceptado),
            ahora=ahora,
        )
        if foto_ingreso:
            orden.registrar_evidencia_fotografica(
                EvidenciaFotografica(EtapaEvidencia.INGRESO, foto_ingreso, usuario.nombre, ahora)
            )
        self._guardar(orden)
        return orden


class RegistrarDiagnosticoService(_ServicioBase):
    def registrar(self, usuario: Usuario, orden_id: str, falla_encontrada: str) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.TECNICO)
        orden = self._orden(orden_id)
        orden.registrar_diagnostico(
            tecnico_id=usuario.id,
            tecnico_nombre=usuario.nombre,
            falla_encontrada=falla_encontrada,
            ahora=self.reloj.ahora(),
        )
        self._guardar(orden)
        return orden


class GenerarCotizacionService(_ServicioBase):
    def generar_y_enviar(self, usuario: Usuario, orden_id: str, lineas: list[dict]) -> Cotizacion:
        requerir_rol(usuario, Rol.ASESOR_DE_SERVICIO)
        orden = self._orden(orden_id)
        ahora = self.reloj.ahora()
        cotizacion = orden.generar_cotizacion(lineas=lineas, ahora=ahora)
        orden.enviar_cotizacion(cotizacion.id, ahora)
        self._guardar(orden)
        self._avisar_cliente(
            orden,
            f"Tu cotización de la orden {orden.folio} por {cotizacion.total} está lista "
            "para que la revises y la autorices.",
        )
        return cotizacion


class AutorizarTrabajosService(_ServicioBase):
    """Punto único de la autorización digital para particulares y flotillas (ADR-003)."""

    def _validar_autorizador(self, usuario: Usuario, orden: OrdenDeServicio) -> None:
        cliente = self._cliente(orden.cliente_id)
        if not AutorizadorValidoSpecification().es_satisfecha_por(CandidatoAutorizador(usuario, cliente)):
            raise AutorizadorNoValido(
                "Solo el cliente titular o un responsable de cuenta registrado puede decidir esta cotización."
            )

    def autorizar_trabajos(self, comando: AutorizarTrabajosCommand) -> RegistroDeAutorizacion:
        orden = self._orden(comando.orden_id)
        self._validar_autorizador(comando.usuario, orden)
        registro = self._registro(
            comando.usuario,
            comando.trabajos_autorizados,
            comando.trabajos_rechazados,
            comando.referencia_evidencia_digital,
        )
        orden.registrar_decision(cotizacion_id=comando.cotizacion_id, registro=registro)
        self._guardar(orden)
        return registro

    def decidir_ampliacion(
        self,
        usuario: Usuario,
        orden_id: str,
        trabajo_id: str,
        ampliacion_id: str,
        autoriza: bool,
        referencia_evidencia_digital: str,
    ) -> RegistroDeAutorizacion:
        orden = self._orden(orden_id)
        self._validar_autorizador(usuario, orden)
        registro = self._registro(
            usuario, [trabajo_id] if autoriza else [], [] if autoriza else [trabajo_id], referencia_evidencia_digital
        )
        orden.registrar_decision_de_ampliacion(
            trabajo_id=trabajo_id, ampliacion_id=ampliacion_id, autoriza=autoriza, registro=registro
        )
        self._guardar(orden)
        return registro


# ---------------------------------------------------------------------- CU-02
class ReportarFallaAdicionalService(_ServicioBase):
    def reportar(self, comando: ReportarFallaAdicionalCommand) -> OrdenDeServicio:
        requerir_rol(comando.usuario, Rol.TECNICO)
        orden = self._orden(comando.orden_id)
        orden.reportar_falla_adicional(descripcion=comando.descripcion, ahora=self.reloj.ahora())
        self._guardar(orden)
        return orden

    def generar_cotizacion_complementaria(self, usuario: Usuario, orden_id: str, lineas: list[dict]) -> Cotizacion:
        requerir_rol(usuario, Rol.ASESOR_DE_SERVICIO)
        orden = self._orden(orden_id)
        cotizacion = orden.generar_cotizacion_complementaria(
            lineas=lineas, politica=PoliticaAutorizacionEstandar(), ahora=self.reloj.ahora()
        )
        self._guardar(orden)
        self._avisar_cliente(
            orden,
            f"Se encontró una falla adicional en la orden {orden.folio}. Revisa la "
            f"cotización complementaria por {cotizacion.total}.",
        )
        return cotizacion


class SolicitarReautorizacionDeAmpliacionService(_ServicioBase):
    def solicitar(self, usuario: Usuario, orden_id: str, trabajo_id: str, monto: str, motivo: str):
        requerir_rol(usuario, Rol.ASESOR_DE_SERVICIO)
        orden = self._orden(orden_id)
        ampliacion = orden.solicitar_ampliacion(
            trabajo_id=trabajo_id,
            monto=Monto.de(monto or 0),
            motivo=motivo,
            politica=PoliticaAutorizacionAmpliacion(),
            ahora=self.reloj.ahora(),
        )
        self._guardar(orden)
        if ampliacion.fecha_hora_envio is not None:
            self._avisar_cliente(
                orden, f"La orden {orden.folio} necesita tu autorización para una ampliación de {ampliacion.monto}."
            )
        return ampliacion


# ---------------------------------------------------------------------- CU-03
class MarcarEsperaDeRefaccionService(_ServicioBase):
    def confirmar_falta_de_existencia(
        self, usuario: Usuario, orden_id: str, trabajo_id: str, codigo_refaccion: str, proveedor: str
    ) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.COMPRAS)
        orden = self._orden(orden_id)
        orden.confirmar_falta_de_existencia(
            trabajo_id=trabajo_id, codigo_refaccion=codigo_refaccion, proveedor=proveedor, ahora=self.reloj.ahora()
        )
        self._guardar(orden)
        return orden


class SolicitarRefaccionAProveedorService(_ServicioBase):
    def al_detectar_refaccion_sin_existencia(self, evento: EventoDeDominio) -> OrdenDeCompra | None:
        trabajo_id = evento.datos["trabajo_id"]
        abierta = next(
            (
                oc
                for oc in self.repos.ordenes_de_compra.listar()
                if oc.trabajo_id == trabajo_id
                and oc.estado == EstadoOrdenDeCompra.SOLICITADA
                and oc.codigo_refaccion == evento.datos["codigo_refaccion"]
            ),
            None,
        )
        if abierta is not None:
            return None  # idempotente (ADR-010)
        orden_de_compra = OrdenDeCompra.solicitar(
            orden_de_servicio_id=evento.agregado_id,
            trabajo_id=trabajo_id,
            codigo_refaccion=evento.datos["codigo_refaccion"],
            proveedor=evento.datos["proveedor"],
            ahora=self.reloj.ahora(),
        )
        self.repos.ordenes_de_compra.guardar(orden_de_compra)
        return orden_de_compra


class NotificarNuevaFechaEntregaService(_ServicioBase):
    def notificar(self, usuario: Usuario, orden_id: str, nueva_fecha: str, motivo: str) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.ASESOR_DE_SERVICIO)
        try:
            fecha = date.fromisoformat(str(nueva_fecha))
        except ValueError as exc:
            raise DatosIncompletos("Selecciona una fecha válida.") from exc
        orden = self._orden(orden_id)
        ahora = self.reloj.ahora()
        orden.notificar_nueva_fecha(nueva_fecha=fecha, motivo=motivo, hoy=ahora.date(), ahora=ahora)
        self._guardar(orden)
        self._avisar_cliente(
            orden,
            f"Tu vehículo (orden {orden.folio}) espera una refacción. Nueva fecha estimada "
            f"de entrega: {fecha:%d/%m/%Y}. Motivo: {orden.motivo_retraso}.",
        )
        return orden


class RegistrarRecepcionDeRefaccionService(_ServicioBase):
    def registrar_recepcion(self, usuario: Usuario, orden_de_compra_id: str) -> OrdenDeCompra:
        requerir_rol(usuario, Rol.COMPRAS)
        orden_de_compra = self.repos.ordenes_de_compra.obtener_por_id(orden_de_compra_id)
        if orden_de_compra is None:
            raise RecursoNoEncontrado("No se encontró la orden de compra.")
        orden_de_compra.registrar_recepcion(self.reloj.ahora())
        eventos = orden_de_compra.extraer_eventos()
        self.repos.ordenes_de_compra.guardar(orden_de_compra)
        self.despachador.publicar(eventos)
        return orden_de_compra


class ReanudarReparacionService(_ServicioBase):
    def al_recibir_refaccion(self, evento: EventoDeDominio) -> None:
        orden = self._orden(evento.datos["orden_de_servicio_id"])
        if orden.reanudar_reparacion(
            trabajo_id=evento.datos["trabajo_id"],
            codigo_refaccion=evento.datos["codigo_refaccion"],
            ahora=self.reloj.ahora(),
        ):
            self._guardar(orden)
            self._avisar_cliente(
                orden, f"Llegó la refacción de tu vehículo (orden {orden.folio}); el trabajo continúa."
            )


# ---------------------------------------------------------------------- CU-04
class EjecutarTrabajoService(_ServicioBase):
    def iniciar(self, usuario: Usuario, orden_id: str, trabajo_id: str) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.TECNICO)
        orden = self._orden(orden_id)
        orden.iniciar_trabajo(trabajo_id=trabajo_id, ahora=self.reloj.ahora())
        self._guardar(orden)
        return orden

    def terminar(self, usuario: Usuario, orden_id: str, trabajo_id: str) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.TECNICO)
        orden = self._orden(orden_id)
        orden.terminar_trabajo(trabajo_id=trabajo_id, ahora=self.reloj.ahora())
        self._guardar(orden)
        if orden.estado == EstadoOrden.LISTO_PARA_ENTREGA:
            self._avisar_cliente(orden, f"Tu vehículo (orden {orden.folio}) está listo para entrega.")
        return orden


class RegistrarEvidenciaFotograficaService(_ServicioBase):
    def registrar(self, usuario: Usuario, orden_id: str, etapa: str, referencia_archivo: str) -> OrdenDeServicio:
        requerir_rol(usuario, Rol.ASESOR_DE_SERVICIO)
        orden = self._orden(orden_id)
        orden.registrar_evidencia_fotografica(
            EvidenciaFotografica(EtapaEvidencia(etapa), referencia_archivo, usuario.nombre, self.reloj.ahora())
        )
        self._guardar(orden)
        return orden


class CerrarOrdenDeServicioService(_ServicioBase):
    def cerrar(self, comando: CerrarOrdenDeServicioCommand) -> OrdenDeServicio:
        requerir_rol(comando.usuario, Rol.CAJA)
        orden = self._orden(comando.orden_id)
        cliente = self._cliente(orden.cliente_id)
        orden.cerrar(
            pago=Monto.de(comando.pago or 0), es_flotilla=cliente.tipo == TipoCliente.FLOTILLA, ahora=self.reloj.ahora()
        )
        self._guardar(orden)
        return orden


# ---------------------------------------------------------------------- CU-05
class GenerarFacturacionConsolidadaService(_ServicioBase):
    def generar(self, usuario: Usuario, cliente_id: str, periodo: str) -> FacturacionConsolidada:
        requerir_rol(usuario, Rol.CAJA)
        cliente = self._cliente(cliente_id)
        if not isinstance(cliente, ClienteFlotilla):
            raise DatosIncompletos("La facturación consolidada solo aplica a clientes de flotilla.")
        ya_facturadas = frozenset(o for f in self.repos.facturaciones.listar() for o in f.ordenes_de_servicio)
        facturacion = FacturacionConsolidada.generar(
            cliente=cliente,
            periodo=str(periodo or "").strip(),
            ordenes=self.repos.ordenes.listar(),
            ordenes_ya_facturadas=ya_facturadas,
            ahora=self.reloj.ahora(),
        )
        self.repos.facturaciones.guardar(facturacion)
        return facturacion


# ---------------------------------------------------------------------- CU-06
class ProcesarPlazosDeRespuestaService(_ServicioBase):
    def __init__(self, *args, plazo_horas: int = 24, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.escalamiento = ServicioDeEscalamiento(timedelta(hours=plazo_horas))

    def procesar(self, usuario: Usuario) -> list[OrdenDeServicio]:
        requerir_rol(usuario, Rol.GERENTE_DEL_TALLER)
        escaladas = self.escalamiento.procesar(self.repos.ordenes.listar(), self.reloj.ahora())
        for orden in escaladas:
            self._guardar(orden)
            if self.notificacion_gerente is not None:
                self.notificacion_gerente.notificar_gerente(
                    orden.id, f"La orden {orden.folio} pasó a «En espera de cliente»: 24 horas sin respuesta."
                )
        return escaladas


# ---------------------------------------------------------------------- CU-07
class RegistrarDisputaService(_ServicioBase):
    def registrar(self, usuario: Usuario, orden_id: str, categoria: str, descripcion: str) -> Disputa:
        requerir_rol(usuario, Rol.CLIENTE_TITULAR, Rol.RESPONSABLE_DE_CUENTA)
        orden = self._orden(orden_id)
        if not self._cliente(orden.cliente_id).validar_autorizador(usuario):
            raise AutorizadorNoValido("Solo puedes registrar disputas sobre tus propias órdenes.")
        try:
            categoria_disputa = CategoriaDisputa(categoria)
        except ValueError as exc:
            raise DatosIncompletos("Elige si la disputa es de «Autorización» o de «Cobro».") from exc
        disputa = Disputa.registrar(
            orden_de_servicio_id=orden.id,
            cliente_id=orden.cliente_id,
            categoria=categoria_disputa,
            descripcion=descripcion,
            ahora=self.reloj.ahora(),
        )
        self.repos.disputas.guardar(disputa)
        if self.notificacion_gerente is not None:
            self.notificacion_gerente.notificar_gerente(
                orden.id, f"Nueva disputa de {categoria_disputa.lower()} en la orden {orden.folio}."
            )
        return disputa


class ResolverDisputaService(_ServicioBase):
    def resolver(self, usuario: Usuario, disputa_id: str, resolucion: str) -> Disputa:
        requerir_rol(usuario, Rol.GERENTE_DEL_TALLER)
        disputa = self.repos.disputas.obtener_por_id(disputa_id)
        if disputa is None:
            raise RecursoNoEncontrado("No se encontró la disputa.")
        disputa.resolver(resolucion, self.reloj.ahora())
        self.repos.disputas.guardar(disputa)
        return disputa
