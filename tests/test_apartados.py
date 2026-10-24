"""Rediseño, paso 1: menú de apartados con navegación por #hash. apartadoDeHash se ejecuta con Node."""
import json
from pathlib import Path

import pytest

from test_historial import correr_js

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")
IDS = ["ofertas", "seguimiento", "metricas", "ajustes"]


def apartado(hash_):
    return correr_js(f"return apartadoDeHash({json.dumps(hash_)});")


@pytest.mark.parametrize("ident", IDS)
def test_cada_hash_valido_elige_su_apartado(ident):
    assert apartado("#" + ident) == ident
    assert apartado(ident) == ident


@pytest.mark.parametrize("hash_", ["", "#", "#otra", "#ofertas/x", None, "#%E0%A4%A"])
def test_hash_vacio_o_desconocido_lleva_a_ofertas(hash_):
    assert apartado(hash_) == "ofertas"


def test_hash_tolera_mayusculas_espacios_y_codificacion():
    assert apartado("#Metricas") == "metricas"
    assert apartado("# ajustes ") == "ajustes"
    assert apartado("#%73eguimiento") == "seguimiento"


def test_hay_cuatro_apartados_en_orden():
    assert correr_js("return APARTADOS.map(a => a[0]);") == IDS


def test_la_pagina_tiene_menu_y_una_seccion_por_apartado():
    assert 'id="menu"' in PAGINA
    menu = PAGINA.index('id="menu"')
    assert PAGINA.index('class="lateral"') < menu < PAGINA.index('<main class="principal">')
    for ident in IDS:
        assert f'id="apartado-{ident}"' in PAGINA
    # la vista de siempre (encabezado, pestañas, filtros y lista) vive dentro de Ofertas
    ofertas = PAGINA.index('id="apartado-ofertas"')
    fin = PAGINA.index("</section>", ofertas)
    for parte in ('id="titulo-sel"', 'id="pestanas"', 'id="filtros"', 'id="lista"'):
        assert ofertas < PAGINA.index(parte) < fin
    # solo Ofertas se ve al cargar sin #hash
    for ident in IDS[1:]:
        etiqueta = PAGINA[PAGINA.index(f'id="apartado-{ident}"'):]
        assert " hidden>" in etiqueta[: etiqueta.index(">") + 1]


DATOS = {
    "principal": [{"estado": "postulada", "corrida_id": 45}, {"estado": "descartada", "corrida_id": 45}],
    "sin_descripcion": [{"estado": "nueva", "corrida_id": 45}, {"estado": "descartada", "corrida_id": 44}],
    "corridas": [{"id": 45, "inicio": "2026-10-23 19:00"}, {"id": 44, "inicio": "2026-10-22 10:00"}],
}


def test_ofertas_cuenta_las_sin_texto_pendientes_aunque_no_haya_otras():
    # el caso «Ofertas 0» con «2 relevantes nuevas»: la única pendiente llegó sin texto (LinkedIn)
    datos = json.dumps(DATOS)
    assert correr_js(f'return listaDe({datos}, "ofertas", {{tipo: "todas"}}).length;') == 0
    assert correr_js(f'return totalOfertas({datos}, {{tipo: "todas"}});') == 1
    assert correr_js(f'return totalOfertas({datos}, {{tipo: "hora", id: 44}});') == 0


def test_lista_de_ofertas_muestra_sin_texto_aunque_la_principal_este_vacia():
    assert "if (!filas.length && !sinTextoFilas.length) {" in PAGINA
    assert 'listaDe(S.datos, "sin_descripcion", S.sel).filter(pasa)' in PAGINA


def test_paso2_sin_barra_derecha_puestos_y_exclusiones_en_ajustes():
    assert "lateral-derecha" not in PAGINA
    inicio = PAGINA.index('id="apartado-ajustes"')
    fin = PAGINA.index("</main>")
    for panel in ('id="puestos-panel"', 'id="exclusiones-panel"'):
        assert PAGINA.count(panel) == 1 and inicio < PAGINA.index(panel) < fin


def test_navegacion_por_hash_y_atajo_vuelve_a_ofertas():
    assert 'window.addEventListener("hashchange"' in PAGINA
    assert 'S.apartado = apartadoDeHash(location.hash);' in PAGINA
    assert 'if (S.apartado !== "ofertas") { irApartado("ofertas", false);' in PAGINA
    assert '"aria-current": S.apartado === id ? "page" : null' in PAGINA
