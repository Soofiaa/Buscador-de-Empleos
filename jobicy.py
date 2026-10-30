"""Jobicy: API pública (sin autenticación) de empleos remotos.

Referencia: https://jobicy.com/api/v2/remote-jobs (verificada el 2026-10-22 con datos reales; documentación en
https://jobi.cy/apidocs). Su robots.txt no bloquea la API. La API no busca por texto: trae el listado más reciente y
el clasificador filtra por rol, igual que con el resto de las fuentes.
Atribución (pedida por Jobicy): la oferta lleva enlace a Jobicy y la postulación va a la oferta original (url).
"""
import re
from datetime import datetime

import pandas as pd
import requests

BASE = "https://jobicy.com/api/v2/remote-jobs"
HEADERS = {"User-Agent": "BuscaEmpleo/0.1 (busqueda personal de empleo)", "Accept": "application/json"}
MAX_POR_PEDIDO = 50   # tope que documenta la API (parámetro count)
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]
GLOBAL = ("anywhere", "worldwide", "global")


def _limpiar_html(t) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    return re.sub(r"\s+", " ", t).strip()


def _instante(v) -> str:
    """pubDate viene como ISO con zona ('2026-10-22T18:57:18+00:00'); "" si no se puede leer."""
    try:
        return datetime.fromisoformat(str(v)).isoformat()
    except (TypeError, ValueError):
        return ""


def a_fila(a: dict):
    """Convierte un aviso de la API al formato del programa. Devuelve None si el aviso no es para Chile
    ni para cualquier lugar (jobGeo vacío o con 'anywhere' / 'worldwide')."""
    paises = [p.strip() for p in str(a.get("jobGeo") or "").split(",") if p.strip()]
    en_chile = any("chile" in p.lower() for p in paises)
    es_global = not paises or any(g in p.lower() for p in paises for g in GLOBAL)
    if not en_chile and not es_global:
        return None
    ubicacion = "Chile" if en_chile else "Remoto (global)"

    # Nivel y modalidad se escriben en la descripción para que el clasificador los vea (igual que Get on Board)
    nivel = str(a.get("jobLevel") or "").strip()
    prefijo = [f"Nivel {nivel}."] if nivel and nivel.lower() != "any" else []
    prefijo.append("Modalidad 100% remota.")
    cuerpo = _limpiar_html(a.get("jobDescription")) or _limpiar_html(a.get("jobExcerpt"))

    sueldo = a.get("salaryCurrency") and (a.get("salaryMin") or a.get("salaryMax"))
    periodo = str(a.get("salaryPeriod") or "").lower()
    return {
        "job_url": a.get("url") or "",
        "title": a.get("jobTitle") or "",
        "company": a.get("companyName") or "",
        "location": ubicacion,
        "description": " ".join(prefijo + [cuerpo]).strip(),
        "date_posted": _instante(a.get("pubDate"))[:10],
        "is_remote": True,   # toda la fuente es de empleos remotos
        "min_amount": a.get("salaryMin") if sueldo else None,
        "max_amount": a.get("salaryMax") if sueldo else None,
        "currency": a.get("salaryCurrency") if sueldo else "",
        "interval": periodo if sueldo else "",
        "posted_at": _instante(a.get("pubDate")),
    }


def _avisar(al_responder, status):
    if al_responder:
        try:
            al_responder(status)
        except Exception:
            pass


def buscar(termino: str = "", resultados: int = MAX_POR_PEDIDO, al_responder=None) -> pd.DataFrame:
    """Trae el listado reciente de Jobicy, o con 'termino' su búsqueda por palabra clave (tag=; la usa «Explorar
    remotos»). Lanza excepción si la API falla. al_responder: telemetría pasiva, recibe el status de la solicitud."""
    params = {"count": min(resultados, MAX_POR_PEDIDO)}
    if termino:
        params["tag"] = termino
    try:
        r = requests.get(BASE, headers=HEADERS, timeout=20, params=params)
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    r.raise_for_status()
    datos = r.json().get("jobs") or []
    filas = [f for f in (a_fila(a) for a in datos) if f and f["job_url"] and f["title"]]
    return pd.DataFrame(filas, columns=COLUMNAS)
