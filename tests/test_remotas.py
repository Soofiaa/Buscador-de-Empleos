"""Himalayas y Jobicy (APIs públicas de empleo remoto). Respuestas de ejemplo con la forma real de la API
(verificada el 2026-10-22), sin red."""
from datetime import datetime, timedelta, timezone

import pytest

import buscar
import config
import filtros
import himalayas
import jobicy

AHORA = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)


def _him(**k):
    base = {"guid": "https://himalayas.app/companies/oceans/jobs/x", "title": "Analista Funcional",
            "companyName": "Oceans", "description": "<p>Analista funcional con SQL.</p>", "excerpt": "resumen",
            "seniority": ["Mid-level"], "locationRestrictions": [], "pubDate": 1792699379,
            "minSalary": None, "maxSalary": None, "currency": None, "salaryPeriod": "annual",
            "applicationLink": "https://himalayas.app/x?utm_source=api"}
    base.update(k)
    return base


def _job(**k):
    base = {"id": 1, "url": "https://jobicy.com/jobs/1-analista", "jobTitle": "Analista Funcional",
            "companyName": "GiveDirectly", "jobGeo": "Canada,  USA", "jobLevel": "Director",
            "jobDescription": "<p>Analista funcional y SQL.</p>", "jobExcerpt": "resumen",
            "pubDate": "2026-10-22T18:57:18+00:00", "salaryMin": 120750, "salaryMax": 120750,
            "salaryCurrency": "USD", "salaryPeriod": "yearly"}
    base.update(k)
    return base


# ---- Himalayas

def test_himalayas_aviso_sin_restriccion_se_acepta_como_remoto_global():
    f = himalayas.a_fila(_him())
    assert f["location"] == "Remoto (global)" and f["is_remote"] is True
    assert f["job_url"].endswith("/x") and f["title"] == "Analista Funcional"
    assert "Modalidad 100% remota." in f["description"] and "Nivel Mid-level." in f["description"]
    assert "<p>" not in f["description"]


def test_himalayas_restringido_a_otro_pais_se_descarta():
    assert himalayas.a_fila(_him(locationRestrictions=["Sri Lanka"])) is None
    assert himalayas.a_fila(_him(locationRestrictions=["El Salvador"])) is None


def test_himalayas_restringido_a_chile_queda_como_chile():
    assert himalayas.a_fila(_him(locationRestrictions=["Chile"]))["location"] == "Chile"


def test_himalayas_sueldo_solo_si_trae_moneda():
    f = himalayas.a_fila(_him(minSalary=90000, maxSalary=110000, currency="USD", salaryPeriod="annual"))
    assert f["min_amount"] == 90000 and f["currency"] == "USD" and f["interval"] == "yearly"
    sin = himalayas.a_fila(_him(minSalary=90000, currency=None))
    assert sin["min_amount"] is None and sin["currency"] == ""


def test_himalayas_fecha_con_hora_utc():
    f = himalayas.a_fila(_him(pubDate=1792699379))
    assert f["posted_at"].endswith("+00:00") and f["date_posted"] == f["posted_at"][:10]


def test_himalayas_buscar_usa_la_api_y_filtra(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"jobs": [_him(), _him(locationRestrictions=["Kenya"]), _him(title="")]}
    llamadas = []
    monkeypatch.setattr(himalayas.requests, "get", lambda url, **k: (llamadas.append(k["params"]), Resp())[1])
    df = himalayas.buscar("", 10)
    assert len(df) == 1 and list(df.columns) == himalayas.COLUMNAS
    assert llamadas == [{"limit": 10}]


def test_himalayas_error_de_red_avisa_status_0(monkeypatch):
    import requests
    estados = []
    def roto(*a, **k): raise requests.ConnectionError("sin red")
    monkeypatch.setattr(himalayas.requests, "get", roto)
    with pytest.raises(requests.ConnectionError):
        himalayas.buscar("", 5, al_responder=estados.append)
    assert estados == [0]


# ---- Jobicy

def test_jobicy_geo_global_se_acepta():
    f = jobicy.a_fila(_job(jobGeo="anywhere"))
    assert f["location"] == "Remoto (global)" and f["is_remote"] is True
    assert jobicy.a_fila(_job(jobGeo=""))["location"] == "Remoto (global)"


def test_jobicy_geo_con_chile_queda_como_chile():
    assert jobicy.a_fila(_job(jobGeo="Chile, Argentina"))["location"] == "Chile"


def test_jobicy_geo_de_otros_paises_se_descarta():
    assert jobicy.a_fila(_job(jobGeo="Canada,  USA")) is None
    assert jobicy.a_fila(_job(jobGeo="Germany, Poland")) is None


def test_jobicy_nivel_any_no_se_escribe():
    f = jobicy.a_fila(_job(jobGeo="anywhere", jobLevel="Any"))
    assert "Nivel" not in f["description"] and "Modalidad 100% remota." in f["description"]


def test_jobicy_sueldo_y_fecha():
    f = jobicy.a_fila(_job(jobGeo="anywhere"))
    assert f["min_amount"] == 120750 and f["currency"] == "USD" and f["interval"] == "yearly"
    assert f["posted_at"] == "2026-10-22T18:57:18+00:00" and f["date_posted"] == "2026-10-22"


def test_jobicy_buscar_usa_la_api_y_filtra(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"jobs": [_job(jobGeo="anywhere"), _job(jobGeo="Germany"), _job(jobTitle="")]}
    llamadas = []
    monkeypatch.setattr(jobicy.requests, "get", lambda url, **k: (llamadas.append(k["params"]), Resp())[1])
    df = jobicy.buscar("", 10)
    assert len(df) == 1 and list(df.columns) == jobicy.COLUMNAS
    assert llamadas == [{"count": 10}]


# ---- Conexión con la app

def test_remotas_estan_en_las_fuentes_y_nombres():
    for s in ("himalayas", "jobicy"):
        assert s in config.SITIOS and s in config.NOMBRE_FUENTE and s in config.MAX_ANTIGUEDAD_DIAS
        assert s in buscar.APIS_REMOTAS


def test_soporte_ti_es_termino_de_busqueda():
    assert "soporte TI" in config.TERMINOS_A and "help desk" in config.TERMINOS_A
    assert "soporte TI" in config.TERMINOS_SECUNDARIOS and "help desk" in config.TERMINOS_SECUNDARIOS


def test_remotas_son_una_consulta_por_corrida(monkeypatch):
    plan = [(s, t, l) for s in config.SITIOS if s not in buscar.PORTALES
            for t in ([""] if s in buscar.APIS_REMOTAS else [config.TERMINOS_SECUNDARIOS[0]])
            for l in (["Chile"] if s in buscar.APIS_REMOTAS else ["Santiago, Chile"])]
    assert ("himalayas", "", "Chile") in plan and ("jobicy", "", "Chile") in plan
    assert sum(1 for p in plan if p[0] == "himalayas") == 1


def test_remotas_pasan_el_filtro_de_zona_como_remoto_global():
    raw = {"job_url": "https://x/1", "title": "Analista Funcional", "company": "Oceans",
           "location": "Remoto (global)", "description": "Nivel Mid-level. Modalidad 100% remota. Analista funcional "
           "con SQL y procesos.", "date_posted": "2026-10-22", "is_remote": True, "fuente": "himalayas",
           "min_amount": None, "max_amount": None, "currency": "", "interval": ""}
    resultado = filtros.clasificar(raw)
    assert resultado["categoria"] != "descartada" or "ubicación" not in resultado["razon"]
    assert "ubicación" not in resultado["razon"]
