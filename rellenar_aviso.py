"""Rellena una postulación manual a partir del enlace del aviso.

Solo lee el JSON-LD JobPosting que muchos portales ponen en la página (schema.org).
Si el sitio no lo trae (LinkedIn, Glassdoor…), no adivina: hay que completar a mano.
"""
import html as html_mod
import json
import re

from bs4 import BeautifulSoup

import filtros
import ia
from red import Bloqueo, ErrorFuente, NoEncontrada, USER_AGENT_HTTP, parece_bloqueo, pedir
from urllib.parse import urlsplit

LIMITE_HTML = 1_500_000
MINIMO_TEXTO = 300          # menos que esto: la página llegó vacía y el contenido lo pinta JavaScript
TIEMPO_NAVEGADOR_MS = 20_000
MODALIDADES = ("Remoto", "Híbrido", "Presencial")


def _limpio(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _texto(desc) -> str:
    t = html_mod.unescape(str(desc or ""))
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", t)
    t = BeautifulSoup(t, "html.parser").get_text() if "<" in t else t
    return "\n".join(_limpio(l) for l in t.replace("\r", "\n").splitlines() if l.strip())


def _sueldo(base) -> str:
    if not isinstance(base, dict) or not isinstance(base.get("value"), dict):
        return ""
    v = base["value"]
    mn, mx = v.get("minValue"), v.get("maxValue")
    if not (mn or mx):
        return ""
    miles = lambda x: f"{int(float(x)):,}".replace(",", ".")
    rango = miles(mn or mx) + (f" a {miles(mx)}" if mx and mn and str(mx) != str(mn) else "")
    unidad = {"MONTH": " al mes", "YEAR": " al año", "HOUR": " por hora"}.get(str(v.get("unitText")).upper(), "")
    return f"{_limpio(base.get('currency'))} {rango}{unidad}".strip()


def _ubicacion(ld: dict) -> str:
    if str(ld.get("jobLocationType") or "").upper() == "TELECOMMUTE" and not ld.get("jobLocation"):
        return "Remoto"
    lugar = ld.get("jobLocation")
    if isinstance(lugar, list):
        lugar = lugar[0] if lugar else {}
    if not isinstance(lugar, dict):
        return ""
    dire = lugar.get("address") if isinstance(lugar.get("address"), dict) else {}
    partes = [_limpio(dire.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry")]
    return ", ".join(p for p in partes if p)


def _modalidad(ld: dict, titulo: str, descripcion: str) -> str:
    if str(ld.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        return "Remoto"
    m, _ = filtros.detectar_modalidad(filtros.normalizar(titulo), filtros.normalizar(descripcion), False)
    return m if m in MODALIDADES else ""


def _job_posting(html: str) -> dict | None:
    soup = BeautifulSoup((html or "")[:LIMITE_HTML], "html.parser")
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            ld = json.loads(s.get_text())
        except ValueError:
            continue
        candidatos = ld if isinstance(ld, list) else [ld]
        if isinstance(ld, dict) and isinstance(ld.get("@graph"), list):
            candidatos = ld["@graph"]
        for item in candidatos:
            if isinstance(item, dict) and item.get("@type") in ("JobPosting", ["JobPosting"]):
                return item
    return None


def parsear_aviso(html: str) -> dict:
    """Campos para el formulario manual. Lanza ErrorFuente si no hay JobPosting usable."""
    ld = _job_posting(html)
    if not ld:
        raise ErrorFuente("el aviso no publica datos de empleo (JobPosting); complétalo a mano")
    titulo = _limpio(ld.get("title"))
    org = ld.get("hiringOrganization") if isinstance(ld.get("hiringOrganization"), dict) else {}
    empresa = _limpio(org.get("name"))
    if not titulo or not empresa:
        raise ErrorFuente("el aviso no trae cargo y empresa; complétalo a mano")
    descripcion = _texto(ld.get("description"))
    return {
        "titulo": titulo[:200],
        "empresa": empresa[:200],
        "ubicacion": _ubicacion(ld)[:200],
        "modalidad": _modalidad(ld, titulo, descripcion),
        "sueldo": _sueldo(ld.get("baseSalary"))[:100],
        "descripcion": descripcion[:10000],
    }


def texto_visible(html: str) -> str:
    """El texto que una persona vería en la página (sin scripts ni estilos), recortado para la IA."""
    soup = BeautifulSoup((html or "")[:LIMITE_HTML], "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return "\n".join(_limpio(l) for l in soup.get_text("\n").splitlines() if l.strip())[:8000]


def html_con_navegador(url: str) -> str:
    """Abre el aviso en un Chromium sin ventana y devuelve el HTML ya renderizado. Solo se llama DESPUÉS de que
    pedir() confirmó que robots.txt permite la URL. Solo carga recursos del mismo sitio."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ErrorFuente("falta Playwright en este equipo; completa a mano o pega el texto del aviso")
    partes = urlsplit(url)
    origen = f"{partes.scheme}://{partes.netloc}"
    with sync_playwright() as p:
        nav = p.chromium.launch()
        try:
            ctx = nav.new_context(user_agent=USER_AGENT_HTTP, locale="es-CL")
            ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith(origen)
                      or r.request.resource_type in ("image", "font", "media") else r.continue_())
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=TIEMPO_NAVEGADOR_MS)
                page.wait_for_timeout(2500)          # tiempo para que el JavaScript pinte el aviso
            except Exception as e:
                raise ErrorFuente(f"el navegador no pudo abrir el aviso ({type(e).__name__})")
            contenido = page.content()
            marca = parece_bloqueo(contenido)
            if marca:
                raise Bloqueo("página de verificación (%s)" % marca)
            return contenido
        finally:
            nav.close()


def desde_url(url: str, cliente, robots) -> dict:
    """Saca los datos del aviso, en este orden:
      1. HTML normal (pedir: robots.txt + pausa). Si trae JSON-LD, listo.
      2. Si la página llega vacía (JavaScript), un navegador la renderiza; después se prueba el JSON-LD otra vez.
      3. Lo que quede de texto visible se le pasa a la IA.
    Propaga Bloqueo, NoEncontrada y ErrorFuente."""
    html = pedir(url, cliente, robots)           # aquí se revisa robots.txt; sin permiso no se llega a ningún paso
    try:
        return parsear_aviso(html)
    except ErrorFuente:
        pass
    texto = texto_visible(html)
    if len(texto) < MINIMO_TEXTO:
        html = html_con_navegador(url)
        try:
            return parsear_aviso(html)
        except ErrorFuente:
            pass
        texto = texto_visible(html)
    datos = ia.extraer_aviso(texto)
    if "error" in datos:
        raise ErrorFuente(datos["error"])
    if not datos.get("titulo") and not datos.get("empresa"):      # la IA no encontró nada: no es un éxito
        raise ErrorFuente("no encontré cargo ni empresa en la página; complétalo a mano")
    return datos


def mensaje_error(ex: Exception) -> str:
    if isinstance(ex, Bloqueo):
        return "el sitio rechazó la lectura; complétalo a mano"
    if isinstance(ex, NoEncontrada):
        return "ese enlace no existe (404)"
    if isinstance(ex, ErrorFuente):
        return str(ex)
    return "no se pudo leer el aviso"
