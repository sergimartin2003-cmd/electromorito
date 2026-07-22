"""Tests de la lista depurada de contactos (una fila por organización)."""

import csv

from scraper.contactos import CAMPOS_CONTACTOS, construir_contactos, exportar_contactos


def _fila(**kw):
    base = {c: "" for c in (
        "nombre", "correo", "tipo_correo", "telefonos", "provincia",
        "relevancia", "web", "dominio", "grupo",
    )}
    base.update(kw)
    return base


def test_elige_correo_generico_como_principal():
    filas = [
        _fila(nombre="F A", correo="juan.perez@a.org", tipo_correo="personal",
              relevancia="5", dominio="a.org", grupo="f a"),
        _fila(nombre="F A", correo="info@a.org", tipo_correo="genérico",
              relevancia="5", dominio="a.org", grupo="f a"),
    ]
    cont = construir_contactos(filas)
    assert len(cont) == 1
    assert cont[0]["correo_principal"] == "info@a.org"
    assert "info@a.org" in cont[0]["todos_los_correos"]
    assert "juan.perez@a.org" in cont[0]["todos_los_correos"]


def test_ordena_por_relevancia_desc():
    filas = [
        _fila(nombre="Baja", correo="a@a.es", tipo_correo="genérico", relevancia="2", grupo="baja"),
        _fila(nombre="Alta", correo="b@b.es", tipo_correo="genérico", relevancia="9", grupo="alta"),
    ]
    cont = construir_contactos(filas)
    assert [c["nombre"] for c in cont] == ["Alta", "Baja"]


def test_excluye_sin_correo():
    filas = [_fila(nombre="Solo tel", correo="", telefonos="600 00 00 00", grupo="solo tel")]
    assert construir_contactos(filas) == []


def test_min_relevancia_filtra():
    filas = [
        _fila(nombre="X", correo="a@a.es", tipo_correo="genérico", relevancia="1", grupo="x"),
        _fila(nombre="Y", correo="b@b.es", tipo_correo="genérico", relevancia="4", grupo="y"),
    ]
    cont = construir_contactos(filas, min_relevancia=3)
    assert [c["nombre"] for c in cont] == ["Y"]


def test_agrupa_por_grupo_varios_dominios():
    # Misma organización (mismo grupo) con dos dominios distintos
    filas = [
        _fila(nombre="Fund", correo="info@fund.org", tipo_correo="genérico", grupo="fund", dominio="fund.org"),
        _fila(nombre="Fund", correo="contacto@fund.com", tipo_correo="genérico", grupo="fund", dominio="fund.com"),
    ]
    cont = construir_contactos(filas)
    assert len(cont) == 1
    assert "info@fund.org" in cont[0]["todos_los_correos"]
    assert "contacto@fund.com" in cont[0]["todos_los_correos"]


def test_exporta_csv(tmp_path):
    filas = [_fila(nombre="F", correo="info@f.es", tipo_correo="genérico", relevancia="3", grupo="f")]
    salida = str(tmp_path / "contactos.csv")
    n = exportar_contactos(filas, salida)
    assert n == 1
    with open(salida, encoding="utf-8-sig", newline="") as fh:
        lector = csv.DictReader(fh)
        assert list(lector.fieldnames) == CAMPOS_CONTACTOS
        assert next(lector)["correo_principal"] == "info@f.es"


def test_exporta_desde_csv_inexistente(tmp_path):
    assert exportar_contactos(str(tmp_path / "no.csv"), str(tmp_path / "out.csv")) is None
