"""Persistencia de vistas y filtros: pestaña, filtros, agrupación y «Más filtros» se guardan en localStorage y se restauran."""
import re
from pathlib import Path

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")


def test_clave_de_preferencias_y_funciones_existen():
    assert 'const CLAVE_PREFS = "vistaPrefs";' in PAGINA
    assert "function cargarPrefs()" in PAGINA and "function guardarPrefs()" in PAGINA
    assert "cargarPrefs();" in PAGINA


def test_se_guardan_los_cuatro_datos():
    m = re.search(r"function guardarPrefs\(\) \{(.*?)\n\}", PAGINA, re.S)
    assert m, "guardarPrefs debe existir"
    cuerpo = m.group(1)
    for clave in ("pestana", "agrupar", "masFiltros", "f:"):
        assert clave in cuerpo, clave


def test_se_guarda_al_cambiar_filtros_pestana_y_plegado():
    assert re.search(r"function pintarLista\(\) \{\s*guardarPrefs\(\);", PAGINA)
    assert "S.masFiltros = e.target.open; guardarPrefs();" in PAGINA
    m = re.search(r"function pintar\(\) \{(.*?)\}", PAGINA)
    assert m and "pintarLista()" in m.group(1)


def test_al_restaurar_se_validan_los_valores():
    m = re.search(r"function cargarPrefs\(\) \{(.*?)\n\}", PAGINA, re.S)
    assert m
    cuerpo = m.group(1)
    assert "PESTANAS.some" in cuerpo                      # la pestaña debe existir
    assert 'p.agrupar === "prioridad" || p.agrupar === "fuente"' in cuerpo
    assert 'typeof p.masFiltros === "boolean"' in cuerpo
    assert "Object.keys(FILTROS_VACIOS())" in cuerpo      # solo claves de filtros conocidas
    assert 'typeof p.f[k] === "string"' in cuerpo


def test_la_carga_de_preferencias_va_antes_del_primer_pintado():
    assert PAGINA.index("cargarPrefs();") < PAGINA.index("cargar();\ncargarPuestos();")
