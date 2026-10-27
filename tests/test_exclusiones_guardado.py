"""Exclusiones guardadas (conexión con el clasificador y la base). Base temporal, sin red."""
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config
import filtros
import servidor
from test_servidor import pedir, puerto_libre

RAW_EMPRESA = {"title": "Analista Funcional", "company": "Acme Chile", "location": "Santiago de Chile, RM, Chile",
               "description": "Analista funcional con SQL.", "is_remote": False, "min_amount": None,
               "max_amount": None, "currency": "", "interval": ""}


@pytest.fixture(autouse=True)
def limpiar_exclusiones():
    yield
    filtros.fijar_exclusiones(None)


@pytest.fixture
def con(tmp_path):
    c = buscar.conectar(str(tmp_path / "t.db"))
    yield c
    c.close()


def test_sin_guardar_rige_config(con):
    buscar.aplicar_exclusiones(con)
    assert filtros.exclusiones_activas()["titulo"] == config.EXCLUIR_PRACTICA_TITULO
    assert buscar.leer_exclusiones(con) is None


def test_guardar_excluye_la_empresa_nueva(con):
    assert filtros.clasificar(RAW_EMPRESA)["razon"] != "empresa excluida"
    buscar.guardar_exclusiones(con, {"empresas": ["acme"], "titulo": [], "descripcion": []})
    assert filtros.clasificar(RAW_EMPRESA)["razon"] == "empresa excluida"


def test_guardar_una_regla_de_titulo_se_aplica(con):
    buscar.guardar_exclusiones(con, {"empresas": [], "titulo": [r"analista funcional"], "descripcion": []})
    buscar.aplicar_exclusiones(con)
    assert filtros.clasificar(RAW_EMPRESA)["razon"] == "práctica / estudiante"


def test_guardado_invalido_no_escribe_y_no_cambia_lo_activo(con):
    buscar.guardar_exclusiones(con, {"empresas": ["acme"], "titulo": [], "descripcion": []})
    with pytest.raises(buscar.ErrorDatos) as e:
        buscar.guardar_exclusiones(con, {"empresas": [], "titulo": [r"(roto"], "descripcion": []})
    assert e.value.codigo == 400
    buscar.aplicar_exclusiones(con)
    assert filtros.clasificar(RAW_EMPRESA)["razon"] == "empresa excluida"


def test_valor_guardado_dañado_vuelve_a_config(con):
    con.execute("INSERT INTO ajustes (clave, valor) VALUES ('exclusiones', ?)", (json.dumps({"empresas": ["x<y"]}),))
    assert buscar.leer_exclusiones(con) is None
    buscar.aplicar_exclusiones(con)
    assert filtros.exclusiones_activas()["titulo"] == config.EXCLUIR_PRACTICA_TITULO


def test_guardar_queda_en_ajustes_sin_cambiar_la_version(con):
    version = con.execute("PRAGMA user_version").fetchone()[0]
    buscar.guardar_exclusiones(con, {"empresas": ["acme"], "titulo": [], "descripcion": []})
    fila = con.execute("SELECT valor FROM ajustes WHERE clave = 'exclusiones'").fetchone()
    assert json.loads(fila[0])["empresas"] == ["acme"]
    assert con.execute("PRAGMA user_version").fetchone()[0] == version


@pytest.fixture
def srv_exclusiones(tmp_path):
    ruta = str(tmp_path / "s.db")
    buscar.conectar(ruta).close()
    httpd = servidor.crear_servidor(servidor.Aplicacion(ruta, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()
    filtros.fijar_exclusiones(None)


def test_servidor_lee_y_guarda_exclusiones(srv_exclusiones):
    p = srv_exclusiones
    st, _, cuerpo = pedir(p, "GET", "/api/ajustes/exclusiones")
    assert st == 200 and json.loads(cuerpo)["empresas"] == config.EXCLUIR_EMPRESAS
    nuevo = {"empresas": ["acme"], "titulo": ["practic"], "descripcion": ["alumno"]}
    st, _, cuerpo = pedir(p, "POST", "/api/ajustes/exclusiones", nuevo)
    assert st == 200
    assert json.loads(pedir(p, "GET", "/api/ajustes/exclusiones")[2]) == nuevo
    assert pedir(p, "POST", "/api/ajustes/exclusiones", {**nuevo, "titulo": ["(roto"]})[0] == 400
    assert pedir(p, "POST", "/api/ajustes/exclusiones", nuevo, {"Origin": "https://evil.example.com"})[0] == 403
    assert json.loads(pedir(p, "GET", "/api/ajustes/exclusiones")[2]) == nuevo
