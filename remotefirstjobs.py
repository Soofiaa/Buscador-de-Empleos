"""Remote First Jobs: API pública (sin autenticación) de empleos remotos.

Referencia: https://remotefirstjobs.com/jobs-api (verificada el 2026-10-24 con una página real de 100 ofertas).
La API no busca por texto en esta integración: trae el listado más reciente y el clasificador filtra por rol,
igual que con Himalayas y Jobicy. Las ofertas aparecen 24 h después de publicarse.
Atribución (pedida por el sitio): la oferta lleva enlace a Remote First Jobs y se menciona como fuente. No se
republican las ofertas en LinkedIn, Google Jobs ni Jooble.
"""
import re
from datetime import datetime

import pandas as pd
import requests

BASE = "https://remotefirstjobs.com/api/search-jobs"
HEADERS = {"User-Agent": "BuscaEmpleo/0.1 (busqueda personal de empleo)", "Accept": "application/json"}
MAX_PAGINAS = 1   # una página (100 ofertas) por corrida: la base ya se revisa a diario y basta para lo reciente
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]
NIVELES = {"entry_level": "junior", "intern": "práctica", "middle": "semi senior", "senior": "senior",
           "staff": "senior", "principal": "senior", "manager": "gerencia", "director": "dirección",
           "executive": "dirección"}


def _limpiar_html(t) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    return re.sub(r"\s+", " ", t).strip()


def _instante(v) -> str:
    """published_at viene como ISO con zona; "" si no se puede leer."""
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).isoformat()
    except (TypeError, ValueError):
        return ""


def a_fila(a: dict):
    """Convierte un aviso de la API al formato del programa. Devuelve None si el aviso es solo para un país
    que no es Chile (locations sin Chile y con países concretos). Sin países = remoto global."""
    paises = [str(p).strip() for p in (a.get("locations") or []) if str(p).strip()]
    en_chile = any("chile" in p.lower() for p in paises)
    if paises and not en_chile:
        return None
    ubicacion = "Chile" if en_chile else "Remoto (global)"

    # Nivel y modalidad se escriben en la descripción para que el clasificador los vea (igual que Himalayas y Jobicy)
    nivel = NIVELES.get(str(a.get("seniority") or "").strip(), "")
    prefijo = [f"Nivel {nivel}."] if nivel else []
    prefijo.append("Modalidad 100% remota.")
    cuerpo = _limpiar_html(a.get("description"))

    minimo, maximo = a.get("salary_min"), a.get("salary_max")
    sueldo = bool(minimo or maximo)
    return {
        "job_url": a.get("url") or "",
        "title": a.get("title") or "",
        "company": a.get("company_name") or "",
        "location": ubicacion,
        "description": " ".join(prefijo + [cuerpo]).strip(),
        "date_posted": _instante(a.get("published_at"))[:10],
        "is_remote": True,   # toda la fuente es de empleos remotos
        "min_amount": minimo if sueldo else None,
        "max_amount": maximo if sueldo else None,
        "currency": "USD" if sueldo else "",   # la API no indica moneda; sus sueldos vienen en USD
        "interval": "yearly" if sueldo else "",
        "posted_at": _instante(a.get("published_at")),
    }


def _avisar(al_responder, status):
    if al_responder:
        try:
            al_responder(status)
        except Exception:
            pass


def buscar(termino: str = "", resultados: int = 100, al_responder=None) -> pd.DataFrame:
    """Trae el listado reciente de Remote First Jobs. 'termino' se ignora (esta integración no busca por texto).
    Lanza excepción si la API falla. al_responder: telemetría pasiva, recibe el status de la solicitud."""
    try:
        r = requests.get(BASE, headers=HEADERS, timeout=20, params={"page": 0})
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    r.raise_for_status()
    datos = r.json().get("jobs") or []
    filas = [f for f in (a_fila(a) for a in datos) if f and f["job_url"] and f["title"]]
    return pd.DataFrame(filas, columns=COLUMNAS)
