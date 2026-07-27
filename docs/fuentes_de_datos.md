# Fuentes de datos: cómo alimentar el motor de rentabilidad (de forma legal)

Este documento explica **de dónde sacar los anuncios** para el modo `--pisos` sin
depender del scraping de los grandes portales, y propone una **arquitectura** para
pasar de prototipo a algo sostenible.

> Resumen: el valor de la herramienta es el **motor de rentabilidad** (cálculo,
> ranking, chollos, hipoteca, IA). Ese motor trabaja sobre una lista de anuncios
> normalizados; **la fuente es intercambiable**. La parte difícil —y con riesgo
> legal— es *conseguir* los anuncios a escala. Esa parte se resuelve con **APIs
> oficiales, feeds con los que tengas derecho y datos públicos**, no scrapeando.

---

## 1. El esquema que consume el motor

El motor (`rentapisos/rentabilidad.py` + `rentapisos/pisos.py`) espera una lista de
**anuncios** (diccionarios). Campos habituales (todos opcionales salvo los que hagan
falta para el cálculo):

| Campo | Descripción |
|---|---|
| `titulo` | Nombre/descripción corta del anuncio |
| `url` | Enlace al anuncio original (lo que abre «Ver anuncio») |
| `zona` | Ciudad / barrio / municipio |
| `precio` | Precio de venta (€) |
| `superficie` | Metros cuadrados |
| `habitaciones` | Nº de habitaciones |
| `alquiler_mensual` | Alquiler esperado (€/mes). Si falta, se estima |
| `estado` | `a reformar` / `reformado` / `obra nueva` / `buen estado` |
| `descripcion` | Texto libre (de aquí se extraen datos que falten) |

**Cualquier fuente que sepa producir esa lista encaja sin tocar el motor.** Ese es el
punto de extensión: ver `rentapisos/fuentes.py`.

---

## 2. El problema legal (por qué NO scrapear los portales)

idealista, Habitaclia (del mismo grupo idealista), Fotocasa (Adevinta), pisos.com, etc.:

- **Prohíben el scraping** en sus condiciones de uso y emplean protecciones anti-bot
  (p. ej. DataDome, Cloudflare). Saltárselas suele infringir el contrato.
- Alegan **derecho *sui generis* sobre su base de datos** (Directiva 96/9/CE, Ley de
  Propiedad Intelectual): extraer una *parte sustancial* de su colección de anuncios
  puede infringirlo aunque los datos sean "públicos".
- **RGPD/LOPDGDD**: los anuncios pueden incluir datos personales (teléfonos de
  particulares, nombres de agentes), con las obligaciones que eso conlleva.

Conclusión: el scraping masivo de portales no es una base sostenible. El modo `--pisos`
por eso **no rastrea**: trabaja sobre datos que tú aportas por una vía legítima.

---

## 3. Fuentes recomendadas

### 3.1. API oficial de idealista  (la vía directa para anuncios)

- Portal: **<https://developers.idealista.com>**. Te das de alta indicando nombre,
  correo y el proyecto; si lo aprueban recibes **`apikey` + `secret`** y la documentación.
- Autenticación **OAuth2**: se codifican las credenciales en base64 y se pide un
  *token* (`/oauth/token`), que luego se envía en las llamadas de búsqueda de inmuebles.
- **Cupo limitado**: el plan de desarrollo permite del orden de **~100 llamadas al mes**;
  para volumen real hay que negociar acceso (suele ser para partners/profesionales).
- Ventaja: datos estructurados y **con derecho de uso**. Mapea la respuesta al esquema
  de la sección 1.

> Es la opción más limpia para obtener anuncios reales, pero el cupo la orienta a
> nichos/segmentos concretos, no a barrer todo el mercado.

### 3.2. Feeds de inmobiliarias  (tu propia oferta o acuerdos)

Muchas inmobiliarias y CRMs inmobiliarios publican sus carteras como **feed XML/JSON**
(formatos tipo *Idealista Feeds*, *Inmovilla*, *Fotocasa Feed*, Kyero, etc.) o permiten
exportar a CSV. Si eres inmobiliaria, colaboras con una, o llegas a un acuerdo, tienes
una fuente legítima y estructurada. Mapea sus campos al esquema del motor
(`normalizar_anuncio` en `rentapisos/fuentes.py` ayuda con los nombres de columna).

### 3.3. Datos públicos  (para *estimar* y *contextualizar*, no para listar)

Estos no te dan anuncios concretos, pero mejoran mucho la **estimación de alquiler** y
la detección de chollos:

- **SERPAVI — Sistema Estatal de Referencia del Precio del Alquiler**
  (<https://serpavi.mivau.gob.es>, Ministerio de Vivienda): precios de alquiler de
  referencia a partir de fuentes tributarias, por sección censal, distrito, municipio,
  provincia y CA. **Ideal para poblar la tabla `rentas_zona` con datos oficiales.**
- **INE**: *Índice de Precios de la Vivienda* (IPV) y el experimental de alquiler
  (IPVA) — evolución de precios; útil para la revalorización proyectada.
- **Catastro** (Sede Electrónica del Catastro): superficie, año de construcción y uso
  por referencia catastral; servicios de consulta (OVC) e INSPIRE.
- **datos.gob.es**: agrega catálogos públicos de vivienda (mapas de precios, etc.).

### 3.4. Lo que tú ya tengas

Un *export* de tu buscador, una lista de URLs que hayas recopilado a mano, una hoja de
cálculo… El modo `--pisos` acepta CSV/JSON/XLSX directamente.

---

## 4. Arquitectura propuesta

```
   ┌─────────────────────────────┐        ┌──────────────────────────────┐
   │ Fuente (intercambiable)     │        │ Motor de rentabilidad         │
   │  · FuenteArchivo (CSV/JSON) │        │  (rentapisos/rentabilidad.py)    │
   │  · FuenteIdealistaAPI       │ ─────▶ │  · parsers                    │
   │  · FuenteFeedInmobiliaria   │ lista  │  · alquiler (zona/SERPAVI/IA) │
   │  · …                        │ de     │  · rentabilidad + hipoteca    │
   └─────────────────────────────┘ dicts  │  · chollos + puntuación       │
                                          │  · panel HTML / web           │
                                          └──────────────────────────────┘
```

- **`Fuente`** (interfaz en `rentapisos/fuentes.py`): cualquier origen implementa
  `anuncios() -> list[dict]` devolviendo el esquema de la sección 1.
- **`normalizar_anuncio`**: traduce nombres de campo alternativos (`m2`, `dormitorios`,
  `precio_venta`, `enlace`…) al esquema canónico, para enchufar feeds sin reescribir el
  motor.
- **Estimación de alquiler por capas**: alquiler del anuncio → tabla `rentas_zona`
  (idealmente poblada con **SERPAVI**) → IA (opcional). Ya implementado en el motor.

### Pasos para producción

1. **Elige la fuente con la que tengas derecho** (API de idealista, feeds, tus datos).
2. Implementa su `Fuente` mapeando al esquema (usa `normalizar_anuncio`).
3. **Puebla `rentas_zona` con SERPAVI** para que la estimación de alquiler sea seria.
4. Reutiliza el motor tal cual para el ranking, los chollos y el panel/web.
5. Respeta cupos, condiciones y RGPD; guarda solo lo necesario.

---

## 5. Aviso

Esta información es orientativa y **no es asesoramiento jurídico**. Antes de montar un
servicio con datos de terceros, revisa sus condiciones y, si vas a operar a escala,
consulta con un profesional. Ver también la sección
[Uso responsable y legal](../README.md#uso-responsable-y-legal) del README.
