"""Servidor local de la página: rutas, seguridad (Host/Origin) y búsqueda en segundo plano."""
import http.client
import json
import re
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import buscar
import servidor
from informe import PAGINA


def df_de(*filas):
    base = {"title": "", "company": "X", "location": "Santiago de Chile, RM, Chile", "description": "",
            "date_posted": None, "is_remote": False, "min_amount": None, "max_amount": None,
            "currency": "", "interval": ""}
    return pd.DataFrame([{**base, **f} for f in filas])


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def srv(tmp_path):
    ruta = str(tmp_path / "t.db")
    con = buscar.conectar(ruta)
    buscar.guardar(con, buscar.procesar(df_de({"job_url": "http://qa", "title": "QA Tester", "is_remote": True}), "t"))
    con.close()
    liberar = threading.Event()

    def falsa(con):                               # búsqueda simulada: espera a que el test la libere
        buscar._say("Paso 1 de la búsqueda")
        liberar.wait(5)
        return 3

    app = servidor.Aplicacion(ruta, falsa)
    httpd = servidor.crear_servidor(app, puerto_libre(), "127.0.0.1")   # 0 no sirve: crear_servidor lo toma como "usar el de config"
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield app, httpd.server_address[1], liberar
    liberar.set()
    httpd.shutdown()
    httpd.server_close()


def pedir(puerto, metodo, ruta, cuerpo=None, cabeceras=None):
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
    c.request(metodo, ruta, json.dumps(cuerpo) if cuerpo is not None else None, cabeceras or {})
    r = c.getresponse()
    datos = r.read()
    return r.status, r.getheader("Content-Type"), datos


def test_pagina_y_datos(srv):
    _, puerto, _ = srv
    st, tipo, cuerpo = pedir(puerto, "GET", "/")
    assert st == 200 and tipo.startswith("text/html") and b"Buscar empleos" in cuerpo
    st, _, cuerpo = pedir(puerto, "GET", "/api/ofertas")
    d = json.loads(cuerpo)
    assert st == 200 and [o["url"] for o in d["principal"]] == ["http://qa"]


def test_api_ofertas_trae_historial(srv):
    _, puerto, _ = srv
    d = json.loads(pedir(puerto, "GET", "/api/ofertas")[2])
    assert d["corridas"] == []                                            # sin búsquedas: historial vacío
    assert d["principal"][0]["corrida_id"] is None                        # -> "Antes del historial"


def test_la_pagina_no_carga_nada_de_afuera():
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", PAGINA)
    assert "@import" not in PAGINA and "url(" not in PAGINA and "<link" not in PAGINA
    assert 'aria-pressed' in PAGINA and "Agrupar: fuente" in PAGINA and "Agrupar: prioridad" in PAGINA and "por día detectado" not in PAGINA


def test_cambiar_estado_se_guarda(srv):
    _, puerto, _ = srv
    st, _, _ = pedir(puerto, "POST", "/api/marcar", {"url": "http://qa", "estado": "postulada"})
    assert st == 200
    d = json.loads(pedir(puerto, "GET", "/api/ofertas")[2])
    assert d["principal"][0]["estado"] == "postulada"
    assert pedir(puerto, "POST", "/api/marcar", {"url": "http://qa", "estado": "x"})[0] == 400
    assert pedir(puerto, "POST", "/api/marcar", {"url": "http://otra", "estado": "revisada"})[0] == 400
    assert pedir(puerto, "POST", "/api/marcar", [1, 2])[0] == 400


def test_rechaza_host_y_origen_no_locales(srv):
    _, puerto, _ = srv
    for cab in ({"Host": "evil.example.com"}, {"Origin": "https://evil.example.com"}):
        assert pedir(puerto, "GET", "/api/ofertas", None, cab)[0] == 403
        assert pedir(puerto, "POST", "/api/marcar", {"url": "http://qa", "estado": "revisada"}, cab)[0] == 403
    assert pedir(puerto, "GET", "/api/ofertas", None, {"Origin": f"http://127.0.0.1:{puerto}"})[0] == 200
    assert pedir(puerto, "GET", "/api/ofertas", None, {"Host": f"localhost:{puerto}"})[0] == 200


def test_busqueda_en_segundo_plano_con_progreso_y_un_solo_hilo(srv):
    app, puerto, liberar = srv
    assert pedir(puerto, "POST", "/api/buscar", {})[0] == 202
    assert pedir(puerto, "POST", "/api/buscar", {})[0] == 409            # ya hay una en curso
    for _ in range(50):
        e = json.loads(pedir(puerto, "GET", "/api/estado")[2])
        if e["mensaje"].startswith("Paso 1"):
            break
        time.sleep(0.05)
    assert e["buscando"] is True and e["mensaje"] == "Paso 1 de la búsqueda"
    liberar.set()
    app.hilo.join(5)
    e = json.loads(pedir(puerto, "GET", "/api/estado")[2])
    assert e["buscando"] is False and "3 ofertas" in e["mensaje"] and e["error"] == ""
    assert buscar.salida is print                                         # se restauró la salida


def test_un_fallo_en_la_busqueda_no_bloquea_el_boton(tmp_path):
    def rota(con):
        raise RuntimeError("se cayó")
    app = servidor.Aplicacion(str(tmp_path / "t.db"), rota)
    assert app.iniciar_busqueda()
    app.hilo.join(5)
    assert app.estado["buscando"] is False and "se cayó" in app.estado["error"]
    assert app.iniciar_busqueda()                                         # se puede volver a intentar
    app.hilo.join(5)


def test_la_pagina_no_usa_innerhtml_con_datos():
    assert "innerHTML" not in PAGINA and "eval(" not in PAGINA
    assert "textContent" in PAGINA or "document.createTextNode" in PAGINA


def test_una_busqueda_real_vacia_queda_registrada_en_corridas(tmp_path, monkeypatch):
    monkeypatch.setattr(buscar.config, "SITIOS", [])
    monkeypatch.setattr(buscar.config, "UBICACIONES", [])
    con = buscar.conectar(str(tmp_path / "t.db"))
    import types, sys as _s
    _s.modules.setdefault("jobspy", types.SimpleNamespace(scrape_jobs=lambda **k: None))
    assert buscar.buscar_ofertas(con) == 0
    c = buscar.ultima_corrida(con)
    assert c and c["nuevas"] == 0 and c["detalle"]["fuentes"] == []
