"""Telemetría PASIVA de una corrida: solo contadores por fuente, dentro de corridas.detalle (sin DDL).

No guarda URLs, parámetros ni términos: solo cuántas solicitudes hubo, su código HTTP agrupado y cuántas búsquedas
volvieron vacías. No cambia reintentos, pausas ni el orden de nada: se anota DESPUÉS de cada respuesta, y un fallo
al anotar se ignora.

  medicion "http":     cada solicitud observada (portales con ClienteHTTP, su robots.txt y la API de Get on Board).
  medicion "consulta": JobSpy (Indeed, Glassdoor) no expone sus solicitudes: se cuenta cada llamada; el código solo se
                       conoce cuando la llamada falla (y se deduce de la excepción).
"""
import re

from filtros import plural

CODIGOS = ("200", "403", "404", "429", "5xx", "otros", "conexion")


def contador(medicion: str = "http") -> dict:
    return {"medicion": medicion, "solicitudes": 0, "codigos": {k: 0 for k in CODIGOS}, "vacias": 0}


def clase_status(status: int) -> str:
    if not status:
        return "conexion"                      # 0 = error de red o tiempo agotado (red.Respuesta)
    if str(status) in CODIGOS:
        return str(status)
    return "5xx" if 500 <= status < 600 else "otros"


def anotar_status(t: dict, status: int) -> None:
    """Una solicitud con su código (0 = sin respuesta). Nunca lanza."""
    try:
        t["solicitudes"] += 1
        t["codigos"][clase_status(status)] += 1
    except Exception:
        pass


def anotar_consulta(t: dict, filas: int) -> None:
    """Una llamada que respondió (JobSpy): cuenta la consulta y si vino vacía. Nunca lanza."""
    try:
        t["solicitudes"] += 1
        t["vacias"] += int(filas == 0)                # int, no bool: el detalle se guarda con tipos simples
    except Exception:
        pass


def anotar_vacia(t: dict) -> None:
    try:
        t["vacias"] += 1
    except Exception:
        pass


def anotar_si_vacio(t: dict, df) -> None:
    """Cuenta una búsqueda vacía si df es None o no tiene filas. Nunca lanza (ni con un df raro)."""
    try:
        if df is None or len(df) == 0:
            t["vacias"] += 1
    except Exception:
        pass


def clase_excepcion(e: BaseException) -> str:
    """Código de una llamada que falló: el de la respuesta si viene en la excepción; si no, 'conexion' para
    tiempos agotados y errores de red; si no, el primer 403/404/429/5xx del mensaje; si no, 'otros'."""
    respuesta = getattr(e, "response", None)
    status = getattr(respuesta, "status_code", None) or getattr(e, "code", None)
    if isinstance(status, int) and status:
        return clase_status(status)
    nombres = " ".join(c.__name__ for c in type(e).__mro__).lower()
    if any(p in nombres for p in ("timeout", "connection", "urlerror", "socket", "ssl")):
        return "conexion"
    m = re.search(r"\b(403|404|429|5\d\d)\b", str(e))
    return clase_status(int(m.group(1))) if m else "otros"


def anotar_excepcion(t: dict, e: BaseException) -> None:
    """Una llamada que falló (cuenta como solicitud). Nunca lanza."""
    try:
        t["solicitudes"] += 1
        t["codigos"][clase_excepcion(e)] += 1
    except Exception:
        pass


def resumen(por_fuente: dict) -> str:
    """Una línea para stderr (docker logs): solicitudes, códigos distintos de cero y vacías, por fuente."""
    partes = []
    for fuente, t in por_fuente.items():
        codigos = ", ".join(f"{k}={v}" for k, v in t["codigos"].items() if v) or "sin códigos"
        cuenta = (plural(t["solicitudes"], "consulta", "consultas") if t["medicion"] == "consulta"
                  else plural(t["solicitudes"], "solicitud", "solicitudes"))
        partes.append(f"{fuente}: {cuenta} ({codigos}), {plural(t['vacias'], 'vacía', 'vacías')}")
    return "[corrida] " + " | ".join(partes)
