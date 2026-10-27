"""Arbeitnow: filtro estricto (remoto y sin ciudad), mapeo y errores (sin red real)."""
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import arbeitnow
import buscar
import config


def aviso(slug, **extra):
    base = {"slug": slug, "company_name": "Acme", "title": f"QA Engineer {slug}", "remote": True, "location": "Remote",
            "url": f"https://www.arbeitnow.com/jobs/companies/acme/{slug}", "tags": ["Remote", "Software Development"],
            "job_types": ["Full Time"], "created_at": 1793061611,
            "description": "&lt;p&gt;We build &lt;strong&gt;great&lt;/strong&gt; software.&lt;/p&gt;"}
    base.update(extra)
    return base


class Respuesta:
    def __init__(self, status=200, datos=None):
        self.status_code = status
        self._datos = datos if datos is not None else {}

    def json(self):
        return self._datos

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def test_registrada_en_config_y_api():
    assert "arbeitnow" in config.SITIOS and config.NOMBRE_FUENTE["arbeitnow"] == "Arbeitnow"
    assert "arbeitnow" in buscar.APIS_REMOTAS and buscar.APIS_REMOTAS["arbeitnow"] is arbeitnow
    assert config.MAX_ANTIGUEDAD_DIAS.get("arbeitnow") == 2


@pytest.mark.parametrize("remote,location,esperado", [
    (True, "Remote", True),
    (True, "Remote job", True),
    (True, "", True),
    (True, "Berlin", False),            # remoto declarado, pero con ciudad: presencial/híbrido
    (True, "Zürich", False),
    (False, "Remote", False),           # no marcado como remoto
    (False, "Berlin", False),
])
def test_filtro_remoto_sin_ciudad(remote, location, esperado):
    assert (arbeitnow.a_fila(aviso("x", remote=remote, location=location)) is not None) is esperado


@pytest.mark.parametrize("texto", [
    "You must be based in the EU to apply.",
    "We require the right to work in Germany.",
    "EU only position.",
    "Candidates must be located in Europe.",
    "Work within the EU time zones.",
])
def test_descarta_los_que_exigen_residir_en_europa(texto):
    assert arbeitnow.a_fila(aviso("x", description=texto)) is None


def test_mapea_y_limpia_html():
    f = arbeitnow.a_fila(aviso("qa-1"))
    assert f["job_url"].endswith("/qa-1") and f["title"] == "QA Engineer qa-1" and f["company"] == "Acme"
    assert f["location"] == "Remoto (global)" and f["is_remote"] is True
    assert "great software" in f["description"] and "<" not in f["description"] and "&lt;" not in f["description"]
    assert f["description"].startswith("Modalidad 100% remota.")
    assert "Etiquetas: Software Development." in f["description"]       # quita la etiqueta "Remote"
    assert f["date_posted"] == "2026-10-26" or f["date_posted"] == "2026-10-27"
    assert arbeitnow.a_fila({"title": "x", "url": "", "remote": True, "location": "Remote"}) is None
    assert arbeitnow.a_fila({"title": "", "url": "https://x.cl", "remote": True, "location": "Remote"}) is None


def test_buscar_filtra_y_respeta_el_tope(monkeypatch):
    datos = {"data": [aviso("a"), aviso("b", location="Berlin"), aviso("c"), aviso("d", remote=False), aviso("e")]}
    monkeypatch.setattr(arbeitnow.requests, "get", lambda *a, **k: Respuesta(200, datos))
    df = arbeitnow.buscar(resultados=100)
    assert isinstance(df, pd.DataFrame) and list(df.columns) == arbeitnow.COLUMNAS
    assert [u.rsplit("/", 1)[1] for u in df["job_url"]] == ["a", "c", "e"]
    assert len(arbeitnow.buscar(resultados=2)) == 2


def test_error_http_se_propaga_y_avisa_el_status(monkeypatch):
    vistos = []
    monkeypatch.setattr(arbeitnow.requests, "get", lambda *a, **k: Respuesta(503, {}))
    with pytest.raises(requests.HTTPError):
        arbeitnow.buscar(resultados=10, al_responder=vistos.append)
    assert vistos == [503]


def test_error_de_red_avisa_status_cero(monkeypatch):
    vistos = []

    def get(*a, **k):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(arbeitnow.requests, "get", get)
    with pytest.raises(requests.ConnectionError):
        arbeitnow.buscar(resultados=10, al_responder=vistos.append)
    assert vistos == [0]
