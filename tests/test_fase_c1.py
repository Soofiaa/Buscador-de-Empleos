"""Fase C1 + historial de estados + ajuste (6): estado y fase atómicos en /api/marcar, historial solo de agregado (tabla
aditiva, la base sigue en v7), una sola función que escribe estado/fase/fecha, fecha editable no futura y en_fase_desde."""
import ast
import json
import re
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import servidor
import unir_bases
from test_servidor import df_de, pedir, puerto_libre
from test_unir_bases import base as base_unir

RAIZ = Path(__file__).resolve().parent.parent
HOY = "2026-10-13"
OBJETOS = set(buscar.DDL_HISTORIAL)


def objetos(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE name IN (%s)" % ", ".join("?" * len(OBJETOS)),
                                     list(OBJETOS))}


def historial(ruta, url=None):
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    filas = [dict(r) for r in con.execute("SELECT * FROM historial_estados " + ("WHERE url = ? " if url else "") +
                                          "ORDER BY id", (url,) if url else ())]
    con.close()
    return filas


def fila(ruta, url):
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    f = dict(con.execute("SELECT * FROM ofertas WHERE url = ?", (url,)).fetchone())
    con.close()
    return f


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(buscar, "ahora_chile", lambda: datetime(2026, 10, 13, 12, 0))
    reloj = iter(f"2026-10-13T15:{m:02d}:00+00:00" for m in range(60))
    monkeypatch.setattr(buscar, "ahora_utc", lambda: next(reloj))
    ruta = str(tmp_path / "t.db")
    con = buscar.conectar(ruta)
    for url, estado, fase, fecha in (("http://a", "nueva", "", ""), ("http://b", "revisada", "", ""),
                                     ("http://c", "entrevista", "rrhh", "2026-10-01")):
        con.execute("INSERT INTO ofertas (url, clave, titulo, empresa, categoria, prioridad, estado, fase, fecha_postulacion) "
                    "VALUES (?, ?, 'QA', 'Acme', 'principal', 'Media', ?, ?, ?)", (url, url, estado, fase, fecha))
    con.commit()
    con.close()
    return ruta


@pytest.fixture
def srv(db):
    httpd = servidor.crear_servidor(servidor.Aplicacion(db, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1], db
    httpd.shutdown()
    httpd.server_close()


def post(puerto, ruta, cuerpo):
    st, _, datos = pedir(puerto, "POST", ruta, cuerpo)
    return st, json.loads(datos or b"{}")


# ------------------------------------------------------------------ la tabla y sus triggers
def test_base_nueva_trae_los_6_objetos_y_sigue_en_v7(tmp_path):
    con = buscar.conectar(str(tmp_path / "n.db"))
    assert objetos(con) == OBJETOS and len(OBJETOS) == 6
    assert con.execute("PRAGMA user_version").fetchone()[0] == 7                 # opción 2: aditiva, sin v8


def test_un_trigger_o_el_indice_borrado_se_recrea_al_conectar(db):
    con = sqlite3.connect(db)
    con.execute("DROP TRIGGER ofertas_sin_borrar_con_historial")
    con.execute("DROP INDEX historial_por_oferta")
    con.commit()
    assert objetos(con) == OBJETOS - {"ofertas_sin_borrar_con_historial", "historial_por_oferta"}
    con.close()
    con = buscar.conectar(db)
    assert objetos(con) == OBJETOS
    assert buscar._asegurar_historial(con) == []                                 # ya no falta nada


def test_reconstruir_ofertas_se_lleva_sus_triggers_y_conectar_los_repone(db):
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE o2 AS SELECT * FROM ofertas")
    con.execute("DROP TABLE ofertas")
    con.execute("ALTER TABLE o2 RENAME TO ofertas")
    con.commit()
    assert not {"ofertas_url_fija_con_historial", "ofertas_sin_borrar_con_historial"} & objetos(con)
    con.close()
    assert objetos(buscar.conectar(db)) == OBJETOS


def test_conectar_con_todo_en_su_lugar_no_toma_el_turno_de_escritura(db, monkeypatch):
    monkeypatch.setattr(buscar, "BUSY_TIMEOUT_MS", 200)
    otra = sqlite3.connect(db, isolation_level=None)
    otra.execute("BEGIN IMMEDIATE")
    try:
        buscar.conectar(db).close()                                               # no lanza BaseOcupada
    finally:
        otra.execute("ROLLBACK")
        otra.close()


def test_el_historial_solo_agrega_y_protege_a_sus_ofertas(srv):
    puerto, db = srv
    post(puerto, "/api/marcar", {"url": "http://a", "estado": "revisada", "origen": "lista"})
    con = sqlite3.connect(db)
    for sql, motivo in (("UPDATE historial_estados SET origen = 'modal'", "solo se agregan"),
                        ("DELETE FROM historial_estados", "solo se agregan"),
                        ("UPDATE ofertas SET url = 'http://otra' WHERE url = 'http://a'", "su url no cambia"),
                        ("DELETE FROM ofertas WHERE url = 'http://a'", "no se borra")):
        with pytest.raises(sqlite3.DatabaseError, match=motivo):
            con.execute(sql)
    con.execute("DELETE FROM ofertas WHERE url = 'http://b'")                   # sin historial: los triggers no estorban
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO historial_estados (url, estado_antes, fase_antes, fecha_antes, estado_nuevo, fase_nueva, "
                    "fecha_nueva, cambiado_en, origen) VALUES ('x', '', '', '', '', '', '', '', 'inventado')")
    con.close()


def test_si_la_migracion_falla_no_se_crea_el_historial(tmp_path):
    ruta = str(tmp_path / "v6.db")
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT, estado TEXT, fase TEXT DEFAULT 'cv', notas TEXT, "
                "fecha_postulacion TEXT)")
    con.execute("INSERT INTO ofertas (url, clave, estado) VALUES ('a', 'a', 'nueva')")
    con.execute("PRAGMA user_version = 6")
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="no se migró nada"):
        buscar.conectar(ruta)
    assert objetos(sqlite3.connect(ruta)) == set()


# ------------------------------------------------------------------ C1: /api/marcar con fase y origen
def test_estado_y_fase_juntos_en_una_fila_de_historial(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/marcar", {"url": "http://b", "estado": "entrevista", "fase": "rrhh", "origen": "tablero"})
    assert st == 200
    assert r["anterior"] == {"estado": "revisada", "fase": "", "fecha_postulacion": ""}
    assert r["actual"] == {"estado": "entrevista", "fase": "rrhh", "fecha_postulacion": HOY}
    f = fila(db, "http://b")
    assert (f["estado"], f["fase"], f["fecha_postulacion"]) == ("entrevista", "rrhh", HOY)
    h, = historial(db, "http://b")
    assert {k: h[k] for k in ("estado_antes", "fase_antes", "fecha_antes", "estado_nuevo", "fase_nueva", "fecha_nueva", "origen")} == \
        {"estado_antes": "revisada", "fase_antes": "", "fecha_antes": "", "estado_nuevo": "entrevista", "fase_nueva": "rrhh",
         "fecha_nueva": HOY, "origen": "tablero"}
    assert h["cambiado_en"] == "2026-10-13T15:00:00+00:00"                        # UTC con desfase


def test_sin_fase_la_fase_no_cambia(srv):
    puerto, db = srv
    _, r = post(puerto, "/api/marcar", {"url": "http://c", "estado": "postulada", "origen": "lista"})
    assert r["actual"] == {"estado": "postulada", "fase": "rrhh", "fecha_postulacion": "2026-10-01"}


def test_deshacer_restaura_estado_fase_y_fecha_y_lo_registra_el_servidor(srv):
    puerto, db = srv
    _, r = post(puerto, "/api/marcar", {"url": "http://a", "estado": "entrevista", "fase": "tecnica", "origen": "modal"})
    st, _ = post(puerto, "/api/marcar", {"url": "http://a", "restaurar": {**r["anterior"], "si_actual": r["actual"]}})
    assert st == 200
    f = fila(db, "http://a")
    assert (f["estado"], f["fase"], f["fecha_postulacion"]) == ("nueva", "", "")
    assert [h["origen"] for h in historial(db, "http://a")] == ["modal", "deshacer"]


def test_deshacer_no_pisa_una_fase_cambiada_entre_medias(srv):
    puerto, db = srv
    _, r = post(puerto, "/api/marcar", {"url": "http://c", "estado": "entrevista", "fase": "tecnica", "origen": "tablero"})
    post(puerto, "/api/marcar", {"url": "http://c", "estado": "entrevista", "fase": "final", "origen": "modal"})
    st, _ = post(puerto, "/api/marcar", {"url": "http://c", "restaurar": {**r["anterior"], "si_actual": r["actual"]}})
    assert st == 409 and fila(db, "http://c")["fase"] == "final" and len(historial(db, "http://c")) == 2


def test_un_cambio_que_no_cambia_nada_no_escribe_historial(srv):
    puerto, db = srv
    st, _ = post(puerto, "/api/marcar", {"url": "http://c", "estado": "entrevista", "fase": "rrhh", "origen": "tablero"})
    assert st == 200 and historial(db) == []


@pytest.mark.parametrize("origen", [None, "manual", "deshacer", "Tablero", "otro", 5, ""])
def test_la_pagina_solo_puede_enviar_tablero_lista_o_modal(srv, origen):
    puerto, db = srv
    antes = fila(db, "http://a")
    cuerpo = {"url": "http://a", "estado": "revisada", **({} if origen is None else {"origen": origen})}
    assert post(puerto, "/api/marcar", cuerpo)[0] == 400
    assert fila(db, "http://a") == antes and historial(db) == []


def test_al_deshacer_la_pagina_no_puede_elegir_el_origen(srv):
    puerto, db = srv
    _, r = post(puerto, "/api/marcar", {"url": "http://a", "estado": "revisada", "origen": "lista"})
    deshacer = {"url": "http://a", "restaurar": {**r["anterior"], "si_actual": r["actual"]}}
    assert post(puerto, "/api/marcar", {**deshacer, "origen": "deshacer"})[0] == 400
    assert post(puerto, "/api/marcar", {**deshacer, "origen": "lista"})[0] == 200     # se registra 'deshacer' igual
    assert [h["origen"] for h in historial(db)] == ["lista", "deshacer"]


@pytest.mark.parametrize("cuerpo", [
    {"url": "http://a", "estado": "entrevista", "fase": "cv", "origen": "tablero"},
    {"url": "http://a", "estado": "entrevista", "fase": 3, "origen": "tablero"},
    {"url": "http://a", "restaurar": {"estado": "nueva", "fecha_postulacion": "", "fase": "Final",
                                      "si_actual": {"estado": "nueva", "fecha_postulacion": ""}}},
])
def test_fase_no_valida_es_400(srv, cuerpo):
    puerto, db = srv
    assert post(puerto, "/api/marcar", cuerpo)[0] == 400 and historial(db) == []


def test_si_falla_el_registro_no_cambia_el_estado(db, monkeypatch):
    def falla():
        raise RuntimeError("reloj roto")
    monkeypatch.setattr(buscar, "ahora_utc", falla)
    con = buscar.conectar(db)
    with pytest.raises(RuntimeError):
        buscar.marcar(con, "http://a", "postulada", origen="lista")
    con.close()
    assert (fila(db, "http://a")["estado"], historial(db)) == ("nueva", [])


def test_cambiar_seguimiento_exige_transaccion_y_origen_valido(db):
    con = buscar.conectar(db)
    nuevo = {"estado": "revisada", "fase": "", "fecha_postulacion": ""}
    with pytest.raises(RuntimeError):
        buscar._cambiar_seguimiento(con, "http://a", None, nuevo, "lista")
    with pytest.raises(ValueError):
        with buscar.transaccion(con):
            buscar._cambiar_seguimiento(con, "http://a", None, nuevo, "inventado")
    con.close()
    assert historial(db) == []


# ------------------------------------------------------------------ /api/nota y ajuste (6): fecha editable
@pytest.mark.parametrize("cambio", [{"fase": "rrhh"}, {"estado": "postulada"}, {"fase": "", "notas": "x"}])
def test_nota_ya_no_cambia_estado_ni_fase(srv, cambio):
    puerto, db = srv
    antes = fila(db, "http://c")
    st, r = post(puerto, "/api/nota", {"url": "http://c", **cambio})
    assert st == 400 and "/api/marcar" in r["error"] and fila(db, "http://c") == antes


def test_editar_la_fecha_queda_en_el_historial_como_modal(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/nota", {"url": "http://c", "fecha_postulacion": "2026-09-28", "notas": "corregida"})
    assert st == 200 and r["oferta"]["fecha_postulacion"] == "2026-09-28" and r["oferta"]["notas"] == "corregida"
    h, = historial(db, "http://c")
    assert (h["fecha_antes"], h["fecha_nueva"], h["estado_antes"], h["estado_nuevo"], h["origen"]) == \
        ("2026-10-01", "2026-09-28", "entrevista", "entrevista", "modal")


def test_fecha_futura_en_hora_de_chile_es_400(srv, monkeypatch):
    puerto, db = srv
    monkeypatch.setattr(buscar, "ahora_chile", lambda: datetime(2026, 10, 13, 23, 30))   # en UTC ya es 14-oct
    assert post(puerto, "/api/nota", {"url": "http://c", "fecha_postulacion": "2026-10-14"})[0] == 400
    assert post(puerto, "/api/nota", {"url": "http://c", "fecha_postulacion": "2026-10-13"})[0] == 200
    assert post(puerto, "/api/oferta/manual", {"titulo": "X", "empresa": "Y", "fecha_postulacion": "2026-12-01"})[0] == 400


def test_nota_sin_fecha_no_escribe_historial(srv):
    puerto, db = srv
    assert post(puerto, "/api/nota", {"url": "http://c", "notas": "solo notas", "prioridad_manual": "Alta"})[0] == 200
    assert historial(db) == []


def test_alta_manual_queda_en_el_historial_como_manual(srv):
    puerto, db = srv
    st, r = post(puerto, "/api/oferta/manual", {"titulo": "Tester", "empresa": "Banco", "fase": "rrhh", "estado": "entrevista"})
    assert st == 201 and (r["oferta"]["estado"], r["oferta"]["fase"], r["oferta"]["fecha_postulacion"]) == ("entrevista", "rrhh", HOY)
    h, = historial(db, r["oferta"]["url"])
    assert (h["estado_antes"], h["fase_antes"], h["fecha_antes"], h["estado_nuevo"], h["fase_nueva"], h["origen"]) == \
        ("", "", "", "entrevista", "rrhh", "manual")


# ------------------------------------------------------------------ en_fase_desde (días en la fase)
def h(i, ea, fa, da, en, fn, dn, origen="tablero", cuando=None):
    return {"id": i, "estado_antes": ea, "fase_antes": fa, "fecha_antes": da, "estado_nuevo": en, "fase_nueva": fn,
            "fecha_nueva": dn, "origen": origen, "cambiado_en": cuando or f"T{i}"}


def test_en_fase_desde_sin_historial_es_none():
    assert buscar.en_fase_desde([], "postulada", "") is None


def test_en_fase_desde_cuenta_desde_el_ultimo_cambio_de_estado_o_fase():
    filas = [h(1, "revisada", "", "", "postulada", "postulacion", "2026-10-01"),
             h(2, "postulada", "postulacion", "2026-10-01", "entrevista", "rrhh", "2026-10-01")]
    assert buscar.en_fase_desde(filas, "entrevista", "rrhh") == "T2"


def test_editar_solo_la_fecha_no_reinicia_el_contador():
    filas = [h(1, "revisada", "", "", "postulada", "postulacion", "2026-10-05"),
             h(2, "postulada", "postulacion", "2026-10-05", "postulada", "postulacion", "2026-10-01", "modal")]
    assert buscar.en_fase_desde(filas, "postulada", "postulacion") == "T1"


def test_deshacer_devuelve_el_contador_a_su_valor_anterior():
    filas = [h(1, "revisada", "", "", "postulada", "postulacion", "2026-10-01"),
             h(2, "postulada", "postulacion", "2026-10-01", "entrevista", "rrhh", "2026-10-01"),
             h(3, "entrevista", "rrhh", "2026-10-01", "postulada", "postulacion", "2026-10-01", "deshacer")]
    assert buscar.en_fase_desde(filas, "postulada", "postulacion") == "T1"


def test_un_deshacer_que_no_revierte_el_ultimo_cambio_no_anula_nada():
    filas = [h(1, "revisada", "", "", "postulada", "", "2026-10-01"),
             h(2, "postulada", "", "2026-10-01", "nueva", "", "", "deshacer")]    # no vuelve a 'revisada': no es su reverso
    assert buscar.en_fase_desde(filas, "nueva", "") == "T2"


def test_un_hueco_del_codigo_anterior_no_inventa_dias():
    filas = [h(1, "revisada", "", "", "postulada", "postulacion", "2026-10-01")]   # luego v7 la pasó a entrevista
    assert buscar.en_fase_desde(filas, "entrevista", "rrhh") is None


def test_el_orden_es_por_id_no_por_la_hora_en_texto():
    # cambio de horario: la hora del segundo cambio "parece" anterior, pero el id manda
    filas = [h(2, "postulada", "", "2026-10-01", "entrevista", "rrhh", "2026-10-01", cuando="2026-04-05T02:30:00+00:00"),
             h(1, "revisada", "", "", "postulada", "", "2026-10-01", cuando="2026-04-05T03:10:00+00:00")]
    assert buscar.en_fase_desde(filas, "entrevista", "rrhh") == "2026-04-05T02:30:00+00:00"


def test_api_ofertas_trae_en_fase_desde(srv):
    puerto, _ = srv
    post(puerto, "/api/marcar", {"url": "http://b", "estado": "postulada", "fase": "postulacion", "origen": "tablero"})
    d = {o["url"]: o for o in json.loads(pedir(puerto, "GET", "/api/ofertas")[2])["principal"]}
    assert d["http://b"]["en_fase_desde"] == "2026-10-13T15:00:00+00:00" and d["http://c"]["en_fase_desde"] is None


# ------------------------------------------------------------------ una sola función escribe estado, fase y fecha
ESCRITOR = ("buscar.py", "_cambiar_seguimiento")
EXENTOS = {("unir_bases.py", "unir")}            # herramienta de una vez; se niega a correr si hay historial
DINAMICOS = {                                    # UPDATE/INSERT con columnas armadas en el código: (archivo, función) -> constante
    ("buscar.py", "reclasificar"): "CAMPOS_CLASIF",
    ("buscar.py", "reclasificar_dirigida.calcular"): "CAMPOS_CLASIF",
    ("buscar.py", "actualizar_seguimiento"): "COLUMNAS_NOTA_LIBRES",
    ("buscar.py", "crear_oferta_manual"): None,    # el dict 'fila': lo comprueba un assert en el código y la traza de abajo
}
SQL_NO_LITERAL = {
    ("buscar.py", "_asegurar_historial"),        # ejecuta DDL_HISTORIAL[nombre] (solo CREATE ... IF NOT EXISTS)
    ("buscar.py", "transaccion.__exit__"),       # 'COMMIT' if ... else 'ROLLBACK'
    ("buscar.py", "ofertas_para_pagina.filas"),  # ayudante de lectura: su SQL se revisa donde se llama a filas(...)
}
AYUDANTES_SQL = {"filas"}                        # llamadas cuyo primer argumento es SQL y también se revisa
BORRADO_PERMITIDO = {("buscar.py", "_migrar_v2"), ("buscar.py", "_migrar_v4")}   # bases < v5, antes de que exista historial
COLS = r"\b(ESTADO|FASE|FECHA_POSTULACION)\b"


def _texto(n, raiz=True):
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value, False
    if isinstance(n, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in n.values), True
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        (a, da), (b, db_) = _texto(n.left, False), _texto(n.right, False)
        return (None, True) if a is None or b is None else (a + b, True)
    return ("{}", True) if not raiz else (None, True)


def sentencias(fuente):
    """[(función, sql normalizado o None si no es literal, línea, código)] de cada execute/executemany/executescript."""
    out, pila = [], []

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, n):
            pila.append(n.name); self.generic_visit(n); pila.pop()
        visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef

        def visit_Call(self, n):
            es_sql = isinstance(n.func, ast.Attribute) and n.func.attr in ("execute", "executemany", "executescript")
            if (es_sql or isinstance(n.func, ast.Name) and n.func.id in AYUDANTES_SQL) and n.args:
                t, _ = _texto(n.args[0])
                out.append((".".join(pila) or "<módulo>", t and " ".join(t.upper().split()), n.lineno, ast.unparse(n.args[0])))
            self.generic_visit(n)
    V().visit(ast.parse(fuente))
    return out


def infracciones(archivo, fuente):
    for fn, sql, linea, codigo in sentencias(fuente):
        lugar, donde = (archivo, fn), f"{archivo}:{linea} ({fn})"
        if sql is None:
            if lugar not in SQL_NO_LITERAL:
                yield f"{donde}: SQL que no es texto literal, no se puede revisar: {codigo}"
            continue
        if re.search(r"\b(UPDATE|DELETE FROM|INTO)\s+HISTORIAL_ESTADOS\b", sql) and lugar != ESCRITOR:
            yield f"{donde}: escribe en historial_estados fuera de _cambiar_seguimiento"
        m = re.search(r"\bUPDATE\s+OFERTAS\s+SET\b(.*?)(\bWHERE\b|$)", sql)
        if m:
            if re.search(COLS + r"\s*=", m.group(1)) and lugar != ESCRITOR and lugar not in EXENTOS:
                yield f"{donde}: UPDATE de estado/fase/fecha fuera de _cambiar_seguimiento"
            if "{}" in m.group(1) and lugar not in DINAMICOS:
                yield f"{donde}: UPDATE con columnas dinámicas no revisadas"
            if re.search(r"\bURL\s*=", m.group(1)) and lugar not in BORRADO_PERMITIDO:
                yield f"{donde}: cambia la url de una oferta"
        m = re.search(r"\bINTO\s+OFERTAS\s*\((.*?)\)", sql)
        if m:
            if re.search(COLS, m.group(1)):
                yield f"{donde}: INSERT con estado/fase/fecha fuera de _cambiar_seguimiento"
            if "{}" in m.group(1) and lugar not in DINAMICOS:
                yield f"{donde}: INSERT con columnas dinámicas no revisadas"
        elif re.search(r"\bINTO\s+OFERTAS\b", sql):
            yield f"{donde}: INSERT en ofertas sin lista de columnas"
        if re.search(r"\bDELETE\s+FROM\s+OFERTAS\b", sql) and lugar not in BORRADO_PERMITIDO:
            yield f"{donde}: borra ofertas"


def test_solo_cambiar_seguimiento_escribe_estado_fase_y_fecha():
    archivos = sorted(RAIZ.glob("*.py"))
    assert {"buscar.py", "servidor.py", "unir_bases.py"} <= {a.name for a in archivos}
    malas = [i for a in archivos for i in infracciones(a.name, a.read_text(encoding="utf-8"))]
    assert malas == [], "\n".join(malas)
    vistos = {(a.name, fn) for a in archivos for fn, *_ in sentencias(a.read_text(encoding="utf-8"))}
    assert {ESCRITOR, *EXENTOS, *DINAMICOS, *SQL_NO_LITERAL, *BORRADO_PERMITIDO} <= vistos   # las listas no quedan viejas


def test_las_constantes_de_columnas_dinamicas_no_tocan_estado_fase_ni_fecha():
    for constante in {c for c in DINAMICOS.values() if c}:
        assert not set(getattr(buscar, constante)) & set(buscar.CAMPOS_HISTORIAL), constante


@pytest.mark.parametrize("malo, motivo", [
    ('def f(con):\n    con.execute("UPDATE ofertas SET fase = ? WHERE url = ?", (1, 2))', "fuera de _cambiar_seguimiento"),
    ('def f(con, c):\n    con.execute(f"UPDATE ofertas SET {c} = ? WHERE url = ?", (1, 2))', "dinámicas"),
    ('def f(con):\n    con.execute("INSERT INTO ofertas (url, estado) VALUES (?, ?)", (1, 2))', "INSERT con estado"),
    ('def f(con, sql):\n    con.execute(sql)', "no es texto literal"),
    ('def f(con):\n    con.execute("DELETE FROM ofertas WHERE url = ?", (1,))', "borra ofertas"),
    ('def f(con):\n    con.execute("UPDATE ofertas SET url = ? WHERE url = ?", (1, 2))', "cambia la url"),
    ('def f(con):\n    con.execute("INSERT INTO historial_estados (url) VALUES (?)", (1,))', "historial_estados"),
])
def test_el_escaner_detecta_lo_que_debe(malo, motivo):
    assert any(motivo in i for i in infracciones("otro.py", malo))


def test_traza_cada_cambio_de_estado_fase_o_fecha_lleva_su_fila_de_historial(tmp_path, monkeypatch):
    monkeypatch.setattr(buscar, "ahora_chile", lambda: datetime(2026, 10, 13, 12, 0))
    db = str(tmp_path / "traza.db")
    con = buscar.conectar(db)
    ofertas = df_de({"job_url": "http://a", "title": "QA Tester", "company": "Acme"},
                    {"job_url": "http://b", "title": "Analista de Soporte TI", "company": "Beta"},
                    {"job_url": "http://c", "title": "Analista QA", "company": "Gama"})
    assert buscar.guardar(con, buscar.procesar(ofertas, "t")) == 3                 # la búsqueda: sin estado/fase/fecha
    buscar.marcar(con, "http://c", "postulada", origen="lista")
    sentencias_vistas = []
    con.set_trace_callback(sentencias_vistas.append)
    buscar.marcar(con, "http://a", "postulada", fase="postulacion", origen="tablero")
    r = buscar.marcar(con, "http://b", "entrevista", origen="lista")
    buscar.marcar(con, "http://b", restaurar={**r["anterior"], "si_actual": r["actual"]})
    buscar.actualizar_seguimiento(con, "http://c", {"fecha_postulacion": "2026-09-30", "notas": "n"})
    buscar.crear_oferta_manual(con, {"titulo": "Manual", "empresa": "M", "estado": "postulada"})
    buscar.reclasificar(con)
    buscar.reclasificar_dirigida(con)
    con.close()
    pendiente, cambios = False, 0
    for s in (" ".join(x.upper().split()) for x in sentencias_vistas):
        assert not re.search(r"\bINTO OFERTAS\s*\([^)]*" + COLS, s), s
        m = re.match(r"UPDATE OFERTAS SET (.*?) WHERE", s)
        if m and re.search(COLS + r" =", m.group(1)):
            assert not pendiente, "dos cambios seguidos sin su fila de historial"
            pendiente, cambios = True, cambios + 1
        elif s.startswith("INSERT INTO HISTORIAL_ESTADOS"):
            assert pendiente, "fila de historial sin cambio"
            pendiente = False
        elif s in ("COMMIT", "ROLLBACK"):
            assert not pendiente, "la transacción terminó con un cambio sin historial"
    assert cambios == 5 and len(historial(db)) == 6     # + el 'postulada' de c, hecho antes de empezar la traza


# ------------------------------------------------------------------ unir_bases: exento, pero no sobre una base con historial
def test_unir_se_niega_si_la_base_principal_tiene_historial(tmp_path):
    principal = base_unir(tmp_path / "vjt.db", [("u1", "nueva", {})], columnas_node=True)
    otra = base_unir(tmp_path / "node.db", [("u1", "postulada", {"fecha_postulacion": "2026-10-12"})], columnas_node=True)
    con = buscar.conectar(principal)
    buscar.marcar(con, "u1", "revisada", origen="lista")
    con.close()
    salida = tmp_path / "unida.db"
    with pytest.raises(unir_bases.ErrorUnion, match="historial"):
        unir_bases.unir(("VJT", principal), [("NODE", otra)], {}, salida, HOY)
    assert not salida.exists() and not Path(str(salida) + ".tmp").exists()


def test_unir_sigue_funcionando_con_el_historial_vacio(tmp_path):
    principal = base_unir(tmp_path / "vjt.db", [("u1", "nueva", {})], columnas_node=True)
    otra = base_unir(tmp_path / "node.db", [("u1", "postulada", {"fecha_postulacion": "2026-10-12"})], columnas_node=True)
    unir_bases.unir(("VJT", principal), [("NODE", otra)], {}, tmp_path / "unida.db", HOY)
    assert fila(str(tmp_path / "unida.db"), "u1")["estado"] == "postulada"


# ------------------------------------------------------------------ la página: estado y fase solo por /api/marcar, con origen
from test_historial import PAGINA, correr_js


def test_pagina_arma_los_pedidos_a_marcar_con_su_origen():
    r = correr_js("""
      const o = {url: "http://x"};
      const malos = ["manual", "deshacer", "", undefined].map(v => { try { pedidoMarcar(o, "revisada", undefined, v); return "pasó"; } catch (e) { return "error"; } });
      const cambio = {anterior: {estado: "revisada", fase: "", fecha_postulacion: ""}, actual: {estado: "entrevista", fase: "rrhh", fecha_postulacion: "2026-10-13"}};
      return {sinFase: pedidoMarcar(o, "postulada", undefined, "lista"), conFase: pedidoMarcar(o, "entrevista", "", "modal"),
              malos, deshacer: pedidoDeshacer(o, cambio), campos: CAMPOS_NOTA,
              fechas: [["", "2026-10-13"], ["2026-10-13", "2026-10-13"], ["2026-10-14", "2026-10-13"]].map(([v, h]) => fechaNoFutura(v, h))};""")
    assert r["sinFase"] == {"url": "http://x", "estado": "postulada", "origen": "lista"}           # sin fase: no la toca
    assert r["conFase"] == {"url": "http://x", "estado": "entrevista", "origen": "modal", "fase": ""}
    assert r["malos"] == ["error"] * 4
    assert r["deshacer"] == {"url": "http://x", "restaurar": {"estado": "revisada", "fase": "", "fecha_postulacion": "",
                                                            "si_actual": {"estado": "entrevista", "fase": "rrhh", "fecha_postulacion": "2026-10-13"}}}
    assert "fase" not in r["campos"] and r["fechas"] == [True, True, False]


def test_pagina_todo_pedido_a_marcar_pasa_por_pedido_marcar_o_pedido_deshacer():
    script = PAGINA.split("<script>")[1]
    llamadas = re.findall(r'api\("/api/marcar",\s*([^)]*\))', script)
    assert llamadas and all(c.startswith(("pedidoMarcar(", "pedidoDeshacer(")) for c in llamadas), llamadas
    assert 'api("/api/nota"' in script and "guardarNota" not in script                  # la fase ya no va por /api/nota
    assert re.findall(r'cambiarEstado\(o, [^,)]+\)', script) == []                         # toda llamada lleva su origen
    assert 'id: "detalle-fecha", max: hoy()' in script and 'id: "manual-fecha", max: hoy()' in script
