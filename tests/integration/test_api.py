"""Pruebas de integración de la API REST con SQLite en memoria (ADR-008, ADR-009)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from src.api.configuracion import Configuracion
from src.api.main import crear_app

URL_PRUEBAS = os.environ.get("TEST_DATABASE_URL", "sqlite://")


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api():
    app = crear_app(Configuracion(database_url=URL_PRUEBAS, cargar_datos_demo=True))
    with TestClient(app) as cliente:
        yield cliente
    if not URL_PRUEBAS.startswith("sqlite"):
        from src.infrastructure.persistencia import metadata

        metadata.drop_all(app.state.contenedor.repos.ordenes.motor)


INGRESO = {
    "cliente_id": "CLI-001",
    "placa": "API-100-A",
    "marca": "Mazda",
    "modelo": "3 2020",
    "vin": "JM1BPAMM1L1123456",
    "kilometraje": 45000,
    "nivel_combustible": "1/2",
    "motivo_ingreso": "Vibración al frenar",
    "cargo_diagnostico": "300",
    "cargo_diagnostico_aceptado": True,
}


def test_api_flujo_completo_de_una_orden_particular(api):
    r = api.post("/api/v1/ordenes-de-servicio", json=INGRESO, headers=h("asesor-demo"))
    assert r.status_code == 201 and r.json()["estado"] == "Recibido"
    orden_id = r.json()["id"]
    assert (
        api.post(
            f"/api/v1/ordenes-de-servicio/{orden_id}/diagnostico",
            json={"falla_encontrada": "Discos dañados"},
            headers=h("tecnico-demo"),
        ).json()["estado"]
        == "Diagnosticado"
    )
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cotizaciones",
        headers=h("asesor-demo"),
        json={
            "trabajos": [
                {"descripcion": "Rectificar discos", "cantidad": 2, "precio_unitario": "600"},
                {"descripcion": "Lavado de motor", "cantidad": 1, "precio_unitario": "250"},
            ]
        },
    )
    assert r.status_code == 201 and r.json()["estado"] == "En espera de autorización"
    cotizacion = r.json()["cotizaciones"][0]
    discos, lavado = (t["id"] for t in cotizacion["trabajos"])
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cotizaciones/{cotizacion['id']}/autorizacion-digital",
        headers=h("cliente-demo"),
        json={
            "trabajos_autorizados": [discos],
            "trabajos_rechazados": [lavado],
            "referencia_evidencia_digital": "Firma en portal",
        },
    )
    assert r.status_code == 200 and r.json()["estado"] == "En reparación"
    ejecutables = api.get(
        f"/api/v1/ordenes-de-servicio/{orden_id}/trabajos?ejecutables=true", headers=h("tecnico-demo")
    ).json()
    assert [t["id"] for t in ejecutables] == [discos]
    api.post(f"/api/v1/ordenes-de-servicio/{orden_id}/trabajos/{discos}/inicio", headers=h("tecnico-demo"))
    r = api.post(f"/api/v1/ordenes-de-servicio/{orden_id}/trabajos/{discos}/terminacion", headers=h("tecnico-demo"))
    assert r.json()["estado"] == "Listo para entrega"
    assert (
        api.post(
            f"/api/v1/ordenes-de-servicio/{orden_id}/evidencias-fotograficas",
            headers=h("asesor-demo"),
            json={"etapa": "Entrega", "referencia_archivo": "salida.jpg"},
        ).status_code
        == 201
    )
    cobro = api.get(f"/api/v1/ordenes-de-servicio/{orden_id}/detalle-para-cobro", headers=h("caja-demo")).json()
    assert cobro["total"] == "$1,500.00 MXN"
    assert (
        api.post(
            f"/api/v1/ordenes-de-servicio/{orden_id}/cierre-de-caja", json={"pago": "100"}, headers=h("caja-demo")
        ).status_code
        == 422
    )
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cierre-de-caja", json={"pago": "1500"}, headers=h("caja-demo")
    )
    assert r.json()["estado"] == "Cerrado"


def test_api_errores_del_negocio_con_codigos_http(api):
    assert api.get("/api/v1/ordenes-de-servicio").status_code == 401
    assert api.get("/api/v1/ordenes-de-servicio", headers=h("token-falso")).status_code == 401
    r = api.post("/api/v1/ordenes-de-servicio", json=INGRESO, headers=h("tecnico-demo"))
    assert r.status_code == 403 and "Asesor de Servicio" in r.json()["detalle"]
    orden_id = api.post("/api/v1/ordenes-de-servicio", json=INGRESO, headers=h("asesor-demo")).json()["id"]
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{orden_id}/cotizaciones",
        headers=h("asesor-demo"),
        json={"trabajos": [{"descripcion": "X", "precio_unitario": "10"}]},
    )
    assert r.status_code == 409
    assert api.get("/api/v1/ordenes-de-servicio/no-existe", headers=h("asesor-demo")).status_code == 404
    assert api.get(f"/api/v1/ordenes-de-servicio/{orden_id}", headers=h("cliente2-demo")).status_code == 403
    r = api.post("/api/v1/ordenes-de-servicio", json={"cliente_id": "CLI-001"}, headers=h("asesor-demo"))
    assert r.status_code == 422 and "Revisa los datos" in r.json()["detalle"]


def test_api_flotilla_refaccion_y_facturacion(api):
    ordenes = api.get("/api/v1/ordenes-de-servicio", headers=h("flotilla-demo")).json()
    assert {o["cliente"] for o in ordenes} == {"Transportes del Norte"}
    hilux = next(o for o in ordenes if o["estado"] == "En reparación")
    vista = api.get(f"/api/v1/ordenes-de-servicio/{hilux['id']}", headers=h("flotilla-demo")).json()
    aceite, filtro = (t["id"] for t in vista["cotizaciones"][0]["trabajos"])
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux['id']}/trabajos/{filtro}/necesidad-de-refaccion",
        headers=h("compras-demo"),
        json={"codigo_refaccion": "FA-220", "proveedor": "Filtros MX"},
    )
    assert r.json()["estado"] == "En espera de refacción"
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux['id']}/nueva-fecha-de-entrega",
        headers=h("asesor-demo"),
        json={"nueva_fecha": "2099-01-15", "motivo": "El proveedor entrega mañana"},
    )
    assert r.json()["nueva_fecha_estimada"] == "15/01/2099"
    [orden_de_compra] = api.get("/api/v1/ordenes-de-compra", headers=h("compras-demo")).json()
    r = api.post(f"/api/v1/ordenes-de-compra/{orden_de_compra['id']}/recepcion-de-refaccion", headers=h("compras-demo"))
    assert r.json()["estado"] == "Recibida" and r.json()["orden_de_servicio"]["estado"] == "En reparación"
    for trabajo in (aceite, filtro):
        api.post(f"/api/v1/ordenes-de-servicio/{hilux['id']}/trabajos/{trabajo}/inicio", headers=h("tecnico-demo"))
        api.post(f"/api/v1/ordenes-de-servicio/{hilux['id']}/trabajos/{trabajo}/terminacion", headers=h("tecnico-demo"))
    r = api.post(f"/api/v1/ordenes-de-servicio/{hilux['id']}/cierre-de-caja", json={}, headers=h("caja-demo"))
    assert r.json()["estado"] == "Cerrado"
    periodo = r.json()["fecha_cierre"][6:10] + "-" + r.json()["fecha_cierre"][3:5]
    r = api.post(
        "/api/v1/facturaciones-consolidadas", json={"cliente_id": "FLO-001", "periodo": periodo}, headers=h("caja-demo")
    )
    assert r.status_code == 201 and r.json()["total"] == "$1,400.00 MXN"


def test_api_falla_adicional_ampliacion_cola_plazos_disputas_e_indicadores(api):
    ordenes = api.get("/api/v1/ordenes-de-servicio", headers=h("asesor-demo")).json()
    hilux = next(o for o in ordenes if o["estado"] == "En reparación")
    vista = api.get(f"/api/v1/ordenes-de-servicio/{hilux['id']}", headers=h("asesor-demo")).json()
    aceite = vista["cotizaciones"][0]["trabajos"][0]["id"]
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux['id']}/trabajos/{aceite}/ampliaciones",
        headers=h("asesor-demo"),
        json={"monto": "500", "motivo": "Aceite adicional"},
    )
    ampliacion = r.json()["cotizaciones"][0]["trabajos"][0]["ampliaciones"][0]
    assert r.json()["estado"] == "En espera de autorización" and ampliacion["estado"] == "Pendiente de autorización"
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux['id']}/trabajos/{aceite}/ampliaciones/{ampliacion['id']}"
        "/autorizacion-digital",
        headers=h("flotilla-demo"),
        json={"autoriza": True, "referencia_evidencia_digital": "Firma"},
    )
    assert r.json()["estado"] == "En reparación"
    assert (
        api.post(
            f"/api/v1/ordenes-de-servicio/{hilux['id']}/fallas-adicionales",
            headers=h("tecnico-demo"),
            json={"descripcion": "Banda desgastada"},
        ).status_code
        == 201
    )
    r = api.post(
        f"/api/v1/ordenes-de-servicio/{hilux['id']}/cotizaciones-complementarias",
        headers=h("asesor-demo"),
        json={"trabajos": [{"descripcion": "Cambio de banda", "precio_unitario": "700"}]},
    )
    assert r.json()["cotizaciones"][1]["tipo"] == "Complementaria"
    cola = api.get("/api/v1/cola-de-atencion", headers=h("asesor-demo")).json()
    assert [o["estado"] for o in cola] == ["Recibido", "Recibido"]
    assert api.post("/api/v1/plazos-de-respuesta/procesamiento", headers=h("gerente-demo")).json() == {
        "ordenes_escaladas": []
    }
    recibida = cola[0]["id"]
    assert (
        api.post(
            "/api/v1/disputas",
            headers=h("cliente-demo"),
            json={"orden_id": recibida, "categoria": "Cobro", "descripcion": "Duda sobre el diagnóstico"},
        ).status_code
        == 201
    )
    [disputa] = api.get("/api/v1/disputas", headers=h("gerente-demo")).json()
    r = api.post(
        f"/api/v1/disputas/{disputa['id']}/resolucion",
        headers=h("gerente-demo"),
        json={"resolucion": "Se explicó el cargo aceptado"},
    )
    assert r.json()["estado"] == "Resuelta"
    r = api.get("/api/v1/indicadores?desde=2020-01-01&hasta=2099-12-31", headers=h("gerente-demo"))
    assert r.status_code == 200 and r.json()["disputas_registradas"] == 1


def test_api_documentacion_openapi_activa(api):
    assert api.get("/docs").status_code == 200
    esquema = api.get("/api/openapi.json").json()
    assert (
        "/api/v1/ordenes-de-servicio/{orden_id}/cotizaciones/{cotizacion_id}/autorizacion-digital" in esquema["paths"]
    )
    assert api.get("/salud").json() == {"estado": "ok"}
