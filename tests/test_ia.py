"""Tests del enriquecimiento con IA (con un cliente falso: no tocan la red)."""

import json

from scraper.ia import enriquecer_pisos, estimar_piso_ia
from scraper.rentabilidad import ParametrosRentabilidad, evaluar_piso

PARAMS = ParametrosRentabilidad(rentas_zona={"Madrid": 15})


class _Bloque:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class _Respuesta:
    def __init__(self, texto):
        self.content = [_Bloque(texto)]


class _Mensajes:
    def __init__(self, payload, registro):
        self._payload = payload
        self._registro = registro

    def create(self, **kwargs):
        self._registro.append(kwargs)
        return _Respuesta(json.dumps(self._payload))


class ClienteFalso:
    """Imita al cliente de Anthropic devolviendo un JSON fijo."""

    def __init__(self, payload):
        self.llamadas = []
        self.messages = _Mensajes(payload, self.llamadas)


class ClienteRoto:
    class messages:  # noqa: N801
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("sin red")


PAYLOAD = {
    "alquiler_mensual_estimado": 1300,
    "estado": "a reformar",
    "resumen": "Piso amplio para reformar en zona céntrica.",
    "riesgos": ["Necesita reforma integral", "Sin ascensor"],
    "confianza": "media",
}


def test_estimar_piso_ia_parsea_json():
    cliente = ClienteFalso(PAYLOAD)
    datos = estimar_piso_ia({"titulo": "Piso", "zona": "Madrid"}, PARAMS, cliente=cliente)
    assert datos["alquiler_mensual_estimado"] == 1300
    assert datos["estado"] == "a reformar"
    # Se pidió salida estructurada (output_config con json_schema)
    assert cliente.llamadas[0]["output_config"]["format"]["type"] == "json_schema"


def test_estimar_piso_ia_error_devuelve_none():
    assert estimar_piso_ia({"titulo": "X"}, PARAMS, cliente=ClienteRoto()) is None


def test_enriquecer_rellena_alquiler_y_marca_estimado():
    filas = [
        {"titulo": "Sin alquiler", "zona": "Madrid", "precio": "250000", "superficie": "90"},
        {"titulo": "Con alquiler", "zona": "Madrid", "precio": "250000",
         "superficie": "90", "alquiler_mensual": "1200"},
    ]
    cliente = ClienteFalso(PAYLOAD)
    n = enriquecer_pisos(filas, PARAMS, cliente=cliente, log=lambda *_: None)

    assert n == 1                                  # solo el que no tenía alquiler
    assert len(cliente.llamadas) == 1             # no se llama para el que ya tenía alquiler
    assert filas[0]["alquiler_mensual"] == 1300
    assert filas[0]["alquiler_estimado"] == "sí"
    assert filas[0]["estado"] == "a reformar"
    assert "Sin ascensor" in filas[0]["ia_riesgos"]
    assert filas[1].get("alquiler_estimado") is None


def test_evaluar_piso_respeta_marca_de_estimado():
    # Un alquiler con la marca 'alquiler_estimado' se cuenta como estimado
    piso = evaluar_piso(
        {"titulo": "X", "zona": "Madrid", "precio": "250000", "superficie": "90",
         "alquiler_mensual": "1300", "alquiler_estimado": "sí"},
        PARAMS,
    )
    assert piso["alquiler_mensual"] == 1300
    assert piso["alquiler_estimado"] is True


def test_ia_fields_llegan_al_piso_evaluado():
    piso = evaluar_piso(
        {"titulo": "X", "zona": "Madrid", "precio": "250000", "superficie": "90",
         "alquiler_mensual": "1300", "ia_riesgos": "Sin ascensor", "ia_resumen": "Resumen"},
        PARAMS,
    )
    assert piso["ia_riesgos"] == "Sin ascensor"
    assert piso["ia_resumen"] == "Resumen"
