"""Motor de rentabilidad de pisos: extrae datos de un anuncio y calcula su rentabilidad.

Todo lo de este módulo es lógica **pura** (sin navegador ni internet), así que se
puede probar con tests. A partir del precio de venta, la superficie y el alquiler
(dado o estimado por zona) calcula la rentabilidad **bruta** y **neta** del alquiler,
y clasifica el piso para poder ordenar los mejores primero.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Optional


# --- Parámetros del cálculo ----------------------------------------------
@dataclass
class ParametrosRentabilidad:
    """Supuestos económicos del cálculo (editables desde config.yaml).

    - `gastos_pct`: fracción del alquiler bruto que se va en gastos recurrentes
      (IBI, comunidad, seguro, mantenimiento, gestión y vacancia). 0.25 = 25 %.
    - `costes_compra_pct`: fracción sobre el precio por impuestos y gastos de
      compra (ITP/IVA, notaría, registro, agencia). 0.11 = 11 %.
    - `rentas_zona`: alquiler de referencia en €/m²/mes por zona, para estimar el
      alquiler cuando el anuncio no lo trae. Ej.: {"Barcelona": 14, "Madrid": 15}.
    - `umbral_*`: cortes (en % de rentabilidad neta) para clasificar cada piso.
    """

    gastos_pct: float = 0.25
    costes_compra_pct: float = 0.11
    rentas_zona: Dict[str, float] = field(default_factory=dict)
    umbral_excelente: float = 8.0
    umbral_buena: float = 6.0
    umbral_correcta: float = 4.0


# --- Lectura de números tolerante (formato español) ----------------------
def _a_numero(valor) -> Optional[float]:
    """Convierte un valor (número o texto) a float, entendiendo el formato español.

    Acepta '180.000', '180.000 €', '90,5 m²', 180000, 90.5… y devuelve el número
    o None si no hay ninguno. El punto se interpreta como separador de miles y la
    coma como decimal (salvo que un punto suelto sea claramente un decimal).
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    m = re.search(r"\d[\d.,\s]*", s)
    if not m:
        return None
    num = re.sub(r"\s", "", m.group(0)).strip(".,")
    if not num:
        return None
    if "," in num:
        # La coma es el decimal; los puntos son separadores de miles.
        num = num.replace(".", "").replace(",", ".")
    elif "." in num:
        partes = num.split(".")
        # Si todos los grupos tras el primer punto tienen 3 cifras, son miles.
        if all(len(p) == 3 for p in partes[1:]):
            num = num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


# --- Extracción desde el texto libre de un anuncio -----------------------
# Un importe en euros: 180.000 € / 180000€ / 195.000 euros
_PRECIO_MONEDA_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d{4,7})\s*(?:€|eur\b|euros?\b)", re.I
)
# … o precedido de la palabra "precio"
_PRECIO_CONTEXTO_RE = re.compile(
    r"precio\D{0,12}?(\d{1,3}(?:\.\d{3})+|\d{4,7})", re.I
)
# Superficie en metros: 90 m² / 90m2 / 90 metros cuadrados
_SUPERFICIE_RE = re.compile(
    r"(\d{2,4}(?:[.,]\d{1,2})?)\s*(?:m²|m2|metros?\s+cuadrados?|metros?)\b", re.I
)
# Habitaciones / dormitorios: 3 habitaciones / 3 hab / 3 dormitorios
_HABITACIONES_RE = re.compile(
    r"(\d{1,2})\s*(?:habitaci|dormitori|hab\b|dorm\b)", re.I
)


def extraer_precio(texto: str) -> Optional[int]:
    """Devuelve el precio de venta (€) más plausible del texto, o None."""
    if not texto:
        return None
    candidatos = [_a_numero(m.group(1)) for m in _PRECIO_MONEDA_RE.finditer(texto)]
    if not any(candidatos):
        m = _PRECIO_CONTEXTO_RE.search(texto)
        if m:
            candidatos.append(_a_numero(m.group(1)))
    validos = [c for c in candidatos if c and 10_000 <= c <= 9_999_999]
    return int(max(validos)) if validos else None


def extraer_superficie(texto: str) -> Optional[float]:
    """Devuelve la superficie en m² más plausible del texto, o None."""
    if not texto:
        return None
    for m in _SUPERFICIE_RE.finditer(texto):
        valor = _a_numero(m.group(1))
        if valor and 10 <= valor <= 3000:
            return valor
    return None


def extraer_habitaciones(texto: str) -> Optional[int]:
    """Devuelve el número de habitaciones/dormitorios del texto, o None."""
    if not texto:
        return None
    m = _HABITACIONES_RE.search(texto)
    if m:
        n = int(m.group(1))
        if 0 <= n <= 20:
            return n
    return None


# --- Estimación del alquiler por zona ------------------------------------
def _normalizar(texto: str) -> str:
    """Minúsculas sin tildes ni signos, para comparar zonas de forma flexible."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())


def _es_sublista(sub: list, lista: list) -> bool:
    """True si `sub` aparece como secuencia contigua de palabras dentro de `lista`."""
    n, m = len(sub), len(lista)
    if n == 0 or n > m:
        return False
    return any(lista[i:i + n] == sub for i in range(m - n + 1))


def estimar_alquiler(superficie: Optional[float], zona: str,
                     params: ParametrosRentabilidad) -> Optional[float]:
    """Estima el alquiler mensual (€) = superficie × €/m²·mes de la zona, o None.

    Empareja la zona del piso con la tabla `rentas_zona` por palabras completas:
    la clave encaja si sus palabras aparecen (en orden y contiguas) dentro de la
    zona del anuncio. Así "Madrid" no se confunde con "Madridejos", y si encajan
    varias claves gana la más específica (la de más palabras).
    """
    if not superficie or superficie <= 0 or not params.rentas_zona:
        return None
    z_tokens = _normalizar(zona).split()
    if not z_tokens:
        return None
    mejor: Optional[float] = None
    mejor_long = -1
    for clave, eur_m2 in params.rentas_zona.items():
        k_tokens = _normalizar(str(clave)).split()
        precio_m2 = _a_numero(eur_m2)
        if not k_tokens or not precio_m2:
            continue
        if _es_sublista(k_tokens, z_tokens) and len(k_tokens) > mejor_long:
            mejor = precio_m2
            mejor_long = len(k_tokens)
    if mejor is None:
        return None
    return round(superficie * mejor)


# --- Cálculo de rentabilidad ---------------------------------------------
def rentabilidad_bruta(precio: Optional[float],
                       alquiler_mensual: Optional[float]) -> Optional[float]:
    """Rentabilidad bruta anual (%) = (alquiler × 12) ÷ precio × 100."""
    if not precio or precio <= 0 or not alquiler_mensual or alquiler_mensual <= 0:
        return None
    return alquiler_mensual * 12 / precio * 100


def rentabilidad_neta(precio: Optional[float], alquiler_mensual: Optional[float],
                      params: ParametrosRentabilidad) -> Optional[float]:
    """Rentabilidad neta anual (%): descuenta gastos del alquiler y costes de compra.

    neta = (alquiler·12·(1−gastos_pct)) ÷ (precio·(1+costes_compra_pct)) × 100
    """
    if not precio or precio <= 0 or not alquiler_mensual or alquiler_mensual <= 0:
        return None
    ingreso_neto = alquiler_mensual * 12 * (1 - params.gastos_pct)
    coste_total = precio * (1 + params.costes_compra_pct)
    if coste_total <= 0:
        return None
    return ingreso_neto / coste_total * 100


def clasificar_rentabilidad(pct: Optional[float],
                            params: ParametrosRentabilidad) -> str:
    """Etiqueta la rentabilidad neta: 'excelente', 'buena', 'correcta', 'baja' o 'sin datos'."""
    if pct is None:
        return "sin datos"
    if pct >= params.umbral_excelente:
        return "excelente"
    if pct >= params.umbral_buena:
        return "buena"
    if pct >= params.umbral_correcta:
        return "correcta"
    return "baja"


def evaluar_piso(fila: dict, params: ParametrosRentabilidad) -> dict:
    """Toma un anuncio (dict) y devuelve sus datos enriquecidos con la rentabilidad.

    Campos de entrada aceptados (todos opcionales salvo lo necesario para el cálculo):
      titulo/nombre, url/web, zona/municipio/provincia, precio, superficie,
      habitaciones, alquiler_mensual, y texto/descripcion (de donde se extraen
      precio/superficie/habitaciones si no vienen sueltos).
    """
    texto = " ".join(
        str(fila.get(c, "")) for c in ("titulo", "nombre", "descripcion", "texto")
    )

    precio = _a_numero(fila.get("precio")) or extraer_precio(texto)
    superficie = _a_numero(fila.get("superficie")) or extraer_superficie(texto)

    habitaciones = _a_numero(fila.get("habitaciones"))
    habitaciones = int(habitaciones) if habitaciones else extraer_habitaciones(texto)

    zona = (fila.get("zona") or fila.get("municipio") or fila.get("provincia") or "").strip()

    alquiler = _a_numero(fila.get("alquiler_mensual"))
    estimado = False
    if not alquiler:
        alquiler = estimar_alquiler(superficie, zona, params)
        estimado = alquiler is not None

    bruta = rentabilidad_bruta(precio, alquiler)
    neta = rentabilidad_neta(precio, alquiler, params)
    precio_m2 = round(precio / superficie) if (precio and superficie) else None

    return {
        "titulo": (fila.get("titulo") or fila.get("nombre") or "").strip(),
        "url": (fila.get("url") or fila.get("web") or "").strip(),
        "zona": zona,
        "precio": int(precio) if precio else None,
        "superficie": superficie,
        "precio_m2": precio_m2,
        "habitaciones": habitaciones,
        "alquiler_mensual": int(alquiler) if alquiler else None,
        "alquiler_estimado": estimado,
        "rentabilidad_bruta": round(bruta, 2) if bruta is not None else None,
        "rentabilidad_neta": round(neta, 2) if neta is not None else None,
        "clasificacion": clasificar_rentabilidad(neta, params),
        "completo": neta is not None,
    }
