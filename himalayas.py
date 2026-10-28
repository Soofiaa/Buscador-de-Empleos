"""Himalayas: API pública (sin autenticación) de empleos remotos.

Referencia: https://himalayas.app/jobs/api (verificada el 2026-10-22 con datos reales).
Su robots.txt no bloquea /jobs/api. La API no busca por texto: trae el listado más reciente y el clasificador
filtra por rol, igual que con el resto de las fuentes.
Atribución: cada oferta lleva el enlace a Himalayas (guid) y la postulación va a la oferta original.
"""
import re
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://himalayas.app/jobs/api"
HEADERS = {"User-Agent": "BuscaEmpleo/0.1 (busqueda personal de empleo)", "Accept": "application/json"}
MAX_POR_PEDIDO = 20   # tope que documenta la API
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]


def _limpiar_html(t) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    return re.sub(r"\s+", " ", t).strip()


def _instante(v) -> str:
    """pubDate es un timestamp en segundos (UTC); "" si no se puede leer."""
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def a_fila(a: dict):
    """Convierte un aviso de la API al formato del programa. Devuelve None si el aviso no es para Chile
    ni remoto sin restricción geográfica (locationRestrictions vacío)."""
    restricciones = [str(r) for r in (a.get("locationRestrictions") or []) if str(r).strip()]
    en_chile = any("chile" in r.lower() for r in restricciones)
    if restricciones and not en_chile:
        return None
    ubicacion = "Chile" if en_chile else "Remoto (global)"

    # Nivel y modalidad se escriben en la descripción para que el clasificador los vea (igual que Get on Board)
    niveles = [str(s) for s in (a.get("seniority") or []) if str(s).strip()]
    prefijo = [f"Nivel {', '.join(niveles)}."] if niveles else []
    prefijo.append("Modalidad 100% remota.")
    cuerpo = _limpiar_html(a.get("description")) or _limpiar_html(a.get("excerpt"))

    sueldo = a.get("currency") and (a.get("minSalary") or a.get("maxSalary"))
    periodo = str(a.get("salaryPeriod") or "").lower()
    periodo = "yearly" if periodo in ("annual", "yearly") else periodo   # mismo valor que Jobicy
    return {
        "job_url": a.get("guid") or a.get("applicationLink") or "",
        "title": a.get("title") or "",
        "company": a.get("companyName") or "",
        "location": ubicacion,
        "description": " ".join(prefijo + [cuerpo]).strip(),
        "date_posted": _instante(a.get("pubDate"))[:10],
        "is_remote": True,   # toda la fuente es de empleos remotos
        "min_amount": a.get("minSalary") if sueldo else None,
        "max_amount": a.get("maxSalary") if sueldo else None,
        "currency": a.get("currency") if sueldo else "",
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
    """Trae el listado reciente de Himalayas, o con 'termino' su búsqueda por texto (/search, solo remotos sin
    restricción de país; la usa «Explorar remotos»). Lanza excepción si la API falla. al_responder: telemetría pasiva,
    recibe el status de la solicitud."""
    params = {"limit": min(resultados, MAX_POR_PEDIDO)}
    if termino:
        params.update(q=termino, worldwide="true")
    try:
        r = requests.get(BASE + ("/search" if termino else ""), headers=HEADERS, timeout=20, params=params)
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    r.raise_for_status()
    datos = r.json().get("jobs") or []
    filas = [f for f in (a_fila(a) for a in datos) if f and f["job_url"] and f["title"]]
    return pd.DataFrame(filas, columns=COLUMNAS)
