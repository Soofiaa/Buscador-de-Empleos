"""Movimiento reducido: quien lo pide en el sistema no ve transiciones ni animaciones de la página.

Verifica que la regla exista y cubra animaciones y transiciones; el efecto real en el navegador no se prueba aquí."""
import re
from pathlib import Path

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")


def test_existe_regla_de_movimiento_reducido():
    assert "@media (prefers-reduced-motion: reduce)" in PAGINA


def test_la_regla_cubre_animaciones_y_transiciones():
    i = PAGINA.index("@media (prefers-reduced-motion: reduce)")
    bloque = PAGINA[i:PAGINA.index("\n  }", i)]
    for prop in ("animation-duration", "animation-iteration-count", "transition-duration"):
        assert f"{prop}:" in bloque, prop
    assert "*, *::before, *::after" in bloque


def test_el_aviso_con_animacion_existe_y_queda_cubierto():
    # la animación de los avisos (slideUpToast) debe estar en el CSS para que la regla la apague
    assert re.search(r"animation:\s*slideUpToast", PAGINA)
