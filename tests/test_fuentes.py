"""Tests de las fuentes de datos (normalización de campos y fuente de archivo)."""

import pytest

from rentapisos.fuentes import (
    FuenteArchivo,
    FuenteFeedInmobiliaria,
    FuenteIdealistaAPI,
    normalizar_anuncio,
)


def test_normaliza_nombres_de_campo():
    crudo = {
        "Enlace": "https://ej.com/1",
        "Ciudad": "Madrid",
        "Precio_venta": "250.000",
        "m2": "90",
        "Dormitorios": "3",
        "Renta": "1300",
    }
    norm = normalizar_anuncio(crudo)
    assert norm["url"] == "https://ej.com/1"
    assert norm["zona"] == "Madrid"
    assert norm["precio"] == "250.000"
    assert norm["superficie"] == "90"
    assert norm["habitaciones"] == "3"
    assert norm["alquiler_mensual"] == "1300"


def test_normaliza_conserva_campos_desconocidos():
    norm = normalizar_anuncio({"titulo": "Piso", "referencia_interna": "AB-12"})
    assert norm["titulo"] == "Piso"
    assert norm["referencia_interna"] == "AB-12"


def test_fuente_archivo(tmp_path):
    csv = tmp_path / "pisos.csv"
    csv.write_text("titulo,zona,precio\nPiso,Madrid,250000\n", encoding="utf-8")
    fuente = FuenteArchivo(str(csv))
    anuncios = fuente.anuncios()
    assert anuncios == [{"titulo": "Piso", "zona": "Madrid", "precio": "250000"}]


def test_fuente_archivo_normaliza(tmp_path):
    csv = tmp_path / "feed.csv"
    csv.write_text("Ciudad,Precio_venta,m2\nMadrid,250000,90\n", encoding="utf-8")
    anuncios = FuenteArchivo(str(csv), normalizar=True).anuncios()
    assert anuncios[0]["zona"] == "Madrid"
    assert anuncios[0]["superficie"] == "90"


def test_fuentes_no_implementadas_avisan():
    with pytest.raises(NotImplementedError):
        FuenteIdealistaAPI("k", "s").anuncios()
    with pytest.raises(NotImplementedError):
        FuenteFeedInmobiliaria("feed.xml").anuncios()
