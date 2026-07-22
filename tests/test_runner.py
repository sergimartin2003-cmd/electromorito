"""Tests de helpers del runner y del lector de URLs (modo --desde-urls)."""

from scraper.__main__ import _leer_urls
from scraper.config import Config
from scraper.runner import _filtrar_urls


# --- _leer_urls ----------------------------------------------------------
def test_leer_urls_normaliza_y_filtra(tmp_path):
    ruta = tmp_path / "urls.txt"
    ruta.write_text(
        "# comentario\n"
        "fundacion.org\n"
        "https://centro.es/contacto\n"
        "\n"
        "   escuela.cat  \n",
        encoding="utf-8",
    )
    urls = _leer_urls(str(ruta))
    assert urls == [
        "https://fundacion.org",
        "https://centro.es/contacto",
        "https://escuela.cat",
    ]


def test_leer_urls_archivo_inexistente(tmp_path):
    assert _leer_urls(str(tmp_path / "no.txt")) == []


# --- _filtrar_urls -------------------------------------------------------
def _cfg(excluidos=None, tope=15):
    c = Config()
    c.dominios_excluidos = excluidos or []
    c.resultados_por_busqueda = tope
    return c


def test_filtrar_dedup_por_dominio():
    urls = ["https://a.es/x", "https://a.es/y", "https://b.es"]
    assert _filtrar_urls(urls, _cfg()) == ["https://a.es/x", "https://b.es"]


def test_filtrar_excluye_dominios():
    urls = ["https://facebook.com/x", "https://fundacion.org"]
    assert _filtrar_urls(urls, _cfg(excluidos=["facebook.com"])) == ["https://fundacion.org"]


def test_filtrar_respeta_tope():
    urls = [f"https://s{i}.es" for i in range(10)]
    assert len(_filtrar_urls(urls, _cfg(tope=3))) == 3


def test_filtrar_sin_limite():
    urls = [f"https://s{i}.es" for i in range(10)]
    assert len(_filtrar_urls(urls, _cfg(tope=3), limite=0)) == 10
