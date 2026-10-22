"""«informático junior»: término de búsqueda (Indeed, Glassdoor/Get on Board y Chiletrabajos; no BNE ni Trabajando) y
regla de último recurso del clasificador -> A: TI, Baja, sin cambiar nada de lo que otra regla ya reconoce."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config

DESC = "Buscamos apoyo para el área de TI. Jornada completa, presencial."


def clas(titulo, desc=DESC):
    c = buscar.clasificar({"title": titulo, "company": "Empresa X", "location": "Santiago, Región Metropolitana, Chile",
                           "description": desc})
    return c["categoria"], c["tipo"], c["prioridad"]


def test_el_termino_va_en_indeed_secundarios_y_chiletrabajos_con_su_convencion_de_tildes():
    assert "informático junior" in config.TERMINOS_A                     # Indeed: con tilde, como el resto
    assert "informático jr" in config.TERMINOS_A
    assert "informático junior" in config.TERMINOS_SECUNDARIOS           # Glassdoor y Get on Board
    assert "informático jr" in config.TERMINOS_SECUNDARIOS
    assert "informatico junior" in config.TERMINOS_CHILETRABAJOS         # va en la URL: sin tilde
    assert "informatico jr" in config.TERMINOS_CHILETRABAJOS
    assert not any("informatic" in t for t in config.TERMINOS_BNE + config.TERMINOS_TRABAJANDO)   # 0 resultados / 404


def test_cada_termino_junior_tiene_variante_jr():
    for lista in (config.TERMINOS_A, config.TERMINOS_B, config.TERMINOS_SECUNDARIOS, config.TERMINOS_CHILETRABAJOS):
        for t in lista:
            if "junior" in t:
                assert t.replace("junior", "jr") in lista
    assert "desarrollador jr" in config.TERMINOS_A
    assert "analista de datos jr" in config.TERMINOS_A
    assert "analista de datos jr" in config.TERMINOS_SECUNDARIOS
    assert "desarrollador jr" in config.TERMINOS_CHILETRABAJOS
    assert "desarrollador junior" not in config.TERMINOS_SECUNDARIOS     # no se agrega jr donde no había junior


@pytest.mark.parametrize("titulo", ["Informático Junior", "Informática Junior", "Ingeniero Informático Junior",
                                    "Analista Informático Junior", "Informatico Jr", "Junior Informático",
                                    "INGENIERA INFORMÁTICA JR."])
def test_informatico_junior_entra_como_ti_baja(titulo):
    assert clas(titulo) == ("principal", "A: TI", "Baja")


@pytest.mark.parametrize("titulo", ["Técnico en Informática", "Encargado de Informática", "Profesor de Informática",
                                    "Analista de Información Junior", "Junior de Información", "Informante Junior"])
def test_sin_junior_o_sin_el_tallo_informatic_sigue_descartada(titulo):
    assert clas(titulo) == ("descartada", "", "")


@pytest.mark.parametrize("titulo, desc", [
    ("Informático Semi Senior Jr", DESC), ("Jefe Informático Junior", DESC), ("Informático Junior / Senior", DESC),
    ("Informático Junior", "Buscamos un perfil senior para el área de TI.")])
def test_el_nivel_senior_lo_descarta_el_filtro_de_siempre(titulo, desc):
    c = buscar.clasificar({"title": titulo, "company": "Empresa X", "location": "Santiago, Chile", "description": desc})
    assert (c["categoria"], c["razon"]) == ("descartada", "nivel semi senior / senior")


def test_informatico_senior_sin_junior_no_tiene_rol():
    assert buscar.clasificar({"title": "Informático Senior", "company": "X", "location": "Santiago, Chile",
                              "description": DESC})["razon"] == "sin rol objetivo"


def test_lo_que_otra_regla_reconoce_no_cambia():
    assert clas("Ingeniero en Informática - Desarrollador Junior") == ("principal", "A: TI", "Alta")
    assert clas("Soporte Informático Junior") == ("principal", "S: Soporte TI", "Baja")
    assert clas("Técnico Informático de Soporte") == ("principal", "S: Soporte TI", "Baja")
    assert clas("Analista de Sistemas Informático Junior") == ("principal", "A: TI", "Alta")
    assert clas("Analista QA Informático Junior") == ("principal", "A: TI", "Alta")
    # la regla va después de todas: un título que otra regla ya reconoce conserva esa regla (y su motivo)
    c = buscar.clasificar({"title": "Desarrollador Informático Junior", "company": "X", "location": "Santiago, Chile",
                           "description": DESC})
    assert c["prioridad"] == "Alta" and "informático junior" not in c["motivo"]


def test_el_motivo_dice_que_entro_por_informatico_junior():
    c = buscar.clasificar({"title": "Informático Junior", "company": "X", "location": "Santiago, Chile", "description": DESC})
    assert c["motivo"].startswith("rol: informático junior")
