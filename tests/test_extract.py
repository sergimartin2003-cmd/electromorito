"""Tests de la extracción de correos, teléfonos, nombres, clasificación y relevancia."""

from scraper.extract import (
    calcular_relevancia,
    clasificar_correo,
    clave_organizacion,
    descifrar_cf_email,
    extraer_codigo_postal,
    extraer_correos,
    extraer_redes,
    extraer_telefonos,
    limpiar_nombre,
    nombre_estructurado,
)


def _cf_encode(email, clave=0x42):
    """Codifica un correo como lo hace la protección de email de Cloudflare."""
    b = [clave] + [ord(c) ^ clave for c in email]
    return "".join(f"{x:02x}" for x in b)

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


def test_filtra_plataformas_web_y_sistema():
    ruido = "web@wordpress.com postmaster@fundacion.org nombre.apellido@x.org"
    assert extraer_correos(ruido + " real@centro.es") == ["real@centro.es"]


# --- Cloudflare email protection -----------------------------------------
def test_cf_descifra_ida_y_vuelta():
    assert descifrar_cf_email(_cf_encode("info@fundacion.org")) == "info@fundacion.org"


def test_cf_hex_invalido():
    assert descifrar_cf_email("zz") == ""
    assert descifrar_cf_email("") == ""


def test_correos_desde_cloudflare():
    html = (
        f'<a class="__cf_email__" data-cfemail="{_cf_encode("a@fund.org")}">x</a>'
        f'<a href="/cdn-cgi/l/email-protection#{_cf_encode("b@centro.es", 0x5a)}">y</a>'
    )
    assert extraer_correos(html) == ["a@fund.org", "b@centro.es"]


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


# --- Código postal -------------------------------------------------------
def test_cp_con_contexto():
    assert extraer_codigo_postal("C/ Mayor 3, C.P. 28013 Madrid") == "28013"


def test_cp_sin_contexto():
    assert extraer_codigo_postal("Calle Falsa 08001 Barcelona") == "08001"


def test_cp_rango_invalido():
    # 99xxx no es una provincia española válida
    assert extraer_codigo_postal("referencia 99123 del pedido") == ""


def test_cp_no_confunde_telefono():
    assert extraer_codigo_postal("Tel 911223344") == ""


# --- Redes sociales ------------------------------------------------------
def test_redes_un_enlace_por_plataforma():
    html_txt = '''
      <a href="https://facebook.com/fundacion">fb</a>
      <a href="https://www.instagram.com/fundacion/">ig</a>
      <a href="https://facebook.com/fundacion/photos">fb2</a>
    '''
    redes = extraer_redes(html_txt)
    assert any("facebook.com/fundacion" in r for r in redes)
    assert any("instagram.com/fundacion" in r for r in redes)
    # facebook aparece una sola vez
    assert sum("facebook.com" in r for r in redes) == 1


def test_redes_ignora_botones_de_compartir():
    html_txt = '<a href="https://www.facebook.com/sharer/sharer.php?u=x">compartir</a>'
    assert extraer_redes(html_txt) == []


def test_redes_ignora_dominio_sin_perfil():
    html_txt = '<a href="https://facebook.com/">facebook</a>'
    assert extraer_redes(html_txt) == []


# --- Clave de organización (agrupar duplicados) --------------------------
def test_clave_ignora_tildes_puntuacion_y_forma_juridica():
    a = clave_organizacion("Fundación Ejemplo, S.L.")
    b = clave_organizacion("FUNDACION  EJEMPLO SL")
    assert a == b == "fundacion ejemplo"


def test_clave_slu():
    assert clave_organizacion("Centro IFE, S.L.U.") == clave_organizacion("Centro IFE SLU")


def test_clave_no_fusiona_distintas():
    assert clave_organizacion("Fundación Ana") != clave_organizacion("Fundación Ander")


def test_clave_vacia():
    assert clave_organizacion("") == ""


# --- Nombre estructurado (JSON-LD / schema.org) --------------------------
def test_nombre_jsonld_organizacion():
    html = ('<script type="application/ld+json">'
            '{"@type":"NGO","name":"Fundación Real"}</script>')
    assert nombre_estructurado(html) == "Fundación Real"


def test_nombre_jsonld_graph():
    html = ('<script type="application/ld+json">'
            '{"@graph":[{"@type":"WebSite","name":"web"},'
            '{"@type":"EducationalOrganization","name":"Escuela X"}]}</script>')
    assert nombre_estructurado(html) == "Escuela X"


def test_nombre_jsonld_ausente_o_invalido():
    assert nombre_estructurado("<p>hola</p>") == ""
    assert nombre_estructurado('<script type="application/ld+json">{no es json}</script>') == ""
