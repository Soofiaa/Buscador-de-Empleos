"""Respaldo de la base a una carpeta del equipo (fuera del volumen de Docker y fuera de OneDrive).

Copia consistente con la API de backup de SQLite (sirve aunque la página o una búsqueda estén escribiendo), a un archivo
temporal; se comprueba con integrity_check, se renombra al nombre final y AL FINAL se escribe su .sha256 al lado (también
temporal + fsync + renombre). Un respaldo es válido solo si tiene su .sha256: un .db sin él (corte entre ambos pasos) es
"incompleto": no cuenta como último ni como el de hoy, no entra en la retención y no se borra solo (se informa).

- ofertas_auto_AAAAMMDD-HHMMSS.db: uno por día (lo hace el servidor solo); se guardan los últimos RETENER_AUTO.
- ofertas_manual_AAAAMMDD-HHMMSS.db: botón "Respaldar ahora"; nunca se borran solos.

La carpeta la fija la configuración (JT_RESPALDOS), nunca un pedido. Si no está configurada, no existe o el disco está
lleno, se informa con un error claro y el servidor sigue funcionando.
"""
import hashlib
import os
import shutil
import sqlite3
import time

RETENER_AUTO = 30                    # ~ un mes de copias diarias
ESPACIO_MINIMO = 50 * 1024 * 1024    # además del doble del tamaño de la base
PREFIJO_TMP = ".tmp-"


class RespaldoNoDisponible(Exception):
    """La carpeta no está configurada, no existe (¿no está montada?) o no se puede escribir."""


class SinEspacio(Exception):
    """No hay espacio suficiente en el disco de la carpeta de respaldos."""


class HuellaNoEscrita(Exception):
    """La copia quedó guardada con su nombre final pero no su .sha256: es un respaldo incompleto (no válido)."""


def _carpeta_lista(carpeta: str) -> None:
    if not carpeta:
        raise RespaldoNoDisponible("el respaldo no está configurado (JT_RESPALDOS)")
    if not os.path.isdir(carpeta):
        raise RespaldoNoDisponible(f"la carpeta de respaldos no existe o no está montada: {carpeta}")
    if not os.access(carpeta, os.W_OK):
        raise RespaldoNoDisponible(f"no se puede escribir en la carpeta de respaldos: {carpeta}")


def _sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _limpiar_temporales(carpeta: str, edad_s: int = 3600) -> None:
    """Restos de un respaldo interrumpido (corte de luz, contenedor detenido a la mitad)."""
    ahora = time.time()
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        if nombre.startswith(PREFIJO_TMP) and ahora - os.path.getmtime(ruta) > edad_s:
            os.remove(ruta)


def _respaldos_db(carpeta: str) -> list[str]:
    # del más nuevo al más viejo por la fecha del nombre (AAAAMMDD-HHMMSS), no por el nombre completo: si no, todos los
    # "manual" quedan antes que los "auto" y el "último respaldo" puede ser un manual más viejo
    nombres = [n for n in os.listdir(carpeta) if n.startswith(("ofertas_auto_", "ofertas_manual_")) and n.endswith(".db")]
    return sorted(nombres, key=lambda n: (n[-18:-3], n), reverse=True)


def incompletos(carpeta: str) -> list[str]:
    """Respaldos con nombre final pero sin su .sha256: no son válidos (no se borran solos)."""
    return [n for n in _respaldos_db(carpeta) if not os.path.exists(os.path.join(carpeta, n + ".sha256"))]


def listar(carpeta: str) -> list[dict]:
    """Respaldos válidos (con su .sha256), del más nuevo al más viejo."""
    out = []
    for nombre in _respaldos_db(carpeta):
        if os.path.exists(os.path.join(carpeta, nombre + ".sha256")):
            out.append({"archivo": nombre, "tipo": "auto" if nombre.startswith("ofertas_auto_") else "manual",
                        "fecha": f"{nombre[-18:-14]}-{nombre[-14:-12]}-{nombre[-12:-10]} {nombre[-9:-7]}:{nombre[-7:-5]}",
                        "bytes": os.path.getsize(os.path.join(carpeta, nombre))})
    return out


def _retener(carpeta: str) -> None:
    autos = [r["archivo"] for r in listar(carpeta) if r["tipo"] == "auto"]
    for nombre in autos[RETENER_AUTO:]:                 # los manuales nunca se borran solos
        for ruta in (os.path.join(carpeta, nombre), os.path.join(carpeta, nombre + ".sha256")):
            if os.path.exists(ruta):
                os.remove(ruta)


def _escribir_huella(carpeta: str, nombre: str, huella: str) -> None:
    """El .sha256, atómico: temporal, fsync y recién entonces el nombre final."""
    tmp, final = os.path.join(carpeta, PREFIJO_TMP + nombre + ".sha256"), os.path.join(carpeta, nombre + ".sha256")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"{huella}  {nombre}\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def respaldar(ruta_db: str, carpeta: str, tipo: str, ahora) -> dict:
    """Hace un respaldo 'auto' o 'manual'. Devuelve {archivo, bytes, sha256, integridad, fecha}."""
    assert tipo in ("auto", "manual")
    _carpeta_lista(carpeta)
    _limpiar_temporales(carpeta)
    necesario = 2 * os.path.getsize(ruta_db) + ESPACIO_MINIMO
    if shutil.disk_usage(carpeta).free < necesario:
        raise SinEspacio(f"no hay espacio suficiente en el disco de la carpeta de respaldos (se necesitan "
                         f"{necesario // (1024 * 1024)} MB libres)")
    nombre = f"ofertas_{tipo}_{ahora:%Y%m%d-%H%M%S}.db"
    final, tmp = os.path.join(carpeta, nombre), os.path.join(carpeta, PREFIJO_TMP + nombre)
    try:
        origen = sqlite3.connect(f"file:{ruta_db}?mode=ro", uri=True)
        destino = sqlite3.connect(tmp)
        try:
            origen.backup(destino)                      # copia consistente aunque otro esté escribiendo
            integridad = destino.execute("PRAGMA integrity_check").fetchone()[0]
            # la copia hereda el modo WAL de la base; un respaldo debe ser UN archivo autosuficiente (y WAL es frágil
            # en una carpeta montada desde Windows)
            destino.execute("PRAGMA journal_mode = DELETE")
        finally:
            destino.close()
            origen.close()
        if integridad != "ok":
            raise RuntimeError(f"el respaldo salió dañado: {integridad}")
        huella = _sha256(tmp)
        os.replace(tmp, final)                          # recién ahora aparece con su nombre final...
        try:
            _escribir_huella(carpeta, nombre, huella)   # ...y es válido cuando tiene su .sha256
        except OSError as ex:
            motivo = "el disco se llenó" if getattr(ex, "errno", None) == 28 else f"{type(ex).__name__}: {ex}"
            raise HuellaNoEscrita(f"la copia {nombre} se guardó, pero no su huella (.sha256): queda como respaldo "
                                  f"incompleto, no válido. Motivo: {motivo}") from ex
    except OSError as ex:
        if getattr(ex, "errno", None) == 28:            # ENOSPC: el disco se llenó durante la copia
            raise SinEspacio("el disco de la carpeta de respaldos se llenó durante la copia") from ex
        raise
    finally:
        for resto in (tmp, tmp + "-wal", tmp + "-shm", tmp + "-journal"):
            if os.path.exists(resto):
                os.remove(resto)
    if tipo == "auto":
        _retener(carpeta)
    return {"archivo": nombre, "bytes": os.path.getsize(final), "sha256": huella, "integridad": integridad,
            "fecha": f"{ahora:%Y-%m-%d %H:%M}"}


def hay_auto_de_hoy(carpeta: str, ahora) -> bool:                   # solo los válidos: un incompleto no cuenta
    return any(r["archivo"].startswith(f"ofertas_auto_{ahora:%Y%m%d}-") for r in listar(carpeta))


def estado(carpeta: str) -> dict:
    """Para la página: configurado, disponible, último respaldo y cuántos hay (sin lanzar excepciones)."""
    if not carpeta:
        return {"configurado": False, "disponible": False, "error": "el respaldo no está configurado"}
    try:
        _carpeta_lista(carpeta)
        todos, sin_huella = listar(carpeta), incompletos(carpeta)
    except (RespaldoNoDisponible, OSError) as ex:
        return {"configurado": True, "disponible": False, "error": str(ex)}
    return {"configurado": True, "disponible": True, "error": "", "ultimo": todos[0] if todos else None,
            "total_auto": sum(r["tipo"] == "auto" for r in todos), "total_manual": sum(r["tipo"] == "manual" for r in todos),
            "incompletos": len(sin_huella)}
