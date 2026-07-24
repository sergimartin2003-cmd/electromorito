#!/bin/bash
# Doble clic en Mac para la EJECUCIÓN COMPLETA.
# Puedes pararlo cuando quieras con Ctrl+C; lo recogido queda guardado.
cd "$(dirname "$0")"
bash run.sh
echo ""
echo "======================================================"
echo "  Terminado. Mira los ficheros resultados.* en esta carpeta."
echo "  Pulsa Enter para cerrar."
read _
