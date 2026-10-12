"""Trabajando.cl: páginas Nuxt con los datos dentro del HTML (<script id="__NUXT_DATA__">), sin sesión ni navegador.

Verificado por la app anterior (2026-10-05; fixtures tests/fixtures/trabajando_*.html):
  - Listado: GET /trabajo-<término-con-guiones>. Solo existe si el sitio tiene esa "landing"; si no, HTTP 404.
    15 ofertas por página, ordenadas por RELEVANCIA (no por fecha), con descripción RECORTADA.
  - Detalle: GET /trabajo/<id>-<slug>: descripción completa, requisitos, años de experiencia, estado y vencimiento.
  - fechaPublicacion del listado: "AAAA-MM-DD HH:MM" sin zona horaria. Las 15 horas de la fixture (09:57 a 15:57) calzan
    con horario de oficina en Chile, así que se supone hora de Chile (sin confirmar; el corte usa un margen de 4 h).
  - __NUXT_DATA__ usa el formato "devalue": un arreglo JSON donde objetos y listas apuntan a sus valores por índice.
Sin verificar: la página 2 (solo se lee la 1) y el valor "Teletrabajo" a secas en nombreJornada.
"""
import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup

from filtros import normalizar
from geo import ubicacion_indeed
from red import ErrorFuente, pedir

BASE = "https://www.trabajando.cl"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval", "posted_at"]
_RX_NUXT = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)
_ENVOLTURAS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}


def url_busqueda(termino: str) -> str:
    return "%s/trabajo-%s" % (BASE, termino)


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")


def url_oferta(id_oferta, titulo: str = "") -> str:
    return "%s/trabajo/%s%s" % (BASE, id_oferta, ("-" + _slug(titulo)) if titulo else "")


def datos_nuxt(html: str) -> List:
    m = _RX_NUXT.search(html or "")
    if not m:
        raise ErrorFuente("la página de Trabajando no trae __NUXT_DATA__ (¿cambió el sitio?)")
    try:
        arr = json.loads(m.group(1))
    except json.JSONDecodeError as ex:
        raise ErrorFuente("__NUXT_DATA__ no es JSON (%s)" % ex.msg)
    if not isinstance(arr, list):
        raise ErrorFuente("__NUXT_DATA__ no tiene el formato esperado")
    return arr


def _valor(arr: List, i, prof: int = 0):
    if not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= len(arr) or prof > 30:
        return None
    v = arr[i]
    if isinstance(v, dict):
        return {k: _valor(arr, x, prof + 1) for k, x in v.items()}
    if isinstance(v, list):
        if v and isinstance(v[0], str) and v[0] in _ENVOLTURAS:
            return _valor(arr, v[1], prof + 1) if len(v) > 1 else None
        return [_valor(arr, x, prof + 1) for x in v]
    return v


def _objetos(arr: List, *claves: str) -> List[Dict]:
    return [{k: _valor(arr, x) for k, x in v.items()} for v in arr if isinstance(v, dict) and all(k in v for k in claves)]


def _texto(s) -> str:
    if not s:
        return ""
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>|<li[^>]*>", "\n", html_mod.unescape(str(s)))
    t = BeautifulSoup(s, "html.parser").get_text()
    return "\n".join(re.sub(r"[ \t ]+", " ", l).strip() for l in t.splitlines() if l.strip())


def _modalidad(jornada: str) -> str:
    """"Mixta (Teletrabajo + Presencial)" -> híbrido; "Teletrabajo" a secas -> remoto (decisión de Sofia)."""
    j = normalizar(jornada or "").strip()
    if "mixta" in j:
        return "hibrido"
    if j == "teletrabajo":
        return "remoto"
    return ""


def _prefijo_modalidad(m: str) -> str:
    return {"hibrido": "Modalidad híbrida. ", "remoto": "Modalidad 100% remota. "}.get(m, "")


def _fecha(s: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime((s or "").strip(), fmt)
        except ValueError:
            continue
    return None


def parsear_listado(html: str) -> pd.DataFrame:
    arr = datos_nuxt(html)
    filas, vistos = [], set()
    for o in _objetos(arr, "idOferta", "nombreCargo", "fechaPublicacion"):
        oid, titulo = o.get("idOferta"), html_mod.unescape(str(o.get("nombreCargo") or "")).strip()
        if not oid or not titulo or oid in vistos:
            continue
        vistos.add(oid)
        modalidad = _modalidad(str(o.get("nombreJornada") or ""))
        ubic = str(o.get("ubicacion") or "")
        comuna, _, region = (p.strip() for p in (ubic.partition(",")))
        f = _fecha(str(o.get("fechaPublicacion") or ""))
        filas.append({
            "job_url": url_oferta(oid, titulo), "title": re.sub(r"\s+", " ", titulo),
            "company": html_mod.unescape(str(o.get("nombreEmpresa") or "")).strip(),
            "location": ubicacion_indeed(comuna, region),
            "description": _prefijo_modalidad(modalidad) + _texto(o.get("descripcionOferta")),
            "date_posted": f.date().isoformat() if f else "", "is_remote": modalidad == "remoto",
            # con hora solo si el listado la trae; sin zona: se entiende hora de Chile (ver MARGEN_HORAS_SIN_ZONA)
            "posted_at": f.isoformat(timespec="minutes") if f and ":" in str(o.get("fechaPublicacion") or "") else "",
            "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    """Una página. Lanza NoEncontrada (404) si el sitio no tiene página para ese término."""
    return parsear_listado(pedir(url_busqueda(termino), cliente, robots))


def parsear_detalle(html: str) -> Dict:
    arr = datos_nuxt(html)
    obj = next(iter(_objetos(arr, "idOferta", "descripcionOferta", "estadoOferta", "requisitosMinimos")), None)
    if not obj:
        raise ErrorFuente("el detalle de Trabajando no trae la oferta (¿cambió el sitio?)")
    try:
        anios = int(obj.get("aniosExperiencia") or 0)
    except (TypeError, ValueError):
        anios = 0
    return {
        "descripcion": _texto(obj.get("descripcionOferta")), "requisitos": _texto(obj.get("requisitosMinimos")),
        "anios": anios, "operador": str(obj.get("nombreOperadorExperiencia") or ""),
        "estado": str(obj.get("estadoOferta") or ""),
        "expira": _fecha(str(obj.get("fechaExpiracionFormatoIngles") or obj.get("fechaExpiracion") or "")),
        "jornada": str(obj.get("nombreJornada") or ""),
    }


def detalle(url: str, cliente, robots) -> Dict:
    return parsear_detalle(pedir(url, cliente, robots))


def completar(fila: dict, det: Dict, ahora: Optional[datetime] = None) -> bool:
    """Agrega lo del detalle. Devuelve False si el sitio dice que la oferta ya no está vigente."""
    ahora = ahora or datetime.now()
    if (det["estado"] and det["estado"].upper() != "PUBLICADA") or (det["expira"] and det["expira"].date() < ahora.date()):
        return False
    partes = [det["descripcion"] or fila.get("description", "")]
    if det["requisitos"]:
        req = det["requisitos"]
        partes.append(req if normalizar(req[:12]).startswith("requisitos") else "Requisitos:\n" + req)
    if det["anios"] > 0 and normalizar(det["operador"]) in ("desde", ""):
        partes.append("Experiencia mínima: %d %s" % (det["anios"], "año" if det["anios"] == 1 else "años"))
    mod = _modalidad(det["jornada"])
    desc = "\n\n".join(p for p in partes if p)
    fila["description"] = _prefijo_modalidad(mod) + desc if mod and mod not in normalizar(fila.get("description", "")) else desc
    if mod == "remoto":
        fila["is_remote"] = True
    return True
