"""Respuestas en texto para Swagger (ADR-015).

Cada función recibe los mismos datos que la API devuelve en JSON y arma un mensaje de confirmación en lenguaje del
negocio. Al final agrega «Para continuar en Swagger» con los identificadores necesarios para el siguiente paso,
nombrados igual que los parámetros de Swagger.
"""

from __future__ import annotations

from collections.abc import Iterable

TITULO_CONTINUAR = "Para continuar en Swagger:"


def _continuar(identificadores: Iterable[str]) -> str:
    lineas = [f"• {i}" for i in identificadores if i]
    return "\n\n" + TITULO_CONTINUAR + "\n" + "\n".join(lineas) if lineas else ""


def _orden(vista: dict) -> str:
    return f"orden {vista['folio']}"


def _trabajos(vista: dict) -> list[dict]:
    return [t for c in vista["cotizaciones"] for t in c["trabajos"]]


def _ids_trabajos(trabajos: Iterable[dict], prefijo: str = "trabajo_id de") -> list[str]:
    return [f"{prefijo} «{t['descripcion']}» ({t['estado']}): {t['id']}" for t in trabajos]


def error(mensaje: str) -> str:
    return f"No se pudo completar la acción: {mensaje}"


# ----------------------------------------------------------------- órdenes
def ingreso(vista: dict) -> str:
    texto = (
        f"Se registró el ingreso del vehículo {vista['vehiculo']['descripcion']} de {vista['cliente']['nombre']}.\n"
        f"La {_orden(vista)} quedó en «{vista['estado']}»."
    )
    if vista["evidencias"]:
        texto += f"\nEvidencia fotográfica de ingreso: {vista['evidencias'][-1]['archivo']}."
    return texto + _continuar([f"orden_id: {vista['id']}"])


def lista_de_ordenes(ordenes: list[dict]) -> str:
    if not ordenes:
        return "No hay órdenes de servicio que puedas consultar."
    lineas = [
        f"{n}. {o['folio']} · {o['cliente']} · {o['vehiculo']} · «{o['estado']}» — orden_id: {o['id']}"
        for n, o in enumerate(ordenes, 1)
    ]
    return f"Órdenes de servicio ({len(ordenes)}):\n" + "\n".join(lineas)


def estado_de_orden(vista: dict) -> str:
    lineas = [
        f"Orden {vista['folio']} · «{vista['estado']}»",
        f"Cliente: {vista['cliente']['nombre']} ({vista['cliente']['tipo']})",
        f"Vehículo: {vista['vehiculo']['descripcion']}",
        f"Ingreso: {vista['fecha_ingreso']}",
    ]
    if vista["diagnostico"]:
        lineas.append(f"Diagnóstico: {vista['diagnostico']['falla_encontrada']}")
    for c in vista["cotizaciones"]:
        pendiente = " · Pendiente de autorización" if c["pendiente"] else ""
        lineas.append(f"Cotización {c['tipo'].lower()} por {c['total']}{pendiente}")
        for t in c["trabajos"]:
            lineas.append(f"   - {t['descripcion']} (x{t['cantidad']}) {t['monto']} · «{t['estado']}»")
    if vista["nueva_fecha_estimada"]:
        lineas.append(f"Nueva fecha estimada de entrega: {vista['nueva_fecha_estimada']} ({vista['motivo_retraso']})")
    lineas.append(f"Total cobrable hasta ahora: {vista['total_cobrable']}")
    ids = [f"orden_id: {vista['id']}"]
    ids += [f"cotizacion_id pendiente: {c['id']}" for c in vista["cotizaciones"] if c["pendiente"]]
    ids += _ids_trabajos(_trabajos(vista))
    ids += [f"orden_de_compra_id «{oc['codigo']}» ({oc['estado']}): {oc['id']}" for oc in vista["ordenes_de_compra"]]
    return "\n".join(lineas) + _continuar(ids)


def evidencia(vista: dict) -> str:
    e = vista["evidencias"][-1]
    return (
        f"Se registró la evidencia fotográfica de {e['etapa'].lower()} ({e['archivo']}) en la {_orden(vista)}."
        + _continuar([f"orden_id: {vista['id']}"])
    )


def diagnostico(vista: dict) -> str:
    return (
        f"Se registró el diagnóstico de la {_orden(vista)}: {vista['diagnostico']['falla_encontrada']}.\n"
        f"La orden pasó a «{vista['estado']}»." + _continuar([f"orden_id: {vista['id']}"])
    )


def cotizacion(vista: dict) -> str:
    c = vista["cotizaciones"][-1]
    falla = f" por la falla adicional «{c['falla_adicional']}»" if c["falla_adicional"] else ""
    return (
        f"Se envió la cotización {c['tipo'].lower()}{falla} de la {_orden(vista)} por {c['total']}.\n"
        f"La orden quedó «{vista['estado']}» y se avisó al cliente."
        + _continuar(
            [f"orden_id: {vista['id']}", f"cotizacion_id: {c['id']}"]
            + [f"trabajo_id de «{t['descripcion']}» ({t['monto']}): {t['id']}" for t in c["trabajos"]]
        )
    )


def decision(vista: dict, cotizacion_id: str) -> str:
    c = next(x for x in vista["cotizaciones"] if x["id"] == cotizacion_id)
    r = c["registros"][-1]
    partes = []
    if r["autorizados"]:
        partes.append("Autorizado: " + ", ".join(r["autorizados"]) + ".")
    if r["rechazados"]:
        partes.append("Rechazado: " + ", ".join(r["rechazados"]) + ".")
    ejecutables = [t for t in _trabajos(vista) if t["estado"] == "Autorizado"]
    return (
        f"Se registró la decisión de {r['autorizador']} ({r['rol']}) el {r['fecha']}.\n"
        + " ".join(partes)
        + f"\nLa {_orden(vista)} quedó «{vista['estado']}»."
        + _continuar([f"orden_id: {vista['id']}"] + _ids_trabajos(ejecutables, "trabajo_id ejecutable"))
    )


def trabajos(vista: dict, lista: list[dict], solo_ejecutables: bool) -> str:
    titulo = "Trabajos ejecutables" if solo_ejecutables else "Trabajos"
    if not lista:
        return f"{titulo} de la {_orden(vista)}: ninguno por ahora." + _continuar([f"orden_id: {vista['id']}"])
    lineas = [f"{n}. {t['descripcion']} (x{t['cantidad']}) · «{t['estado']}»" for n, t in enumerate(lista, 1)]
    return (
        f"{titulo} de la {_orden(vista)} ({len(lista)}):\n"
        + "\n".join(lineas)
        + _continuar([f"orden_id: {vista['id']}"] + _ids_trabajos(lista))
    )


def trabajo(vista: dict, trabajo_id: str, accion: str) -> str:
    t = next(x for x in _trabajos(vista) if x["id"] == trabajo_id)
    texto = (
        f"{accion} el trabajo «{t['descripcion']}»; quedó «{t['estado']}». La {_orden(vista)} está «{vista['estado']}»."
    )
    ids = [f"orden_id: {vista['id']}"]
    if vista["estado"] == "Listo para entrega":
        texto += "\nTodos los trabajos autorizados terminaron: el vehículo está listo para entrega."
    else:
        ids.append(f"trabajo_id: {t['id']}")
    return texto + _continuar(ids)


def falla_adicional(vista: dict) -> str:
    return (
        f"Se reportó la falla adicional «{vista['fallas_por_cotizar'][-1]}» en la {_orden(vista)}.\n"
        "El Asesor de Servicio debe generar la cotización complementaria." + _continuar([f"orden_id: {vista['id']}"])
    )


def ampliacion(vista: dict, trabajo_id: str, ampliacion_id: str) -> str:
    t = next(x for x in _trabajos(vista) if x["id"] == trabajo_id)
    a = next(x for x in t["ampliaciones"] if x["id"] == ampliacion_id)
    if a["estado"] == "Pendiente de autorización":
        texto = (
            f"La ampliación de {a['monto']} en «{t['descripcion']}» supera el 20 % del total autorizado "
            f"y se envió al cliente para su autorización.\nLa {_orden(vista)} quedó «{vista['estado']}»."
        )
        ids = [f"orden_id: {vista['id']}", f"trabajo_id: {t['id']}", f"ampliacion_id: {a['id']}"]
    else:
        texto = (
            f"La ampliación de {a['monto']} en «{t['descripcion']}» no supera el 20 % del total autorizado "
            f"y se aplicó.\nLa {_orden(vista)} sigue «{vista['estado']}»."
        )
        ids = [f"orden_id: {vista['id']}", f"trabajo_id: {t['id']}"]
    return texto + _continuar(ids)


def decision_de_ampliacion(vista: dict, trabajo_id: str, ampliacion_id: str) -> str:
    t = next(x for x in _trabajos(vista) if x["id"] == trabajo_id)
    a = next(x for x in t["ampliaciones"] if x["id"] == ampliacion_id)
    return (
        f"La ampliación de {a['monto']} en «{t['descripcion']}» quedó «{a['estado']}».\n"
        f"La {_orden(vista)} está «{vista['estado']}»."
        + _continuar([f"orden_id: {vista['id']}", f"trabajo_id: {t['id']}"])
    )


def falta_de_existencia(vista: dict, trabajo_id: str) -> str:
    t = next(x for x in _trabajos(vista) if x["id"] == trabajo_id)
    oc = next((o for o in vista["ordenes_de_compra"] if o["trabajo"] == t["descripcion"]), None)
    texto = (
        f"Se registró la refacción sin existencia de «{t['descripcion']}» y se generó la orden de compra"
        + (f" de {oc['codigo']} a {oc['proveedor']}" if oc else "")
        + f".\nLa {_orden(vista)} quedó «{vista['estado']}»."
    )
    ids = [f"orden_id: {vista['id']}"]
    if oc:
        ids.append(f"orden_de_compra_id: {oc['id']}")
    return texto + _continuar(ids)


def nueva_fecha(vista: dict) -> str:
    return (
        f"Se avisó al cliente la nueva fecha estimada de entrega de la {_orden(vista)}: "
        f"{vista['nueva_fecha_estimada']} ({vista['motivo_retraso']})." + _continuar([f"orden_id: {vista['id']}"])
    )


def ordenes_de_compra(lista: list[dict]) -> str:
    if not lista:
        return "No hay órdenes de compra."
    lineas = [
        f"{n}. {o['folio']} · {o['codigo']} · {o['proveedor']} · «{o['estado']}» — orden_de_compra_id: {o['id']}"
        for n, o in enumerate(lista, 1)
    ]
    return f"Órdenes de compra ({len(lista)}):\n" + "\n".join(lineas)


def recepcion(vista: dict, orden_de_compra_id: str) -> str:
    oc = next(o for o in vista["ordenes_de_compra"] if o["id"] == orden_de_compra_id)
    return (
        f"Se registró la recepción de la refacción {oc['codigo']}; la orden de compra quedó «{oc['estado']}».\n"
        f"La {_orden(vista)} está «{vista['estado']}» y se avisó al cliente que el trabajo continúa."
        + _continuar([f"orden_id: {vista['id']}"])
    )


# -------------------------------------------------------------------- caja
def detalle_para_cobro(detalle: dict) -> str:
    lineas = [f"   - {c['concepto']}: {c['importe']}" for c in detalle["conceptos"]] or ["   (sin conceptos)"]
    estado = "puede cerrarse" if detalle["puede_cerrarse"] else "aún no puede cerrarse"
    nota = " Es cliente de flotilla: se cerrará para la facturación consolidada." if detalle["es_flotilla"] else ""
    return (
        f"Detalle para cobro de la orden {detalle['folio']} ({detalle['cliente']}) · «{detalle['estado']}»:\n"
        + "\n".join(lineas)
        + f"\nTotal a cobrar: {detalle['total']}. La orden {estado}.{nota}"
    )


def cierre(vista: dict) -> str:
    if vista["estado"] == "Cerrada sin reparación":
        texto = f"La {_orden(vista)} quedó «Cerrada sin reparación»; se cobró solo el diagnóstico aceptado."
    elif vista["cliente"]["tipo"] == "Flotilla":
        texto = f"La {_orden(vista)} quedó «Cerrado» y se incluirá en la facturación consolidada del mes."
    else:
        texto = f"Caja cobró {vista['total_cobrable']} y la {_orden(vista)} quedó «Cerrado»."
    return texto


def facturacion(resultado: dict) -> str:
    return (
        f"Se generó la facturación consolidada de {resultado['periodo']} por {resultado['total']} "
        f"con las órdenes {', '.join(resultado['ordenes'])}."
    )


# ---------------------------------------------------- consultas y gerencia
def cola(ordenes: list[dict]) -> str:
    if not ordenes:
        return "La cola de atención está vacía: no hay vehículos esperando diagnóstico."
    lineas = []
    for n, o in enumerate(ordenes, 1):
        prioridad = " · Prioridad contractual" if o["prioridad_contractual"] else ""
        lineas.append(f"{n}. {o['folio']} · {o['cliente']}{prioridad} · {o['vehiculo']} — orden_id: {o['id']}")
    return f"Cola de atención ({len(ordenes)}):\n" + "\n".join(lineas)


def plazos(folios: list[str]) -> str:
    if not folios:
        return "No hay solicitudes con 24 horas o más sin respuesta."
    return "Pasaron a «En espera de cliente» y se avisó al Gerente del Taller: " + ", ".join(folios) + "."


def disputa_registrada(disputa: dict, orden_id: str) -> str:
    return (
        f"Se registró la disputa de {disputa['categoria'].lower()}; quedó «{disputa['estado']}». "
        "El Gerente del Taller la revisará." + _continuar([f"disputa_id: {disputa['id']}", f"orden_id: {orden_id}"])
    )


def lista_de_disputas(lista: list[dict]) -> str:
    if not lista:
        return "No hay disputas registradas."
    lineas = [
        f"{n}. {d['folio']} · {d['categoria']} · «{d['estado']}» · {d['descripcion']} — disputa_id: {d['id']}"
        for n, d in enumerate(lista, 1)
    ]
    return f"Disputas ({len(lista)}):\n" + "\n".join(lineas)


def disputa_resuelta(disputa: dict) -> str:
    return f"La disputa quedó «{disputa['estado']}». Resolución: {disputa['resolucion']}"


def indicadores(datos: dict) -> str:
    minutos = datos["tiempo_promedio_comunicacion_retraso_minutos"]
    if datos["avisos_de_retraso"]:
        minutos = f"{minutos} minutos"
    return (
        f"Indicadores del periodo {datos['periodo']}:\n"
        f"• Órdenes cerradas: {datos['ordenes_cerradas']}\n"
        f"• Disputas registradas: {datos['disputas_registradas']} ({datos['disputas_abiertas']} abiertas)\n"
        f"• Decisiones con evidencia digital: {datos['porcentaje_con_evidencia_digital']} "
        f"de {datos['decisiones_de_autorizacion']} decisiones\n"
        f"• Tiempo promedio de comunicación de retraso: {minutos}\n"
        f"• Avisos de retraso en menos de 2 horas: {datos['porcentaje_avisos_menos_de_2_horas']} "
        f"de {datos['avisos_de_retraso']} avisos"
    )
