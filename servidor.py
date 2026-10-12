"""Servidor local de la página de ofertas (reemplaza al Excel).

  GET  /                  la página
  GET  /api/ofertas       {principal, fuera_perfil, sospechosas, descartadas, total_descartadas, corridas}
                          corridas = [{id, inicio, fin, nuevas, fuentes}], la más reciente primero; cada oferta
                          lleva corrida_id (la corrida cuyo inicio <= detectada_en <= fin, o null)
  GET  /api/estado        {buscando, mensaje, error, corrida}   (corrida = resumen de la última búsqueda)
  POST /api/buscar        inicia una búsqueda en segundo plano (409 si ya hay una en curso)
  POST /api/marcar        {"url": str, "estado": "nueva|revisada|postulada|entrevista|descartada"}

Seguridad (heredada de la app anterior): solo atiende peticiones cuyo Host u Origin sean locales, de modo que otra
página abierta en tu navegador no pueda mandarle órdenes ni leer tus resultados. En Docker escucha en 0.0.0.0
DENTRO del contenedor, pero el puerto se publica únicamente en 127.0.0.1 (ver docker-compose.yml).

Uso:  python servidor.py [--puerto 8765] [--no-abrir]
"""
import argparse
import json
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import buscar
import config
from informe import PAGINA

LOCALES = ("127.0.0.1", "localhost", "[::1]")
LIMITE_CUERPO = 10_000


def _host_local(valor: str) -> bool:
    host = (valor or "").split("://")[-1].split("/")[0]
    if host.startswith("["):
        host = host[:host.index("]") + 1] if "]" in host else host
    else:
        host = host.rsplit(":", 1)[0] if ":" in host else host
    return host in LOCALES


class Aplicacion:
    def __init__(self, ruta_db=None, buscar_fn=None):
        self.ruta_db = ruta_db or config.DB_PATH
        self.buscar_fn = buscar_fn or buscar.buscar_ofertas
        self._lock = threading.Lock()
        self.estado = {"buscando": False, "mensaje": "", "error": ""}
        self.hilo = None

    def conexion(self):                       # una conexión por petición/hilo
        return buscar.conectar(self.ruta_db)

    def snapshot(self) -> dict:
        with self._lock:
            est = dict(self.estado)
        con = self.conexion()
        try:
            est["corrida"] = buscar.ultima_corrida(con)
        finally:
            con.close()
        return est

    def _set(self, **kw):
        with self._lock:
            self.estado.update(kw)

    def iniciar_busqueda(self) -> bool:
        with self._lock:
            if self.estado["buscando"]:
                return False
            self.estado.update(buscando=True, mensaje="Iniciando la búsqueda...", error="")
        self.hilo = threading.Thread(target=self._correr, daemon=True)
        self.hilo.start()
        return True

    def _correr(self):
        con = self.conexion()
        anterior = buscar.salida
        buscar.salida = lambda m: self._set(mensaje=str(m).strip().splitlines()[-1] if str(m).strip() else "")
        try:
            nuevas = self.buscar_fn(con)
            self._set(buscando=False, mensaje=f"Búsqueda terminada: {nuevas} ofertas relevantes nuevas.", error="")
        except Exception as ex:               # un fallo no deja el botón bloqueado
            self._set(buscando=False, error="%s: %s" % (type(ex).__name__, ex))
        finally:
            buscar.salida = anterior
            con.close()


def crear_servidor(app: Aplicacion, puerto: int = None, host: str = None) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        server_version = "JobTracker"

        def log_message(self, *a):
            pass

        def _enviar(self, codigo, cuerpo: bytes, tipo="application/json; charset=utf-8"):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, codigo, obj):
            self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

        def _permitido(self) -> bool:
            origen = self.headers.get("Origin")
            return _host_local(self.headers.get("Host", "")) and (origen is None or _host_local(origen))

        def do_GET(self):
            if not self._permitido():
                return self._json(403, {"error": "origen no permitido"})
            ruta = urllib.parse.urlsplit(self.path).path
            if ruta == "/":
                return self._enviar(200, PAGINA.encode("utf-8"), "text/html; charset=utf-8")
            if ruta == "/api/estado":
                return self._json(200, app.snapshot())
            if ruta == "/api/ofertas":
                con = app.conexion()
                try:
                    return self._json(200, buscar.ofertas_para_pagina(con))
                finally:
                    con.close()
            self._json(404, {"error": "no existe"})

        def do_POST(self):
            # el cuerpo se lee ANTES de rechazar: responder sin leerlo hace que Windows a veces corte la conexión
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                crudo = self.rfile.read(min(max(largo, 0), LIMITE_CUERPO))
            except ValueError:
                crudo = b""
            if not self._permitido():
                return self._json(403, {"error": "origen no permitido"})
            ruta = urllib.parse.urlsplit(self.path).path
            try:
                datos = json.loads(crudo or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido"})
            if ruta == "/api/buscar":
                if app.iniciar_busqueda():
                    return self._json(202, {"ok": True})
                return self._json(409, {"error": "ya hay una búsqueda en curso"})
            if ruta == "/api/marcar":
                if not isinstance(datos, dict):
                    return self._json(400, {"error": "formato inválido"})
                con = app.conexion()
                try:
                    ok = buscar.marcar_estado(con, str(datos.get("url") or ""), str(datos.get("estado") or ""))
                finally:
                    con.close()
                return self._json(200 if ok else 400, {"ok": ok} if ok else {"error": "estado u oferta no válidos"})
            self._json(404, {"error": "no existe"})

    return ThreadingHTTPServer((host or config.HOST, puerto or config.PUERTO), Manejador)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--puerto", type=int, default=config.PUERTO)
    ap.add_argument("--no-abrir", action="store_true", help="no abrir el navegador al iniciar")
    args = ap.parse_args()
    app = Aplicacion()
    app.conexion().close()                    # crea/migra la base antes de atender
    srv = crear_servidor(app, args.puerto)
    url = f"http://127.0.0.1:{args.puerto}/"
    print(f"Página de ofertas en {url}  (Ctrl+C para cerrar)")
    if not args.no_abrir and config.HOST == "127.0.0.1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
