"""Genera una lista depurada de contactos (una fila por organización) para envío.

A partir de las filas del CSV (una por correo), agrupa por organización, elige el
MEJOR correo de cada una (prioriza buzones genéricos tipo info@) y produce una lista
lista para una campaña de contacto en frío.
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional

CAMPOS_CONTACTOS = [
    "nombre", "correo_principal", "todos_los_correos", "telefonos",
    "provincia", "web", "relevancia",
]

# Preferencia de tipo de correo para elegir el principal (menor = mejor)
_ORDEN_TIPO = {"genérico": 0, "generico": 0, "personal": 1, "otro": 2, "gratuito": 3, "": 4}


def _rel(fila: dict) -> int:
    try:
        return int(fila.get("relevancia") or 0)
    except (TypeError, ValueError):
        return 0


def _rango(fila: dict) -> tuple:
    """Ordena de mejor a peor: primero con correo, luego mejor tipo, luego más relevancia."""
    tiene_correo = 1 if (fila.get("correo") or "").strip() else 0
    tipo = (fila.get("tipo_correo") or "").strip().lower()
    return (-tiene_correo, _ORDEN_TIPO.get(tipo, 5), -_rel(fila))


def _primero(filas: List[dict], campo: str) -> str:
    for f in filas:
        v = (f.get(campo) or "").strip()
        if v:
            return v
    return ""


def construir_contactos(filas: List[dict], min_relevancia: int = 0) -> List[dict]:
    """Agrupa las filas por organización y devuelve un contacto por organización.

    Solo incluye organizaciones con al menos un correo. Ordena por relevancia
    (de mayor a menor) y descarta las que no llegan a `min_relevancia`.
    """
    grupos: Dict[str, List[dict]] = {}
    for f in filas:
        clave = (f.get("grupo") or f.get("dominio") or f.get("web") or "").strip().lower()
        if not clave:
            clave = (f.get("correo") or "").strip().lower()
        if clave:
            grupos.setdefault(clave, []).append(f)

    contactos: List[dict] = []
    for filas_grupo in grupos.values():
        ordenadas = sorted(filas_grupo, key=_rango)
        correos = list(dict.fromkeys(
            (f.get("correo") or "").strip().lower()
            for f in ordenadas if (f.get("correo") or "").strip()
        ))
        if not correos:
            continue  # sin correo no sirve para envío por email
        relevancia = max((_rel(f) for f in filas_grupo), default=0)
        if relevancia < min_relevancia:
            continue
        contactos.append({
            "nombre": _primero(ordenadas, "nombre"),
            "correo_principal": correos[0],
            "todos_los_correos": "; ".join(correos),
            "telefonos": _primero(ordenadas, "telefonos"),
            "provincia": _primero(ordenadas, "provincia"),
            "web": _primero(ordenadas, "web"),
            "relevancia": str(relevancia),
        })

    contactos.sort(key=lambda c: (-int(c["relevancia"] or 0), c["nombre"].lower()))
    return contactos


def _leer_csv(ruta_csv: str) -> List[dict]:
    with open(ruta_csv, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def exportar_contactos(
    filas_o_csv, ruta_salida: str, min_relevancia: int = 0
) -> Optional[int]:
    """Escribe la lista de contactos en `ruta_salida` (CSV). Devuelve cuántos, o None.

    `filas_o_csv` puede ser una lista de filas o la ruta de un CSV existente.
    """
    if isinstance(filas_o_csv, str):
        if not os.path.exists(filas_o_csv):
            return None
        filas = _leer_csv(filas_o_csv)
    else:
        filas = list(filas_o_csv)

    contactos = construir_contactos(filas, min_relevancia=min_relevancia)
    with open(ruta_salida, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_CONTACTOS)
        writer.writeheader()
        writer.writerows(contactos)
    return len(contactos)
