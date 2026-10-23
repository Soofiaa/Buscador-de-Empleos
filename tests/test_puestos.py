"""Validación de la lista de puestos editable (puestos.py). Sin red ni base."""
import pytest

import puestos


def test_lista_valida_se_devuelve_igual():
    limpia, errores = puestos.validar(["analista funcional", "QA", "desarrollador python"])
    assert errores == [] and limpia == ["analista funcional", "QA", "desarrollador python"]


def test_espacios_sobrantes_se_limpian():
    limpia, errores = puestos.validar(["  analista   funcional  "])
    assert errores == [] and limpia == ["analista funcional"]


def test_no_es_lista_de_textos():
    for malo in ("analista", None, {"a": 1}, [1, "analista"], ["analista", None]):
        limpia, errores = puestos.validar(malo)
        assert limpia == [] and errores, malo


def test_vacio_no_se_permite():
    _, errores = puestos.validar([])
    assert "la lista no puede quedar vacía" in errores
    _, errores = puestos.validar(["   "])
    assert "hay un puesto vacío" in errores


def test_qa_y_dos_letras_se_permiten():
    limpia, errores = puestos.validar(["QA", "ti"])
    assert errores == [] and limpia == ["QA", "ti"]


def test_una_letra_no_se_permite():
    _, errores = puestos.validar(["a"])
    assert any("entre 2 y 60" in e for e in errores)


def test_maximo_sesenta_caracteres():
    _, errores = puestos.validar(["a" * 61])
    assert any("entre 2 y 60" in e for e in errores)
    limpia, errores = puestos.validar(["a" * 60])
    assert errores == [] and len(limpia[0]) == 60


@pytest.mark.parametrize("malo", ["analista <script>", "dev; DROP TABLE ofertas", "a\tb\x00c", "puesto $1", "x=y"])
def test_caracteres_no_permitidos(malo):
    limpia, errores = puestos.validar([malo])
    assert limpia == [] and errores


def test_tildes_y_enie_se_permiten():
    limpia, errores = puestos.validar(["analista de reportería", "diseñador UX", "ingeniería de datos"])
    assert errores == [] and len(limpia) == 3


def test_repetidos_ignoran_mayusculas_y_tildes():
    limpia, errores = puestos.validar(["Analista de reportería", "analista de reporteria", "ANALISTA DE REPORTERÍA"])
    assert len(limpia) == 1
    assert sum("repetido" in e for e in errores) == 2


def test_maximo_ochenta_puestos():
    limpia, errores = puestos.validar([f"puesto {i:02d}" for i in range(81)])
    assert "como máximo 80 puestos" in errores


def test_errores_de_varios_puestos_se_informan_juntos():
    limpia, errores = puestos.validar(["ok puesto", "a", "ok puesto", "x<y"])
    assert limpia == ["ok puesto"]
    assert len(errores) == 3
