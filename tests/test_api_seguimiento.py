"""Fase A: /api/marcar (fecha automática y deshacer exacto), /api/nota (parcial y validada), 503 y prioridad mostrada."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import servidor
from test_servidor import pedir, puerto_libre   # mismo cliente HTTP que el resto de las pruebas del servidor

import threading

HOY = "2026-10-13"


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(buscar, "ahora_chile", lambda: datetime(2026, 10, 13, 12, 0))
    ruta = str(tmp_path / "t.db")
    con = buscar.conectar(ruta)
    for url, estado, fecha in (("http://a", "nueva", ""), ("http://b", "revisada", ""), ("http://c", "descartada", "2026-10-01")):
        con.execute("INSERT INTO ofertas (url, clave, titulo, categoria, prioridad, estado, fecha_postulacion, notas) "
                    "VALUES (?, ?, 'QA', 'principal', 'Media', ?, ?, 'nota previa')", (url, url, estado, fecha))
    con.commit()
    con.close()
    httpd = servidor.crear_servidor(servidor.Aplicacion(ruta, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1], ruta
    httpd.shutdown()
    httpd.server_close()


def post(puerto, ruta, cuerpo):
    st, _, datos = pedir(puerto, "POST", ruta, cuerpo)
    return st, json.loads(datos or b"{}")


def fila(ruta_db, url):
    con = sqlite3.connect(ruta_db)
    con.row_factory = sqlite3.Row
    f = dict(con.execute("SELECT * FROM ofertas WHERE url = ?", (url,)).fetchone())
    con.close()
    return f


# ------------------------------------------------------------------ /api/marcar
def test_postular_pone_la_fecha_de_hoy_y_deshacer_la_quita_exactamente(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/marcar", {"url": "http://a", "estado": "postulada", "origen": "lista"})
    assert st == 200 and r["anterior"] == {"estado": "nueva", "fase": "", "fecha_postulacion": ""}
    assert r["actual"] == {"estado": "postulada", "fase": "", "fecha_postulacion": HOY}
    st, _ = post(puerto, "/api/marcar", {"url": "http://a", "restaurar": {**r["anterior"], "si_actual": r["actual"]}})
    assert st == 200
    f = fila(db, "http://a")
    assert (f["estado"], f["fecha_postulacion"]) == ("nueva", "")            # vuelve exactamente: sin fecha


def test_una_fecha_existente_no_se_pisa_ni_se_borra(srv):
    puerto, db = srv
    _, r = post(puerto, "/api/marcar", {"url": "http://c", "estado": "entrevista", "origen": "lista"})
    assert r["actual"] == {"estado": "entrevista", "fase": "", "fecha_postulacion": "2026-10-01"}
    post(puerto, "/api/marcar", {"url": "http://c", "estado": "descartada", "origen": "lista"})
    assert fila(db, "http://c")["fecha_postulacion"] == "2026-10-01"         # cambiar de estado no borra el historial


def test_deshacer_no_pisa_un_cambio_hecho_entre_medias(srv):
    puerto, db = srv
    _, r1 = post(puerto, "/api/marcar", {"url": "http://b", "estado": "postulada", "origen": "lista"})
    post(puerto, "/api/marcar", {"url": "http://b", "estado": "entrevista", "origen": "lista"})   # otro cambio después
    st, r = post(puerto, "/api/marcar", {"url": "http://b", "restaurar": {**r1["anterior"], "si_actual": r1["actual"]}})
    assert st == 409 and "cambió" in r["error"]
    assert fila(db, "http://b")["estado"] == "entrevista"


@pytest.mark.parametrize("restaurar", [
    {"estado": "inventado", "fecha_postulacion": "", "si_actual": {"estado": "postulada", "fecha_postulacion": HOY}},
    {"estado": "nueva", "fecha_postulacion": "2026-02-30", "si_actual": {"estado": "postulada", "fecha_postulacion": HOY}},
    {"estado": "nueva", "fecha_postulacion": "13/10/2026", "si_actual": {"estado": "postulada", "fecha_postulacion": HOY}},
    {"estado": "nueva", "fecha_postulacion": ""},                                      # falta si_actual
    {"estado": "nueva", "fecha_postulacion": "", "si_actual": {"estado": "postulada", "fecha_postulacion": 5}},
    "nueva",
])
def test_restaurar_invalido_es_400_y_no_cambia_nada(srv, restaurar):
    puerto, db = srv
    antes = fila(db, "http://a")
    assert post(puerto, "/api/marcar", {"url": "http://a", "restaurar": restaurar})[0] == 400
    assert fila(db, "http://a") == antes


def test_marcar_oferta_inexistente_o_estado_invalido(srv):
    puerto, _ = srv
    assert post(puerto, "/api/marcar", {"url": "http://no-existe", "estado": "revisada", "origen": "lista"})[0] == 404
    assert post(puerto, "/api/marcar", {"url": "http://a", "estado": "x", "origen": "lista"})[0] == 400
    assert post(puerto, "/api/marcar", {"estado": "revisada", "origen": "lista"})[0] == 400


# ------------------------------------------------------------------ /api/nota
def test_nota_es_parcial_solo_cambia_lo_enviado(srv):
    puerto, db = srv
    antes = fila(db, "http://b")
    st, r = post(puerto, "/api/nota", {"url": "http://b", "fecha_postulacion": "2026-10-10", "sueldo_manual": "$1.300.000"})
    assert st == 200 and r["oferta"]["fecha_postulacion"] == "2026-10-10" and r["oferta"]["sueldo_manual"] == "$1.300.000"
    despues = fila(db, "http://b")
    assert despues["notas"] == "nota previa" and despues["sueldo"] == antes["sueldo"]   # no pisa el sueldo calculado
    assert {k: v for k, v in despues.items() if k not in ("fecha_postulacion", "sueldo_manual")} == \
        {k: v for k, v in antes.items() if k not in ("fecha_postulacion", "sueldo_manual")}


def test_nota_guarda_texto_con_html_tal_cual(srv):
    puerto, db = srv
    malicioso = '<img src=x onerror="alert(1)"><script>alert(2)</script> & "comillas" \'simples\''
    st, r = post(puerto, "/api/nota", {"url": "http://a", "notas": malicioso})
    assert st == 200 and r["oferta"]["notas"] == malicioso and fila(db, "http://a")["notas"] == malicioso
    d = json.loads(pedir(puerto, "GET", "/api/ofertas")[2])
    assert [o["notas"] for o in d["principal"] if o["url"] == "http://a"] == [malicioso]   # la página lo pinta con textContent


def test_limite_de_5000_caracteres_en_notas_y_100_en_sueldo(srv):
    puerto, db = srv
    assert post(puerto, "/api/nota", {"url": "http://a", "notas": "x" * 5000})[0] == 200
    assert post(puerto, "/api/nota", {"url": "http://a", "notas": "y" * 5001})[0] == 400
    assert fila(db, "http://a")["notas"] == "x" * 5000
    assert post(puerto, "/api/nota", {"url": "http://a", "sueldo_manual": "1" * 101})[0] == 400


@pytest.mark.parametrize("cambio", [
    {"fase": "cv"}, {"fase": "Final"}, {"prioridad_manual": "Urgente"}, {"fecha_postulacion": "2026-13-01"},
    {"fecha_postulacion": "ayer"}, {"notas": 5}, {"estado": "postulada"}, {"categoria": "principal"}, {},
])
def test_nota_rechaza_campos_o_valores_no_validos(srv, cambio):
    puerto, db = srv
    antes = fila(db, "http://a")
    assert post(puerto, "/api/nota", {"url": "http://a", **cambio})[0] == 400
    assert fila(db, "http://a") == antes


def test_marcar_acepta_todas_las_fases_y_nota_las_prioridades_y_borrar(srv):   # Fase C: la fase va por /api/marcar
    puerto, _ = srv
    for fase in buscar.FASES:
        assert post(puerto, "/api/marcar", {"url": "http://a", "estado": "entrevista", "fase": fase, "origen": "modal"})[0] == 200
    for p in ["", "Alta", "Media", "Baja"]:
        assert post(puerto, "/api/nota", {"url": "http://a", "prioridad_manual": p})[0] == 200
    assert post(puerto, "/api/nota", {"url": "http://a", "fecha_postulacion": ""})[0] == 200
    assert post(puerto, "/api/nota", {"url": "http://no-existe", "notas": "x"})[0] == 404


# ------------------------------------------------------------------ prioridad mostrada
def test_prioridad_mostrada_es_la_manual_si_existe(srv):
    puerto, _ = srv
    post(puerto, "/api/nota", {"url": "http://a", "prioridad_manual": "Alta"})
    d = {o["url"]: o for o in json.loads(pedir(puerto, "GET", "/api/ofertas")[2])["principal"]}
    assert (d["http://a"]["prioridad"], d["http://a"]["prioridad_calculada"], d["http://a"]["prioridad_manual"]) == ("Alta", "Media", "Alta")
    assert (d["http://b"]["prioridad"], d["http://b"]["prioridad_calculada"]) == ("Media", "Media")
    activas = [o["url"] for o in json.loads(pedir(puerto, "GET", "/api/ofertas")[2])["principal"] if o["estado"] == "nueva"]
    assert activas == ["http://a"]
    orden = [o["url"] for o in json.loads(pedir(puerto, "GET", "/api/ofertas")[2])["principal"]]
    assert orden.index("http://a") < orden.index("http://b")                 # la Alta manual se ordena primero


# ------------------------------------------------------------------ base ocupada
def test_base_ocupada_responde_503_y_no_escribe(srv, monkeypatch):
    puerto, db = srv
    monkeypatch.setattr(buscar, "BUSY_TIMEOUT_MS", 200)
    otra = sqlite3.connect(db, isolation_level=None)
    otra.execute("BEGIN IMMEDIATE")
    try:
        st, r = post(puerto, "/api/nota", {"url": "http://a", "notas": "no debe quedar"})
        st2, _ = post(puerto, "/api/marcar", {"url": "http://a", "estado": "postulada", "origen": "lista"})
    finally:
        otra.execute("ROLLBACK")
        otra.close()
    assert (st, r["error"], st2) == (503, "base ocupada, reintenta", 503)
    f = fila(db, "http://a")
    assert (f["notas"], f["estado"]) == ("nota previa", "nueva")
