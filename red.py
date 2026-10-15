"""Acceso a la red para las fuentes que no usa JobSpy (BNE, Trabajando, Chiletrabajos).

Reglas (heredadas de la app anterior "Busca Empleo", que las trae de decisiones de Sofia):
  - Se consulta robots.txt de cada sitio antes de pedir una página.
  - Pausa aleatoria de 3 a 5 segundos entre peticiones y un User-Agent que dice quién es (no se disfraza).
  - Ante 401/403/429 o una página de verificación/CAPTCHA se DETIENE ese sitio: no se reintenta ni se esquiva.
"""
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

PAUSA_ENTRE_PETICIONES = (3.0, 5.0)
USER_AGENT_HTTP = "BuscaEmpleo/0.1 (busqueda personal de empleo)"

STATUS_BLOQUEO = (401, 403, 429)
MARCAS_BLOQUEO = ("captcha", "cf-chl", "just a moment", "attention required", "challenge-platform",
                  "actividad inusual", "unusual activity", "verifica que eres humano", "access denied")


class Bloqueo(Exception):
    """El sitio nos rechazó (o no se pudo leer su robots.txt): se deja ese sitio en paz el resto de la corrida."""


class ErrorFuente(Exception):
    """Fallo de un sitio que no es un bloqueo (red, formato inesperado). Quien llama decide si insistir."""


class NoEncontrada(ErrorFuente):
    """HTTP 404."""


def es_bloqueo(status: int) -> bool:
    return status in STATUS_BLOQUEO


def parece_bloqueo(texto: str) -> Optional[str]:
    """Señal encontrada si una respuesta 200 es en realidad un CAPTCHA o una verificación."""
    t = (texto or "")[:20000].lower()
    return next((m for m in MARCAS_BLOQUEO if m in t), None)


@dataclass
class Respuesta:
    status: int          # 0 = error de red / tiempo agotado
    texto: str = ""
    error: str = ""


class ClienteHTTP:
    def __init__(self, user_agent: Optional[str] = None, pausa: Tuple[float, float] = None, timeout: int = 25,
                 dormir: Callable[[float], None] = time.sleep, azar: Callable[[float, float], float] = random.uniform,
                 abrir: Callable = None):
        self.ua = user_agent or USER_AGENT_HTTP
        self.pausa = pausa or PAUSA_ENTRE_PETICIONES
        self.timeout = timeout
        self._dormir, self._azar = dormir, azar
        self._abrir = abrir or urllib.request.urlopen
        self._primera = True
        self.peticiones = 0
        self.al_responder: Optional[Callable[[int], None]] = None   # telemetría pasiva: recibe solo el status

    def get(self, url: str) -> Respuesta:
        if not self._primera:
            self._dormir(self._azar(*self.pausa))
        self._primera = False
        self.peticiones += 1
        respuesta = self._get(url)
        if self.al_responder:
            try:
                self.al_responder(respuesta.status)
            except Exception:
                pass                                       # la telemetría nunca cambia lo que pasa con la fuente
        return respuesta

    def _get(self, url: str) -> Respuesta:
        req = urllib.request.Request(url, headers={
            "User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9",
            "Accept-Language": "es-CL,es;q=0.9", "Accept-Encoding": "identity",
        })
        try:
            with self._abrir(req, timeout=self.timeout) as r:
                cuerpo = r.read()
                cs = r.headers.get_content_charset() if hasattr(r.headers, "get_content_charset") else None
                return Respuesta(getattr(r, "status", 200), cuerpo.decode(cs or "utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            return Respuesta(e.code, "", "HTTP %d" % e.code)
        except Exception as e:  # DNS, timeout, SSL...
            return Respuesta(0, "", "%s: %s" % (type(e).__name__, e))


def pedir(url: str, cliente, robots) -> str:
    """Descarga una URL respetando robots.txt. Devuelve el texto o lanza Bloqueo / NoEncontrada / ErrorFuente."""
    rechazo = getattr(robots, "bloqueo", lambda _u: "")(url)
    if rechazo:
        raise Bloqueo("robots.txt rechazó la lectura (%s)" % rechazo)
    if robots.no_disponible(url):
        raise ErrorFuente("no se pudo leer robots.txt (¿sin internet o el sitio no responde?); no se visitó nada")
    if not robots.permitido(url):
        raise ErrorFuente("robots.txt no permite esta URL")
    r = cliente.get(url)
    if es_bloqueo(r.status):
        raise Bloqueo(r.error or "HTTP %d" % r.status)
    if r.status == 404:
        raise NoEncontrada("HTTP 404")
    if r.status != 200:
        raise ErrorFuente(r.error or "HTTP %s" % r.status)
    marca = parece_bloqueo(r.texto)
    if marca and "__NUXT_DATA__" not in r.texto and '"paginaOfertas"' not in r.texto and "job-item" not in r.texto:
        raise Bloqueo("página de verificación (%s)" % marca)
    return r.texto
