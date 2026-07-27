#!/usr/bin/env python3
"""Lanzador cómodo. Equivale a  `python -m rentapisos`.

    python run.py --pisos pisos.csv     # analiza un fichero de anuncios
    python run.py --web                 # interfaz web local (pega y analiza)
    python run.py -c otro.yaml --pisos pisos.csv
"""

from rentapisos.__main__ import main

if __name__ == "__main__":
    main()
