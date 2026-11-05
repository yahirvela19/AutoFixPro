"""Exporta el contrato OpenAPI a docs/api/openapi.json.

Uso: python -m scripts.exportar_openapi
"""

import json
from pathlib import Path

from src.api.configuracion import Configuracion
from src.api.main import crear_app

RAIZ = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    app = crear_app(Configuracion(database_url="sqlite://", cargar_datos_demo=False))
    destino = RAIZ / "docs" / "api" / "openapi.json"
    destino.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Contrato OpenAPI escrito en {destino.relative_to(RAIZ)}")
