"""Respaldo de la base a una carpeta del equipo (fuera del volumen de Docker y fuera de OneDrive).

Copia consistente con la API de backup de SQLite (sirve aunque la página o una búsqueda estén escribiendo), a un archivo
temporal; se comprueba con integrity_check, se anota su sha256 en un .sha256 al lado y recién entonces se renombra al
nombre final: nunca queda visible un respaldo a medias.

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


def listar(carpeta: str) -> list[dict]:
    """Respaldos terminados, del más nuevo al más viejo."""
    out = []
    for nombre in sorted(os.listdir(carpeta), reverse=True):
        if nombre.startswith(("ofertas_auto_", "ofertas_manual_")) and nombre.endswith(".db"):
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
        finally:
            destino.close()
            origen.close()
        if integridad != "ok":
            raise RuntimeError(f"el respaldo salió dañado: {integridad}")
        huella = _sha256(tmp)
        with open(final + ".sha256", "w", encoding="utf-8") as f:
            f.write(f"{huella}  {nombre}\n")
        os.replace(tmp, final)                          # recién ahora aparece con su nombre final
    except OSError as ex:
        if getattr(ex, "errno", None) == 28:            # ENOSPC: el disco se llenó durante la copia
            raise SinEspacio("el disco de la carpeta de respaldos se llenó durante la copia") from ex
        raise
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if tipo == "auto":
        _retener(carpeta)
    return {"archivo": nombre, "bytes": os.path.getsize(final), "sha256": huella, "integridad": integridad,
            "fecha": f"{ahora:%Y-%m-%d %H:%M}"}


def hay_auto_de_hoy(carpeta: str, ahora) -> bool:
    return any(n.startswith(f"ofertas_auto_{ahora:%Y%m%d}-") and n.endswith(".db") for n in os.listdir(carpeta))


def estado(carpeta: str) -> dict:
    """Para la página: configurado, disponible, último respaldo y cuántos hay (sin lanzar excepciones)."""
    if not carpeta:
        return {"configurado": False, "disponible": False, "error": "el respaldo no está configurado"}
    try:
        _carpeta_lista(carpeta)
        todos = listar(carpeta)
    except (RespaldoNoDisponible, OSError) as ex:
        return {"configurado": True, "disponible": False, "error": str(ex)}
    return {"configurado": True, "disponible": True, "error": "", "ultimo": todos[0] if todos else None,
            "total_auto": sum(r["tipo"] == "auto" for r in todos), "total_manual": sum(r["tipo"] == "manual" for r in todos)}
