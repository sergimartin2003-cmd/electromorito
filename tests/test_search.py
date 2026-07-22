"""Tests de las funciones puras del motor de búsqueda."""

from scraper.search import (
    _decodificar_ddg,
    limpiar_url,
    limpiar_y_dedup,
    pagina_bloqueada,
)


# --- limpiar_url ---------------------------------------------------------
def test_limpiar_url_quita_tracking_y_fragmento():
    u = "https://fundacion.org/contacto?utm_source=ddg&id=5#seccion"
    assert limpiar_url(u) == "https://fundacion.org/contacto?id=5"


def test_limpiar_url_sin_parametros_utiles():
    assert limpiar_url("https://x.es/a?fbclid=123&gclid=abc") == "https://x.es/a"


def test_limpiar_url_rechaza_no_http():
    assert limpiar_url("mailto:info@x.es") == ""
    assert limpiar_url("javascript:void(0)") == ""
    assert limpiar_url("") == ""


# --- limpiar_y_dedup -----------------------------------------------------
def test_dedup_tras_limpiar():
    urls = [
        "https://a.es/",
        "https://a.es/?utm_medium=x",   # igual tras limpiar
        "https://b.es/pagina",
        "mailto:no@vale.es",             # se descarta
    ]
    assert limpiar_y_dedup(urls) == ["https://a.es/", "https://b.es/pagina"]


def test_dedup_conserva_orden():
    urls = ["https://c.es", "https://a.es", "https://c.es"]
    assert limpiar_y_dedup(urls) == ["https://c.es", "https://a.es"]


# --- pagina_bloqueada ----------------------------------------------------
def test_bloqueo_detectado():
    assert pagina_bloqueada("Please verify you are human")
    assert pagina_bloqueada("Se ha detectado tráfico inusual")
    assert pagina_bloqueada("Too many requests")


def test_bloqueo_no_falso_positivo():
    assert not pagina_bloqueada("Resultados de fundaciones de discapacidad en Madrid")
    assert not pagina_bloqueada("")


# --- _decodificar_ddg ----------------------------------------------------
def test_ddg_decodifica_redirect():
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Ffundacion.org%2F&rut=abc"
    assert _decodificar_ddg(href) == "https://fundacion.org/"


def test_ddg_enlace_directo():
    assert _decodificar_ddg("https://centro.es/contacto") == "https://centro.es/contacto"


def test_ddg_none():
    assert _decodificar_ddg("") is None
