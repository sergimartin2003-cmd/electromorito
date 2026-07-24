#!/usr/bin/env bash
# Lanzador para Mac/Linux.
# La primera vez crea el entorno e instala todo; después solo ejecuta.
# Uso:  ./run.sh --pisos pisos.csv     (analiza un fichero)
#       ./run.sh --web                 (interfaz web local)
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Creando entorno virtual (solo la primera vez)…"
  python3 -m venv venv
  ./venv/bin/pip install --upgrade pip >/dev/null
  ./venv/bin/pip install -r requirements.txt
fi

exec ./venv/bin/python run.py "$@"
