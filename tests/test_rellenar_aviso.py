"""rellenar_aviso: extrae cargo, empresa, ubicación, modalidad y sueldo del JSON-LD JobPosting."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest

import rellenar_aviso
from red import ErrorFuente


def pagina(ld):
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head><body></body></html>'


def test_extrae_campos_del_jobposting():
    r = rellenar_aviso.parsear_aviso(pagina({
        "@type": "JobPosting", "title": "  Analista QA  ", "description": "<p>Trabajo <b>híbrido</b> en Santiago</p>",
        "hiringOrganization": {"name": "Banco Ejemplo"},
        "jobLocation": {"address": {"addressLocality": "Santiago", "addressRegion": "RM", "addressCountry": "CL"}},
        "baseSalary": {"currency": "CLP", "value": {"minValue": 1200000, "unitText": "MONTH"}},
    }))
    assert r["titulo"] == "Analista QA"
    assert r["empresa"] == "Banco Ejemplo"
    assert r["ubicacion"] == "Santiago, RM, CL"
    assert r["modalidad"] == "Híbrido"
    assert r["sueldo"] == "CLP 1.200.000 al mes"


def test_sin_jobposting_no_inventa_datos():
    try:
        rellenar_aviso.parsear_aviso("<html><body>nada</body></html>")
    except ErrorFuente:
        return
    raise AssertionError("debió lanzar ErrorFuente")


def test_desde_base_devuelve_lo_guardado_sin_red(tmp_path):
    import buscar
    import pandas as pd
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = pd.DataFrame([{"job_url": "https://cl.indeed.com/viewjob?jk=1", "title": "Analista QA", "company": "Acme",
                        "location": "Santiago, Chile", "description": "Modalidad híbrida. Buscamos QA con SQL.",
                        "date_posted": "", "is_remote": False, "min_amount": None, "max_amount": None,
                        "currency": "", "interval": ""}])
    buscar.guardar(con, buscar.procesar(df, "t", "indeed"))
    r = rellenar_aviso.desde_base(con, "https://cl.indeed.com/viewjob?jk=1")
    assert r["titulo"] == "Analista QA" and r["empresa"] == "Acme" and r["modalidad"] == "Híbrido"
    assert r["sueldo"] == ""                     # "No indicado" no se copia como sueldo
    assert rellenar_aviso.desde_base(con, "https://cl.indeed.com/viewjob?jk=999") is None


def test_texto_visible_no_incluye_scripts():
    html = "<html><script>var x='secreto';</script><body><h1>Analista QA</h1><p>Santiago</p></body></html>"
    t = rellenar_aviso.texto_visible(html)
    assert "Analista QA" in t and "Santiago" in t and "secreto" not in t


def test_sin_jobposting_la_ia_lee_la_pagina_que_se_pidio(monkeypatch):
    texto_largo = "<body><h1>Analista QA</h1><p>Santiago</p>" + "<p>detalle del cargo</p>" * 30 + "</body>"
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda url, c, r: texto_largo)
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: pytest.fail("no debía abrir navegador"))
    visto = {}
    def falsa_ia(texto):
        visto["texto"] = texto
        return {"titulo": "Analista QA", "empresa": "Acme", "ubicacion": "Santiago", "modalidad": "", "sueldo": ""}
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso", falsa_ia)
    r = rellenar_aviso.desde_url("https://x.cl/1", None, None)
    assert r["empresa"] == "Acme" and "Santiago" in visto["texto"]


def test_si_la_ia_no_encuentra_cargo_ni_empresa_es_error(monkeypatch):
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda u, c, r: "<body>" + "<p>texto suficiente</p>" * 40 + "</body>")
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso",
                        lambda t: {"titulo": "", "empresa": "", "ubicacion": "", "modalidad": "", "sueldo": ""})
    try:
        rellenar_aviso.desde_url("https://x.cl/1", None, None)
    except ErrorFuente:
        return
    raise AssertionError("una respuesta vacía no puede pasar como éxito")


def test_si_la_ia_falla_el_error_llega_al_usuario(monkeypatch):
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda url, c, r: "<body>texto</body>")
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso", lambda t: {"error": "sin API Key"})
    try:
        rellenar_aviso.desde_url("https://x.cl/1", None, None)
    except ErrorFuente as ex:
        assert "sin API Key" in str(ex)
        return
    raise AssertionError("debió lanzar ErrorFuente")


def test_sin_empresa_no_devuelve_datos_parciales():
    try:
        rellenar_aviso.parsear_aviso(pagina({"@type": "JobPosting", "title": "X"}))
    except ErrorFuente:
        return
    raise AssertionError("debió lanzar ErrorFuente")
