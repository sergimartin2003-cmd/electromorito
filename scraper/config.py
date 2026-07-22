"""Carga y validación de la configuración (config.yaml)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Tuple

import yaml


@dataclass
class Config:
    """Contiene todos los ajustes del scraper con valores por defecto sensatos."""

    motor_busqueda: str = "duckduckgo"
    idioma_region: str = "es-es"

    categorias: List[str] = field(default_factory=list)
    ubicaciones: List[str] = field(default_factory=list)
    busquedas_extra: List[str] = field(default_factory=list)

    resultados_por_busqueda: int = 15
    paginas_por_busqueda: int = 1
    max_paginas_por_web: int = 4
    max_busquedas: int = 0

    navegador_visible: bool = True
    bloquear_recursos: bool = True
    timeout_segundos: int = 30

    espera_min_segundos: float = 2.0
    espera_max_segundos: float = 5.0
    respetar_robots: bool = True

    dominios_excluidos: List[str] = field(default_factory=list)
    archivo_salida: str = "resultados"

    # ------------------------------------------------------------------
    @classmethod
    def cargar(cls, ruta: str = "config.yaml") -> "Config":
        """Lee el YAML y devuelve un objeto Config. Si falta una clave, usa el valor por defecto."""
        if not os.path.exists(ruta):
            raise FileNotFoundError(
                f"No se encuentra el archivo de configuración '{ruta}'. "
                "Copia el config.yaml de ejemplo junto a run.py."
            )
        with open(ruta, "r", encoding="utf-8") as f:
            datos = yaml.safe_load(f) or {}

        conocidas = {c.name for c in cls.__dataclass_fields__.values()}
        filtrado = {k: v for k, v in datos.items() if k in conocidas}
        desconocidas = set(datos) - conocidas
        if desconocidas:
            print(f"  Aviso: claves ignoradas en config.yaml: {', '.join(sorted(desconocidas))}")

        cfg = cls(**filtrado)
        cfg._validar()
        return cfg

    def _validar(self) -> None:
        if self.motor_busqueda not in ("duckduckgo", "bing"):
            raise ValueError(
                f"motor_busqueda '{self.motor_busqueda}' no válido. Usa 'duckduckgo' o 'bing'."
            )
        if self.espera_max_segundos < self.espera_min_segundos:
            self.espera_max_segundos = self.espera_min_segundos
        if not self.categorias and not self.busquedas_extra:
            raise ValueError(
                "No hay nada que buscar: define 'categorias' o 'busquedas_extra' en config.yaml."
            )

    # ------------------------------------------------------------------
    def construir_busquedas(self) -> List[Tuple[str, str]]:
        """Genera la lista de (categoría, texto_de_búsqueda) a partir de la configuración.

        Combina cada categoría con cada ubicación, y añade las búsquedas extra.
        """
        pares: List[Tuple[str, str]] = []
        vistas = set()

        def _add(categoria: str, consulta: str) -> None:
            consulta = " ".join(consulta.split())
            clave = consulta.lower()
            if consulta and clave not in vistas:
                vistas.add(clave)
                pares.append((categoria, consulta))

        if self.ubicaciones:
            for categoria in self.categorias:
                for ubicacion in self.ubicaciones:
                    _add(categoria, f"{categoria} {ubicacion}")
        else:
            for categoria in self.categorias:
                _add(categoria, categoria)

        for consulta in self.busquedas_extra:
            _add("extra", consulta)

        if self.max_busquedas and self.max_busquedas > 0:
            pares = pares[: self.max_busquedas]
        return pares
