"""La página (un solo archivo HTML con CSS y JS): web/pagina.html. Los datos llegan por /api/ofertas y se pintan con
el DOM (textContent, nunca HTML armado con texto), así que ningún texto de un aviso puede inyectar código en la página.
Las tipografías se sirven desde la propia app (/fuentes/, font-src 'self'): la CSP no deja cargar nada de afuera."""
from pathlib import Path

RUTA_PAGINA = Path(__file__).resolve().parent / "web" / "pagina.html"
PAGINA = RUTA_PAGINA.read_text(encoding="utf-8")
