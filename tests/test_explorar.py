"""«Explorar remotos»: categoría 'explorar' en el clasificador, búsqueda aparte y que corra junto con la normal."""
import json
import sys
import threading
import types
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import buscar
import servidor
from filtros import ZONA, clasificar
from informe import PAGINA

REMOTO = "Trabajo 100% remoto desde Chile. Sin experiencia previa."


def oferta(titulo, descripcion=REMOTO, **kw):
    return {"title": titulo, "company": "X", "location": "Santiago, RM, Chile", "description": descripcion,
            "is_remote": False, "fuente": "indeed", **kw}


@pytest.mark.parametrize("titulo, etiqueta, prioridad", [
    ("Customer Success Specialist", "customer success", "Media"),
    ("Onboarding Specialist", "implementación / onboarding", "Alta"),     # B pide señales; remoto, se explora
    ("Asistente Virtual", "asistente virtual / administrativo", "Baja"),
    ("Evaluador de IA en español", "IA y datos", "Media"),
    ("Technical Writer", "documentación técnica", "Alta"),
    ("Diseñador de presentaciones freelance", "freelance / por proyecto", "Baja"),
    ("Redactor técnico freelance", "documentación técnica", "Alta"),            # gana el rol, no "freelance"
    ("Diseñador de presentaciones a honorarios", "freelance / por proyecto", "Baja"),
    ("Diseñador de presentaciones a honorario", "freelance / por proyecto", "Baja"),
])
def test_rol_remoto_fuera_de_perfil_va_a_explorar(titulo, etiqueta, prioridad):
    c = clasificar(oferta(titulo))
    assert (c["categoria"], c["tipo"], c["prioridad"]) == ("explorar", "E: Explorar", prioridad)
    assert f"rol: {etiqueta}" in c["motivo"]


def test_explorar_exige_remoto_y_pasa_los_mismos_filtros():
    assert clasificar(oferta("Customer Success", "Presencial en Santiago."))["razon"] == "explorar: no es remoto"
    assert clasificar(oferta("Customer Success Manager"))["categoria"] == "descartada"           # nivel
    assert clasificar(oferta("Asistente virtual", REMOTO + " Requisito: 3 años de experiencia."))["categoria"] == "descartada"
    assert clasificar(oferta("Ejecutivo de ventas remoto"))["categoria"] == "descartada"          # no es rol a explorar
    assert clasificar(oferta("Asistente virtual ventas"))["razon"] == "explorar: ventas / call center / atención"
    assert clasificar(oferta("Practicante asistente virtual"))["razon"] == "práctica / estudiante"
    # "honorarios" como tema del puesto, no como forma de contrato
    for titulo in ("Ejecutivo Proceso Pago Honorarios Médicos RedSalud", "Analista de Pago de Honorarios"):
        assert clasificar(oferta(titulo))["categoria"] != "explorar"


def test_los_roles_del_perfil_no_cambian():
    assert clasificar(oferta("Analista QA"))["categoria"] == "principal"
    assert clasificar(oferta("Analista funcional CRM"))["tipo"] == "A: TI"       # "crm" no le gana a su regla
    assert clasificar(oferta("Desarrollador Python freelance"))["categoria"] == "principal"
    assert clasificar(oferta("Vendedor freelance"))["categoria"] == "descartada"


@pytest.fixture
def con(tmp_path):
    c = buscar.conectar(str(tmp_path / "t.db"))
    yield c
    c.close()


def test_la_ventana_de_la_busqueda_normal_ignora_las_exploraciones(con):
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-20 10:00', '2026-10-20 10:20', 0, '{}')")
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle, origen) "
                "VALUES ('2026-10-27 10:00', '2026-10-27 10:05', 0, '{}', 'explorar')")
    v = buscar.ventanas_efectivas(con, datetime(2026, 10, 28, 9, 0, tzinfo=ZONA))
    assert v["indeed"] == 9                       # desde el 20 (la normal), no desde el 27 (la exploración)
    assert buscar.ventanas_efectivas(con, datetime(2026, 10, 28, 9, 0, tzinfo=ZONA), explorar=True)["indeed"] == 2


def test_la_primera_exploracion_mira_el_maximo_de_dias(con):
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-28 08:00', '2026-10-28 08:20', 0, '{}')")
    v = buscar.ventanas_efectivas(con, datetime(2026, 10, 28, 9, 0, tzinfo=ZONA), explorar=True)
    assert v["indeed"] == buscar.config.DIAS_MAXIMOS


def test_explorar_remotos_guarda_en_explorar_y_registra_su_corrida(con, monkeypatch):
    pedidos = []

    def scrape_jobs(**kw):
        pedidos.append(kw)
        return pd.DataFrame([{"job_url": f"http://e/{len(pedidos)}", "title": "Customer Success Specialist",
                              "company": f"E{len(pedidos)}", "location": "Chile", "description": REMOTO,
                              "date_posted": None, "is_remote": True}])
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=scrape_jobs))
    monkeypatch.setattr(buscar, "_pausa_jobspy", lambda s: 0)
    monkeypatch.setattr(buscar.config, "TERMINOS_EXPLORAR", ["customer success", "onboarding"])
    monkeypatch.setattr(buscar.config, "EXPLORAR_APIS", ())
    assert buscar.explorar_remotos(con) == 2
    assert [p["site_name"] for p in pedidos] == [["indeed"], ["indeed"]]
    assert pedidos[0]["search_term"] == "customer success remoto"
    d = buscar.ofertas_para_pagina(con)
    assert [o["url"] for o in d["explorar"]] == ["http://e/1", "http://e/2"] and d["principal"] == []
    assert all(o["corrida_id"] is not None for o in d["explorar"])
    fila = con.execute("SELECT origen, nuevas FROM corridas").fetchone()
    assert (fila["origen"], fila["nuevas"]) == ("explorar", 2)


def test_explorar_busca_en_las_apis_por_texto_y_ante_429_no_insiste(con, monkeypatch):
    import requests
    pedidos = []

    def himalayas(termino, resultados, al_responder=None):
        pedidos.append(("himalayas", termino))
        return pd.DataFrame([{"job_url": f"http://h/{termino}", "title": "Technical Writer", "company": termino,
                              "location": "Remoto (global)", "description": "Modalidad 100% remota. " + REMOTO,
                              "date_posted": None, "is_remote": True}])

    def jobicy(termino, resultados, al_responder=None):
        pedidos.append(("jobicy", termino))
        r = requests.Response()
        r.status_code = 429
        raise requests.HTTPError("429", response=r)
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=lambda **kw: pd.DataFrame()))
    monkeypatch.setattr(buscar, "_pausa_jobspy", lambda s: 0)
    monkeypatch.setitem(buscar.APIS_REMOTAS, "himalayas", types.SimpleNamespace(buscar=himalayas))
    monkeypatch.setitem(buscar.APIS_REMOTAS, "jobicy", types.SimpleNamespace(buscar=jobicy))
    monkeypatch.setattr(buscar.config, "TERMINOS_EXPLORAR", [])
    monkeypatch.setattr(buscar.config, "TERMINOS_EXPLORAR_EN", ["technical writer", "ux research"])
    assert buscar.explorar_remotos(con) == 2
    assert pedidos == [("himalayas", "technical writer"), ("himalayas", "ux research"), ("jobicy", "technical writer")]
    assert [o["url"] for o in buscar.ofertas_para_pagina(con)["explorar"]] == ["http://h/technical writer",
                                                                                "http://h/ux research"]
    d = json.loads(con.execute("SELECT detalle FROM corridas").fetchone()[0])
    assert [f["fuente"] for f in d["fuentes"]] == ["Himalayas (explorar)", "Jobicy (explorar)"]
    assert d["fuentes"][1]["errores"] == 1 and any("Jobicy respondió 429" in a for a in d["avisos"])


def test_buscar_y_explorar_corren_a_la_vez_cada_una_con_su_avance(tmp_path):
    liberar = threading.Event()

    def falsa(nombre, n):
        def fn(con):
            buscar._say(f"avance de {nombre}")
            liberar.wait(5)
            return n
        return fn
    buscar.conectar(str(tmp_path / "t.db")).close()   # base ya creada y en WAL, como la real
    app = servidor.Aplicacion(str(tmp_path / "t.db"), falsa("buscar", 3), explorar_fn=falsa("explorar", 1))
    assert app.iniciar_busqueda("buscar") and app.iniciar_busqueda("explorar")
    assert not app.iniciar_busqueda("explorar") and not app.iniciar_busqueda("buscar")   # cada una, una a la vez
    for _ in range(100):
        e = app.snapshot()
        if e["mensaje"].startswith("avance") and e["explorar"]["mensaje"].startswith("avance"):
            break
        threading.Event().wait(0.02)
    assert e["mensaje"] == "avance de buscar" and e["explorar"]["mensaje"] == "avance de explorar"
    liberar.set()
    for _ in range(100):
        e = app.snapshot()
        if not e["buscando"] and not e["explorar"]["buscando"]:
            break
        threading.Event().wait(0.02)
    assert e["mensaje"].startswith("Búsqueda terminada: 3 ofertas relevantes nuevas.")
    assert e["explorar"]["mensaje"].startswith("Exploración terminada: 1 oferta nueva.")
    assert buscar.salida is print


def test_si_la_base_no_abre_el_boton_no_queda_bloqueado(tmp_path, monkeypatch):
    import sqlite3
    app = servidor.Aplicacion(str(tmp_path / "t.db"), lambda con: 0, explorar_fn=lambda con: 0)
    monkeypatch.setattr(app, "conexion", lambda: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
    assert app.iniciar_busqueda("explorar")
    app.hilo.join(5)
    e = app.trabajos["explorar"][0]       # snapshot() también abre la base
    assert not e["buscando"] and e["error"] == "OperationalError: database is locked"


def test_la_pagina_tiene_la_lista_explorar():
    # «Buscar empleos» ya hace también la exploración de remotos: un solo botón, su propia barra de progreso con cronómetro
    assert 'id="buscar"' in PAGINA and '"/api/buscar"' in PAGINA
    assert 'id="progreso-explorar"' in PAGINA and 'id="barra-tiempo"' in PAGINA
    assert '["explorar", "Explorar remotos"]' in PAGINA and "datos.explorar" in PAGINA
