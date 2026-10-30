"""rellenar_linkedin: solo postuladas de LinkedIn en «Sin texto»; guarda el texto sin reclasificar."""
import json

import pandas as pd

import buscar
import rellenar_linkedin
from red import Bloqueo, ErrorFuente


def _fila(url):
    return {"job_url": url, "title": "Analista Funcional", "company": "Empresa " + url[-1],   # distintas: no se unen
            "location": "Santiago, Región Metropolitana, Chile", "description": "", "date_posted": None,
            "is_remote": False, "min_amount": None, "max_amount": None, "currency": "", "interval": ""}


def _base(tmp_path, urls, fuente="linkedin"):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(pd.DataFrame([_fila(u) for u in urls]), "t", fuente))
    return con


def _estado(con, url, estado):
    con.execute("UPDATE ofertas SET estado = ? WHERE url = ?", (estado, url))
    con.commit()


def test_solo_postuladas_y_sin_reclasificar(tmp_path):
    con = _base(tmp_path, ["http://li/1", "http://li/2"])
    _estado(con, "http://li/1", "postulada")
    _estado(con, "http://li/2", "descartada")
    antes = dict(con.execute("SELECT * FROM ofertas WHERE url = 'http://li/1'").fetchone())

    r = rellenar_linkedin.rellenar(con, lambda url: "Requisito: 5 años de experiencia en SAP.")

    assert r == {"hechas": ["http://li/1"], "fallidas": []}
    despues = dict(con.execute("SELECT * FROM ofertas WHERE url = 'http://li/1'").fetchone())
    assert json.loads(despues.pop("raw"))["description"] == "Requisito: 5 años de experiencia en SAP."
    antes.pop("raw")
    assert despues == antes                       # categoría, estado, razón, etc. intactos
    assert json.loads(con.execute("SELECT raw FROM ofertas WHERE url = 'http://li/2'").fetchone()["raw"])["description"] == ""
    assert rellenar_linkedin.pendientes(con) == []  # una segunda corrida no hace nada


def test_bloqueo_detiene_y_error_salta(tmp_path):
    con = _base(tmp_path, ["http://li/1", "http://li/2", "http://li/3"])
    for u in ("http://li/1", "http://li/2", "http://li/3"):
        _estado(con, u, "postulada")

    def obtener(url):
        if url.endswith("1"):
            raise ErrorFuente("sin descripción")
        raise Bloqueo("HTTP 429")

    r = rellenar_linkedin.rellenar(con, obtener)
    assert r["hechas"] == [] and [u for u, _ in r["fallidas"]] == ["http://li/1", "http://li/2"]


def test_otra_fuente_no_se_toca(tmp_path):
    con = _base(tmp_path, ["http://gd/1"], fuente="glassdoor")
    _estado(con, "http://gd/1", "postulada")
    assert rellenar_linkedin.pendientes(con) == []
