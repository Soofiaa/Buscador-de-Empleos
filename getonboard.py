"""Get on Board: API pública oficial (sin autenticación) para ofertas tech de Latinoamérica.

Formato verificado con datos reales (probar_getonboard.py, 2026-10-10): la empresa viene
anidada con expand, y 'seniority' solo trae un id salvo que se pida expandido.
Referencia: https://www.getonbrd.com/api-doc.html
"""
import re
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://www.getonbrd.com/api/v0"
HEADERS = {"User-Agent": "Mozilla/5.0 (busqueda-empleo-personal)", "Accept": "application/json"}
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]


def _limpiar_html(t) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    return re.sub(r"\s+", " ", t).strip()


def _valor(d, *ruta):
    """Navega un diccionario anidado; devuelve None si algo falta."""
    for k in ruta:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _nombre(x) -> str:
    """Un campo puede venir como texto, como {'name': ..} o como {'data': {'attributes': {'name': ..}}}."""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        for ruta in (("name",), ("attributes", "name"), ("data", "attributes", "name"),
                     ("data", "name"), ("data", "id"), ("id",)):
            v = _valor(x, *ruta)
            if isinstance(v, str) and v:
                return v
    return ""


def _fecha(v) -> str:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return str(v)[:10] if v else ""


def _instante(v) -> str:
    """published_at con hora (UTC, ISO), para el corte exacto de antigüedad; "" si no es un timestamp."""
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def a_fila(item: dict):
    """Convierte una oferta de la API al formato que usa el resto del programa.
    Devuelve None si no es para Chile ni remota global."""
    a = item.get("attributes") or item
    paises = a.get("countries") or []
    paises = [_nombre(p).lower() for p in (paises if isinstance(paises, list) else [paises])]
    modalidad = str(a.get("remote_modality") or "").lower()
    es_remoto = bool(a.get("remote")) or ("remote" in modalidad and "no_remote" not in modalidad)
    global_ = "global" in modalidad or "worldwide" in modalidad
    en_chile = any(p in ("chile", "cl") for p in paises)

    # Se aceptan ofertas de Chile o remotas sin restricción geográfica
    if not en_chile and not global_:
        return None
    ubicacion = "Chile" if en_chile else "Remoto (global)"
    if a.get("remote_zone"):
        ubicacion += f" - {a['remote_zone']}"

    # Nivel y modalidad se escriben en la descripción para que el clasificador los vea
    nivel = _nombre(a.get("seniority"))
    prefijo = []
    if nivel:
        prefijo.append(f"Nivel {nivel}.")
    if "hybrid" in modalidad:
        prefijo.append("Modalidad híbrida.")
    elif es_remoto:
        prefijo.append("Modalidad 100% remota.")
    elif modalidad in ("no_remote", "onsite", "in_person"):
        prefijo.append("Modalidad presencial.")
    cuerpo = " ".join(_limpiar_html(a.get(c)) for c in
                      ("description_headline", "description", "functions", "desirable"))

    return {
        "job_url": _valor(item, "links", "public_url") or a.get("public_url") or a.get("url") or "",
        "title": a.get("title") or "",
        "company": _nombre(a.get("company")) or _nombre(_valor(item, "relationships", "company")),
        "location": ubicacion,
        "description": " ".join(prefijo + [cuerpo]).strip(),
        "date_posted": _fecha(a.get("published_at")), "posted_at": _instante(a.get("published_at")),
        "is_remote": es_remoto,
        "min_amount": a.get("min_salary"), "max_amount": a.get("max_salary"),
        "currency": "USD" if (a.get("min_salary") or a.get("max_salary")) else "",
        "interval": "monthly" if (a.get("min_salary") or a.get("max_salary")) else "",
    }


def _pedir(termino, resultados, expand):
    return requests.get(f"{BASE}/search/jobs", headers=HEADERS, timeout=20,
                        params={"query": termino, "per_page": min(resultados, 100), "page": 1,
                                "expand[]": expand})


def _pedir_observado(termino, resultados, expand, al_responder):
    """_pedir y, después, el status a la telemetría pasiva (0 si no hubo respuesta). No cambia nada más."""
    try:
        r = _pedir(termino, resultados, expand)
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    return r


def _avisar(al_responder, status):
    if al_responder:
        try:
            al_responder(status)
        except Exception:
            pass


def buscar(termino: str, resultados: int = 30, al_responder=None) -> pd.DataFrame:
    """Busca ofertas publicadas que coincidan con el texto. Lanza excepción si la API falla.
    Pide también el nivel (seniority) expandido, porque por defecto solo trae un id numérico;
    si la API rechazara esa expansión, reintenta solo con la empresa.
    al_responder: telemetría pasiva, recibe el status de cada solicitud."""
    r = _pedir_observado(termino, resultados, ["company", "seniority"], al_responder)
    if r.status_code in (400, 422):
        r = _pedir_observado(termino, resultados, ["company"], al_responder)
    r.raise_for_status()
    datos = r.json().get("data") or []
    filas = [f for f in (a_fila(i) for i in datos) if f and f["job_url"] and f["title"]]
    return pd.DataFrame(filas, columns=COLUMNAS)
