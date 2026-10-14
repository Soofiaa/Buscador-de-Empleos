"""Código 137: SIGTERM con cierre ordenado. El servidor real corre en un subproceso y la señal se envía con
signal.raise_signal DENTRO de él (en Windows, Popen.send_signal no manda señales): valida el manejador y el cierre,
no la entrega de Docker (eso se prueba con `docker compose stop` sobre una candidata)."""
import os
import socket
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import servidor
from test_servidor import pedir, puerto_libre

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = {"Origin": "http://127.0.0.1", "Content-Type": "application/json"}

# El subproceso arranca servidor.main() tal cual; un hilo espera el archivo "senal" y entonces se manda SIGTERM.
# Con BUSQUEDA_ETERNA, la búsqueda no termina nunca (para probar que su hilo daemon no impide salir).
LANZADOR = textwrap.dedent("""
    import os, signal, sys, threading, time
    sys.path.insert(0, os.environ["RAIZ"])
    import buscar, servidor
    if os.environ.get("BUSQUEDA_ETERNA"):
        buscar.buscar_ofertas = lambda con: time.sleep(3600)
    def esperar():
        while not os.path.exists(os.environ["SENAL"]):
            time.sleep(0.05)
        signal.raise_signal(signal.SIGTERM)
    threading.Thread(target=esperar, daemon=True).start()
    sys.argv = ["servidor.py", "--puerto", os.environ["PUERTO"], "--no-abrir"]
    servidor.main()
""")


class Servidor:
    def __init__(self, tmp_path, **env_extra):
        self.ruta = str(tmp_path / "t.db")
        self.senal = tmp_path / "senal"
        self.puerto = puerto_libre()
        env = {**os.environ, "RAIZ": str(RAIZ), "SENAL": str(self.senal), "PUERTO": str(self.puerto),
               "JT_DB": self.ruta, "JT_RESPALDOS": "", "PYTHONIOENCODING": "utf-8", **env_extra}
        self.p = subprocess.Popen([sys.executable, "-c", LANZADOR], env=env, cwd=str(tmp_path),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        for _ in range(100):                                   # hasta que atienda
            try:
                if pedir(self.puerto, "GET", "/api/estado")[0] == 200:
                    return
            except OSError:
                time.sleep(0.1)
        self.p.kill()
        raise AssertionError("el servidor no arrancó: " + self.p.communicate()[1])

    def sigterm(self, limite=10):
        t0 = time.monotonic()
        self.senal.write_text("ya")
        out, err = self.p.communicate(timeout=limite)
        return self.p.returncode, time.monotonic() - t0, out, err

    def wal(self):
        ruta = self.ruta + "-wal"
        return os.path.getsize(ruta) if os.path.exists(ruta) else 0


def escribir(srv):
    """Deja páginas en el -wal. Una conexión de la prueba queda abierta (sin transacción): si no, SQLite consolida el
    -wal al cerrarse la última conexión y no habría nada que probar. Devuelve esa conexión."""
    testigo = sqlite3.connect(srv.ruta)
    testigo.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()   # recién al leer abre el -wal
    st, _, _ = pedir(srv.puerto, "POST", "/api/ajustes/soporte", {"incluir": False}, ORIGEN)
    assert st == 200
    assert srv.wal() > 0
    return testigo


def test_sigterm_sale_con_0_y_consolida_el_wal(tmp_path):
    srv = Servidor(tmp_path)
    testigo = escribir(srv)
    try:
        codigo, dur, out, err = srv.sigterm()
    finally:
        testigo.close()
    assert codigo == 0, err
    assert dur < 3, dur
    assert srv.wal() == 0                                      # -wal consolidado (TRUNCATE lo deja en 0 bytes)
    assert "Servidor detenido." in out and "cierre:" not in err
    con = sqlite3.connect(srv.ruta)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert con.execute("SELECT valor FROM ajustes WHERE clave = 'soporte'").fetchone()[0] == '{"incluir": false}'
    con.close()


def test_una_busqueda_en_curso_no_impide_salir(tmp_path):
    srv = Servidor(tmp_path, BUSQUEDA_ETERNA="1")
    st, _, _ = pedir(srv.puerto, "POST", "/api/buscar", {}, ORIGEN)
    assert st in (200, 202)
    assert b'"buscando": true' in pedir(srv.puerto, "GET", "/api/estado")[2]
    codigo, dur, _, err = srv.sigterm()
    assert codigo == 0, err
    assert dur < 3, dur


def test_un_pedido_colgado_no_impide_salir(tmp_path):
    srv = Servidor(tmp_path)
    colgado = socket.create_connection(("127.0.0.1", srv.puerto))
    colgado.sendall(b"GET /api/estado HTTP/1.1\r\nHost: 127.0.0.1\r\n")   # sin la línea vacía final: queda esperando
    time.sleep(0.3)
    try:
        codigo, dur, _, err = srv.sigterm()
    finally:
        colgado.close()
    assert codigo == 0, err
    assert dur < 3, dur


def test_checkpoint_bloqueado_sale_igual_y_deja_el_motivo(tmp_path):
    srv = Servidor(tmp_path)
    lector = escribir(srv)
    lector.execute("BEGIN")
    lector.execute("SELECT COUNT(*) FROM ofertas").fetchone()   # lectura abierta: TRUNCATE no puede terminar
    try:
        codigo, dur, _, err = srv.sigterm()
    finally:
        lector.rollback()
        lector.close()
    assert codigo == 0, err
    assert dur < 6, dur                                       # límite del checkpoint (3 s) + arranque/cierre
    assert "cierre: el -wal no se consolidó" in err


# ------------------------------------------------------------------ apagar() y cerrar_base(), en el mismo proceso
def base_con_wal(tmp_path):
    """Base con páginas en el -wal; devuelve (ruta, conexión testigo abierta que evita la consolidación al cerrar)."""
    ruta = str(tmp_path / "t.db")
    con = buscar.conectar(ruta)
    testigo = sqlite3.connect(ruta)
    testigo.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()   # recién al leer abre el -wal
    with buscar.transaccion(con):
        con.execute("INSERT OR REPLACE INTO ajustes (clave, valor) VALUES ('x', '1')")
    con.close()
    assert os.path.getsize(ruta + "-wal") > 0
    return ruta, testigo


def test_cerrar_base_consolida_y_respeta_el_limite(tmp_path):
    ruta, lector = base_con_wal(tmp_path)
    lector.execute("BEGIN")
    lector.execute("SELECT 1 FROM ajustes").fetchone()
    t0 = time.monotonic()
    assert servidor.cerrar_base(ruta, limite_s=0.5) is False
    assert time.monotonic() - t0 < 2
    lector.rollback()                                        # sin la lectura abierta, sí se consolida
    assert os.path.getsize(ruta + "-wal") > 0
    assert servidor.cerrar_base(ruta) is True
    assert os.path.getsize(ruta + "-wal") == 0
    lector.close()


def test_apagar_espera_el_respaldo_en_curso(tmp_path):
    ruta, testigo = base_con_wal(tmp_path)
    app = servidor.Aplicacion(ruta_db=ruta, carpeta_respaldos="")
    app._lock_respaldo.acquire()
    threading.Timer(1.0, app._lock_respaldo.release).start()   # el respaldo termina al segundo
    t0 = time.monotonic()
    assert app.apagar(espera_respaldo_s=5) is True
    assert 0.9 < time.monotonic() - t0 < 3
    assert not app._lock_respaldo.acquire(blocking=False)      # se queda con el turno: no empieza otro respaldo
    assert os.path.getsize(ruta + "-wal") == 0
    testigo.close()


def test_apagar_no_espera_mas_del_limite_y_lo_registra(tmp_path, capsys):
    ruta, testigo = base_con_wal(tmp_path)
    app = servidor.Aplicacion(ruta_db=ruta, carpeta_respaldos="")
    app._lock_respaldo.acquire()                               # un respaldo que no termina
    t0 = time.monotonic()
    assert app.apagar(espera_respaldo_s=0.5) is True           # el -wal igual se consolida
    assert time.monotonic() - t0 < 2
    assert "el respaldo en curso no terminó en 0.5 s" in capsys.readouterr().err
    assert os.path.getsize(ruta + "-wal") == 0
    testigo.close()


def test_compose_da_15_s_para_el_cierre():
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "stop_grace_period: 15s" in compose
    assert servidor.ESPERA_RESPALDO_S + servidor.LIMITE_CHECKPOINT_S < 15
