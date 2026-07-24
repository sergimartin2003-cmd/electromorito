"""Fuentes de datos de anuncios: punto de extensión para alimentar el motor.

El motor de rentabilidad trabaja sobre una lista de "anuncios" (dicts) con el esquema
descrito en docs/fuentes_de_datos.md. Cualquier origen que sepa producir esa lista
encaja sin tocar el motor. Aquí se define la interfaz `Fuente`, un normalizador de
nombres de campo (`normalizar_anuncio`) y una implementación de referencia sobre
ficheros (`FuenteArchivo`), más esbozos documentados de fuentes legales para producción
(API de idealista, feeds de inmobiliarias).

IMPORTANTE: no scrapees los grandes portales (lo prohíben). Usa una fuente con la que
tengas derecho: la API oficial, feeds, o datos públicos. Ver docs/fuentes_de_datos.md.
"""

from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from typing import List, Optional

from .pisos import cargar_pisos


# --- Normalización de nombres de campo -----------------------------------
def _clave(texto: str) -> str:
    """Normaliza el nombre de una columna: minúsculas, sin tildes ni signos."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", t.lower())


# Nombres alternativos habituales (en forma normalizada) -> campo canónico del motor
ALIAS = {
    "url": "url", "enlace": "url", "link": "url", "anuncio": "url",
    "titulo": "titulo", "nombre": "titulo", "direccion": "titulo",
    "zona": "zona", "ciudad": "zona", "municipio": "zona", "poblacion": "zona",
    "localidad": "zona", "barrio": "zona",
    "provincia": "provincia",
    "precio": "precio", "precioventa": "precio", "importe": "precio", "price": "precio",
    "superficie": "superficie", "superficieconstruida": "superficie", "m2": "superficie",
    "metros": "superficie", "metroscuadrados": "superficie", "size": "superficie",
    "habitaciones": "habitaciones", "dormitorios": "habitaciones", "hab": "habitaciones",
    "dorm": "habitaciones", "rooms": "habitaciones",
    "alquilermensual": "alquiler_mensual", "alquiler": "alquiler_mensual",
    "renta": "alquiler_mensual", "rent": "alquiler_mensual",
    "estado": "estado", "condicion": "estado",
    "descripcion": "descripcion", "texto": "descripcion", "description": "descripcion",
}


def normalizar_anuncio(dic: dict, alias: Optional[dict] = None) -> dict:
    """Traduce los nombres de campo de un anuncio al esquema canónico del motor.

    Los campos desconocidos se conservan con su nombre original. Así se pueden enchufar
    feeds o exports con columnas tipo 'm2', 'dormitorios', 'precio_venta', 'enlace'…
    """
    alias = alias or ALIAS
    salida: dict = {}
    for clave, valor in dic.items():
        canon = alias.get(_clave(clave)) or (clave or "").strip()
        # No pisar un valor ya presente con uno vacío que llegue después
        if canon not in salida or (salida.get(canon) in (None, "") and valor not in (None, "")):
            salida[canon] = valor
    return salida


# --- Interfaz de fuente ---------------------------------------------------
class Fuente(ABC):
    """Un origen de anuncios. Implementa `anuncios()` devolviendo el esquema del motor."""

    @abstractmethod
    def anuncios(self) -> List[dict]:
        """Devuelve la lista de anuncios (dicts) lista para el motor de rentabilidad."""
        raise NotImplementedError


class FuenteArchivo(Fuente):
    """Fuente de referencia (ya funcional): un CSV, JSON o XLSX en disco.

    Con `normalizar=True` traduce los nombres de columna al esquema canónico.
    """

    def __init__(self, ruta: str, normalizar: bool = False) -> None:
        self.ruta = ruta
        self.normalizar = normalizar

    def anuncios(self) -> List[dict]:
        filas = cargar_pisos(self.ruta)
        return [normalizar_anuncio(f) for f in filas] if self.normalizar else filas


class FuenteIdealistaAPI(Fuente):
    """Esbozo: API oficial de idealista (https://developers.idealista.com).

    Para producción: date de alta para obtener `apikey` + `secret`, pide un token
    OAuth2 y llama al servicio de búsqueda de inmuebles respetando el cupo del plan.
    Implementa `anuncios()` mapeando cada inmueble de la respuesta al esquema del motor
    (precio→precio, size→superficie, rooms→habitaciones, url→url…), p. ej. con
    `normalizar_anuncio`. Ver docs/fuentes_de_datos.md §3.1.
    """

    def __init__(self, apikey: str, secret: str, **filtros) -> None:
        self.apikey = apikey
        self.secret = secret
        self.filtros = filtros

    def anuncios(self) -> List[dict]:
        raise NotImplementedError(
            "Fuente de la API de idealista no implementada. Da de alta tus credenciales en "
            "https://developers.idealista.com, obtén el token OAuth2 y mapea la respuesta al "
            "esquema del motor. Guía en docs/fuentes_de_datos.md."
        )


class FuenteFeedInmobiliaria(Fuente):
    """Esbozo: feed XML/JSON de una inmobiliaria o CRM (con derecho de uso).

    Implementa `anuncios()` leyendo el feed y mapeando sus campos con
    `normalizar_anuncio`. Ver docs/fuentes_de_datos.md §3.2.
    """

    def __init__(self, ruta_o_url: str) -> None:
        self.ruta_o_url = ruta_o_url

    def anuncios(self) -> List[dict]:
        raise NotImplementedError(
            "Fuente de feed de inmobiliaria no implementada. Lee el feed (XML/JSON) y mapea "
            "sus campos al esquema del motor con normalizar_anuncio(). Ver docs/fuentes_de_datos.md."
        )
