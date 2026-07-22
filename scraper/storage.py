"""Guarda los resultados en CSV (incremental) y Excel, evitando duplicados.

El CSV se escribe fila a fila mientras rastrea, así que si el proceso se corta
no se pierde nada. El Excel se genera al final a partir de todo lo recogido.
También recuerda los dominios ya visitados para poder REANUDAR otro día.
"""

from __future__ import annotations

import csv
import datetime as _dt
import os
from typing import Dict, List, Set

CAMPOS = ["nombre", "correo", "telefonos", "web", "dominio", "categoria", "busqueda", "fecha"]


class Almacen:
    def __init__(self, config) -> None:
        base = config.archivo_salida
        self.ruta_csv = base + ".csv"
        self.ruta_xlsx = base + ".xlsx"
        self.ruta_estado = base + "_dominios_visitados.txt"

        self.correos_vistos: Set[str] = set()
        self.dominios_vistos: Set[str] = set()
        self.filas: List[Dict[str, str]] = []

        self._cargar_existente()

    # ------------------------------------------------------------------
    def _cargar_existente(self) -> None:
        """Rellena los conjuntos de 'ya vistos' desde ficheros previos (para reanudar)."""
        if os.path.exists(self.ruta_csv):
            try:
                with open(self.ruta_csv, "r", encoding="utf-8-sig", newline="") as f:
                    for fila in csv.DictReader(f):
                        self.filas.append(fila)
                        correo = (fila.get("correo") or "").strip().lower()
                        if correo:
                            self.correos_vistos.add(correo)
                        dom = (fila.get("dominio") or "").strip().lower()
                        if dom:
                            self.dominios_vistos.add(dom)
            except Exception as e:  # noqa: BLE001
                print(f"  Aviso: no se pudo leer el CSV existente ({e}).")

        if os.path.exists(self.ruta_estado):
            try:
                with open(self.ruta_estado, "r", encoding="utf-8") as f:
                    for linea in f:
                        dom = linea.strip().lower()
                        if dom:
                            self.dominios_vistos.add(dom)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _escribir_csv(self, nuevas: List[Dict[str, str]]) -> None:
        nuevo = not os.path.exists(self.ruta_csv)
        with open(self.ruta_csv, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CAMPOS)
            if nuevo:
                writer.writeheader()
            for fila in nuevas:
                writer.writerow(fila)

    def _marcar_dominio(self, dom: str) -> None:
        if not dom:
            return
        try:
            with open(self.ruta_estado, "a", encoding="utf-8") as f:
                f.write(dom + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    def guardar_organizacion(self, org: dict) -> int:
        """Guarda una organización. Devuelve cuántas filas NUEVAS se añadieron.

        - Una fila por cada correo nuevo (deduplicando correos en toda la ejecución).
        - Si no hay correos pero sí teléfono, guarda una fila con correo vacío.
        """
        dom = (org.get("dominio") or "").strip().lower()
        self.dominios_vistos.add(dom)
        self._marcar_dominio(dom)

        fecha = _dt.date.today().isoformat()
        telefonos = "; ".join(org.get("telefonos") or [])
        base = {
            "nombre": org.get("nombre", ""),
            "telefonos": telefonos,
            "web": org.get("web", ""),
            "dominio": dom,
            "categoria": org.get("categoria", ""),
            "busqueda": org.get("busqueda", ""),
            "fecha": fecha,
        }

        nuevas: List[Dict[str, str]] = []
        for correo in org.get("correos") or []:
            correo = correo.strip().lower()
            if not correo or correo in self.correos_vistos:
                continue
            self.correos_vistos.add(correo)
            nuevas.append({**base, "correo": correo})

        # Sin correos pero con teléfono -> guarda igualmente el contacto (una vez por dominio)
        if not org.get("correos") and telefonos:
            nuevas.append({**base, "correo": ""})

        if nuevas:
            self.filas.extend(nuevas)
            self._escribir_csv(nuevas)
        return len(nuevas)

    # ------------------------------------------------------------------
    def exportar_excel(self) -> bool:
        """Vuelca todo a un .xlsx. Devuelve True si se generó."""
        if not self.filas:
            return False
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
        except ImportError:
            print("  (openpyxl no está instalado: se omite el Excel. El CSV sí está generado.)")
            return False

        wb = Workbook()
        ws = wb.active
        ws.title = "Contactos"
        ws.append(CAMPOS)
        for celda in ws[1]:
            celda.font = Font(bold=True)
        for fila in self.filas:
            ws.append([fila.get(c, "") for c in CAMPOS])

        # Ajusta el ancho de las columnas al contenido
        for i, campo in enumerate(CAMPOS, start=1):
            ancho = max([len(campo)] + [len(str(f.get(campo, ""))) for f in self.filas])
            ws.column_dimensions[get_column_letter(i)].width = min(ancho + 2, 60)
        ws.freeze_panes = "A2"

        try:
            wb.save(self.ruta_xlsx)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  Aviso: no se pudo guardar el Excel ({e}). El CSV sí está generado.")
            return False
