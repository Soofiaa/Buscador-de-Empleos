"""Laborum.cl: la búsqueda solo funciona con JavaScript, así que se abre con Playwright (Chromium sin ventana).

Verificado el 2026-10-20 (fixture tests/fixtures/laborum_busqueda.json):
  - robots.txt permite /empleos-busqueda-<término>.html (prohíbe, entre otras, `*recientes=true` y `?localidades=`:
    no se usan). El User-Agent es el mismo de la app (no se disfraza de navegador) y Laborum lo acepta.
  - La página arma los resultados pidiendo POST /api/avisos/searchV2?pageSize=20&page=0 (orden por relevancia). Se
    lee ESA respuesta, la que pide la propia página: no se llama a la API por fuera. Cada aviso trae id, titulo,
    empresa, localizacion ("Providencia, Región Metropolitana"), fechaHoraPublicacion ("19-10-2026 14:12:08"),
    modalidadTrabajo y detalle (la descripción completa): no hace falta abrir el detalle (SIN_DETALLE).
  - El enlace del aviso (/empleos/<slug>-<id>.html) se toma del HTML ya armado.
  - Solo se cargan recursos de laborum.cl, sin imágenes ni tipografías: los rastreadores de terceros se cortan.
Sin Playwright instalado (pip install playwright; playwright install chromium), Laborum se detiene con un aviso.
"""
import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict

import pandas as pd

from filtros import normalizar
from geo import ubicacion_indeed
from red import Bloqueo, ErrorFuente, USER_AGENT_HTTP, es_bloqueo, parece_bloqueo

BASE = "https://www.laborum.cl"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval"]
SIN_DETALLE = True             # buscar._buscar_portal no abre detalles: la descripción ya viene completa
TIEMPO_MS = 45_000
_RX_ID = re.compile(r"-(\d{6,})\.html$")


def url_busqueda(termino: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalizar(termino)).strip("-")
    return "%s/empleos-busqueda-%s.html" % (BASE, slug)


def _limpio(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _ubicacion(texto: str) -> str:
    partes = [p.strip() for p in _limpio(texto).split(",") if p.strip()]
    if not partes:
        return ""
    if len(partes) == 1:
        return ubicacion_indeed("", partes[0]) if re.search(r"region", normalizar(partes[0])) else ubicacion_indeed(partes[0])
    return ubicacion_indeed(partes[0], partes[1])


def _fecha(texto: str) -> str:
    try:
        return datetime.strptime(_limpio(texto)[:10], "%d-%m-%Y").date().isoformat()
    except ValueError:
        return ""


def parsear_busqueda(datos, enlaces: Dict[str, str] = None) -> pd.DataFrame:
    """datos: el JSON de searchV2 (dict o texto). enlaces: {id: url} sacados del HTML."""
    if isinstance(datos, str):
        try:
            datos = json.loads(datos)
        except ValueError:
            raise ErrorFuente("la búsqueda de Laborum no devolvió JSON (¿cambió el sitio?)")
    if not isinstance(datos, dict) or not isinstance(datos.get("content"), list):
        raise ErrorFuente("la búsqueda de Laborum no trae 'content' (¿cambió el sitio?)")
    enlaces = enlaces or {}
    filas = []
    for a in datos["content"]:
        if not isinstance(a, dict) or not a.get("id") or not a.get("titulo"):
            continue
        ident, titulo = str(a["id"]), _limpio(a["titulo"])
        url = enlaces.get(ident) or "%s/empleos/%s-%s.html" % (BASE, re.sub(r"[^a-z0-9]+", "-", normalizar(titulo)).strip("-"), ident)
        modalidad = _limpio(a.get("modalidadTrabajo"))
        desc = _limpio(html_mod.unescape(str(a.get("detalle") or "")))
        if modalidad:
            desc = "Modalidad: %s.\n\n%s" % (modalidad, desc)
        filas.append({
            "job_url": url, "title": titulo,
            "company": "" if a.get("confidencial") is True else _limpio(a.get("empresa")),
            "location": _ubicacion(a.get("localizacion")), "description": desc,
            "date_posted": _fecha(a.get("fechaHoraPublicacion") or a.get("fechaPublicacion")),
            "is_remote": "remot" in normalizar(modalidad),
            "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def _abrir_busqueda(url: str):
    """(status de la página, status de searchV2, JSON de searchV2, {id: url}). Separado para poder probar sin navegador."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise Bloqueo("falta Playwright en este equipo (pip install playwright; playwright install chromium)")
    with sync_playwright() as p:
        nav = p.chromium.launch()
        try:
            ctx = nav.new_context(user_agent=USER_AGENT_HTTP, locale="es-CL")
            ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith(BASE)
                      or r.request.resource_type in ("image", "font", "media") else r.continue_())
            page = ctx.new_page()
            capturadas = []
            page.on("response", lambda r: capturadas.append(r) if "/api/avisos/searchV2" in r.url else None)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=TIEMPO_MS)
            except Exception as e:     # TimeoutError de Playwright, red caída...
                raise ErrorFuente("Laborum no respondió (%s)" % type(e).__name__)
            if resp is None or resp.status != 200:
                return (resp.status if resp else 0), 0, None, {}
            for _ in range(TIEMPO_MS // 250):
                if capturadas:
                    break
                page.wait_for_timeout(250)
            if not capturadas:
                raise ErrorFuente("la página de Laborum no pidió sus resultados (¿cambió el sitio?)")
            busq = capturadas[0]
            try:
                datos = busq.json() if busq.status == 200 else None
            except Exception:
                raise ErrorFuente("la búsqueda de Laborum no devolvió JSON (¿cambió el sitio?)")
            if datos and datos.get("content"):
                try:
                    page.wait_for_selector("a[href*='/empleos/']", timeout=10_000)
                except Exception:
                    pass
            hrefs = page.eval_on_selector_all("a[href*='/empleos/']", "els => els.map(e => e.getAttribute('href'))")
            enlaces = {}
            for h in hrefs:
                m = _RX_ID.search((h or "").split("?")[0])
                if m:
                    enlaces.setdefault(m.group(1), h if h.startswith("http") else BASE + h)
            marca = parece_bloqueo(page.content()) if not datos else None
            if marca:
                raise Bloqueo("página de verificación (%s)" % marca)
            return 200, busq.status, datos, enlaces
        finally:
            nav.close()


def listar(termino: str, cliente, robots, abrir=None) -> pd.DataFrame:
    """Mismas reglas que red.pedir: robots.txt antes de visitar, pausa del cliente entre búsquedas y detención ante
    401/403/429 o una verificación."""
    url = url_busqueda(termino)
    rechazo = getattr(robots, "bloqueo", lambda _u: "")(url)
    if rechazo:
        raise Bloqueo("robots.txt rechazó la lectura (%s)" % rechazo)
    if robots.no_disponible(url):
        raise ErrorFuente("no se pudo leer robots.txt (¿sin internet o el sitio no responde?); no se visitó nada")
    if not robots.permitido(url):
        raise ErrorFuente("robots.txt no permite esta URL")
    if hasattr(cliente, "esperar_turno"):
        cliente.esperar_turno()
    status, status_api, datos, enlaces = (abrir or _abrir_busqueda)(url)
    for s in (status, status_api):
        if s and getattr(cliente, "al_responder", None):
            try:
                cliente.al_responder(s)
            except Exception:
                pass
    for s in (status, status_api):
        if es_bloqueo(s):
            raise Bloqueo("HTTP %d" % s)
    if status != 200 or status_api != 200:
        raise ErrorFuente("HTTP %s" % (status if status != 200 else status_api))
    return parsear_busqueda(datos, enlaces)


def detalle(url: str, cliente, robots) -> Dict:
    raise ErrorFuente("Laborum no abre detalles (SIN_DETALLE)")


def completar(fila: dict, det: Dict) -> bool:
    return True
