"""Servidor local de la página de ofertas (reemplaza al Excel).

  GET  /                  la página
  GET  /api/ofertas       {principal, sin_descripcion, fuera_perfil, sospechosas, descartadas, total_descartadas,
                          corridas}   (sin_descripcion: llegaron sin descripción; las revisa Sofia, ver filtros.py)
                          corridas = [{id, inicio, fin, nuevas, fuentes}], la más reciente primero; cada oferta
                          lleva corrida_id (la corrida cuyo inicio <= detectada_en <= fin, o null)
  GET  /fuentes/<archivo> las tipografías (solo las de la lista FUENTES; la CSP permite font-src 'self')
  GET  /api/estado        {buscando, mensaje, error, corrida, total_ofertas}   (corrida = resumen de la última búsqueda)
  POST /api/buscar        inicia una búsqueda en segundo plano (409 si ya hay una en curso)
  POST /api/marcar        {"url", "estado", "fase" (opcional), "origen": tablero|lista|modal} -> {ok, anterior, actual}
                          con estado, fase y fecha_postulacion, escritos en UNA transacción y registrados en
                          historial_estados (la fecha se pone sola al pasar a postulada/entrevista si estaba vacía).
                          Deshacer: {"url", "restaurar": {estado, fecha_postulacion, fase, si_actual: {...}}}; el
                          origen lo fija el servidor ('deshacer'); 409 si la oferta cambió entre medias
  POST /api/nota          {"url", y solo lo que cambia: notas (<=5000), fecha_postulacion (AAAA-MM-DD o "", no futura;
                          queda en el historial), sueldo_manual (<=100), prioridad_manual ("", Alta, Media, Baja)}
                          -> {ok, oferta}. estado o fase aquí -> 400 (se cambian con /api/marcar)
  POST /api/descripcion   {"url", "descripcion"} (<=10000): pega el texto de un aviso de «Sin texto» y lo reclasifica
                          solo a esa oferta -> {ok, categoria, razon, experiencia}. Otra oferta -> 400; no existe -> 404
  GET  /api/ofertas       ... y cada oferta principal trae en_fase_desde (UTC) según su historial, o null
  GET  /api/ajustes/soporte  {incluir}: si la categoría Soporte TI se muestra en Ofertas
  POST /api/ajustes/soporte  {"incluir": true|false} (nada más) -> {ok, incluir}
  GET  /api/ajustes/puestos  {lista}: los puestos que busca Indeed (guardados o los de config)
  POST /api/ajustes/puestos  {"lista": [...]} (nada más) -> {ok, lista}; validación en puestos.py
  POST /api/oferta/manual  {titulo, empresa (obligatorios), url (http/https), ubicacion, modalidad, estado,
                          fecha_postulacion, notas, fase, sueldo_manual, prioridad_manual} -> 201 {ok, oferta};
                          409 {error, url_existente} si la URL o la misma oferta (cargo+empresa+ciudad) ya existe
  GET  /api/exportar?formato=csv|json&alcance=seguimiento|principal|todas  descarga (attachment); el CSV protege
                          las celdas que empiezan con = + - @ tab CR; columnas de una lista cerrada (sin raw)
  Límite de cuerpo: 10 KB, 64 KB en /api/nota y /api/oferta/manual; más grande -> 413
  GET  /api/respaldo       estado del respaldo (configurado, disponible, último, error)
  POST /api/respaldo       {} -> 201 {ok, respaldo}; 429 si hubo otro hace < 1 min; 503 carpeta no disponible;
                          507 sin espacio en disco
  Errores: 400 pedido inválido, 404 oferta inexistente, 503 "base ocupada, reintenta" (no se escribió nada)

Seguridad (heredada de la app anterior): solo atiende peticiones cuyo Host u Origin sean locales, de modo que otra
página abierta en tu navegador no pueda mandarle órdenes ni leer tus resultados. En Docker escucha en 0.0.0.0
DENTRO del contenedor, pero el puerto se publica únicamente en 127.0.0.1 (ver docker-compose.yml).

Uso:  python servidor.py [--puerto 8765] [--no-abrir]
"""
import argparse
import json
import signal
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import buscar
import config
import respaldo
from informe import PAGINA

LOCALES = ("127.0.0.1", "localhost", "[::1]")
LIMITE_CUERPO = 10_000
# rutas con textos largos: 5000 caracteres con tildes o emojis ocupan más de 10 KB en UTF-8
LIMITES_POR_RUTA = {"/api/nota": 64_000, "/api/oferta/manual": 64_000, "/api/descripcion": 64_000}   # 5000 caracteres x 12 bytes si el cliente los escapa como \uXXXX
MAXIMO_A_DESCARTAR = 1_000_000      # un cuerpo demasiado grande se lee (hasta aquí) y se descarta antes del 413
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src 'self'; "
       "connect-src 'self'; form-action 'none'; base-uri 'none'")
# Al apagar (docker stop / compose stop manda SIGTERM; stop_grace_period: 15s en docker-compose.yml): se espera un
# respaldo en curso y se consolida el -wal, cada cosa con su límite (5 + 3 s, con margen antes del SIGKILL).
ESPERA_RESPALDO_S = 5
LIMITE_CHECKPOINT_S = 3


def _log(mensaje: str) -> None:              # a stderr: queda en `docker logs`
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {mensaje}", file=sys.stderr, flush=True)


def cerrar_base(ruta_db: str, limite_s: float = LIMITE_CHECKPOINT_S) -> bool:
    """Consolida el -wal en la base (PRAGMA wal_checkpoint(TRUNCATE)) con límite de tiempo. Si falla, la base está
    ocupada o se agota el tiempo, no insiste: deja el motivo en stderr y sigue (SQLite recupera el -wal al abrir).
    True si quedó consolidado."""
    try:
        con = sqlite3.connect(ruta_db, timeout=min(2.0, limite_s))   # espera máxima por un bloqueo
    except sqlite3.Error as ex:
        _log(f"cierre: no se pudo abrir la base para consolidar el -wal ({type(ex).__name__}: {ex})")
        return False
    corte = threading.Timer(limite_s, con.interrupt)                   # tope duro, pase lo que pase
    corte.start()
    try:
        ocupada, paginas, copiadas = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if ocupada:
            _log(f"cierre: el -wal no se consolidó del todo: base ocupada ({copiadas} de {paginas} páginas)")
            return False
        return True
    except sqlite3.Error as ex:
        _log(f"cierre: el -wal no se consolidó ({type(ex).__name__}: {ex})")
        return False
    finally:
        corte.cancel()
        con.close()


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
    def __init__(self, ruta_db=None, buscar_fn=None, carpeta_respaldos=None, reloj=None):
        self.ruta_db = ruta_db or config.DB_PATH
        self.buscar_fn = buscar_fn or buscar.buscar_ofertas
        self._lock = threading.Lock()
        self.estado = {"buscando": False, "mensaje": "", "error": ""}
        self.hilo = None
        self.carpeta_respaldos = config.RESPALDOS_DIR if carpeta_respaldos is None else carpeta_respaldos
        self.reloj = reloj or buscar.ahora_chile         # inyectable: las pruebas usan un reloj simulado
        self._lock_respaldo = threading.Lock()
        self._ultimo_manual = 0.0                          # time.monotonic() del último "Respaldar ahora"
        self.error_respaldo_auto = ""

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
        # locked() solo mira el turno, no lo toma: nunca demora ni hace fallar un "Respaldar ahora". Con un respaldo en
        # curso no se cuentan incompletos (su .db puede estar, por milisegundos, antes que su .sha256)
        en_curso = self._lock_respaldo.locked()
        est["respaldo"] = {**respaldo.estado(self.carpeta_respaldos), "error_auto": self.error_respaldo_auto,
                           "en_curso": en_curso}
        if en_curso and "incompletos" in est["respaldo"]:
            est["respaldo"]["incompletos"] = None
        return est

    def respaldar_ahora(self) -> dict:
        """Botón "Respaldar ahora": como mucho uno por minuto."""
        with self._lock_respaldo:
            if time.monotonic() - self._ultimo_manual < 60:
                raise buscar.ErrorDatos(429, "ya hiciste un respaldo hace menos de un minuto")
            hecho = respaldo.respaldar(self.ruta_db, self.carpeta_respaldos, "manual", self.reloj())
            self._ultimo_manual = time.monotonic()
            return hecho

    def revisar_respaldo_diario(self):
        """Una pasada del respaldo automático: si hoy no hay uno, lo hace. Nunca lanza: anota el error para la página."""
        if not self.carpeta_respaldos:
            return None
        try:
            with self._lock_respaldo:
                ahora = self.reloj()
                respaldo._carpeta_lista(self.carpeta_respaldos)
                if respaldo.hay_auto_de_hoy(self.carpeta_respaldos, ahora):
                    self.error_respaldo_auto = ""
                    return None
                hecho = respaldo.respaldar(self.ruta_db, self.carpeta_respaldos, "auto", ahora)
            self.error_respaldo_auto = ""
            return hecho
        except Exception as ex:                             # el servidor sigue atendiendo pase lo que pase
            self.error_respaldo_auto = f"{type(ex).__name__}: {ex}"
            _log(f"respaldo automático falló: {self.error_respaldo_auto}")
            return None

    def iniciar_respaldo_diario(self, cada_s: int = 3600):
        parar = threading.Event()
        def bucle():
            while not parar.is_set():
                self.revisar_respaldo_diario()
                parar.wait(cada_s)
        threading.Thread(target=bucle, daemon=True, name="respaldo-diario").start()
        return parar

    def apagar(self, espera_respaldo_s: float = ESPERA_RESPALDO_S, limite_checkpoint_s: float = LIMITE_CHECKPOINT_S):
        """Cierre ordenado: espera (con límite) el respaldo en curso y se queda con su turno, para que no empiece otro;
        después consolida el -wal. Un respaldo que no alcanza a terminar queda como temporal (.tmp-), nunca válido.
        La búsqueda no se espera (puede durar minutos): su hilo es daemon y lo no confirmado lo deshace SQLite."""
        if not self._lock_respaldo.acquire(timeout=espera_respaldo_s):
            _log(f"cierre: el respaldo en curso no terminó en {espera_respaldo_s:g} s; se cierra igual "
                 "(queda como temporal, nunca como respaldo válido)")
        return cerrar_base(self.ruta_db, limite_checkpoint_s)

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

        def _enviar(self, codigo, cuerpo: bytes, tipo="application/json; charset=utf-8", cache="no-store", extra=None):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
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
            if ruta == "/api/exportar":
                consulta = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                con = app.conexion()
                try:
                    cuerpo, tipo, nombre = buscar.exportar(con, (consulta.get("formato") or ["csv"])[0],
                                                           (consulta.get("alcance") or ["principal"])[0])
                except buscar.ErrorDatos as ex:
                    return self._json(ex.codigo, {"error": str(ex)})
                finally:
                    con.close()
                return self._enviar(200, cuerpo, tipo, extra={"Content-Disposition": f'attachment; filename="{nombre}"'})
            if ruta == "/api/respaldo":
                return self._json(200, app.snapshot()["respaldo"])
            if ruta == "/api/ajustes/soporte":
                con = app.conexion()
                try:
                    return self._json(200, {"incluir": buscar.leer_ajuste(con, "soporte")["incluir"]})
                finally:
                    con.close()
            if ruta == "/api/ajustes/puestos":
                con = app.conexion()
                try:
                    return self._json(200, {"lista": buscar.leer_puestos(con)})
                finally:
                    con.close()
            self._json(404, {"error": "no existe"})

        def do_POST(self):
            # el cuerpo se lee ANTES de rechazar: responder sin leerlo hace que Windows a veces corte la conexión
            ruta = urllib.parse.urlsplit(self.path).path
            limite = LIMITES_POR_RUTA.get(ruta, LIMITE_CUERPO)
            try:
                largo = max(int(self.headers.get("Content-Length") or 0), 0)
            except ValueError:
                largo = 0
            if largo > limite:
                self.rfile.read(min(largo, MAXIMO_A_DESCARTAR))
                if not self._permitido():
                    return self._json(403, {"error": "origen no permitido"})
                return self._json(413, {"error": f"pedido demasiado grande (máximo {limite} bytes)"})
            crudo = self.rfile.read(largo)
            if not self._permitido():
                return self._json(403, {"error": "origen no permitido"})
            try:
                datos = json.loads(crudo or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido"})
            if ruta == "/api/respaldo":
                if datos != {}:
                    return self._json(400, {"error": "este pedido no lleva datos"})
                try:
                    return self._json(201, {"ok": True, "respaldo": app.respaldar_ahora()})
                except buscar.ErrorDatos as ex:
                    return self._json(ex.codigo, {"error": str(ex)})
                except respaldo.RespaldoNoDisponible as ex:
                    return self._json(503, {"error": str(ex)})
                except respaldo.SinEspacio as ex:
                    return self._json(507, {"error": str(ex)})
                except respaldo.HuellaNoEscrita as ex:         # la copia quedó, pero incompleta: se dice tal cual
                    return self._json(500, {"error": str(ex)})
                except Exception as ex:                     # el servidor sigue; la página muestra el motivo
                    return self._json(500, {"error": f"el respaldo falló: {type(ex).__name__}: {ex}"})
            if ruta == "/api/buscar":
                if app.iniciar_busqueda():
                    return self._json(202, {"ok": True})
                return self._json(409, {"error": "ya hay una búsqueda en curso"})
            escrituras = {
                "/api/marcar": lambda con, d: buscar.marcar(con, d.get("url"), d.get("estado"), d.get("restaurar"),
                                                            d.get("fase"), d.get("origen")),
                "/api/nota": lambda con, d: {"oferta": buscar.actualizar_seguimiento(
                    con, d.get("url"), {k: v for k, v in d.items() if k != "url"})},
                "/api/ajustes/soporte": lambda con, d: buscar.guardar_soporte(con, d),
                "/api/ajustes/puestos": lambda con, d: buscar.guardar_puestos(con, d),
                "/api/oferta/manual": lambda con, d: {"oferta": buscar.crear_oferta_manual(con, d)},
                "/api/descripcion": lambda con, d: buscar.pegar_descripcion(con, d.get("url"), d.get("descripcion")),
            }
            codigo_ok = {"/api/oferta/manual": 201}
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
                    return self._json(ex.codigo, {"error": str(ex), **ex.extra})
                except (buscar.BaseOcupada, sqlite3.OperationalError) as ex:
                    if isinstance(ex, buscar.BaseOcupada) or buscar.es_base_ocupada(ex):
                        return self._json(503, {"error": "base ocupada, reintenta"})
                    raise
                return self._json(codigo_ok.get(ruta, 200), {"ok": True, **resultado})
            self._json(404, {"error": "no existe"})

    return ThreadingHTTPServer((host or config.HOST, puerto or config.PUERTO), Manejador)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--puerto", type=int, default=config.PUERTO)
    ap.add_argument("--no-abrir", action="store_true", help="no abrir el navegador al iniciar")
    args = ap.parse_args()
    app = Aplicacion()
    app.conexion().close()                    # crea/migra la base antes de atender
    app.iniciar_respaldo_diario()             # si JT_RESPALDOS está configurado: un respaldo automático por día
    srv = crear_servidor(app, args.puerto)
    url = f"http://127.0.0.1:{args.puerto}/"
    print(f"Página de ofertas en {url}  (Ctrl+C para cerrar)")
    if not args.no_abrir and config.HOST == "127.0.0.1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    # docker stop manda SIGTERM al PID 1, que sin manejador lo ignora (y Docker lo mata: código 137). Con esto, SIGTERM
    # interrumpe serve_forever igual que Ctrl+C: en el hilo principal, que es el que atiende.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for s in (signal.SIGTERM, signal.SIGINT):   # una segunda señal no corta el cierre a la mitad
            signal.signal(s, signal.SIG_IGN)
        srv.server_close()                           # los hilos de pedidos son daemon: no se esperan
        app.apagar()
        print("Servidor detenido.", flush=True)


if __name__ == "__main__":
    main()
