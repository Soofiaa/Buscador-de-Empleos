"""Fase B1: postulación manual (/api/oferta/manual), exportar (/api/exportar) y límite de cuerpo por ruta."""
import csv
import io
import json
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import servidor
from test_servidor import df_de, pedir, puerto_libre

HOY = "2026-10-13"


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(buscar, "ahora_chile", lambda: datetime(2026, 10, 13, 12, 0))
    ruta = str(tmp_path / "t.db")
    con = buscar.conectar(ruta)
    buscar.guardar(con, buscar.procesar(df_de({"job_url": "http://qa", "title": "QA Tester", "company": "Acme", "is_remote": True}), "t"))
    con.close()
    httpd = servidor.crear_servidor(servidor.Aplicacion(ruta, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1], ruta
    httpd.shutdown()
    httpd.server_close()


def post(puerto, ruta, cuerpo, cab=None):
    st, _, datos = pedir(puerto, "POST", ruta, cuerpo, cab)
    return st, json.loads(datos or b"{}")


def filas(ruta):
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    r = {f["url"]: dict(f) for f in con.execute("SELECT * FROM ofertas")}
    con.close()
    return r


MANUAL = {"titulo": "Analista QA", "empresa": "Banco Ejemplo", "ubicacion": "Santiago", "url": "https://empleos.ejemplo.cl/123"}


# ------------------------------------------------------------------ postulación manual
def test_manual_se_crea_como_principal_con_fecha_de_hoy(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/oferta/manual", {**MANUAL, "prioridad_manual": "Alta", "notas": "me contactó RRHH"})
    assert st == 201 and r["oferta"]["url"] == MANUAL["url"]
    f = filas(db)[MANUAL["url"]]
    assert (f["categoria"], f["tipo"], f["fuente"], f["estado"], f["fecha_postulacion"], f["prioridad_manual"]) == \
        ("principal", "M: Manual", "manual", "postulada", HOY, "Alta")
    assert r["oferta"]["prioridad"] == "Alta" and "raw" not in r["oferta"]
    assert MANUAL["url"] in [o["url"] for o in json.loads(pedir(puerto, "GET", "/api/ofertas")[2])["principal"]]


def test_manual_sin_url_usa_clave_sintetica_unica(srv):
    puerto, db = srv
    _, r1 = post(puerto, "/api/oferta/manual", {"titulo": "Tester", "empresa": "Uno", "estado": "nueva"})
    _, r2 = post(puerto, "/api/oferta/manual", {"titulo": "Tester", "empresa": "Dos", "estado": "nueva"})
    u1, u2 = r1["oferta"]["url"], r2["oferta"]["url"]
    assert u1.startswith("manual:") and u2.startswith("manual:") and u1 != u2
    assert filas(db)[u1]["fecha_postulacion"] == ""                     # "nueva": no se inventa fecha


@pytest.mark.parametrize("repetida", [
    {**MANUAL},                                                          # misma URL
    {**MANUAL, "url": "https://otro-portal.cl/999"},                     # misma oferta, otra URL
    {**MANUAL, "url": ""},                                               # misma oferta, sin URL
    {"titulo": "QA Tester", "empresa": "Acme", "ubicacion": "Santiago"},  # una que trajo la búsqueda
])
def test_manual_duplicada_es_409_y_no_crea_nada(srv, repetida):
    puerto, db = srv
    post(puerto, "/api/oferta/manual", MANUAL)
    antes = filas(db)
    st, r = post(puerto, "/api/oferta/manual", repetida)
    assert st == 409 and r["url_existente"] in antes
    assert filas(db) == antes


def test_el_aviso_de_duplicada_no_mete_null_en_el_dom():
    # replaceChildren(null) crea un nodo de texto "null": el botón "Ver la existente" solo se añade si hay existente
    pagina = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")
    linea = next(l for l in pagina.splitlines() if "error.replaceChildren(mensajeManual" in l)
    assert "null" not in linea
    assert "if (existente) error.append(" in pagina


@pytest.mark.parametrize("malo", [
    {"empresa": "X"}, {"titulo": "X"}, {"titulo": "   ", "empresa": "X"},
    {**MANUAL, "url": "javascript:alert(1)"}, {**MANUAL, "url": "ftp://x.cl"}, {**MANUAL, "url": "https://"},
    {**MANUAL, "url": 'https://x.cl/"><script>'}, {**MANUAL, "titulo": "x" * 201}, {**MANUAL, "estado": "inventado"},
    {**MANUAL, "fase": "cv"}, {**MANUAL, "modalidad": "Teletrabajo"}, {**MANUAL, "prioridad_manual": "Urgente"},
    {**MANUAL, "fecha_postulacion": "2026-02-30"}, {**MANUAL, "categoria": "principal"}, {**MANUAL, "notas": 5},
])
def test_manual_invalida_es_400(srv, malo):
    puerto, db = srv
    antes = filas(db)
    assert post(puerto, "/api/oferta/manual", malo)[0] == 400
    assert filas(db) == antes


def test_mismo_cargo_y_empresa_sin_ciudad_pide_confirmar_y_trae_la_existente(srv):
    puerto, db = srv                     # la de la búsqueda es «Santiago»; la nueva no trae ciudad
    antes = filas(db)
    st, r = post(puerto, "/api/oferta/manual", {"titulo": "QA Tester", "empresa": "Acme", "estado": "nueva"})
    assert st == 409 and r["confirmable"] is True and r["url_existente"] == "http://qa"
    assert r["existente"]["url"] == "http://qa" and r["existente"]["titulo"] == "QA Tester"
    assert "raw" not in r["existente"] and "clave" not in r["existente"]
    assert filas(db) == antes


def test_guardar_de_todas_formas_crea_una_fila_aparte(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/oferta/manual", {"titulo": "QA Tester", "empresa": "Acme", "ubicacion": "Valparaíso",
                                                "confirmar_duplicada": True})
    assert st == 201 and r["oferta"]["url"].startswith("manual:")
    assert len(filas(db)) == 2 and filas(db)["http://qa"]["estado"] == "nueva"


def test_confirmar_no_salta_la_misma_url(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/oferta/manual", {"titulo": "QA Tester", "empresa": "Acme", "url": "http://qa",
                                                "confirmar_duplicada": True})
    assert st == 409 and "confirmable" not in r and r["url_existente"] == "http://qa"
    assert len(filas(db)) == 1


def test_confirmar_debe_ser_booleano_y_no_llega_a_la_base(srv):
    puerto, db = srv
    assert post(puerto, "/api/oferta/manual", {"titulo": "X", "empresa": "Y", "confirmar_duplicada": "si"})[0] == 201
    assert "confirmar_duplicada" not in filas(db)[next(u for u in filas(db) if u.startswith("manual:") and filas(db)[u]["titulo"] == "X")]["raw"]


def test_manual_sobre_una_descartada_la_revive_sin_duplicar(srv):
    puerto, db = srv
    post(puerto, "/api/oferta/manual", MANUAL)
    assert post(puerto, "/api/marcar", {"url": MANUAL["url"], "estado": "descartada", "origen": "lista"})[0] == 200
    st, r = post(puerto, "/api/oferta/manual", {**MANUAL, "notas": "volví a postular"})
    assert st == 200 and r["actualizada"] is True and "actualizada" not in r["oferta"]
    f = filas(db)[MANUAL["url"]]
    assert (f["estado"], f["categoria"], f["notas"]) == ("postulada", "principal", "volví a postular")
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 2          # la de la búsqueda + esta, sin duplicar
    origenes = [x[0] for x in con.execute("SELECT origen FROM historial_estados WHERE url = ? ORDER BY id", (MANUAL["url"],))]
    con.close()
    assert origenes[-1] == "manual"


def test_manual_sobre_una_descartada_de_la_busqueda_revive_esa_fila(srv):
    puerto, db = srv
    assert post(puerto, "/api/marcar", {"url": "http://qa", "estado": "descartada", "origen": "lista"})[0] == 200
    st, r = post(puerto, "/api/oferta/manual", {"titulo": "QA Tester", "empresa": "Acme", "ubicacion": "Santiago"})
    assert st == 200 and r["oferta"]["url"] == "http://qa" and r["actualizada"] is True
    assert len(filas(db)) == 1 and filas(db)["http://qa"]["estado"] == "postulada"


def test_manual_sobre_una_descartada_no_la_revive_si_el_formulario_la_descarta(srv):
    puerto, db = srv
    post(puerto, "/api/oferta/manual", MANUAL)
    post(puerto, "/api/marcar", {"url": MANUAL["url"], "estado": "descartada", "origen": "lista"})
    antes = filas(db)
    assert post(puerto, "/api/oferta/manual", {**MANUAL, "estado": "descartada"})[0] == 409
    assert filas(db) == antes


def test_manual_guarda_texto_con_html_tal_cual(srv):
    puerto, db = srv
    raro = '<img src=x onerror="alert(1)"> & "comillas"'
    st, r = post(puerto, "/api/oferta/manual", {"titulo": raro, "empresa": "E", "notas": raro})
    assert st == 201 and filas(db)[r["oferta"]["url"]]["titulo"] == raro


def test_manual_rechaza_origen_ajeno(srv):
    puerto, db = srv
    antes = filas(db)
    assert post(puerto, "/api/oferta/manual", MANUAL, {"Origin": "https://evil.example.com"})[0] == 403
    assert filas(db) == antes


def test_manual_base_ocupada_es_503(srv, monkeypatch):
    puerto, db = srv
    monkeypatch.setattr(buscar, "BUSY_TIMEOUT_MS", 200)
    otra = sqlite3.connect(db, isolation_level=None)
    otra.execute("BEGIN IMMEDIATE")
    try:
        assert post(puerto, "/api/oferta/manual", MANUAL)[0] == 503
    finally:
        otra.execute("ROLLBACK")
        otra.close()
    assert MANUAL["url"] not in filas(db)


# ------------------------------------------------------------------ la búsqueda no toca lo manual
def test_una_busqueda_no_duplica_ni_modifica_lo_manual(srv):
    puerto, db = srv
    post(puerto, "/api/oferta/manual", {**MANUAL, "notas": "mía"})
    con = buscar.conectar(db)
    misma_otra_url = df_de({"job_url": "https://cl.indeed.com/viewjob?jk=nuevo", "title": "Analista QA", "company": "Banco Ejemplo",
                            "location": "Santiago, RM, Chile"})
    assert buscar.guardar(con, buscar.procesar(misma_otra_url, "t")) == 0      # _duplicada la reconoce
    antes = filas(db)
    buscar.reclasificar(con)
    for regla in buscar.SELECCIONES_DIRIGIDAS.values():
        buscar.reclasificar_dirigida(con, seleccion=regla)
    con.close()
    despues = filas(db)
    assert len(despues) == 2 and despues[MANUAL["url"]] == antes[MANUAL["url"]]   # ni otra fila ni cambios


# ------------------------------------------------------------------ exportar
def leer_csv(cuerpo: bytes):
    texto = cuerpo.decode("utf-8")
    assert texto.startswith("﻿")
    return list(csv.reader(io.StringIO(texto[1:]), delimiter=";"))


def test_csv_protege_formulas_y_es_descarga(srv):
    puerto, db = srv
    for titulo in ("=HYPERLINK(\"http://x\")", "+1+1", "-2", "@SUM(A1)"):
        post(puerto, "/api/oferta/manual", {"titulo": titulo, "empresa": "E" + str(len(titulo)), "estado": "postulada"})
    base = buscar.conectar(db)                           # tab y CR al inicio: el formulario los recorta, una búsqueda no
    for i, titulo in enumerate(("\tcon tab", "\rcon cr")):
        base.execute("INSERT INTO ofertas (url, clave, titulo, categoria, estado, raw) VALUES (?, ?, ?, 'principal', 'nueva', '{}')",
                     (f"http://raro{i}", f"kr{i}", titulo))
    base.commit()
    base.close()
    import http.client
    con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
    con.request("GET", "/api/exportar?formato=csv&alcance=todas")
    r = con.getresponse()
    cuerpo = r.read()
    assert r.status == 200 and r.getheader("Content-Type").startswith("text/csv")
    assert r.getheader("Content-Disposition").startswith('attachment; filename="ofertas_todas_')
    tabla = leer_csv(cuerpo)
    assert tabla[0] == buscar.COLUMNAS_EXPORTAR and "raw" not in tabla[0] and "clave" not in tabla[0]
    titulos = {fila[0] for fila in tabla[1:]}
    assert {"'=HYPERLINK(\"http://x\")", "'+1+1", "'-2", "'@SUM(A1)", "'\tcon tab", "'\rcon cr"} <= titulos
    assert not any(t[:1] in "=+-@\t\r" for t in titulos)


def test_json_exporta_columnas_cerradas_sin_raw(srv):
    puerto, _ = srv
    post(puerto, "/api/oferta/manual", MANUAL)
    st, tipo, cuerpo = pedir(puerto, "GET", "/api/exportar?formato=json&alcance=todas")
    d = json.loads(cuerpo)
    assert st == 200 and tipo.startswith("application/json") and d["formato"] == "job-tracker" and d["version"] == 1
    assert d["total"] == 2 and all(set(o) == set(buscar.COLUMNAS_EXPORTAR) for o in d["ofertas"])
    assert not any(k in o for o in d["ofertas"] for k in ("raw", "clave", "clave_base", "busqueda"))


def test_alcances_de_exportar(srv):
    puerto, db = srv
    post(puerto, "/api/oferta/manual", {**MANUAL, "estado": "entrevista"})
    con = buscar.conectar(db)
    con.execute("INSERT INTO ofertas (url, clave, titulo, categoria, estado, raw) VALUES ('http://d', 'kd', 'Desc', 'descartada', 'nueva', '{}')")
    con.commit()
    con.close()
    total = {a: json.loads(pedir(puerto, "GET", f"/api/exportar?formato=json&alcance={a}")[2])["total"] for a in ("seguimiento", "principal", "todas")}
    assert total == {"seguimiento": 1, "principal": 2, "todas": 3}


@pytest.mark.parametrize("consulta", ["formato=xlsx&alcance=todas", "formato=csv&alcance=raw", "formato=csv&alcance=todas;drop"])
def test_exportar_parametros_invalidos_es_400(srv, consulta):
    puerto, _ = srv
    assert pedir(puerto, "GET", "/api/exportar?" + consulta)[0] == 400


def test_exportar_respeta_host_y_origen(srv):
    puerto, _ = srv
    for cab in ({"Host": "evil.example.com"}, {"Origin": "https://evil.example.com"}):
        assert pedir(puerto, "GET", "/api/exportar?formato=csv&alcance=todas", None, cab)[0] == 403


# ------------------------------------------------------------------ límite de cuerpo por ruta
def test_notas_de_5000_caracteres_con_tildes_caben(srv):
    puerto, db = srv
    notas = "á" * 2500 + "😀" * 2500                                     # 5000 caracteres, ~15 KB en UTF-8
    assert len(json.dumps({"url": "http://qa", "notas": notas}, ensure_ascii=False).encode()) > servidor.LIMITE_CUERPO
    st, _ = post(puerto, "/api/nota", {"url": "http://qa", "notas": notas})
    assert st == 200 and filas(db)["http://qa"]["notas"] == notas


def test_cuerpo_demasiado_grande_es_413_y_no_escribe(srv):
    puerto, db = srv
    antes = filas(db)
    assert post(puerto, "/api/nota", {"url": "http://qa", "notas": "x" * 70_000})[0] == 413
    assert post(puerto, "/api/marcar", {"url": "http://qa", "estado": "revisada", "relleno": "x" * 12_000})[0] == 413   # 10 KB aquí
    assert filas(db) == antes
