"""Funciones auxiliares compartidas por el resto de módulos."""

from __future__ import annotations

import random
import socket
import time
from typing import Dict
from urllib.parse import urlparse

# Caché de resoluciones DNS por dominio (evita repetir la misma consulta)
_cache_dns: Dict[str, bool] = {}


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


class EsperaAdaptativa:
    """Ajusta el tiempo de espera entre peticiones según cómo vaya el buscador.

    Si detecta problemas (búsquedas vacías/bloqueos) sube el ritmo de espera;
    cuando todo va bien lo baja poco a poco hacia el valor base. Así se es más
    prudente solo cuando hace falta.
    """

    def __init__(self, base_min: float, base_max: float,
                 factor: float = 1.5, maximo: float = 4.0) -> None:
        self.base_min = max(0.0, base_min)
        self.base_max = max(self.base_min, base_max)
        self.factor = max(1.0, factor)
        self.maximo = max(1.0, maximo)
        self.multiplicador = 1.0

    def penalizar(self) -> None:
        """Sube el multiplicador (hasta el máximo) tras un problema."""
        self.multiplicador = min(self.maximo, self.multiplicador * self.factor)

    def recuperar(self) -> None:
        """Baja el multiplicador poco a poco hacia 1.0 cuando todo va bien."""
        self.multiplicador = max(1.0, self.multiplicador * 0.85)

    def esperar(self) -> None:
        espera_aleatoria(self.base_min * self.multiplicador,
                         self.base_max * self.multiplicador)


def dominio_resuelve(dom: str) -> bool:
    """Comprueba por DNS si un dominio existe (tiene dirección IP).

    Es 'fail-open': ante un error temporal o de red devuelve True para no
    descartar contactos válidos; solo devuelve False si el nombre NO existe.
    """
    dom = (dom or "").strip().lower().rstrip(".")
    if not dom:
        return False
    if dom in _cache_dns:
        return _cache_dns[dom]
    try:
        socket.getaddrinfo(dom, None)
        ok = True
    except socket.gaierror as e:
        # EAI_NONAME = el nombre no existe -> no resuelve. Otros errores -> fail-open.
        ok = e.errno != socket.EAI_NONAME
    except Exception:
        ok = True
    _cache_dns[dom] = ok
    return ok
