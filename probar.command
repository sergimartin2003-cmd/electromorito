#!/bin/bash
# Doble clic en Mac: analiza el fichero de EJEMPLO (pisos_ejemplo.csv).
# La primera vez instala todo (tarda un poco); después es rápido.
cd "$(dirname "$0")"
bash run.sh --pisos pisos_ejemplo.csv
echo ""
echo "======================================================"
echo "  Listo. Abre 'resultados_pisos.html' en esta carpeta."
echo "  Pulsa Enter para cerrar."
read _
