"""Punto de entrada:  python -m scraper  [--config config.yaml]"""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .runner import ejecutar


def main() -> None:
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
