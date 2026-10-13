"""Soporte TI: interruptor guardado en la base (ajuste "soporte") y reclasificación dirigida de soporte y SAP."""
import json
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config
import servidor
from test_servidor import pedir, puerto_libre


def raw(titulo, desc=""):
    return {"title": titulo, "company": "Empresa X", "location": "Santiago de Chile, RM, Chile", "description": desc,
            "is_remote": False, "min_amount": None, "max_amount": None, "currency": "", "interval": ""}


def insertar(con, url, titulo, estado="nueva", guardada=None, desc="", **manual):
    """Inserta una oferta con su raw y una clasificación GUARDADA (la actual del código si no se indica otra)."""
    clas = guardada or buscar.clasificar(raw(titulo, desc))
    con.execute("INSERT INTO ofertas (url, clave, titulo, empresa, raw, estado, " + ", ".join(buscar.CAMPOS_CLASIF)
                + "".join(", " + k for k in manual) + ") VALUES (?, ?, ?, 'Empresa X', ?, ?"
                + ", ?" * (len(buscar.CAMPOS_CLASIF) + len(manual)) + ")",
                [url, url, titulo, json.dumps(raw(titulo, desc)), estado] + [clas[c] for c in buscar.CAMPOS_CLASIF] + list(manual.values()))
    con.commit()


ANTIGUA_SOPORTE = {"categoria": "fuera_perfil", "razon": "soporte / helpdesk", "tipo": "", "prioridad": "", "modalidad": "",
                   "contrato": "", "sueldo": "", "experiencia": "", "motivo": ""}
ANTIGUA_SAP = {**ANTIGUA_SOPORTE, "categoria": "descartada", "razon": "sin rol objetivo"}


# ------------------------------------------------------------------ interruptor
def test_soporte_visible_por_defecto_y_oculto_con_el_ajuste(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    insertar(con, "http://mesa", "Mesa de Ayuda TI")
    insertar(con, "http://mesa-postulada", "Soporte TI", estado="postulada")
    insertar(con, "http://qa", "QA Tester")
    d = buscar.ofertas_para_pagina(con)
    assert d["soporte_incluido"] is True and {o["url"] for o in d["principal"]} == {"http://mesa", "http://mesa-postulada", "http://qa"}
    assert d["fuera_perfil"] == []
    buscar.guardar_soporte(con, {"incluir": False})
    d = buscar.ofertas_para_pagina(con)
    assert d["soporte_incluido"] is False
    assert {o["url"] for o in d["principal"]} == {"http://mesa-postulada", "http://qa"}   # lo decidido por ti se queda
    assert [(o["url"], o["razon"]) for o in d["fuera_perfil"]] == [("http://mesa", "soporte / helpdesk (oculto)")]
    fila = con.execute("SELECT categoria, tipo FROM ofertas WHERE url = 'http://mesa'").fetchone()
    assert tuple(fila) == ("principal", config.SOPORTE_TIPO)                             # la clasificación no cambia


def test_un_ajuste_ausente_vale_por_defecto(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    con.execute("DELETE FROM ajustes WHERE clave = 'soporte'")                            # como la base real, migrada antes
    con.commit()
    assert buscar.leer_ajuste(con, "soporte") == {"incluir": True}


@pytest.fixture
def srv(tmp_path):
    ruta = str(tmp_path / "t.db")
    con = buscar.conectar(ruta)
    insertar(con, "http://mesa", "Mesa de Ayuda TI")
    con.close()
    httpd = servidor.crear_servidor(servidor.Aplicacion(ruta, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1], ruta
    httpd.shutdown()
    httpd.server_close()


def test_ruta_del_ajuste_de_soporte(srv):
    puerto, _ = srv
    assert json.loads(pedir(puerto, "GET", "/api/ajustes/soporte")[2]) == {"incluir": True}
    st, _, cuerpo = pedir(puerto, "POST", "/api/ajustes/soporte", {"incluir": False})
    assert st == 200 and json.loads(cuerpo) == {"ok": True, "incluir": False}
    assert json.loads(pedir(puerto, "GET", "/api/ajustes/soporte")[2]) == {"incluir": False}
    d = json.loads(pedir(puerto, "GET", "/api/ofertas")[2])
    assert d["principal"] == [] and [o["url"] for o in d["fuera_perfil"]] == ["http://mesa"]


@pytest.mark.parametrize("cuerpo", [{"incluir": "no"}, {"incluir": 0}, {}, {"incluir": True, "otro": 1}, [True]])
def test_ajuste_de_soporte_invalido_es_400_y_no_cambia(srv, cuerpo):
    puerto, _ = srv
    assert pedir(puerto, "POST", "/api/ajustes/soporte", cuerpo)[0] == 400
    assert json.loads(pedir(puerto, "GET", "/api/ajustes/soporte")[2]) == {"incluir": True}


def test_ajuste_de_soporte_rechaza_origen_ajeno(srv):
    puerto, _ = srv
    assert pedir(puerto, "POST", "/api/ajustes/soporte", {"incluir": False}, {"Origin": "https://evil.example.com"})[0] == 403
    assert json.loads(pedir(puerto, "GET", "/api/ajustes/soporte")[2]) == {"incluir": True}


# ------------------------------------------------------------------ reclasificación dirigida
@pytest.fixture
def base_con_historia(tmp_path):
    """Ofertas guardadas con reglas antiguas: soporte en Fuera de perfil, SAP sin cargo, y una 'deriva' ajena."""
    con = buscar.conectar(str(tmp_path / "t.db"))
    insertar(con, "http://soporte", "Mesa de Ayuda TI", guardada=ANTIGUA_SOPORTE, notas="mi nota", fase="", prioridad_manual="Alta")
    insertar(con, "http://soporte-senior", "Coordinador de Soporte TI", guardada=ANTIGUA_SOPORTE)
    insertar(con, "http://sap", "Consultor SAP Junior", guardada=ANTIGUA_SAP, estado="revisada")
    insertar(con, "http://sap-igual", "Gerente SAP")                                        # seleccionada, pero no cambia
    deriva = {**buscar.clasificar(raw("QA Tester")), "experiencia": "1 años"}               # guardada distinta, NO seleccionada
    insertar(con, "http://deriva", "QA Tester", guardada=deriva)
    return con


def foto(con):
    return {r["url"]: dict(r) for r in con.execute("SELECT * FROM ofertas")}


def test_reclasificacion_dirigida_solo_cambia_lo_seleccionado_que_difiere(base_con_historia):
    con = base_con_historia
    antes = foto(con)
    cambios = buscar.reclasificar_dirigida(con)
    assert sorted(c["url"] for c in cambios) == ["http://sap", "http://soporte", "http://soporte-senior"]
    despues = foto(con)
    assert (despues["http://soporte"]["categoria"], despues["http://soporte"]["tipo"], despues["http://soporte"]["prioridad"]) == \
        ("principal", "S: Soporte TI", "Baja")
    assert (despues["http://soporte-senior"]["categoria"], despues["http://soporte-senior"]["razon"]) == ("descartada", "nivel semi senior / senior")
    assert (despues["http://sap"]["categoria"], despues["http://sap"]["tipo"], despues["http://sap"]["prioridad"]) == ("principal", "A: TI", "Media")
    assert despues["http://deriva"] == antes["http://deriva"] and despues["http://sap-igual"] == antes["http://sap-igual"]
    for url in antes:                                     # nunca toca el estado ni lo que escribe la usuaria
        for c in ["estado", *buscar.COLUMNAS_SEGUIMIENTO]:
            assert despues[url][c] == antes[url][c], (url, c)
    assert buscar.reclasificar_dirigida(con) == []        # repetirla no cambia nada


def test_reclasificacion_dirigida_en_simulacion_no_escribe(base_con_historia):
    con = base_con_historia
    antes = foto(con)
    assert len(buscar.reclasificar_dirigida(con, escribir=False)) == 3
    assert foto(con) == antes and not con.in_transaction


def test_reclasificacion_dirigida_es_todo_o_nada(base_con_historia, monkeypatch):
    con = base_con_historia
    antes = foto(con)
    llamadas = []
    original = buscar.clasificar

    def falla_a_la_segunda(o):
        llamadas.append(o["title"])
        if len(llamadas) == 2:
            raise RuntimeError("falla simulada")
        return original(o)
    monkeypatch.setattr(buscar, "clasificar", falla_a_la_segunda)
    with pytest.raises(RuntimeError):
        buscar.reclasificar_dirigida(con)
    assert foto(con) == antes
