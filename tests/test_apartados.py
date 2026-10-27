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
    # Ofertas y Seguimiento comparten la vista de lista (encabezado, pestañas, filtros y lista)
    lista = PAGINA.index('id="vista-lista"')
    fin = PAGINA.index("</section>", lista)
    for parte in ('id="titulo-sel"', 'id="pestanas"', 'id="filtros"', 'id="lista"'):
        assert lista < PAGINA.index(parte) < fin
    # Métricas y Ajustes tienen su sección, oculta al cargar sin #hash
    for ident in ("metricas", "ajustes"):
        etiqueta = PAGINA[PAGINA.index(f'id="apartado-{ident}"'):]
        assert " hidden>" in etiqueta[: etiqueta.index(">") + 1]
    assert 'id="apartado-seguimiento"' not in PAGINA and 'id="ir-seguimiento"' not in PAGINA


def test_paso3_seguimiento_es_apartado_y_no_pestana():
    pestanas = PAGINA[PAGINA.index("const PESTANAS = ["):]
    pestanas = pestanas[: pestanas.index("];")]
    assert '"seguimiento"' not in pestanas and '"ofertas"' in pestanas
    assert 'const vista = () => S.apartado === "seguimiento" ? "seguimiento" : S.pestana;' in PAGINA
    assert '$("pestanas").hidden = S.apartado !== "ofertas";' in PAGINA
    # lo que pinta la lista usa vista(), no la pestaña de Ofertas
    for trozo in ('listaDe(S.datos, vista(), S.sel).filter(pasa)', 'const cabecera = vista() === "seguimiento"',
                  'AYUDA_PESTANA[S.apartado === "metricas"'):
        assert trozo in PAGINA
    # una preferencia vieja con la pestaña «seguimiento» abre el apartado
    assert 'else if (p.pestana === "seguimiento" && !location.hash) S.apartado = "seguimiento";' in PAGINA
    # elegir una búsqueda del historial desde otro apartado vuelve a Ofertas
    elegir = PAGINA[PAGINA.index("function elegir(sel) {"):]
    assert 'irApartado("ofertas", false)' in elegir[:300]


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


def test_paso4_datos_y_apariencia_viven_en_ajustes():
    inicio = PAGINA.index('id="apartado-ajustes"')
    fin = PAGINA.index("</main>")
    for ident in ("tema", "contraste-aa", "avisos", "btn-exportar-csv", "btn-exportar-csv-seg",
                  "btn-exportar-json", "btn-respaldo", "estado-respaldo"):
        marca = f'id="{ident}"'
        assert PAGINA.count(marca) == 1 and inicio < PAGINA.index(marca) < fin, ident
    assert "aviso-provisional" not in PAGINA
    # el menú izquierdo queda con lo de todos los días
    lateral = PAGINA[PAGINA.index('<aside class="lateral">'):PAGINA.index("</aside>")]
    for ident in ("menu", "ultima", "buscar", "progreso", "busquedas-manuales", "historial", "estado-db"):
        assert f'id="{ident}"' in lateral, ident
    assert "seccion-lateral-titulo" not in lateral
    # cada botón de CSV exporta lo suyo, sin depender del apartado abierto
    assert 'descargar("csv", alcanceExportar("ofertas"))' in PAGINA
    assert 'descargar("csv", alcanceExportar("seguimiento"))' in PAGINA


def test_seguimiento_tiene_un_solo_selector_de_vista():
    # Tablero · Tarjetas · Compacta en un grupo; el de densidad de los filtros no sale en Seguimiento
    sel = PAGINA[PAGINA.index("function selectorVista() {"):]
    sel = sel[: sel.index("\n}\n")]
    for clave in ('boton("tablero"', 'boton("detallada"', 'boton("compacta"'):
        assert clave in sel
    assert 'if (vista() !== "seguimiento") partes.push(h("div", { class: "selector-vista", role: "group", "aria-label": "Densidad de vista" }' in PAGINA
    assert 'const opcionVistaSeg = () => S.vistaSeg === "tablero" ? "tablero" : S.densidad;' in PAGINA


def test_ayuda_de_cada_apartado_y_textos_al_dia():
    # Métricas y Ajustes tienen su botón de ayuda y su texto; Ofertas y Seguimiento, el suyo
    for ident in ("metricas", "ajustes"):
        inicio = PAGINA.index(f'id="apartado-{ident}"')
        assert 'btn-ayuda-pantalla' in PAGINA[inicio:PAGINA.index("</section>", inicio)]
    assert PAGINA.count('id="btn-ayuda"') == 1
    assert 'for (const b of document.querySelectorAll("#btn-ayuda, .btn-ayuda-pantalla"))' in PAGINA
    assert "metricas: { titulo:" in PAGINA and "ajustes: { titulo:" in PAGINA
    # los textos nombran lo que hay hoy: el selector de vista de Seguimiento y las secciones de Ajustes
    assert "Arriba eliges cómo verlas: Tablero, Tarjetas o Compacta" in PAGINA
    assert "Qué busco" in PAGINA and "Apariencia y avisos" in PAGINA
    assert 'AYUDA_PESTANA[S.apartado === "metricas" || S.apartado === "ajustes" ? S.apartado : vista()]' in PAGINA


def test_navegacion_por_hash_y_atajo_vuelve_a_ofertas():
    assert 'window.addEventListener("hashchange"' in PAGINA
    assert 'S.apartado = apartadoDeHash(location.hash);' in PAGINA
    assert 'if (SECCION_APARTADO[S.apartado] !== "vista-lista") { irApartado("ofertas", false);' in PAGINA
    assert '"aria-current": S.apartado === id ? "page" : null' in PAGINA
