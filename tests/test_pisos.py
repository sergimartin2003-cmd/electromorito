"""Tests del flujo de pisos: ordenación por rentabilidad y escritura de CSV/HTML."""

import csv

from scraper.pisos import (
    CAMPOS_PISOS,
    cargar_pisos,
    escribir_csv,
    generar_informe_pisos,
    procesar_pisos,
)
from scraper.rentabilidad import ParametrosRentabilidad

PARAMS = ParametrosRentabilidad(rentas_zona={"Barcelona": 14})

FILAS = [
    {"titulo": "Buena", "url": "u1", "zona": "X", "precio": "100000",
     "superficie": "60", "alquiler_mensual": "700"},   # bruta 8.4 %
    {"titulo": "Floja", "url": "u2", "zona": "X", "precio": "300000",
     "superficie": "90", "alquiler_mensual": "700"},   # bruta 2.8 %
    {"titulo": "Incompleta", "url": "u3", "zona": "Cuenca"},  # sin datos
]


def test_procesar_ordena_por_rentabilidad_y_deja_incompletos_al_final():
    pisos = procesar_pisos(FILAS, PARAMS)
    assert [p["titulo"] for p in pisos] == ["Buena", "Floja", "Incompleta"]
    assert pisos[0]["puntuacion"] >= pisos[1]["puntuacion"]
    assert pisos[-1]["completo"] is False


def test_detecta_chollo_por_mediana_de_zona():
    filas = [
        {"titulo": "Barato", "url": "u1", "zona": "Zeta", "precio": "100000",
         "superficie": "50", "alquiler_mensual": "600"},   # 2000 €/m²
        {"titulo": "Caro", "url": "u2", "zona": "Zeta", "precio": "200000",
         "superficie": "50", "alquiler_mensual": "700"},    # 4000 €/m²
    ]
    pisos = procesar_pisos(filas, PARAMS)
    por_titulo = {p["titulo"]: p for p in pisos}
    # Mediana de la zona = 3000 €/m²; el barato está un 33% por debajo => chollo
    assert por_titulo["Barato"]["es_chollo"] is True
    assert por_titulo["Barato"]["descuento_zona"] > 10
    assert por_titulo["Caro"]["es_chollo"] is False


def test_sin_comparables_no_marca_chollo():
    # Una sola vivienda en su zona: no hay mediana con la que comparar
    filas = [{"titulo": "Solo", "url": "u", "zona": "Rara", "precio": "100000",
              "superficie": "50", "alquiler_mensual": "600"}]
    pisos = procesar_pisos(filas, PARAMS)
    assert pisos[0]["descuento_zona"] is None
    assert pisos[0]["es_chollo"] is False


def test_marca_duplicados():
    filas = [
        {"titulo": "Piso A (portal 1)", "url": "u1", "zona": "Madrid",
         "precio": "200000", "superficie": "80", "alquiler_mensual": "1000"},
        {"titulo": "Piso A (portal 2)", "url": "u2", "zona": "Madrid",
         "precio": "200000", "superficie": "80", "alquiler_mensual": "1000"},
        {"titulo": "Otro piso", "url": "u3", "zona": "Madrid",
         "precio": "150000", "superficie": "70", "alquiler_mensual": "900"},
    ]
    pisos = procesar_pisos(filas, PARAMS)
    duplicados = [p for p in pisos if p["duplicado"]]
    # De los dos anuncios del mismo piso, solo uno se marca como duplicado
    assert len(duplicados) == 1
    assert sum(1 for p in pisos if not p["duplicado"]) == 2


def test_cargar_xlsx(tmp_path):
    import pytest
    Workbook = pytest.importorskip("openpyxl").Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["titulo", "zona", "precio", "superficie", "alquiler_mensual"])
    ws.append(["Piso Excel", "Madrid", 200000, 80, 1000])
    ruta = tmp_path / "pisos.xlsx"
    wb.save(ruta)

    filas = cargar_pisos(str(ruta))
    assert len(filas) == 1
    assert filas[0]["titulo"] == "Piso Excel"
    assert filas[0]["precio"] == 200000


def test_escribir_csv(tmp_path):
    pisos = procesar_pisos(FILAS, PARAMS)
    ruta = tmp_path / "salida_pisos.csv"
    escribir_csv(pisos, str(ruta))
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    assert list(filas[0].keys()) == CAMPOS_PISOS
    assert filas[0]["titulo"] == "Buena"
    assert filas[0]["fecha"]  # se rellena la fecha
    # Los booleanos se escriben como sí/no
    assert filas[0]["alquiler_estimado"] in ("sí", "no")


def test_generar_informe_incrusta_datos(tmp_path):
    pisos = procesar_pisos(FILAS, PARAMS)
    ruta = tmp_path / "salida_pisos.html"
    generar_informe_pisos(pisos, str(ruta))
    html = ruta.read_text(encoding="utf-8")
    assert "Pisos ordenados por rentabilidad" in html
    assert "Buena" in html
    # Todos los marcadores se han sustituido por datos reales
    for marcador in ("/*__DATOS__*/null", "/*__COLS__*/null", "/*__NUMCOLS__*/null"):
        assert marcador not in html
