"""Rentas de referencia ORIENTATIVAS por zona (€/m²/mes) para estimar el alquiler.

Sirven para que la estimación funcione "de fábrica" cuando no defines `rentas_zona`
en config.yaml. Son valores APROXIMADOS de mercado (capitales/provincias) y NO
sustituyen a un dato real: reemplázalos por los tuyos o por los de SERPAVI
(Sistema Estatal de Referencia del Precio del Alquiler, https://serpavi.mivau.gob.es).

Puedes desactivar esta tabla con `usar_rentas_referencia: false` en config.yaml.
Tus valores de `rentas_zona` siempre tienen prioridad sobre estos.
"""

from __future__ import annotations

# €/m²/mes orientativos. Se emparejan por palabras completas (ver estimar_alquiler),
# así que "Madrid centro" en un anuncio usa "Madrid" si no hay una clave más específica.
RENTAS_REFERENCIA = {
    # Grandes ciudades / áreas tensionadas
    "Madrid": 16,
    "Barcelona": 16,
    "San Sebastián": 15,
    "Donostia": 15,
    "Palma": 13,
    "Palma de Mallorca": 13,
    "Bilbao": 12,
    "Málaga": 12,
    "Valencia": 11,
    "Las Palmas": 11,
    "Santa Cruz de Tenerife": 11,
    "Cádiz": 11,
    "Girona": 11,
    "Alicante": 10,
    "Sevilla": 10,
    "Vitoria": 10,
    "Pamplona": 10,
    "Tarragona": 10,
    "A Coruña": 9,
    "Granada": 9,
    "Santander": 9,
    "Zaragoza": 9,
    "Valladolid": 8,
    "Córdoba": 8,
    "Vigo": 8,
    "Murcia": 8,
    "Gijón": 8,
    "Salamanca": 8,
    "Almería": 8,
    "León": 7,
    "Toledo": 7,
    "Albacete": 7,
    "Badajoz": 7,
    "Cáceres": 7,
    "Jaén": 7,
    "Ourense": 7,
    "Ciudad Real": 6,
}
