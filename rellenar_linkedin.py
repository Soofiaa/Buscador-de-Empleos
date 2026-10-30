"""Una vez (30-10-2026, decisión de Sofia): trae la descripción de las ofertas de LinkedIn postuladas que quedaron en
«Sin texto» y la guarda SOLO en raw.description, sin reclasificar: categoría, estado, fase y fecha no cambian, así la
postulación no sale del tablero aunque el texto pida más experiencia. Sirve para leerla y para el análisis con IA.

Uso (dentro del contenedor, con el contenedor real detenido y la referencia hecha, ver skill /desplegar):
    python rellenar_linkedin.py /datos/ofertas.db
"""
import json
import sys

import buscar
import linkedin
from red import Bloqueo, ClienteHTTP, ErrorFuente


class _SinRobots:
    """LinkedIn prohíbe todo en robots.txt; Sofia decidió pedir el detalle igual (como fetch_description en JobSpy)."""
    def bloqueo(self, _url): return ""
    def no_disponible(self, _url): return False
    def permitido(self, _url): return True


def pendientes(con) -> list:
    return [r["url"] for r in con.execute(
        "SELECT url FROM ofertas WHERE fuente = 'linkedin' AND categoria = 'sin_descripcion' AND estado = 'postulada' "
        "AND COALESCE(json_extract(raw, '$.description'), '') = '' ORDER BY url")]


def rellenar(con, obtener) -> dict:
    """obtener(url) -> texto. Un bloqueo detiene todo (no se insiste); otro error salta solo esa oferta."""
    hechas, fallidas = [], []
    for url in pendientes(con):
        try:
            texto = (obtener(url) or "").strip()[:buscar.LIMITE_DESCRIPCION]
        except Bloqueo as e:
            fallidas.append((url, "bloqueo: %s" % e))
            break
        except ErrorFuente as e:
            fallidas.append((url, str(e)))
            continue
        if not texto:
            fallidas.append((url, "sin texto"))
            continue
        with buscar.transaccion(con):
            raw = json.loads(con.execute("SELECT raw FROM ofertas WHERE url = ?", (url,)).fetchone()["raw"])
            raw["description"] = texto
            con.execute("UPDATE ofertas SET raw = ? WHERE url = ?", (json.dumps(raw, ensure_ascii=False), url))
        hechas.append(url)
    return {"hechas": hechas, "fallidas": fallidas}


if __name__ == "__main__":
    con = buscar.conectar(sys.argv[1])
    cliente, robots = ClienteHTTP(), _SinRobots()
    r = rellenar(con, lambda url: linkedin.detalle(url, cliente, robots)["descripcion"])
    print("hechas: %d, fallidas: %d" % (len(r["hechas"]), len(r["fallidas"])))
    for url, motivo in r["fallidas"]:
        print("  FALLÓ", url, "-", motivo)
