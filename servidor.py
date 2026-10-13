"""Servidor local de la página de ofertas (reemplaza al Excel).

  GET  /                  la página
  GET  /api/ofertas       {principal, fuera_perfil, sospechosas, descartadas, total_descartadas, corridas}
                          corridas = [{id, inicio, fin, nuevas, fuentes}], la más reciente primero; cada oferta
                          lleva corrida_id (la corrida cuyo inicio <= detectada_en <= fin, o null)
  GET  /fuentes/<archivo> las tipografías (solo las de la lista FUENTES; la CSP permite font-src 'self')
  GET  /api/estado        {buscando, mensaje, error, corrida, total_ofertas}   (corrida = resumen de la última búsqueda)
  POST /api/buscar        inicia una búsqueda en segundo plano (409 si ya hay una en curso)
  POST /api/marcar        {"url", "estado"} -> {ok, anterior, actual} con estado y fecha_postulacion (la fecha se pone sola
                          al pasar a postulada/entrevista si estaba vacía). Deshacer: {"url", "restaurar": {estado,
                          fecha_postulacion, si_actual: {estado, fecha_postulacion}}}; 409 si la oferta cambió entre medias
  POST /api/nota          {"url", y solo lo que cambia: notas (<=5000), fecha_postulacion (AAAA-MM-DD o ""), fase,
                          sueldo_manual (<=100), prioridad_manual ("", Alta, Media, Baja)} -> {ok, oferta}
  GET  /api/ajustes/soporte  {incluir}: si la categoría Soporte TI se muestra en Ofertas
  POST /api/ajustes/soporte  {"incluir": true|false} (nada más) -> {ok, incluir}
  Errores: 400 pedido inválido, 404 oferta inexistente, 503 "base ocupada, reintenta" (no se escribió nada)

Seguridad (heredada de la app anterior): solo atiende peticiones cuyo Host u Origin sean locales, de modo que otra
página abierta en tu navegador no pueda mandarle órdenes ni leer tus resultados. En Docker escucha en 0.0.0.0
DENTRO del contenedor, pero el puerto se publica únicamente en 127.0.0.1 (ver docker-compose.yml).

Uso:  python servidor.py [--puerto 8765] [--no-abrir]
"""
import argparse
import json
import sqlite3
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import buscar
import config
from informe import PAGINA

LOCALES = ("127.0.0.1", "localhost", "[::1]")
LIMITE_CUERPO = 10_000
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src 'self'; "
       "connect-src 'self'; form-action 'none'; base-uri 'none'")
# Solo estos archivos se sirven bajo /fuentes/ (nada de rutas armadas con lo que pida el navegador)
DIR_FUENTES = Path(__file__).resolve().parent / "web" / "fuentes"
FUENTES = {n: DIR_FUENTES / n for n in ("outfit-latin-wght-normal-5.3.0.woff2",
                                        "plus-jakarta-sans-latin-wght-normal-5.3.0.woff2")}


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
            est["total_ofertas"] = con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0]
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
            self._set(buscando=False, error="", mensaje="Búsqueda terminada: "
                      + buscar.plural(nuevas, "oferta relevante nueva", "ofertas relevantes nuevas") + ".")
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

        def _enviar(self, codigo, cuerpo: bytes, tipo="application/json; charset=utf-8", cache="no-store"):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", CSP)
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
            if ruta.startswith("/fuentes/"):
                archivo = FUENTES.get(ruta[len("/fuentes/"):])
                if archivo is None or not archivo.is_file():
                    return self._json(404, {"error": "no existe"})
                # el nombre lleva la versión: si cambia la fuente, cambia la URL, así que se puede guardar un año
                return self._enviar(200, archivo.read_bytes(), "font/woff2", "public, max-age=31536000, immutable")
            if ruta == "/api/estado":
                return self._json(200, app.snapshot())
            if ruta == "/api/ofertas":
                con = app.conexion()
                try:
                    return self._json(200, buscar.ofertas_para_pagina(con))
                finally:
                    con.close()
            if ruta == "/api/ajustes/soporte":
                con = app.conexion()
                try:
                    return self._json(200, {"incluir": buscar.leer_ajuste(con, "soporte")["incluir"]})
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
            escrituras = {
                "/api/marcar": lambda con, d: buscar.marcar(con, d.get("url"), d.get("estado"), d.get("restaurar")),
                "/api/nota": lambda con, d: {"oferta": buscar.actualizar_seguimiento(
                    con, d.get("url"), {k: v for k, v in d.items() if k != "url"})},
                "/api/ajustes/soporte": lambda con, d: buscar.guardar_soporte(con, d),
            }
            if ruta in escrituras:
                if not isinstance(datos, dict):
                    return self._json(400, {"error": "formato inválido"})
                try:
                    con = app.conexion()
                    try:
                        resultado = escrituras[ruta](con, datos)
                    finally:
                        con.close()
                except buscar.ErrorDatos as ex:
                    return self._json(ex.codigo, {"error": str(ex)})
                except (buscar.BaseOcupada, sqlite3.OperationalError) as ex:
                    if isinstance(ex, buscar.BaseOcupada) or buscar.es_base_ocupada(ex):
                        return self._json(503, {"error": "base ocupada, reintenta"})
                    raise
                return self._json(200, {"ok": True, **resultado})
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
