"""rellenar_aviso con navegador: solo se abre si robots.txt permitió la URL y la página llegó vacía (JavaScript)."""
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rellenar_aviso
from red import Bloqueo, ErrorFuente

PAGINA_JS = b"""<html><body><div id="x"></div><script>
document.getElementById('x').innerHTML = '<h1>Analista de Datos Junior</h1><p>Empresa Acme, Santiago, Chile. ' + 'Buscamos profesional con SQL y Python para reportes de gestion. '.repeat(8) + '</p>';
</script></body></html>"""


class Robots:
    def __init__(self, bloqueado=False):
        self.bloqueado = bloqueado

    def bloqueo(self, url):
        return "HTTP 403" if self.bloqueado else ""

    def no_disponible(self, url):
        return False

    def permitido(self, url):
        return not self.bloqueado


def test_no_abre_navegador_si_robots_no_permite(monkeypatch):
    llamado = []
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: llamado.append(u) or "")
    with pytest.raises(Bloqueo):
        rellenar_aviso.desde_url("https://ejemplo.cl/1", None, Robots(bloqueado=True))
    assert llamado == []


def test_pagina_vacia_usa_navegador_y_luego_la_ia(monkeypatch):
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda u, c, r: "<html><body><div id=x></div></body></html>")
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador",
                        lambda u: "<html><body><h1>Analista QA</h1>" + "<p>texto del aviso</p>" * 30 + "</body></html>")
    visto = {}
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso",
                        lambda t: visto.setdefault("t", t) and {"titulo": "Analista QA", "empresa": "X"})
    r = rellenar_aviso.desde_url("https://ejemplo.cl/1", None, Robots())
    assert r["titulo"] == "Analista QA" and "Analista QA" in visto["t"]


def test_pagina_con_texto_no_abre_navegador(monkeypatch):
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda u, c, r: "<body>" + "<p>texto suficiente del aviso</p>" * 20 + "</body>")
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: pytest.fail("no debía abrir navegador"))
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso", lambda t: {"titulo": "X", "empresa": "Y"})
    assert rellenar_aviso.desde_url("https://ejemplo.cl/1", None, Robots())["empresa"] == "Y"


def test_navegador_real_renderiza_javascript():
    """Playwright de verdad contra un servidor local: el texto aparece solo después de ejecutar el JavaScript."""
    pytest.importorskip("playwright.sync_api")

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGINA_JS)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/aviso"
    try:
        try:
            html = rellenar_aviso.html_con_navegador(url)
        except ErrorFuente as ex:
            if "Executable doesn't exist" in str(ex) or "playwright install" in str(ex):
                pytest.skip("Chromium de Playwright no instalado en este equipo")
            raise
    finally:
        srv.shutdown()
        srv.server_close()
    assert "Analista de Datos Junior" in html
