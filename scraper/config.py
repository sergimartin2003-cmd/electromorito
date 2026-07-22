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

    # Palabras que indican que la web trata del tema buscado (para puntuar relevancia)
    palabras_relevancia: List[str] = field(default_factory=list)
    # Si es True, no guarda organizaciones cuya relevancia sea 0
    guardar_solo_relevantes: bool = False

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

        if not isinstance(datos, dict):
            raise ValueError(
                "El archivo config.yaml no tiene el formato esperado "
                "(debe ser una lista de 'clave: valor')."
            )

        conocidas = {c.name for c in cls.__dataclass_fields__.values()}
        filtrado = {k: v for k, v in datos.items() if k in conocidas}
        desconocidas = set(datos) - conocidas
        if desconocidas:
            print(f"  Aviso: claves ignoradas en config.yaml: {', '.join(sorted(desconocidas))}")

        cfg = cls(**filtrado)
        cfg._validar()
        return cfg

    def _validar(self) -> None:
        # Las listas escritas vacías en YAML quedan como None: las normalizamos.
        for campo in ("categorias", "ubicaciones", "busquedas_extra",
                      "dominios_excluidos", "palabras_relevancia"):
            valor = getattr(self, campo)
            if valor is None:
                setattr(self, campo, [])
            elif not isinstance(valor, list):
                setattr(self, campo, [str(valor)])
            else:
                setattr(
                    self,
                    campo,
                    [str(v).strip() for v in valor if v is not None and str(v).strip()],
                )

        # Números y booleanos: el usuario podría escribirlos como texto en el YAML.
        self.resultados_por_busqueda = _entero(self.resultados_por_busqueda, 15, minimo=1)
        self.paginas_por_busqueda = _entero(self.paginas_por_busqueda, 1, minimo=1)
        self.max_paginas_por_web = _entero(self.max_paginas_por_web, 4, minimo=1)
        self.max_busquedas = _entero(self.max_busquedas, 0, minimo=0)
        self.timeout_segundos = _entero(self.timeout_segundos, 30, minimo=5)
        self.espera_min_segundos = _decimal(self.espera_min_segundos, 2.0, minimo=0.0)
        self.espera_max_segundos = _decimal(self.espera_max_segundos, 5.0, minimo=0.0)
        self.navegador_visible = _booleano(self.navegador_visible, True)
        self.bloquear_recursos = _booleano(self.bloquear_recursos, True)
        self.respetar_robots = _booleano(self.respetar_robots, True)
        self.guardar_solo_relevantes = _booleano(self.guardar_solo_relevantes, False)

        self.motor_busqueda = str(self.motor_busqueda).strip().lower()
        if self.motor_busqueda not in ("duckduckgo", "bing"):
            raise ValueError(
                f"motor_busqueda '{self.motor_busqueda}' no válido. Usa 'duckduckgo' o 'bing'."
            )
        if self.espera_max_segundos < self.espera_min_segundos:
            self.espera_max_segundos = self.espera_min_segundos
        if not self.archivo_salida or not str(self.archivo_salida).strip():
            self.archivo_salida = "resultados"
        self.archivo_salida = str(self.archivo_salida).strip()
        if not self.categorias and not self.busquedas_extra:
            raise ValueError(
                "No hay nada que buscar: define 'categorias' o 'busquedas_extra' en config.yaml."
            )

    # ------------------------------------------------------------------
    def construir_busquedas(self) -> List[Tuple[str, str, str]]:
        """Genera la lista de (categoría, provincia, texto_de_búsqueda).

        Combina cada categoría con cada ubicación, y añade las búsquedas extra
        (con provincia vacía).
        """
        pares: List[Tuple[str, str, str]] = []
        vistas = set()

        def _add(categoria: str, provincia: str, consulta: str) -> None:
            consulta = " ".join(consulta.split())
            clave = consulta.lower()
            if consulta and clave not in vistas:
                vistas.add(clave)
                pares.append((categoria, provincia, consulta))

        if self.ubicaciones:
            for categoria in self.categorias:
                for ubicacion in self.ubicaciones:
                    _add(categoria, ubicacion, f"{categoria} {ubicacion}")
        else:
            for categoria in self.categorias:
                _add(categoria, "", categoria)

        for consulta in self.busquedas_extra:
            _add("extra", "", consulta)

        if self.max_busquedas and self.max_busquedas > 0:
            pares = pares[: self.max_busquedas]
        return pares


# --- Coerción de tipos desde el YAML (tolerante con errores del usuario) -----
def _entero(valor, por_defecto: int, minimo: int | None = None) -> int:
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        return por_defecto
    if minimo is not None and n < minimo:
        return minimo
    return n


def _decimal(valor, por_defecto: float, minimo: float | None = None) -> float:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return por_defecto
    if minimo is not None and n < minimo:
        return minimo
    return n


def _booleano(valor, por_defecto: bool) -> bool:
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return por_defecto
    texto = str(valor).strip().lower()
    if texto in ("true", "si", "sí", "yes", "1", "on", "verdadero"):
        return True
    if texto in ("false", "no", "0", "off", "falso"):
        return False
    return por_defecto
