"""Jooble: buscador de empleo con API pública (clave gratuita para uso no comercial).

Referencia: https://jooble.org/api/about — POST https://jooble.org/api/{clave} con {"keywords", "location", "page"}.
Su robots.txt prohíbe /employer/api, no el endpoint de búsqueda. Verificado el 2026-10-26 con la clave real: location
"Chile" devuelve 0 avisos, pero "Santiago" responde con normalidad (226 para "analista QA"), así que se consulta por
ciudad (UBICACIONES). Devuelve un resumen (snippet) y un enlace a la ficha de Jooble, que a su vez lleva al aviso
original; como no trae la descripción completa, sus ofertas van a «Sin texto» (FUENTES_SIN_TEXTO), igual que LinkedIn.
Sin JOOBLE_KEY la fuente no se consulta y el resto de la app funciona igual.
"""
import os
import time

import pandas as pd
import requests

BASE = "https://jooble.org/api/"
UA = "BuscaEmpleo/0.1 (busqueda personal de empleo)"
PAUSA_ENTRE_TERMINOS = 2.0        # la cuota gratuita es limitada: se pide poco y espaciado
TERMINOS = ["analista QA", "tester", "analista funcional", "analista de datos junior",
            "desarrollador python", "soporte TI"]
UBICACIONES = ["Santiago, Chile", "Viña del Mar, Chile"]   # por país ("Chile") la API devuelve 0
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted",
            "is_remote", "min_amount", "max_amount", "currency", "interval", "posted_at"]


def clave() -> str:
    return (os.environ.get("JOOBLE_KEY") or "").strip()


def disponible() -> bool:
    return bool(clave())


def a_fila(j: dict):
    """Convierte un aviso de Jooble al formato del programa; None si no sirve (sin título o sin enlace)."""
    url = str(j.get("link") or "").strip()
    titulo = str(j.get("title") or "").strip()
    if not titulo or not url.startswith("http"):
        return None
    actualizado = str(j.get("updated") or "").strip()
    ubicacion = str(j.get("location") or "").strip()
    return {
        "job_url": url,
        "title": titulo,
        "company": str(j.get("company") or "").strip(),
        "location": ubicacion,
        "description": "",          # Jooble solo entrega un resumen: la oferta queda en «Sin texto»
        "date_posted": actualizado[:10],
        "is_remote": "remoto" in ubicacion.lower() or "remote" in ubicacion.lower(),
        "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        "posted_at": actualizado,
    }


def _avisar(al_responder, status):
    if al_responder:
        try:
            al_responder(status)
        except Exception:
            pass


def _pagina(termino: str, lugar: str, al_responder=None) -> list:
    """Una página de resultados de un término en una ciudad. Lanza si la API falla o no devuelve JSON."""
    try:
        r = requests.post(BASE + clave(), json={"keywords": termino, "location": lugar, "page": "1"},
                          headers={"User-Agent": UA}, timeout=25)
    except requests.RequestException:
        _avisar(al_responder, 0)
        raise
    _avisar(al_responder, getattr(r, "status_code", 0))
    r.raise_for_status()
    return (r.json() or {}).get("jobs") or []


def buscar(termino: str = "", resultados: int = 100, al_responder=None) -> pd.DataFrame:
    """Consulta Jooble por cada término y cada ciudad de UBICACIONES. Un fallo no tumba la fuente; si fallan todos,
    se lanza el último error para que la corrida lo cuente. Un 429 corta de inmediato: no se insiste contra la cuota."""
    if not disponible():
        return pd.DataFrame(columns=COLUMNAS)
    terminos = [termino] if termino else TERMINOS
    filas, vistos, ultimo, primera = [], set(), None, True
    for t in terminos:
        for lugar in UBICACIONES:
            if not primera:
                time.sleep(PAUSA_ENTRE_TERMINOS)
            primera = False
            try:
                avisos = _pagina(t, lugar, al_responder)
            except requests.HTTPError as e:
                ultimo = e
                if getattr(getattr(e, "response", None), "status_code", None) == 429:
                    raise
                continue
            except requests.RequestException as e:
                ultimo = e
                continue
            for j in avisos:
                f = a_fila(j)
                if f and f["job_url"] not in vistos:
                    vistos.add(f["job_url"])
                    filas.append(f)
            if len(filas) >= resultados:
                break
        if len(filas) >= resultados:
            break
    if ultimo is not None and not filas:
        raise ultimo
    return pd.DataFrame(filas[:resultados], columns=COLUMNAS)
