#!/usr/bin/env bash
# Lanzador para Mac/Linux.
# La primera vez crea el entorno e instala todo; después solo ejecuta.
# Uso:  ./run.sh            (ejecución normal)
#       ./run.sh --prueba   (prueba rápida)
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Creando entorno virtual (solo la primera vez)…"
  python3 -m venv venv
  ./venv/bin/pip install --upgrade pip >/dev/null
  ./venv/bin/pip install -r requirements.txt
  ./venv/bin/python -m playwright install chromium
fi

exec ./venv/bin/python run.py "$@"
