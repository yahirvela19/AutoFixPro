"""Pruebas de la interfaz web: flujo completo por roles y reglas de usabilidad (ADR-014)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.api.configuracion import Configuracion
from src.api.main import crear_app


@pytest.fixture
def web():
    with TestClient(crear_app(Configuracion(database_url="sqlite://"))) as cliente:
        yield cliente


def entrar(web, token):
    web.post("/sesion", data={"token": token})


def aviso(respuesta) -> str:
    texto = re.search(r'class="aviso[^"]*"[^>]*>(.*?)</div>', respuesta.text, re.S)
    return re.sub(r"<[^>]+>", "", texto.group(1)).strip() if texto else ""


def sin_codigo(html: str) -> bool:
    """La interfaz no muestra JSON, trazas ni identificadores técnicos al usuario."""
    visible = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S))
    return not any(marca in visible for marca in ("Traceback", '{"', "None", "__", "Exception"))


def test_web_pide_elegir_rol_y_muestra_menu_por_rol(web):
    r = web.get("/")
    assert "Elige" in r.text or "elige" in r.text
    entrar(web, "caja-demo")
    r = web.get("/")
    assert "Facturación consolidada" in r.text and "Nueva orden" not in r.text
    r = web.get("/ordenes/nueva", follow_redirects=True)
    assert "Asesor de Servicio" in aviso(r)
    assert web.get("/salir", follow_redirects=True).status_code == 200


def test_web_sin_sesion_redirige_con_mensaje(web):
    r = web.post("/ordenes/x/diagnostico", data={"falla": "x"}, follow_redirects=True)
    assert "Elige tu rol" in aviso(r)


def test_web_flujo_completo_por_roles_sin_mostrar_codigo(web):
    entrar(web, "asesor-demo")
    r = web.post(
        "/ordenes",
        data={
            "cliente_id": "CLI-001",
            "placa": "WEB-001-A",
            "marca": "Kia",
            "modelo": "Rio 2022",
            "vin": "KNADN5A3XN1234567",
            "kilometraje": "21000",
            "nivel_combustible": "3/4",
            "motivo_ingreso": "Servicio",
            "danos_visibles": "",
            "cargo_diagnostico": "0",
        },
        files={"foto": ("frente.jpg", b"imagen", "image/jpeg")},
        follow_redirects=True,
    )
    assert "quedó en «Recibido»" in aviso(r)
    orden_url = str(r.url).split("?")[0]
    assert sin_codigo(r.text) and "frente.jpg" in r.text

    entrar(web, "tecnico-demo")
    r = web.get(orden_url)
    assert "Registrar diagnóstico" in r.text and "Enviar cotización" not in r.text
    r = web.post(orden_url + "/diagnostico", data={"falla": "Bujías desgastadas"}, follow_redirects=True)
    assert "Diagnosticado" in aviso(r)

    entrar(web, "asesor-demo")
    r = web.post(
        orden_url + "/cotizacion",
        data={
            "descripcion_1": "Cambio de bujías",
            "cantidad_1": "4",
            "precio_1": "150",
            "descripcion_2": "Limpieza de inyectores",
            "cantidad_2": "1",
            "precio_2": "800",
        },
        follow_redirects=True,
    )
    assert "En espera de autorización" in aviso(r)

    entrar(web, "cliente2-demo")
    assert "No tienes acceso" in aviso(web.get(orden_url, follow_redirects=True))

    entrar(web, "cliente-demo")
    r = web.get(orden_url)
    assert "Autorización digital" in r.text and sin_codigo(r.text)
    ids = re.findall(r'name="decision_([0-9a-f]{12})"', r.text)
    accion = re.search(r'action="(/ordenes/[0-9a-f]+/cotizaciones/[0-9a-f]+/autorizacion)"', r.text).group(1)
    r = web.post(
        accion, data={f"decision_{ids[0]}": "autorizar", f"decision_{ids[2]}": "rechazar"}, follow_redirects=True
    )
    assert "Confirma tu decisión" in aviso(r) or "confirma tu decisión" in aviso(r)
    r = web.post(
        accion,
        data={f"decision_{ids[0]}": "autorizar", f"decision_{ids[2]}": "rechazar", "confirmo": "si"},
        follow_redirects=True,
    )
    assert "evidencia digital" in aviso(r)
    assert "Registro de autorización: Ana López" in r.text

    entrar(web, "tecnico-demo")
    r = web.get(orden_url)
    assert r.text.count("Iniciar trabajo") == 1
    iniciar = re.search(r'action="([^"]+/iniciar)"', r.text).group(1)
    web.post(iniciar, follow_redirects=True)
    terminar = re.search(r'action="([^"]+/terminar)"', web.get(orden_url).text).group(1)
    r = web.post(terminar, follow_redirects=True)
    assert "Listo para entrega" in r.text

    entrar(web, "asesor-demo")
    r = web.post(
        orden_url + "/evidencia",
        data={"etapa": "Entrega"},
        files={"foto": ("salida.jpg", b"img", "image/jpeg")},
        follow_redirects=True,
    )
    assert "Evidencia fotográfica registrada" in aviso(r)

    entrar(web, "caja-demo")
    r = web.get(orden_url)
    assert (
        "Cierre de caja" in r.text
        and "$600.00 MXN" in r.text
        and "Limpieza de inyectores" not in r.text.split("Cierre de caja")[1].split("</form>")[0]
    )
    r = web.post(orden_url + "/cierre", data={"pago": "10"}, follow_redirects=True)
    assert "insuficiente" in aviso(r)
    r = web.post(orden_url + "/cierre", data={"pago": "600"}, follow_redirects=True)
    assert "se cerró" in aviso(r) and sin_codigo(r.text)

    entrar(web, "cliente-demo")
    r = web.post(
        orden_url + "/disputa", data={"categoria": "Cobro", "descripcion": "Revisar cobro"}, follow_redirects=True
    )
    assert "disputa quedó registrada" in aviso(r)
    entrar(web, "gerente-demo")
    r = web.get("/disputas")
    resolver = re.search(r'action="(/disputas/[0-9a-f]+/resolucion)"', r.text).group(1)
    r = web.post(resolver, data={"resolucion": "Cobro correcto"}, follow_redirects=True)
    assert "Resuelta" in aviso(r)


def test_web_pantallas_de_compras_caja_gerente_y_cola(web):
    entrar(web, "flotilla-demo")
    r = web.get("/")
    hilux = re.findall(r'href="(/ordenes/[0-9a-f]{12})"', r.text)
    entrar(web, "compras-demo")
    for url in hilux:
        pagina = web.get(url).text
        if "Refacción sin existencia" in pagina:
            accion = re.search(r'action="([^"]+/falta-de-refaccion)"', pagina).group(1)
            r = web.post(accion, data={"codigo": "FA-220", "proveedor": "Filtros MX"}, follow_redirects=True)
            assert "En espera de refacción" in aviso(r)
            break
    r = web.get("/compras")
    recepcion = re.search(r'action="(/ordenes-de-compra/[0-9a-f]+/recepcion)"', r.text).group(1)
    r = web.post(recepcion, data={"volver": "/compras"}, follow_redirects=True)
    assert "Refacción recibida" in aviso(r)

    entrar(web, "caja-demo")
    r = web.post("/caja/facturacion", data={"cliente_id": "FLO-001", "periodo": "2026-01"}, follow_redirects=True)
    assert "No hay órdenes" in aviso(r)

    entrar(web, "gerente-demo")
    r = web.get("/gerente")
    assert "Tiempo de comunicación de retraso" in r.text and sin_codigo(r.text)
    r = web.post("/gerente/plazos", follow_redirects=True)
    assert "24 horas" in aviso(r)
    assert "fechas válidas" in aviso(web.get("/gerente?desde=mal", follow_redirects=True))

    entrar(web, "asesor-demo")
    r = web.get("/cola")
    assert "Ana López" in r.text and "Carlos Ramírez" in r.text
    entrar(web, "caja-demo")
    assert "Asesor de Servicio" in aviso(web.get("/cola", follow_redirects=True))
