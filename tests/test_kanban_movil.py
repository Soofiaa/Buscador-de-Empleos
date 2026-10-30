"""Tablero en pantalla angosta: las columnas se apilan (sin deslizar de lado) y «Mover a…» sigue presente en cada tarjeta.

Verifica la forma del CSS y de la plantilla; el aspecto visual real no se prueba aquí (no hay navegador en esta sesión)."""
import re
from pathlib import Path

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")


def bloque_movil():
    # la regla del tablero se identifica por su comentario, no por posición (hay otras reglas de 620px)
    i = PAGINA.index("las columnas se apilan")
    inicio = PAGINA.rindex("@media (max-width:620px)", 0, i)
    fin = PAGINA.index("\n  }", i)
    return PAGINA[inicio:fin]


def test_el_tablero_angosto_apila_las_columnas_sin_deslizar():
    b = bloque_movil()
    assert ".kanban-board { grid-template-columns:minmax(0, 1fr); overflow-x:visible; }" in b
    assert "scroll-snap" not in b                       # ya no se desliza de lado


def test_el_tablero_angosto_no_usa_el_deslizamiento_viejo():
    assert "repeat(4, min(82vw, 300px))" not in PAGINA
    assert "scroll-snap-type:x mandatory" not in PAGINA


def test_mover_a_sigue_en_cada_tarjeta():
    # la alternativa al arrastre (que no funciona con el dedo) no depende del ancho
    assert 'h("option", { value: "" }, "Mover a…")' in PAGINA
    assert "aria-label\": \"Mover a… (\" + titulo + \")\"" in PAGINA
