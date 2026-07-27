"""Interfaz web mínima del modo pisos: pega los anuncios y obtén el ranking.

Levanta un pequeño servidor local (solo con la librería estándar, sin dependencias
extra). Abres el navegador, pegas una lista de anuncios (CSV o JSON), y te devuelve
el mismo panel de rentabilidad que genera `--pisos`, ordenado y con enlace a cada
anuncio. Pensado para uso local:  python run.py --web

No expone nada a internet: por defecto escucha en 127.0.0.1.
"""

from __future__ import annotations

import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .pisos import construir_html_pisos, parsear_texto, procesar_con_config

_EJEMPLO = (
    "titulo,url,zona,precio,superficie,habitaciones,alquiler_mensual\n"
    "Piso reformado junto al metro,https://www.habitaclia.com/ej-1,Barcelona,235000,75,3,1150\n"
    "Ático para reformar,https://www.habitaclia.com/ej-2,Barcelona,198000,68,2,\n"
    "Piso con garaje,https://www.idealista.com/ej-3,Madrid,240000,90,3,1300"
)

_FORMULARIO = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rentabilidad de pisos</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --txt:#1c2430; --muted:#6b7684; --bd:#e2e6ea; --acc:#2563eb; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0f141a; --card:#171d25; --txt:#e6eaef; --muted:#9aa5b1; --bd:#2a323c; --acc:#60a5fa; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); }}
  .caja {{ max-width:820px; margin:0 auto; padding:32px 22px 60px; }}
  h1 {{ font-size:24px; margin:0 0 6px; }}
  p.sub {{ color:var(--muted); margin:0 0 22px; }}
  textarea {{ width:100%; min-height:280px; font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;
            padding:12px; border:1px solid var(--bd); border-radius:10px;
            background:var(--card); color:var(--txt); resize:vertical; }}
  .fila {{ display:flex; gap:12px; align-items:center; margin-top:14px; flex-wrap:wrap; }}
  button {{ font:inherit; font-weight:600; background:var(--acc); color:#fff; border:none;
          border-radius:9px; padding:11px 20px; cursor:pointer; }}
  button:hover {{ opacity:.92; }}
  a.demo {{ color:var(--acc); cursor:pointer; text-decoration:none; }}
  a.demo:hover {{ text-decoration:underline; }}
  .aviso {{ color:var(--muted); font-size:13px; margin-top:24px; border-top:1px solid var(--bd); padding-top:16px; }}
  code {{ background:rgba(127,127,127,.14); padding:1px 5px; border-radius:5px; }}
  .error {{ background:#fee2e2; color:#991b1b; border:1px solid #fecaca; border-radius:10px;
          padding:12px 14px; margin-bottom:18px; }}
  @media (prefers-color-scheme: dark) {{ .error {{ background:#3b1618; color:#fca5a5; border-color:#7f1d1d; }} }}
</style></head>
<body><div class="caja">
  <h1>Rentabilidad de pisos</h1>
  <p class="sub">Pega tus anuncios (CSV o JSON) y obtén el ranking por rentabilidad, con
  enlace a cada anuncio. Los datos no salen de tu ordenador.</p>
  {error}
  <form method="post" action="/">
    <textarea name="datos" placeholder="Pega aquí el CSV o el JSON…">{datos}</textarea>
    <div class="fila">
      <button type="submit">Analizar rentabilidad →</button>
      <a class="demo" href="/?demo=1">Cargar datos de ejemplo</a>
    </div>
  </form>
  <div class="aviso">
    Columnas admitidas (todas opcionales salvo las del cálculo):
    <code>titulo</code>, <code>url</code>, <code>zona</code>, <code>precio</code>,
    <code>superficie</code>, <code>habitaciones</code>, <code>alquiler_mensual</code>,
    <code>estado</code>. Si falta el alquiler, se estima por zona (o con IA si la activas).
    Los grandes portales prohíben el scraping: aporta los datos por una vía con la que tengas derecho.
  </div>
</div></body></html>
"""


def _pagina_formulario(datos: str = "", error: str = "") -> str:
    bloque_error = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return _FORMULARIO.format(datos=html.escape(datos), error=bloque_error)


class _Handler(BaseHTTPRequestHandler):
    config = None  # se inyecta al arrancar

    def _responder(self, cuerpo: str, estado: int = 200) -> None:
        datos = cuerpo.encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self) -> None:  # noqa: N802
        partes = urllib.parse.urlparse(self.path)
        if partes.path not in ("/", "/index.html"):
            self._responder("<h1>404</h1>", 404)
            return
        params = urllib.parse.parse_qs(partes.query)
        datos = _EJEMPLO if params.get("demo") else ""
        self._responder(_pagina_formulario(datos))

    def do_POST(self) -> None:  # noqa: N802
        longitud = int(self.headers.get("Content-Length", 0) or 0)
        cuerpo = self.rfile.read(longitud).decode("utf-8", "replace")
        campos = urllib.parse.parse_qs(cuerpo, keep_blank_values=True)
        texto = (campos.get("datos") or [""])[0]
        try:
            filas = parsear_texto(texto)
        except Exception as e:  # noqa: BLE001
            self._responder(_pagina_formulario(texto, f"No se pudo leer el texto: {e}"))
            return
        if not filas:
            self._responder(_pagina_formulario(texto, "No hay anuncios que analizar."))
            return
        pisos = procesar_con_config(self.config, filas)
        self._responder(construir_html_pisos(pisos))

    def log_message(self, *_args) -> None:  # silencia el log por petición
        pass


def iniciar_servidor(config, host: str = "127.0.0.1", puerto: int = 8000) -> None:
    """Arranca el servidor web local hasta que se pulse Ctrl+C."""
    _Handler.config = config
    servidor = ThreadingHTTPServer((host, puerto), _Handler)
    print("=" * 60)
    print("  RENTABILIDAD DE PISOS — interfaz web")
    print("=" * 60)
    print(f"  Abre en tu navegador:  http://{host}:{puerto}")
    print("  (Ctrl+C para parar)")
    print("=" * 60)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
    finally:
        servidor.server_close()
