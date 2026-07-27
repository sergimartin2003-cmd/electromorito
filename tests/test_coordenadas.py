"""Tests de la geolocalización de zonas para el mapa."""

from rentapisos.coordenadas import coordenada_de
from rentapisos.pisos import procesar_pisos
from rentapisos.rentabilidad import ParametrosRentabilidad

PARAMS = ParametrosRentabilidad(rentas_zona={"Madrid": 15})


def test_coordenada_zona_exacta():
    nombre, lat, lon = coordenada_de("Barcelona")
    assert nombre == "Barcelona"
    assert 41 < lat < 42 and 1 < lon < 3


def test_coordenada_gana_la_mas_especifica():
    # "Madrid centro" cae en Madrid (no hay clave más específica)
    assert coordenada_de("Piso en Madrid centro")[0] == "Madrid"


def test_coordenada_desconocida():
    assert coordenada_de("Villa Inventada del Monte") is None
    assert coordenada_de("") is None


def test_procesar_geolocaliza_los_pisos():
    filas = [
        {"titulo": "A", "zona": "Madrid", "precio": "250000", "superficie": "90",
         "alquiler_mensual": "1300"},
        {"titulo": "B", "zona": "Zona Rara", "precio": "100000", "superficie": "60",
         "alquiler_mensual": "500"},
    ]
    pisos = procesar_pisos(filas, PARAMS)
    por_titulo = {p["titulo"]: p for p in pisos}
    assert por_titulo["A"]["zona_mapa"] == "Madrid"
    assert por_titulo["A"]["lat"] and por_titulo["A"]["lon"]
    # La zona no reconocida no recibe coordenadas (no aparecerá en el mapa)
    assert "lat" not in por_titulo["B"]
