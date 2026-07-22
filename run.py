#!/usr/bin/env python3
"""Lanzador cómodo del scraper.

Equivale a  `python -m scraper`.  Ejecútalo con:

    python run.py                 # usa config.yaml
    python run.py --prueba        # prueba rápida (3 búsquedas)
    python run.py -c otro.yaml    # con otra configuración
"""

from scraper.__main__ import main

if __name__ == "__main__":
    main()
