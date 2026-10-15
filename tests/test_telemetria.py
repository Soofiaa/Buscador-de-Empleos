"""Telemetría pasiva de las corridas: solo contadores por fuente en corridas.detalle, sin cambiar el comportamiento."""
import json
import socket
import sys
import types
import urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest
import requests

import bne
import buscar
import config
import getonboard
import robots as robots_mod
import telemetria
from filtros import ZONA
from red import ClienteHTTP
from robots import GestorRobots
from test_filtros import AHORA, df_de
from test_portales import RobotsLibre, leer


class Ctx:
    def __init__(self, texto):
        self.status, self._cuerpo = 200, texto.encode("utf-8")
        self.headers = type("H", (), {"get_content_charset": lambda s: "utf-8"})()
    def read(self): return self._cuerpo
    def __enter__(self): return self
    def __exit__(self, *a): return False


def cliente(respuestas, dormidas=None):
    """ClienteHTTP real con una red falsa: {trozo_de_url: (status, texto) | "timeout"}; lo demás responde 404."""
    pedidas = []

    def abrir(req, timeout):
        pedidas.append(req.full_url)
        for trozo, r in respuestas.items():
            if trozo in req.full_url:
                if r == "timeout":
                    raise socket.timeout("timed out")
                status, texto = r
                if status != 200:
                    raise urllib.error.HTTPError(req.full_url, status, "x", {}, None)
                return Ctx(texto)
        raise urllib.error.HTTPError(req.full_url, 404, "x", {}, None)
    c = ClienteHTTP(dormir=(dormidas.append if dormidas is not None else lambda s: None), azar=lambda a, b: 4.0,
                    abrir=abrir)
    return c, pedidas


def con_telemetria(c):
    t = telemetria.contador("http")
    c.al_responder = lambda status: telemetria.anotar_status(t, status)
    return t


def st_vacio():
    return {"encontradas": 0, "antiguas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0}


@pytest.fixture
def con(tmp_path):
    return buscar.conectar(str(tmp_path / "t.db"))


# ---- portales: 429, 403, 404, timeout y listado vacío
@pytest.mark.parametrize("status", [429, 403])
def test_bloqueo_se_cuenta_y_el_sitio_se_detiene_igual(con, monkeypatch, status):
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643", "tester"])
    c, pedidas = cliente({"bne.gob.cl": (status, "")})
    t = con_telemetria(c)
    avisos = []
    buscar._buscar_portal(con, "bne", st_vacio(), avisos, c, RobotsLibre(), tele=t)
    assert len(pedidas) == 1 and any("se detuvo" in a for a in avisos)        # igual que sin telemetría
    assert t["solicitudes"] == 1 and t["codigos"][str(status)] == 1


def test_404_se_cuenta(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_TRABAJANDO", ["desarrollador-junior"])
    c, pedidas = cliente({})
    t = con_telemetria(c)
    st = st_vacio()
    buscar._buscar_portal(con, "trabajando", st, [], c, RobotsLibre(), tele=t)
    assert len(pedidas) == 1 and st["errores"] == 0
    assert t["solicitudes"] == 1 and t["codigos"]["404"] == 1


def test_timeout_se_cuenta_como_conexion(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643"])
    c, _ = cliente({"bne.gob.cl": "timeout"})
    t = con_telemetria(c)
    st = st_vacio()
    buscar._buscar_portal(con, "bne", st, [], c, RobotsLibre(), tele=t)
    assert st["errores"] == 1
    assert t["solicitudes"] == 1 and t["codigos"]["conexion"] == 1


def test_listado_vacio_se_cuenta(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643", "tester"])
    monkeypatch.setattr(bne, "listar", lambda termino, cli, rob: pd.DataFrame(columns=bne.COLUMNAS))
    t = telemetria.contador("http")
    buscar._buscar_portal(con, "bne", st_vacio(), [], None, RobotsLibre(), tele=t)
    assert t["vacias"] == 2


def test_robots_txt_cuenta_su_solicitud(monkeypatch):
    t = telemetria.contador("http")
    g = GestorRobots("ua")
    g.al_responder = lambda status: telemetria.anotar_status(t, status)

    def abrir(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "x", {}, None)
    monkeypatch.setattr(robots_mod.urllib.request, "urlopen", abrir)
    assert g.permitido("https://x.cl/a") and g.permitido("https://x.cl/b")   # 404 = todo permitido, y se cachea
    monkeypatch.setattr(robots_mod.urllib.request, "urlopen",
                        lambda req, timeout: (_ for _ in ()).throw(socket.timeout("timed out")))
    assert g.no_disponible("https://y.cl/a")
    assert t["solicitudes"] == 2 and t["codigos"]["404"] == 1 and t["codigos"]["conexion"] == 1


# ---- Get on Board (API) y JobSpy
def test_get_on_board_cuenta_cada_solicitud_y_el_timeout(monkeypatch):
    t = telemetria.contador("http")
    anotar = lambda status: telemetria.anotar_status(t, status)                  # noqa: E731

    class Resp:
        def __init__(self, code): self.status_code = code
        def raise_for_status(self): pass
        def json(self): return {"data": []}
    codigos = iter([422, 200])
    monkeypatch.setattr(getonboard.requests, "get", lambda *a, **k: Resp(next(codigos)))
    assert getonboard.buscar("QA", 10, al_responder=anotar).empty               # reintento sin 'seniority', igual
    monkeypatch.setattr(getonboard.requests, "get",
                        lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("timed out")))
    with pytest.raises(requests.Timeout):
        getonboard.buscar("QA", 10, al_responder=anotar)
    assert t["solicitudes"] == 3 and t["codigos"]["otros"] == 1 and t["codigos"]["200"] == 1
    assert t["codigos"]["conexion"] == 1


def test_resumen_usa_singular_y_plural():
    t = telemetria.contador("http")
    telemetria.anotar_status(t, 200)
    assert telemetria.resumen({"BNE": t, "Indeed": telemetria.contador("consulta")}) == \
        "[corrida] BNE: 1 solicitud (200=1), 0 vacías | Indeed: 0 consultas (sin códigos), 0 vacías"


def test_clase_de_excepcion():
    class ConCodigo(Exception):
        response = types.SimpleNamespace(status_code=429)
    assert telemetria.clase_excepcion(ConCodigo()) == "429"
    assert telemetria.clase_excepcion(requests.ConnectionError("x")) == "conexion"
    assert telemetria.clase_excepcion(socket.timeout("x")) == "conexion"
    assert telemetria.clase_excepcion(RuntimeError("bad response status code 503")) == "5xx"
    assert telemetria.clase_excepcion(ValueError("formato raro")) == "otros"


def corrida_jobspy(tmp_path, monkeypatch, respuestas):
    """buscar_ofertas solo con Indeed y un JobSpy falso que responde, por término, un DataFrame o una excepción."""
    pedidos = []

    def scrape_jobs(**kw):
        pedidos.append(kw["search_term"])
        r = respuestas[kw["search_term"]]
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=scrape_jobs))
    for k, v in {"SITIOS": ["indeed"], "TERMINOS_A": list(respuestas), "TERMINOS_B": [],
                 "UBICACIONES": ["Santiago, Chile"], "INCLUIR_REMOTO": False, "PAUSA_ENTRE_BUSQUEDAS": 0}.items():
        monkeypatch.setattr(config, k, v)
    monkeypatch.setattr(buscar, "ahora_chile", lambda: AHORA)
    c = buscar.conectar(str(tmp_path / "t.db"))
    buscar.buscar_ofertas(c)
    return c, pedidos, buscar.ultima_corrida(c)["detalle"]


def test_jobspy_cuenta_consultas_vacias_y_errores_y_escribe_resumen(tmp_path, monkeypatch, capsys):
    respuestas = {"terminoSecreto": df_de({"job_url": "http://hoy/privada?x=1", "title": "QA Tester",
                                           "date_posted": "2026-10-11"}),
                  "vacio": pd.DataFrame(),
                  "limitado": RuntimeError("HTTP 429 Too Many Requests"),
                  "lento": requests.Timeout("timed out")}
    c, pedidos, detalle = corrida_jobspy(tmp_path, monkeypatch, respuestas)
    t = detalle["fuentes"][0]["telemetria"]
    assert t["medicion"] == "consulta" and t["solicitudes"] == 4 and t["vacias"] == 1
    assert t["codigos"]["429"] == 1 and t["codigos"]["conexion"] == 1
    assert detalle["fuentes"][0]["errores"] == 2                                  # lo de siempre, sin cambios
    guardado = json.dumps(detalle, ensure_ascii=False)
    assert "terminoSecreto" not in guardado and "privada" not in guardado          # solo contadores
    err = capsys.readouterr().err
    linea = [l for l in err.splitlines() if l.startswith("[corrida] ")]
    assert linea == ["[corrida] Indeed: 4 consultas (429=1, conexion=1), 1 vacía"]
    assert "terminoSecreto" not in err and "privada" not in err


# ---- pasiva: mismo comportamiento con y sin telemetría
def test_el_comportamiento_no_cambia_con_y_sin_telemetria(tmp_path, monkeypatch):
    ahora = datetime(2026, 10, 5, 12, 0, tzinfo=ZONA)
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643", "tester"])
    monkeypatch.setitem(config.MAX_DETALLES, "bne", 2)
    red = {"buscarListas": (200, leer("bne_ocupacion.json")), "/oferta/": (200, leer("bne_detalle_2026-120083.html"))}
    resultados = []
    for con_tele in (False, True):
        c_db = buscar.conectar(str(tmp_path / f"t{con_tele}.db"))
        dormidas = []
        c, pedidas = cliente(red, dormidas)
        t = con_telemetria(c) if con_tele else None
        st, avisos = st_vacio(), []
        n = buscar._buscar_portal(c_db, "bne", st, avisos, c, RobotsLibre(), ahora, 3, tele=t)
        filas = [tuple(r) for r in c_db.execute("SELECT * FROM ofertas ORDER BY url")]
        resultados.append((n, pedidas, dormidas, st, avisos, filas))
        if con_tele:
            assert t["solicitudes"] == len(pedidas) and t["codigos"]["200"] == len(pedidas)
    assert resultados[0] == resultados[1]


def test_un_fallo_de_la_telemetria_no_afecta_a_la_fuente(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643"])
    c, pedidas = cliente({"bne.gob.cl": (429, "")})
    c.al_responder = lambda status: 1 / 0
    avisos = []
    buscar._buscar_portal(con, "bne", st_vacio(), avisos, c, RobotsLibre())
    assert len(pedidas) == 1 and any("se detuvo" in a for a in avisos)


def test_sin_ddl_version_7_y_corridas_antiguas_intactas(tmp_path, monkeypatch):
    c = buscar.conectar(str(tmp_path / "t.db"))
    viejo = json.dumps({"fuentes": [{"fuente": "Indeed", "encontradas": 3, "errores": 0}]})
    c.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-10 10:00', '2026-10-10 10:05', 1, ?)",
              (viejo,))
    c.commit()
    esquema = c.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
    c.close()
    c, _, _ = corrida_jobspy(tmp_path, monkeypatch, {"QA": pd.DataFrame()})
    assert buscar.VERSION_DB == 7 and c.execute("PRAGMA user_version").fetchone()[0] == 7
    assert c.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == esquema
    assert c.execute("SELECT detalle FROM corridas WHERE id = 1").fetchone()[0] == viejo
    assert buscar.historial_corridas(c)[-1]["fuentes"] == json.loads(viejo)["fuentes"]


# ---- condición 1: un listado None o raro no hace fallar a la telemetría
class LenRoto:
    def __len__(self): raise RuntimeError("len roto")


def test_anotar_si_vacio_es_tolerante():
    t = telemetria.contador("http")
    telemetria.anotar_si_vacio(t, None)
    telemetria.anotar_si_vacio(t, pd.DataFrame())
    telemetria.anotar_si_vacio(t, LenRoto())                                   # no lanza ni cuenta
    telemetria.anotar_si_vacio(t, pd.DataFrame({"a": [1]}))
    telemetria.anotar_si_vacio(None, None)                                     # contador ausente: tampoco lanza
    assert t["vacias"] == 2 and type(t["vacias"]) is int


@pytest.mark.parametrize("listado", [None, LenRoto()], ids=["None", "len-roto"])
def test_listado_none_falla_igual_con_y_sin_telemetria(tmp_path, monkeypatch, listado):
    """Con un listado None (o sin len) la telemetría no agrega su propio error: la fuente se comporta igual que sin ella."""
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643"])
    monkeypatch.setattr(bne, "listar", lambda termino, cli, rob: listado)
    errores = []
    for con_tele in (False, True):
        c_db = buscar.conectar(str(tmp_path / f"n{con_tele}.db"))
        t = telemetria.contador("http") if con_tele else None
        try:
            buscar._buscar_portal(c_db, "bne", st_vacio(), [], None, RobotsLibre(), tele=t)
            errores.append(None)
        except Exception as e:                                     # lo que haga recientes() con un df inválido
            errores.append((type(e), str(e)))
    assert errores[0] == errores[1]


# ---- condición 2: se escribe en corridas.detalle con tipos simples y se lee de vuelta de la base
def hojas(x, ruta=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from hojas(v, f"{ruta}.{k}")
    else:
        yield ruta, x


def test_telemetria_se_guarda_en_la_base_con_tipos_simples(tmp_path, monkeypatch):
    respuestas = {"QA": df_de({"job_url": "http://hoy/1", "title": "QA Tester", "date_posted": "2026-10-11"}),
                  "vacio": pd.DataFrame(), "limitado": RuntimeError("HTTP 429")}
    c, _, _ = corrida_jobspy(tmp_path, monkeypatch, respuestas)
    c.close()
    import sqlite3
    crudo = sqlite3.connect(str(tmp_path / "t.db")).execute("SELECT detalle FROM corridas ORDER BY id DESC").fetchone()[0]
    t = json.loads(crudo)["fuentes"][0]["telemetria"]                          # leído de vuelta del disco
    assert t == {"medicion": "consulta", "solicitudes": 3, "vacias": 1,
                 "codigos": {"200": 0, "403": 0, "404": 0, "429": 1, "5xx": 0, "otros": 0, "conexion": 0}}
    for ruta, v in hojas(t):
        assert type(v) in (int, str), ruta                                      # ni bool, ni numpy, ni float


def test_contadores_son_int_tras_cada_anotacion():
    import numpy as np
    t = telemetria.contador("consulta")
    telemetria.anotar_consulta(t, 0)
    telemetria.anotar_consulta(t, np.int64(5))
    telemetria.anotar_status(t, np.int64(429))
    telemetria.anotar_excepcion(t, requests.Timeout("x"))
    telemetria.anotar_si_vacio(t, pd.DataFrame())
    for ruta, v in hojas(t):
        assert type(v) in (int, str), ruta
    json.dumps(t)                                                                # serializable sin default=


# ---- condición 3: la página y los endpoints muestran lo mismo; el campo nuevo solo viaja
CAMPOS_FUENTE_PAGINA = {"fuente", "encontradas", "relevantes", "errores", "antiguas", "ventana_dias"}


def test_la_pagina_no_lee_la_telemetria():
    from informe import PAGINA
    assert "telemetria" not in PAGINA
    import re
    usados = set(re.findall(r"\bf\.(\w+)", PAGINA))
    # f. también nombra las fechas y filtros en otras funciones: solo importa que ninguno sea un campo nuevo
    assert "telemetria" not in usados and CAMPOS_FUENTE_PAGINA & usados == CAMPOS_FUENTE_PAGINA


def test_endpoints_iguales_salvo_el_campo_nuevo(tmp_path, monkeypatch):
    """/api/ofertas (corridas[].fuentes) y /api/estado (corrida.detalle) devuelven exactamente lo mismo que una corrida
    sin telemetría, más la clave 'telemetria' en cada fuente."""
    import servidor
    c, _, detalle = corrida_jobspy(tmp_path, monkeypatch, {"QA": pd.DataFrame()})
    sin = json.loads(json.dumps(detalle))
    for f in sin["fuentes"]:
        f.pop("telemetria")
    c.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-10 10:00', '2026-10-10 10:05', 0, ?)",
              (json.dumps(sin, ensure_ascii=False),))
    c.commit()
    corridas = buscar.ofertas_para_pagina(c)["corridas"]
    nueva, vieja = [x for x in corridas if x["inicio"] != "2026-10-10 10:00"][0], corridas[-1]
    assert [{k: v for k, v in f.items() if k != "telemetria"} for f in nueva["fuentes"]] == vieja["fuentes"]
    app = servidor.Aplicacion(str(tmp_path / "t.db"), lambda con: 0)
    est = app.snapshot()["corrida"]["detalle"]
    assert [{k: v for k, v in f.items() if k != "telemetria"} for f in est["fuentes"]] == sin["fuentes"]
    assert est["avisos"] == sin["avisos"] and est["ventana_dias"] == sin["ventana_dias"]


def test_corridas_antiguas_conservan_su_huella(tmp_path, monkeypatch):
    import hashlib
    c = buscar.conectar(str(tmp_path / "t.db"))
    for i, d in enumerate([{"fuentes": [{"fuente": "BNE", "encontradas": 2}]}, {"fuentes": []}, None], start=1):
        c.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES (?, ?, 0, ?)",
                  (f"2026-10-0{i} 10:00", f"2026-10-0{i} 10:05", json.dumps(d) if d is not None else None))
    c.commit()
    huella = lambda con: hashlib.sha256(repr([tuple(r) for r in con.execute(      # noqa: E731
        "SELECT id, inicio, fin, nuevas, detalle FROM corridas WHERE id <= 3 ORDER BY id")]).encode()).hexdigest()
    antes = huella(c)
    c.close()
    c, _, _ = corrida_jobspy(tmp_path, monkeypatch, {"QA": pd.DataFrame()})
    assert huella(c) == antes and c.execute("SELECT COUNT(*) FROM corridas").fetchone()[0] == 4
