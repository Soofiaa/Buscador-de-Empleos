"""Chumi (chumi-it.com): portal de empleo IT chileno, scraping de HTML estático.

Estructura basada en patrones típicos de portales de empleo. Requiere verificación
de la estructura actual del sitio (2026-10-19).
"""
import html as html_mod
import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote_plus

import pandas as pd
from bs4 import BeautifulSoup

from filtros import normalizar
from geo import ubicacion_indeed
from red import ErrorFuente, pedir

BASE = "https://chumi-it.com"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval"]
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                     "septiembre", "octubre", "noviembre", "diciembre"], 1)}
_RX_FECHA = re.compile(r"(\d{1,2})\s+de\s+([a-zA-Záéíóú]+)\s+de\s+(\d{4})")


def url_busqueda(termino: str) -> str:
    return "%s/jobs?q=%s" % (BASE, quote_plus(termino))


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


def _modalidad(texto: str) -> str:
    t = normalizar(texto or "")
    if "remoto" in t or "teletrabajo" in t:
        return "remoto"
    if "hibrido" in t or "mixto" in t or "presencial y remoto" in t:
        return "hibrido"
    return ""


def parsear_listado(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html or "", "html.parser")
    filas, vistos = [], set()
    
    # Selectores típicos de Chumi (requieren verificación)
    tarjetas = soup.select("div.job-card") or soup.select("div.offer") or soup.select("div.card")
    
    if not tarjetas:
        raise ErrorFuente("la página de Chumi no tiene tarjetas de ofertas (¿cambió el sitio?)")
    
    for tarjeta in tarjetas:
        a = tarjeta.select_one("a[href]") or tarjeta.select_one("h2 a") or tarjeta.select_one("h3 a")
        if not a:
            continue
        url = a.get("href", "").split("#")[0]
        if url.startswith("/"):
            url = BASE + url
        if url in vistos:
            continue
        vistos.add(url)
        
        titulo = _limpio(a.get_text())
        empresa = _limpio(tarjeta.select_one("p.company") or tarjeta.select_one("span.company") or "").get_text() if tarjeta.select_one("p.company") or tarjeta.select_one("span.company") else ""
        ubicacion = _limpio(tarjeta.select_one("p.location") or tarjeta.select_one("span.location") or "").get_text() if tarjeta.select_one("p.location") or tarjeta.select_one("span.location") else ""
        fecha_elem = tarjeta.select_one("span.date") or tarjeta.select_one("p.date")
        fecha = _fecha(fecha_elem.get_text()) if fecha_elem else ""
        desc_elem = tarjeta.select_one("p.description") or tarjeta.select_one("div.description")
        descripcion = _limpio(desc_elem.get_text()) if desc_elem else ""
        
        modalidad = _modalidad(descripcion + " " + ubicacion)
        
        filas.append({
            "job_url": url,
            "title": titulo,
            "company": empresa,
            "location": ubicacion_indeed(ubicacion),
            "description": descripcion,
            "date_posted": fecha,
            "is_remote": modalidad == "remoto",
            "min_amount": None,
            "max_amount": None,
            "currency": "",
            "interval": "",
        })
    
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    return parsear_listado(pedir(url_busqueda(termino), cliente, robots))


def parsear_detalle(html: str) -> Dict:
    soup = BeautifulSoup(html or "", "html.parser")
    
    # Intentar extraer descripción completa
    desc_elem = soup.select_one("div.description") or soup.select_one("p.description") or soup.select_one("div.job-description")
    descripcion = _limpio(desc_elem.get_text()) if desc_elem else ""
    
    # Intentar extraer requisitos
    req_elem = soup.select_one("div.requirements") or soup.select_one("ul.requirements")
    requisitos = _limpio(req_elem.get_text()) if req_elem else ""
    
    # Intentar extraer modalidad
    modalidad_elem = soup.select_one("span.modality") or soup.select_one("p.modality")
    modalidad = _modalidad(modalidad_elem.get_text()) if modalidad_elem else ""
    
    # Intentar extraer salario
    salario_elem = soup.select_one("span.salary") or soup.select_one("p.salary")
    salario = _limpio(salario_elem.get_text()) if salario_elem else ""
    
    return {
        "descripcion": descripcion,
        "requisitos": requisitos,
        "modalidad": modalidad,
        "salario": salario,
    }


def detalle(url: str, cliente, robots) -> Dict:
    return parsear_detalle(pedir(url, cliente, robots))


def completar(fila: dict, det: Dict) -> bool:
    """Agrega información del detalle a la fila."""
    desc = fila.get("description", "")
    
    if len(det.get("descripcion") or "") > len(desc):
        desc = det["descripcion"]
    
    if det.get("requisitos"):
        req = det["requisitos"]
        desc += "\n\nRequisitos:\n" + req if not normalizar(req[:12]).startswith("requisitos") else req
    
    if det.get("modalidad"):
        mod = det["modalidad"]
        if mod == "remoto":
            fila["is_remote"] = True
        if mod and mod not in normalizar(desc):
            prefijo = "Modalidad 100% remota. " if mod == "remoto" else "Modalidad híbrida. "
            desc = prefijo + desc
    
    if det.get("salario"):
        desc += "\n\nSalario: " + det["salario"]
    
    fila["description"] = desc
    return True
