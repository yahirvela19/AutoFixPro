"""Aggregate Root Cliente y su especialización ClienteFlotilla (ADR-003)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.estados import Rol, TipoCliente
from src.domain.value_objects import Usuario


@dataclass
class Cliente:
    id: str
    nombre: str
    telefono: str = ""
    tipo: TipoCliente = TipoCliente.PARTICULAR

    def validar_autorizador(self, usuario: Usuario) -> bool:
        """Un cliente particular solo puede ser autorizado por su cliente titular."""
        return usuario.rol == Rol.CLIENTE_TITULAR and usuario.id == self.id

    def puede_consultar(self, usuario: Usuario) -> bool:
        return self.validar_autorizador(usuario)


@dataclass
class ClienteFlotilla(Cliente):
    responsables_de_cuenta: list[str] = field(default_factory=list)
    prioridad_contractual: bool = False
    tipo: TipoCliente = TipoCliente.FLOTILLA

    def validar_autorizador(self, usuario: Usuario) -> bool:
        """Una flotilla autoriza a través de sus responsables de cuenta registrados (RN-02, RN-12)."""
        return usuario.rol == Rol.RESPONSABLE_DE_CUENTA and usuario.id in self.responsables_de_cuenta
