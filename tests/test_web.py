"""Tests de los ayudantes de la interfaz web (sin levantar el servidor)."""

from types import SimpleNamespace

from scraper.pisos import parsear_texto, procesar_con_config
from scraper.web import _pagina_formulario

CONFIG = SimpleNamespace(rentas_zona={"Madrid": 15}, usar_ia=False)


def test_parsear_texto_csv():
    texto = "titulo,zona,precio,superficie,alquiler_mensual\nPiso,Madrid,250000,90,1300"
    filas = parsear_texto(texto)
    assert filas == [{"titulo": "Piso", "zona": "Madrid", "precio": "250000",
                      "superficie": "90", "alquiler_mensual": "1300"}]


def test_parsear_texto_json():
    filas = parsear_texto('[{"titulo": "Piso", "zona": "Madrid"}]')
    assert filas[0]["titulo"] == "Piso"


def test_parsear_texto_vacio():
    assert parsear_texto("   ") == []


def test_procesar_con_config():
    filas = [
        {"titulo": "Bueno", "zona": "Madrid", "precio": "100000",
         "superficie": "60", "alquiler_mensual": "700"},
        {"titulo": "Malo", "zona": "Madrid", "precio": "400000",
         "superficie": "90", "alquiler_mensual": "700"},
    ]
    pisos = procesar_con_config(CONFIG, filas)
    assert pisos[0]["titulo"] == "Bueno"
    assert pisos[0]["puntuacion"] >= pisos[1]["puntuacion"]


def test_pagina_formulario_escapa_y_muestra_error():
    pagina = _pagina_formulario("<script>x</script>", "algo falló")
    assert "<textarea" in pagina
    assert "&lt;script&gt;" in pagina          # el contenido se escapa
    assert "algo falló" in pagina
