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
from typing import Dict, List, Optional

from .rentabilidad import ParametrosRentabilidad, evaluar_piso

CAMPOS_PISOS = [
    "titulo", "zona", "precio", "superficie", "precio_m2", "habitaciones",
    "alquiler_mensual", "alquiler_estimado", "rentabilidad_bruta",
    "rentabilidad_neta", "clasificacion", "url", "fecha",
]


def parametros_desde_config(config) -> ParametrosRentabilidad:
    """Construye los ParametrosRentabilidad a partir del objeto Config."""
    return ParametrosRentabilidad(
        gastos_pct=getattr(config, "gastos_pct", 0.25),
        costes_compra_pct=getattr(config, "costes_compra_pct", 0.11),
        rentas_zona=dict(getattr(config, "rentas_zona", {}) or {}),
    )


def cargar_pisos(ruta: str) -> List[dict]:
    """Lee los anuncios desde un CSV (una fila por piso) o un JSON (lista de objetos)."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encuentra el archivo de pisos '{ruta}'.")
    if ruta.lower().endswith(".json"):
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict):
            datos = datos.get("pisos") or datos.get("anuncios") or []
        return [d for d in datos if isinstance(d, dict)]
    filas: List[dict] = []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            filas.append({(k or "").strip(): v for k, v in fila.items()})
    return filas


def procesar_pisos(filas: List[dict], params: ParametrosRentabilidad) -> List[dict]:
    """Evalúa cada anuncio y devuelve la lista ordenada por rentabilidad neta (desc.).

    Los pisos sin datos suficientes para calcular la rentabilidad quedan al final.
    """
    evaluados = [evaluar_piso(fila, params) for fila in filas]

    def _clave(p: dict):
        neta = p.get("rentabilidad_neta")
        # Los que tienen rentabilidad van primero (True<False al invertir), y dentro,
        # de mayor a menor. Los incompletos, al final.
        return (p.get("completo", False), neta if neta is not None else float("-inf"))

    evaluados.sort(key=_clave, reverse=True)
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


def generar_informe_pisos(pisos: List[dict], ruta_html: str) -> str:
    """Crea un panel HTML autónomo (filtrar/ordenar/abrir anuncio) y devuelve su ruta."""
    datos = json.dumps(pisos, ensure_ascii=False).replace("</", "<\\/")
    salida = _PLANTILLA.replace("/*__DATOS__*/null", datos)
    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(salida)
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
    pisos = procesar_pisos(filas, params)

    base = config.archivo_salida + "_pisos"
    ruta_csv = base + ".csv"
    ruta_html = base + ".html"
    escribir_csv(pisos, ruta_csv)
    generar_informe_pisos(pisos, ruta_html)

    completos = [p for p in pisos if p.get("completo")]
    print("=" * 64)
    print("  RENTABILIDAD DE PISOS")
    print("=" * 64)
    print(f"  Anuncios analizados:     {len(pisos)}")
    print(f"  Con rentabilidad calc.:  {len(completos)}")
    if completos:
        estimados = sum(1 for p in completos if p.get("alquiler_estimado"))
        if estimados:
            print(f"    (de ellos, {estimados} con el alquiler ESTIMADO por zona)")
        print("\n  Mejores por rentabilidad neta:")
        for p in completos[:10]:
            titulo = (p.get("titulo") or p.get("zona") or p.get("url") or "—")[:44]
            print(f"    {p['rentabilidad_neta']:>5.2f}%  {p.get('clasificacion',''):10} {titulo}")
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
</style>
</head>
<body>
<header>
  <h1>Pisos ordenados por rentabilidad</h1>
  <div class="sub" id="resumen"></div>
  <div class="aviso">La rentabilidad es una <b>estimación</b> a partir de los datos del anuncio y de los
  supuestos de gastos/compra configurados. El alquiler marcado <span class="est">(est.)</span> se ha
  estimado por zona. Verifica siempre los números antes de decidir.</div>
</header>
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
const COLS = [
  ["titulo","Piso"],["zona","Zona"],["precio","Precio"],["superficie","m²"],
  ["precio_m2","€/m²"],["habitaciones","Hab."],["alquiler_mensual","Alquiler/mes"],
  ["rentabilidad_bruta","Rent. bruta"],["rentabilidad_neta","Rent. neta"],
  ["clasificacion","Valoración"],["url","Anuncio"],
];
const NUM = new Set(["precio","superficie","precio_m2","habitaciones","alquiler_mensual",
                     "rentabilidad_bruta","rentabilidad_neta"]);
let orden = {col:"rentabilidad_neta", dir:-1};

const $ = s => document.querySelector(s);
const esc = s => (s==null?"":String(s)).replace(/[&<>"]/g, c => (
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtEur = n => (n==null||n==="") ? "" : Number(n).toLocaleString("es-ES") + " €";
const fmtPct = n => (n==null||n==="") ? "" : Number(n).toLocaleString("es-ES",
  {minimumFractionDigits:2, maximumFractionDigits:2}) + " %";

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
  if (col === "precio" || col === "precio_m2") return fmtEur(v);
  if (col === "superficie") return (v==null||v==="") ? "" : `${esc(v)} m²`;
  if (col === "alquiler_mensual") {
    if (v==null||v==="") return "";
    const est = fila.alquiler_estimado ? ` <span class="est">(est.)</span>` : "";
    return fmtEur(v) + est;
  }
  if (col === "rentabilidad_bruta") return fmtPct(v);
  if (col === "rentabilidad_neta") return v==null ? "" : `<span class="neta">${fmtPct(v)}</span>`;
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
  let f = DATOS.filter(r => {
    if (soloCompleto && !r.completo) return false;
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

function pintar() {
  const filas = filtradas();
  $("#cuerpo").innerHTML = filas.map(r =>
    "<tr>" + COLS.map(([c]) => {
      const clase = c==="titulo" ? "tit" : (NUM.has(c) ? "num" : "");
      return `<td class="${clase}">${celda(c,r)}</td>`;
    }).join("") + "</tr>"
  ).join("");
  $("#cuenta").textContent = `${filas.length} piso(s)`;
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
  ["#buscar","#fZona","#fRent","#fPrecio","#fCompleto"].forEach(s => {
    $(s).addEventListener("input", pintar); $(s).addEventListener("change", pintar);
  });
  pintar();
}
init();
</script>
</body>
</html>
"""
