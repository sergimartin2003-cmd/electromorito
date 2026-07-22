"""Funciones auxiliares compartidas por el resto de módulos."""

from __future__ import annotations

import random
import time
from urllib.parse import urlparse


def dominio(url: str) -> str:
    """Devuelve el dominio (sin 'www.') de una URL. '' si no se puede analizar."""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    # Quita el puerto si lo hubiera
    return host.split(":")[0]


def dominio_registrable(url: str) -> str:
    """Aproximación al dominio 'registrable' (ejemplo.com) para agrupar subdominios.

    No usa la lista pública de sufijos (para evitar dependencias), pero es suficiente
    para deduplicar. Ej.: 'www.blog.fundacion.org' -> 'fundacion.org'.
    """
    host = dominio(url)
    if not host:
        return ""
    partes = host.split(".")
    if len(partes) <= 2:
        return host
    # Sufijos compuestos frecuentes en España
    dobles = {"co.uk", "com.es", "org.es", "gob.es", "edu.es"}
    ultimos_dos = ".".join(partes[-2:])
    if ultimos_dos in dobles and len(partes) >= 3:
        return ".".join(partes[-3:])
    return ultimos_dos


def espera_aleatoria(min_s: float, max_s: float) -> None:
    """Pausa un tiempo aleatorio entre min_s y max_s segundos (buen comportamiento)."""
    if max_s <= 0:
        return
    time.sleep(random.uniform(max(0.0, min_s), max(0.0, max_s)))
