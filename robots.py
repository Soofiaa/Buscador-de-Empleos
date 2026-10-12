"""Lector de robots.txt con soporte de comodines (*) y fin de ruta ($).

`urllib.robotparser` no entiende comodines, y Computrabajo y Laborum los usan
(p. ej. `/ofertas-de-trabajo/*pubdate=`), así que se implementa aquí según la
convención de Google: gana la regla más larga; a igual largo, gana Allow.
"""
import re
import urllib.error
import urllib.parse
import urllib.request

from red import es_bloqueo


def _a_regex(patron: str) -> re.Pattern:
    fin = patron.endswith("$")
    if fin:
        patron = patron[:-1]
    partes = [re.escape(p) for p in patron.split("*")]
    return re.compile(".*".join(partes) + ("$" if fin else ""))


class Robots:
    def __init__(self, texto: str, agente: str = "*", permitir_todo: bool = False, bloquear_todo: bool = False,
                 bloqueo: str = ""):
        self.permitir_todo = permitir_todo
        self.bloquear_todo = bloquear_todo or bool(bloqueo)
        self.bloqueo = bloqueo  # p. ej. "HTTP 403": el sitio rechazó la lectura de su robots.txt
        self.reglas = []  # (largo, es_allow, regex)
        if not (permitir_todo or bloquear_todo):
            self._cargar(texto, agente.lower())

    def _cargar(self, texto: str, agente: str):
        grupos = []  # (agentes, reglas)
        agentes, reglas, leyendo_agentes = [], [], True
        for linea in texto.splitlines():
            linea = linea.split("#", 1)[0].strip()
            if ":" not in linea:
                continue
            clave, valor = [x.strip() for x in linea.split(":", 1)]
            clave = clave.lower()
            if clave == "user-agent":
                if not leyendo_agentes:
                    grupos.append((agentes, reglas))
                    agentes, reglas, leyendo_agentes = [], [], True
                agentes.append(valor.lower())
            elif clave in ("allow", "disallow"):
                leyendo_agentes = False
                if valor:  # "Disallow:" vacío = permite todo; no agrega regla
                    reglas.append((len(valor), clave == "allow", _a_regex(valor)))
        if agentes or reglas:
            grupos.append((agentes, reglas))

        especifico = [g for g in grupos if any(a != "*" and a in agente for a in g[0])]
        general = [g for g in grupos if "*" in g[0]]
        elegidos = especifico or general
        for _, r in elegidos:
            self.reglas.extend(r)

    def permitido(self, url: str) -> bool:
        if self.bloquear_todo:
            return False
        if self.permitir_todo:
            return True
        p = urllib.parse.urlsplit(url)
        ruta = p.path or "/"
        if p.query:
            ruta += "?" + p.query
        mejor = None  # (largo, es_allow)
        for largo, es_allow, rx in self.reglas:
            if rx.match(ruta):
                if mejor is None or largo > mejor[0] or (largo == mejor[0] and es_allow):
                    mejor = (largo, es_allow)
        return True if mejor is None else mejor[1]


class GestorRobots:
    """Descarga y cachea el robots.txt de cada sitio. Criterio conservador:
    404 y otros 4xx -> todo permitido (convención de Google); 401/403/429 -> el sitio nos rechaza: bloqueado;
    error de red o 5xx -> no se visita ese sitio."""

    def __init__(self, user_agent_http: str, agente_robots: str = "*", timeout: int = 15):
        self.ua_http = user_agent_http
        self.agente = agente_robots
        self.timeout = timeout
        self._cache = {}

    def _descargar(self, base: str) -> Robots:
        req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": self.ua_http})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                texto = r.read().decode("utf-8", errors="replace")
            return Robots(texto, self.agente)
        except urllib.error.HTTPError as e:
            if es_bloqueo(e.code):
                return Robots("", bloqueo="HTTP %d" % e.code)
            if 400 <= e.code < 500:
                return Robots("", permitir_todo=True)
            return Robots("", bloquear_todo=True)
        except Exception:
            return Robots("", bloquear_todo=True)

    def permitido(self, url: str) -> bool:
        return self._de(url).permitido(url)

    def _de(self, url: str) -> Robots:
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._cache:
            self._cache[base] = self._descargar(base)
        return self._cache[base]

    def no_disponible(self, url: str) -> bool:
        """True si no se pudo leer el robots.txt del sitio (sin internet, sitio caído, error 5xx, o el sitio
        rechazó la petición). Distinto de "el sitio no permite esa ruta"."""
        return self._de(url).bloquear_todo

    def bloqueo(self, url: str) -> str:
        """Texto del bloqueo (p. ej. 'HTTP 403') si el sitio rechazó leer su robots.txt; cadena vacía si no."""
        return self._de(url).bloqueo

    def inyectar(self, base: str, robots: Robots):
        """Para pruebas: fija el robots.txt de un sitio sin red."""
        self._cache[base] = robots
