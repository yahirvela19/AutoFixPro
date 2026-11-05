"""Ejecuta los 120 casos y las 20 transiciones del paquete docente y escribe los resultados.

Uso: python -m scripts.ejecutar_paquete_docente
"""

from pathlib import Path

from src.infrastructure.paquete_docente import escribir_resultados, leer_paquete

RAIZ = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    paquete = leer_paquete(RAIZ / "datos" / "paquete_docente")
    casos, transiciones = escribir_resultados(paquete, RAIZ / "docs" / "testing")
    print(f"Resultados escritos en {casos.relative_to(RAIZ)} y {transiciones.relative_to(RAIZ)}")
