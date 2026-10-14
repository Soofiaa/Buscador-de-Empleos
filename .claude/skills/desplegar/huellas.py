"""Huellas de una base de job-tracker para comparar antes/después de un despliegue (solo lectura, solo biblioteca estándar).

Uso:
    python huellas.py RUTA_DB > huellas.json
        versión, integrity_check, objetos del esquema y, por tabla, el conteo de filas y el sha256 de TODAS sus filas
        (ordenadas, así no depende del orden físico), más postuladas, POR VERIFICAR y estados por categoría.
    python huellas.py --comparar ANTES.json DESPUES.json [--nuevas tabla1,tabla2]
        tabla antes/después completa; termina con código 1 si una tabla que ya existía cambió, si desaparece alguna, si
        aparece una tabla no declarada en --nuevas, o si la versión o el integrity_check no coinciden.
"""
import hashlib
import json
import sqlite3
import sys


def huellas(ruta: str) -> dict:
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    q = lambda sql: con.execute(sql).fetchall()            # noqa: E731
    tablas = {}
    for (nombre,) in q("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
        filas = sorted(repr(tuple(f)) for f in q(f'SELECT * FROM "{nombre}"'))
        tablas[nombre] = {"filas": len(filas), "sha256": hashlib.sha256("\n".join(filas).encode("utf-8")).hexdigest()}
    out = {
        "version": q("PRAGMA user_version")[0][0],
        "integrity_check": q("PRAGMA integrity_check")[0][0],
        "objetos": [f"{t}:{n}" for t, n in q("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' "
                                             "ORDER BY type, name")],
        "tablas": tablas,
        "postuladas": q("SELECT COUNT(*) FROM ofertas WHERE estado = 'postulada'")[0][0],
        "por_verificar": q("SELECT COUNT(*) FROM ofertas WHERE notas LIKE '%POR VERIFICAR%'")[0][0],
        "estados": [f"{c}/{e}: {n}" for c, e, n in q("SELECT categoria, estado, COUNT(*) FROM ofertas GROUP BY 1, 2 ORDER BY 1, 2")],
    }
    con.close()
    return out


def comparar(antes: dict, despues: dict, nuevas: set) -> bool:
    ok = True
    print(f"| {'':24} | {'Antes':76} | {'Después':76} | |")
    print(f"|{'-' * 26}|{'-' * 78}|{'-' * 78}|---|")
    for clave in ("version", "integrity_check", "postuladas", "por_verificar"):
        igual = antes[clave] == despues[clave]
        ok &= igual
        print(f"| {clave:24} | {str(antes[clave]):76} | {str(despues[clave]):76} | {'igual' if igual else 'DISTINTO'} |")
    for t in sorted(set(antes["tablas"]) | set(despues["tablas"])):
        a, d = antes["tablas"].get(t), despues["tablas"].get(t)
        celda = lambda x: f"{x['filas']} filas · {x['sha256']}" if x else "—"      # noqa: E731
        if a is None:
            marca = "nueva (declarada)" if t in nuevas else "NUEVA NO DECLARADA"
            ok &= t in nuevas
        else:
            marca = "IDÉNTICA" if a == d else ("DESAPARECIÓ" if d is None else "DISTINTA")
            ok &= a == d
        print(f"| {t:24} | {celda(a):76} | {celda(d):76} | {marca} |")
    print("\nEstados por categoría:", "igual" if antes["estados"] == despues["estados"] else "DISTINTO")
    for linea in despues["estados"]:
        print("  ", linea)
    print("Objetos agregados:", sorted(set(despues["objetos"]) - set(antes["objetos"])) or "ninguno")
    print("Objetos que faltan:", sorted(set(antes["objetos"]) - set(despues["objetos"])) or "ninguno")
    ok &= not set(antes["objetos"]) - set(despues["objetos"])
    print("\nRESULTADO:", "OK" if ok else "DETENERSE: hay diferencias")
    return ok


if __name__ == "__main__":
    if sys.argv[1:2] == ["--comparar"]:
        nuevas = set(sys.argv[sys.argv.index("--nuevas") + 1].split(",")) if "--nuevas" in sys.argv else set()
        cargar = lambda r: json.load(open(r, encoding="utf-8"))                  # noqa: E731
        sys.exit(0 if comparar(cargar(sys.argv[2]), cargar(sys.argv[3]), nuevas) else 1)
    print(json.dumps(huellas(sys.argv[1]), ensure_ascii=False, indent=1))
