"""Realiza las búsquedas usando el navegador.

Buscadores disponibles: DuckDuckGo, Bing, Mojeek, Startpage y Google.
En modo 'auto' o con una lista, se prueban en orden hasta obtener resultados.
"""

from __future__ import annotations

from typing import List
from urllib.parse import (
    parse_qs,
    parse_qsl,
    quote_plus,
    unquote,
    urlencode,
    urlparse,
    urlunparse,
)

from .config import Config
from .util import espera_aleatoria

# Parámetros de URL que son solo de rastreo (se eliminan de los resultados)
_PARAMS_RUIDO = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "spm",
    "igshid", "yclid", "_ga",
}

# Señales de que el buscador nos está bloqueando o pidiendo verificación
_MARCAS_BLOQUEO = (
    "unusual traffic", "detected unusual", "are you a robot", "captcha",
    "recaptcha", "if this error persists", "anomaly", "verify you are human",
    "verifica que eres humano", "tráfico inusual", "trafico inusual",
    "too many requests", "forbidden",
)


def _abrir(page, url: str, config: Config) -> bool:
    """Navega a `url`. Devuelve True si cargó, False si falló."""
    try:
        page.goto(url, timeout=config.timeout_segundos * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        return True
    except Exception:
        return False


def _contenido(page) -> str:
    """Texto/HTML de la página para detectar bloqueos (mejor esfuerzo)."""
    try:
        return page.content()
    except Exception:
        return ""


def pagina_bloqueada(texto: str) -> bool:
    """True si el contenido parece una página de bloqueo/CAPTCHA del buscador."""
    t = (texto or "").lower()
    return any(m in t for m in _MARCAS_BLOQUEO)


def limpiar_url(url: str) -> str:
    """Normaliza una URL de resultado: quita el fragmento y los parámetros de rastreo."""
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        p = urlparse(url)
    except Exception:
        return ""
    if not p.netloc:
        return ""
    query = ""
    if p.query:
        params = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                  if k.lower() not in _PARAMS_RUIDO]
        query = urlencode(params)
    return urlunparse((p.scheme, p.netloc, p.path, "", query, ""))


def limpiar_y_dedup(urls: List[str]) -> List[str]:
    """Limpia cada URL y elimina duplicados conservando el orden."""
    vistas = set()
    salida: List[str] = []
    for u in urls:
        limpia = limpiar_url(u)
        if not limpia or limpia in vistas:
            continue
        vistas.add(limpia)
        salida.append(limpia)
    return salida


def buscar(page, consulta: str, config: Config) -> List[str]:
    """Devuelve URLs de resultados, probando los buscadores configurados en orden.

    En modo 'auto' (varios motores) usa el primero que devuelva resultados.
    Las URLs se limpian (sin parámetros de rastreo) y se deduplican.
    """
    for motor in config.motores:
        funcion = _MOTORES.get(motor)
        if funcion is None:
            continue
        try:
            urls = funcion(page, consulta, config)
        except Exception:
            urls = []
        urls = limpiar_y_dedup(urls)
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


def _href_attrs(page, selector: str) -> List[str]:
    """Devuelve los atributos href (crudos) de un selector, o []."""
    try:
        return page.eval_on_selector_all(
            selector, "els => els.map(e => e.getAttribute('href'))"
        ) or []
    except Exception:
        return []


def _ddg_click_siguiente(page) -> bool:
    """Pulsa el botón 'Siguiente' de DuckDuckGo (html/lite). True si pudo."""
    for selector in (
        ".nav-link input[type=submit]",
        "input.btn--alt[type=submit]",
        "input[type=submit][value='Next']",
        "input[type=submit][value*='iguiente']",
        "form.nav-link input[type=submit]",
    ):
        try:
            botones = page.query_selector_all(selector)
            if botones:
                botones[-1].click(timeout=3000)
                page.wait_for_timeout(900)
                return True
        except Exception:
            continue
    return False


def _ddg_recoger(page, selector: str, config: Config) -> List[str]:
    """Recoge resultados de DuckDuckGo paginando hasta `paginas_por_busqueda`."""
    urls: List[str] = []
    paginas = max(1, config.paginas_por_busqueda)
    for i in range(paginas):
        for href in _href_attrs(page, selector):
            real = _decodificar_ddg(href)
            if real:
                urls.append(real)
        if i < paginas - 1 and not _ddg_click_siguiente(page):
            break
    return urls


def _ddg_endpoint(page, base: str, selector: str, consulta: str, config: Config) -> List[str]:
    url = base + "?q=" + quote_plus(consulta) + f"&kl={config.idioma_region}"
    if not _abrir(page, url, config):
        return []
    if pagina_bloqueada(_contenido(page)):
        return []
    return _ddg_recoger(page, selector, config)


def _buscar_duckduckgo(page, consulta: str, config: Config) -> List[str]:
    """DuckDuckGo con paginación; si el endpoint HTML falla o bloquea, prueba Lite."""
    urls = _ddg_endpoint(
        page, "https://html.duckduckgo.com/html/",
        "a.result__a, a[href*='uddg=']", consulta, config,
    )
    if urls:
        return urls
    # Reintento con espera algo mayor sobre el endpoint 'lite' (más simple y tolerante)
    espera_aleatoria(config.espera_min_segundos, config.espera_max_segundos * 1.5)
    return _ddg_endpoint(
        page, "https://lite.duckduckgo.com/lite/",
        "a.result-link, a[href*='uddg=']", consulta, config,
    )


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
            break
        _aceptar_consentimiento(page)
        if pagina_bloqueada(_contenido(page)):
            break
        hrefs = _hrefs(page, "li.b_algo h2 a", "#b_results h2 a", "#b_results li.b_algo a[href^='http']")
        if not hrefs:
            break  # sin resultados: no tiene sentido seguir paginando
        urls.extend(hrefs)
    return urls


# --- Mojeek (buscador propio, tolera bien la automatización) -------------
def _buscar_mojeek(page, consulta: str, config: Config) -> List[str]:
    url = "https://www.mojeek.com/search?q=" + quote_plus(consulta)
    if not _abrir(page, url, config):
        return []
    if pagina_bloqueada(_contenido(page)):
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
    if pagina_bloqueada(_contenido(page)):
        return []
    hrefs = _hrefs(page, "a.result-link", "a.w-gl__result-title",
                   ".w-gl__result a[href^='http']", ".result a[href^='http']")
    return [h for h in hrefs if "startpage.com" not in h]


# --- Google (frágil: suele mostrar CAPTCHA/consentimiento) ---------------
def _buscar_google(page, consulta: str, config: Config) -> List[str]:
    url = ("https://www.google.com/search?hl=es&num=20&q=" + quote_plus(consulta))
    if not _abrir(page, url, config):
        return []
    _aceptar_consentimiento(page)
    if pagina_bloqueada(_contenido(page)):
        return []
    hrefs = _hrefs(page, "div.yuRUbf > a", "#search a[href^='http']",
                   "#rso a[href^='http']")
    malos = ("google.com", "google.es", "gstatic.com", "googleusercontent.com",
             "youtube.com", "webcache.googleusercontent.com", "accounts.google")
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
