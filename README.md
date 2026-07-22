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

Con las listas de ejemplo salen **240 búsquedas**. Empieza con pocas ciudades
para probar y ve ampliando.

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

## Consejos y resolución de problemas

- **"playwright: command not found" / no encuentra el navegador** → ejecuta
  `pip install -r requirements.txt` y luego `playwright install chromium`.
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
- El detector de teléfonos es **conservador** a propósito (exige `+34` o
  separadores) para evitar falsos positivos; prioriza siempre los enlaces `tel:`.

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
│   ├── runner.py        # orquesta todo el proceso
│   └── util.py          # utilidades (dominios, pausas, DNS, espera adaptativa)
└── tests/               # tests automáticos (pytest)
```
