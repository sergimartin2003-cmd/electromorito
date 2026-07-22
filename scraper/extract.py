"""Extracción y limpieza de correos, teléfonos y nombres a partir del contenido de una web."""

from __future__ import annotations

import html
import re
from typing import Iterable, List, Optional

# --- Correos electrónicos ------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")

# Extensiones de archivo que delatan que un "correo" es en realidad una imagen/recurso
_ASSET_EXT = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico",
    ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".pdf", ".zip",
)

# Dominios que no corresponden a correos de contacto reales (ejemplos, plantillas, trackers…)
_DOMINIOS_RUIDO = {
    "example.com", "example.org", "example.net", "domain.com", "email.com",
    "yourdomain.com", "your-email.com", "tudominio.com", "tuempresa.com",
    "sentry.io", "wixpress.com", "wix.com", "godaddy.com", "w3.org",
    "schema.org", "googleapis.com", "gstatic.com", "cloudflare.com",
    "test.com", "correo.com", "nombre.com", "dominio.com", "mail.com",
    "sentry.wixpress.com", "core.trace.moz.com",
}

# Partes locales genéricas de ejemplos ("nombre@…", "tucorreo@…")
_LOCAL_RUIDO = {
    "email", "correo", "tucorreo", "tuemail", "nombre", "usuario", "user",
    "name", "example", "ejemplo", "sentry", "no-reply", "noreply",
}

# --- Teléfonos (formato español) ----------------------------------------
# Captura un "candidato" a teléfono: prefijo opcional +34/0034 y 9 dígitos que
# empiezan por 6,7,8 o 9, permitiendo separadores (espacio, punto, guion).
# Los límites (?<![\w\d]) / (?![\w\d]) evitan cazar trozos dentro de hashes o
# de números más largos (checksums, identificadores, etc.).
_TEL_CANDIDATO = re.compile(
    r"(?<![\w\d])"
    r"((?:(?:\+|00)\s?34[\s.\-]?)?[6789][\d\s.\-]{7,13}\d)"
    r"(?![\w\d])"
)


def _desofuscar(texto: str) -> str:
    """Convierte correos "camuflados" a su forma normal.

    Maneja entidades HTML (&#64;) y trucos anti-spam como  nombre [at] dominio [dot] com.
    """
    t = html.unescape(texto)
    # nombre [at] dominio  /  nombre (arroba) dominio
    t = re.sub(r"(\w)\s*[\[\(\{]\s*(?:at|arroba)\s*[\]\)\}]\s*(\w)", r"\1@\2", t, flags=re.I)
    # dominio [dot] com  /  dominio (punto) com
    t = re.sub(r"(\w)\s*[\[\(\{]\s*(?:dot|punto)\s*[\]\)\}]\s*(\w)", r"\1.\2", t, flags=re.I)
    # nombre arroba dominio  (palabra suelta entre caracteres)
    t = re.sub(r"(\w)\s+arroba\s+(\w)", r"\1@\2", t, flags=re.I)
    t = re.sub(r"(\w)\s+punto\s+(\w)", r"\1.\2", t, flags=re.I)
    return t


def _correo_valido(correo: str) -> bool:
    correo = correo.strip().strip(".").lower()
    if not correo or "@" not in correo:
        return False
    if correo.endswith(_ASSET_EXT):
        return False
    if len(correo) > 100:
        return False
    local, _, dominio = correo.partition("@")
    if not local or not dominio or "." not in dominio:
        return False
    if dominio in _DOMINIOS_RUIDO or local in _LOCAL_RUIDO:
        return False
    tld = dominio.rsplit(".", 1)[-1]
    if len(tld) < 2 or tld.isdigit():
        return False
    # Descarta cadenas tipo hash/versionado (u003e, sha256…) con muchos números en el dominio
    if any(c.isdigit() for c in dominio) and sum(c.isdigit() for c in dominio) > len(dominio) / 2:
        return False
    return True


def extraer_correos(contenido: str, mailtos: Optional[Iterable[str]] = None) -> List[str]:
    """Devuelve la lista ordenada y sin duplicados de correos encontrados.

    - `contenido`: HTML y/o texto visible de la página.
    - `mailtos`:   valores de enlaces  <a href="mailto:...">  (más fiables).
    """
    encontrados = set()

    for direccion in (mailtos or []):
        if not direccion:
            continue
        direccion = direccion.replace("mailto:", "").split("?")[0].strip()
        # Un enlace mailto puede llevar varias direcciones separadas por comas
        for parte in direccion.split(","):
            parte = parte.strip().lower()
            if _correo_valido(parte):
                encontrados.add(parte.strip(".").lower())

    fuente = _desofuscar(contenido or "")
    for m in _EMAIL_RE.findall(fuente):
        if _correo_valido(m):
            encontrados.add(m.strip(".").lower())

    return sorted(encontrados)


def _quita_prefijo_es(digitos: str) -> str:
    """Elimina el prefijo internacional de España (+34 -> 11 díg., 0034 -> 13 díg.)."""
    if len(digitos) == 13 and digitos.startswith("0034"):
        return digitos[4:]
    if len(digitos) == 11 and digitos.startswith("34"):
        return digitos[2:]
    return digitos


def _normaliza_telefono(crudo: str) -> Optional[str]:
    """Valida un candidato y lo devuelve como 'XXX XX XX XX', o None si no es válido."""
    tiene_prefijo = bool(re.match(r"\s*(?:\+|00)\s?34", crudo))
    tiene_separador = bool(re.search(r"[\s.\-]", crudo.strip()))
    digitos = _quita_prefijo_es(re.sub(r"\D", "", crudo))
    if len(digitos) != 9 or digitos[0] not in "6789":
        return None
    # Un bloque de 9 dígitos pegados, sin +34 ni separadores, es demasiado
    # ambiguo (puede ser un identificador): se descarta salvo que venga de tel:.
    if not (tiene_prefijo or tiene_separador):
        return None
    return f"{digitos[:3]} {digitos[3:5]} {digitos[5:7]} {digitos[7:9]}"


def extraer_telefonos(texto: str, tels_href: Optional[Iterable[str]] = None) -> List[str]:
    """Devuelve teléfonos españoles normalizados como 'XXX XX XX XX'.

    - `texto`:      texto visible de la página.
    - `tels_href`:  valores de enlaces  <a href="tel:...">  (muy fiables).
    """
    telefonos = set()

    for href in (tels_href or []):
        digitos = _quita_prefijo_es(re.sub(r"\D", "", (href or "").replace("tel:", "")))
        if len(digitos) == 9 and digitos[0] in "6789":
            telefonos.add(f"{digitos[:3]} {digitos[3:5]} {digitos[5:7]} {digitos[7:9]}")

    for crudo in _TEL_CANDIDATO.findall(texto or ""):
        normalizado = _normaliza_telefono(crudo)
        if normalizado:
            telefonos.add(normalizado)

    return sorted(telefonos)


def limpiar_nombre(titulo: Optional[str]) -> str:
    """Limpia el título de una página para obtener un nombre de organización más presentable."""
    if not titulo:
        return ""
    nombre = " ".join(titulo.split())
    # Corta en el primer separador habitual de títulos (« | », « - », « – », « » »)
    for sep in ("|", "•", "·", "—", "–", " - ", " » ", " :: "):
        if sep in nombre:
            partes = [p.strip() for p in nombre.split(sep) if p.strip()]
            if partes:
                # Nos quedamos con el fragmento más largo (suele ser el nombre real)
                nombre = max(partes, key=len)
            break
    # Elimina coletillas típicas al final
    nombre = re.sub(r"\s*[-|]?\s*(inicio|home|bienvenidos?|welcome)\s*$", "", nombre, flags=re.I)
    return nombre.strip()[:150]
