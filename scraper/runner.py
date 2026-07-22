"""Orquesta todo el proceso: buscar -> filtrar -> visitar cada web -> guardar."""

from __future__ import annotations

import sys
from typing import Dict, List

from .config import Config
from .crawl import _USER_AGENT, analizar_web, robots_permite
from .search import aviso_buscador, buscar
from .storage import Almacen
from .util import dominio_registrable, espera_aleatoria


def _log(msg: str) -> None:
    """Imprime siendo tolerante con consolas que no aceptan ciertos caracteres (Windows)."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = (getattr(sys.stdout, "encoding", None) or "utf-8")
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def _dominio_excluido(url: str, config: Config) -> bool:
    dom = dominio_registrable(url)
    if not dom:
        return True
    for excluido in config.dominios_excluidos:
        excluido = excluido.strip().lower()
        if excluido and (dom == excluido or dom.endswith("." + excluido)):
            return True
    return False


def _filtrar_urls(urls: List[str], config: Config) -> List[str]:
    """Quita duplicados por dominio, dominios excluidos y limita al máximo configurado."""
    vistos = set()
    limpias: List[str] = []
    for url in urls:
        if not url or not url.startswith("http"):
            continue
        if _dominio_excluido(url, config):
            continue
        dom = dominio_registrable(url)
        if dom in vistos:
            continue
        vistos.add(dom)
        limpias.append(url)
        if config.resultados_por_busqueda > 0 and len(limpias) >= config.resultados_por_busqueda:
            break
    return limpias


def _lanzar_navegador(p, config: Config):
    """Lanza Chromium. Reintenta con --no-sandbox (necesario en algunos Linux)."""
    args = ["--disable-blink-features=AutomationControlled"]
    headless = not config.navegador_visible
    try:
        return p.chromium.launch(headless=headless, args=args)
    except Exception:
        return p.chromium.launch(headless=headless, args=args + ["--no-sandbox"])


def ejecutar(config: Config) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _log(
            "\nERROR: Playwright no está instalado.\n"
            "Instálalo con:\n"
            "    pip install -r requirements.txt\n"
            "    playwright install chromium\n"
        )
        sys.exit(1)

    consultas = config.construir_busquedas()
    almacen = Almacen(config)

    _log("=" * 64)
    _log("  SCRAPER DE CONTACTOS")
    _log("=" * 64)
    _log(f"  Buscador:            {config.motor_busqueda}")
    _log(f"  Búsquedas a realizar: {len(consultas)}")
    _log(f"  Navegador visible:    {'sí' if config.navegador_visible else 'no'}")
    _log(f"  Salida:               {almacen.ruta_csv}  /  {almacen.ruta_xlsx}")
    if almacen.dominios_vistos:
        _log(f"  Reanudando: {len(almacen.dominios_vistos)} dominios ya visitados se saltarán.")
    _log("=" * 64 + "\n")

    total_correos = len(almacen.correos_vistos)
    total_orgs = 0

    with sync_playwright() as p:
        try:
            navegador = _lanzar_navegador(p, config)
        except Exception as e:  # noqa: BLE001
            _log(
                "\nERROR: no se pudo abrir el navegador Chromium.\n"
                f"Detalle: {e}\n\n"
                "Asegúrate de haber ejecutado:\n"
                "    playwright install chromium\n"
            )
            return

        contexto = navegador.new_context(
            user_agent=_USER_AGENT,
            locale="es-ES",
            viewport={"width": 1366, "height": 900},
        )

        if config.bloquear_recursos:
            def _ruta(route):
                try:
                    if route.request.resource_type in ("image", "media", "font", "stylesheet"):
                        route.abort()
                    else:
                        route.continue_()
                except Exception:
                    # La página pudo cerrarse o la petición ya estar resuelta.
                    pass
            contexto.route("**/*", _ruta)

        page = contexto.new_page()

        vacios_seguidos = 0
        try:
            for i, (categoria, provincia, consulta) in enumerate(consultas, start=1):
                _log(f"[{i}/{len(consultas)}] Buscando: '{consulta}'")
                try:
                    urls = _filtrar_urls(buscar(page, consulta, config), config)
                except Exception as e:  # noqa: BLE001
                    _log(f"    Error en la búsqueda: {e}")
                    urls = []
                _log(f"    -> {len(urls)} webs candidatas")

                # Detecta posible bloqueo del buscador (muchas búsquedas seguidas vacías)
                vacios_seguidos = vacios_seguidos + 1 if not urls else 0
                aviso = aviso_buscador(vacios_seguidos)
                if aviso:
                    _log(f"    ⚠ {aviso}")

                for url in urls:
                    dom = dominio_registrable(url)
                    if dom in almacen.dominios_vistos:
                        continue
                    if not robots_permite(url, config):
                        _log(f"    · (robots.txt no permite)  {dom}")
                        almacen.dominios_vistos.add(dom)
                        continue

                    try:
                        org = analizar_web(page, url, config, categoria, provincia, consulta)
                    except Exception as e:  # noqa: BLE001
                        _log(f"    · error al visitar {dom}: {e}")
                        almacen.dominios_vistos.add(dom)
                        org = None

                    if org:
                        # Filtro opcional: descarta webs sin ninguna señal del tema buscado
                        if config.guardar_solo_relevantes and org.get("relevancia", 0) == 0:
                            almacen.dominios_vistos.add(dom)
                            _log(f"    · {(org.get('nombre') or dom)[:50]} — sin relevancia, descartada")
                        else:
                            nuevos = almacen.guardar_organizacion(org)
                            total_orgs += 1
                            n_correos = len(org.get("correos") or [])
                            rel = org.get("relevancia", 0)
                            etiqueta = org.get("nombre") or dom
                            if n_correos:
                                _log(f"    ✓ {etiqueta[:50]} — {n_correos} correo(s), +{nuevos} nuevo(s) [rel:{rel}]")
                            elif org.get("telefonos"):
                                _log(f"    ~ {etiqueta[:50]} — sin correo, teléfono guardado [rel:{rel}]")
                            else:
                                _log(f"    · {etiqueta[:50]} — sin datos de contacto")

                    espera_aleatoria(config.espera_min_segundos, config.espera_max_segundos)

        except KeyboardInterrupt:
            _log("\n  Interrumpido por el usuario. Guardando lo recogido hasta ahora…")
        finally:
            try:
                navegador.close()
            except Exception:
                pass

    nuevos_correos = len(almacen.correos_vistos) - total_correos
    _log("\n" + "=" * 64)
    _log(f"  FIN. Webs visitadas esta sesión: {total_orgs}")
    _log(f"       Correos nuevos añadidos:    {nuevos_correos}")
    _log(f"       Total de filas en el CSV:   {len(almacen.filas)}")
    if almacen.exportar_excel():
        _log(f"       Excel generado:             {almacen.ruta_xlsx}")
    _log(f"       CSV:                        {almacen.ruta_csv}")
    try:
        from .report import generar_informe
        ruta_html = generar_informe(almacen.ruta_csv)
        if ruta_html:
            _log(f"       Informe HTML:               {ruta_html}")
    except Exception as e:  # noqa: BLE001
        _log(f"       (No se pudo generar el informe HTML: {e})")
    _resumen(almacen)
    _log("=" * 64)


def _resumen(almacen) -> None:
    """Imprime un pequeño desglose de los contactos recogidos."""
    filas = [f for f in almacen.filas if (f.get("correo") or "").strip()]
    if not filas:
        return

    def _cuenta(campo: str):
        conteo: Dict[str, int] = {}
        for f in filas:
            clave = (f.get(campo) or "—").strip() or "—"
            conteo[clave] = conteo.get(clave, 0) + 1
        return sorted(conteo.items(), key=lambda x: x[1], reverse=True)

    _log("\n  Desglose de correos:")
    _log("    Por tipo de correo:")
    for clave, n in _cuenta("tipo_correo"):
        _log(f"      - {clave or '—':12} {n}")
    provincias = _cuenta("provincia")
    if provincias:
        _log("    Por provincia (top 10):")
        for clave, n in provincias[:10]:
            _log(f"      - {clave:22} {n}")
