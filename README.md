# Scraper de contactos de fundaciones, escuelas PFI/IFE y centros de estudios

Herramienta que **abre un navegador real en tu ordenador**, realiza cientos de
búsquedas (una por cada combinación de *categoría* × *ciudad*), entra en las webs
de los resultados y extrae los **correos y teléfonos de contacto publicados**
de forma pública. El objetivo es ayudarte a preparar una lista de organizaciones
(fundaciones de discapacidad, centros de educación especial, escuelas PFI/IFE,
centros de estudios…) a las que ofrecer tus servicios para sus alumnos y personas.

Los resultados se guardan en **`resultados.csv`** y **`resultados.xlsx`**.

> ⚠️ **Antes de usarla, lee la sección [Uso responsable y legal](#uso-responsable-y-legal).**
> Recoger y, sobre todo, *contactar* con estas direcciones tiene obligaciones
> legales en España y la UE (RGPD y LSSI-CE).

---

## Qué hace, paso a paso

1. Lee `config.yaml` y genera la lista de búsquedas (categorías × ubicaciones).
2. Abre Chromium con Playwright y busca cada consulta en DuckDuckGo (o Bing).
3. De cada búsqueda coge las primeras webs (sin repetir dominios ni redes sociales).
4. Entra en cada web, busca sus páginas de *contacto* / *aviso legal* / *quiénes somos*.
5. Extrae correos (`mailto:`, texto y correos camuflados como `nombre [at] dominio`)
   y teléfonos (`tel:`, `+34…`, números con espacios/guiones).
6. Elimina duplicados y va guardando fila a fila en el CSV (a prueba de cortes).
7. Al terminar genera también el Excel.

---

## Requisitos

- **Python 3.9 o superior** — <https://www.python.org/downloads/>
  (en Windows, marca *"Add Python to PATH"* durante la instalación).
- Conexión a internet.

---

## Instalación (una sola vez)

### Opción fácil (recomendada): los lanzadores

- **Windows:** haz **doble clic en `run.bat`**. La primera vez crea el entorno,
  instala todo y ejecuta; las siguientes veces solo ejecuta.
- **Mac:** haz **doble clic en `probar.command`** (prueba rápida) o en
  **`ejecutar.command`** (ejecución completa). La primera vez, macOS puede pedir
  permiso: haz **clic derecho → Abrir → Abrir**. (El archivo `run.bat` es solo de
  Windows, en Mac se ignora.)
- **Linux / Terminal:** `./run.sh` (acepta opciones, p. ej. `./run.sh --prueba`).

### Opción manual

Abre una terminal (en Windows: *PowerShell* o *Símbolo del sistema*) **dentro de
la carpeta del proyecto** y ejecuta:

```bash
# 1) (recomendado) crea un entorno virtual
python -m venv venv

# Actívalo:
#   Windows:      venv\Scripts\activate
#   Mac / Linux:  source venv/bin/activate

# 2) instala las dependencias
pip install -r requirements.txt

# 3) descarga el navegador que usará Playwright
playwright install chromium
```

---

## Configuración

Todo se controla desde **`config.yaml`** (está comentado en español). Lo más útil:

| Opción | Para qué sirve |
|---|---|
| `categorias` | Tipos de organización a buscar. Añade o quita líneas. |
| `ubicaciones` | Ciudades/provincias. Se combinan con cada categoría. |
| `busquedas_extra` | Búsquedas sueltas escritas a mano. |
| `motor_busqueda` | `duckduckgo`, `bing`, `mojeek`, `startpage`, `google`, `auto`, o una lista. |
| `resultados_por_busqueda` | Cuántas webs coger de cada búsqueda. |
| `navegador_visible` | `true` para ver el navegador; `false` para que vaya oculto y más rápido. |
| `respetar_robots` | `true` = respeta el `robots.txt` de cada web (recomendado). |
| `espera_min_segundos` / `espera_max_segundos` | Pausa entre webs para no saturar servidores. |
| `espera_adaptativa` | `true` = sube el ritmo de espera si el buscador te limita. |
| `palabras_relevancia` | Palabras del tema que se cuentan para puntuar cada web. |
| `guardar_solo_relevantes` | `true` = descarta las webs con relevancia 0. |
| `verificar_dominio` | `true` = comprueba por DNS que el dominio del correo existe (más lento). |
| `archivo_salida` | Nombre base de los ficheros de salida. |

**Buscadores.** `duckduckgo` y `mojeek` toleran bien la automatización; `bing` va
razonablemente; `startpage` y `google` son más frágiles (suelen pedir aceptar
cookies o mostrar CAPTCHA). Con `auto` (o una lista) se prueban varios en orden y
se usa el primero que dé resultados — útil si uno empieza a limitarte.

**Resiliencia automática.** Con varios buscadores, si el preferido falla varias
veces seguidas el programa **rota solo** al siguiente (verás `↻ Cambiando de
buscador…`). Y con `espera_adaptativa: true`, cuando detecta que te están limitando
**sube el ritmo de espera** para ser más prudente, y lo baja de nuevo cuando todo
vuelve a ir bien. Así no tienes que estar vigilando la ejecución.

Con las listas de ejemplo salen unas **300 búsquedas** (20 tipos de organización ×
15 ciudades). Cubren fundaciones y asociaciones de discapacidad, colegios y centros
de educación especial, PFI/IFE, centros especiales de empleo y empresas de inserción,
atención temprana, centros de día, residencias, etc. Puedes añadir más ciudades (hay
varias listas para activar quitando el `#`) o quitar tipos que no te interesen.
Para una primera vez, prueba con `--prueba` o baja `max_busquedas`.

---

## Uso

```bash
# Prueba rápida (solo 3 búsquedas) para ver que todo funciona:
python run.py --prueba

# Ejecución completa:
python run.py

# Con otro archivo de configuración:
python run.py -c mi_config.yaml
```

Opciones disponibles:

| Opción | Qué hace |
|---|---|
| `--prueba` | Limita a 3 búsquedas (para comprobar que todo va). |
| `--reiniciar` | Borra los resultados previos y empieza de cero (no reanuda). |
| `--solo-relevantes` | Guarda solo webs con alguna palabra del tema (relevancia > 0). |
| `--salida NOMBRE` / `-o` | Nombre base de los ficheros de salida. |
| `--informe` | No rastrea: solo regenera el panel HTML desde el CSV. |
| `--contactos` | No rastrea: genera la lista depurada de contactos desde el CSV. |
| `--desde-urls ARCHIVO` | No busca: extrae los contactos de una lista de URLs (una por línea). |
| `--pisos ARCHIVO` | No rastrea: calcula la **rentabilidad** de los pisos de un CSV/JSON y genera un panel ordenado (ver más abajo). |
| `--rentas ARCHIVO` | Con `--pisos`/`--web`: carga una tabla de **rentas por zona** (€/m²·mes, p. ej. de SERPAVI) para estimar el alquiler. |
| `--ia` | Con `--pisos`: usa la **IA** (API de Claude) para estimar el alquiler y detectar riesgos en los pisos sin alquiler. |
| `--navegador RUTA` | Usa un Chrome/Chromium ya instalado (si no usas `playwright install`). |
| `-c ARCHIVO` | Usa otro archivo de configuración. |

- Puedes **detenerlo en cualquier momento** con `Ctrl + C`: lo ya recogido queda
  guardado en el CSV.
- Si vuelves a lanzarlo, **reanuda** saltándose los dominios ya visitados
  (recordados en `resultados_dominios_visitados.txt`). Usa `--reiniciar` para no reanudar.
- Si el buscador empieza a limitar las peticiones (muchas búsquedas seguidas sin
  resultados), el programa te **avisa** para que subas las esperas o cambies de buscador.

### Resultado

Se generan **tres** ficheros: `resultados.csv`, `resultados.xlsx` y
`resultados.html` (un panel navegable, ver más abajo). Columnas:

`nombre` · `correo` · `tipo_correo` · `telefonos` · `provincia` · `codigo_postal` ·
`categoria` · `relevancia` · `web` · `redes` · `dominio` · `grupo` · `busqueda` · `fecha`

- **`tipo_correo`**: `genérico` (buzón tipo `info@`, ideal para contacto), `personal`
  (parece `nombre.apellido@`), `gratuito` (gmail, hotmail…) u `otro`.
- **`provincia`** / **`codigo_postal`**: zona de la organización (el CP se detecta
  del texto de la web cuando aparece).
- **`relevancia`**: cuántas palabras del tema (discapacidad, PFI, IFE, inclusión…)
  aparecen en la web. **Cuanto más alto, más probable es que encaje**; un `0` suele
  ser un resultado que no va del tema.
- **`redes`**: enlaces a perfiles de redes sociales (Facebook, Instagram, LinkedIn…),
  útiles como vía de contacto alternativa.
- **`grupo`**: nombre normalizado de la organización. Las filas con el mismo `grupo`
  son probablemente la **misma organización** (aunque aparezca con varias webs), para
  no contactarla dos veces. Al terminar se indica cuántos posibles duplicados hay.

Hay **una fila por cada correo** encontrado (los correos no se repiten en todo el
fichero). El `.xlsx` es cómodo para abrir en Excel/LibreOffice y **ordenar por
`relevancia` o filtrar por `tipo_correo`**. Al terminar, el programa imprime un
resumen con el reparto de correos por tipo y por provincia.

### Panel HTML

Se genera también **`resultados.html`**: ábrelo con doble clic en tu navegador.
Permite **buscar, filtrar** (por tipo de correo, provincia y relevancia mínima),
**ordenar** por cualquier columna y **copiar de golpe todos los correos filtrados**
al portapapeles (botón «Copiar correos»). Los correos son enlaces `mailto:` y las
webs y redes se abren en una pestaña nueva.

Para regenerar solo el panel a partir de un CSV ya existente (sin volver a rastrear):

```bash
python run.py --informe
```

> Consejo: para una lista de contacto en frío, filtra `tipo_correo = genérico` y
> ordena por `relevancia` de mayor a menor.

### Lista depurada para envío (`resultados_contactos.csv`)

Además, se genera **`resultados_contactos.csv`**: **una fila por organización**
(no por correo), eligiendo el **mejor correo** de cada una (prioriza los buzones
genéricos tipo `info@`) y juntando el resto en `todos_los_correos`. Está **ordenada
por relevancia** de mayor a menor, así que es la lista más práctica para empezar a
contactar. Columnas: `nombre`, `correo_principal`, `todos_los_correos`, `telefonos`,
`provincia`, `web`, `relevancia`.

Para regenerarla desde un CSV ya existente: `python run.py --contactos`.

---

## Rentabilidad de pisos (modo `--pisos`)

Además del scraper de contactos, la herramienta incluye un **filtro de pisos por
rentabilidad de alquiler**. La idea: partir de una lista de anuncios, calcular la
rentabilidad de cada uno y quedarte con los mejores, con un panel que **enlaza de
vuelta a cada anuncio** (así "mandas a la gente a la web" del portal original).

> Este modo **no rastrea** ningún portal: trabaja sobre datos que **tú aportas**
> (un export, una lista de anuncios, una API con la que tengas permiso…). Los
> grandes portales inmobiliarios (idealista, Habitaclia, Fotocasa…) **prohíben el
> scraping** en sus condiciones y lo bloquean activamente; consíguelo por una vía
> con la que tengas derecho. Ver [Uso responsable y legal](#uso-responsable-y-legal)
> y, para las fuentes legales y la arquitectura, **[docs/fuentes_de_datos.md](docs/fuentes_de_datos.md)**.

### Cómo se usa

```bash
# Prueba con el fichero de ejemplo incluido:
python run.py --pisos pisos_ejemplo.csv
```

La entrada es un **CSV** (una fila por piso), un **JSON** (lista de objetos) o un
**XLSX** (primera hoja, primera fila = cabecera) con estas columnas —todas opcionales
salvo las que hagan falta para el cálculo:

| Columna | Para qué |
|---|---|
| `titulo` | Nombre/descripción corta del anuncio. |
| `url` | Enlace al anuncio (es lo que abre el botón «Ver anuncio»). |
| `zona` | Ciudad/barrio; sirve para estimar el alquiler si no lo das. |
| `precio` | Precio de venta en €. |
| `superficie` | Metros cuadrados. |
| `habitaciones` | Nº de habitaciones (informativo). |
| `alquiler_mensual` | Alquiler esperado en €/mes. **Si lo dejas vacío**, se estima. |
| `estado` | `a reformar` / `reformado` / `obra nueva`… (si no, se deduce del texto). |
| `planta` | Planta (`ático`, `bajo`, `3`…). Informativo. |
| `ascensor` | `sí` / `no`. Informativo. |

Si no hay `precio`/`superficie`/`habitaciones` en su columna, se intentan **extraer
del texto** (`descripcion` o `texto`), igual que el `estado` (para reformar, reformado,
obra nueva…), la `planta` y el `ascensor`. Si falta `alquiler_mensual`, se **estima**
como `superficie × €/m²·mes` de la zona (tu tabla `rentas_zona` en `config.yaml` y, para
las zonas que falten, una **tabla de referencia orientativa integrada** por provincia —
desactivable con `usar_rentas_referencia: false`); esos pisos se marcan como *(est.)* en
el panel. Así funciona "de fábrica" aunque no configures nada.

### El cálculo

- **Rentabilidad bruta** = `alquiler × 12 ÷ precio × 100`.
- **Rentabilidad neta** = descontando gastos del alquiler y costes de compra:
  `(alquiler·12·(1−gastos_pct)) ÷ (precio·(1+costes_compra_pct)) × 100`.

Cada piso se clasifica en `excelente` / `buena` / `correcta` / `baja` según su
rentabilidad neta, y se calcula el **PER** (*price-to-rent*): años en recuperar la
compra con el alquiler.

**Precio objetivo (para negociar).** Con `rentabilidad_objetivo > 0` (p. ej. 7 %) se
calcula, para cada piso, **a qué precio deberías comprarlo** para lograr esa
rentabilidad neta. El panel muestra la columna «Precio objetivo» (en verde si el precio
actual ya la cumple) y permite filtrar **«solo si cumplen objetivo»**.

**Detección de chollos (comparativa de zona).** Con los pisos del propio fichero se
calcula la **mediana de €/m² de cada zona** (hace falta al menos 2 pisos en la zona) y
se marca 🔥 el que esté un `umbral_chollo` % (10 por defecto) o más **por debajo** de
esa mediana: un indicio de piso infravalorado.

**Puntuación (0–100).** Para ordenar oportunidades de un vistazo, cada piso recibe una
puntuación que combina, de forma transparente: rentabilidad neta (hasta 60 pts),
descuento respecto a la mediana de su zona (hasta 25 pts) y calidad (hasta 15 pts,
restando por estar *a reformar* o tener el alquiler estimado). El panel se ordena por
ella por defecto.

**Escenario de estrés (opcional).** Con `estres_alquiler_pct > 0` se calcula una
rentabilidad neta *pesimista* suponiendo el alquiler ese % más bajo: un test de
resistencia rápido ante bajadas de renta o más vacancia.

**Rentabilidad después de IRPF (opcional).** Con `tipo_irpf > 0` se calcula la
rentabilidad neta *tras impuestos*: descuenta los **intereses de la hipoteca** (gasto
deducible, si hay financiación), aplica la **reducción del 60 %** del rendimiento neto
por alquiler de vivienda habitual (`reduccion_irpf`) y tu **tipo marginal** (`tipo_irpf`).
Refleja que apalancarse baja la factura fiscal. Es una aproximación (no incluye la
amortización del inmueble ni otras deducciones), pero da una idea realista de lo que
queda en el bolsillo.

**Proyección a futuro (opcional).** Con `revalorizacion_anual > 0` se estima, a
`horizonte_anios`, la ganancia por revalorización del precio y el **ROI proyectado**
(revalorización + flujo del alquiler sobre el dinero invertido). Es una proyección
simplificada y conservadora (ignora la amortización del principal y los costes de venta).

**Duplicados.** Si el mismo piso aparece repetido (misma zona, precio y superficie —
p. ej. anunciado en varios portales), se detecta y se conserva solo el mejor; el panel
los oculta por defecto (hay una casilla para mostrarlos).

### Estimación con IA (opcional)

Cuando un anuncio de venta **no trae el alquiler**, en vez de estimarlo solo por la
tabla de zona puedes pedirle a **Claude** que lo estime a partir de la zona, los metros,
las habitaciones y la descripción, y que además **detecte riesgos** (ocupado, derramas o
reforma integral pendiente, planta baja o sin ascensor, precio sospechoso…). El panel
añade entonces una columna **«Riesgos (IA)»** (con el resumen al pasar el ratón).

Es **opcional** y con **degradación elegante**: si no está instalado el SDK o no hay
clave, no falla — se usa la estimación por zona de siempre. Para activarla:

```bash
pip install -r requirements-ia.txt
export ANTHROPIC_API_KEY=...        # o bien:  ant auth login
python run.py --pisos pisos_ejemplo.csv --ia
```

O de forma permanente en `config.yaml` con `usar_ia: true`. Solo se llama a la IA para
los pisos sin alquiler indicado (para acotar el coste); el modelo se configura con
`modelo_ia` (por defecto `claude-opus-4-8`).

### Rentas por zona desde un fichero (SERPAVI)

Para que la estimación del alquiler use datos serios, puedes cargar una tabla de
**€/m²·mes por zona** (por ejemplo, exportada de [SERPAVI](https://serpavi.mivau.gob.es)):

```bash
python run.py --pisos pisos.csv --rentas rentas_zona.csv
```

El fichero (CSV/JSON/XLSX) solo necesita una columna de zona (`zona`, `municipio`,
`provincia`…) y otra de precio (`eur_m2_mes`, `precio_m2`, `renta_m2`, `valor`…). Esas
rentas tienen prioridad sobre la tabla de referencia integrada.

### Interfaz web (opcional)

Si prefieres no usar la terminal, hay una **interfaz web local** (sin dependencias
extra, solo la librería estándar):

```bash
python run.py --web            # abre http://127.0.0.1:8000
python run.py --web --puerto 8080 --ia   # otro puerto y con IA
```

Abre esa dirección en el navegador, **pega tus anuncios** (CSV o JSON) y pulsa
«Analizar»: te devuelve el mismo panel de rentabilidad, ordenado y con enlace a cada
anuncio. No expone nada a internet (escucha solo en tu ordenador) y usa los mismos
ajustes de `config.yaml` (zonas, hipoteca, IA…).

**Con hipoteca (apalancamiento).** Si en `config.yaml` pones `financiacion_pct > 0`,
además se calcula, para cada piso:

- **Cuota mensual** de la hipoteca (sistema francés, con `interes_hipoteca` y `anios_hipoteca`).
- **Cash-flow mensual** = alquiler neto de gastos − cuota (en verde si es positivo, rojo si no).
- **Rentabilidad sobre fondos propios** (*cash-on-cash*) = cash-flow anual ÷ dinero que
  pones de tu bolsillo (entrada + gastos de compra). Es la métrica clave al comprar con
  hipoteca. Con `financiacion_pct: 0` (compra al contado) estas columnas no aparecen.

Todos los supuestos se configuran en `config.yaml`: `gastos_pct`, `costes_compra_pct`,
`rentas_zona`, `financiacion_pct`, `interes_hipoteca` y `anios_hipoteca`.

### Resultado

Se generan `<archivo_salida>_pisos.csv`, `<archivo_salida>_pisos.html` y también
`<archivo_salida>_pisos.md` (un **informe en Markdown** con el resumen, los supuestos,
los chollos y una tabla con las mejores oportunidades y su enlace, listo para pegar en
un email o compartir). El panel
HTML ordena los pisos por puntuación y permite **filtrar por zona, rentabilidad neta
mínima, precio máximo y solo chollos**, ordenar por cualquier columna (puntuación,
rentabilidad, PER, cash-flow, rentabilidad sobre fondos propios…) y abrir cada anuncio
en el portal original. Arriba muestra unos **indicadores** (nº de pisos, rentabilidad
neta media, PER medio, cash-flow medio, nº de chollos), un **mapa de España** con una
burbuja por zona (tamaño = nº de pisos, color = rentabilidad neta media; **clic en una
zona para filtrar**) y dos **gráficos** —«Pisos por valoración» y «Precio vs.
rentabilidad neta» con los chollos resaltados—. Todo se **recalcula al filtrar**, y hay
un botón para **descargar el CSV ya filtrado**. El mapa es SVG en línea (sin mapas
externos): sitúa cada piso por su `zona` con coordenadas de provincias/capitales. Las rentabilidades son **estimaciones**
a partir de los datos del anuncio y de los supuestos configurados: verifícalas antes de decidir.

---

## Consejos y resolución de problemas

- **"playwright: command not found" / no encuentra el navegador** → ejecuta
  `pip install -r requirements.txt` y luego `playwright install chromium`. Si no
  puedes instalarlo, usa un Chrome ya instalado con `--navegador "ruta\a\chrome.exe"`
  (o la opción `ruta_navegador` del `config.yaml`).
- **¿Ya tienes una lista de webs?** → guárdalas en un `.txt` (una por línea) y usa
  `python run.py --desde-urls webs.txt`: extrae los contactos sin buscar.
- **Pocos resultados o el buscador te bloquea** → sube `espera_min_segundos` y
  `espera_max_segundos`, reduce `resultados_por_busqueda`, o pon
  `motor_busqueda: auto` (prueba varios buscadores). No lo lances de forma agresiva.
  El programa **detecta el bloqueo/CAPTCHA** y, en DuckDuckGo, reintenta por su
  versión *lite* antes de rendirse.
- **Va lento** → pon `navegador_visible: false` y deja `bloquear_recursos: true`.
- **Quieres más resultados por búsqueda** → sube `paginas_por_busqueda` (ahora
  funciona tanto en DuckDuckGo como en Bing).
- El detector de teléfonos es **conservador** a propósito (exige `+34` o
  separadores) para evitar falsos positivos; prioriza siempre los enlaces `tel:`.
- **Correos ocultos**: se descifran automáticamente los protegidos por Cloudflare
  (`data-cfemail`) y se aceptan los avisos de cookies de cada web por si tapan los
  datos de contacto.

---

## Uso responsable y legal

Esta herramienta solo recopila información **publicada públicamente** por las
propias organizaciones, y está pensada para un fin legítimo (ofrecer servicios a
centros y fundaciones). Aun así, en España y la UE tienes obligaciones que debes
cumplir **por tu cuenta**:

- **RGPD / LOPDGDD.** Un correo como `nombre.apellido@centro.org` es un dato
  personal. Si guardas y usas estos datos para contactar, debes tener una **base
  legal** (normalmente *interés legítimo* en un contexto B2B), informar del
  tratamiento, permitir el **derecho de oposición/baja** y no conservarlos más de
  lo necesario. Correos genéricos (`info@`, `contacto@`) son menos sensibles, pero
  las mismas obligaciones aplican.
- **LSSI-CE (art. 21).** El **envío de comunicaciones comerciales por email** sin
  consentimiento previo está, por regla general, **prohibido**. Hay margen en
  contactos B2B con relación previa, pero infórmate antes de hacer envíos masivos:
  el spam puede acarrear sanciones. Ofrece siempre una forma sencilla de darse de baja.
- **`robots.txt` y condiciones de cada web.** Mantén `respetar_robots: true` y no
  ignores las condiciones de uso de los sitios.
- **No satures los servidores.** Mantén las pausas entre peticiones (ya vienen
  configuradas). No conviertas esto en un ataque de tráfico.
- **Calidad, no cantidad.** Es mejor una lista pequeña y bien segmentada, contactada
  con respeto, que miles de correos enviados a ciegas.

- **Portales inmobiliarios (modo `--pisos`).** El modo de rentabilidad **no rastrea**
  ningún portal: trabaja sobre datos que tú aportas. Ten en cuenta que idealista,
  Habitaclia, Fotocasa y similares **prohíben el scraping** en sus condiciones de uso,
  emplean protecciones anti-bot y suelen alegar **derecho *sui generis* sobre su base
  de datos** de anuncios. Consigue los datos por una vía con la que tengas derecho
  (su API oficial, *feeds* de inmobiliarias, o acuerdos), no extrayéndolos a lo bruto.

Esta información es orientativa y **no es asesoramiento jurídico**. Si vas a hacer
campañas de contacto a gran escala, consulta con un profesional.

---

## Tests

La lógica de extracción (correos, teléfonos, clasificación, relevancia),
la configuración y el almacenamiento están cubiertos por tests automáticos
que no necesitan navegador ni internet:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Estructura del proyecto

```
electromorito/
├── run.py               # lanzador: python run.py
├── run.sh / run.bat     # lanzadores (Linux/Terminal y Windows)
├── probar.command       # doble clic en Mac: prueba rápida
├── ejecutar.command     # doble clic en Mac: ejecución completa
├── config.yaml          # QUÉ buscar y CÓMO (edítalo tú)
├── requirements.txt     # dependencias
├── requirements-dev.txt # dependencias de test (pytest)
├── pytest.ini           # configuración de los tests
├── scraper/
│   ├── __main__.py      # python -m scraper
│   ├── config.py        # carga config.yaml y genera las búsquedas
│   ├── search.py        # busca en DuckDuckGo / Bing
│   ├── crawl.py         # visita webs y páginas de contacto
│   ├── extract.py       # extrae correos, teléfonos, CP, redes, nombre, clasifica y puntúa
│   ├── storage.py       # guarda CSV + Excel, deduplica, migra y reanuda
│   ├── report.py        # genera el panel HTML navegable
│   ├── contactos.py     # lista depurada (una fila por organización) para envío
│   ├── rentabilidad.py  # motor de rentabilidad de pisos (parsers + cálculo)
│   ├── rentas_referencia.py  # tabla orientativa de €/m²·mes por provincia
│   ├── coordenadas.py   # coordenadas de provincias/capitales para el mapa
│   ├── pisos.py         # modo --pisos: filtra/ordena pisos y genera su panel HTML
│   ├── ia.py            # enriquecimiento opcional con IA (API de Claude)
│   ├── web.py           # interfaz web local del modo --pisos (--web)
│   ├── fuentes.py       # interfaz de fuentes de datos (API/feeds) + normalizador
│   ├── runner.py        # orquesta todo el proceso
│   └── util.py          # utilidades (dominios, pausas, DNS, espera adaptativa)
├── pisos_ejemplo.csv    # anuncios de ejemplo para  python run.py --pisos
└── tests/               # tests automáticos (pytest)
```
