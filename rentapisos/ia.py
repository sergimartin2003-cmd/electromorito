"""Enriquecimiento opcional con IA (API de Claude): estima el alquiler y detecta riesgos.

Este módulo es **totalmente opcional**. Si no está instalado el SDK de Anthropic o no
hay credenciales, el programa sigue funcionando con la estimación por zona de siempre
(no falla). Cuando está disponible y se activa (`usar_ia: true` en config.yaml o
`--ia`), para los pisos sin alquiler conocido pide a Claude:

  - una estimación del alquiler mensual a partir de zona, superficie y estado,
  - una detección de riesgos (okupas, derramas, reforma integral, sin ascensor…),
  - un resumen corto y un nivel de confianza.

Se usa `output_config.format` (salida estructurada JSON) para respuestas fiables.
Cualquier error de red/credenciales se captura y se cae a la estimación por zona.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

from .rentabilidad import ParametrosRentabilidad, _a_numero

# Modelo por defecto (el más capaz de la familia Opus). Se puede cambiar en config.yaml.
MODELO_POR_DEFECTO = "claude-opus-4-8"

# Esquema de la respuesta estructurada que pedimos a Claude.
_ESQUEMA = {
    "type": "object",
    "properties": {
        "alquiler_mensual_estimado": {"type": ["integer", "null"]},
        "estado": {
            "type": "string",
            "enum": ["a reformar", "reformado", "obra nueva", "buen estado", ""],
        },
        "resumen": {"type": "string"},
        "riesgos": {"type": "array", "items": {"type": "string"}},
        "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
    },
    "required": ["alquiler_mensual_estimado", "estado", "resumen", "riesgos", "confianza"],
    "additionalProperties": False,
}

_SISTEMA = (
    "Eres un analista de inversión inmobiliaria en España. A partir de los datos de un "
    "anuncio de venta de un piso, estima el ALQUILER MENSUAL de mercado (en euros) que "
    "podría obtenerse por ese piso, teniendo en cuenta la zona, los metros cuadrados, las "
    "habitaciones y el estado. Detecta riesgos relevantes para un inversor (por ejemplo: "
    "ocupado/okupas, derramas o reforma integral pendiente, planta baja o sin ascensor, "
    "problemas legales, precio sospechosamente bajo). Sé prudente y realista; si no puedes "
    "estimar el alquiler con la información dada, devuelve null en ese campo. Responde solo "
    "con el JSON pedido, en español."
)


def ia_disponible() -> bool:
    """True si el SDK de Anthropic está instalado (las credenciales se comprueban al llamar)."""
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return True


def _pistas_zona(params: ParametrosRentabilidad) -> str:
    if not params.rentas_zona:
        return ""
    partes = [f"{zona}: {eur} €/m²·mes" for zona, eur in params.rentas_zona.items()]
    return "Referencias de alquiler por zona (orientativas): " + "; ".join(partes) + ".\n"


def _prompt_piso(fila: dict, params: ParametrosRentabilidad) -> str:
    campos = [
        ("Título", fila.get("titulo") or fila.get("nombre")),
        ("Zona", fila.get("zona") or fila.get("municipio") or fila.get("provincia")),
        ("Precio de venta (€)", fila.get("precio")),
        ("Superficie (m²)", fila.get("superficie")),
        ("Habitaciones", fila.get("habitaciones")),
        ("Descripción", fila.get("descripcion") or fila.get("texto")),
    ]
    lineas = [f"{k}: {v}" for k, v in campos if v not in (None, "")]
    return _pistas_zona(params) + "Datos del anuncio:\n" + "\n".join(lineas)


def estimar_piso_ia(fila: dict, params: ParametrosRentabilidad,
                    modelo: str = MODELO_POR_DEFECTO, cliente=None) -> Optional[dict]:
    """Pide a Claude la estimación y el análisis de un piso. Devuelve un dict o None si falla.

    `cliente` permite inyectar un cliente ya creado (o un doble en los tests).
    """
    try:
        if cliente is None:
            import anthropic
            cliente = anthropic.Anthropic()
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=1024,
            system=_SISTEMA,
            messages=[{"role": "user", "content": _prompt_piso(fila, params)}],
            output_config={"format": {"type": "json_schema", "schema": _ESQUEMA}},
        )
        texto = next((b.text for b in respuesta.content if getattr(b, "type", "") == "text"), "")
        datos = json.loads(texto)
    except Exception:
        return None
    if not isinstance(datos, dict):
        return None
    return datos


def enriquecer_pisos(filas: List[dict], params: ParametrosRentabilidad,
                     modelo: str = MODELO_POR_DEFECTO, cliente=None,
                     log=print) -> int:
    """Completa con IA el alquiler que falte y añade estado/resumen/riesgos a cada anuncio.

    Solo llama a la IA para los pisos SIN alquiler indicado (para acotar el coste).
    Devuelve cuántos pisos se enriquecieron. Modifica las filas en el sitio.
    """
    if cliente is None and not ia_disponible():
        log("  (IA no disponible: instala 'anthropic' y configura la clave. Se usa la estimación por zona.)")
        return 0

    enriquecidos = 0
    for fila in filas:
        if _a_numero(fila.get("alquiler_mensual")):
            continue  # ya tiene alquiler: no gastamos una llamada
        datos = estimar_piso_ia(fila, params, modelo=modelo, cliente=cliente)
        if not datos:
            continue
        alquiler = _a_numero(datos.get("alquiler_mensual_estimado"))
        if alquiler:
            fila["alquiler_mensual"] = int(alquiler)
            fila["alquiler_estimado"] = "sí"
        if datos.get("estado") and not (fila.get("estado") or "").strip():
            fila["estado"] = datos["estado"]
        fila["ia_resumen"] = (datos.get("resumen") or "").strip()
        fila["ia_riesgos"] = "; ".join(datos.get("riesgos") or [])
        fila["ia_confianza"] = datos.get("confianza") or ""
        enriquecidos += 1
    return enriquecidos
