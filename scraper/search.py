"""Realiza las búsquedas en un buscador (DuckDuckGo o Bing) usando el navegador."""

from __future__ import annotations

from typing import List
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from .config import Config


def _abrir(page, url: str, config: Config) -> bool:
    """Navega a `url`. Devuelve True si cargó, False si falló."""
    try:
        page.goto(url, timeout=config.timeout_segundos * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        return True
    except Exception:
        return False


def buscar(page, consulta: str, config: Config) -> List[str]:
    """Devuelve una lista de URLs de resultados para `consulta`."""
    if config.motor_busqueda == "bing":
        return _buscar_bing(page, consulta, config)
    return _buscar_duckduckgo(page, consulta, config)


# --- DuckDuckGo ----------------------------------------------------------
def _decodificar_ddg(href: str) -> str | None:
    """Los enlaces de DuckDuckGo van envueltos en un redirect //duckduckgo.com/l/?uddg=..."""
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    try:
        p = urlparse(href)
    except Exception:
        return None
    if "duckduckgo.com" in p.netloc and p.path.startswith("/l/"):
        q = parse_qs(p.query)
        if "uddg" in q:
            return unquote(q["uddg"][0])
        return None
    return href if href.startswith("http") else None


def _buscar_duckduckgo(page, consulta: str, config: Config) -> List[str]:
    url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(consulta)
        + f"&kl={config.idioma_region}"
    )
    if not _abrir(page, url, config):
        return []
    try:
        hrefs = page.eval_on_selector_all(
            "a.result__a", "els => els.map(e => e.getAttribute('href'))"
        )
    except Exception:
        hrefs = []

    urls: List[str] = []
    for href in hrefs:
        real = _decodificar_ddg(href)
        if real:
            urls.append(real)
    return urls


# --- Bing ----------------------------------------------------------------
def _buscar_bing(page, consulta: str, config: Config) -> List[str]:
    urls: List[str] = []
    paginas = max(1, config.paginas_por_busqueda)
    for i in range(paginas):
        first = i * 10 + 1
        url = (
            "https://www.bing.com/search?q="
            + quote_plus(consulta)
            + f"&first={first}&setlang=es&cc=ES"
        )
        if not _abrir(page, url, config):
            continue
        try:
            hrefs = page.eval_on_selector_all(
                "li.b_algo h2 a", "els => els.map(e => e.href)"
            )
        except Exception:
            hrefs = []
        urls.extend(h for h in hrefs if h and h.startswith("http"))
    return urls
