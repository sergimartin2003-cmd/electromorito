"""Punto de entrada:  python -m scraper  [--config config.yaml]"""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .runner import ejecutar


def _forzar_utf8() -> None:
    """Hace que la consola use UTF-8 para que los acentos y símbolos se vean bien.

    Especialmente útil en Windows, donde la consola suele usar cp1252.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> None:
    _forzar_utf8()
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="Scraper de contactos de fundaciones, escuelas PFI/IFE y centros de estudios.",
    )
    parser.add_argument(
        "--config", "-c", default="config.yaml",
        help="Ruta al archivo de configuración (por defecto: config.yaml)",
    )
    parser.add_argument(
        "--prueba", action="store_true",
        help="Modo prueba: limita a 3 búsquedas para comprobar que todo funciona.",
    )
    args = parser.parse_args()

    try:
        config = Config.cargar(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR de configuración: {e}")
        sys.exit(1)

    if args.prueba:
        config.max_busquedas = 3
        print("  [modo prueba] Se limitará a 3 búsquedas.\n")

    ejecutar(config)


if __name__ == "__main__":
    main()
