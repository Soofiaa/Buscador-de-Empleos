"""BNE (Bolsa Nacional de Empleo, bne.gob.cl): API JSON que usa la propia página, sin sesión ni cuenta.

Formato verificado el 28-10-2026 (fixtures en tests/fixtures/bne_*). La versión anterior (/data/ofertas/buscarListas,
/oferta/<codigo> en HTML) dejó de responder: 404 en todo.
  Listado: POST /api/ofertas/busqueda?page=0&size=25  cuerpo {"textoBusqueda": T, "idsOcupPr": [7643]}
    -> {content: [{id, codigoOferta, empresario: {nombreComercial}, nombrePuesto, region: {nombre}, comuna: {nombre},
        fechaPublicacion "AAAA-MM-DD", descripcion (texto plano, completo)}], totalElements, totalPages, ...}
    - idsOcupPr=[7643] = ocupación TI ("Desarrolladores y analistas de sistemas informáticos"); sin él, todas las ofertas.
    - textoBusqueda busca por palabras (no por frase exacta). Sin el campo, devuelve todas las ofertas (no sirve).
    - Si la empresa es confidencial, empresario.nombreComercial = "Confidencial".
  Detalle: GET /api/ofertas/publica/<id> -> {descripcion, experienciaRequerida (años; 0 = no requerida),
        tipoContratoNombre, tipoJornadaNombre, mostrarEmpresa, nombreEmpresa, fecPublicacionInicio, fecPublicacionFin,
        estadoOferta}
  Sin verificar: páginas > 0 (page=1) y textoBusqueda con más de una palabra.
"""
import html
import json
import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote

import pandas as pd

from filtros import normalizar
from geo import ubicacion_indeed
from red import ErrorFuente, pedir

BASE = "https://www.bne.gob.cl"
POR_PAGINA = 25
OCUPACION_TI = 7643
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval"]
# Contrato que el sitio no informa de verdad
CONTRATO_NO_INDICADO = ("no sabe / no responde", "indiferente", "", "sin contrato")


def _limpio(s) -> str:
    t = html.unescape(str(s or "")).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(l.strip() for l in t.splitlines() if l.strip())


def _fecha(s: str) -> str:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def _nombre(obj) -> str:
    return str((obj or {}).get("nombre") or "") if isinstance(obj, dict) else ""


def parsear_busqueda(texto: str) -> pd.DataFrame:
    """Lanza ErrorFuente si la respuesta no es el JSON esperado."""
    try:
        j = json.loads(texto)
    except json.JSONDecodeError as ex:
        raise ErrorFuente("la respuesta de BNE no es JSON (%s)" % ex.msg)
    resultados = j.get("content") if isinstance(j, dict) else None
    if not isinstance(resultados, list):
        raise ErrorFuente("el JSON de BNE no trae 'content' (¿cambió el sitio?)")
    filas = []
    for o in resultados:
        if not isinstance(o, dict):
            continue
        titulo, codigo = _limpio(o.get("nombrePuesto")), str(o.get("id") or "").strip()
        if not titulo or not codigo:
            continue
        empresario = o.get("empresario") if isinstance(o.get("empresario"), dict) else {}
        filas.append({
            "job_url": "%s/ofertas/%s" % (BASE, quote(codigo)), "title": titulo,
            "company": _limpio(empresario.get("nombreComercial")),
            "location": ubicacion_indeed(_nombre(o.get("comuna")), _nombre(o.get("region"))),
            "description": _limpio(o.get("descripcion")), "date_posted": _fecha(o.get("fechaPublicacion")),
            "is_remote": False, "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    """Una página de resultados de ocupación TI. `termino` es texto libre o 'ocupacion:7643'."""
    cuerpo = {"idsOcupPr": [OCUPACION_TI]} if termino.startswith("ocupacion:") else {"textoBusqueda": termino}
    url = "%s/api/ofertas/busqueda?page=0&size=%d" % (BASE, POR_PAGINA)
    return parsear_busqueda(pedir(url, cliente, robots, datos=cuerpo))


# ---- detalle ----
def _id_de(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def parsear_detalle(texto: str) -> Dict:
    try:
        j = json.loads(texto)
    except json.JSONDecodeError as ex:
        raise ErrorFuente("el detalle de BNE no es JSON (%s)" % ex.msg)
    if not isinstance(j, dict) or "descripcion" not in j or "experienciaRequerida" not in j:
        raise ErrorFuente("el detalle de BNE no trae 'descripcion' y 'experienciaRequerida' (¿cambió el sitio?)")
    exp = j.get("experienciaRequerida")
    return {"descripcion": _limpio(j.get("descripcion")),
            "experiencia": "No requerida" if not exp else "%d años" % int(exp),
            "contrato": _limpio(j.get("tipoContratoNombre"))}


def detalle(url: str, cliente, robots) -> Dict:
    return parsear_detalle(pedir("%s/api/ofertas/publica/%s" % (BASE, _id_de(url)), cliente, robots))


def completar(fila: dict, det: Dict) -> bool:
    """Agrega lo del detalle como frases que el clasificador ya entiende. Devuelve False si la oferta ya no sirve."""
    desc = fila.get("description") or ""
    if len(det.get("descripcion") or "") > len(desc):
        desc = det["descripcion"]
    exp = (det.get("experiencia") or "").strip()
    if re.search(r"\d", exp):
        desc += "\n\nExperiencia mínima (BNE): %s." % exp
    elif exp:
        desc += "\n\nExperiencia (BNE): %s." % exp.lower()
    contrato = (det.get("contrato") or "").strip()
    if normalizar(contrato) not in CONTRATO_NO_INDICADO:
        desc += "\n\nTipo de contrato (BNE): %s." % contrato
    fila["description"] = desc
    return True
