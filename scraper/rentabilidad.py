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
    # Hipoteca (para el análisis con apalancamiento). financiacion_pct = 0 => compra al contado.
    financiacion_pct: float = 0.0
    interes_hipoteca: float = 0.03
    anios_hipoteca: int = 25
    # % por debajo de la mediana de €/m² de su zona para marcar un piso como "chollo".
    umbral_chollo: float = 10.0


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


def _a_booleano(valor) -> Optional[bool]:
    """Interpreta 'sí/no/true/false/1/0' (o un bool) desde una columna del CSV."""
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return None
    t = str(valor).strip().lower()
    if t in ("si", "sí", "true", "1", "yes", "con ascensor"):
        return True
    if t in ("no", "false", "0", "sin ascensor"):
        return False
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


def extraer_estado(texto: str) -> str:
    """Deduce el estado del piso: 'a reformar', 'obra nueva', 'reformado', 'buen estado' o ''.

    El orden importa: 'a reformar' tiene prioridad (baja el interés del piso y sube
    el presupuesto), y 'reformado' se distingue de 'para reformar'.
    """
    if not texto:
        return ""
    t = _normalizar(texto)
    if any(f in t for f in ("a reformar", "para reformar", "sin reformar",
                            "necesita reforma", "para actualizar", "a actualizar",
                            "para rehabilitar", "para entrar a reformar")):
        return "a reformar"
    if any(f in t for f in ("obra nueva", "a estrenar", "nueva construccion")):
        return "obra nueva"
    if any(f in t for f in ("reformado", "reformada", "reforma integral",
                            "totalmente reformad", "recien reformad", "semireformad")):
        return "reformado"
    if any(f in t for f in ("buen estado", "buenas condiciones", "perfecto estado",
                            "impecable", "seminuevo")):
        return "buen estado"
    return ""


def tiene_ascensor(texto: str) -> Optional[bool]:
    """True/False si el anuncio menciona (o niega) ascensor; None si no lo dice."""
    if not texto:
        return None
    t = _normalizar(texto)
    if any(f in t for f in ("sin ascensor", "no ascensor", "no dispone de ascensor")):
        return False
    if "ascensor" in t:
        return True
    return None


def extraer_planta(texto: str) -> str:
    """Devuelve la planta del piso ('ático', 'bajo', '3'…) o '' si no se indica."""
    if not texto:
        return ""
    t = _normalizar(texto)
    for palabra, etiqueta in (("sobreatico", "sobreático"), ("atico", "ático"),
                              ("entresuelo", "entresuelo"), ("principal", "principal"),
                              ("bajo", "bajo")):
        if palabra in t:
            return etiqueta
    m = re.search(r"(\d{1,2})\s*[ao]?\s*planta", t) or re.search(r"planta\s*[:\-]?\s*(\d{1,2})", t)
    return m.group(1) if m else ""


def tiene_terraza(texto: str) -> Optional[bool]:
    """True si el anuncio menciona terraza; None si no dice nada."""
    if not texto:
        return None
    return True if "terraza" in _normalizar(texto) else None


def tiene_garaje(texto: str) -> Optional[bool]:
    """True/False si el anuncio menciona (o niega) garaje/parking; None si no lo dice."""
    if not texto:
        return None
    t = _normalizar(texto)
    if any(f in t for f in ("sin garaje", "sin plaza de garaje", "sin parking")):
        return False
    if any(f in t for f in ("garaje", "parking", "plaza de aparcamiento")):
        return True
    return None


def es_exterior(texto: str) -> Optional[bool]:
    """True si es exterior, False si es interior, None si no se indica."""
    if not texto:
        return None
    t = _normalizar(texto)
    if "exterior" in t:
        return True
    if "interior" in t:
        return False
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


def cuota_hipoteca(capital: float, interes_anual: float, anios: int) -> float:
    """Cuota mensual de una hipoteca francesa (cuota constante). 0 si no hay capital."""
    if not capital or capital <= 0 or not anios or anios <= 0:
        return 0.0
    n = int(anios * 12)
    i = interes_anual / 12
    if i <= 0:
        return capital / n
    return capital * i / (1 - (1 + i) ** (-n))


def analizar_apalancamiento(precio: Optional[float], alquiler_mensual: Optional[float],
                            params: ParametrosRentabilidad) -> Optional[dict]:
    """Análisis con hipoteca: fondos propios, cuota, cash-flow y rentabilidad sobre fondos propios.

    Devuelve None si no hay financiación configurada o faltan datos. La rentabilidad
    sobre fondos propios (cash-on-cash) es el cash-flow anual dividido entre el dinero
    que pones de tu bolsillo (entrada + gastos de compra).
    """
    if (not precio or precio <= 0 or not alquiler_mensual or alquiler_mensual <= 0
            or not params.financiacion_pct or params.financiacion_pct <= 0):
        return None
    capital_prestamo = precio * params.financiacion_pct
    entrada = precio - capital_prestamo
    costes_compra = precio * params.costes_compra_pct
    fondos_propios = entrada + costes_compra
    cuota = cuota_hipoteca(capital_prestamo, params.interes_hipoteca, params.anios_hipoteca)
    ingreso_neto_mensual = alquiler_mensual * (1 - params.gastos_pct)
    cash_flow_mensual = ingreso_neto_mensual - cuota
    cash_flow_anual = cash_flow_mensual * 12
    roe = cash_flow_anual / fondos_propios * 100 if fondos_propios > 0 else None
    return {
        "fondos_propios": round(fondos_propios),
        "cuota_hipoteca": round(cuota),
        "cash_flow_mensual": round(cash_flow_mensual),
        "cash_flow_anual": round(cash_flow_anual),
        "rentabilidad_fondos_propios": round(roe, 2) if roe is not None else None,
    }


def price_to_rent(precio: Optional[float],
                  alquiler_mensual: Optional[float]) -> Optional[float]:
    """PER (price-to-rent): años en recuperar la compra = precio ÷ (alquiler × 12)."""
    if not precio or precio <= 0 or not alquiler_mensual or alquiler_mensual <= 0:
        return None
    return round(precio / (alquiler_mensual * 12), 1)


def puntuacion(piso: dict, params: ParametrosRentabilidad) -> Optional[int]:
    """Puntuación compuesta 0–100 para ordenar oportunidades (más alto = mejor).

    Combina, de forma transparente:
      - hasta 60 pts por rentabilidad neta (60 al llegar a `umbral_excelente`),
      - hasta 25 pts por comprar por debajo de la mediana de €/m² de la zona,
      - hasta 15 pts de calidad, restando por 'a reformar' (más presupuesto) y por
        tener el alquiler estimado (dato menos fiable).
    Devuelve None si el piso no tiene rentabilidad calculada.
    """
    neta = piso.get("rentabilidad_neta")
    if neta is None:
        return None
    tope = params.umbral_excelente or 8.0
    pts = max(0.0, min(60.0, neta / tope * 60.0))

    desc = piso.get("descuento_zona")
    if desc is not None and desc > 0:
        pts += min(25.0, desc / 15.0 * 25.0)

    calidad = 15.0
    if piso.get("estado") == "a reformar":
        calidad -= 10.0
    if piso.get("alquiler_estimado"):
        calidad -= 5.0
    pts += max(0.0, calidad)

    return int(round(min(100.0, pts)))


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

    # Datos cualitativos del anuncio (del texto o de columnas propias)
    def _campo_bool(clave, extractor):
        v = fila.get(clave)
        return _a_booleano(v) if v not in (None, "") else extractor(texto)

    estado = (fila.get("estado") or "").strip() or extraer_estado(texto)
    planta = (fila.get("planta") or "").strip() or extraer_planta(texto)
    ascensor = _campo_bool("ascensor", tiene_ascensor)
    terraza = _campo_bool("terraza", tiene_terraza)
    garaje = _campo_bool("garaje", tiene_garaje)
    exterior = _campo_bool("exterior", es_exterior)

    apalancamiento = analizar_apalancamiento(precio, alquiler, params) or {}

    return {
        "titulo": (fila.get("titulo") or fila.get("nombre") or "").strip(),
        "url": (fila.get("url") or fila.get("web") or "").strip(),
        "zona": zona,
        "precio": int(precio) if precio else None,
        "superficie": superficie,
        "precio_m2": precio_m2,
        "mediana_zona_m2": None,   # lo rellena el orquestador con el dataset completo
        "descuento_zona": None,
        "es_chollo": False,
        "habitaciones": habitaciones,
        "estado": estado,
        "planta": planta,
        "ascensor": ascensor,
        "terraza": terraza,
        "garaje": garaje,
        "exterior": exterior,
        "alquiler_mensual": int(alquiler) if alquiler else None,
        "alquiler_estimado": estimado,
        "rentabilidad_bruta": round(bruta, 2) if bruta is not None else None,
        "rentabilidad_neta": round(neta, 2) if neta is not None else None,
        "per": price_to_rent(precio, alquiler),
        "clasificacion": clasificar_rentabilidad(neta, params),
        "cuota_hipoteca": apalancamiento.get("cuota_hipoteca"),
        "cash_flow_mensual": apalancamiento.get("cash_flow_mensual"),
        "rentabilidad_fondos_propios": apalancamiento.get("rentabilidad_fondos_propios"),
        "fondos_propios": apalancamiento.get("fondos_propios"),
        "puntuacion": None,        # lo rellena el orquestador (depende del descuento de zona)
        "completo": neta is not None,
    }
