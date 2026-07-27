"""Punto de entrada del análisis de rentabilidad de pisos.

    python -m rentapisos --pisos pisos.csv     # genera CSV + panel HTML + informe
    python -m rentapisos --web                 # interfaz web local (pega y analiza)
"""

from __future__ import annotations

import argparse
import sys

from .config import Config


def _forzar_utf8() -> None:
    """Hace que la consola use UTF-8 para que los acentos se vean bien (útil en Windows)."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> None:
    _forzar_utf8()
    parser = argparse.ArgumentParser(
        prog="pisos",
        description="Analiza la rentabilidad de alquiler de una lista de pisos (CSV/JSON/XLSX) "
                    "y genera un CSV, un panel HTML interactivo y un informe.",
    )
    parser.add_argument(
        "--config", "-c", default="config.yaml",
        help="Ruta al archivo de configuración (por defecto: config.yaml).",
    )
    parser.add_argument(
        "--pisos", default=None, metavar="ARCHIVO",
        help="Archivo de anuncios (CSV/JSON/XLSX) a analizar.",
    )
    parser.add_argument(
        "--rentas", default=None, metavar="ARCHIVO",
        help="Carga una tabla de rentas por zona (€/m²·mes, p. ej. de SERPAVI) para "
             "estimar el alquiler.",
    )
    parser.add_argument(
        "--ia", action="store_true",
        help="Usa la IA (API de Claude) para estimar el alquiler y detectar riesgos en "
             "los pisos que no traen alquiler.",
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Abre una interfaz web local: pega los anuncios y obtén el ranking.",
    )
    parser.add_argument(
        "--puerto", type=int, default=8000, metavar="N",
        help="Puerto para la interfaz web (por defecto 8000).",
    )
    parser.add_argument(
        "--salida", "-o", default=None,
        help="Nombre base de los ficheros de salida (sobrescribe config.yaml).",
    )
    args = parser.parse_args()

    try:
        config = Config.cargar(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR de configuración: {e}")
        sys.exit(1)

    if args.salida:
        config.archivo_salida = args.salida
    if args.ia:
        config.usar_ia = True

    if args.rentas:
        from .pisos import cargar_rentas_zona_csv
        try:
            extra = cargar_rentas_zona_csv(args.rentas)
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR al leer las rentas: {e}")
            sys.exit(1)
        config.rentas_zona = {**(config.rentas_zona or {}), **extra}
        print(f"  Rentas por zona cargadas de '{args.rentas}': {len(extra)} zona(s).")

    if args.web:
        from .web import iniciar_servidor
        iniciar_servidor(config, puerto=args.puerto)
        return

    if args.pisos:
        from .pisos import ejecutar_pisos
        ejecutar_pisos(config, args.pisos)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
