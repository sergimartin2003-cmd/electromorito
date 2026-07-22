"""Genera un informe HTML navegable (buscar, filtrar y ordenar) a partir del CSV."""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional

from .storage import CAMPOS


def _leer_filas(ruta_csv: str) -> List[Dict[str, str]]:
    filas: List[Dict[str, str]] = []
    with open(ruta_csv, "r", encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            filas.append({c: (fila.get(c) or "") for c in CAMPOS})
    return filas


def generar_informe(ruta_csv: str, ruta_html: Optional[str] = None) -> Optional[str]:
    """Crea un HTML autónomo a partir de `ruta_csv`. Devuelve la ruta del HTML o None."""
    if not os.path.exists(ruta_csv):
        return None
    filas = _leer_filas(ruta_csv)
    if ruta_html is None:
        ruta_html = os.path.splitext(ruta_csv)[0] + ".html"

    # JSON seguro para incrustar dentro de <script> (evita cerrar la etiqueta)
    datos = json.dumps(filas, ensure_ascii=False).replace("</", "<\\/")
    salida = _PLANTILLA.replace("/*__DATOS__*/null", datos)

    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(salida)
    return ruta_html


_PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contactos — Informe</title>
<style>
  :root { --bg:#f6f7f9; --card:#fff; --txt:#1c2430; --muted:#6b7684; --bd:#e2e6ea;
          --acc:#2563eb; --gen:#16a34a; --per:#d97706; --gra:#64748b; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f141a; --card:#171d25; --txt:#e6eaef; --muted:#9aa5b1; --bd:#2a323c;
            --acc:#60a5fa; --gen:#4ade80; --per:#fbbf24; --gra:#94a3b8; }
  }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); }
  header { padding:18px 22px; border-bottom:1px solid var(--bd); background:var(--card); }
  h1 { margin:0 0 2px; font-size:19px; }
  .sub { color:var(--muted); font-size:13px; }
  .controles { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
               padding:14px 22px; background:var(--card); border-bottom:1px solid var(--bd);
               position:sticky; top:0; z-index:5; }
  input, select, button { font:inherit; color:var(--txt); background:var(--bg);
         border:1px solid var(--bd); border-radius:8px; padding:8px 10px; }
  input[type=search] { min-width:230px; flex:1; }
  button { background:var(--acc); color:#fff; border:none; cursor:pointer; }
  button.sec { background:var(--bg); color:var(--txt); border:1px solid var(--bd); }
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
  td.nom { white-space:normal; max-width:260px; font-weight:600; }
  a { color:var(--acc); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .pill { font-size:11px; padding:2px 8px; border-radius:999px; font-weight:600;
          border:1px solid var(--bd); }
  .t-genérico { color:var(--gen); border-color:var(--gen); }
  .t-personal { color:var(--per); border-color:var(--per); }
  .t-gratuito, .t-otro { color:var(--gra); border-color:var(--gra); }
  .rel { font-variant-numeric:tabular-nums; font-weight:600; }
  .muted { color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>Contactos recopilados</h1>
  <div class="sub" id="resumen"></div>
</header>
<div class="controles">
  <input type="search" id="buscar" placeholder="Buscar nombre, correo, web…">
  <select id="fTipo"><option value="">Todos los tipos</option></select>
  <select id="fProv"><option value="">Todas las provincias</option></select>
  <select id="fRel">
    <option value="0">Relevancia ≥ 0</option>
    <option value="1">≥ 1</option>
    <option value="3">≥ 3</option>
    <option value="5">≥ 5</option>
  </select>
  <label class="muted"><input type="checkbox" id="fCorreo" style="width:auto"> Solo con correo</label>
  <button class="sec" id="btnCopiar">Copiar correos</button>
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
  ["nombre","Nombre"],["correo","Correo"],["tipo_correo","Tipo"],["telefonos","Teléfonos"],
  ["provincia","Provincia"],["codigo_postal","CP"],["categoria","Categoría"],
  ["relevancia","Rel."],["web","Web"],["redes","Redes"],["fecha","Fecha"],
];
const NUM = new Set(["relevancia"]);
let orden = {col:"relevancia", dir:-1};

const $ = s => document.querySelector(s);
const esc = s => (s==null?"":String(s)).replace(/[&<>"]/g, c => (
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function opciones(sel, valores) {
  const el = $(sel);
  [...new Set(valores.filter(Boolean))].sort().forEach(v => {
    const o = document.createElement("option"); o.value = v; o.textContent = v; el.appendChild(o);
  });
}

function celda(col, fila) {
  const v = fila[col] || "";
  if (col === "correo" && v) return `<a href="mailto:${esc(v)}">${esc(v)}</a>`;
  if (col === "web" && v) return `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(v.replace(/^https?:\/\//,""))}</a>`;
  if (col === "tipo_correo" && v) return `<span class="pill t-${esc(v)}">${esc(v)}</span>`;
  if (col === "relevancia") return `<span class="rel">${esc(v)}</span>`;
  if (col === "redes" && v) return v.split(";").map(u => u.trim()).filter(Boolean)
      .map(u => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\/(www\.)?/,"").split("/")[0])}</a>`).join(" · ");
  if (col === "nombre") return `<span>${esc(v)}</span>`;
  return esc(v);
}

function filtradas() {
  const q = $("#buscar").value.trim().toLowerCase();
  const tipo = $("#fTipo").value, prov = $("#fProv").value;
  const minRel = parseInt($("#fRel").value, 10) || 0;
  const soloCorreo = $("#fCorreo").checked;
  let f = DATOS.filter(r => {
    if (tipo && r.tipo_correo !== tipo) return false;
    if (prov && r.provincia !== prov) return false;
    if ((parseInt(r.relevancia,10)||0) < minRel) return false;
    if (soloCorreo && !r.correo) return false;
    if (q) {
      const blob = (r.nombre+" "+r.correo+" "+r.web+" "+r.provincia+" "+r.categoria).toLowerCase();
      if (!blob.includes(q)) return false;
    }
    return true;
  });
  const c = orden.col;
  f.sort((a,b) => {
    let x=a[c]||"", y=b[c]||"";
    if (NUM.has(c)) { x=parseInt(x,10)||0; y=parseInt(y,10)||0; return (x-y)*orden.dir; }
    return x.localeCompare(y,"es")*orden.dir;
  });
  return f;
}

function pintar() {
  const filas = filtradas();
  $("#cuerpo").innerHTML = filas.map(r =>
    "<tr>" + COLS.map(([c]) => `<td class="${c==='nombre'?'nom':''}">${celda(c,r)}</td>`).join("") + "</tr>"
  ).join("");
  const conCorreo = filas.filter(r => r.correo).length;
  $("#cuenta").textContent = `${filas.length} filas · ${conCorreo} con correo`;
}

function init() {
  $("#resumen").textContent = `${DATOS.length} filas · generado desde el CSV`;
  $("#cabecera").innerHTML = COLS.map(([c,t]) =>
    `<th data-col="${c}">${t}</th>`).join("");
  opciones("#fTipo", DATOS.map(r => r.tipo_correo));
  opciones("#fProv", DATOS.map(r => r.provincia));
  $("#cabecera").querySelectorAll("th").forEach(th => th.onclick = () => {
    const c = th.dataset.col;
    orden = {col:c, dir: orden.col===c ? -orden.dir : (NUM.has(c)?-1:1)};
    pintar();
  });
  ["#buscar","#fTipo","#fProv","#fRel","#fCorreo"].forEach(s => {
    $(s).addEventListener("input", pintar); $(s).addEventListener("change", pintar);
  });
  $("#btnCopiar").onclick = () => {
    const correos = [...new Set(filtradas().map(r => r.correo).filter(Boolean))];
    navigator.clipboard.writeText(correos.join("; ")).then(
      () => { $("#btnCopiar").textContent = `¡${correos.length} copiados!`;
              setTimeout(() => $("#btnCopiar").textContent = "Copiar correos", 1500); });
  };
  pintar();
}
init();
</script>
</body>
</html>
"""
