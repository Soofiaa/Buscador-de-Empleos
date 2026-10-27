"""Tope de consultas por corrida (LinkedIn): el cursor rota y, en pocas corridas, se cubren todas las combinaciones."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config


@pytest.fixture
def con(tmp_path):
    c = buscar.conectar(str(tmp_path / "t.db"))
    yield c
    c.close()


COMBOS = [("t", str(i), "Chile") for i in range(75)]


def test_tope_de_linkedin_es_6():
    assert config.TOPE_CONSULTAS["linkedin"] == 6


def test_sin_tope_si_hay_pocas_combinaciones(con):
    assert buscar._rotar_plan(con, "linkedin", COMBOS[:4], 6) == COMBOS[:4]
    assert con.execute("SELECT COUNT(*) FROM ajustes WHERE clave LIKE 'rotacion_%'").fetchone()[0] == 0


def test_cada_corrida_toma_el_tope_y_avanza(con):
    primera = buscar._rotar_plan(con, "linkedin", COMBOS, 6)
    segunda = buscar._rotar_plan(con, "linkedin", COMBOS, 6)
    assert len(primera) == 6 and len(segunda) == 6
    assert primera == COMBOS[:6] and segunda == COMBOS[6:12]


def test_en_13_corridas_se_cubren_las_75(con):
    vistas = []
    for _ in range(13):
        vistas += buscar._rotar_plan(con, "linkedin", COMBOS, 6)
    assert set(COMBOS) <= set(vistas)


def test_el_cursor_da_la_vuelta(con):
    for _ in range(13):                       # 78 lugares en 13 corridas: el cursor vuelve a 3
        buscar._rotar_plan(con, "linkedin", COMBOS, 6)
    assert buscar._rotar_plan(con, "linkedin", COMBOS, 6) == COMBOS[3:9]


def test_cursor_corrupto_arranca_de_cero(con):
    con.execute("INSERT INTO ajustes (clave, valor) VALUES ('rotacion_linkedin', 'basura')")
    assert buscar._rotar_plan(con, "linkedin", COMBOS, 6) == COMBOS[:6]


def test_el_cursor_no_afecta_a_otras_fuentes(con):
    buscar._rotar_plan(con, "linkedin", COMBOS, 6)
    assert buscar._rotar_plan(con, "glassdoor", COMBOS, 6) == COMBOS[:6]
