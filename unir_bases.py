"""Une varias copias de la base de ofertas en una sola (herramienta de una vez, unión del 13-oct-2026).

La base principal se copia tal cual (ofertas, clasificación, corridas) y de las otras se toman solo los datos de
seguimiento según estas reglas:
  - En un conflicto gana el estado de la base principal.
  - El estado de otra base solo se aplica si la principal tiene "nueva" y la otra tiene una decisión
    (revisada, postulada, entrevista o descartada). Si dos bases deciden distinto, el script se detiene.
  - Cuando se descarta una decisión de otra base (no un "nueva"), se agrega a notas "[unión FECHA] estados previos: ..." (con la
    fecha_postulacion de las otras bases, si la tenían): nada se pierde en silencio.
  - fecha_postulacion: la de la principal o, si no tiene, la de otra base. No se inventa.
  - Excepciones decididas a mano (JSON {url: {estado, fecha_postulacion, nota, por_verificar}}) mandan sobre todo.
  - Las corridas de las otras bases NO se copian.
Las bases de entrada se abren en solo lectura. La salida solo se escribe si todas las verificaciones pasan.

Uso:
    python unir_bases.py --base VJT=ruta.db --otra NODE=ruta.db --otra VBE=ruta.db \\
        --excepciones excepciones.json --salida unida.db [--fecha 2026-10-13] [--esperadas-postuladas 9]
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import buscar

DECISIONES = {"revisada", "postulada", "entrevista", "descartada"}
ACTIVOS = {"postulada", "entrevista"}
COLS_SEGUIMIENTO = ["estado", *buscar.COLUMNAS_SEGUIMIENTO]


class ErrorUnion(Exception):
    pass


def abrir_ro(ruta) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(ruta).resolve().as_posix()}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    return con


def filas_por_url(con) -> dict:
    return {r["url"]: dict(r) for r in con.execute("SELECT * FROM ofertas")}


def huella(con, tabla, excluir=()):
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({tabla})") if r[1] not in excluir]
    return [tuple(r) for r in con.execute(f"SELECT {', '.join(cols)} FROM {tabla} ORDER BY 1, 2")]


def unir(base: tuple, otras: list, excepciones: dict, salida, fecha_union: str, esperadas_postuladas=None) -> list:
    """Devuelve la lista de conflictos (para mostrarla) y deja la base unida en `salida`."""
    nombre_base, ruta_base = base
    src = abrir_ro(ruta_base)
    filas_base = filas_por_url(src)
    otras_filas = {n: filas_por_url(abrir_ro(r)) for n, r in otras}

    errores = []
    for n, filas in otras_filas.items():
        solo = sorted(set(filas) - set(filas_base))
        if solo:
            errores.append(f"{len(solo)} ofertas existen en {n} y no en {nombre_base} (se perderían): {solo[:5]}")
    faltan = sorted(set(excepciones) - set(filas_base))
    if faltan:
        errores.append(f"excepciones que no están en {nombre_base}: {faltan}")
    if errores:
        raise ErrorUnion("\n".join(errores))

    tmp = str(salida) + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    dst = sqlite3.connect(tmp)
    src.backup(dst)                                   # copia exacta de la base principal
    dst.close()
    con = buscar.conectar(tmp)                         # migra a la versión actual (columnas de seguimiento)

    conflictos, cambios = [], []
    for url, fb in filas_base.items():
        previos = {nombre_base: fb["estado"]}
        previos.update({n: f[url]["estado"] for n, f in otras_filas.items() if url in f})
        fechas_otras = {n: f[url].get("fecha_postulacion") for n, f in otras_filas.items()
                        if url in f and f[url].get("fecha_postulacion")}
        categorias = {n: f[url]["categoria"] for n, f in otras_filas.items() if url in f}
        notas_otras = [f"[unión {fecha_union}] notas en {n}: {f[url]['notas']}"
                       for n, f in otras_filas.items() if url in f and (f[url].get("notas") or "").strip()]
        fases_otras = {f[url]["fase"] for f in otras_filas.values() if url in f and f[url].get("fase")}
        notas = []
        if url in excepciones:
            ex = excepciones[url]
            final, fecha = ex["estado"], ex.get("fecha_postulacion", "")
            notas.append(ex["nota"])
            por_verificar, motivo = bool(ex.get("por_verificar")), "excepción"
        else:
            final, motivo = fb["estado"], f"regla {nombre_base}"
            decisiones = {n: e for n, e in previos.items() if n != nombre_base and e in DECISIONES}
            if fb["estado"] == "nueva" and decisiones:
                if len(set(decisiones.values())) > 1:
                    errores.append(f"decisión ambigua en {url}: {decisiones}")
                    continue
                final = next(iter(decisiones.values()))
                motivo = "aplicado de " + "/".join(decisiones)
            if len(set(fechas_otras.values())) > 1:
                errores.append(f"fechas de postulación distintas en {url}: {fechas_otras}")
                continue
            fecha = fb.get("fecha_postulacion") or next(iter(fechas_otras.values()), "")
            if any(e != final and e in DECISIONES for n, e in previos.items() if n != nombre_base):
                # se descarta una DECISIÓN de otra base (un "nueva" descartado no aporta nada que anotar)
                notas.append(f"[unión {fecha_union}] estados previos: "
                             + ", ".join(f"{n}={e}" for n, e in previos.items())
                             + "".join(f"; fecha_postulacion en {n}={f}" for n, f in fechas_otras.items()))
            otros = [e for n, e in previos.items() if n != nombre_base]
            por_verificar = (final not in ACTIVOS and any(e in ACTIVOS for e in otros)) or \
                            (final in ACTIVOS and "descartada" in otros)
        if len(fases_otras) > 1:
            errores.append(f"fases distintas en {url}: {fases_otras}")
            continue
        fase = fb.get("fase") or next(iter(fases_otras), "")
        notas_final = "\n".join(x for x in [fb.get("notas") or "", *notas, *notas_otras] if x)
        nuevo = (final, fecha or "", fase or "", notas_final)
        if nuevo != (fb["estado"], fb.get("fecha_postulacion") or "", fb.get("fase") or "", fb.get("notas") or ""):
            cambios.append((*nuevo, url))
        if len(set(previos.values())) > 1 or set(categorias.values()) - {fb["categoria"]} or fechas_otras \
                or url in excepciones:
            conflictos.append({"url": url, "titulo": fb["titulo"], "empresa": fb["empresa"], "previos": previos,
                               "categoria": fb["categoria"], "categorias_otras": categorias, "final": final,
                               "fecha": fecha or "", "motivo": motivo, "por_verificar": por_verificar,
                               "nota": notas_final})
    if errores:
        con.close()
        os.remove(tmp)
        raise ErrorUnion("\n".join(errores))

    con.executemany("UPDATE ofertas SET estado = ?, fecha_postulacion = ?, fase = ?, notas = ? WHERE url = ?", cambios)
    con.commit()
    _verificar(con, src, filas_base, otras_filas, esperadas_postuladas)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("PRAGMA journal_mode = DELETE")        # un solo archivo, listo para copiar al volumen
    con.close()
    os.replace(tmp, salida)
    return conflictos


def _verificar(con, src, filas_base, otras_filas, esperadas_postuladas):
    n = con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0]
    urls = {r[0] for r in con.execute("SELECT url FROM ofertas")}
    todas = set(filas_base).union(*otras_filas.values())
    assert n == len(filas_base) and urls == todas, f"ofertas: {n} filas, faltan {sorted(todas - urls)[:5]}"
    for tabla in ("corridas", "terminos_no_disponibles"):
        assert huella(con, tabla) == huella(src, tabla), f"{tabla} cambió"
    excluir = set(COLS_SEGUIMIENTO)
    assert huella(con, "ofertas", excluir) == huella(src, "ofertas", excluir), "la clasificación cambió"
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    postuladas = con.execute("SELECT COUNT(*) FROM ofertas WHERE estado = 'postulada'").fetchone()[0]
    if esperadas_postuladas is not None:
        assert postuladas == esperadas_postuladas, f"postuladas: {postuladas}, se esperaban {esperadas_postuladas}"


def resumen(ruta) -> dict:
    con = abrir_ro(ruta)
    return {"ofertas": con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0],
            "corridas": [tuple(r) for r in con.execute("SELECT id, inicio, fin, nuevas FROM corridas ORDER BY id")],
            "estados": dict(con.execute("SELECT estado, COUNT(*) FROM ofertas GROUP BY 1").fetchall()),
            "version": con.execute("PRAGMA user_version").fetchone()[0]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    nombre_ruta = lambda s: tuple(s.split("=", 1))   # noqa: E731
    ap.add_argument("--base", required=True, type=nombre_ruta)
    ap.add_argument("--otra", action="append", default=[], type=nombre_ruta)
    ap.add_argument("--excepciones")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--fecha", default="2026-10-13")
    ap.add_argument("--esperadas-postuladas", type=int)
    args = ap.parse_args(argv)
    if os.path.exists(args.salida):
        sys.exit(f"{args.salida} ya existe: no se sobrescribe")
    excepciones = json.loads(Path(args.excepciones).read_text(encoding="utf-8")) if args.excepciones else {}
    try:
        conflictos = unir(args.base, args.otra, excepciones, args.salida, args.fecha, args.esperadas_postuladas)
    except (ErrorUnion, AssertionError) as ex:
        sys.exit(f"Unión cancelada, no se escribió nada:\n{ex}")
    nombres = [args.base[0]] + [n for n, _ in args.otra]
    print("\t".join(["", "oferta", "empresa", "url", *nombres, "FINAL", "fecha_post", "motivo", "nota"]))
    for c in sorted(conflictos, key=lambda c: (not c["por_verificar"], c["final"] != "postulada", c["titulo"])):
        cat = c["categoria"] + "".join(f" ({n}: {v})" for n, v in c["categorias_otras"].items() if v != c["categoria"])
        print("\t".join(["POR VERIFICAR" if c["por_verificar"] else "", c["titulo"], c["empresa"], c["url"],
                         *[c["previos"].get(n, "—") for n in nombres], c["final"], c["fecha"],
                         c["motivo"] + "; categoría " + cat, c["nota"].replace("\n", " | ")]))
    print(f"\n{len(conflictos)} URLs con conflicto. Resultado: {resumen(args.salida)}")


if __name__ == "__main__":
    main()
