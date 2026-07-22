"""Tests del aviso de bloqueo del buscador y de la limpieza de salidas."""

import os

from scraper.search import aviso_buscador
from scraper.storage import limpiar_salidas


# --- aviso_buscador ------------------------------------------------------
def test_aviso_none_al_principio():
    assert aviso_buscador(0) is None
    assert aviso_buscador(4) is None


def test_aviso_a_los_5():
    msg = aviso_buscador(5)
    assert msg and "5 búsquedas" in msg


def test_aviso_multiplos_de_15():
    assert aviso_buscador(15) is not None
    assert aviso_buscador(30) is not None
    assert aviso_buscador(16) is None


# --- limpiar_salidas -----------------------------------------------------
def test_limpiar_salidas_borra_ficheros(tmp_path):
    base = str(tmp_path / "res")
    # Crea los ficheros típicos de una ejecución previa
    for ext in (".csv", ".xlsx", ".html", "_dominios_visitados.txt"):
        open(base + ext, "w").close()
    borrados = limpiar_salidas(base)
    assert len(borrados) == 4
    for ext in (".csv", ".xlsx", ".html", "_dominios_visitados.txt"):
        assert not os.path.exists(base + ext)


def test_limpiar_salidas_sin_ficheros(tmp_path):
    assert limpiar_salidas(str(tmp_path / "no_hay")) == []
