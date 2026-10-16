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
    assert sorted(os.listdir(carpeta)) == [r["archivo"], r["archivo"] + ".sha256"]      # ni -wal ni -shm
    c = sqlite3.connect(f"file:{final}?mode=ro", uri=True)
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"                 # un solo archivo autosuficiente
    c.close()


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


# ------------------------------------------------------------------ .sha256 al final y atómico; válido = .db con su .sha256
def sha256_ok(carpeta, nombre):                                         # como `sha256sum -c`
    linea = open(os.path.join(carpeta, nombre + ".sha256"), encoding="utf-8").read().split()
    return linea[1] == nombre and linea[0] == hashlib.sha256(open(os.path.join(carpeta, nombre), "rb").read()).hexdigest()


def test_a_corte_entre_el_db_y_su_sha256_deja_un_incompleto_que_no_cuenta(base, monkeypatch):
    ruta, carpeta = base
    def corte(*a):
        raise OSError("corte justo después del .db")
    monkeypatch.setattr(respaldo, "_escribir_huella", corte)
    with pytest.raises(respaldo.HuellaNoEscrita, match="queda como respaldo incompleto"):
        respaldo.respaldar(ruta, carpeta, "auto", AHORA)
    monkeypatch.undo()
    assert os.listdir(carpeta) == ["ofertas_auto_20261013-093000.db"]   # quedó el .db, sin .sha256 ni temporales
    assert respaldo.listar(carpeta) == [] and respaldo.incompletos(carpeta) == ["ofertas_auto_20261013-093000.db"]
    est = respaldo.estado(carpeta)
    assert est["ultimo"] is None and est["total_auto"] == 0 and est["incompletos"] == 1
    assert not respaldo.hay_auto_de_hoy(carpeta, AHORA)                 # no cuenta como el de hoy: se vuelve a intentar
    app = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos=carpeta, reloj=Reloj(AHORA + timedelta(minutes=1)))
    hecho = app.revisar_respaldo_diario()
    assert hecho["archivo"] == "ofertas_auto_20261013-093100.db" and sha256_ok(carpeta, hecho["archivo"])
    assert respaldo.estado(carpeta)["incompletos"] == 1                 # el incompleto no se borra solo: se informa


def test_b_corte_al_escribir_el_sha256_no_deja_nada_que_parezca_valido(base, monkeypatch):
    ruta, carpeta = base
    def fsync_falla(fd):
        raise OSError("disco desconectado")
    monkeypatch.setattr(respaldo.os, "fsync", fsync_falla)
    with pytest.raises(respaldo.HuellaNoEscrita, match="Motivo: OSError: disco desconectado"):
        respaldo.respaldar(ruta, carpeta, "manual", AHORA)
    monkeypatch.undo()
    assert sorted(os.listdir(carpeta)) == ["ofertas_manual_20261013-093000.db"]   # sin .sha256 final ni temporal
    assert respaldo.listar(carpeta) == []
    # si el proceso muere a mitad (sin llegar al finally), queda solo el temporal: se ignora y se limpia
    resto = os.path.join(carpeta, respaldo.PREFIJO_TMP + "ofertas_manual_20261013-093000.db.sha256")
    open(resto, "w").write("a medias")
    os.utime(resto, (0, 0))
    assert respaldo.listar(carpeta) == []
    respaldo.respaldar(ruta, carpeta, "auto", AHORA)
    assert not os.path.exists(resto)


def test_listar_ordena_por_la_fecha_del_nombre_mezclando_auto_y_manual(base):
    ruta, carpeta = base
    respaldo.respaldar(ruta, carpeta, "manual", AHORA - timedelta(hours=10))           # 12-10 23:30 (manual, más viejo)
    respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=2))               # 11-10 09:30
    respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(hours=9, minutes=25))  # 13-10 00:05 (el más nuevo)
    respaldo.respaldar(ruta, carpeta, "manual", AHORA - timedelta(days=3))             # 10-10 09:30
    shutil.copy(ruta, os.path.join(carpeta, "ofertas_manual_20261013-120000.db"))     # incompleto: no cuenta como último
    assert [r["archivo"] for r in respaldo.listar(carpeta)] == [
        "ofertas_auto_20261013-000500.db", "ofertas_manual_20261012-233000.db",
        "ofertas_auto_20261011-093000.db", "ofertas_manual_20261010-093000.db"]
    e = respaldo.estado(carpeta)
    assert e["ultimo"]["archivo"] == "ofertas_auto_20261013-000500.db" and e["ultimo"]["fecha"] == "2026-10-13 00:05"
    assert e["incompletos"] == 1 and e["total_auto"] == 2 and e["total_manual"] == 2


def test_la_retencion_no_cambia_con_el_nuevo_orden(base):
    ruta, carpeta = base
    for d in range(3):                                                  # manuales más nuevos que todos los auto
        respaldo.respaldar(ruta, carpeta, "manual", AHORA + timedelta(days=d))
    for d in range(32):
        respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=32 - d))
    todos = respaldo.listar(carpeta)
    assert [r["tipo"] for r in todos[:3]] == ["manual"] * 3
    autos = [r["archivo"] for r in todos if r["tipo"] == "auto"]
    assert len(autos) == 30 and autos[-1] == f"ofertas_auto_{AHORA - timedelta(days=30):%Y%m%d}-093000.db"


# nombres que empiezan y terminan como un respaldo pero no son el formato exacto (copias renombradas a mano)
NOMBRES_RAROS = ["ofertas_auto_x.db", "ofertas_manual_copia.db", "ofertas_auto_20261013.db",
                 "ofertas_auto_20261013-0930.db", "ofertas_manual_20261013-093000-copia.db",
                 "ofertas_auto_20261013-09300\uff10.db"]                       # último dígito "０" de ancho completo


def poner_raros(carpeta, origen):
    """Copia un respaldo válido con cada nombre raro y le escribe su .sha256 correcto: parecerían válidos."""
    huella = hashlib.sha256(open(os.path.join(carpeta, origen), "rb").read()).hexdigest()
    for n in NOMBRES_RAROS:
        shutil.copy(os.path.join(carpeta, origen), os.path.join(carpeta, n))
        open(os.path.join(carpeta, n + ".sha256"), "w", encoding="utf-8").write(f"{huella}  {n}\n")


def test_a_un_nombre_que_no_calza_no_queda_primero(base):
    ruta, carpeta = base
    respaldo.respaldar(ruta, carpeta, "manual", AHORA - timedelta(days=1))
    nuevo = respaldo.respaldar(ruta, carpeta, "auto", AHORA)["archivo"]
    poner_raros(carpeta, nuevo)
    shutil.copy(os.path.join(carpeta, nuevo), os.path.join(carpeta, "ofertas_manual_sin_huella.db"))   # raro y sin .sha256
    assert [r["archivo"] for r in respaldo.listar(carpeta)] == [nuevo, "ofertas_manual_20261012-093000.db"]
    e = respaldo.estado(carpeta)
    assert e["ultimo"]["archivo"] == nuevo and e["ultimo"]["fecha"] == "2026-10-13 09:30"
    assert e["total_auto"] == 1 and e["total_manual"] == 1 and e["incompletos"] == 0   # los raros ni siquiera son incompletos
    assert not respaldo.hay_auto_de_hoy(carpeta, AHORA + timedelta(days=1))           # un raro no cuenta como "el de hoy"


def test_b_la_retencion_no_cuenta_ni_borra_un_nombre_que_no_calza(base):
    ruta, carpeta = base
    primero = respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=40))["archivo"]
    poner_raros(carpeta, primero)                                       # antes de rotar: deben sobrevivir a todas las rotaciones
    for d in range(32):
        respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=32 - d))
    autos = [r["archivo"] for r in respaldo.listar(carpeta)]
    assert len(autos) == respaldo.RETENER_AUTO == 30                    # 30 válidos: los raros no ocupan cupo
    assert autos[-1] == f"ofertas_auto_{AHORA - timedelta(days=30):%Y%m%d}-093000.db"
    assert not os.path.exists(os.path.join(carpeta, primero))          # el válido más viejo sí se fue
    for n in NOMBRES_RAROS:                                             # los raros siguen ahí, con su .sha256
        assert os.path.exists(os.path.join(carpeta, n)) and os.path.exists(os.path.join(carpeta, n + ".sha256"))


def test_c_el_orden_entre_nombres_validos_no_cambia_con_raros(base):
    ruta, carpeta = base
    for tipo, delta in [("manual", timedelta(hours=-10)), ("auto", timedelta(days=-2)), ("auto", timedelta(hours=-9)),
                        ("manual", timedelta(days=-3)), ("manual", timedelta(0)), ("auto", timedelta(0))]:
        respaldo.respaldar(ruta, carpeta, tipo, AHORA + delta)
    antes = [r["archivo"] for r in respaldo.listar(carpeta)]
    assert antes == ["ofertas_manual_20261013-093000.db", "ofertas_auto_20261013-093000.db",   # misma hora: manual > auto
                     "ofertas_auto_20261013-003000.db", "ofertas_manual_20261012-233000.db",
                     "ofertas_auto_20261011-093000.db", "ofertas_manual_20261010-093000.db"]
    poner_raros(carpeta, antes[0])
    assert [r["archivo"] for r in respaldo.listar(carpeta)] == antes


def test_c_la_rotacion_cuenta_y_borra_solo_validos(base):
    ruta, carpeta = base
    for d in range(3):                                                  # 3 incompletos, más viejos que todo
        nombre = f"ofertas_auto_{AHORA - timedelta(days=60 + d):%Y%m%d}-093000.db"
        shutil.copy(ruta, os.path.join(carpeta, nombre))
    for d in range(32):
        respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=32 - d))
    validos = [r["archivo"] for r in respaldo.listar(carpeta)]
    assert len(validos) == respaldo.RETENER_AUTO == 30
    assert validos[-1] == f"ofertas_auto_{AHORA - timedelta(days=30):%Y%m%d}-093000.db"   # se fueron los 2 válidos más viejos
    assert len(respaldo.incompletos(carpeta)) == 3                      # intactos: ni cuentan ni se borran
    assert all(sha256_ok(carpeta, n) for n in validos)


def test_d_formato_antiguo_sigue_valido_y_un_sha256_suelto_se_ignora(base):
    ruta, carpeta = base
    hecho = respaldo.respaldar(ruta, carpeta, "auto", AHORA - timedelta(days=1))
    viejo = "ofertas_auto_20261001-093000.db"                          # formato antiguo: .sha256 escrito ANTES del .db
    huella = hashlib.sha256(open(os.path.join(carpeta, hecho["archivo"]), "rb").read()).hexdigest()
    open(os.path.join(carpeta, viejo + ".sha256"), "w", encoding="utf-8").write(f"{huella}  {viejo}\n")
    shutil.copy(os.path.join(carpeta, hecho["archivo"]), os.path.join(carpeta, viejo))
    open(os.path.join(carpeta, "ofertas_auto_20260901-093000.db.sha256"), "w").write("x  suelto\n")   # sin su .db
    assert [r["archivo"] for r in respaldo.listar(carpeta)] == [hecho["archivo"], viejo]
    assert respaldo.incompletos(carpeta) == [] and sha256_ok(carpeta, viejo)


def test_un_respaldo_automatico_fallido_queda_en_stderr(base, capsys):
    ruta, carpeta = base
    app = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos=os.path.join(carpeta, "desmontada"), reloj=Reloj(AHORA))
    assert app.revisar_respaldo_diario() is None
    err = capsys.readouterr().err
    assert "respaldo automático falló: RespaldoNoDisponible" in err and app.error_respaldo_auto in err


def test_snapshot_no_toma_el_turno_del_respaldo(base):
    ruta, carpeta = base
    shutil.copy(ruta, os.path.join(carpeta, "ofertas_manual_20261001-093000.db"))      # un incompleto
    app = servidor.Aplicacion(ruta, lambda con: 0, carpeta_respaldos=carpeta, reloj=Reloj(AHORA))
    r = app.snapshot()["respaldo"]
    assert r["en_curso"] is False and r["incompletos"] == 1
    app._lock_respaldo.acquire()                                       # un respaldo en curso
    try:
        r = app.snapshot()["respaldo"]                                 # responde al tiro, sin esperar el turno
        assert r["en_curso"] is True and r["incompletos"] is None
    finally:
        app._lock_respaldo.release()
    app.snapshot()
    assert app._lock_respaldo.acquire(blocking=False)                  # snapshot nunca deja el turno tomado
    app._lock_respaldo.release()


def test_si_falla_el_replace_del_sha256_el_mensaje_lo_dice_claro(srv, monkeypatch):
    puerto, app, carpeta = srv
    replace_real = os.replace
    def replace(src, dst):
        if str(dst).endswith(".sha256"):
            raise PermissionError(13, "Permission denied")
        return replace_real(src, dst)
    monkeypatch.setattr(respaldo.os, "replace", replace)
    st, _, cuerpo = pedir(puerto, "POST", "/api/respaldo", {}, {"Origin": "http://127.0.0.1", "Content-Type": "application/json"})
    monkeypatch.undo()
    error = json.loads(cuerpo)["error"]
    assert st == 500
    assert error.startswith("la copia ofertas_manual_20261013-093000.db se guardó, pero no su huella (.sha256): "
                            "queda como respaldo incompleto, no válido. Motivo: PermissionError")
    assert "el respaldo falló" not in error
    r = json.loads(pedir(puerto, "GET", "/api/respaldo")[2])
    assert r["incompletos"] == 1 and r["ultimo"] is None and r["en_curso"] is False
    assert sorted(os.listdir(carpeta)) == ["ofertas_manual_20261013-093000.db"]   # sin temporales
