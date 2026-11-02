"""/api/aviso/ia: validación de largo, límite de cuerpo y caché de Groq."""
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ia
import servidor
from test_servidor import pedir, puerto_libre


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "_extraer_aviso_api", lambda t: {"titulo": "QA", "empresa": "Acme", "ubicacion": "",
                                                              "modalidad": "", "sueldo": ""})
    ia._cache.clear()
    app = servidor.Aplicacion(str(tmp_path / "t.db"), lambda con: 0)
    httpd = servidor.crear_servidor(app, puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def post(puerto, cuerpo):
    st, _, datos = pedir(puerto, "POST", "/api/aviso/ia", cuerpo)
    return st, json.loads(datos or b"{}")


TEXTO_OK = "Buscamos analista QA con experiencia en pruebas funcionales y SQL. " * 4   # > 150 caracteres


def test_texto_corto_se_rechaza_con_el_mensaje_de_la_pagina(srv):
    st, r = post(srv, {"texto": "muy corto"})
    assert st == 400 and "demasiado corto" in r["error"]


def test_texto_largo_se_acepta(srv):
    st, r = post(srv, {"texto": TEXTO_OK})
    assert st == 200 and r["aviso"]["titulo"] == "QA"


def test_texto_sobre_el_maximo_se_rechaza(srv):
    st, r = post(srv, {"texto": "a" * (ia.MAX_TEXTO_AVISO + 1)})
    assert st == 400 and "supera" in r["error"]


def test_cuerpo_sobre_el_limite_de_bytes_da_413(srv):
    st, _ = post(srv, {"texto": "é" * 30_000})       # 60 KB de UTF-8: sobre el límite de la ruta
    assert st == 413


def test_mismo_texto_en_corto_tiempo_no_vuelve_a_llamar_a_groq(srv, monkeypatch):
    llamadas = []
    monkeypatch.setattr(ia, "_extraer_aviso_api", lambda t: llamadas.append(1) or {"titulo": "QA", "empresa": "Acme",
                                                                                   "ubicacion": "", "modalidad": "", "sueldo": ""})
    post(srv, {"texto": TEXTO_OK})
    st, r = post(srv, {"texto": TEXTO_OK})
    assert st == 200 and r["aviso"]["empresa"] == "Acme" and len(llamadas) == 1


def test_un_error_de_groq_no_se_guarda_en_cache(monkeypatch):
    llamadas = []
    ia._cache.clear()
    monkeypatch.setattr(ia, "_extraer_aviso_api", lambda t: llamadas.append(1) or {"error": "caído"})
    ia.extraer_aviso(TEXTO_OK)
    ia.extraer_aviso(TEXTO_OK)
    assert len(llamadas) == 2


def test_la_cache_vence_y_tiene_tope(monkeypatch):
    ia._cache.clear()
    monkeypatch.setattr(ia, "_extraer_aviso_api", lambda t: {"titulo": t[:10], "empresa": "E"})
    for i in range(ia.CACHE_MAX + 5):
        ia.extraer_aviso(f"{i:04d} " + TEXTO_OK)
    assert len(ia._cache) <= ia.CACHE_MAX
