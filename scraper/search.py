"""Realiza las búsquedas usando el navegador.

Buscadores disponibles: DuckDuckGo, Bing, Mojeek, Startpage y Google.
En modo 'auto' o con una lista, se prueban en orden hasta obtener resultados.
"""

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
    """Devuelve URLs de resultados, probando los buscadores configurados en orden.

    En modo 'auto' (varios motores) usa el primero que devuelva resultados.
    """
    for motor in config.motores:
        funcion = _MOTORES.get(motor)
        if funcion is None:
            continue
        try:
            urls = funcion(page, consulta, config)
        except Exception:
            urls = []
        if urls:
            return urls
    return []


def aviso_buscador(consecutivos_vacios: int) -> str | None:
    """Devuelve un aviso si demasiadas búsquedas seguidas no dan resultados.

    Suele indicar que el buscador está limitando las peticiones automáticas.
    Devuelve None si no hay que avisar todavía.
    """
    if consecutivos_vacios == 5:
        return ("AVISO: 5 búsquedas seguidas sin resultados. El buscador podría estar "
                "limitando las peticiones. Prueba a subir 'espera_min_segundos' y "
                "'espera_max_segundos', o cambia 'motor_busqueda' (p.ej. a 'auto').")
    if consecutivos_vacios and consecutivos_vacios % 15 == 0:
        return (f"AVISO: {consecutivos_vacios} búsquedas seguidas sin resultados. "
                "Considera detener (Ctrl+C) y reanudar más tarde con más espera.")
    return None


# Botones de "aceptar cookies/consentimiento" habituales (Google, Bing, Startpage…)
_CONSENTIMIENTO = (
    "#L2AGLb", "button#bnp_btn_accept", "button[aria-label*='Aceptar']",
    "button:has-text('Aceptar todo')", "button:has-text('Accept all')",
    "button:has-text('I agree')", "button:has-text('Estoy de acuerdo')",
)


def _aceptar_consentimiento(page) -> None:
    """Intenta cerrar el aviso de cookies del buscador (mejor esfuerzo)."""
    for selector in _CONSENTIMIENTO:
        try:
            el = page.query_selector(selector)
            if el:
                el.click(timeout=2000)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def _hrefs(page, *selectores) -> List[str]:
    """Devuelve los href absolutos del primer selector que encuentre algo."""
    for selector in selectores:
        try:
            hrefs = page.eval_on_selector_all(
                selector, "els => els.map(e => e.href || e.getAttribute('href'))"
            )
        except Exception:
            hrefs = []
        hrefs = [h for h in (hrefs or []) if h and h.startswith("http")]
        if hrefs:
            return hrefs
    return []


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
    # Respaldo por si cambia el marcado: cualquier enlace con el redirect 'uddg='
    if not hrefs:
        try:
            hrefs = page.eval_on_selector_all(
                "a[href*='uddg=']", "els => els.map(e => e.getAttribute('href'))"
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
        if not hrefs:
            try:
                hrefs = page.eval_on_selector_all(
                    "#b_results h2 a", "els => els.map(e => e.href)"
                )
            except Exception:
                hrefs = []
        urls.extend(h for h in hrefs if h and h.startswith("http"))
    return urls


# --- Mojeek (buscador propio, tolera bien la automatización) -------------
def _buscar_mojeek(page, consulta: str, config: Config) -> List[str]:
    url = "https://www.mojeek.com/search?q=" + quote_plus(consulta)
    if not _abrir(page, url, config):
        return []
    hrefs = _hrefs(page, "a.title", "ul.results-standard li a[href^='http']",
                   ".results a[href^='http']")
    return [h for h in hrefs if "mojeek.com" not in h]


# --- Startpage (usa resultados de Google; puede pedir consentimiento) ----
def _buscar_startpage(page, consulta: str, config: Config) -> List[str]:
    url = "https://www.startpage.com/sp/search?query=" + quote_plus(consulta)
    if not _abrir(page, url, config):
        return []
    _aceptar_consentimiento(page)
    hrefs = _hrefs(page, "a.result-link", "a.w-gl__result-title",
                   ".w-gl__result a[href^='http']", ".result a[href^='http']")
    return [h for h in hrefs if "startpage.com" not in h]


# --- Google (frágil: suele mostrar CAPTCHA/consentimiento) ---------------
def _buscar_google(page, consulta: str, config: Config) -> List[str]:
    url = ("https://www.google.com/search?hl=es&num=20&q=" + quote_plus(consulta))
    if not _abrir(page, url, config):
        return []
    _aceptar_consentimiento(page)
    hrefs = _hrefs(page, "div.yuRUbf > a", "#search a[href^='http']",
                   "#rso a[href^='http']")
    malos = ("google.com", "google.es", "gstatic.com", "googleusercontent.com",
             "youtube.com", "webcache.googleusercontent.com")
    return [h for h in hrefs if not any(m in h for m in malos)]


# Registro de buscadores disponibles
_MOTORES = {
    "duckduckgo": _buscar_duckduckgo,
    "bing": _buscar_bing,
    "mojeek": _buscar_mojeek,
    "startpage": _buscar_startpage,
    "google": _buscar_google,
}

# Motores válidos (para validar la configuración desde config.py)
MOTORES_VALIDOS = set(_MOTORES) | {"auto"}
# Orden que usa el modo "auto": primero los más fiables
MOTORES_AUTO = ["duckduckgo", "mojeek", "bing"]
