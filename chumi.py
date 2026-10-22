"""Chumi (chumi-it.com): portal de empleo TI, HTML estático, sin sesión ni navegador.

Verificado el 2026-10-20 (fixtures tests/fixtures/chumi_trabajos.html y chumi_detalle.html):
  - robots.txt permite todo salvo áreas privadas (/adm/, /my/, /api/, /login...). Aprobado por Sofia el 20-10 pese al
    punto 2 de sus Condiciones de Uso (ver NOTAS.md).
  - El buscador /jobs?q= arma los resultados con JavaScript: no sirve. El listado general /trabajos?page=N sí trae en
    el HTML unas 25 tarjetas por página: <a href="/trabajos/<slug>"> con h2 (título, a veces con un código interno
    "ROS1001 - "), el p siguiente (empresa) y dos span (ubicación, casi siempre "Chile" a secas, y modalidad:
    Presencial / Híbrida / Remoto). Sin fecha en la tarjeta.
  - Detalle: GET /trabajos/<slug>. JSON-LD JobPosting con description completa, datePosted, validThrough,
    hiringOrganization, jobLocation y, a veces, baseSalary (en USD).
  - Las páginas por categoría (/empleos/<x>) mezclan avisos de otros sitios (LinkedIn...): no se usan.
"""
import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from bs4 import BeautifulSoup

from filtros import normalizar
from geo import ubicacion_indeed
from red import ErrorFuente, pedir

BASE = "https://chumi-it.com"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval"]
_RX_CODIGO = re.compile(r"^[A-Z]{2,5}\d{3,5}\s*[-–]?\s+")    # "ROS1001 - Consultor..." -> "Consultor..."
MODALIDADES = {"presencial": "Modalidad presencial.", "hibrida": "Modalidad híbrida.", "hibrido": "Modalidad híbrida.",
               "remoto": "Modalidad remota.", "remota": "Modalidad remota."}


def url_busqueda(termino: str) -> str:
    """Los "términos" de Chumi son páginas del listado general ("página 1"): el sitio no tiene búsqueda en HTML."""
    m = re.search(r"\d+", termino or "")
    return "%s/trabajos?page=%d" % (BASE, int(m.group()) if m else 1)


def _limpio(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _ubicacion(texto: str) -> str:
    """"Chile" a secas queda así (como Glassdoor: sin región, el clasificador no la saca de zona); una comuna se
    normaliza al formato de Indeed; otro país queda tal cual (el clasificador lo descarta)."""
    t = _limpio(texto)
    n = normalizar(t)
    if not t or n == "chile":
        return "Chile"
    if "chile" in n or not re.search(r"mexico|peru|colombia|argentina|ecuador|uruguay|latam|brasil|espana", n):
        return ubicacion_indeed(re.sub(r",?\s*chile$", "", t, flags=re.I))
    return t


def parsear_listado(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html or "", "html.parser")
    tarjetas = soup.select('a[href^="/trabajos/"]')
    titulo_pag = soup.title.get_text() if soup.title else ""
    if not tarjetas and "chumi" not in titulo_pag.lower():
        raise ErrorFuente("la página de Chumi no tiene tarjetas de ofertas (¿cambió el sitio?)")
    filas, vistos = [], set()
    for a in tarjetas:
        h2 = a.select_one("h2")
        if not h2:
            continue
        url = BASE + a["href"].split("#")[0].split("?")[0]
        if url in vistos:
            continue
        vistos.add(url)
        empresa = h2.find_next_sibling("p")
        spans = [_limpio(s.get_text(" ")) for s in a.select("span")]
        modalidad = next((MODALIDADES[normalizar(s)] for s in spans if normalizar(s) in MODALIDADES), "")
        filas.append({
            "job_url": url, "title": _RX_CODIGO.sub("", _limpio(h2.get_text(" "))),
            "company": _limpio(empresa.get_text(" ")) if empresa else "",
            "location": _ubicacion(spans[0] if spans else ""), "description": modalidad, "date_posted": "",
            "is_remote": modalidad == "Modalidad remota.",
            "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    return parsear_listado(pedir(url_busqueda(termino), cliente, robots))


def _texto(desc) -> str:
    t = html_mod.unescape(str(desc or ""))
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "\n", t)
    t = BeautifulSoup(t, "html.parser").get_text() if "<" in t else t
    return "\n".join(_limpio(l) for l in t.replace("\r", "\n").splitlines() if l.strip())


def _fecha_iso(valor) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(valor or "")[:19])
    except ValueError:
        return None


def _sueldo(base) -> str:
    """'USD 2.000 a 2.500 al mes'. Solo como texto: los montos no van a min/max_amount porque el clasificador los
    compara en pesos (SUELDO_ALERTA)."""
    if not isinstance(base, dict) or not isinstance(base.get("value"), dict):
        return ""
    v = base["value"]
    mn, mx = v.get("minValue"), v.get("maxValue")
    if not (mn or mx):
        return ""
    miles = lambda x: f"{int(float(x)):,}".replace(",", ".")
    rango = miles(mn or mx) + (f" a {miles(mx)}" if mx and mn and mx != mn else "")
    unidad = {"MONTH": " al mes", "YEAR": " al año", "HOUR": " por hora"}.get(str(v.get("unitText")).upper(), "")
    return f"{_limpio(base.get('currency'))} {rango}{unidad}".strip()


def parsear_detalle(html: str) -> Dict:
    soup = BeautifulSoup(html or "", "html.parser")
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            ld = json.loads(s.get_text())
        except ValueError:
            continue
        if not (isinstance(ld, dict) and ld.get("@type") == "JobPosting"):
            continue
        lugar = ld.get("jobLocation") if isinstance(ld.get("jobLocation"), dict) else {}
        dire = lugar.get("address") if isinstance(lugar.get("address"), dict) else {}
        org = ld.get("hiringOrganization") if isinstance(ld.get("hiringOrganization"), dict) else {}
        publicada = _fecha_iso(ld.get("datePosted"))
        return {"descripcion": _texto(ld.get("description")), "publicada": publicada.date().isoformat() if publicada else "",
                "vence": _fecha_iso(ld.get("validThrough")), "empresa": _limpio(org.get("name")),
                "localidad": _limpio(dire.get("addressLocality")), "region": _limpio(dire.get("addressRegion")),
                "teletrabajo": str(ld.get("jobLocationType") or "").upper() == "TELECOMMUTE",
                "sueldo": _sueldo(ld.get("baseSalary"))}
    raise ErrorFuente("el detalle de Chumi no trae el JSON-LD JobPosting (¿cambió el sitio?)")


def detalle(url: str, cliente, robots) -> Dict:
    return parsear_detalle(pedir(url, cliente, robots))


def completar(fila: dict, det: Dict, ahora: Optional[datetime] = None) -> bool:
    """Devuelve False si el aviso ya venció."""
    ahora = ahora or datetime.now()
    if det["vence"] and det["vence"].date() < ahora.date():
        return False
    modalidad = fila.get("description") or ""          # en el listado, la descripción es solo la modalidad
    desc = det["descripcion"] or modalidad
    if modalidad and modalidad not in desc:
        desc = modalidad + "\n\n" + desc
    if det.get("sueldo"):
        desc += "\n\nSueldo informado (Chumi): %s." % det["sueldo"]
    fila["description"] = desc
    fila["date_posted"] = fila.get("date_posted") or det.get("publicada") or ""
    fila["company"] = fila.get("company") or det.get("empresa") or ""
    if det.get("localidad") and normalizar(det["localidad"]) != "chile":
        fila["location"] = ubicacion_indeed(det["localidad"], det.get("region") or "")
    if det.get("teletrabajo"):
        fila["is_remote"] = True
    return True
