"""Filtra y ordena pisos por rentabilidad y genera un panel HTML que enlaza a cada anuncio.

Lee una lista de anuncios (CSV o JSON), calcula la rentabilidad de cada uno con
`rentabilidad.evaluar_piso`, los ordena de más a menos rentables y escribe:

  - `<salida>_pisos.csv`   (una fila por piso, ordenada por rentabilidad neta)
  - `<salida>_pisos.html`  (panel navegable: filtra por zona/precio y abre el anuncio)

Es la parte que "manda a la gente a la web": cada fila enlaza al anuncio original.
No usa navegador ni internet: trabaja sobre datos que tú aportas (un export, una
lista de URLs ya extraídas, una API con la que tengas permiso…).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
from statistics import median
from typing import Dict, List, Optional

from .rentabilidad import (
    ParametrosRentabilidad,
    _normalizar,
    evaluar_piso,
    puntuacion,
)

CAMPOS_PISOS = [
    "titulo", "zona", "precio", "superficie", "precio_m2", "mediana_zona_m2",
    "descuento_zona", "es_chollo", "habitaciones", "estado", "planta", "ascensor",
    "terraza", "garaje", "exterior", "alquiler_mensual", "alquiler_estimado",
    "rentabilidad_bruta", "rentabilidad_neta", "rentabilidad_neta_estres", "per",
    "roi_proyectado_pct", "roi_anual_medio_pct", "ganancia_capital",
    "precio_objetivo", "cumple_objetivo", "clasificacion",
    "cuota_hipoteca", "cash_flow_mensual", "rentabilidad_fondos_propios",
    "fondos_propios", "puntuacion", "ia_resumen", "ia_riesgos", "ia_confianza",
    "duplicado", "url", "fecha",
]


def parametros_desde_config(config) -> ParametrosRentabilidad:
    """Construye los ParametrosRentabilidad a partir del objeto Config."""
    # Rentas por zona: parte de la tabla de referencia (si está activada) y encima las
    # del usuario, que siempre tienen prioridad.
    rentas: dict = {}
    if getattr(config, "usar_rentas_referencia", True):
        from .rentas_referencia import RENTAS_REFERENCIA
        rentas.update(RENTAS_REFERENCIA)
    rentas.update(dict(getattr(config, "rentas_zona", {}) or {}))

    return ParametrosRentabilidad(
        gastos_pct=getattr(config, "gastos_pct", 0.25),
        costes_compra_pct=getattr(config, "costes_compra_pct", 0.11),
        rentas_zona=rentas,
        financiacion_pct=getattr(config, "financiacion_pct", 0.0),
        interes_hipoteca=getattr(config, "interes_hipoteca", 0.03),
        anios_hipoteca=getattr(config, "anios_hipoteca", 25),
        umbral_chollo=getattr(config, "umbral_chollo", 10.0),
        revalorizacion_anual=getattr(config, "revalorizacion_anual", 0.0),
        horizonte_anios=getattr(config, "horizonte_anios", 10),
        estres_alquiler_pct=getattr(config, "estres_alquiler_pct", 0.0),
        rentabilidad_objetivo=getattr(config, "rentabilidad_objetivo", 0.0),
    )


def _leer_xlsx(ruta: str) -> List[dict]:
    """Lee un .xlsx (primera hoja, primera fila = cabecera) como lista de dicts."""
    from openpyxl import load_workbook
    wb = load_workbook(ruta, read_only=True, data_only=True)
    ws = wb.active
    filas_iter = ws.iter_rows(values_only=True)
    try:
        cabecera = [str(c).strip() if c is not None else "" for c in next(filas_iter)]
    except StopIteration:
        return []
    filas: List[dict] = []
    for fila in filas_iter:
        d = {cabecera[i]: fila[i] for i in range(min(len(cabecera), len(fila))) if cabecera[i]}
        if any(v not in (None, "") for v in d.values()):
            filas.append(d)
    return filas


def cargar_pisos(ruta: str) -> List[dict]:
    """Lee los anuncios desde un CSV (una fila por piso), un JSON (lista) o un XLSX."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encuentra el archivo de pisos '{ruta}'.")
    if ruta.lower().endswith(".json"):
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict):
            datos = datos.get("pisos") or datos.get("anuncios") or []
        return [d for d in datos if isinstance(d, dict)]
    if ruta.lower().endswith((".xlsx", ".xlsm")):
        return _leer_xlsx(ruta)
    filas: List[dict] = []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            filas.append({(k or "").strip(): v for k, v in fila.items()})
    return filas


def _anotar_zona(pisos: List[dict], params: ParametrosRentabilidad) -> None:
    """Calcula la mediana de €/m² por zona y marca descuento, chollo y puntuación.

    La mediana solo se usa si la zona tiene al menos 2 pisos con precio/m² (para que
    la comparación tenga sentido). Modifica los pisos en el sitio.
    """
    grupos: Dict[str, List[float]] = {}
    for p in pisos:
        z = _normalizar(p.get("zona", ""))
        if z and p.get("precio_m2"):
            grupos.setdefault(z, []).append(p["precio_m2"])
    medianas = {z: median(v) for z, v in grupos.items() if len(v) >= 2}

    for p in pisos:
        z = _normalizar(p.get("zona", ""))
        med = medianas.get(z)
        if med and p.get("precio_m2"):
            desc = (med - p["precio_m2"]) / med * 100
            p["mediana_zona_m2"] = round(med)
            p["descuento_zona"] = round(desc, 1)
            p["es_chollo"] = desc >= params.umbral_chollo
        p["puntuacion"] = puntuacion(p, params)


def _clave_dedup(p: dict) -> Optional[str]:
    """Clave para detectar el mismo piso repetido (misma zona, precio y superficie)."""
    precio, sup = p.get("precio"), p.get("superficie")
    if precio and sup:
        return f"{_normalizar(p.get('zona', ''))}|{precio}|{round(sup)}"
    titulo = _normalizar(p.get("titulo", ""))
    return titulo or None


def _marcar_duplicados(pisos: List[dict]) -> None:
    """Marca como duplicado (en el sitio) todo piso repetido salvo el primero (el mejor)."""
    vistos: set = set()
    for p in pisos:  # ya vienen ordenados de mejor a peor
        clave = _clave_dedup(p)
        p["duplicado"] = bool(clave and clave in vistos)
        if clave:
            vistos.add(clave)


def parsear_texto(texto: str) -> List[dict]:
    """Convierte un texto pegado (CSV o JSON) en una lista de anuncios (dicts)."""
    texto = (texto or "").strip()
    if not texto:
        return []
    if texto[0] in "[{":
        datos = json.loads(texto)
        if isinstance(datos, dict):
            datos = datos.get("pisos") or datos.get("anuncios") or []
        return [d for d in datos if isinstance(d, dict)]
    import io
    filas: List[dict] = []
    for fila in csv.DictReader(io.StringIO(texto)):
        filas.append({(k or "").strip(): v for k, v in fila.items()})
    return filas


def procesar_con_config(config, filas: List[dict]) -> List[dict]:
    """Evalúa los anuncios usando los parámetros del config (incluida la IA si está activa)."""
    params = parametros_desde_config(config)
    if getattr(config, "usar_ia", False):
        from .ia import enriquecer_pisos
        enriquecer_pisos(filas, params,
                         modelo=getattr(config, "modelo_ia", "claude-opus-4-8"),
                         log=lambda *_: None)
    return procesar_pisos(filas, params)


def procesar_pisos(filas: List[dict], params: ParametrosRentabilidad) -> List[dict]:
    """Evalúa cada anuncio y devuelve la lista ordenada por puntuación (desc.).

    Los pisos sin datos suficientes para calcular la rentabilidad quedan al final.
    Marca duplicados (mismo piso repetido) conservando el mejor de cada grupo.
    """
    evaluados = [evaluar_piso(fila, params) for fila in filas]
    _anotar_zona(evaluados, params)

    def _clave(p: dict):
        # Los que tienen rentabilidad van primero; dentro, por puntuación y luego
        # por rentabilidad neta (desempate). Los incompletos, al final.
        punt = p.get("puntuacion")
        neta = p.get("rentabilidad_neta")
        return (
            p.get("completo", False),
            punt if punt is not None else float("-inf"),
            neta if neta is not None else float("-inf"),
        )

    evaluados.sort(key=_clave, reverse=True)
    _marcar_duplicados(evaluados)
    return evaluados


def _a_fila_csv(p: dict, fecha: str) -> Dict[str, str]:
    """Convierte un piso evaluado a la fila de texto del CSV."""
    def _txt(v):
        if v is None:
            return ""
        if isinstance(v, bool):
            return "sí" if v else "no"
        return str(v)

    return {campo: _txt(p.get(campo)) for campo in CAMPOS_PISOS if campo != "fecha"} | {"fecha": fecha}


def escribir_csv(pisos: List[dict], ruta: str) -> None:
    """Escribe los pisos evaluados en un CSV con las columnas de CAMPOS_PISOS."""
    fecha = _dt.date.today().isoformat()
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_PISOS)
        writer.writeheader()
        for p in pisos:
            writer.writerow(_a_fila_csv(p, fecha))


# Columnas del panel: (clave, título). Las de hipoteca solo se muestran si hay financiación.
_COLS_BASE = [
    ("puntuacion", "Puntuación"), ("titulo", "Piso"), ("zona", "Zona"),
    ("precio", "Precio"), ("precio_m2", "€/m²"), ("descuento_zona", "vs. zona"),
    ("superficie", "m²"), ("habitaciones", "Hab."), ("estado", "Estado"),
    ("alquiler_mensual", "Alquiler/mes"), ("rentabilidad_bruta", "Rent. bruta"),
    ("rentabilidad_neta", "Rent. neta"), ("per", "PER (años)"),
    ("clasificacion", "Valoración"),
]
_COLS_ESTRES = [("rentabilidad_neta_estres", "Rent. neta (estrés)")]
_COLS_PROY = [("roi_anual_medio_pct", "ROI medio/año")]
_COLS_OBJ = [("precio_objetivo", "Precio objetivo")]
_COLS_HIPOTECA = [
    ("cuota_hipoteca", "Cuota/mes"), ("cash_flow_mensual", "Cash-flow/mes"),
    ("rentabilidad_fondos_propios", "Rent. s/ fondos"),
]
_COLS_IA = [("ia_riesgos", "Riesgos (IA)")]
_COLS_FIN = [("url", "Anuncio")]
_COLS_NUM = [
    "puntuacion", "precio", "superficie", "precio_m2", "mediana_zona_m2",
    "descuento_zona", "habitaciones", "alquiler_mensual", "rentabilidad_bruta",
    "rentabilidad_neta", "rentabilidad_neta_estres", "per", "roi_anual_medio_pct",
    "roi_proyectado_pct", "ganancia_capital", "precio_objetivo", "cuota_hipoteca",
    "cash_flow_mensual", "rentabilidad_fondos_propios", "fondos_propios",
]


def construir_html_pisos(pisos: List[dict]) -> str:
    """Devuelve el panel HTML autónomo (como cadena) para la lista de pisos evaluados."""
    con_hipoteca = any(p.get("cuota_hipoteca") is not None for p in pisos)
    con_estres = any(p.get("rentabilidad_neta_estres") is not None for p in pisos)
    con_proy = any(p.get("roi_anual_medio_pct") is not None for p in pisos)
    con_ia = any((p.get("ia_riesgos") or p.get("ia_resumen")) for p in pisos)
    con_obj = any(p.get("precio_objetivo") is not None for p in pisos)
    cols = (_COLS_BASE
            + (_COLS_ESTRES if con_estres else [])
            + (_COLS_PROY if con_proy else [])
            + (_COLS_OBJ if con_obj else [])
            + (_COLS_HIPOTECA if con_hipoteca else [])
            + (_COLS_IA if con_ia else [])
            + _COLS_FIN)

    datos = json.dumps(pisos, ensure_ascii=False).replace("</", "<\\/")
    return (
        _PLANTILLA
        .replace("/*__DATOS__*/null", datos)
        .replace("/*__COLS__*/null", json.dumps(cols, ensure_ascii=False))
        .replace("/*__NUMCOLS__*/null", json.dumps(_COLS_NUM))
    )


def generar_informe_pisos(pisos: List[dict], ruta_html: str) -> str:
    """Crea un panel HTML autónomo (filtrar/ordenar/abrir anuncio) y devuelve su ruta."""
    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(construir_html_pisos(pisos))
    return ruta_html


def ejecutar_pisos(config, ruta_entrada: str) -> Optional[int]:
    """Flujo completo del modo pisos. Devuelve cuántos pisos se procesaron (o None si falla)."""
    try:
        filas = cargar_pisos(ruta_entrada)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR al leer los pisos: {e}")
        return None
    if not filas:
        print(f"El archivo '{ruta_entrada}' no contiene anuncios.")
        return 0

    params = parametros_desde_config(config)

    if getattr(config, "usar_ia", False):
        from .ia import enriquecer_pisos
        modelo = getattr(config, "modelo_ia", "claude-opus-4-8")
        print(f"  Enriqueciendo con IA (modelo {modelo}) los pisos sin alquiler…")
        n_ia = enriquecer_pisos(filas, params, modelo=modelo)
        if n_ia:
            print(f"  IA: {n_ia} piso(s) con alquiler/estado estimado por IA.")

    pisos = procesar_pisos(filas, params)

    base = config.archivo_salida + "_pisos"
    ruta_csv = base + ".csv"
    ruta_html = base + ".html"
    escribir_csv(pisos, ruta_csv)
    generar_informe_pisos(pisos, ruta_html)

    completos = [p for p in pisos if p.get("completo")]
    chollos = [p for p in completos if p.get("es_chollo")]
    print("=" * 64)
    print("  RENTABILIDAD DE PISOS")
    print("=" * 64)
    print(f"  Anuncios analizados:     {len(pisos)}")
    print(f"  Con rentabilidad calc.:  {len(completos)}")
    if chollos:
        print(f"  Chollos (bajo mediana):  {len(chollos)} 🔥")
    if completos:
        estimados = sum(1 for p in completos if p.get("alquiler_estimado"))
        if estimados:
            print(f"    (de ellos, {estimados} con el alquiler ESTIMADO por zona)")
        con_hipoteca = params.financiacion_pct > 0
        if con_hipoteca:
            print(f"    (con hipoteca: {int(params.financiacion_pct*100)}% financiado, "
                  f"{params.interes_hipoteca*100:.1f}% interés, {params.anios_hipoteca} años)")
        print("\n  Mejores por puntuación (rentabilidad + descuento de zona + calidad):")
        for p in completos[:10]:
            titulo = (p.get("titulo") or p.get("zona") or p.get("url") or "—")[:34]
            marca = " 🔥" if p.get("es_chollo") else ""
            extra = ""
            if con_hipoteca and p.get("cash_flow_mensual") is not None:
                extra = f"  cash-flow {p['cash_flow_mensual']:>+5} €/mes"
            print(f"    [{p.get('puntuacion', 0):>3}]  {p['rentabilidad_neta']:>5.2f}% neta  "
                  f"{titulo:34}{marca}{extra}")
    print("\n  Ficheros generados:")
    print(f"    CSV:   {ruta_csv}")
    print(f"    Panel: {ruta_html}")
    print("=" * 64)
    return len(pisos)


_PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pisos por rentabilidad</title>
<style>
  :root { --bg:#f6f7f9; --card:#fff; --txt:#1c2430; --muted:#6b7684; --bd:#e2e6ea;
          --acc:#2563eb; --exc:#16a34a; --bue:#65a30d; --cor:#d97706; --baj:#dc2626; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f141a; --card:#171d25; --txt:#e6eaef; --muted:#9aa5b1; --bd:#2a323c;
            --acc:#60a5fa; --exc:#4ade80; --bue:#a3e635; --cor:#fbbf24; --baj:#f87171; }
  }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); }
  header { padding:18px 22px; border-bottom:1px solid var(--bd); background:var(--card); }
  h1 { margin:0 0 2px; font-size:19px; }
  .sub { color:var(--muted); font-size:13px; }
  .aviso { color:var(--muted); font-size:12px; margin-top:6px; }
  .controles { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
               padding:14px 22px; background:var(--card); border-bottom:1px solid var(--bd);
               position:sticky; top:0; z-index:5; }
  input, select, button { font:inherit; color:var(--txt); background:var(--bg);
         border:1px solid var(--bd); border-radius:8px; padding:8px 10px; }
  input[type=search] { min-width:220px; flex:1; }
  input[type=number] { width:120px; }
  button { cursor:pointer; }
  button:hover { border-color:var(--acc); color:var(--acc); }
  .cuenta { color:var(--muted); font-size:13px; margin-left:auto; }
  .envoltura { overflow-x:auto; padding:0 22px 40px; }
  table { border-collapse:collapse; width:100%; margin-top:12px; background:var(--card);
          border:1px solid var(--bd); border-radius:10px; overflow:hidden; }
  th, td { padding:9px 11px; text-align:left; border-bottom:1px solid var(--bd);
           vertical-align:top; font-size:14px; white-space:nowrap; }
  th { cursor:pointer; user-select:none; background:var(--card); position:sticky; top:64px;
       font-size:12px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }
  th:hover { color:var(--txt); }
  tr:hover td { background:rgba(127,127,127,.06); }
  td.tit { white-space:normal; max-width:280px; font-weight:600; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; }
  a { color:var(--acc); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .pill { font-size:11px; padding:2px 8px; border-radius:999px; font-weight:700; border:1px solid var(--bd); }
  .c-excelente { color:var(--exc); border-color:var(--exc); }
  .c-buena { color:var(--bue); border-color:var(--bue); }
  .c-correcta { color:var(--cor); border-color:var(--cor); }
  .c-baja, .c-sin.datos, .c-sin { color:var(--baj); border-color:var(--baj); }
  .neta { font-weight:800; font-variant-numeric:tabular-nums; }
  .est { color:var(--muted); font-size:11px; }
  .ver { font-weight:600; }
  .cf-pos { color:var(--exc); font-weight:700; font-variant-numeric:tabular-nums; }
  .cf-neg { color:var(--baj); font-weight:700; font-variant-numeric:tabular-nums; }
  .e-reformar { color:var(--cor); border-color:var(--cor); }
  .e-ok { color:var(--muted); border-color:var(--bd); }
  .punt { display:inline-block; min-width:34px; text-align:center; padding:3px 8px;
          border-radius:8px; font-weight:800; font-variant-numeric:tabular-nums; color:#fff; }
  .p-alta { background:var(--exc); }
  .p-media { background:var(--cor); }
  .p-baja { background:var(--gra, #94a3b8); }
  .chollo { color:var(--baj); border-color:var(--baj); font-weight:800; }
  .tiles { display:flex; flex-wrap:wrap; gap:12px; padding:14px 22px 0; }
  .tile { background:var(--card); border:1px solid var(--bd); border-radius:10px;
          padding:10px 14px; min-width:120px; }
  .tile .k { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.03em; }
  .tile .val { font-size:20px; font-weight:800; font-variant-numeric:tabular-nums; margin-top:2px; }
  tr.dup td { opacity:.5; font-style:italic; }
  .riesgo { display:inline-block; white-space:normal; max-width:280px; color:var(--cor); font-size:13px; }
</style>
</head>
<body>
<header>
  <h1>Pisos ordenados por rentabilidad</h1>
  <div class="sub" id="resumen"></div>
  <div class="aviso">La rentabilidad es una <b>estimación</b> a partir de los datos del anuncio y de los
  supuestos de gastos/compra configurados. El alquiler marcado <span class="est">(est.)</span> se ha
  estimado por zona; 🔥 marca los pisos por debajo de la mediana de €/m² de su zona.
  Verifica siempre los números antes de decidir.</div>
</header>
<div class="tiles" id="tiles"></div>
<div class="controles">
  <input type="search" id="buscar" placeholder="Buscar título, zona…">
  <select id="fZona"><option value="">Todas las zonas</option></select>
  <select id="fRent">
    <option value="0">Rent. neta ≥ 0 %</option>
    <option value="4">≥ 4 %</option>
    <option value="5">≥ 5 %</option>
    <option value="6">≥ 6 %</option>
    <option value="7">≥ 7 %</option>
    <option value="8">≥ 8 %</option>
  </select>
  <input type="number" id="fPrecio" placeholder="Precio máx. €" min="0" step="10000">
  <label class="est"><input type="checkbox" id="fCompleto" style="width:auto" checked> Solo con rentabilidad</label>
  <label class="est"><input type="checkbox" id="fChollo" style="width:auto"> Solo chollos 🔥</label>
  <label class="est"><input type="checkbox" id="fObj" style="width:auto"> Solo si cumplen objetivo</label>
  <label class="est"><input type="checkbox" id="fDup" style="width:auto" checked> Ocultar duplicados</label>
  <button class="sec" id="btnCsv">Descargar CSV filtrado</button>
  <span class="cuenta" id="cuenta"></span>
</div>
<div class="envoltura">
  <table>
    <thead><tr id="cabecera"></tr></thead>
    <tbody id="cuerpo"></tbody>
  </table>
</div>
<script>
const DATOS = /*__DATOS__*/null;
const COLS = /*__COLS__*/null;
const NUM = new Set(/*__NUMCOLS__*/null);
let orden = {col:"puntuacion", dir:-1};

const $ = s => document.querySelector(s);
const esc = s => (s==null?"":String(s)).replace(/[&<>"]/g, c => (
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtEur = n => (n==null||n==="") ? "" : Number(n).toLocaleString("es-ES") + " €";
const fmtPct = n => (n==null||n==="") ? "" : Number(n).toLocaleString("es-ES",
  {minimumFractionDigits:2, maximumFractionDigits:2}) + " %";
const fmtNum = n => (n==null||n==="") ? "" : Number(n).toLocaleString("es-ES",
  {maximumFractionDigits:1});

function opciones(sel, valores) {
  const el = $(sel);
  [...new Set(valores.filter(Boolean))].sort((a,b)=>a.localeCompare(b,"es")).forEach(v => {
    const o = document.createElement("option"); o.value = v; o.textContent = v; el.appendChild(o);
  });
}

function celda(col, fila) {
  const v = fila[col];
  if (col === "url") return v ? `<a class="ver" href="${esc(v)}" target="_blank" rel="noopener">Ver anuncio →</a>` : "";
  if (col === "titulo") return `<span>${esc(v || "(sin título)")}</span>`;
  if (col === "puntuacion") {
    if (v==null||v==="") return "";
    const b = v >= 70 ? "p-alta" : (v >= 45 ? "p-media" : "p-baja");
    return `<span class="punt ${b}">${esc(v)}</span>`;
  }
  if (col === "descuento_zona") {
    if (v==null||v==="") return "";
    const chollo = fila.es_chollo ? ' <span class="pill chollo">🔥 chollo</span>' : "";
    if (Number(v) > 0) return `<span class="cf-pos">▼ ${fmtNum(v)} %</span>${chollo}`;
    if (Number(v) < 0) return `<span class="cf-neg">▲ ${fmtNum(-v)} %</span>`;
    return "0 %";
  }
  if (col === "per") return (v==null||v==="") ? "" : `${fmtNum(v)} años`;
  if (col === "precio_objetivo") {
    if (v==null||v==="") return "";
    const cls = fila.cumple_objetivo ? "cf-pos" : "";
    return `<span class="${cls}">${fmtEur(v)}</span>`;
  }
  if (col === "precio" || col === "precio_m2") return fmtEur(v);
  if (col === "superficie") return (v==null||v==="") ? "" : `${esc(v)} m²`;
  if (col === "alquiler_mensual") {
    if (v==null||v==="") return "";
    const est = fila.alquiler_estimado ? ` <span class="est">(est.)</span>` : "";
    return fmtEur(v) + est;
  }
  if (col === "rentabilidad_bruta") return fmtPct(v);
  if (col === "rentabilidad_neta_estres" || col === "roi_anual_medio_pct") return fmtPct(v);
  if (col === "rentabilidad_neta") return v==null ? "" : `<span class="neta">${fmtPct(v)}</span>`;
  if (col === "rentabilidad_fondos_propios") return v==null ? "" : `<span class="neta">${fmtPct(v)}</span>`;
  if (col === "cuota_hipoteca") return fmtEur(v);
  if (col === "cash_flow_mensual") {
    if (v==null||v==="") return "";
    const cls = Number(v) < 0 ? "cf-neg" : "cf-pos";
    return `<span class="${cls}">${fmtEur(v)}</span>`;
  }
  if (col === "estado") {
    if (!v) return "";
    const cls = (v === "a reformar") ? "e-reformar" : "e-ok";
    return `<span class="pill ${cls}">${esc(v)}</span>`;
  }
  if (col === "ia_riesgos") {
    const t = fila.ia_resumen ? ` title="${esc(fila.ia_resumen)}"` : "";
    if (v) return `<span class="riesgo"${t}>${esc(v)}</span>`;
    return fila.ia_resumen ? `<span class="est"${t}>ℹ︎ resumen</span>` : "";
  }
  if (col === "clasificacion") {
    const cls = "c-" + esc(v || "sin").split(" ")[0];
    return v ? `<span class="pill ${cls}">${esc(v)}</span>` : "";
  }
  return esc(v);
}

function filtradas() {
  const q = $("#buscar").value.trim().toLowerCase();
  const zona = $("#fZona").value;
  const minRent = parseFloat($("#fRent").value) || 0;
  const maxPrecio = parseFloat($("#fPrecio").value);
  const soloCompleto = $("#fCompleto").checked;
  const soloChollo = $("#fChollo").checked;
  const soloObjetivo = $("#fObj").checked;
  const ocultarDup = $("#fDup").checked;
  let f = DATOS.filter(r => {
    if (ocultarDup && r.duplicado) return false;
    if (soloCompleto && !r.completo) return false;
    if (soloChollo && !r.es_chollo) return false;
    if (soloObjetivo && !r.cumple_objetivo) return false;
    if (zona && r.zona !== zona) return false;
    const neta = (r.rentabilidad_neta==null) ? -Infinity : Number(r.rentabilidad_neta);
    if (neta < minRent) return false;
    if (!isNaN(maxPrecio) && r.precio && Number(r.precio) > maxPrecio) return false;
    if (q) {
      const blob = ((r.titulo||"")+" "+(r.zona||"")+" "+(r.url||"")).toLowerCase();
      if (!blob.includes(q)) return false;
    }
    return true;
  });
  const c = orden.col;
  f.sort((a,b) => {
    let x=a[c], y=b[c];
    if (NUM.has(c)) {
      x = (x==null||x==="") ? -Infinity : Number(x);
      y = (y==null||y==="") ? -Infinity : Number(y);
      return (x-y)*orden.dir;
    }
    return String(x||"").localeCompare(String(y||""),"es")*orden.dir;
  });
  return f;
}

function media(filas, campo) {
  const v = filas.map(r => r[campo]).filter(x => x!=null && x!=="").map(Number);
  return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null;
}

function tiles(filas) {
  const conRent = filas.filter(r => r.completo);
  const mNeta = media(conRent, "rentabilidad_neta");
  const mPer = media(conRent, "per");
  const mCash = media(conRent, "cash_flow_mensual");
  const nChollos = filas.filter(r => r.es_chollo).length;
  const t = [
    ["Pisos", filas.length],
    ["Con rentabilidad", conRent.length],
    ["Rent. neta media", mNeta==null ? "—" : fmtPct(mNeta)],
    ["PER medio", mPer==null ? "—" : fmtNum(mPer)+" años"],
  ];
  if (conRent.some(r => r.cash_flow_mensual!=null))
    t.push(["Cash-flow medio", mCash==null ? "—" : fmtEur(Math.round(mCash))+"/mes"]);
  t.push(["Chollos", nChollos + (nChollos? " 🔥":"")]);
  $("#tiles").innerHTML = t.map(([k,v]) =>
    `<div class="tile"><div class="k">${esc(k)}</div><div class="val">${v}</div></div>`).join("");
}

function pintar() {
  const filas = filtradas();
  $("#cuerpo").innerHTML = filas.map(r =>
    `<tr class="${r.duplicado ? 'dup' : ''}">` + COLS.map(([c]) => {
      const clase = c==="titulo" ? "tit" : (NUM.has(c) ? "num" : "");
      return `<td class="${clase}">${celda(c,r)}</td>`;
    }).join("") + "</tr>"
  ).join("");
  $("#cuenta").textContent = `${filas.length} piso(s)`;
  tiles(filas);
}

function descargarCsv() {
  const filas = filtradas();
  const cabecera = COLS.map(([,t]) => t);
  const lineas = [cabecera.join(",")];
  for (const r of filas) {
    const celdas = COLS.map(([c]) => {
      let v = r[c];
      if (v==null) v = "";
      else if (typeof v === "boolean") v = v ? "sí" : "no";
      v = String(v);
      return /[",\n]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v;
    });
    lineas.push(celdas.join(","));
  }
  const blob = new Blob(["﻿"+lineas.join("\n")], {type:"text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pisos_filtrados.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

function init() {
  const completos = DATOS.filter(r => r.completo).length;
  $("#resumen").textContent = `${DATOS.length} anuncios · ${completos} con rentabilidad calculada`;
  $("#cabecera").innerHTML = COLS.map(([c,t]) => `<th data-col="${c}">${t}</th>`).join("");
  opciones("#fZona", DATOS.map(r => r.zona));
  $("#cabecera").querySelectorAll("th").forEach(th => th.onclick = () => {
    const c = th.dataset.col;
    orden = {col:c, dir: orden.col===c ? -orden.dir : (NUM.has(c)?-1:1)};
    pintar();
  });
  ["#buscar","#fZona","#fRent","#fPrecio","#fCompleto","#fChollo","#fObj","#fDup"].forEach(s => {
    $(s).addEventListener("input", pintar); $(s).addEventListener("change", pintar);
  });
  $("#btnCsv").addEventListener("click", descargarCsv);
  pintar();
}
init();
</script>
</body>
</html>
"""
