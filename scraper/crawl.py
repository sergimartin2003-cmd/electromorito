"""Visita una web, localiza sus páginas de contacto y extrae correos, teléfonos y nombre."""

from __future__ import annotations

import urllib.error
import urllib.request
import urllib.robotparser
from typing import Dict, List, Optional

from .config import Config
from .extract import (
    calcular_relevancia,
    clave_organizacion,
    extraer_codigo_postal,
    extraer_correos,
    extraer_redes,
    extraer_telefonos,
    limpiar_nombre,
    nombre_estructurado,
)
from .util import dominio, dominio_registrable, dominio_resuelve, espera_aleatoria

# Palabras que sugieren que un enlace lleva a información de contacto/legal
_PALABRAS_CONTACTO = (
    "contact", "contacto", "contacte", "contáctanos", "contactanos",
    "about", "sobre-nosotros", "sobre_nosotros", "quienes-somos", "quienes",
    "nosotros", "conocenos", "conócenos", "equipo", "empresa",
    "aviso-legal", "aviso_legal", "aviso", "legal", "privacidad",
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Tiempo máximo (segundos) para descargar un robots.txt: evita que un servidor
# lento cuelgue todo el proceso (urllib.robotparser.read() no tiene timeout).
_ROBOTS_TIMEOUT = 10

# Caché de robots.txt por dominio para no descargarlo una y otra vez
_cache_robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}


def _descargar_robots(dom: str) -> Optional[urllib.robotparser.RobotFileParser]:
    """Descarga y analiza el robots.txt de un dominio con timeout.

    Devuelve un RobotFileParser configurado, o None si no se pudo leer
    (en cuyo caso se permite el acceso por defecto).
    """
    rp = urllib.robotparser.RobotFileParser()
    url = f"https://{dom}/robots.txt"
    rp.set_url(url)
    try:
        peticion = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(peticion, timeout=_ROBOTS_TIMEOUT) as resp:
            estado = getattr(resp, "status", 200) or 200
            datos = resp.read(1_000_000)  # límite de tamaño por seguridad
    except urllib.error.HTTPError as e:
        estado = e.code
        datos = b""
    except Exception:
        return None  # sin red / sin robots accesible -> permitir
    if estado in (401, 403):
        rp.disallow_all = True
    elif estado >= 400:
        rp.allow_all = True
    else:
        try:
            rp.parse(datos.decode("utf-8", "ignore").splitlines())
        except Exception:
            return None
    return rp


def robots_permite(url: str, config: Config) -> bool:
    """Comprueba el robots.txt del dominio. Si no se puede leer, permite por defecto."""
    if not config.respetar_robots:
        return True
    dom = dominio(url)
    if not dom:
        return True
    if dom not in _cache_robots:
        _cache_robots[dom] = _descargar_robots(dom)
    rp = _cache_robots[dom]
    if rp is None:
        return True
    try:
        return rp.can_fetch(_USER_AGENT, url)
    except Exception:
        return True


def _abrir(page, url: str, config: Config, reintentos: int = 0) -> bool:
    for intento in range(reintentos + 1):
        try:
            page.goto(url, timeout=config.timeout_segundos * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)  # deja que el JS inserte correos si los oculta
            return True
        except Exception:
            if intento < reintentos:
                try:
                    page.wait_for_timeout(1500)  # espera breve antes de reintentar
                except Exception:
                    pass
    return False


# Selectores habituales del botón "aceptar cookies" (bibliotecas y textos comunes)
_COOKIES_SELECTORES = (
    "#onetrust-accept-btn-handler", ".cc-allow", "#cookie-accept", ".cookie-accept",
    ".js-accept-cookies", "#aceptarCookies", "#acceptCookies",
    "button:has-text('Aceptar todo')", "button:has-text('Aceptar todas')",
    "button:has-text('Aceptar cookies')", "button:has-text('Aceptar y cerrar')",
    "button:has-text('Accept all')", "a:has-text('Aceptar todo')",
)


def _aceptar_cookies(page) -> None:
    """Cierra el aviso de cookies de la web (mejor esfuerzo) por si tapa el contenido."""
    for selector in _COOKIES_SELECTORES:
        try:
            el = page.query_selector(selector)
            if el and el.is_visible():
                el.click(timeout=1500)
                page.wait_for_timeout(300)
                return
        except Exception:
            continue


def _texto_y_html(page) -> str:
    """Combina el HTML renderizado y el texto visible del body."""
    partes = []
    try:
        partes.append(page.content())
    except Exception:
        pass
    try:
        cuerpo = page.query_selector("body")
        if cuerpo:
            partes.append(cuerpo.inner_text())
    except Exception:
        pass
    return "\n".join(partes)


def _mailtos(page) -> List[str]:
    try:
        return page.eval_on_selector_all(
            "a[href^='mailto:']", "els => els.map(e => e.getAttribute('href'))"
        ) or []
    except Exception:
        return []


def _tels_href(page) -> List[str]:
    try:
        return page.eval_on_selector_all(
            "a[href^='tel:']", "els => els.map(e => e.getAttribute('href'))"
        ) or []
    except Exception:
        return []


def _nombre(page) -> str:
    # 1) Datos estructurados (schema.org / JSON-LD): suelen tener el nombre oficial
    try:
        estructurado = nombre_estructurado(page.content())
        if estructurado:
            return estructurado
    except Exception:
        pass
    # 2) Meta og:site_name
    try:
        el = page.query_selector("meta[property='og:site_name']")
        if el:
            valor = el.get_attribute("content")
            if valor and valor.strip():
                return valor.strip()[:150]
    except Exception:
        pass
    # 3) Título de la página
    try:
        return limpiar_nombre(page.title())
    except Exception:
        return ""


def _enlaces_contacto(page, base_url: str) -> List[str]:
    """Devuelve enlaces INTERNOS que parezcan de contacto / aviso legal."""
    try:
        anchors = page.eval_on_selector_all(
            "a",
            "els => els.map(e => ({href: e.href, text: (e.textContent||'').trim()}))",
        )
    except Exception:
        return []

    base_dom = dominio_registrable(base_url)
    encontrados: List[str] = []
    for a in anchors:
        href = (a.get("href") or "").strip()
        text = (a.get("text") or "").lower()
        if not href.startswith("http"):
            continue
        if dominio_registrable(href) != base_dom:
            continue  # solo dentro de la misma web
        blob = href.lower() + " " + text
        if any(p in blob for p in _PALABRAS_CONTACTO):
            href = href.split("#")[0]
            if href not in encontrados and href != base_url:
                encontrados.append(href)
    return encontrados


def analizar_web(
    page, url: str, config: Config, categoria: str, provincia: str, busqueda: str
) -> Optional[dict]:
    """Visita `url` (y sus páginas de contacto) y devuelve un dict con los datos, o None si falla."""
    if not _abrir(page, url, config, reintentos=1):
        return None

    _aceptar_cookies(page)  # por si un aviso de cookies tapa los datos de contacto
    contenido = [_texto_y_html(page)]
    mailtos = _mailtos(page)
    tels_href = _tels_href(page)
    nombre = _nombre(page)
    web_final = page.url  # por si hubo redirección

    enlaces = _enlaces_contacto(page, web_final)
    for enlace in enlaces[: max(0, config.max_paginas_por_web - 1)]:
        espera_aleatoria(config.espera_min_segundos, config.espera_max_segundos)
        if _abrir(page, enlace, config):
            contenido.append(_texto_y_html(page))
            mailtos.extend(_mailtos(page))
            tels_href.extend(_tels_href(page))

    texto = "\n".join(contenido)
    correos = extraer_correos(texto, mailtos)
    telefonos = extraer_telefonos(texto, tels_href)
    relevancia = calcular_relevancia(texto, config.palabras_relevancia)
    codigo_postal = extraer_codigo_postal(texto)
    redes = extraer_redes(texto)

    # Verificación opcional por DNS: descarta correos cuyo dominio no existe.
    # El dominio propio de la web ya resuelve (lo acabamos de cargar).
    if config.verificar_dominio and correos:
        dom_web = dominio(web_final)
        correos = [c for c in correos
                   if c.split("@")[-1] == dom_web or dominio_resuelve(c.split("@")[-1])]

    return {
        "nombre": nombre,
        "correos": correos,
        "telefonos": telefonos,
        "provincia": provincia,
        "codigo_postal": codigo_postal,
        "relevancia": relevancia,
        "redes": redes,
        "grupo": clave_organizacion(nombre),
        "web": web_final,
        "dominio": dominio_registrable(web_final),
        "categoria": categoria,
        "busqueda": busqueda,
    }
