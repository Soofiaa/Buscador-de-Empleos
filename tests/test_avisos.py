"""Fase 3: avisos del navegador. La decisión (decidirAviso) se ejecuta con Node; el resto se verifica en la página."""
from pathlib import Path

import pytest

from test_historial import correr_js

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")


def decidir(previa, corrida, relevantes):
    return correr_js(f"return decidirAviso({'null' if previa is None else previa}, "
                     f"{'null' if corrida is None else corrida}, {relevantes});")


def test_primera_vez_solo_recuerda_no_avisa():
    # al abrir por primera vez no se avisa de lo que ya estaba en la base
    assert decidir(None, 5, 12) == {"avisar": False, "ultima": 5}


def test_corrida_nueva_con_relevantes_avisa_y_recuerda():
    assert decidir(5, 6, 3) == {"avisar": True, "ultima": 6}


def test_corrida_nueva_sin_relevantes_no_avisa_pero_recuerda():
    assert decidir(5, 6, 0) == {"avisar": False, "ultima": 6}


def test_corrida_ya_vista_no_avisa_ni_retrocede():
    assert decidir(6, 6, 4) == {"avisar": False, "ultima": 6}
    assert decidir(6, 4, 4) == {"avisar": False, "ultima": 6}


def test_sin_corrida_no_cambia_nada():
    assert decidir(5, None, 3) == {"avisar": False, "ultima": 5}
    assert decidir(None, None, 3) == {"avisar": False, "ultima": None}


def test_la_pagina_tiene_el_panel_de_avisos_y_el_sondeo():
    assert 'id="avisos"' in PAGINA
    assert "function revisarAvisos(" in PAGINA and "function pintarAvisos(" in PAGINA
    assert 'setInterval(() => { if (!sondeo) estado(); }, 60000)' in PAGINA
    assert 'if (!e.buscando) revisarAvisos(S.ultima);' in PAGINA


def test_avisos_solo_con_mensaje_de_texto_seguro():
    # la página no usa innerHTML: los textos van con h() o textContent
    assert "innerHTML" not in PAGINA


def test_avisos_no_piden_permiso_sin_gesto_del_usuario():
    # el permiso solo se pide dentro del clic del botón
    assert PAGINA.count("Notification.requestPermission()") == 1
    antes_del_clic = PAGINA[: PAGINA.index("Notification.requestPermission()")]
    assert "onclick: async () =>" in antes_del_clic[-600:]
