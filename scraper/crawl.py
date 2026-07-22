"""Visita una web, localiza sus páginas de contacto y extrae correos, teléfonos y nombre."""

from __future__ import annotations

import urllib.robotparser
from typing import Dict, List, Optional

from .config import Config
from .extract import extraer_correos, extraer_telefonos, limpiar_nombre
from .util import dominio, dominio_registrable, espera_aleatoria

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

# Caché de robots.txt por dominio para no descargarlo una y otra vez
_cache_robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}


def robots_permite(url: str, config: Config) -> bool:
    """Comprueba el robots.txt del dominio. Si no se puede leer, permite por defecto."""
    if not config.respetar_robots:
        return True
    dom = dominio(url)
    if not dom:
        return True
    if dom not in _cache_robots:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"https://{dom}/robots.txt")
        try:
            rp.read()
            _cache_robots[dom] = rp
        except Exception:
            _cache_robots[dom] = None  # no se pudo leer -> permitir
    rp = _cache_robots[dom]
    if rp is None:
        return True
    try:
        return rp.can_fetch(_USER_AGENT, url)
    except Exception:
        return True


def _abrir(page, url: str, config: Config) -> bool:
    try:
        page.goto(url, timeout=config.timeout_segundos * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)  # deja que el JS inserte correos si los oculta
        return True
    except Exception:
        return False


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
    try:
        el = page.query_selector("meta[property='og:site_name']")
        if el:
            valor = el.get_attribute("content")
            if valor and valor.strip():
                return valor.strip()[:150]
    except Exception:
        pass
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


def analizar_web(page, url: str, config: Config, categoria: str, busqueda: str) -> Optional[dict]:
    """Visita `url` (y sus páginas de contacto) y devuelve un dict con los datos, o None si falla."""
    if not _abrir(page, url, config):
        return None

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

    return {
        "nombre": nombre,
        "correos": correos,
        "telefonos": telefonos,
        "web": web_final,
        "dominio": dominio_registrable(web_final),
        "categoria": categoria,
        "busqueda": busqueda,
    }
