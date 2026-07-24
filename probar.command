#!/bin/bash
# Doble clic en Mac para una PRUEBA RÁPIDA (solo 3 búsquedas).
# La primera vez instala todo (tarda unos minutos); después es rápido.
cd "$(dirname "$0")"
bash run.sh --prueba
echo ""
echo "======================================================"
echo "  Prueba terminada. Pulsa Enter para cerrar."
read _
