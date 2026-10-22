"""Pegar la descripción de una oferta de «Sin texto» (LinkedIn/Glassdoor): solo esa oferta, y el texto decide."""
import json

import pandas as pd
import pytest

import buscar


def _fila(url, titulo, empresa="X", ubic="Santiago, Región Metropolitana, Chile", desc=""):
    return {"job_url": url, "title": titulo, "company": empresa, "location": ubic, "description": desc,
            "date_posted": None, "is_remote": False, "min_amount": None, "max_amount": None,
            "currency": "", "interval": ""}


def _linkedin(tmp_path, titulo, url="http://li"):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(pd.DataFrame([_fila(url, titulo)]), "t", "linkedin"))
    assert buscar.ofertas_para_pagina(con)["sin_descripcion"][0]["url"] == url
    return con


def test_texto_con_3_anos_descarta_la_oferta(tmp_path):
    con = _linkedin(tmp_path, "Analista Funcional")
    r = buscar.pegar_descripcion(con, "http://li", "Buscamos analista con 3 años de experiencia en proyectos SAP.")
    assert r["categoria"] == "descartada"
    assert "exige" in r["razon"]
    d = buscar.ofertas_para_pagina(con)
    assert d["sin_descripcion"] == [] and d["principal"] == []


def test_texto_con_3_a_5_anos_descarta_la_oferta(tmp_path):
    con = _linkedin(tmp_path, "Analista de Sistemas")
    r = buscar.pegar_descripcion(con, "http://li", "Requisitos: entre 3 a 5 años de experiencia en desarrollo.")
    assert r["categoria"] == "descartada"


def test_texto_con_5_anos_en_ingles_descarta_la_oferta(tmp_path):
    con = _linkedin(tmp_path, "QA Tester")
    r = buscar.pegar_descripcion(con, "http://li", "We need 5 years of experience in software testing.")
    assert r["categoria"] == "descartada"


@pytest.mark.xfail(strict=True, reason="Hallazgo 22-10: con un título que ya calza un rol TI (Alta), la descripción "
                   "no se revisa para decidir si el cargo es TI. Corregirlo cambia lo guardado; pendiente de aprobación.")
def test_texto_no_ti_no_pasa(tmp_path):
    """Un aviso de eléctrico no debe quedar como principal aunque el título diga «analista»."""
    con = _linkedin(tmp_path, "Analista Funcional")
    r = buscar.pegar_descripcion(con, "http://li", "Se busca técnico eléctrico para mantenimiento de tableros industriales.")
    assert r["categoria"] == "descartada"


def test_texto_ti_sin_anos_pasa_a_ofertas(tmp_path):
    con = _linkedin(tmp_path, "Analista Funcional")
    r = buscar.pegar_descripcion(con, "http://li", "Levantamiento de requerimientos y pruebas funcionales con SQL.")
    assert r["categoria"] == "principal"
    d = buscar.ofertas_para_pagina(con)
    assert [f["url"] for f in d["principal"]] == ["http://li"] and d["sin_descripcion"] == []


def test_guarda_el_texto_en_raw_y_no_toca_el_estado(tmp_path):
    con = _linkedin(tmp_path, "Analista Funcional")
    buscar.marcar_estado(con, "http://li", "revisada", origen="lista")
    buscar.pegar_descripcion(con, "http://li", "Analista con SQL y pruebas funcionales.")
    fila = con.execute("SELECT raw, estado FROM ofertas WHERE url = ?", ("http://li",)).fetchone()
    assert json.loads(fila["raw"])["description"] == "Analista con SQL y pruebas funcionales."
    assert fila["estado"] == "revisada"


def test_solo_cambia_la_oferta_pedida(tmp_path):
    con = _linkedin(tmp_path, "Analista Funcional")
    buscar.guardar(con, buscar.procesar(
        pd.DataFrame([_fila("http://otra", "QA Tester", empresa="Y", ubic="Santiago de Chile, RM, Chile")]), "t", "linkedin"))
    antes = con.execute("SELECT url, categoria, raw FROM ofertas WHERE url = ?", ("http://otra",)).fetchone()
    buscar.pegar_descripcion(con, "http://li", "Texto con 3 años de experiencia.")
    despues = con.execute("SELECT url, categoria, raw FROM ofertas WHERE url = ?", ("http://otra",)).fetchone()
    assert tuple(antes) == tuple(despues)


@pytest.mark.parametrize("url, texto_, error", [
    ("", "algo", "falta la oferta"),
    ("http://li", "   ", "la descripción está vacía"),
    ("http://li", 123, "la descripción debe ser texto"),
    ("http://li", "x" * (buscar.LIMITE_DESCRIPCION + 1), "tiene más de"),
])
def test_rechaza_pedidos_invalidos(tmp_path, url, texto_, error):
    con = _linkedin(tmp_path, "Analista Funcional")
    with pytest.raises(buscar.ErrorDatos) as ex:
        buscar.pegar_descripcion(con, url, texto_)
    assert error in str(ex.value)


def test_no_acepta_ofertas_que_no_estan_en_sin_texto(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(
        pd.DataFrame([_fila("http://ind", "Analista Funcional", ubic="Santiago de Chile, RM, Chile", desc="Texto.")]),
        "t", "indeed"))
    with pytest.raises(buscar.ErrorDatos) as ex:
        buscar.pegar_descripcion(con, "http://ind", "Otro texto con 3 años de experiencia.")
    assert ex.value.codigo == 400


def test_oferta_inexistente_responde_404(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    with pytest.raises(buscar.ErrorDatos) as ex:
        buscar.pegar_descripcion(con, "http://no", "texto")
    assert ex.value.codigo == 404
