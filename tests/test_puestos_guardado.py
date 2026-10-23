"""Lista de puestos guardada en ajustes (paso 2): lectura por defecto, guardado validado y uso en la búsqueda.
Base temporal, sin red."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config
from test_servidor import pedir, puerto_libre


@pytest.fixture
def con(tmp_path):
    c = buscar.conectar(str(tmp_path / "t.db"))
    yield c
    c.close()


def test_sin_guardar_se_usan_los_puestos_de_config(con):
    assert buscar.leer_puestos(con) == config.TERMINOS_A + config.TERMINOS_B


def test_guardar_y_leer(con):
    buscar.guardar_puestos(con, {"lista": ["analista funcional", "QA"]})
    assert buscar.leer_puestos(con) == ["analista funcional", "QA"]


def test_guardar_queda_en_ajustes_sin_cambiar_la_version(con):
    version = con.execute("PRAGMA user_version").fetchone()[0]
    buscar.guardar_puestos(con, {"lista": ["Analista   funcional"]})
    fila = con.execute("SELECT valor FROM ajustes WHERE clave = 'puestos'").fetchone()
    assert json.loads(fila[0]) == {"lista": ["Analista funcional"]}
    assert con.execute("PRAGMA user_version").fetchone()[0] == version


@pytest.mark.parametrize("malo", [{"lista": []}, {"lista": ["a"]}, {"lista": ["x<y"]}, {"lista": "analista"},
                                  {"otra": ["analista"]}, {"lista": ["analista"], "extra": 1}, ["analista"]])
def test_guardar_rechaza_listas_invalidas_y_no_escribe(con, malo):
    with pytest.raises(buscar.ErrorDatos) as e:
        buscar.guardar_puestos(con, malo)
    assert e.value.codigo == 400
    assert con.execute("SELECT COUNT(*) FROM ajustes WHERE clave = 'puestos'").fetchone()[0] == 0


def test_si_un_puesto_guardado_se_daña_se_usa_config(con):
    con.execute("INSERT INTO ajustes (clave, valor) VALUES ('puestos', ?)", (json.dumps({"lista": ["x<y"]}),))
    assert buscar.leer_puestos(con) == config.TERMINOS_A + config.TERMINOS_B
    con.execute("UPDATE ajustes SET valor = 'no es json' WHERE clave = 'puestos'")
    assert buscar.leer_puestos(con) == config.TERMINOS_A + config.TERMINOS_B


def test_la_busqueda_de_indeed_usa_la_lista_guardada(con, monkeypatch):
    buscar.guardar_puestos(con, {"lista": ["analista funcional", "tester"]})
    usados = []
    monkeypatch.setattr(config, "SITIOS", ["indeed"])
    monkeypatch.setattr(config, "UBICACIONES", ["Santiago, Chile"])
    monkeypatch.setattr(config, "INCLUIR_REMOTO", False)
    monkeypatch.setattr(buscar, "_pausa_jobspy", lambda s: 0)
    monkeypatch.setattr(buscar.time, "sleep", lambda s: None)

    import types
    fake = types.ModuleType("jobspy")
    fake.scrape_jobs = lambda **kw: (usados.append(kw["search_term"]), buscar.pd.DataFrame())[1]
    monkeypatch.setitem(sys.modules, "jobspy", fake)
    buscar.buscar_ofertas(con)
    assert usados == ["analista funcional", "tester"]


@pytest.fixture
def srv_puestos(tmp_path):
    import threading
    import servidor
    ruta = str(tmp_path / "s.db")
    buscar.conectar(ruta).close()
    httpd = servidor.crear_servidor(servidor.Aplicacion(ruta, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def test_servidor_lee_y_guarda_puestos(srv_puestos):
    puerto = srv_puestos
    st, _, cuerpo = pedir(puerto, "GET", "/api/ajustes/puestos")
    assert st == 200 and json.loads(cuerpo) == {"lista": config.TERMINOS_A + config.TERMINOS_B}
    st, _, cuerpo = pedir(puerto, "POST", "/api/ajustes/puestos", {"lista": ["analista funcional"]})
    assert st == 200 and json.loads(cuerpo)["lista"] == ["analista funcional"]
    assert json.loads(pedir(puerto, "GET", "/api/ajustes/puestos")[2]) == {"lista": ["analista funcional"]}
    assert pedir(puerto, "POST", "/api/ajustes/puestos", {"lista": []})[0] == 400
    assert pedir(puerto, "POST", "/api/ajustes/puestos", {"lista": ["x<y"]})[0] == 400
    assert pedir(puerto, "POST", "/api/ajustes/puestos", {"lista": ["analista"]},
                 {"Origin": "https://evil.example.com"})[0] == 403
    assert json.loads(pedir(puerto, "GET", "/api/ajustes/puestos")[2]) == {"lista": ["analista funcional"]}
