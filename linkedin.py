"""LinkedIn: endpoint público para invitados (sin cuenta ni autenticación).

Las ofertas de LinkedIn son públicas (las empresas pagan para que se encuentren). El endpoint
``/jobs-guest/jobs/api/seeMoreJobPostings/search`` devuelve HTML con tarjetas de empleo que se
parsean con BeautifulSoup; el detalle de cada oferta se obtiene con ``/jobs-guest/jobs/api/jobPosting/{id}``.

Verificado con datos reales (2026-10-15; fixtures tests/fixtures/linkedin_listado.html y linkedin_detalle.html):
  - Listado: GET /jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=<término>&location=Chile&start=0
    10 tarjetas por página. Cada ``<li>`` tiene h3.base-search-card__title (título),
    h4.base-search-card__subtitle (empresa), span.job-search-card__location (ubicación),
    a.base-card__full-link (URL), <time datetime="AAAA-MM-DD"> (fecha).
  - Detalle: GET /jobs-guest/jobs/api/jobPosting/<id>. Descripción en div.show-more-less-html__markup;
    criterios (nivel, tipo de empleo, sector) en li.description__job-criteria-item.
  - Sueldo: raro en Chile; si aparece, en span.job-search-card__salary-info.
  - Paginación: start=0, 10, 20... Solo se lee la primera página (10 ofertas).
No autenticada: sin cuenta, sin credenciales, sin cookies.
"""
import html as html_mod
import re
from typing import Dict, Optional
from urllib.parse import urlsplit

import pandas as pd
from bs4 import BeautifulSoup

from filtros import normalizar
from red import ErrorFuente, pedir

BASE = "https://www.linkedin.com"
COLUMNAS = ["job_url", "title", "company", "location", "description", "date_posted", "is_remote",
            "min_amount", "max_amount", "currency", "interval"]

# ---- utilidades ----

def _limpio(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _limpiar_html(t) -> str:
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", html_mod.unescape(str(t or "")))
    t = re.sub(r"<[^>]+>", " ", t)
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in t.splitlines() if l.strip())


def _url_limpia(href: str) -> str:
    """Quita los parámetros de tracking de LinkedIn; deja solo la URL base del aviso."""
    return href.split("?")[0] if href else ""


def _job_id(url: str) -> str:
    """Extrae el id numérico de la URL del aviso (último segmento numérico en el path o el final del slug)."""
    m = re.search(r"-(\d{5,})(?:\?|$)", url)
    if m:
        return m.group(1)
    partes = urlsplit(url).path.rstrip("/").rsplit("/", 1)
    return partes[-1] if partes else ""


# ---- búsqueda (listado) ----

def url_busqueda(termino: str, ubicacion: str = "Chile", start: int = 0) -> str:
    from urllib.parse import quote_plus
    return ("%s/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=%s&location=%s&start=%d"
            % (BASE, quote_plus(termino), quote_plus(ubicacion), start))


def parsear_listado(html: str) -> pd.DataFrame:
    """Lanza ErrorFuente si la respuesta no tiene tarjetas reconocibles."""
    soup = BeautifulSoup(html or "", "html.parser")
    tarjetas = soup.find_all("li")
    if not tarjetas:
        # Puede ser un bloqueo suave (página vacía) o un cambio de formato
        if not html or len(html.strip()) < 100:
            raise ErrorFuente("LinkedIn devolvió una respuesta vacía (¿bloqueo?)")
        return pd.DataFrame(columns=COLUMNAS)
    filas, vistos = [], set()
    for card in tarjetas:
        enlace = card.find("a", class_="base-card__full-link")
        if not enlace or not enlace.get("href"):
            continue
        url = _url_limpia(html_mod.unescape(enlace["href"]))
        if not url or url in vistos:
            continue
        vistos.add(url)

        titulo_el = card.find("h3", class_="base-search-card__title")
        empresa_el = card.find("h4", class_="base-search-card__subtitle")
        ubicacion_el = card.find("span", class_="job-search-card__location")
        tiempo_el = card.find("time", class_="job-search-card__listdate")
        if not tiempo_el:
            tiempo_el = card.find("time")
        sueldo_el = card.find("span", class_="job-search-card__salary-info")

        titulo = _limpio(titulo_el.get_text()) if titulo_el else ""
        if not titulo:
            continue

        fecha = ""
        if tiempo_el and tiempo_el.get("datetime"):
            fecha = tiempo_el["datetime"][:10]   # "AAAA-MM-DD"

        ubicacion_txt = _limpio(ubicacion_el.get_text()) if ubicacion_el else ""
        # Normalizar ubicaciones de Chile: "Gran Santiago, Región Metropolitana de Santiago, Chile" -> simplificar
        # Se deja tal cual; el clasificador (filtros.py) ya sabe leer "Chile" en la ubicación.

        sueldo = _limpio(sueldo_el.get_text()) if sueldo_el else ""
        min_amount, max_amount, currency = None, None, ""
        if sueldo:
            # intentar extraer rango numérico (raro en Chile pero posible)
            nums = re.findall(r"[\d.,]+", sueldo.replace(".", "").replace(",", ""))
            if len(nums) >= 2:
                try:
                    min_amount, max_amount = int(nums[0]), int(nums[1])
                except ValueError:
                    pass
            elif len(nums) == 1:
                try:
                    min_amount = max_amount = int(nums[0])
                except ValueError:
                    pass
            if min_amount is not None:
                currency = "CLP" if "$" in sueldo and "usd" not in sueldo.lower() else "USD"

        filas.append({
            "job_url": url, "title": titulo,
            "company": _limpio(empresa_el.get_text()) if empresa_el else "",
            "location": ubicacion_txt, "description": "",   # el listado no trae descripción
            "date_posted": fecha, "is_remote": False,
            "min_amount": min_amount, "max_amount": max_amount,
            "currency": currency, "interval": "monthly" if min_amount else "",
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def listar(termino: str, cliente, robots) -> pd.DataFrame:
    """Una página de resultados (10 ofertas). Usa red.pedir (robots.txt + pausa)."""
    return parsear_listado(pedir(url_busqueda(termino), cliente, robots))


# ---- detalle ----

def parsear_detalle(html: str) -> Dict:
    """Extrae descripción y criterios del detalle de una oferta."""
    soup = BeautifulSoup(html or "", "html.parser")

    # Descripción completa
    desc_el = soup.find("div", class_="show-more-less-html__markup")
    if not desc_el:
        desc_el = soup.find("div", class_="description__text")
    if not desc_el:
        raise ErrorFuente("el detalle de LinkedIn no trae la descripción (¿cambió el sitio?)")
    descripcion = _limpiar_html(str(desc_el))

    # Criterios: nivel de antigüedad, tipo de empleo, función, sectores
    criterios = {}
    for item in soup.find_all("li", class_="description__job-criteria-item"):
        label = item.find("h3")
        valor = item.find("span")
        if label and valor:
            clave = normalizar(label.get_text(strip=True))
            criterios[clave] = _limpio(valor.get_text())

    return {"descripcion": descripcion, "criterios": criterios}


def detalle(url: str, cliente, robots) -> Dict:
    """Pide el detalle a través del endpoint de la API guest (no la página pública del aviso)."""
    jid = _job_id(url)
    if not jid:
        raise ErrorFuente("no se pudo extraer el id del aviso de LinkedIn (%s)" % url[:80])
    api_url = "%s/jobs-guest/jobs/api/jobPosting/%s" % (BASE, jid)
    return parsear_detalle(pedir(api_url, cliente, robots))


def completar(fila: dict, det: Dict) -> bool:
    """Agrega el detalle al listado. Siempre devuelve True (LinkedIn no informa vencimiento en el detalle)."""
    desc = det.get("descripcion") or fila.get("description", "")
    criterios = det.get("criterios", {})

    # Agregar el nivel si lo informa
    nivel = criterios.get("nivel de antiguedad", "")
    tipo_empleo = criterios.get("tipo de empleo", "")
    prefijo = []
    if nivel:
        prefijo.append("Nivel: %s." % nivel)
    if tipo_empleo:
        prefijo.append("Tipo de empleo: %s." % tipo_empleo)

    # Modalidad: si la ubicación original dice "remoto" o el tipo dice algo de remoto
    ubicacion = normalizar(fila.get("location") or "")
    if "remoto" in ubicacion or "remote" in ubicacion:
        fila["is_remote"] = True
        prefijo.append("Modalidad remota.")

    fila["description"] = " ".join(prefijo + [desc]).strip() if prefijo else desc
    return True
