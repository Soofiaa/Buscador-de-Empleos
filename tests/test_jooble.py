"""Jooble: mapeo defensivo, clave por entorno y comportamiento ante errores/cuota (sin red real)."""
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config
import jooble


class Respuesta:
    def __init__(self, status=200, datos=None):
        self.status_code = status
        self._datos = datos if datos is not None else {}

    def json(self):
        return self._datos

    def raise_for_status(self):
        if self.status_code >= 400:
            e = requests.HTTPError(f"{self.status_code}")
            e.response = self
            raise e


def aviso(i, **extra):
    base = {"id": str(i), "title": f"Analista QA {i}", "company": "Empresa", "location": "Santiago, Chile",
            "link": f"https://cl.jooble.org/desc/{i}", "salary": "", "type": "Full-time",
            "updated": "2026-10-24T12:34:56", "snippet": "resumen", "source": "chiletrabajos"}
    base.update(extra)
    return base


@pytest.fixture
def con_clave(monkeypatch):
    monkeypatch.setenv("JOOBLE_KEY", "clave-de-prueba")
    monkeypatch.setattr(jooble.time, "sleep", lambda s: None)


def test_registrada_en_config_y_api():
    assert "jooble" in config.SITIOS and config.NOMBRE_FUENTE["jooble"] == "Jooble"
    assert "jooble" in buscar.APIS_REMOTAS and buscar.APIS_REMOTAS["jooble"] is jooble
    assert "jooble" in config.FUENTES_SIN_TEXTO      # solo trae resumen: va a «Sin texto»
    assert config.MAX_ANTIGUEDAD_DIAS.get("jooble") == 7


def test_sin_clave_no_consulta_y_devuelve_vacio(monkeypatch):
    monkeypatch.delenv("JOOBLE_KEY", raising=False)
    llamado = []
    monkeypatch.setattr(jooble.requests, "post", lambda *a, **k: llamado.append(1))
    df = jooble.buscar(resultados=10)
    assert list(df.columns) == jooble.COLUMNAS and df.empty and not llamado
    assert jooble.disponible() is False


def test_a_fila_mapea_y_descarta_lo_incompleto():
    f = jooble.a_fila(aviso(1))
    assert f["job_url"] == "https://cl.jooble.org/desc/1" and f["title"] == "Analista QA 1"
    assert f["description"] == "" and f["date_posted"] == "2026-10-24" and f["posted_at"] == "2026-10-24T12:34:56"
    assert f["is_remote"] is False and f["min_amount"] is None
    assert jooble.a_fila({"title": "x", "link": ""}) is None
    assert jooble.a_fila({"title": "", "link": "https://x.cl"}) is None
    assert jooble.a_fila({"title": "x", "link": "javascript:alert(1)"}) is None
    assert jooble.a_fila(aviso(2, location="Remoto (Chile)"))["is_remote"] is True


def test_buscar_recorre_terminos_y_ciudades_y_deduplica(con_clave, monkeypatch):
    pedidos = []

    def post(url, json=None, **kw):
        pedidos.append((json["keywords"], json["location"]))
        return Respuesta(200, {"totalCount": 2, "jobs": [aviso(1), aviso(2), aviso(1)]})

    monkeypatch.setattr(jooble.requests, "post", post)
    df = jooble.buscar(resultados=100)
    assert isinstance(df, pd.DataFrame) and len(df) == 2            # deduplica por enlace
    assert len(pedidos) == len(jooble.TERMINOS) * len(jooble.UBICACIONES)
    assert {t for t, _ in pedidos} == set(jooble.TERMINOS)
    assert {l for _, l in pedidos} == set(jooble.UBICACIONES)
    assert "Chile" not in {l for _, l in pedidos}                   # por país la API devuelve 0
    assert list(df.columns) == jooble.COLUMNAS
    assert set(df["description"]) == {""}


def test_buscar_corta_al_llegar_al_tope(con_clave, monkeypatch):
    pedidos = []

    def post(url, json=None, **kw):
        pedidos.append(json["keywords"])
        return Respuesta(200, {"jobs": [aviso(i) for i in range(10)]})

    monkeypatch.setattr(jooble.requests, "post", post)
    assert len(jooble.buscar(resultados=5)) == 5 and len(pedidos) == 1


def test_un_termino_caido_no_tumba_la_fuente(con_clave, monkeypatch):
    llamadas = {"n": 0}

    def post(url, json=None, **kw):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return Respuesta(500, {})
        return Respuesta(200, {"jobs": [aviso(9)]})

    monkeypatch.setattr(jooble.requests, "post", post)
    df = jooble.buscar(resultados=100)
    assert len(df) == 1 and df.iloc[0]["job_url"].endswith("/9")


def test_si_fallan_todos_se_lanza_para_contarlo(con_clave, monkeypatch):
    monkeypatch.setattr(jooble.requests, "post", lambda *a, **k: Respuesta(500, {}))
    with pytest.raises(requests.HTTPError):
        jooble.buscar(resultados=100)


def test_429_corta_de_inmediato(con_clave, monkeypatch):
    pedidos = []

    def post(url, json=None, **kw):
        pedidos.append(json["keywords"])
        return Respuesta(429, {})

    monkeypatch.setattr(jooble.requests, "post", post)
    with pytest.raises(requests.HTTPError):
        jooble.buscar(resultados=100)
    assert len(pedidos) == 1                                        # no insiste contra la cuota


def test_la_telemetria_recibe_el_status(con_clave, monkeypatch):
    vistos = []
    monkeypatch.setattr(jooble.requests, "post", lambda *a, **k: Respuesta(200, {"jobs": [aviso(3)]}))
    jooble.buscar(termino="qa", resultados=10, al_responder=vistos.append)
    assert vistos == [200, 200]                                     # una por ciudad
