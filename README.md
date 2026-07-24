# Analizador de rentabilidad de pisos

Herramienta que, a partir de una **lista de anuncios de venta** (CSV, JSON o Excel),
calcula la **rentabilidad de alquiler** de cada piso y te ayuda a encontrar los más
rentables. Genera un **CSV**, un **panel HTML interactivo** (con mapa, gráficos,
comparador y filtros) y un **informe** en Markdown, y **enlaza a cada anuncio** original.

> **No rastrea ningún portal.** Trabaja sobre datos que **tú aportas** (un export, una
> lista de anuncios, una API con la que tengas permiso…). Los grandes portales
> inmobiliarios (idealista, Habitaclia, Fotocasa…) **prohíben el scraping**. Para las
> fuentes de datos legales y la arquitectura, ver
> **[docs/fuentes_de_datos.md](docs/fuentes_de_datos.md)**.

---

## Requisitos e instalación

- **Python 3.9 o superior** — <https://www.python.org/downloads/>

```bash
pip install -r requirements.txt
```

(Los lanzadores `run.sh` / `run.bat` crean el entorno e instalan todo la primera vez.)

---

## Uso rápido

```bash
# Analiza un fichero de anuncios y genera CSV + panel + informe:
python run.py --pisos pisos_ejemplo.csv

# O abre la interfaz web local (pega los anuncios en el navegador):
python run.py --web            # http://127.0.0.1:8000
```

| Opción | Qué hace |
|---|---|
| `--pisos ARCHIVO` | Analiza los anuncios de un CSV/JSON/XLSX. |
| `--web` | Interfaz web local: pega los anuncios y obtén el ranking. |
| `--rentas ARCHIVO` | Carga una tabla de rentas por zona (€/m²·mes, p. ej. de SERPAVI). |
| `--ia` | Usa la IA (API de Claude) para estimar el alquiler y detectar riesgos. |
| `--salida NOMBRE` / `-o` | Nombre base de los ficheros de salida. |
| `-c ARCHIVO` | Usa otro archivo de configuración. |
| `--puerto N` | Puerto de la interfaz web (por defecto 8000). |

---

## Datos de entrada

Un **CSV** (una fila por piso), un **JSON** (lista de objetos) o un **XLSX** con estas
columnas — todas opcionales salvo las que hagan falta para el cálculo:

| Columna | Descripción |
|---|---|
| `titulo` | Nombre/descripción corta del anuncio. |
| `url` | Enlace al anuncio (lo que abre «Ver anuncio»). |
| `zona` | Ciudad / barrio / municipio. |
| `precio` | Precio de venta en €. |
| `superficie` | Metros cuadrados. |
| `habitaciones` | Nº de habitaciones. |
| `alquiler_mensual` | Alquiler esperado en €/mes. **Si lo dejas vacío, se estima.** |
| `estado` | `a reformar` / `reformado` / `obra nueva`… (si no, se deduce del texto). |
| `descripcion` | Texto libre (de aquí se extraen datos que falten). |

Si no vienen en su columna, `precio`/`superficie`/`habitaciones`, el `estado`, la planta
y el ascensor se intentan **extraer del texto**. Si falta `alquiler_mensual`, se
**estima** como `superficie × €/m²·mes` de la zona (tu tabla `rentas_zona` en
`config.yaml` y, para las zonas que falten, una **tabla de referencia integrada** por
provincia). Así funciona "de fábrica" aunque no configures nada.

---

## El cálculo

- **Rentabilidad bruta** = `alquiler × 12 ÷ precio × 100`.
- **Rentabilidad neta** = descontando gastos del alquiler y costes de compra:
  `(alquiler·12·(1−gastos_pct)) ÷ (precio·(1+costes_compra_pct)) × 100`.
- **PER** (*price-to-rent*): años en recuperar la compra con el alquiler.
- **Clasificación**: `excelente` / `buena` / `correcta` / `baja`.

**Chollos.** Con los pisos del propio fichero se calcula la **mediana de €/m² de cada
zona** y se marca 🔥 el que esté un `umbral_chollo` % (10 por defecto) o más por debajo.

**Puntuación (0–100).** Combina rentabilidad neta (60), descuento respecto a la mediana
de zona (25) y calidad (15, restando por *a reformar* o alquiler estimado). El panel se
ordena por ella.

**Con hipoteca (apalancamiento).** Con `financiacion_pct > 0`: cuota mensual (sistema
francés), **cash-flow mensual** y **rentabilidad sobre fondos propios** (*cash-on-cash*).

**Después de IRPF.** Con `tipo_irpf > 0`: rentabilidad neta tras impuestos, descontando
los intereses de la hipoteca (deducibles), la reducción del 60 % por alquiler de vivienda
habitual y tu tipo marginal.

**Precio objetivo (break-even).** Con `rentabilidad_objetivo > 0`: a qué precio deberías
comprar cada piso para lograr esa rentabilidad neta. Útil para negociar.

**Escenario de estrés** (`estres_alquiler_pct`) y **proyección** con revalorización
(`revalorizacion_anual`, `horizonte_anios`) son opcionales.

Todos los supuestos se configuran en **`config.yaml`**.

---

## Salidas

Se generan `<archivo_salida>_pisos.csv`, `<archivo_salida>_pisos.html` y
`<archivo_salida>_pisos.md`:

- **CSV** — una fila por piso, con todas las métricas (para Excel/LibreOffice).
- **Panel HTML** (autocontenido, ábrelo con doble clic) — ordena por puntuación y ofrece:
  - **indicadores** (KPIs) que se recalculan al filtrar;
  - un **mapa de España** con una burbuja por zona (tamaño = nº de pisos; color según la
    métrica elegida: rentabilidad, cash-flow, €/m² o precio); **clic para filtrar**;
  - **gráficos** (pisos por valoración, precio vs. rentabilidad con los chollos resaltados);
  - una **tabla** filtrable y ordenable (por zona, rentabilidad mínima, precio máximo,
    solo chollos, solo si cumplen objetivo…);
  - un **comparador**: marca varios pisos y velos enfrentados métrica a métrica;
  - botón para **descargar el CSV ya filtrado**.
- **Informe Markdown** — resumen, supuestos, chollos y una tabla con las mejores
  oportunidades y su enlace, listo para pegar en un email o compartir.

Las rentabilidades son **estimaciones**: verifica los números antes de decidir.

---

## Estimación con IA (opcional)

Cuando un anuncio no trae el alquiler, puedes pedirle a **Claude** que lo estime a partir
de la zona, los metros y la descripción, y que **detecte riesgos** (ocupado, derramas,
reforma integral, sin ascensor, precio sospechoso…). El panel añade una columna
«Riesgos (IA)».

Es **opcional** y con degradación elegante: si no está el SDK o no hay clave, no falla —
se usa la estimación por zona. Para activarla:

```bash
pip install -r requirements-ia.txt
export ANTHROPIC_API_KEY=...        # o bien:  ant auth login
python run.py --pisos pisos_ejemplo.csv --ia
```

O de forma permanente con `usar_ia: true` en `config.yaml`.

---

## Rentas por zona desde un fichero (SERPAVI)

Para que la estimación use datos serios, puedes cargar una tabla de **€/m²·mes por zona**
(por ejemplo, de [SERPAVI](https://serpavi.mivau.gob.es)):

```bash
python run.py --pisos pisos.csv --rentas rentas_zona.csv
```

El fichero solo necesita una columna de zona (`zona`, `municipio`, `provincia`…) y otra
de precio (`eur_m2_mes`, `precio_m2`, `renta_m2`, `valor`…).

---

## Estructura del proyecto

```
electromorito/
├── run.py                    # lanzador:  python run.py --pisos pisos.csv
├── run.sh / run.bat          # lanzadores (Mac/Linux y Windows)
├── probar.command            # doble clic en Mac: analiza el ejemplo
├── ejecutar.command          # doble clic en Mac: abre la interfaz web
├── config.yaml               # supuestos del cálculo (edítalo tú)
├── pisos_ejemplo.csv         # anuncios de ejemplo
├── requirements.txt          # dependencias (PyYAML, openpyxl)
├── requirements-ia.txt       # dependencia opcional de IA (anthropic)
├── requirements-dev.txt      # dependencias de test (pytest)
├── docs/
│   └── fuentes_de_datos.md   # de dónde sacar los anuncios (legal) + arquitectura
├── scraper/
│   ├── __main__.py           # CLI (python -m scraper)
│   ├── config.py             # carga y valida config.yaml
│   ├── rentabilidad.py       # motor de rentabilidad (parsers + cálculo)
│   ├── rentas_referencia.py  # tabla orientativa de €/m²·mes por provincia
│   ├── coordenadas.py        # coordenadas de provincias/capitales para el mapa
│   ├── pisos.py              # orquesta: evalúa, ordena y genera CSV/panel/informe
│   ├── ia.py                 # enriquecimiento opcional con IA (API de Claude)
│   ├── web.py                # interfaz web local (--web)
│   └── fuentes.py            # interfaz de fuentes de datos (API/feeds) + normalizador
└── tests/                    # tests automáticos (pytest)
```

---

## Uso responsable

- **Los datos los aportas tú.** No scrapees los portales: lo prohíben sus condiciones y
  suelen alegar derecho sobre su base de datos. Consíguelos por una vía con la que tengas
  derecho (API oficial, feeds, datos públicos). Ver
  [docs/fuentes_de_datos.md](docs/fuentes_de_datos.md).
- **Las rentabilidades son estimaciones.** Verifica siempre los números y, para decisiones
  de inversión importantes, consulta con un profesional.

---

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
