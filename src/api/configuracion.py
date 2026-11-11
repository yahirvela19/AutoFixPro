"""Configuración por variables de entorno (12-Factor) e identidades de demostración (ADR-012)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.domain.estados import Rol
from src.domain.value_objects import Usuario

TOKENS_POR_DEFECTO = (
    "asesor-demo:ASE-001:Laura Méndez:ASESOR_DE_SERVICIO,"
    "tecnico-demo:TEC-001:Jorge Salinas:TECNICO,"
    "compras-demo:COM-001:Rosa Treviño:COMPRAS,"
    "caja-demo:CAJ-001:Miguel Garza:CAJA,"
    "gerente-demo:GER-001:Patricia Leal:GERENTE_DEL_TALLER,"
    "cliente-demo:CLI-001:Ana López:CLIENTE_TITULAR,"
    "cliente2-demo:CLI-002:Carlos Ramírez:CLIENTE_TITULAR,"
    "flotilla-demo:RESP-001:Daniel Ortiz:RESPONSABLE_DE_CUENTA,"
    "flotilla2-demo:RESP-002:Mariana Cantú:RESPONSABLE_DE_CUENTA"
)


def _cargar_env_local(ruta: str = ".env") -> None:
    """Carga un .env local sin sobrescribir variables existentes (solo desarrollo)."""
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                os.environ.setdefault(clave.strip(), valor.strip())


def leer_tokens(texto: str) -> dict[str, Usuario]:
    tokens: dict[str, Usuario] = {}
    for entrada in filter(None, (e.strip() for e in texto.split(","))):
        token, usuario_id, nombre, rol = entrada.split(":")
        tokens[token] = Usuario(usuario_id, nombre, Rol[rol])
    return tokens


@dataclass
class Configuracion:
    database_url: str = "sqlite:///./autofixpro.db"
    cargar_datos_demo: bool = True
    plazo_de_respuesta_horas: int = 24
    tokens: dict[str, Usuario] = field(default_factory=lambda: leer_tokens(TOKENS_POR_DEFECTO))

    @classmethod
    def desde_entorno(cls) -> Configuracion:
        _cargar_env_local()
        url = os.environ.get("DATABASE_URL", cls.database_url)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return cls(
            database_url=url,
            cargar_datos_demo=os.environ.get("CARGAR_DATOS_DEMO", "true").lower() in ("1", "true", "si", "sí"),
            plazo_de_respuesta_horas=int(os.environ.get("PLAZO_DE_RESPUESTA_HORAS", "24")),
            tokens=leer_tokens(os.environ.get("TOKENS_DEMO", TOKENS_POR_DEFECTO)),
        )
