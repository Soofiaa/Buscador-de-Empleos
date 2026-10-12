"""BNE (Bolsa Nacional de Empleo, bne.gob.cl): JSON público que usa la propia página, sin sesión ni cuenta.

Formato verificado por la app anterior (2026-10-05 y 2026-10-10, fixtures en tests/fixtures/bne_*):
  GET /data/ofertas/buscarListas?mostrar=empleo&(idOcupacion=N | textoLibre=T)&numPaginaRecuperar=1
      &numResultadosPorPagina=25&clasificarYPaginar=true
  -> {"paginaOfertas": {numPaginasTotal, resultados: [{codigo, fecha "dd/mm/aa", titulo, descripcion (recortada a
      ~1.000 caracteres), empresa, region, comuna, mostrarEmpresa}]}}
  - idOcupacion=7643 = "Desarrolladores y analistas de sistemas informáticos" (grupo TI, de la más nueva a la más antigua).
  - Varias palabras se buscan como Y/frase. No distingue tildes. Busca también dentro de palabras ("rpa" -> "SERPAJ").
  - Palabras de menos de 3 letras dan 0 resultados ("qa").
Detalle: GET /oferta/<codigo> -> HTML del servidor con "REQUISITOS SOLICITADOS" (Experiencia: "No requerida" | "N años")
  y "CARACTERÍSTICAS" (Tipo de contrato). No informa modalidad. Sin verificar: numPaginaRecuperar > 1.
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
CONTRATO_NO_INDICADO = ("no sabe / no responde", "indiferente", "")


def url_busqueda(ocupacion: Optional[int] = None, termino: str = "", pagina: int = 1) -> str:
    filtro = "idOcupacion=%d" % ocupacion if ocupacion is not None else "textoLibre=%s" % quote(termino)
    return ("%s/data/ofertas/buscarListas?mostrar=empleo&%s&numPaginaRecuperar=%d&numResultadosPorPagina=%d"
            "&clasificarYPaginar=true" % (BASE, filtro, pagina, POR_PAGINA))


def _limpio(s) -> str:
    t = html.unescape(str(s or "")).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(l.strip() for l in t.splitlines() if l.strip())


def _fecha(s: str) -> str:
    try:
        return datetime.strptime((s or "").strip(), "%d/%m/%y").date().isoformat()
    except ValueError:
        return ""


def parsear_busqueda(texto: str) -> pd.DataFrame:
    """Lanza ErrorFuente si la respuesta no es el JSON esperado."""
    try:
        j = json.loads(texto)
    except json.JSONDecodeError as ex:
        raise ErrorFuente("la respuesta de BNE no es JSON (%s)" % ex.msg)
    p = j.get("paginaOfertas") if isinstance(j, dict) else None
    if not isinstance(p, dict) or not isinstance(p.get("resultados"), list):
        raise ErrorFuente("el JSON de BNE no trae 'paginaOfertas.resultados' (¿cambió el sitio?)")
    filas = []
    for o in p["resultados"]:
        if not isinstance(o, dict):
            continue
        titulo, codigo = _limpio(o.get("titulo")), str(o.get("codigo") or "").strip()
        if not titulo or not codigo:
            continue
        empresa = _limpio(o.get("empresa")) if o.get("mostrarEmpresa", True) else ""
        filas.append({
            "job_url": "%s/oferta/%s" % (BASE, quote(codigo)), "title": titulo, "company": empresa,
            "location": ubicacion_indeed(o.get("comuna") or "", o.get("region") or ""),
            "description": _limpio(o.get("descripcion")), "date_posted": _fecha(o.get("fecha")),
            "is_remote": False, "min_amount": None, "max_amount": None, "currency": "", "interval": "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    """Una página de resultados. `termino` es un texto o 'ocupacion:7643'."""
    if termino.startswith("ocupacion:"):
        url = url_busqueda(ocupacion=int(termino.split(":", 1)[1]))
    else:
        url = url_busqueda(termino=termino)
    return parsear_busqueda(pedir(url, cliente, robots))


# ---- detalle ----
_RX_PANEL = re.compile(r'<h3 class="panel-title">\s*(DESCRIPCI(?:Ó|&Oacute;)N|REQUISITOS SOLICITADOS|CARACTER(?:Í|&Iacute;)STICAS)'
                       r'\s*</h3>(.*?)</article>', re.S | re.I)


def _texto(fragmento: str) -> str:
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", fragmento)
    return _limpio(re.sub(r"<[^>]+>", " ", t)).replace(" \n", "\n")


def _campo(panel: str, etiqueta: str) -> str:
    m = re.search(r"<strong>\s*<span>\s*" + re.escape(etiqueta) + r"\s*:?\s*</span>\s*</strong>\s*<br\s*/?>(.*?)</div>",
                  panel, re.S | re.I)
    return re.sub(r"\s+", " ", _texto(m.group(1))).strip() if m else ""


def parsear_detalle(texto: str) -> Dict:
    paneles = {normalizar(html.unescape(m.group(1))).upper(): m.group(2) for m in _RX_PANEL.finditer(texto or "")}
    if "REQUISITOS SOLICITADOS" not in paneles:
        raise ErrorFuente("el detalle de BNE no trae 'REQUISITOS SOLICITADOS' (¿cambió el sitio?)")
    m = re.search(r"<p>(.*?)</p>", paneles.get("DESCRIPCION", ""), re.S)
    return {"descripcion": _texto(m.group(1)) if m else "",
            "experiencia": _campo(paneles["REQUISITOS SOLICITADOS"], "Experiencia"),
            "contrato": _campo(paneles.get("CARACTERISTICAS", ""), "Tipo de contrato")}


def detalle(url: str, cliente, robots) -> Dict:
    return parsear_detalle(pedir(url, cliente, robots))


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
