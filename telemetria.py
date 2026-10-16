"""Telemetría PASIVA de una corrida: solo contadores por fuente, dentro de corridas.detalle (sin DDL).

No guarda URLs, parámetros ni términos: solo cuántas solicitudes hubo, su código HTTP agrupado y cuántas búsquedas
volvieron vacías. No cambia reintentos, pausas ni el orden de nada: se anota DESPUÉS de cada respuesta, y un fallo
al anotar se ignora.

  medicion "http":     cada solicitud observada (portales con ClienteHTTP, su robots.txt y la API de Get on Board).
  medicion "consulta": JobSpy (Indeed, Glassdoor) no expone sus solicitudes: se cuenta cada llamada; el código solo se
                       conoce cuando la llamada falla (y se deduce de la excepción). Por eso "200" es None ("no
                       medido", null en el JSON) y no 0. Lleva además "por_ubicacion": consultas, vacías y errores por
                       cada ubicación de la configuración (sin términos ni nada de las ofertas).
"""
import re

from filtros import plural

CODIGOS = ("200", "403", "404", "429", "5xx", "otros", "conexion")


def contador(medicion: str = "http", lugares=()) -> dict:
    """lugares: solo para "consulta", las ubicaciones de la configuración (config.UBICACIONES y "Chile (remoto)")."""
    t = {"medicion": medicion, "solicitudes": 0, "codigos": {k: 0 for k in CODIGOS}, "vacias": 0}
    if medicion == "consulta":
        t["codigos"]["200"] = None                     # JobSpy no informa el código de una llamada que funcionó
        t["por_ubicacion"] = {l: {"consultas": 0, "vacias": 0, "errores": 0} for l in lugares}
    return t


def _ubicacion(t: dict, lugar):
    """El contador de esa ubicación, o None si no hay (otra medición, o una ubicación que no se declaró)."""
    return t.get("por_ubicacion", {}).get(lugar) if lugar is not None else None


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
        clase = clase_status(status)
        if t["codigos"].get(clase) is None:           # "200" no medido en una consulta: no se mezcla con un número
            clase = "otros"
        t["codigos"][clase] += 1
    except Exception:
        pass


def anotar_consulta(t: dict, filas: int, lugar=None) -> None:
    """Una llamada que respondió (JobSpy): cuenta la consulta y si vino vacía, en total y en su ubicación. Nunca lanza."""
    try:
        t["solicitudes"] += 1
        t["vacias"] += int(filas == 0)                # int, no bool: el detalle se guarda con tipos simples
        u = _ubicacion(t, lugar)
        if u is not None:
            u["consultas"] += 1
            u["vacias"] += int(filas == 0)
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


def anotar_excepcion(t: dict, e: BaseException, lugar=None) -> None:
    """Una llamada que falló (cuenta como solicitud y, si se indica, como consulta con error de su ubicación). Nunca
    lanza."""
    try:
        t["solicitudes"] += 1
        clase = clase_excepcion(e)
        if t["codigos"].get(clase) is None:           # "200" no medido (o una clase rara): no se mezcla con un número
            clase = "otros"
        t["codigos"][clase] += 1
        u = _ubicacion(t, lugar)
        if u is not None:
            u["consultas"] += 1
            u["errores"] += 1
    except Exception:
        pass


def _etiqueta_lugar(lugar: str) -> str:
    """'Santiago, Chile' -> 'Santiago'; 'Viña del Mar, Chile' -> 'Viña'; 'Chile (remoto)' -> 'remoto'."""
    if "remoto" in lugar.lower():
        return "remoto"
    return (lugar.split(",")[0].split() or [lugar])[0]


def resumen(por_fuente: dict) -> str:
    """Una línea para stderr (docker logs): solicitudes, códigos distintos de cero y vacías, por fuente; en JobSpy,
    además, consultas/vacías por ubicación."""
    partes = []
    for fuente, t in por_fuente.items():
        codigos = [f"{k}={v}" for k, v in t["codigos"].items() if v]
        if t["medicion"] == "consulta":
            codigos.insert(0, "200 no medido")
        codigos = ", ".join(codigos) or "sin códigos"
        cuenta = (plural(t["solicitudes"], "consulta", "consultas") if t["medicion"] == "consulta"
                  else plural(t["solicitudes"], "solicitud", "solicitudes"))
        texto = f"{fuente}: {cuenta} ({codigos}), {plural(t['vacias'], 'vacía', 'vacías')}"
        lugares = t.get("por_ubicacion") or {}
        if lugares:
            texto += " [" + ", ".join(
                f"{_etiqueta_lugar(l)} {u['consultas']}/{u['vacias']}"
                + (f" ({plural(u['errores'], 'error', 'errores')})" if u["errores"] else "")
                for l, u in lugares.items()) + "]"
        partes.append(texto)
    return "[corrida] " + " | ".join(partes)
