"""Tests del generador de informe HTML."""

import csv

from scraper.report import generar_informe
from scraper.storage import CAMPOS


def _crear_csv(ruta, filas):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        for fila in filas:
            writer.writerow({c: fila.get(c, "") for c in CAMPOS})


def test_genera_html(tmp_path):
    csv_path = str(tmp_path / "res.csv")
    _crear_csv(csv_path, [
        {"nombre": "Fundación X", "correo": "info@x.org", "tipo_correo": "genérico",
         "provincia": "Madrid", "relevancia": "5", "web": "https://x.org"},
    ])
    ruta = generar_informe(csv_path)
    assert ruta and ruta.endswith(".html")
    contenido = open(ruta, encoding="utf-8").read()
    assert "info@x.org" in contenido
    assert "Fundación X" in contenido
    # Los datos se incrustaron (ya no queda el marcador)
    assert "/*__DATOS__*/null" not in contenido
    assert "const DATOS =" in contenido


def test_csv_inexistente_devuelve_none(tmp_path):
    assert generar_informe(str(tmp_path / "no_existe.csv")) is None


def test_escapa_cierre_de_script(tmp_path):
    csv_path = str(tmp_path / "res.csv")
    _crear_csv(csv_path, [{"nombre": "Malo </script><b>", "correo": "a@b.es"}])
    ruta = generar_informe(csv_path)
    contenido = open(ruta, encoding="utf-8").read()
    # El </script> de los datos no debe aparecer sin escapar dentro del bloque de datos
    assert "</script><b>" not in contenido
