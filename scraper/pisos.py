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
    "rentabilidad_bruta", "rentabilidad_neta", "rentabilidad_neta_estres",
    "rentabilidad_neta_impuestos", "per",
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
        tipo_irpf=getattr(config, "tipo_irpf", 0.0),
        reduccion_irpf=getattr(config, "reduccion_irpf", 0.60),
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


def _geolocalizar(pisos: List[dict]) -> None:
    """Añade zona_mapa/lat/lon a cada piso emparejando su zona con las coordenadas."""
    from .coordenadas import coordenada_de
    for p in pisos:
        coord = coordenada_de(p.get("zona", ""))
        if coord:
            p["zona_mapa"], p["lat"], p["lon"] = coord


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


def cargar_rentas_zona_csv(ruta: str) -> dict:
    """Lee una tabla de rentas (€/m²·mes por zona) desde CSV/JSON/XLSX → dict {zona: eur}.

    Detecta de forma flexible la columna de zona y la de precio (p. ej. una exportación
    de SERPAVI). Columnas de zona: zona/ciudad/municipio/provincia/… ; de precio:
    eur_m2_mes/euro_m2/precio_m2/renta_m2/valor/renta…
    """
    from .fuentes import _clave  # import diferido (evita ciclo de importación)
    from .rentabilidad import _a_numero

    filas = cargar_pisos(ruta)
    claves_zona = [_clave(k) for k in
                   ("zona", "ciudad", "municipio", "provincia", "poblacion", "localidad",
                    "barrio", "nombre", "seccion", "distrito")]
    claves_val = [_clave(k) for k in
                  ("eurm2mes", "eurosm2mes", "eurm2", "eurosm2", "preciom2", "rentam2",
                   "alquilerm2", "valor", "renta", "importe", "precio")]
    rentas: dict = {}
    for fila in filas:
        norm = {_clave(k): v for k, v in fila.items()}
        zona = next((norm[c] for c in claves_zona if norm.get(c) not in (None, "")), None)
        valor = None
        for c in claves_val:
            if norm.get(c) not in (None, ""):
                valor = _a_numero(norm[c])
                if valor:
                    break
        if zona and valor:
            rentas[str(zona).strip()] = valor
    return rentas


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
    _geolocalizar(evaluados)

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
_COLS_IRPF = [("rentabilidad_neta_impuestos", "Rent. neta (tras IRPF)")]
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
    "rentabilidad_neta", "rentabilidad_neta_estres", "rentabilidad_neta_impuestos", "per",
    "roi_anual_medio_pct", "roi_proyectado_pct", "ganancia_capital", "precio_objetivo",
    "cuota_hipoteca", "cash_flow_mensual", "rentabilidad_fondos_propios", "fondos_propios",
]


def construir_html_pisos(pisos: List[dict]) -> str:
    """Devuelve el panel HTML autónomo (como cadena) para la lista de pisos evaluados."""
    con_hipoteca = any(p.get("cuota_hipoteca") is not None for p in pisos)
    con_estres = any(p.get("rentabilidad_neta_estres") is not None for p in pisos)
    con_irpf = any(p.get("rentabilidad_neta_impuestos") is not None for p in pisos)
    con_proy = any(p.get("roi_anual_medio_pct") is not None for p in pisos)
    con_ia = any((p.get("ia_riesgos") or p.get("ia_resumen")) for p in pisos)
    con_obj = any(p.get("precio_objetivo") is not None for p in pisos)
    cols = (_COLS_BASE
            + (_COLS_ESTRES if con_estres else [])
            + (_COLS_IRPF if con_irpf else [])
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


def _eur(valor) -> str:
    if valor in (None, ""):
        return "—"
    return f"{int(round(float(valor))):,} €".replace(",", ".")


def _pct(valor) -> str:
    if valor in (None, ""):
        return "—"
    return f"{float(valor):.2f}".replace(".", ",") + " %"


def construir_informe_md(pisos: List[dict], params, titulo: str = "Rentabilidad de pisos",
                         top: int = 10) -> str:
    """Devuelve un informe en Markdown con las mejores oportunidades (para email/compartir)."""
    completos = [p for p in pisos if p.get("completo")]
    chollos = [p for p in completos if p.get("es_chollo")]
    con_hip = getattr(params, "financiacion_pct", 0) and params.financiacion_pct > 0

    lineas: List[str] = []
    lineas.append(f"# {titulo}")
    lineas.append(f"_Generado el {_dt.date.today().isoformat()} · {len(pisos)} anuncios, "
                  f"{len(completos)} con rentabilidad calculada._")
    lineas.append("")

    supuestos = [f"gastos {int(params.gastos_pct * 100)} %",
                 f"costes de compra +{int(params.costes_compra_pct * 100)} %"]
    if con_hip:
        supuestos.append(f"hipoteca {int(params.financiacion_pct * 100)} % a "
                         f"{params.anios_hipoteca} años ({params.interes_hipoteca * 100:.1f} %)")
    if getattr(params, "rentabilidad_objetivo", 0) > 0:
        supuestos.append(f"objetivo {params.rentabilidad_objetivo:g} % neto")
    if getattr(params, "tipo_irpf", 0) > 0:
        supuestos.append(f"IRPF {params.tipo_irpf * 100:g} % (reducción "
                         f"{int(params.reduccion_irpf * 100)} %)")
    lineas.append("**Supuestos:** " + "; ".join(supuestos) + ".")
    if chollos:
        lineas.append(f"**Chollos detectados:** {len(chollos)} 🔥 "
                      "(por debajo de la mediana de €/m² de su zona).")
    lineas.append("")

    n = min(top, len(completos))
    lineas.append(f"## Mejores oportunidades (top {n})" if n else "## Sin pisos con rentabilidad")
    if n:
        cabecera = ["#", "Puntuación", "Piso", "Zona", "Precio", "Rent. neta"]
        if con_hip:
            cabecera.append("Cash-flow/mes")
        cabecera.append("Enlace")
        lineas.append("| " + " | ".join(cabecera) + " |")
        lineas.append("|" + "|".join(["---"] * len(cabecera)) + "|")
        for i, p in enumerate(completos[:top], 1):
            nombre = (p.get("titulo") or "(sin título)").replace("|", "/")
            if p.get("es_chollo"):
                nombre += " 🔥"
            fila = [str(i), str(p.get("puntuacion") or ""), nombre, p.get("zona") or "—",
                    _eur(p.get("precio")), _pct(p.get("rentabilidad_neta"))]
            if con_hip:
                cf = p.get("cash_flow_mensual")
                fila.append((f"+{_eur(cf)}" if (cf or 0) >= 0 else _eur(cf)) if cf is not None else "—")
            url = (p.get("url") or "").replace("|", "%7C")
            fila.append(f"[ver anuncio]({url})" if url else "—")
            lineas.append("| " + " | ".join(fila) + " |")
    lineas.append("")
    lineas.append("---")
    lineas.append("_Rentabilidades estimadas a partir de los datos del anuncio y de los supuestos "
                  "configurados: verifica los números antes de decidir. Consigue los anuncios por "
                  "una vía con la que tengas derecho (ver docs/fuentes_de_datos.md)._")
    return "\n".join(lineas)


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
    ruta_md = base + ".md"
    escribir_csv(pisos, ruta_csv)
    generar_informe_pisos(pisos, ruta_html)
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(construir_informe_md(pisos, params))

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
    print(f"    CSV:      {ruta_csv}")
    print(f"    Panel:    {ruta_html}")
    print(f"    Informe:  {ruta_md}")
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
  .graficos { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:14px;
              padding:14px 22px 0; }
  .grafico { background:var(--card); border:1px solid var(--bd); border-radius:10px; padding:12px 14px; }
  .grafico h3 { margin:0 0 8px; font-size:12px; font-weight:700; text-transform:uppercase;
                letter-spacing:.03em; color:var(--muted); }
  .grafico svg { width:100%; height:auto; display:block; }
  .grafico .eje { stroke:var(--bd); stroke-width:1; }
  .grafico .rot { fill:var(--muted); font-size:9px; }
  .grafico .val { fill:var(--txt); font-size:9px; font-weight:700; }
  .grafico.mapa { grid-column:1/-1; max-width:640px; margin:0 auto; width:100%; }
  .mapa .contorno { fill:rgba(127,127,127,.09); stroke:var(--bd); stroke-width:1; }
  .mapa .inset { fill:none; stroke:var(--bd); stroke-width:1; stroke-dasharray:3 3; }
  .mapa .burbuja { cursor:pointer; transition:stroke-width .1s; }
  .mapa .burbuja:hover { stroke:var(--txt); stroke-width:2; }
  .mapa .leyenda { display:flex; gap:14px; flex-wrap:wrap; align-items:center;
                   margin-top:8px; color:var(--muted); font-size:12px; }
  .mapa .leyenda .sw { display:inline-block; width:10px; height:10px; border-radius:50%;
                       margin-right:4px; vertical-align:middle; }
  .mapa .mapactrl { font-size:12px; color:var(--muted); margin-bottom:8px; }
  .mapa .mapactrl select { padding:4px 8px; font-size:12px; }
  .tiles { display:flex; flex-wrap:wrap; gap:12px; padding:14px 22px 0; }
  .tile { background:var(--card); border:1px solid var(--bd); border-radius:10px;
          padding:10px 14px; min-width:120px; }
  .tile .k { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.03em; }
  .tile .val { font-size:20px; font-weight:800; font-variant-numeric:tabular-nums; margin-top:2px; }
  tr.dup td { opacity:.5; font-style:italic; }
  .riesgo { display:inline-block; white-space:normal; max-width:280px; color:var(--cor); font-size:13px; }
  th.chk, td.chk { width:28px; text-align:center; padding-left:14px; }
  td.chk input, th.chk input { cursor:pointer; }
  #comparador { padding:0 22px; }
  .cmp-card { background:var(--card); border:1px solid var(--bd); border-radius:10px;
              padding:14px; margin-top:12px; overflow-x:auto; }
  .cmp-card h3 { margin:0 0 10px; font-size:13px; font-weight:700; text-transform:uppercase;
                 letter-spacing:.03em; color:var(--muted); display:flex; align-items:center; }
  .cmp-tabla { border-collapse:collapse; }
  .cmp-tabla th, .cmp-tabla td { border-bottom:1px solid var(--bd); padding:6px 12px;
                                 text-align:right; white-space:nowrap; font-size:13px;
                                 font-variant-numeric:tabular-nums; }
  .cmp-tabla thead th { text-align:center; font-weight:700; max-width:170px; white-space:normal; }
  .cmp-tabla th.met { text-align:left; color:var(--muted); font-weight:600; }
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
<div class="graficos" id="graficos"></div>
<div id="comparador"></div>
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
let metricaMapa = "neta";
const sel = new Set();   // índices (en DATOS) de los pisos marcados para comparar

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
  if (col === "rentabilidad_neta_estres" || col === "roi_anual_medio_pct"
      || col === "rentabilidad_neta_impuestos") return fmtPct(v);
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

function svgBarras(filas) {
  const orden = [["excelente","--exc"],["buena","--bue"],["correcta","--cor"],["baja","--baj"]];
  const cuenta = {};
  filas.forEach(r => { if (r.clasificacion) cuenta[r.clasificacion] = (cuenta[r.clasificacion]||0)+1; });
  const W=320, H=150, pb=26, pt=16, n=orden.length, bw=42, gap=(W-n*bw)/(n+1);
  const max = Math.max(1, ...orden.map(([k]) => cuenta[k]||0));
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pisos por valoración">`;
  orden.forEach(([k,varc],i) => {
    const c = cuenta[k]||0, h = (H-pb-pt)*(c/max), x = gap + i*(bw+gap), y = H-pb-h;
    s += `<rect x="${x}" y="${y.toFixed(1)}" width="${bw}" height="${h.toFixed(1)}" rx="4" fill="var(${varc})"><title>${k}: ${c}</title></rect>`;
    if (c) s += `<text class="val" x="${x+bw/2}" y="${(y-4).toFixed(1)}" text-anchor="middle">${c}</text>`;
    s += `<text class="rot" x="${x+bw/2}" y="${H-pb+12}" text-anchor="middle">${k}</text>`;
  });
  return s + `<line class="eje" x1="0" y1="${H-pb}" x2="${W}" y2="${H-pb}"/></svg>`;
}

function svgDispersion(filas) {
  const pts = filas.filter(r => r.precio && r.rentabilidad_neta!=null)
    .map(r => ({x:Number(r.precio), y:Number(r.rentabilidad_neta), chollo:r.es_chollo, t:r.titulo||""}));
  const W=320, H=160, pl=34, pr=8, pt=10, pb=22;
  if (!pts.length) return `<svg viewBox="0 0 ${W} ${H}"><text class="rot" x="${W/2}" y="${H/2}" text-anchor="middle">Sin datos</text></svg>`;
  const xs=pts.map(p=>p.x), ys=pts.map(p=>p.y);
  let xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(0,...ys), ymax=Math.max(...ys);
  if (xmax===xmin) { xmax+=1; xmin-=1; }
  if (ymax===ymin) { ymax+=1; }
  const px = x => pl + (W-pl-pr)*((x-xmin)/(xmax-xmin));
  const py = y => (H-pb) - (H-pb-pt)*((y-ymin)/(ymax-ymin));
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Precio frente a rentabilidad neta">`;
  s += `<line class="eje" x1="${pl}" y1="${pt}" x2="${pl}" y2="${H-pb}"/>`;
  s += `<line class="eje" x1="${pl}" y1="${H-pb}" x2="${W-pr}" y2="${H-pb}"/>`;
  s += `<text class="rot" x="${pl}" y="${H-7}" text-anchor="start">${fmtEur(Math.round(xmin))}</text>`;
  s += `<text class="rot" x="${W-pr}" y="${H-7}" text-anchor="end">${fmtEur(Math.round(xmax))}</text>`;
  s += `<text class="rot" x="3" y="${(py(ymax)+3).toFixed(1)}">${fmtNum(ymax)}%</text>`;
  s += `<text class="rot" x="3" y="${H-pb}">${fmtNum(ymin)}%</text>`;
  pts.filter(p=>!p.chollo).forEach(p => {
    s += `<circle cx="${px(p.x).toFixed(1)}" cy="${py(p.y).toFixed(1)}" r="3" fill="var(--acc)" opacity="0.6"><title>${esc(p.t)} — ${fmtEur(p.x)} · ${fmtPct(p.y)}</title></circle>`;
  });
  pts.filter(p=>p.chollo).forEach(p => {
    s += `<circle cx="${px(p.x).toFixed(1)}" cy="${py(p.y).toFixed(1)}" r="5" fill="var(--exc)" stroke="var(--card)" stroke-width="1.5"><title>🔥 ${esc(p.t)} — ${fmtEur(p.x)} · ${fmtPct(p.y)}</title></circle>`;
  });
  return s + `</svg>`;
}

const _media = a => a.length ? a.reduce((x,y)=>x+y,0)/a.length : null;
const _sw = (c,t) => `<span><span class="sw" style="background:${c}"></span>${t}</span>`;

function svgMapa(filas) {
  const grupos = {};
  filas.forEach(r => {
    if (r.lat==null || r.lon==null) return;
    const k = r.zona_mapa || r.zona || "";
    const g = grupos[k] || (grupos[k] = {n:0, chollos:0, lat:r.lat, lon:r.lon, clave:k,
      neta:[], m2:[], cf:[], precio:[]});
    g.n++; if (r.es_chollo) g.chollos++;
    if (r.rentabilidad_neta!=null) g.neta.push(Number(r.rentabilidad_neta));
    if (r.precio_m2!=null) g.m2.push(Number(r.precio_m2));
    if (r.cash_flow_mensual!=null) g.cf.push(Number(r.cash_flow_mensual));
    if (r.precio!=null) g.precio.push(Number(r.precio));
  });
  const lista = Object.values(grupos);
  if (!lista.length)
    return `<div class="grafico mapa"><h3>Mapa por zona</h3>` +
           `<p class="est">No hay pisos geolocalizables (zonas no reconocidas).</p></div>`;

  // Métricas disponibles y la activa
  const conCf = lista.some(g => g.cf.length);
  const opciones = [["neta","Rentabilidad neta"]];
  if (conCf) opciones.push(["cf","Cash-flow/mes"]);
  opciones.push(["m2","€/m²"], ["precio","Precio medio"]);
  const metrica = opciones.some(([v]) => v===metricaMapa) ? metricaMapa : "neta";
  const campo = {neta:"neta", cf:"cf", m2:"m2", precio:"precio"}[metrica];
  const valor = g => _media(g[campo]);

  // Escala de color según el tipo de métrica
  const OP = [0.35,0.55,0.72,0.9];
  let colorDe, leyenda, fmt;
  if (metrica === "neta") {
    fmt = fmtPct;
    colorDe = v => `fill="var(${v>=8?"--exc":v>=6?"--bue":v>=4?"--cor":"--baj"})" fill-opacity="0.8"`;
    leyenda = _sw("var(--exc)","≥8 %")+_sw("var(--bue)","≥6 %")+_sw("var(--cor)","≥4 %")+_sw("var(--baj)","&lt;4 %");
  } else if (metrica === "cf") {
    fmt = v => fmtEur(Math.round(v))+"/mes";
    colorDe = v => `fill="var(${v<0?"--baj":v<100?"--cor":"--exc"})" fill-opacity="0.8"`;
    leyenda = _sw("var(--baj)","negativo")+_sw("var(--cor)","0–100 €")+_sw("var(--exc)","≥100 €");
  } else {  // secuencial (€/m² o precio): un solo tono (--acc) por opacidad
    fmt = v => fmtEur(Math.round(v));
    const vals = lista.map(valor).filter(v => v!=null);
    const min = Math.min(...vals), max = Math.max(...vals), rng = (max-min)||1;
    const bin = v => Math.max(0, Math.min(3, Math.floor((v-min)/rng*4 - 1e-9)));
    colorDe = v => `fill="var(--acc)" fill-opacity="${OP[bin(v)]}"`;
    const corte = i => min + rng*i/4;
    leyenda = [0,1,2,3].map(i =>
      `<span><span class="sw" style="background:var(--acc);opacity:${OP[i]}"></span>`+
      `${fmt(corte(i))}${i<3?"–"+fmt(corte(i+1)):"+"}</span>`).join("");
  }

  const M = {lonMin:-9.5, lonMax:4.5, latMin:35.7, latMax:44.0}, COS = Math.cos(40*Math.PI/180);
  const W = 460, pad = 12, H = Math.round(W*(M.latMax-M.latMin)/((M.lonMax-M.lonMin)*COS));
  const mainX = lon => pad + (lon-M.lonMin)/(M.lonMax-M.lonMin)*(W-2*pad);
  const mainY = lat => pad + (M.latMax-lat)/(M.latMax-M.latMin)*(H-2*pad);
  const ix0=14, iy0=H-70, iw=116, ih=58, C={lonMin:-18.3,lonMax:-13.2,latMin:27.5,latMax:29.6};
  const canX = lon => ix0 + (lon-C.lonMin)/(C.lonMax-C.lonMin)*iw;
  const canY = lat => iy0 + (C.latMax-lat)/(C.latMax-C.latMin)*ih;
  const P = (lon,lat) => lon < -12 ? [canX(lon),canY(lat)] : [mainX(lon),mainY(lat)];
  const OUTLINE = [[-7.69,43.79],[-5.85,43.65],[-3.80,43.46],[-2.92,43.36],[-1.79,43.38],
    [-0.30,43.30],[1.43,42.60],[3.32,42.32],[2.17,41.30],[0.86,40.71],[0.00,40.00],
    [-0.10,39.30],[0.22,38.73],[-0.48,38.35],[-0.72,37.85],[-1.30,37.55],[-2.19,36.72],
    [-3.50,36.70],[-4.42,36.55],[-5.35,36.15],[-5.61,36.01],[-6.29,36.53],[-6.95,37.20],
    [-7.42,37.24],[-7.10,38.02],[-7.01,38.87],[-6.86,40.27],[-6.80,41.03],[-8.20,41.88],
    [-8.87,41.90],[-9.00,42.58],[-8.30,43.20]];

  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mapa por zona">`;
  s += `<path class="contorno" d="M ${OUTLINE.map(([lo,la]) =>
        mainX(lo).toFixed(1)+" "+mainY(la).toFixed(1)).join(" L ")} Z"/>`;
  [[2.65,39.57],[4.00,39.95],[1.43,38.98]].forEach(([lo,la]) => {
    const [x,y]=P(lo,la); s += `<circle class="contorno" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3"/>`;
  });
  s += `<rect class="inset" x="${ix0}" y="${iy0}" width="${iw}" height="${ih}" rx="4"/>`;
  s += `<text class="rot" x="${ix0+4}" y="${iy0+12}">Canarias</text>`;

  lista.sort((a,b) => b.n-a.n);
  lista.forEach(g => {
    const [x,y]=P(g.lon,g.lat), v=valor(g), r=Math.min(24, 5+Math.sqrt(g.n)*3.2);
    const netaTxt = _media(g.neta)!=null ? fmtPct(_media(g.neta)) : "—";
    const info = `${g.clave}: ${g.n} piso(s) · rent. ${netaTxt}`+
                 (v!=null && metrica!=="neta" ? ` · ${fmt(v)}` : "")+(g.chollos?` · ${g.chollos} 🔥`:"");
    const fill = v!=null ? colorDe(v) : `fill="var(--muted)" fill-opacity="0.4"`;
    s += `<circle class="burbuja" data-zona="${esc(g.clave)}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" `+
         `r="${r.toFixed(1)}" ${fill} stroke="var(--card)" stroke-width="1"><title>${esc(info)}</title></circle>`;
    if (r>=9) s += `<text x="${x.toFixed(1)}" y="${(y+3).toFixed(1)}" text-anchor="middle" font-size="9" `+
                   `font-weight="700" fill="var(--txt)" stroke="var(--card)" stroke-width="2.5" `+
                   `paint-order="stroke" style="pointer-events:none">${g.n}</text>`;
  });
  s += `</svg>`;

  const sel = `<div class="mapactrl">Colorear por: <select id="mapaMetrica">`+
    opciones.map(([v,t]) => `<option value="${v}"${v===metrica?" selected":""}>${t}</option>`).join("")+
    `</select></div>`;
  const pie = `<div class="leyenda">${leyenda}`+
    `<span style="margin-left:auto">tamaño = nº de pisos · clic en una zona para filtrar</span></div>`;
  return `<div class="grafico mapa"><h3>Mapa por zona</h3>${sel}${s}${pie}</div>`;
}

function dibujar_graficos(filas) {
  const conRent = filas.filter(r => r.completo);
  const g = $("#graficos");
  if (!conRent.length) { g.innerHTML = ""; return; }
  const chollos = conRent.filter(r => r.es_chollo).length;
  g.innerHTML =
    svgMapa(conRent) +
    `<div class="grafico"><h3>Pisos por valoración</h3>${svgBarras(conRent)}</div>` +
    `<div class="grafico"><h3>Precio vs. rentabilidad neta${chollos ? " · 🔥 chollo" : ""}</h3>${svgDispersion(conRent)}</div>`;
}

const CMP = [
  ["Zona","zona",v=>esc(v)],["Precio","precio",fmtEur],
  ["Superficie","superficie",v=>esc(v)+" m²"],["€/m²","precio_m2",fmtEur],
  ["Hab.","habitaciones",v=>esc(v)],["Estado","estado",v=>esc(v)],
  ["vs. zona","descuento_zona",v=>fmtNum(v)+" %"],
  ["Alquiler/mes","alquiler_mensual",fmtEur],
  ["Rent. bruta","rentabilidad_bruta",fmtPct],["Rent. neta","rentabilidad_neta",fmtPct],
  ["Rent. tras IRPF","rentabilidad_neta_impuestos",fmtPct],
  ["Cash-flow/mes","cash_flow_mensual",fmtEur],
  ["Rent. s/ fondos","rentabilidad_fondos_propios",fmtPct],
  ["PER (años)","per",v=>fmtNum(v)+" años"],
  ["Precio objetivo","precio_objetivo",fmtEur],["Puntuación","puntuacion",v=>esc(v)],
];

function renderComparador() {
  const cont = $("#comparador");
  const pisos = [...sel].map(i => DATOS[i]).filter(Boolean);
  if (!pisos.length) { cont.innerHTML = ""; return; }
  let h = `<div class="cmp-card"><h3>Comparador (${pisos.length})`+
          `<button class="sec" id="cmpLimpiar" style="margin-left:10px">Limpiar</button></h3>`+
          `<table class="cmp-tabla"><thead><tr><th class="met"></th>`;
  pisos.forEach(p => h += `<th>${esc((p.titulo||"(sin título)").slice(0,32))}${p.es_chollo?" 🔥":""}</th>`);
  h += `</tr></thead><tbody>`;
  CMP.forEach(([lab,key,fmt]) => {
    if (!pisos.some(p => p[key]!=null && p[key]!=="")) return;
    h += `<tr><th class="met">${lab}</th>`;
    pisos.forEach(p => h += `<td>${(p[key]==null||p[key]==="") ? "—" : fmt(p[key])}</td>`);
    h += `</tr>`;
  });
  h += `<tr><th class="met">Anuncio</th>`;
  pisos.forEach(p => h += `<td>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">ver →</a>`:"—"}</td>`);
  h += `</tr></tbody></table></div>`;
  cont.innerHTML = h;
  $("#cmpLimpiar").onclick = () => { sel.clear(); renderComparador(); pintar(); };
}

function pintar() {
  const filas = filtradas();
  $("#cuerpo").innerHTML = filas.map(r =>
    `<tr class="${r.duplicado ? 'dup' : ''}">`+
    `<td class="chk"><input type="checkbox" class="cmp" data-i="${r._i}"${sel.has(r._i)?" checked":""}></td>` +
    COLS.map(([c]) => {
      const clase = c==="titulo" ? "tit" : (NUM.has(c) ? "num" : "");
      return `<td class="${clase}">${celda(c,r)}</td>`;
    }).join("") + "</tr>"
  ).join("");
  $("#cuenta").textContent = `${filas.length} piso(s)`;
  tiles(filas);
  dibujar_graficos(filas);
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
  DATOS.forEach((r,i) => r._i = i);
  $("#resumen").textContent = `${DATOS.length} anuncios · ${completos} con rentabilidad calculada`;
  $("#cabecera").innerHTML = `<th class="chk" title="Comparar"></th>` +
    COLS.map(([c,t]) => `<th data-col="${c}">${t}</th>`).join("");
  opciones("#fZona", DATOS.map(r => r.zona));
  $("#cabecera").querySelectorAll("th[data-col]").forEach(th => th.onclick = () => {
    const c = th.dataset.col;
    orden = {col:c, dir: orden.col===c ? -orden.dir : (NUM.has(c)?-1:1)};
    pintar();
  });
  $("#cuerpo").addEventListener("change", e => {
    const c = e.target.closest(".cmp");
    if (!c) return;
    const i = Number(c.getAttribute("data-i"));
    if (c.checked) sel.add(i); else sel.delete(i);
    renderComparador();
  });
  ["#buscar","#fZona","#fRent","#fPrecio","#fCompleto","#fChollo","#fObj","#fDup"].forEach(s => {
    $(s).addEventListener("input", pintar); $(s).addEventListener("change", pintar);
  });
  $("#btnCsv").addEventListener("click", descargarCsv);
  $("#graficos").addEventListener("click", e => {
    const b = e.target.closest(".burbuja");
    if (b) { $("#buscar").value = b.getAttribute("data-zona"); pintar(); }
  });
  $("#graficos").addEventListener("change", e => {
    if (e.target.id === "mapaMetrica") { metricaMapa = e.target.value; pintar(); }
  });
  pintar();
}
init();
</script>
</body>
</html>
"""
