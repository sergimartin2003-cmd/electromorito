"""Tests del motor de rentabilidad de pisos (parsers, cálculo y evaluación)."""

from scraper.rentabilidad import (
    ParametrosRentabilidad,
    _a_numero,
    analizar_apalancamiento,
    clasificar_rentabilidad,
    cuota_hipoteca,
    es_exterior,
    estimar_alquiler,
    evaluar_piso,
    extraer_estado,
    extraer_habitaciones,
    extraer_planta,
    extraer_precio,
    extraer_superficie,
    price_to_rent,
    puntuacion,
    rentabilidad_bruta,
    rentabilidad_neta,
    tiene_ascensor,
    tiene_garaje,
    tiene_terraza,
)

PARAMS = ParametrosRentabilidad(
    gastos_pct=0.25,
    costes_compra_pct=0.11,
    rentas_zona={"Barcelona": 14, "Madrid centro": 18, "Madrid": 15},
)

PARAMS_HIP = ParametrosRentabilidad(
    gastos_pct=0.25, costes_compra_pct=0.11,
    financiacion_pct=0.70, interes_hipoteca=0.03, anios_hipoteca=25,
    rentas_zona={"Madrid": 15},
)


# --- Lectura de números en formato español -------------------------------
def test_numero_con_separador_de_miles():
    assert _a_numero("180.000") == 180000
    assert _a_numero("1.234.567") == 1234567


def test_numero_con_decimal_coma():
    assert _a_numero("90,5") == 90.5
    assert _a_numero("1.250,75") == 1250.75


def test_numero_con_texto_alrededor():
    assert _a_numero("180.000 €") == 180000
    assert _a_numero("90 m²") == 90


def test_numero_ya_numerico():
    assert _a_numero(180000) == 180000.0
    assert _a_numero(None) is None
    assert _a_numero("sin precio") is None


# --- Extracción desde el texto del anuncio -------------------------------
def test_extraer_precio_con_simbolo_y_miles():
    assert extraer_precio("Se vende piso por 180.000 €") == 180000
    assert extraer_precio("Precio: 195000 euros") == 195000


def test_extraer_precio_por_contexto_sin_simbolo():
    assert extraer_precio("Precio de venta 210.000, negociable") == 210000


def test_extraer_precio_ignora_importes_pequenos():
    # La comunidad (50 €) no debe confundirse con el precio
    assert extraer_precio("Comunidad 50 €. Piso de 165.000 €") == 165000


def test_extraer_precio_sin_precio():
    assert extraer_precio("Bonito piso reformado") is None


def test_extraer_superficie():
    assert extraer_superficie("Piso de 90 m² exterior") == 90
    assert extraer_superficie("Superficie 78,5 metros cuadrados") == 78.5
    assert extraer_superficie("Vivienda de 110m2") == 110


def test_extraer_superficie_sin_dato():
    assert extraer_superficie("Piso céntrico y luminoso") is None


def test_extraer_habitaciones():
    assert extraer_habitaciones("3 habitaciones y 2 baños") == 3
    assert extraer_habitaciones("Piso de 2 dormitorios") == 2
    assert extraer_habitaciones("4 hab, exterior") == 4


# --- Cálculo de rentabilidad ---------------------------------------------
def test_rentabilidad_bruta():
    # 900 €/mes sobre 180.000 € => 6 %
    assert rentabilidad_bruta(180000, 900) == 6.0


def test_rentabilidad_bruta_datos_invalidos():
    assert rentabilidad_bruta(0, 900) is None
    assert rentabilidad_bruta(180000, None) is None


def test_rentabilidad_neta():
    # (900*12*0.75) / (180000*1.11) * 100 = 8100 / 199800 * 100 = 4.054...
    neta = rentabilidad_neta(180000, 900, PARAMS)
    assert round(neta, 2) == 4.05


def test_rentabilidad_neta_menor_que_bruta():
    bruta = rentabilidad_bruta(150000, 800)
    neta = rentabilidad_neta(150000, 800, PARAMS)
    assert neta < bruta


# --- Clasificación -------------------------------------------------------
def test_clasificar_rentabilidad():
    assert clasificar_rentabilidad(9.0, PARAMS) == "excelente"
    assert clasificar_rentabilidad(6.5, PARAMS) == "buena"
    assert clasificar_rentabilidad(4.2, PARAMS) == "correcta"
    assert clasificar_rentabilidad(2.0, PARAMS) == "baja"
    assert clasificar_rentabilidad(None, PARAMS) == "sin datos"


# --- Estimación de alquiler por zona -------------------------------------
def test_estimar_alquiler_zona_exacta():
    assert estimar_alquiler(80, "Barcelona", PARAMS) == 1120  # 80 * 14


def test_estimar_alquiler_gana_la_zona_mas_especifica():
    # "Madrid centro" (18) debe ganar a "Madrid" (15) por ser más específica
    assert estimar_alquiler(70, "Piso en Madrid centro", PARAMS) == 1260  # 70 * 18


def test_estimar_alquiler_zona_desconocida():
    assert estimar_alquiler(80, "Cuenca", PARAMS) is None


def test_estimar_alquiler_sin_superficie():
    assert estimar_alquiler(None, "Barcelona", PARAMS) is None


# --- Evaluación completa de un piso --------------------------------------
def test_evaluar_piso_con_datos_directos():
    piso = evaluar_piso(
        {"titulo": "Piso 3 hab", "url": "https://ej.com/1", "zona": "Sevilla",
         "precio": "180.000", "superficie": "90", "alquiler_mensual": "900"},
        PARAMS,
    )
    assert piso["precio"] == 180000
    assert piso["superficie"] == 90
    assert piso["precio_m2"] == 2000
    assert piso["rentabilidad_bruta"] == 6.0
    assert piso["rentabilidad_neta"] == 4.05
    assert piso["clasificacion"] == "correcta"
    assert piso["completo"] is True
    assert piso["alquiler_estimado"] is False


def test_evaluar_piso_estima_alquiler_por_zona():
    piso = evaluar_piso(
        {"titulo": "Piso céntrico", "zona": "Barcelona",
         "precio": "300000", "superficie": "80"},
        PARAMS,
    )
    assert piso["alquiler_mensual"] == 1120  # estimado: 80 * 14
    assert piso["alquiler_estimado"] is True
    assert piso["rentabilidad_bruta"] is not None


def test_evaluar_piso_extrae_del_texto():
    piso = evaluar_piso(
        {"titulo": "Piso en venta", "zona": "Madrid",
         "descripcion": "Vivienda de 100 m² con 3 habitaciones por 250.000 €"},
        PARAMS,
    )
    assert piso["precio"] == 250000
    assert piso["superficie"] == 100
    assert piso["habitaciones"] == 3
    # Alquiler estimado por zona Madrid (15 €/m²) => 1500
    assert piso["alquiler_mensual"] == 1500


def test_evaluar_piso_incompleto():
    piso = evaluar_piso({"titulo": "Piso sin datos", "zona": "Teruel"}, PARAMS)
    assert piso["completo"] is False
    assert piso["rentabilidad_neta"] is None
    assert piso["clasificacion"] == "sin datos"


# --- Hipoteca / apalancamiento -------------------------------------------
def test_cuota_hipoteca_frances():
    assert round(cuota_hipoteca(150000, 0.03, 25), 2) == 711.32


def test_cuota_hipoteca_sin_interes():
    assert cuota_hipoteca(120000, 0, 20) == 500.0


def test_cuota_hipoteca_sin_capital():
    assert cuota_hipoteca(0, 0.03, 25) == 0.0


def test_analizar_apalancamiento():
    a = analizar_apalancamiento(180000, 900, PARAMS_HIP)
    assert a["fondos_propios"] == 73800          # 30% entrada + 11% costes
    assert a["cuota_hipoteca"] == 598            # sobre 126.000 € a 25 años
    assert a["cash_flow_mensual"] == 77          # 675 neto − 598 cuota
    assert a["rentabilidad_fondos_propios"] is not None


def test_apalancamiento_sin_financiacion_es_none():
    assert analizar_apalancamiento(180000, 900, PARAMS) is None


def test_evaluar_piso_incluye_hipoteca():
    piso = evaluar_piso(
        {"titulo": "Piso", "zona": "Madrid", "precio": "250000", "superficie": "100",
         "alquiler_mensual": "1400"},
        PARAMS_HIP,
    )
    assert piso["cuota_hipoteca"] is not None
    assert piso["cash_flow_mensual"] is not None
    assert piso["rentabilidad_fondos_propios"] is not None


# --- Estado, planta y ascensor -------------------------------------------
def test_extraer_estado():
    assert extraer_estado("Piso para reformar, mucha luz") == "a reformar"
    assert extraer_estado("Vivienda totalmente reformada") == "reformado"
    assert extraer_estado("Obra nueva a estrenar") == "obra nueva"
    assert extraer_estado("Piso en buen estado") == "buen estado"
    assert extraer_estado("Piso céntrico y luminoso") == ""


def test_estado_para_reformar_tiene_prioridad():
    # "para reformar" no debe clasificarse como "reformado"
    assert extraer_estado("Piso para reformar a tu gusto") == "a reformar"


def test_tiene_ascensor():
    assert tiene_ascensor("Finca con ascensor") is True
    assert tiene_ascensor("Sin ascensor, 2º piso") is False
    assert tiene_ascensor("Piso luminoso") is None


def test_extraer_planta():
    assert extraer_planta("Bonito ático con terraza") == "ático"
    assert extraer_planta("Piso en planta 3") == "3"
    assert extraer_planta("Vivienda en bajo con patio") == "bajo"
    assert extraer_planta("Piso luminoso") == ""


def test_extras_terraza_garaje_exterior():
    assert tiene_terraza("Piso con terraza") is True
    assert tiene_terraza("Piso interior") is None
    assert tiene_garaje("Incluye plaza de garaje") is True
    assert tiene_garaje("Sin garaje") is False
    assert es_exterior("Vivienda exterior") is True
    assert es_exterior("Piso interior") is False
    assert es_exterior("Piso céntrico") is None


# --- PER y puntuación ----------------------------------------------------
def test_price_to_rent():
    assert price_to_rent(180000, 900) == 16.7   # 180000 / (900*12)
    assert price_to_rent(0, 900) is None


def test_puntuacion_maxima():
    piso = {"rentabilidad_neta": 8.0, "descuento_zona": 15.0,
            "estado": "reformado", "alquiler_estimado": False}
    assert puntuacion(piso, PARAMS) == 100      # 60 (rent) + 25 (descuento) + 15 (calidad)


def test_puntuacion_penaliza_reformar_y_estimado():
    piso = {"rentabilidad_neta": 4.0, "descuento_zona": None,
            "estado": "a reformar", "alquiler_estimado": True}
    assert puntuacion(piso, PARAMS) == 30       # 30 (rent) + 0 + 0 (calidad 15-10-5)


def test_puntuacion_none_sin_rentabilidad():
    assert puntuacion({"rentabilidad_neta": None}, PARAMS) is None


# --- Escenario de estrés y proyección ------------------------------------
def test_rentabilidad_neta_estres_es_menor():
    p = ParametrosRentabilidad(gastos_pct=0.25, costes_compra_pct=0.11, estres_alquiler_pct=0.10)
    from scraper.rentabilidad import rentabilidad_neta_estres
    normal = rentabilidad_neta(180000, 900, p)
    estres = rentabilidad_neta_estres(180000, 900, p)
    assert estres < normal


def test_estres_desactivado_es_none():
    from scraper.rentabilidad import rentabilidad_neta_estres
    assert rentabilidad_neta_estres(180000, 900, PARAMS) is None


def test_proyeccion_desactivada_es_none():
    from scraper.rentabilidad import proyeccion
    assert proyeccion(180000, 900, PARAMS) is None


def test_proyeccion_calcula_ganancia_y_roi():
    from scraper.rentabilidad import proyeccion
    p = ParametrosRentabilidad(gastos_pct=0.25, costes_compra_pct=0.11,
                               revalorizacion_anual=0.02, horizonte_anios=10)
    proy = proyeccion(200000, 1000, p)
    # 200.000 € al 2% anual durante 10 años => +43.799 € de ganancia de capital
    assert proy["ganancia_capital"] == 43799
    assert proy["roi_proyectado_pct"] is not None
    assert proy["roi_anual_medio_pct"] == round(proy["roi_proyectado_pct"] / 10, 1)


def test_evaluar_piso_incluye_estres_y_proyeccion():
    p = ParametrosRentabilidad(gastos_pct=0.25, costes_compra_pct=0.11,
                               revalorizacion_anual=0.02, horizonte_anios=10,
                               estres_alquiler_pct=0.10)
    piso = evaluar_piso({"titulo": "X", "zona": "Sevilla", "precio": "180000",
                         "superficie": "90", "alquiler_mensual": "900"}, p)
    assert piso["rentabilidad_neta_estres"] is not None
    assert piso["rentabilidad_neta_estres"] < piso["rentabilidad_neta"]
    assert piso["roi_anual_medio_pct"] is not None
    assert piso["ganancia_capital"] > 0
