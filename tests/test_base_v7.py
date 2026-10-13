"""Fase A: migración a v7, turno de escritura (BEGIN IMMEDIATE), base ocupada y reclasificar sin tocar lo manual."""
import hashlib
import json
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar


def base_v6(ruta, filas=(("a", "postulada", ""), ("b", "nueva", ""), ("c", "descartada", "2026-10-12"))):
    """Una base v6 como la real: tabla ofertas con las 4 columnas de seguimiento de v6 y corridas sin 'origen'."""
    con = sqlite3.connect(ruta)
    con.execute("""CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT UNIQUE, titulo TEXT, empresa TEXT,
        ubicacion TEXT, publicada TEXT, raw TEXT, categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT,
        modalidad TEXT, contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT, estado TEXT DEFAULT 'nueva',
        busqueda TEXT, detectada_en TEXT, fuente TEXT DEFAULT 'indeed', clave_base TEXT, ciudad TEXT DEFAULT '',
        notas TEXT DEFAULT '', fecha_postulacion TEXT DEFAULT '', fase TEXT DEFAULT '', sueldo_manual TEXT DEFAULT '')""")
    con.execute("CREATE TABLE corridas (id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT, fin TEXT, nuevas INTEGER, detalle TEXT)")
    con.execute("CREATE TABLE terminos_no_disponibles (sitio TEXT, termino TEXT, hasta TEXT, PRIMARY KEY (sitio, termino))")
    for i, (url, estado, fecha) in enumerate(filas):
        con.execute("INSERT INTO ofertas (url, clave, titulo, categoria, prioridad, estado, fecha_postulacion, notas) "
                    "VALUES (?, ?, ?, 'principal', 'Media', ?, ?, ?)", (url, f"k{i}", "T" + url, estado, fecha, "nota " + url))
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-11 10:58', '2026-10-11 11:06', 7, '{}')")
    con.execute("PRAGMA user_version = 6")
    con.commit()
    con.close()
    return ruta


def foto(ruta):
    c = sqlite3.connect(ruta)
    cols = [r[1] for r in c.execute("PRAGMA table_info(ofertas)") if r[1] != "prioridad_manual"]
    filas = c.execute(f"SELECT {', '.join(cols)} FROM ofertas ORDER BY url").fetchall()
    corridas = c.execute("SELECT id, inicio, fin, nuevas, detalle FROM corridas ORDER BY id").fetchall()
    c.close()
    return filas, corridas


def test_migracion_v6_a_v7_dos_veces_sin_perder_nada(tmp_path):
    ruta = base_v6(str(tmp_path / "v6.db"))
    antes = foto(ruta)
    for _ in range(2):
        con = buscar.conectar(ruta)
        assert con.execute("PRAGMA user_version").fetchone()[0] == buscar.VERSION_DB == 7
        con.close()
    assert foto(ruta) == antes                                            # todas las columnas v6 y las corridas, intactas
    con = sqlite3.connect(ruta)
    assert {r[0] for r in con.execute("SELECT DISTINCT prioridad_manual FROM ofertas")} == {""}
    assert {r[0] for r in con.execute("SELECT DISTINCT origen FROM corridas")} == {"manual"}
    ajustes = dict(con.execute("SELECT clave, valor FROM ajustes"))
    assert ajustes == {k: json.dumps(v) for k, v in buscar.AJUSTES_POR_DEFECTO.items()}
    assert json.loads(ajustes["programacion"])["activa"] is False                       # programación apagada
    assert con.execute("SELECT COUNT(*) FROM alertas").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM pruebas_fuentes").fetchone()[0] == 0
    assert list(tmp_path.glob("*_antigua_*")) == []


def test_los_ajustes_existentes_no_se_pisan(tmp_path):
    ruta = base_v6(str(tmp_path / "v6.db"))
    buscar.conectar(ruta).close()
    con = sqlite3.connect(ruta)
    con.execute("UPDATE ajustes SET valor = ? WHERE clave = 'programacion'", ('{"activa": true}',))
    con.execute("PRAGMA user_version = 6")                                # fuerza otra pasada de la migración
    con.commit()
    con.close()
    buscar.conectar(ruta).close()
    con = sqlite3.connect(ruta)
    assert con.execute("SELECT valor FROM ajustes WHERE clave = 'programacion'").fetchone()[0] == '{"activa": true}'


def test_migracion_desde_v5_llega_a_v7(tmp_path):
    ruta = base_v6(str(tmp_path / "v5.db"))
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA user_version = 5")
    con.commit()
    con.close()
    con = buscar.conectar(ruta)
    cols = {r[1] for r in con.execute("PRAGMA table_info(ofertas)")}
    assert set(buscar.COLUMNAS_SEGUIMIENTO) <= cols and con.execute("PRAGMA user_version").fetchone()[0] == 7
    assert list(tmp_path.glob("*_antigua_*")) == []


def test_base_nueva_nace_en_v7_con_espera_explicita(tmp_path):
    con = buscar.conectar(str(tmp_path / "nueva.db"))
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"ofertas", "corridas", "ajustes", "alertas", "pruebas_fuentes"} <= tablas
    assert con.execute("PRAGMA user_version").fetchone()[0] == 7
    assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 15000
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_fallo_en_la_migracion_no_cambia_nada(tmp_path):
    ruta = base_v6(str(tmp_path / "v6.db"))
    con = sqlite3.connect(ruta)
    con.execute("UPDATE ofertas SET fase = 'cv' WHERE url = 'a'")        # fase de la app Node, no válida aquí
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="no se migró nada"):
        buscar.conectar(ruta)
    con = sqlite3.connect(ruta)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 6
    assert "prioridad_manual" not in {r[1] for r in con.execute("PRAGMA table_info(ofertas)")}
    assert "origen" not in {r[1] for r in con.execute("PRAGMA table_info(corridas)")}
    assert {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")} == \
        {"ofertas", "corridas", "terminos_no_disponibles", "sqlite_sequence"}
    con.close()
    assert foto(ruta)[0][0][-1] == "" and [f for f in foto(ruta)[0] if f[0] == "a"][0][-2] == "cv"


def test_una_version_desconocida_se_sigue_respaldando(tmp_path):
    ruta = base_v6(str(tmp_path / "v9.db"))
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA user_version = 9")
    con.commit()
    con.close()
    buscar.conectar(ruta).close()
    assert len(list(tmp_path.glob("v9_antigua_*.db"))) == 1


def test_base_ocupada_no_escribe_nada_a_medias(tmp_path, monkeypatch):
    ruta = base_v6(str(tmp_path / "v6.db"))
    buscar.conectar(ruta).close()
    monkeypatch.setattr(buscar, "BUSY_TIMEOUT_MS", 200)
    otra = sqlite3.connect(ruta, isolation_level=None)
    otra.execute("BEGIN IMMEDIATE")                                       # otra escritura tiene el turno
    con = buscar.conectar(ruta)
    with pytest.raises(buscar.BaseOcupada):
        with buscar.transaccion(con):
            con.execute("UPDATE ofertas SET notas = 'x' WHERE url = 'a'")
    otra.execute("ROLLBACK")
    otra.close()
    assert con.execute("SELECT notas FROM ofertas WHERE url = 'a'").fetchone()[0] == "nota a"


def test_dos_hilos_escribiendo_a_la_vez_no_se_pisan(tmp_path):
    ruta = base_v6(str(tmp_path / "v6.db"), filas=[(f"u{i}", "nueva", "") for i in range(40)])
    buscar.conectar(ruta).close()
    errores = []

    def escribir(campo, valor):
        con = buscar.conectar(ruta)
        try:
            for i in range(40):
                with buscar.transaccion(con):
                    con.execute(f"UPDATE ofertas SET {campo} = ? WHERE url = ?", (valor, f"u{i}"))
        except Exception as ex:
            errores.append(ex)
        finally:
            con.close()
    hilos = [threading.Thread(target=escribir, args=("notas", "del hilo 1")),
             threading.Thread(target=escribir, args=("sueldo_manual", "del hilo 2"))]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(30)
    assert errores == []
    con = sqlite3.connect(ruta)
    assert con.execute("SELECT COUNT(*) FROM ofertas WHERE notas = 'del hilo 1' AND sueldo_manual = 'del hilo 2'").fetchone()[0] == 40


def test_reclasificar_no_toca_las_columnas_manuales(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    raw = {"title": "QA Tester", "company": "A", "location": "Santiago de Chile, RM, Chile", "description": "",
           "job_url": "http://qa", "is_remote": True}
    con.execute("INSERT INTO ofertas (url, clave, titulo, raw, categoria, prioridad, estado, notas, fecha_postulacion, fase, "
                "sueldo_manual, prioridad_manual) VALUES ('http://qa', 'k', 'QA Tester', ?, 'principal', 'Alta', 'entrevista', "
                "'mi nota', '2026-10-12', 'tecnica', '$1.500.000', 'Baja')", (json.dumps(raw),))
    con.commit()
    buscar.reclasificar(con)
    f = con.execute("SELECT * FROM ofertas").fetchone()
    assert (f["estado"], f["notas"], f["fecha_postulacion"], f["fase"], f["sueldo_manual"], f["prioridad_manual"]) == \
        ("entrevista", "mi nota", "2026-10-12", "tecnica", "$1.500.000", "Baja")
    assert not set(buscar.COLUMNAS_SEGUIMIENTO) & set(buscar.CAMPOS_CLASIF)
