"""Carga y validación de la configuración (config.yaml) del análisis de rentabilidad."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml


@dataclass
class Config:
    """Ajustes del análisis de rentabilidad de pisos, con valores por defecto sensatos."""

    # Nombre base de los ficheros de salida (<archivo_salida>_pisos.csv/.html/.md)
    archivo_salida: str = "resultados"

    # €/m²/mes de referencia por zona, para estimar el alquiler cuando el anuncio
    # no lo trae. Ej.: {"Barcelona": 14, "Madrid": 15}
    rentas_zona: dict = field(default_factory=dict)
    # Fracción del alquiler bruto que se va en gastos (IBI, comunidad, seguro,
    # mantenimiento, gestión, vacancia). 0.25 = 25 %.
    gastos_pct: float = 0.25
    # Fracción sobre el precio por impuestos y gastos de compra (ITP/IVA,
    # notaría, registro, agencia). 0.11 = 11 %.
    costes_compra_pct: float = 0.11
    # Hipoteca (análisis con apalancamiento). financiacion_pct = 0 => compra al contado.
    financiacion_pct: float = 0.0
    interes_hipoteca: float = 0.03
    anios_hipoteca: int = 25
    # % por debajo de la mediana de €/m² de su zona para marcar un piso como "chollo".
    umbral_chollo: float = 10.0
    # Proyección a futuro: revalorización anual del precio y horizonte (años).
    revalorizacion_anual: float = 0.0
    horizonte_anios: int = 10
    # Escenario de estrés: % de bajada de alquiler para una rentabilidad "pesimista".
    estres_alquiler_pct: float = 0.0
    # Rentabilidad neta objetivo (%). Si > 0, calcula el precio de compra al que cada
    # piso la alcanzaría (precio objetivo / break-even). 0 = desactivado.
    rentabilidad_objetivo: float = 0.0
    # IRPF: tipo marginal (0.30 = 30 %) y reducción del rendimiento neto por alquiler de
    # vivienda habitual (0.60 = 60 %). Con tipo_irpf > 0 se calcula la rentabilidad neta
    # después de impuestos. 0 = desactivado.
    tipo_irpf: float = 0.0
    reduccion_irpf: float = 0.60
    # Usar la tabla de rentas de referencia integrada cuando falte la zona en rentas_zona.
    usar_rentas_referencia: bool = True
    # IA opcional (API de Claude) para estimar el alquiler y detectar riesgos.
    usar_ia: bool = False
    modelo_ia: str = "claude-opus-4-8"

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
        cfg = cls(**filtrado)
        cfg._validar()
        return cfg

    def _validar(self) -> None:
        # Números y booleanos: el usuario podría escribirlos como texto en el YAML.
        self.gastos_pct = _decimal(self.gastos_pct, 0.25, minimo=0.0)
        self.costes_compra_pct = _decimal(self.costes_compra_pct, 0.11, minimo=0.0)
        self.financiacion_pct = _decimal(self.financiacion_pct, 0.0, minimo=0.0)
        if self.financiacion_pct > 0.95:
            self.financiacion_pct = 0.95
        self.interes_hipoteca = _decimal(self.interes_hipoteca, 0.03, minimo=0.0)
        self.anios_hipoteca = _entero(self.anios_hipoteca, 25, minimo=1)
        self.umbral_chollo = _decimal(self.umbral_chollo, 10.0, minimo=0.0)
        self.revalorizacion_anual = _decimal(self.revalorizacion_anual, 0.0, minimo=0.0)
        self.horizonte_anios = _entero(self.horizonte_anios, 10, minimo=1)
        self.estres_alquiler_pct = _decimal(self.estres_alquiler_pct, 0.0, minimo=0.0)
        self.rentabilidad_objetivo = _decimal(self.rentabilidad_objetivo, 0.0, minimo=0.0)
        self.tipo_irpf = _decimal(self.tipo_irpf, 0.0, minimo=0.0)
        self.reduccion_irpf = _decimal(self.reduccion_irpf, 0.60, minimo=0.0)
        self.usar_rentas_referencia = _booleano(self.usar_rentas_referencia, True)
        self.usar_ia = _booleano(self.usar_ia, False)
        self.modelo_ia = str(self.modelo_ia or "claude-opus-4-8").strip() or "claude-opus-4-8"

        if self.rentas_zona is None or not isinstance(self.rentas_zona, dict):
            self.rentas_zona = {}
        else:
            rentas: dict = {}
            for zona, precio in self.rentas_zona.items():
                valor = _decimal(precio, 0.0, minimo=0.0)
                if valor > 0 and str(zona).strip():
                    rentas[str(zona).strip()] = valor
            self.rentas_zona = rentas

        if not self.archivo_salida or not str(self.archivo_salida).strip():
            self.archivo_salida = "resultados"
        self.archivo_salida = str(self.archivo_salida).strip()


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
