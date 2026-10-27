"""LinkedIn se distancia: sus consultas se intercalan con los turnos de las demás fuentes (no van en ráfaga)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config


def plan_de(*fuentes):
    """Plan simple: una tupla (fuente, termino, lugar) por cada entrada."""
    return [(s, f"t{i}", "Chile") for i, s in enumerate(fuentes)]


def test_linkedin_esta_marcada_para_distanciar():
    assert "linkedin" in config.DISTANCIAR


def test_sin_otras_fuentes_no_cambia_nada():
    plan = plan_de("linkedin", "linkedin")
    assert buscar._intercalar(plan, "linkedin") == plan


def test_sin_consultas_propias_no_cambia_nada():
    plan = plan_de("indeed", "glassdoor")
    assert buscar._intercalar(plan, "linkedin") == plan


def test_linkedin_no_va_en_rafaga_y_empieza_su_turno():
    plan = plan_de(*(["linkedin"] * 6 + ["indeed"] * 2 + ["glassdoor"] * 2))
    res = [p[0] for p in buscar._intercalar(plan, "linkedin")]
    assert res[0] == "linkedin"                       # primero un turno de LinkedIn
    assert res.count("linkedin") == 6 and len(res) == 10
    assert "linkedin" not in res[-2:] or res.index("linkedin") < len(res) - 2   # no todas al final
    # entre dos turnos de LinkedIn hay otra fuente
    idx = [i for i, s in enumerate(res) if s == "linkedin"]
    assert any(res[i + 1] != "linkedin" for i in idx[:-1])


def test_ninguna_consulta_se_pierde_ni_se_duplica():
    plan = plan_de(*(["linkedin"] * 75 + ["indeed"] * 30 + ["glassdoor"] * 12 + ["jooble"]))
    res = buscar._intercalar(plan, "linkedin")
    assert sorted(res) == sorted(plan)


def test_el_orden_de_las_otras_fuentes_se_respeta():
    otras = plan_de(*(["indeed"] * 3 + ["glassdoor"] * 3))
    res = [p for p in buscar._intercalar(otras + plan_de(*["linkedin"] * 4), "linkedin") if p[0] != "linkedin"]
    assert res == otras
