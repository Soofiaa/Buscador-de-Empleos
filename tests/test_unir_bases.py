"""Reglas de unir_bases.py: gana la base principal, nada se pierde en silencio y las entradas no se tocan."""
import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import unir_bases


def base(ruta, filas, columnas_node=False, corridas=1):
    con = buscar.conectar(str(ruta))
    if not columnas_node:          # como la base del volumen: v5, sin columnas de seguimiento
        con.close()
        v = sqlite3.connect(str(ruta))
        v.execute("CREATE TABLE o2 AS SELECT url, clave, titulo, empresa, categoria, estado, detectada_en FROM ofertas")
        v.execute("DROP TABLE ofertas"); v.execute("ALTER TABLE o2 RENAME TO ofertas")
        v.execute("PRAGMA user_version = 5"); v.commit()
        con = v
    for i, (url, estado, extra) in enumerate(filas):
        con.execute("INSERT INTO ofertas (url, clave, titulo, empresa, categoria, estado) VALUES (?, ?, ?, 'E', 'principal', ?)",
                    (url, f"k{i}", "T " + url, estado))
        for col, val in extra.items():
            con.execute(f"UPDATE ofertas SET {col} = ? WHERE url = ?", (val, url))
    for i in range(corridas):
        con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES (?, ?, 1, '{}')",
                    (f"2026-10-1{i} 10:00", f"2026-10-1{i} 10:05"))
    con.commit(); con.close()
    return str(ruta)


def sha(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


@pytest.fixture
def bases(tmp_path):
    vjt = base(tmp_path / "vjt.db", [("u1", "descartada", {}), ("u2", "nueva", {}), ("u3", "postulada", {}),
                                    ("u4", "nueva", {}), ("u5", "descartada", {})], corridas=3)
    node = base(tmp_path / "node.db", [("u1", "postulada", {"fecha_postulacion": "2026-10-12"}),
                                      ("u2", "postulada", {"fecha_postulacion": "2026-10-12", "notas": "llamar"}),
                                      ("u3", "descartada", {}), ("u4", "nueva", {}),
                                      ("u5", "postulada", {"fecha_postulacion": "2026-10-12"})],
                columnas_node=True, corridas=1)
    return tmp_path, vjt, node


def correr(tmp_path, vjt, node, excepciones=None, **kw):
    salida = tmp_path / "unida.db"
    conflictos = unir_bases.unir(("VJT", vjt), [("NODE", node)], excepciones or {}, salida, "2026-10-13", **kw)
    con = sqlite3.connect(salida); con.row_factory = sqlite3.Row
    return {r["url"]: dict(r) for r in con.execute("SELECT * FROM ofertas")}, con, conflictos


def test_gana_la_base_principal_y_deja_nota(bases):
    tmp_path, vjt, node = bases
    filas, _, conflictos = correr(tmp_path, vjt, node)
    assert filas["u1"]["estado"] == "descartada"          # VJT gana aunque NODE diga postulada
    assert filas["u1"]["notas"] == ("[unión 2026-10-13] estados previos: VJT=descartada, NODE=postulada; "
                                    "fecha_postulacion en NODE=2026-10-12")
    assert filas["u1"]["fecha_postulacion"] == "2026-10-12"   # la fecha de NODE no se pierde
    assert filas["u3"]["estado"] == "postulada" and "NODE=descartada" in filas["u3"]["notas"]
    assert {c["url"]: c["por_verificar"] for c in conflictos}["u1"] is True


def test_nueva_en_la_principal_toma_la_decision_de_la_otra(bases):
    tmp_path, vjt, node = bases
    filas, _, _ = correr(tmp_path, vjt, node)
    assert (filas["u2"]["estado"], filas["u2"]["fecha_postulacion"]) == ("postulada", "2026-10-12")
    assert filas["u2"]["notas"] == "[unión 2026-10-13] notas en NODE: llamar"   # sin "estados previos": no se descartó nada
    assert (filas["u4"]["estado"], filas["u4"]["notas"]) == ("nueva", "")


def test_descartar_solo_un_nueva_no_deja_nota(tmp_path):
    vjt = base(tmp_path / "vjt.db", [("u1", "postulada", {})])
    node = base(tmp_path / "node.db", [("u1", "postulada", {"fecha_postulacion": "2026-10-12"})], columnas_node=True)
    vbe = base(tmp_path / "vbe.db", [("u1", "nueva", {})], columnas_node=True)
    unir_bases.unir(("VJT", vjt), [("NODE", node), ("VBE", vbe)], {}, tmp_path / "u.db", "2026-10-13")
    f = sqlite3.connect(tmp_path / "u.db").execute("SELECT estado, fecha_postulacion, notas FROM ofertas").fetchone()
    assert f == ("postulada", "2026-10-12", "")           # la fecha de NODE se toma igual, sin nota


def test_excepcion_manda_con_su_nota(bases):
    tmp_path, vjt, node = bases
    ex = {"u5": {"estado": "postulada", "fecha_postulacion": "2026-10-12", "nota": "POR VERIFICAR x", "por_verificar": True}}
    filas, _, conflictos = correr(tmp_path, vjt, node, ex)
    assert (filas["u5"]["estado"], filas["u5"]["notas"]) == ("postulada", "POR VERIFICAR x")
    assert [c["motivo"] for c in conflictos if c["url"] == "u5"] == ["excepción"]


def test_corridas_solo_de_la_principal_y_entradas_intactas(bases):
    tmp_path, vjt, node = bases
    antes = (sha(vjt), sha(node))
    _, con, _ = correr(tmp_path, vjt, node, esperadas_postuladas=2)
    assert con.execute("SELECT COUNT(*) FROM corridas").fetchone()[0] == 3
    assert con.execute("PRAGMA user_version").fetchone()[0] == buscar.VERSION_DB
    assert (sha(vjt), sha(node)) == antes


def test_postuladas_distintas_de_lo_esperado_cancelan_sin_escribir(bases):
    tmp_path, vjt, node = bases
    with pytest.raises(AssertionError):
        correr(tmp_path, vjt, node, esperadas_postuladas=99)
    assert not (tmp_path / "unida.db").exists()


def test_oferta_que_solo_existe_en_otra_base_cancela(tmp_path):
    vjt = base(tmp_path / "vjt.db", [("u1", "nueva", {})])
    node = base(tmp_path / "node.db", [("u1", "nueva", {}), ("solo", "postulada", {})], columnas_node=True)
    with pytest.raises(unir_bases.ErrorUnion, match="se perderían"):
        unir_bases.unir(("VJT", vjt), [("NODE", node)], {}, tmp_path / "u.db", "2026-10-13")
    assert not (tmp_path / "u.db").exists()


def test_decisiones_ambiguas_cancelan(tmp_path):
    vjt = base(tmp_path / "vjt.db", [("u1", "nueva", {})])
    a = base(tmp_path / "a.db", [("u1", "postulada", {})], columnas_node=True)
    b = base(tmp_path / "b.db", [("u1", "descartada", {})], columnas_node=True)
    with pytest.raises(unir_bases.ErrorUnion, match="ambigua"):
        unir_bases.unir(("VJT", vjt), [("A", a), ("B", b)], {}, tmp_path / "u.db", "2026-10-13")
