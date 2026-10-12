"""Chiletrabajos: HTML estático, sin sesión ni navegador.

Verificado por la app anterior (2026-10-05; fixtures tests/fixtures/chiletrabajos_*.html):
  - Listado: GET /encuentra-un-empleo/?2=<término>&filterSearch=Buscar. Tarjetas `div.job-item` con `h2.title a`
    (título y /trabajo/<slug>-<id>), `h3.meta` ("Empresa, Ciudad" y la fecha "05 de Octubre de 2026") y
    `p.description` (RECORTADA). Vienen casi de la más nueva a la más antigua. Solo se lee la página 1.
  - Detalle: GET /trabajo/<slug>-<id>. JSON-LD `JobPosting` con description completa, validThrough (vencimiento) y
    jobLocationType ("TELECOMMUTE" = remoto); la tabla trae "Duración" (tipo de contrato).
  - El ícono "trabaja algunos días en tu hogar" NO se toma como modalidad.
La ubicación del listado es solo la ciudad: la región se deduce de la lista de comunas (geo.py).
"""
import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote_plus

import pandas as pd
from bs4 import BeautifulSoup

from filtros import normalizar
from geo import ubicacion_indeed
from red import ErrorFuente, pedir

BASE = "https://www.chiletrabajos.cl"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval"]
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                     "septiembre", "octubre", "noviembre", "diciembre"], 1)}
_RX_FECHA = re.compile(r"(\d{1,2})\s+de\s+([a-zA-Záéíóú]+)\s+de\s+(\d{4})")
_RX_LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
_RX_DURACION = re.compile(r"<td[^>]*>\s*Duraci(?:ó|&oacute;)n\s*</td>\s*<td[^>]*>(.*?)</td>", re.S | re.I)


def url_busqueda(termino: str) -> str:
    return "%s/encuentra-un-empleo/?2=%s&filterSearch=Buscar" % (BASE, quote_plus(termino))


def _limpio(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _fecha(texto: str) -> str:
    m = _RX_FECHA.search(texto or "")
    if not m:
        return ""
    mes = MESES.get(normalizar(m.group(2)))
    try:
        return datetime(int(m.group(3)), mes, int(m.group(1))).date().isoformat() if mes else ""
    except ValueError:
        return ""


def parsear_listado(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html or "", "html.parser")
    tarjetas = soup.select("div.job-item")
    titulo_pag = soup.title.get_text() if soup.title else ""
    if not tarjetas and "trabajos" not in titulo_pag.lower():
        raise ErrorFuente("la página de Chiletrabajos no tiene tarjetas de ofertas (¿cambió el sitio?)")
    filas, vistos = [], set()
    for c in tarjetas:
        a = c.select_one("h2.title a[href]")
        if not a or "/trabajo/" not in a["href"]:
            continue
        url = a["href"].split("#")[0]
        if url.startswith("/"):
            url = BASE + url
        if url in vistos:
            continue
        vistos.add(url)
        metas = c.select("h3.meta")
        empresa, ciudad = "", ""
        if metas:
            enlace = metas[0].find("a")
            ciudad = _limpio(enlace.get_text()) if enlace else ""
            texto = _limpio(metas[0].get_text(" "))
            empresa = _limpio(texto[: len(texto) - len(ciudad)] if ciudad and texto.endswith(ciudad) else texto).rstrip(",").strip()
        fecha = next((f for f in (_fecha(m.get_text(" ")) for m in metas[1:]) if f), "")
        desc = c.select_one("p.description")
        if desc:
            for x in desc.select("a.ver-mas-btn"):
                x.decompose()
        filas.append({
            "job_url": url, "title": _limpio(a.get_text()), "company": empresa,
            "location": ubicacion_indeed(ciudad), "description": _limpio(desc.get_text(" ")) if desc else "",
            "date_posted": fecha, "is_remote": False,
            "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    return parsear_listado(pedir(url_busqueda(termino), cliente, robots))


def _duracion(html: str) -> str:
    m = _RX_DURACION.search(html or "")
    return _limpio(html_mod.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))) if m else ""


def parsear_detalle(html: str) -> Dict:
    for m in _RX_LD.finditer(html or ""):
        try:
            ld = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(ld, dict) and ld.get("@type") == "JobPosting":
            texto = html_mod.unescape(str(ld.get("description") or ""))
            texto = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "\n", texto)
            texto = BeautifulSoup(texto, "html.parser").get_text() if "<" in texto else texto
            texto = "\n".join(_limpio(l) for l in texto.replace("\r", "\n").splitlines() if l.strip())
            vence = None
            try:
                vence = datetime.fromisoformat(str(ld.get("validThrough") or "")[:19])
            except ValueError:
                pass
            return {"descripcion": texto, "vence": vence, "lugar": str(ld.get("jobLocationType") or ""),
                    "duracion": _duracion(html)}
    raise ErrorFuente("el detalle de Chiletrabajos no trae el JSON-LD JobPosting (¿cambió el sitio?)")


def detalle(url: str, cliente, robots) -> Dict:
    return parsear_detalle(pedir(url, cliente, robots))


def completar(fila: dict, det: Dict, ahora: Optional[datetime] = None) -> bool:
    """Devuelve False si el aviso ya venció."""
    ahora = ahora or datetime.now()
    if det["vence"] and det["vence"].date() < ahora.date():
        return False
    desc = det["descripcion"] or fila.get("description", "")
    dur = det.get("duracion") or ""
    if dur:
        if re.search(r"plazo fijo", normalizar(dur)) and re.search(r"indefinid", normalizar(dur)):
            dur = "contrato inicial y luego indefinido"   # no es plazo fijo a secas (aviso de la app anterior)
        desc += "\n\nTipo de contrato (Chiletrabajos), duración: %s." % dur
    fila["description"] = desc
    if det["lugar"].upper() == "TELECOMMUTE":
        fila["is_remote"] = True
    return True
