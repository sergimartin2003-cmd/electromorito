#!/bin/bash
# Doble clic en Mac: abre la INTERFAZ WEB local y el navegador.
# Para pararla, cierra esta ventana o pulsa Ctrl+C.
cd "$(dirname "$0")"
( sleep 2; open "http://127.0.0.1:8000" ) &
bash run.sh --web
