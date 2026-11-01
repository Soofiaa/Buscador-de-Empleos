"""rellenar_aviso: extrae cargo, empresa, ubicación, modalidad y sueldo del JSON-LD JobPosting."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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


def test_sin_empresa_no_devuelve_datos_parciales():
    try:
        rellenar_aviso.parsear_aviso(pagina({"@type": "JobPosting", "title": "X"}))
    except ErrorFuente:
        return
    raise AssertionError("debió lanzar ErrorFuente")
