"""Respaldo de la base a una carpeta del equipo: consistente, atómico, con retención, y sin tumbar el servidor."""
import errno
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import threading
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import respaldo
import servidor
from test_servidor import pedir, puerto_libre

AHORA = datetime(2026, 10, 13, 9, 30)


@pytest.fixture
def base(tmp_path):
    ruta = str(tmp_path / "ofertas.db")
    con = buscar.conectar(ruta)
    con.executemany("INSERT INTO ofertas (url, clave, titulo, categoria, estado, raw) VALUES (?, ?, ?, 'principal', 'nueva', '{}')",
                    [(f"http://o{i}", f"k{i}", f"Oferta {i}") for i in range(200)])
    con.commit()
    con.close()
    carpeta = tmp_path / "respaldos"
    carpeta.mkdir()
    return ruta, str(carpeta)


def filas(ruta):
    c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    r = c.execute("SELECT url, titulo, estado FROM ofertas ORDER BY url").fetchall()
    c.close()
    return r


def test_respaldo_es_copia_valida_con_su_sha256(base):
    ruta, carpeta = base
    r = respaldo.respaldar(ruta, carpeta, "manual", AHORA)
    final = os.path.join(carpeta, r["archivo"])
    assert r["archivo"] == "ofertas_manual_20261013-093000.db" and r["integridad"] == "ok"
    assert filas(final) == filas(ruta)
    sidecar = open(final + ".sha256", encoding="utf-8").read().split()
    assert sidecar == [hashlib.sha256(open(final, "rb").read()).hexdigest(), r["archivo"]] and r["sha256"] == sidecar[0]
    assert not [n for n in os.listdir(carpeta) if n.startswith(respaldo.PREFIJO_TMP)]   # nada a medias


def test_respaldo_consistente_mientras_otro_escribe(base):
    ruta, carpeta = base
    parar = threading.Event()

    def escribir():
        con = buscar.conectar(ruta)
        i = 0
        while not parar.is_set():
            with buscar.transaccion(con):
                con.execute("UPDATE ofertas SET notas = ? WHERE url = ?", (f"nota {i}", f"http://o{i % 200}"))
            i += 1
        con.close()
    hilo = threading.Thread(target=escribir)
    hilo.start()
    try:
        hechos = [respaldo.respaldar(ruta, carpeta, "manual", AHORA + timedelta(seconds=s)) for s in range(5)]
    finally:
        parar.set()
        hilo.join(10)
    for h in hechos:
        c = sqlite3.connect(os.path.join(carpeta, h["archivo"]))
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 200
        c.close()


def test_retencion_guarda_30_automaticos_y_nunca_borra_manuales(base):
    ruta, carpeta = base
    respaldo.respaldar(ruta, carpeta, "manual", AHORA - timedelta(days=90))
    for d in range(35):
        respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=35 - d))
    todos = respaldo.listar(carpeta)
    autos = [r for r in todos if r["tipo"] == "auto"]
    assert len(autos) == respaldo.RETENER_AUTO == 30 and len([r for r in todos if r["tipo"] == "manual"]) == 1
    assert autos[-1]["archivo"] == f"ofertas_auto_{AHORA - timedelta(days=30):%Y%m%d}-093000.db"   # se fueron los 5 más viejos
    assert len([n for n in os.listdir(carpeta) if n.endswith(".sha256")]) == 31


def test_restos_de_un_respaldo_interrumpido_se_limpian(base):
    ruta, carpeta = base
    resto = os.path.join(carpeta, respaldo.PREFIJO_TMP + "ofertas_auto_20261001-090000.db")
    open(resto, "wb").write(b"a medias")
    os.utime(resto, (0, 0))                                                # viejo
    respaldo.respaldar(ruta, carpeta, "manual", AHORA)
    assert not os.path.exists(resto)


@pytest.mark.parametrize("carpeta", ["", "no-existe"])
def test_carpeta_no_configurada_o_no_montada(base, carpeta):
    ruta, real = base
    destino = carpeta and os.path.join(real, carpeta)
    with pytest.raises(respaldo.RespaldoNoDisponible):
        respaldo.respaldar(ruta, destino, "manual", AHORA)
    e = respaldo.estado(destino)
    assert e["disponible"] is False and e["error"] and e["configurado"] is bool(carpeta)


def test_disco_lleno_no_deja_archivos(base, monkeypatch):
    ruta, carpeta = base
    Uso = namedtuple("Uso", "total used free")
    monkeypatch.setattr(respaldo.shutil, "disk_usage", lambda _: Uso(10**9, 10**9, 1024))
    with pytest.raises(respaldo.SinEspacio):
        respaldo.respaldar(ruta, carpeta, "manual", AHORA)
    assert os.listdir(carpeta) == []


def test_disco_que_se_llena_durante_la_copia(base, monkeypatch):
    ruta, carpeta = base
    original = respaldo._sha256
    def sin_espacio(_):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(respaldo, "_sha256", sin_espacio)
    with pytest.raises(respaldo.SinEspacio):
        respaldo.respaldar(ruta, carpeta, "manual", AHORA)
    assert [n for n in os.listdir(carpeta) if n.endswith(".db")] == []    # ni el temporal ni uno final a medias


# ------------------------------------------------------------------ el servidor
class Reloj:
    def __init__(self, ahora):
        self.ahora = ahora

    def __call__(self):
        return self.ahora


def test_respaldo_diario_con_reloj_simulado(base):
    ruta, carpeta = base
    reloj = Reloj(AHORA)
    app = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos=carpeta, reloj=reloj)
    assert app.revisar_respaldo_diario()["archivo"] == "ofertas_auto_20261013-093000.db"
    reloj.ahora = AHORA + timedelta(hours=10)
    assert app.revisar_respaldo_diario() is None                          # ya hay uno de hoy
    reloj.ahora = AHORA + timedelta(days=1)
    assert app.revisar_respaldo_diario()["archivo"] == "ofertas_auto_20261014-093000.db"
    assert len(respaldo.listar(carpeta)) == 2


def test_un_fallo_del_respaldo_diario_no_tumba_nada(base):
    ruta, carpeta = base
    app = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos=os.path.join(carpeta, "desmontada"), reloj=Reloj(AHORA))
    assert app.revisar_respaldo_diario() is None
    assert "RespaldoNoDisponible" in app.error_respaldo_auto
    assert app.snapshot()["respaldo"]["error_auto"] == app.error_respaldo_auto
    sin_config = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos="", reloj=Reloj(AHORA))
    assert sin_config.revisar_respaldo_diario() is None and sin_config.error_respaldo_auto == ""


@pytest.fixture
def srv(base):
    ruta, carpeta = base
    app = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos=carpeta, reloj=Reloj(AHORA))
    httpd = servidor.crear_servidor(app, puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1], app, carpeta
    httpd.shutdown()
    httpd.server_close()


def test_boton_respaldar_ahora_y_limite_de_uno_por_minuto(srv):
    puerto, app, carpeta = srv
    st, _, cuerpo = pedir(puerto, "POST", "/api/respaldo", {})
    assert st == 201 and json.loads(cuerpo)["respaldo"]["archivo"] == "ofertas_manual_20261013-093000.db"
    assert pedir(puerto, "POST", "/api/respaldo", {})[0] == 429
    e = json.loads(pedir(puerto, "GET", "/api/respaldo")[2])
    assert e["disponible"] and e["total_manual"] == 1 and e["ultimo"]["fecha"] == "2026-10-13 09:30"
    assert json.loads(pedir(puerto, "GET", "/api/estado")[2])["respaldo"]["ultimo"]["archivo"] == "ofertas_manual_20261013-093000.db"


def test_ruta_de_respaldo_rechaza_datos_y_origen_ajeno(srv):
    puerto, _, carpeta = srv
    assert pedir(puerto, "POST", "/api/respaldo", {"carpeta": "C:/otra"})[0] == 400        # la carpeta no viene del pedido
    assert pedir(puerto, "POST", "/api/respaldo", {}, {"Origin": "https://evil.example.com"})[0] == 403
    assert os.listdir(carpeta) == []


def test_carpeta_no_montada_es_503_y_el_servidor_sigue(srv):
    puerto, app, carpeta = srv
    app.carpeta_respaldos = os.path.join(carpeta, "no-montada")
    st, _, cuerpo = pedir(puerto, "POST", "/api/respaldo", {})
    assert st == 503 and "no existe o no está montada" in json.loads(cuerpo)["error"]
    assert pedir(puerto, "GET", "/api/ofertas")[0] == 200
