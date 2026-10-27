"""We Work Remotely: feed RSS público de empleos remotos.

Referencia: https://weworkremotely.com/remote-jobs.rss (verificado el 2026-10-26: 200, RSS 2.0, 96 items). Su robots.txt
permite el feed. Cada item trae campos estructurados: title ("Empresa: Cargo"), link, region, country, pubDate,
category, skills y la descripción en media:content. Se aceptan solo ofertas sin restricción geográfica o de América
(incluida Chile); las de "Europe Only" / "USA Only" se descartan, que es la mayoría del feed. Atribución: el enlace
lleva a We Work Remotely.
"""
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import pandas as pd
import requests

BASE = "https://weworkremotely.com/remote-jobs.rss"
UA = "BuscaEmpleo/0.1 (busqueda personal de empleo)"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]
GLOBALES = ("anywhere in the world", "worldwide", "global", "remote")
AMERICAS = ("americas", "latin america", "latam", "south america", "north america")
CONTENIDO = "{http://search.yahoo.com/mrss}content"


def _limpiar_html(t) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()


def _instante(v) -> str:
    """pubDate es RFC 822 ("Tue, 27 Oct 2026 01:00:00 +0000"); "" si no se puede leer."""
    try:
        return parsedate_to_datetime(str(v)).isoformat()
    except (TypeError, ValueError):
        return ""


def acepta(region: str, country: str) -> bool:
    """Sin restricción (ni region ni country) o de América/Chile. El resto se descarta."""
    r, c = (region or "").strip().lower(), (country or "").strip().lower()
    if "chile" in c:
        return True
    if not r and not c:
        return True
    if any(g in r for g in GLOBALES):
        return True
    return any(a in r for a in AMERICAS)


def a_fila(item):
    """Convierte un <item> del RSS al formato del programa; None si no sirve o está restringido."""
    link = (item.findtext("link") or "").strip()
    crudo = (item.findtext("title") or "").strip()
    region = (item.findtext("region") or "").strip()
    country = (item.findtext("country") or "").strip()
    if not link.startswith("http") or not crudo or not acepta(region, country):
        return None
    empresa, _, cargo = crudo.partition(": ")
    titulo = (cargo or crudo).strip()
    publicado = _instante(item.findtext("pubDate"))
    contenido = item.find(CONTENIDO)
    if contenido is not None:
        # el HTML va en hijos (<p>, <strong>...): se toma todo el texto, no solo el directo del elemento
        bruto = ET.tostring(contenido, encoding="unicode", method="text") or ""
        if not bruto.strip():
            bruto = "".join(contenido.itertext())
        descripcion = _limpiar_html(bruto)
    else:
        descripcion = _limpiar_html(item.findtext("description"))
    etiquetas = [e.text.strip() for e in item.findall("category") if (e.text or "").strip()]
    if etiquetas:
        descripcion = "Etiquetas: " + ", ".join(etiquetas) + ". " + descripcion
    return {
        "job_url": link,
        "title": titulo,
        "company": empresa.strip(),
        "location": "Chile" if "chile" in country.lower() else "Remoto (global)",
        "description": descripcion,
        "date_posted": publicado[:10],
        "is_remote": True,
        "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        "posted_at": publicado,
    }


def _avisar(al_responder, status):
    if al_responder:
        try:
            al_responder(status)
        except Exception:
            pass


def buscar(termino: str = "", resultados: int = 100, al_responder=None) -> pd.DataFrame:
    """Trae el feed completo y deja las ofertas sin restricción geográfica o de América. 'termino' se ignora.
    Lanza excepción si el feed falla. al_responder: telemetría pasiva, recibe el status de la solicitud."""
    try:
        r = requests.get(BASE, headers={"User-Agent": UA}, timeout=25)
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    r.raise_for_status()
    root = ET.fromstring(r.content)
    canal = root.find("channel")
    filas = [f for f in (a_fila(it) for it in (canal.findall("item") if canal is not None else [])) if f]
    return pd.DataFrame(filas[:resultados], columns=COLUMNAS)
