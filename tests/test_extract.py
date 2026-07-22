"""Tests de la extracción de correos, teléfonos, nombres, clasificación y relevancia."""

from scraper.extract import (
    calcular_relevancia,
    clasificar_correo,
    extraer_correos,
    extraer_telefonos,
    limpiar_nombre,
)

PALABRAS = ["discapacidad", "educación especial", "fundación", "IFE", "PFI", "inclusión"]


# --- Correos -------------------------------------------------------------
def test_correo_desde_mailto():
    assert extraer_correos("", ["mailto:info@fundacion.org"]) == ["info@fundacion.org"]


def test_correo_en_texto():
    assert "info@fundacion.org" in extraer_correos("Escríbenos a info@fundacion.org hoy")


def test_correo_camuflado_at_y_dot():
    correos = extraer_correos("secretaria [at] centro (dot) es")
    assert "secretaria@centro.es" in correos


def test_correo_camuflado_arroba_punto():
    correos = extraer_correos("admin (arroba) colegio (punto) org")
    assert "admin@colegio.org" in correos


def test_entidades_html():
    assert "hola@web.es" in extraer_correos("hola&#64;web.es")


def test_filtra_imagenes_y_ejemplos():
    ruido = "logo@2x.png usuario@example.com sentry@sentry.io banner@3x.jpg"
    assert extraer_correos(ruido) == []


def test_filtra_dominios_malformados():
    assert extraer_correos("malo@fund..org bien@fund.org") == ["bien@fund.org"]


def test_correos_sin_duplicados_y_ordenados():
    txt = "b@x.es a@x.es b@x.es"
    assert extraer_correos(txt) == ["a@x.es", "b@x.es"]


# --- Teléfonos -----------------------------------------------------------
def test_telefono_con_prefijo_internacional():
    assert extraer_telefonos("+34 912 34 56 78") == ["912 34 56 78"]
    assert extraer_telefonos("0034 617373657") == ["617 37 36 57"]


def test_telefono_con_separadores():
    assert extraer_telefonos("Tel. 934-567-890") == ["934 56 78 90"]


def test_telefono_desde_tel_href():
    assert extraer_telefonos("", ["tel:+34911223344"]) == ["911 22 33 44"]


def test_rechaza_hash_y_numeros_largos():
    assert extraer_telefonos("sha 6167344246173736574661746166") == []
    assert extraer_telefonos("id 123456789012345") == []


def test_no_une_numeros_de_lineas_distintas():
    txt = "Sede A: 934 56 78 90\nSede B: 911 22 33 44"
    assert set(extraer_telefonos(txt)) == {"934 56 78 90", "911 22 33 44"}


# --- Nombre --------------------------------------------------------------
def test_limpiar_nombre_corta_en_separador():
    assert limpiar_nombre("Fundación Ejemplo | Inicio") == "Fundación Ejemplo"


def test_limpiar_nombre_vacio():
    assert limpiar_nombre(None) == ""


# --- Clasificación de correo --------------------------------------------
def test_clasifica_generico():
    assert clasificar_correo("info@fundacion.org") == "genérico"
    assert clasificar_correo("contacto@centro.es") == "genérico"


def test_clasifica_gratuito():
    assert clasificar_correo("hola@gmail.com") == "gratuito"
    assert clasificar_correo("x@hotmail.es") == "gratuito"


def test_clasifica_personal():
    assert clasificar_correo("juan.perez@fundacion.org") == "personal"
    assert clasificar_correo("maria_lopez@centro.es") == "personal"


def test_clasifica_otro():
    assert clasificar_correo("ventas2024@empresa.com") == "otro"


# --- Relevancia ----------------------------------------------------------
def test_relevancia_cuenta_senales():
    texto = "Fundación para la discapacidad y la educación especial con IFE"
    assert calcular_relevancia(texto, PALABRAS) >= 3


def test_relevancia_cero_si_no_hay_tema():
    assert calcular_relevancia("Tienda de zapatos y moda", PALABRAS) == 0


def test_relevancia_sin_palabras():
    assert calcular_relevancia("cualquier cosa", []) == 0
