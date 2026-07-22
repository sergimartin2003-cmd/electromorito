"""Tests de carga y validación de la configuración."""

import textwrap

import pytest

from scraper.config import Config


def _escribir(tmp_path, contenido: str):
    ruta = tmp_path / "config.yaml"
    ruta.write_text(textwrap.dedent(contenido), encoding="utf-8")
    return str(ruta)


def test_config_minima(tmp_path):
    ruta = _escribir(tmp_path, """
        categorias: ["fundación discapacidad"]
        ubicaciones: ["Madrid", "Barcelona"]
    """)
    cfg = Config.cargar(ruta)
    busquedas = cfg.construir_busquedas()
    assert len(busquedas) == 2
    assert busquedas[0] == ("fundación discapacidad", "Madrid", "fundación discapacidad Madrid")


def test_coercion_de_tipos(tmp_path):
    ruta = _escribir(tmp_path, """
        categorias: ["x"]
        resultados_por_busqueda: "20"
        espera_min_segundos: "1.5"
        navegador_visible: "no"
        respetar_robots: "sí"
        max_busquedas: -5
    """)
    cfg = Config.cargar(ruta)
    assert cfg.resultados_por_busqueda == 20 and isinstance(cfg.resultados_por_busqueda, int)
    assert cfg.espera_min_segundos == 1.5 and isinstance(cfg.espera_min_segundos, float)
    assert cfg.navegador_visible is False
    assert cfg.respetar_robots is True
    assert cfg.max_busquedas == 0  # negativo -> 0


def test_listas_none_y_ruido(tmp_path):
    ruta = _escribir(tmp_path, """
        categorias: ["fundación", "  ", "escuela"]
        ubicaciones:
        dominios_excluidos:
    """)
    cfg = Config.cargar(ruta)
    assert cfg.categorias == ["fundación", "escuela"]
    assert cfg.ubicaciones == []
    assert cfg.dominios_excluidos == []


def test_motor_invalido(tmp_path):
    ruta = _escribir(tmp_path, """
        categorias: ["x"]
        motor_busqueda: "yahoo"
    """)
    with pytest.raises(ValueError):
        Config.cargar(ruta)


def test_sin_nada_que_buscar(tmp_path):
    ruta = _escribir(tmp_path, """
        ubicaciones: ["Madrid"]
    """)
    with pytest.raises(ValueError):
        Config.cargar(ruta)


def test_yaml_no_es_diccionario(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text("- uno\n- dos\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Config.cargar(str(ruta))


def test_max_busquedas_limita(tmp_path):
    ruta = _escribir(tmp_path, """
        categorias: ["a", "b", "c"]
        ubicaciones: ["M", "B"]
        max_busquedas: 3
    """)
    cfg = Config.cargar(ruta)
    assert len(cfg.construir_busquedas()) == 3


def test_busquedas_extra_provincia_vacia(tmp_path):
    ruta = _escribir(tmp_path, """
        categorias: []
        busquedas_extra: ["fundación autismo contacto"]
    """)
    cfg = Config.cargar(ruta)
    b = cfg.construir_busquedas()
    assert b == [("extra", "", "fundación autismo contacto")]
