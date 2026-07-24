"""Coordenadas aproximadas (lat, lon) de provincias y ciudades españolas.

Sirven para situar cada piso en el mapa del panel a partir de su `zona`. Son
centroides orientativos de capitales/provincias; para el mapa esquemático del panel
es más que suficiente. La zona del anuncio se empareja por palabras completas (igual
que las rentas): "Madrid centro" cae en "Madrid" si no hay una clave más específica.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .rentabilidad import _es_sublista, _normalizar

# (lat, lon)
COORDENADAS = {
    "A Coruña": (43.3623, -8.4115),
    "Coruña": (43.3623, -8.4115),
    "Álava": (42.8467, -2.6716),
    "Vitoria": (42.8467, -2.6716),
    "Albacete": (38.9943, -1.8585),
    "Alicante": (38.3452, -0.4810),
    "Almería": (36.8340, -2.4637),
    "Oviedo": (43.3619, -5.8494),
    "Asturias": (43.3619, -5.8494),
    "Gijón": (43.5322, -5.6611),
    "Ávila": (40.6565, -4.6818),
    "Badajoz": (38.8794, -6.9707),
    "Palma": (39.5696, 2.6502),
    "Palma de Mallorca": (39.5696, 2.6502),
    "Baleares": (39.5696, 2.6502),
    "Barcelona": (41.3874, 2.1686),
    "Bilbao": (43.2630, -2.9350),
    "Vizcaya": (43.2630, -2.9350),
    "Bizkaia": (43.2630, -2.9350),
    "Burgos": (42.3439, -3.6969),
    "Cáceres": (39.4753, -6.3724),
    "Cádiz": (36.5271, -6.2886),
    "Santander": (43.4623, -3.8099),
    "Cantabria": (43.4623, -3.8099),
    "Castellón": (39.9864, -0.0513),
    "Ciudad Real": (38.9848, -3.9274),
    "Córdoba": (37.8882, -4.7794),
    "Cuenca": (40.0704, -2.1374),
    "Girona": (41.9794, 2.8214),
    "Gerona": (41.9794, 2.8214),
    "Granada": (37.1773, -3.5986),
    "Guadalajara": (40.6320, -3.1601),
    "San Sebastián": (43.3183, -1.9812),
    "Donostia": (43.3183, -1.9812),
    "Guipúzcoa": (43.3183, -1.9812),
    "Huelva": (37.2614, -6.9447),
    "Huesca": (42.1362, -0.4089),
    "Jaén": (37.7796, -3.7849),
    "León": (42.5987, -5.5671),
    "Lleida": (41.6176, 0.6200),
    "Lérida": (41.6176, 0.6200),
    "Lugo": (43.0121, -7.5559),
    "Madrid": (40.4168, -3.7038),
    "Málaga": (36.7213, -4.4214),
    "Murcia": (37.9922, -1.1307),
    "Pamplona": (42.8125, -1.6458),
    "Navarra": (42.8125, -1.6458),
    "Ourense": (42.3357, -7.8639),
    "Orense": (42.3357, -7.8639),
    "Palencia": (42.0096, -4.5288),
    "Las Palmas": (28.1235, -15.4363),
    "Pontevedra": (42.4310, -8.6444),
    "Vigo": (42.2406, -8.7207),
    "Logroño": (42.4627, -2.4449),
    "La Rioja": (42.4627, -2.4449),
    "Salamanca": (40.9701, -5.6635),
    "Santa Cruz de Tenerife": (28.4636, -16.2518),
    "Tenerife": (28.4636, -16.2518),
    "Segovia": (40.9429, -4.1088),
    "Sevilla": (37.3891, -5.9845),
    "Soria": (41.7665, -2.4790),
    "Tarragona": (41.1189, 1.2445),
    "Teruel": (40.3440, -1.1069),
    "Toledo": (39.8628, -4.0273),
    "Valencia": (39.4699, -0.3763),
    "Valladolid": (41.6523, -4.7245),
    "Zamora": (41.5033, -5.7446),
    "Zaragoza": (41.6488, -0.8891),
}


def coordenada_de(zona: str) -> Optional[Tuple[str, float, float]]:
    """Devuelve (nombre, lat, lon) para la zona, o None si no se reconoce.

    Empareja por palabras completas y gana la clave más específica (la más larga),
    igual que la estimación de alquiler por zona.
    """
    z_tokens = _normalizar(zona).split()
    if not z_tokens:
        return None
    mejor = None
    mejor_long = -1
    for nombre, (lat, lon) in COORDENADAS.items():
        k = _normalizar(nombre).split()
        if _es_sublista(k, z_tokens) and len(k) > mejor_long:
            mejor = (nombre, lat, lon)
            mejor_long = len(k)
    return mejor
