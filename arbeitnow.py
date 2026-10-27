"""Arbeitnow: API pública (sin autenticación) del tablero de empleo europeo.

Referencia: https://www.arbeitnow.com/api/job-board-api (verificada el 2026-10-27: 200, 300 avisos por página). Su
robots.txt solo bloquea "?__hstc". Piden enlazar de vuelta: cada oferta apunta a su ficha en Arbeitnow.
Casi todo el tablero es presencial en Alemania/Países Bajos/Suiza, y su campo "remote" no dice desde qué países se
puede postular. Por eso el filtro es estricto: solo avisos con remote=true y SIN ciudad (location "Remote", "Remote job"
o vacía); los que traen ciudad (Berlin, Zürich...) son presenciales o híbridos y se descartan. Aun así un "Remote" puede
exigir residir en la UE: se descartan los que lo dicen en la descripción. Aportará pocas ofertas; es una fuente de prueba.
"""
import html
import re
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://www.arbeitnow.com/api/job-board-api"
HEADERS = {"User-Agent": "BuscaEmpleo/0.1 (busqueda personal de empleo)", "Accept": "application/json"}
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]
SIN_CIUDAD = ("", "remote", "remote job", "remote work", "worldwide", "anywhere")
# "debes vivir/tener permiso en la UE, Alemania, UK..." en la descripción: no sirve desde Chile
RESTRINGIDO = re.compile(
    r"(must|need to|have to)\s+(be\s+)?(based|located|living|resident)\s+in\s+(the\s+)?(eu|europe|germany|uk|netherlands|dach)"
    r"|(work\s+permit|right\s+to\s+work|authori[sz]ation\s+to\s+work)\s+(for|in)\s+(the\s+)?(eu|europe|germany|uk|netherlands)"
    r"|\b(eu|europe|european|emea|dach)\s*[- ]?\s*(only|residents?|based)\b"
    r"|\bwithin\s+(the\s+)?(eu|europe|european union|germany|cet)\b",
    re.I)


def _limpiar_html(t) -> str:
    t = html.unescape(str(t or ""))
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace("\u202f", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def _instante(v) -> str:
    """created_at es un timestamp en segundos (UTC), a veces como texto; "" si no se puede leer."""
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def acepta(a: dict, texto: str) -> bool:
    if not a.get("remote"):
        return False
    if str(a.get("location") or "").strip().lower() not in SIN_CIUDAD:
        return False
    return not RESTRINGIDO.search(texto)


def a_fila(a: dict):
    """Convierte un aviso de la API al formato del programa; None si no es remoto sin ciudad o exige residir en Europa."""
    url = str(a.get("url") or "").strip()
    titulo = str(a.get("title") or "").strip()
    if not url.startswith("http") or not titulo:
        return None
    cuerpo = _limpiar_html(a.get("description"))
    if not acepta(a, f"{titulo} {cuerpo}"):
        return None
    etiquetas = [str(t).strip() for t in (a.get("tags") or []) if str(t).strip() and str(t).strip().lower() != "remote"]
    prefijo = ["Modalidad 100% remota."]
    if etiquetas:
        prefijo.append("Etiquetas: " + ", ".join(etiquetas) + ".")
    publicado = _instante(a.get("created_at"))
    return {
        "job_url": url,
        "title": titulo,
        "company": str(a.get("company_name") or "").strip(),
        "location": "Remoto (global)",
        "description": " ".join(prefijo + [cuerpo]).strip(),
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
    """Trae la primera página del tablero (300 avisos) y deja solo los remotos sin ciudad. 'termino' se ignora.
    Lanza excepción si la API falla. al_responder: telemetría pasiva, recibe el status de la solicitud."""
    try:
        r = requests.get(BASE, headers=HEADERS, timeout=25)
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    r.raise_for_status()
    datos = r.json().get("data") or []
    filas = [f for f in (a_fila(a) for a in datos) if f]
    return pd.DataFrame(filas[:resultados], columns=COLUMNAS)
