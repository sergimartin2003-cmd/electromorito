"""Tests de utilidades de dominio y del almacenamiento (CSV, dedup, migración)."""

import csv

from scraper.storage import CAMPOS, Almacen
from scraper.util import dominio, dominio_registrable


# --- util ----------------------------------------------------------------
def test_dominio_quita_www():
    assert dominio("https://www.fundacion.org/contacto") == "fundacion.org"


def test_dominio_registrable_subdominio():
    assert dominio_registrable("https://blog.sub.fundacion.org/x") == "fundacion.org"


def test_dominio_registrable_sufijo_compuesto():
    assert dominio_registrable("https://portal.ayto.gob.es/x") == "ayto.gob.es"


def test_dominio_url_invalida():
    assert dominio("no-es-una-url") == ""


# --- storage -------------------------------------------------------------
class _Cfg:
    """Configuración mínima para instanciar el Almacen."""
    def __init__(self, base):
        self.archivo_salida = base


def _org(dominio="centro.es", correos=("info@centro.es",), telefonos=("600 00 00 00",)):
    return {
        "nombre": "Centro X",
        "correos": list(correos),
        "telefonos": list(telefonos),
        "provincia": "Madrid",
        "relevancia": 4,
        "web": f"https://{dominio}",
        "dominio": dominio,
        "categoria": "escuela",
        "busqueda": "escuela Madrid",
    }


def test_guarda_una_fila_por_correo(tmp_path):
    alm = Almacen(_Cfg(str(tmp_path / "out")))
    n = alm.guardar_organizacion(_org(correos=["a@centro.es", "b@centro.es"]))
    assert n == 2
    assert {f["correo"] for f in alm.filas} == {"a@centro.es", "b@centro.es"}
    assert all(f["tipo_correo"] for f in alm.filas)  # clasificado


def test_dedup_de_correos(tmp_path):
    alm = Almacen(_Cfg(str(tmp_path / "out")))
    alm.guardar_organizacion(_org(dominio="a.es", correos=["mismo@x.es"]))
    n = alm.guardar_organizacion(_org(dominio="b.es", correos=["mismo@x.es"]))
    assert n == 0  # ya existía ese correo


def test_sin_correo_pero_con_telefono(tmp_path):
    alm = Almacen(_Cfg(str(tmp_path / "out")))
    n = alm.guardar_organizacion(_org(correos=[], telefonos=["600 11 22 33"]))
    assert n == 1
    assert alm.filas[0]["correo"] == ""
    assert alm.filas[0]["telefonos"] == "600 11 22 33"


def test_csv_incremental_con_cabecera(tmp_path):
    base = str(tmp_path / "out")
    alm = Almacen(_Cfg(base))
    alm.guardar_organizacion(_org())
    with open(base + ".csv", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        assert list(lector.fieldnames) == CAMPOS
        filas = list(lector)
    assert filas[0]["correo"] == "info@centro.es"
    assert filas[0]["provincia"] == "Madrid"


def test_reanudacion_recuerda_correos_y_dominios(tmp_path):
    base = str(tmp_path / "out")
    Almacen(_Cfg(base)).guardar_organizacion(_org(dominio="centro.es", correos=["info@centro.es"]))
    # Nueva instancia: debe recordar lo anterior
    alm2 = Almacen(_Cfg(base))
    assert "info@centro.es" in alm2.correos_vistos
    assert "centro.es" in alm2.dominios_vistos


def test_migracion_de_csv_antiguo(tmp_path):
    base = str(tmp_path / "out")
    # CSV con esquema viejo (8 columnas)
    with open(base + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        f.write("nombre,correo,telefonos,web,dominio,categoria,busqueda,fecha\n")
        f.write("Viejo,viejo@x.org,911111111,https://x.org,x.org,fund,q,2026-01-01\n")
    alm = Almacen(_Cfg(base))  # debe migrar al cargar
    # El fichero ya tiene la cabecera nueva
    with open(base + ".csv", encoding="utf-8-sig", newline="") as f:
        assert list(csv.DictReader(f).fieldnames) == CAMPOS
    # Y conserva el dato para dedup/reanudar
    assert "viejo@x.org" in alm.correos_vistos
    # Un append posterior no corrompe el fichero
    alm.guardar_organizacion(_org(dominio="nuevo.es", correos=["nuevo@nuevo.es"]))
    with open(base + ".csv", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    assert {fila["correo"] for fila in filas} == {"viejo@x.org", "nuevo@nuevo.es"}
