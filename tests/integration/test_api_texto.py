"""Respuestas en texto para Swagger (ADR-015): mensajes con identificadores para seguir el flujo."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.api.configuracion import Configuracion
from src.api.main import crear_app


@pytest.fixture
def api():
    with TestClient(crear_app(Configuracion(database_url="sqlite://"))) as cliente:
        yield cliente


def texto(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "text/plain"}


def identificador(mensaje: str, nombre: str) -> str:
    encontrado = re.search(rf"• {re.escape(nombre)}[^:\n]*: ([0-9a-f]{{12}})", mensaje)
    assert encontrado, f"No se encontró «{nombre}» en:\n{mensaje}"
    return encontrado.group(1)


def sin_json(mensaje: str) -> bool:
    return "{" not in mensaje and "}" not in mensaje and '"' not in mensaje


INGRESO = {
    "cliente_id": "CLI-001",
    "placa": "TXT-001-A",
    "marca": "Mazda",
    "modelo": "3 2020",
    "vin": "JM1BPAMM1L1123456",
    "kilometraje": 45000,
    "nivel_combustible": "1/2",
    "motivo_ingreso": "Vibración al frenar",
    "cargo_diagnostico": "300",
    "cargo_diagnostico_aceptado": True,
}


def test_flujo_completo_en_texto_siguiendo_los_identificadores(api):
    r = api.post("/api/v1/ordenes-de-servicio", json=INGRESO, headers=texto("asesor-demo"))
    assert r.status_code == 201 and r.headers["content-type"].startswith("text/plain")
    assert "quedó en «Recibido»" in r.text and sin_json(r.text)
    orden_id = identificador(r.text, "orden_id")

    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/diagnostico",
        json={"falla_encontrada": "Discos dañados"},
        headers=texto("tecnico-demo"),
    )
    assert "pasó a «Diagnosticado»" in r.text

    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cotizaciones",
        headers=texto("asesor-demo"),
        json={
            "trabajos": [
                {"descripcion": "Cambio de balatas", "cantidad": 1, "precio_unitario": "1200"},
                {"descripcion": "Lavado de motor", "cantidad": 1, "precio_unitario": "250"},
            ]
        },
    )
    assert r.status_code == 201 and "$1,450.00 MXN" in r.text and sin_json(r.text)
    cotizacion_id = identificador(r.text, "cotizacion_id")
    balatas = identificador(r.text, "trabajo_id de «Cambio de balatas»")
    lavado = identificador(r.text, "trabajo_id de «Lavado de motor»")

    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cotizaciones/{cotizacion_id}/autorizacion-digital",
        headers=texto("cliente-demo"),
        json={
            "trabajos_autorizados": [balatas],
            "trabajos_rechazados": [lavado],
            "referencia_evidencia_digital": "Firma",
        },
    )
    assert "Autorizado: Cambio de balatas. Rechazado: Lavado de motor." in r.text
    assert "quedó «En reparación»" in r.text
    assert identificador(r.text, "trabajo_id ejecutable «Cambio de balatas»") == balatas

    r = api.get(f"/api/v1/ordenes-de-servicio/{orden_id}/trabajos?ejecutables=true", headers=texto("tecnico-demo"))
    assert "Trabajos ejecutables" in r.text and "Lavado" not in r.text
    api.post(f"/api/v1/ordenes-de-servicio/{orden_id}/trabajos/{balatas}/inicio", headers=texto("tecnico-demo"))
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/trabajos/{balatas}/terminacion", headers=texto("tecnico-demo")
    )
    assert "listo para entrega" in r.text

    r = api.get(f"/api/v1/ordenes-de-servicio/{orden_id}/detalle-para-cobro", headers=texto("caja-demo"))
    assert "Total a cobrar: $1,500.00 MXN" in r.text and "Lavado" not in r.text
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cierre-de-caja", json={"pago": "1500"}, headers=texto("caja-demo")
    )
    assert "quedó «Cerrado»" in r.text and sin_json(r.text)

    r = api.get(f"/api/v1/ordenes-de-servicio/{orden_id}", headers=texto("cliente-demo"))
    assert r.text.startswith("Orden ") and "«Cerrado»" in r.text


def test_errores_en_texto_con_su_codigo(api):
    r = api.post("/api/v1/ordenes-de-servicio", json=INGRESO, headers=texto("tecnico-demo"))
    assert r.status_code == 403 and r.text.startswith("No se pudo completar la acción:")
    r = api.get("/api/v1/ordenes-de-servicio", headers={"Accept": "text/plain"})
    assert r.status_code == 401 and "token" in r.text and sin_json(r.text)
    r = api.post("/api/v1/ordenes-de-servicio", json={"cliente_id": "CLI-001"}, headers=texto("asesor-demo"))
    assert r.status_code == 422 and "Revisa los datos enviados" in r.text and sin_json(r.text)


def test_flotilla_ampliacion_refaccion_y_consultas_en_texto(api):
    lista = api.get("/api/v1/ordenes-de-servicio", headers=texto("flotilla-demo")).text
    hilux = re.search(r"Toyota Hilux 2020 · NLE-118-D · «En reparación» — orden_id: ([0-9a-f]{12})", lista).group(1)
    estado = api.get(f"/api/v1/ordenes-de-servicio/{hilux}", headers=texto("asesor-demo")).text
    aceite = identificador(estado, "trabajo_id de «Cambio de aceite sintético»")
    filtro = identificador(estado, "trabajo_id de «Cambio de filtro de aire»")

    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux}/trabajos/{aceite}/ampliaciones",
        headers=texto("asesor-demo"),
        json={"monto": "500", "motivo": "Aceite adicional"},
    )
    assert "supera el 20 %" in r.text and "En espera de autorización" in r.text
    ampliacion_id = identificador(r.text, "ampliacion_id")
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux}/trabajos/{aceite}/ampliaciones/{ampliacion_id}/autorizacion-digital",
        headers=texto("flotilla-demo"),
        json={"autoriza": True, "referencia_evidencia_digital": "Firma"},
    )
    assert "quedó «Autorizada»" in r.text

    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux}/trabajos/{filtro}/necesidad-de-refaccion",
        headers=texto("compras-demo"),
        json={"codigo_refaccion": "FA-220", "proveedor": "Filtros MX"},
    )
    assert "«En espera de refacción»" in r.text
    orden_de_compra_id = identificador(r.text, "orden_de_compra_id")
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux}/nueva-fecha-de-entrega",
        headers=texto("asesor-demo"),
        json={"nueva_fecha": "2099-01-15", "motivo": "Llega el lunes"},
    )
    assert "15/01/2099" in r.text
    assert orden_de_compra_id in api.get("/api/v1/ordenes-de-compra", headers=texto("compras-demo")).text
    r = api.post(
        f"/api/v1/ordenes-de-compra/{orden_de_compra_id}/recepcion-de-refaccion", headers=texto("compras-demo")
    )
    assert "quedó «Recibida»" in r.text and "el trabajo continúa" in r.text

    assert api.get("/api/v1/cola-de-atencion", headers=texto("asesor-demo")).text.startswith("Cola de atención")
    plazos = api.post("/api/v1/plazos-de-respuesta/procesamiento", headers=texto("gerente-demo"))
    assert plazos.text == "No hay solicitudes con 24 horas o más sin respuesta."
    r = api.post(
        "/api/v1/disputas",
        headers=texto("flotilla-demo"),
        json={"orden_id": hilux, "categoria": "Cobro", "descripcion": "Revisar ampliación"},
    )
    disputa_id = identificador(r.text, "disputa_id")
    assert disputa_id in api.get("/api/v1/disputas", headers=texto("gerente-demo")).text
    r = api.post(
        f"/api/v1/disputas/{disputa_id}/resolucion",
        headers=texto("gerente-demo"),
        json={"resolucion": "Ampliación autorizada por el responsable"},
    )
    assert "quedó «Resuelta»" in r.text
    r = api.get("/api/v1/indicadores?desde=2020-01-01&hasta=2099-12-31", headers=texto("gerente-demo"))
    assert r.text.startswith("Indicadores del periodo") and sin_json(r.text)


def test_sin_pedir_texto_la_api_sigue_respondiendo_json(api):
    r = api.get("/api/v1/ordenes-de-servicio", headers={"Authorization": "Bearer asesor-demo"})
    assert r.headers["content-type"].startswith("application/json") and isinstance(r.json(), list)
    r = api.get(
        "/api/v1/ordenes-de-servicio", headers={"Authorization": "Bearer asesor-demo", "Accept": "application/json"}
    )
    assert isinstance(r.json(), list)


def test_openapi_declara_texto_como_primer_formato(api):
    esquema = api.get("/api/openapi.json").json()
    respuestas = esquema["paths"]["/api/v1/ordenes-de-servicio"]["post"]["responses"]
    assert list(respuestas["201"]["content"])[0] == "text/plain"
    assert list(respuestas["409"]["content"])[0] == "text/plain"


def test_swagger_pide_texto_por_defecto(api):
    pagina = api.get("/docs")
    assert pagina.status_code == 200 and "SwaggerUIBundle" in pagina.text
    assert "requestInterceptor" in pagina.text and "'text/plain'" in pagina.text
