"""Tests de la carga y validación de la configuración (config.yaml)."""

import pytest

from scraper.config import Config


def test_cargar_config_de_ejemplo():
    # El config.yaml del repo debe cargar sin errores
    cfg = Config.cargar("config.yaml")
    assert cfg.gastos_pct > 0
    assert isinstance(cfg.rentas_zona, dict)


def test_valores_por_defecto_y_coercion(tmp_path):
    yaml = tmp_path / "c.yaml"
    yaml.write_text(
        "gastos_pct: '0.3'\n"          # texto -> número
        "financiacion_pct: 2\n"        # se limita a 0.95
        "usar_ia: 'no'\n"
        "rentas_zona:\n  Madrid: 15\n  Mala: 0\n",  # 0 se descarta
        encoding="utf-8",
    )
    cfg = Config.cargar(str(yaml))
    assert cfg.gastos_pct == 0.3
    assert cfg.financiacion_pct == 0.95
    assert cfg.usar_ia is False
    assert cfg.rentas_zona == {"Madrid": 15.0}


def test_config_inexistente():
    with pytest.raises(FileNotFoundError):
        Config.cargar("no_existe_este_fichero.yaml")


def test_claves_desconocidas_se_ignoran(tmp_path):
    yaml = tmp_path / "c.yaml"
    yaml.write_text("gastos_pct: 0.25\nmotor_busqueda: duckduckgo\n", encoding="utf-8")
    cfg = Config.cargar(str(yaml))          # 'motor_busqueda' (del scraper viejo) se ignora
    assert not hasattr(cfg, "motor_busqueda")
