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
# Nota: los separadores internos son solo espacio, punto y guion (NO \s), para
# no unir por error dos números que estén en líneas distintas.
_TEL_CANDIDATO = re.compile(
    r"(?<![\w\d])"
    r"((?:(?:\+|00)\s?34[ .\-]?)?[6789][\d .\-]{7,13}\d)"
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
    # Dominios mal formados (puntos dobles o al principio/fin)
    if ".." in dominio or dominio.startswith(".") or dominio.endswith("."):
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


# --- Clasificación de correos -------------------------------------------
# Proveedores de correo gratuitos (no son un dominio propio de la organización)
_PROVEEDORES_GRATUITOS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.es", "outlook.com",
    "outlook.es", "live.com", "live.es", "yahoo.com", "yahoo.es", "icloud.com",
    "me.com", "aol.com", "gmx.com", "gmx.es", "protonmail.com", "proton.me",
    "yandex.com", "mail.ru", "terra.es", "telefonica.net", "wanadoo.es",
}

# Partes locales típicas de un buzón genérico de organización (ideal para contacto)
_LOCALES_GENERICOS = {
    "info", "contacto", "contact", "hola", "administracion", "administración",
    "admin", "secretaria", "secretaría", "recepcion", "recepción", "oficina",
    "comunicacion", "comunicación", "direccion", "dirección", "gerencia",
    "general", "correo", "atencion", "atención", "clientes", "rrhh", "empleo",
    "prensa", "ventas", "comercial", "soporte", "ayuda", "citas", "reservas",
}


def clasificar_correo(correo: str) -> str:
    """Etiqueta un correo para ayudar a priorizar el contacto.

    Devuelve: 'genérico' (buzón de organización tipo info@),
              'gratuito' (gmail, hotmail…),
              'personal' (parece nombre.apellido),
              'otro'.
    """
    correo = (correo or "").lower().strip()
    local, _, dom = correo.partition("@")
    if not dom:
        return "otro"
    if dom in _PROVEEDORES_GRATUITOS:
        return "gratuito"
    base_local = local.split("+")[0]
    if base_local in _LOCALES_GENERICOS:
        return "genérico"
    if "." in base_local or "_" in base_local:
        return "personal"
    return "otro"


def calcular_relevancia(texto: str, palabras: Iterable[str]) -> int:
    """Cuenta cuántas palabras clave del tema aparecen en el texto (señales de relevancia)."""
    if not texto or not palabras:
        return 0
    t = texto.lower()
    encontradas = 0
    for palabra in palabras:
        palabra = (palabra or "").strip().lower()
        if palabra and palabra in t:
            encontradas += 1
    return encontradas


# --- Código postal (España) ---------------------------------------------
# 5 dígitos cuyos dos primeros son un código de provincia válido (01–52).
_CP_RE = re.compile(r"(?<!\d)(0[1-9]|[1-4]\d|5[0-2])(\d{3})(?!\d)")
# Igual, pero precedido de "C.P.", "CP" o "código postal" (más fiable).
_CP_CONTEXTO_RE = re.compile(
    r"(?:c\.?\s?p\.?|c[oó]digo\s+postal)\D{0,8}((?:0[1-9]|[1-4]\d|5[0-2])\d{3})",
    re.I,
)


def extraer_codigo_postal(texto: str) -> str:
    """Devuelve el primer código postal español plausible, o '' si no hay."""
    if not texto:
        return ""
    m = _CP_CONTEXTO_RE.search(texto)
    if m:
        return m.group(1)
    m = _CP_RE.search(texto)
    if m:
        return m.group(1) + m.group(2)
    return ""


# --- Redes sociales ------------------------------------------------------
_REDES_DOMINIOS = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "youtube.com", "t.me", "wa.me",
)
# Enlaces que NO son un perfil (botones de compartir, login, plugins…)
_REDES_EXCLUIR = (
    "sharer", "share.php", "/share", "intent/", "/plugins/", "dialog/",
    "/login", "/sharer.php", "oauth",
)
_URL_RE = re.compile(r"https?://[^\s\"'<>)]+")


def extraer_redes(html_texto: str) -> List[str]:
    """Devuelve un enlace de perfil por cada red social encontrada (sin botones de compartir)."""
    if not html_texto:
        return []
    encontrados: dict = {}
    for url in _URL_RE.findall(html_texto):
        low = url.lower()
        limpio = low.split("?")[0].rstrip("/")
        for dom in _REDES_DOMINIOS:
            if dom in limpio:
                if any(x in low for x in _REDES_EXCLUIR):
                    break
                # El perfil real tiene algo después del dominio (facebook.com/nombre)
                resto = limpio.split(dom, 1)[1].strip("/")
                if resto:
                    encontrados.setdefault(dom, url.split("?")[0].rstrip("/"))
                break
    return list(encontrados.values())
