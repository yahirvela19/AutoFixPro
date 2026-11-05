"""Errores del dominio expresados en el lenguaje del negocio (Arquitectura §10)."""


class ErrorDeDominio(Exception):
    """Base de todos los errores del negocio; el mensaje se muestra al usuario."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class DatosIncompletos(ErrorDeDominio):
    """Faltan datos obligatorios o tienen un valor inválido."""


class AutorizadorNoValido(ErrorDeDominio):
    """El usuario no es el cliente titular ni un responsable de cuenta registrado (RN-02)."""


class RolNoPermitido(ErrorDeDominio):
    """El rol del usuario no puede realizar la acción."""


class TransicionNoPermitida(ErrorDeDominio):
    """La máquina de estados no permite el cambio solicitado (ADR-006)."""


class DecisionYaRegistrada(ErrorDeDominio):
    """La cotización o ampliación ya tiene una decisión registrada (RN-04)."""


class RecursoNoEncontrado(ErrorDeDominio):
    """No existe el elemento solicitado."""
