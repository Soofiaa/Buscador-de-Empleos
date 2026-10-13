"""Busca ofertas, las clasifica según tu perfil y las guarda en SQLite. Se ven en la página (servidor.py).

Uso:
    python buscar.py                  # busca y clasifica (también se puede lanzar desde el botón de la página)
    python buscar.py --reclasificar   # re-aplica config.py a lo ya guardado (sin buscar)
"""
import argparse
import json
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd

import bne
import chiletrabajos
import config
import getonboard
import trabajando
from red import Bloqueo, ClienteHTTP, ErrorFuente, NoEncontrada, USER_AGENT_HTTP
from robots import GestorRobots
from filtros import (ORDEN_MODALIDAD, ORDEN_PRIORIDAD, ZONA, ahora_chile, antiguedad, base_oferta, ciudad_de,
                     clasificar, clave_oferta, normalizar, numero, plural, sin_genero, texto)

VERSION_DB = 7
salida = print   # la página la reemplaza para mostrar el avance de la búsqueda en vivo


def _say(mensaje: str):
    salida(mensaje)


PORTALES = {"bne": bne, "trabajando": trabajando, "chiletrabajos": chiletrabajos}
ESTADOS = ["nueva", "revisada", "postulada", "entrevista", "descartada"]
ESTADOS_CERRADOS = {"postulada", "entrevista", "descartada"}
LIMITE_DESCARTADAS = 300   # la página muestra las descartadas más recientes (con su motivo)
CAMPOS_CLASIF = ["categoria", "razon", "tipo", "prioridad", "modalidad",
                 "contrato", "sueldo", "experiencia", "motivo"]

# ------------------------------------------------------------------ base de datos
def _migrar_v2(con) -> int:
    """v2 -> v3: agrega 'fuente' y recalcula la clave (ahora solo cuenta la ciudad)
    para detectar duplicados entre fuentes. Conserva los estados que ya marcaste."""
    con.execute("ALTER TABLE ofertas ADD COLUMN fuente TEXT DEFAULT 'indeed'")
    filas = con.execute("SELECT url, titulo, empresa, ubicacion FROM ofertas "
                        "ORDER BY (estado = 'nueva'), detectada_en, rowid").fetchall()
    con.execute("UPDATE ofertas SET clave = NULL")
    vistas = set()
    for r in filas:
        k = clave_oferta(r["titulo"], r["empresa"], r["ubicacion"])
        if k in vistas:
            con.execute("DELETE FROM ofertas WHERE url = ?", (r["url"],))
        else:
            vistas.add(k)
            con.execute("UPDATE ofertas SET clave = ? WHERE url = ?", (k, r["url"]))
    con.commit()
    return len(filas) - len(vistas)


def _migrar_v3(con) -> None:
    """v3 -> v4: guarda por separado título+empresa y ciudad, para detectar duplicados
    aunque una fuente (Glassdoor) entregue solo 'Chile' como ubicación."""
    con.execute("ALTER TABLE ofertas ADD COLUMN clave_base TEXT")
    con.execute("ALTER TABLE ofertas ADD COLUMN ciudad TEXT DEFAULT ''")
    for r in con.execute("SELECT url, titulo, empresa, ubicacion FROM ofertas").fetchall():
        con.execute("UPDATE ofertas SET clave_base = ?, ciudad = ? WHERE url = ?",
                    (base_oferta(r["titulo"], r["empresa"]), ciudad_de(r["ubicacion"]), r["url"]))
    con.commit()


def _migrar_v4(con) -> int:
    """v4 -> v5: la empresa se compara sin sufijos ('Empresas X - Chile' = 'X'). Recalcula las
    claves y une las que ahora coinciden, conservando la que tenga estado de seguimiento."""
    vistas, nuevas, borrar = {}, [], []
    filas = con.execute("SELECT url, titulo, empresa, ubicacion FROM ofertas "
                        "ORDER BY (estado != 'nueva') DESC, detectada_en").fetchall()
    con_ciudad = {base_oferta(r["titulo"], r["empresa"]) for r in filas if ciudad_de(r["ubicacion"])}
    for r in filas:
        clave = clave_oferta(r["titulo"], r["empresa"], r["ubicacion"])
        sin_ciudad_repetida = not ciudad_de(r["ubicacion"]) and base_oferta(r["titulo"], r["empresa"]) in con_ciudad
        if clave in vistas or sin_ciudad_repetida:   # 'Chile' a secas ya existe con ciudad en otra fuente
            borrar.append(r["url"])
            continue
        vistas[clave] = r["url"]
        nuevas.append((clave, base_oferta(r["titulo"], r["empresa"]), ciudad_de(r["ubicacion"]), r["url"]))
    for url in borrar:
        con.execute("DELETE FROM ofertas WHERE url = ?", (url,))
    con.execute("UPDATE ofertas SET clave = 'tmp:' || url")   # evita choques con claves antiguas (UNIQUE)
    con.executemany("UPDATE ofertas SET clave = ?, clave_base = ?, ciudad = ? WHERE url = ?", nuevas)
    con.commit()
    return len(borrar)


# las escribe la usuaria, no la búsqueda: reclasificar() y guardar() nunca las tocan
COLUMNAS_SEGUIMIENTO = ["notas", "fecha_postulacion", "fase", "sueldo_manual", "prioridad_manual"]
FASES = ["", "postulacion", "rrhh", "tecnica", "final", "oferta"]      # "" = sin fase
PRIORIDADES = ["Alta", "Media", "Baja"]
BUSY_TIMEOUT_MS = 15_000         # cuánto espera una escritura a que otra termine antes de rendirse ("base ocupada")
AJUSTES_POR_DEFECTO = {          # se insertan solo si faltan; la Automatización (fase D) los usará
    "programacion": {"activa": False, "horas": ["09:00"], "ultimas": {}},
    "fuentes_activas": {s: True for s in config.SITIOS},
    "alertas": {"notificar_navegador": False, "sueldo_minimo": None},
    "soporte": {"incluir": True},   # mostrar la categoría Soporte TI en Ofertas (si no, va a "Fuera de perfil")
}


def leer_ajuste(con, clave: str) -> dict:
    """El ajuste guardado, completado con los valores por defecto (una base v7 anterior puede no tenerlo)."""
    fila = con.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    guardado = json.loads(fila[0]) if fila else {}
    return {**AJUSTES_POR_DEFECTO.get(clave, {}), **(guardado if isinstance(guardado, dict) else {})}


def guardar_soporte(con, datos) -> dict:
    """POST /api/ajustes/soporte: solo {"incluir": true|false}."""
    if not isinstance(datos, dict) or set(datos) != {"incluir"} or not isinstance(datos["incluir"], bool):
        raise ErrorDatos(400, 'se espera {"incluir": true} o {"incluir": false}')
    with transaccion(con):
        con.execute("INSERT OR REPLACE INTO ajustes (clave, valor) VALUES ('soporte', ?)", (json.dumps({"incluir": datos["incluir"]}),))
    return {"incluir": datos["incluir"]}


class BaseOcupada(Exception):
    """Otra escritura tuvo la base tomada más de BUSY_TIMEOUT_MS: no se escribió nada."""


def es_base_ocupada(ex: Exception) -> bool:
    return isinstance(ex, sqlite3.OperationalError) and ("locked" in str(ex) or "busy" in str(ex))


def _abrir(path) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    con.row_factory = sqlite3.Row
    con.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT_MS)}")
    con.execute("PRAGMA journal_mode = WAL")       # la página lee mientras una búsqueda escribe
    return con


class transaccion:
    """BEGIN IMMEDIATE ... COMMIT: toma el turno de escritura al EMPEZAR (no a mitad de camino, que es lo que provoca
    "database is locked"). Si algo falla, ROLLBACK: nunca queda nada escrito a medias."""
    def __init__(self, con):
        self.con = con

    def __enter__(self):
        if self.con.in_transaction:
            self.con.commit()
        try:
            self.con.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as ex:
            if es_base_ocupada(ex):
                raise BaseOcupada(str(ex)) from ex
            raise
        return self.con

    def __exit__(self, tipo, ex, tb):
        self.con.execute("COMMIT" if tipo is None else "ROLLBACK")
        if ex is not None and es_base_ocupada(ex):
            raise BaseOcupada(str(ex)) from ex
        return False


def _migrar_v7(con) -> None:
    """-> v7, en UNA transacción (si algo falla, la base queda como estaba): columnas de seguimiento (incluida
    prioridad_manual), corridas.origen y las tablas ajustes, alertas y pruebas_fuentes. Idempotente."""
    with transaccion(con):
        existentes = {r[1] for r in con.execute("PRAGMA table_info(ofertas)")}
        for col in COLUMNAS_SEGUIMIENTO:          # una base de la app Node ya trae notas, fecha_postulacion y fase
            if col not in existentes:
                con.execute(f"ALTER TABLE ofertas ADD COLUMN {col} TEXT DEFAULT ''")
        if "origen" not in {r[1] for r in con.execute("PRAGMA table_info(corridas)")}:
            con.execute("ALTER TABLE corridas ADD COLUMN origen TEXT DEFAULT 'manual'")
        con.execute("CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
        con.executemany("INSERT OR IGNORE INTO ajustes (clave, valor) VALUES (?, ?)",
                        [(k, json.dumps(v)) for k, v in AJUSTES_POR_DEFECTO.items()])
        con.execute("""CREATE TABLE IF NOT EXISTS alertas (url TEXT PRIMARY KEY REFERENCES ofertas(url),
                       corrida_id INTEGER, creada_en TEXT, leida INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS pruebas_fuentes (fuente TEXT PRIMARY KEY, probada_en TEXT,
                       ok INTEGER, ms INTEGER, resultados INTEGER, detalle TEXT)""")
        malas = con.execute(f"SELECT COUNT(*) FROM ofertas WHERE COALESCE(fase, '') NOT IN "
                            f"({', '.join('?' * len(FASES))})", FASES).fetchone()[0]
        if malas:
            raise ValueError(f"{plural(malas, 'oferta tiene', 'ofertas tienen')} una fase no válida: "
                             "no se migró nada (la base quedó como estaba)")
        con.execute(f"PRAGMA user_version = {VERSION_DB}")


def conectar(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    con = _abrir(path)
    existe = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ofertas'").fetchone()
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if existe and version in (2, 3, 4):
        repetidas = 0
        if version == 2:
            repetidas += _migrar_v2(con)
        if version <= 2 or version == 3:
            _migrar_v3(con)
        repetidas += _migrar_v4(con)
        if repetidas:
            print(f"Base de datos actualizada: {plural(repetidas, 'duplicada', 'duplicadas')} entre fuentes eliminadas")
    elif existe and version not in (5, 6, VERSION_DB):  # base de una versión desconocida: se respalda
        con.close()
        base, ext = os.path.splitext(path)
        respaldo = f"{base}_antigua_{datetime.now():%Y%m%d%H%M%S}{ext}"
        os.replace(path, respaldo)
        print(f"Base de datos anterior respaldada como {respaldo}")
        con = _abrir(path)
        version = 0
    con.execute("""
        CREATE TABLE IF NOT EXISTS ofertas (
            url TEXT PRIMARY KEY, clave TEXT UNIQUE,
            titulo TEXT, empresa TEXT, ubicacion TEXT, publicada TEXT, raw TEXT,
            categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT, modalidad TEXT,
            contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT,
            estado TEXT DEFAULT 'nueva', busqueda TEXT, detectada_en TEXT,
            fuente TEXT DEFAULT 'indeed', clave_base TEXT, ciudad TEXT DEFAULT '')""")
    con.execute("""CREATE TABLE IF NOT EXISTS corridas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT, fin TEXT, nuevas INTEGER, detalle TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS terminos_no_disponibles (
        sitio TEXT, termino TEXT, hasta TEXT, PRIMARY KEY (sitio, termino))""")
    con.commit()
    if version < VERSION_DB:          # solo cuando hace falta: así cada petición no toma el turno de escritura
        _migrar_v7(con)
    return con


def _duplicada(con, f: dict) -> bool:
    """¿Ya tenemos esta oferta (aunque venga de otra fuente o con otra URL)?
    Misma ciudad, o una de las dos sin ciudad (Glassdoor entrega solo 'Chile')."""
    if f["ciudad"]:
        fila = con.execute("SELECT 1 FROM ofertas WHERE clave_base = ? AND (ciudad = ? OR ciudad = '' "
                           "OR ciudad IS NULL)", (f["clave_base"], f["ciudad"])).fetchone()
    else:
        fila = con.execute("SELECT 1 FROM ofertas WHERE clave_base = ?", (f["clave_base"],)).fetchone()
    return fila is not None


def guardar(con, filas: list[dict]) -> int:
    """Inserta ofertas nuevas. Devuelve cuántas fueron nuevas y relevantes (no descartadas)."""
    nuevas = 0
    for f in filas:
        if _duplicada(con, f):
            continue
        cur = con.execute(
            """INSERT OR IGNORE INTO ofertas
               (url, clave, clave_base, ciudad, titulo, empresa, ubicacion, publicada, raw,
                categoria, razon, tipo, prioridad, modalidad, contrato, sueldo, experiencia,
                motivo, busqueda, detectada_en, fuente)
               VALUES (:url, :clave, :clave_base, :ciudad, :titulo, :empresa, :ubicacion,
                :publicada, :raw, :categoria, :razon, :tipo, :prioridad, :modalidad, :contrato,
                :sueldo, :experiencia, :motivo, :busqueda, :detectada_en, :fuente)""", f)
        if cur.rowcount and f["categoria"] != "descartada":
            nuevas += 1
    con.commit()
    return nuevas


def reclasificar(con) -> Counter:
    """Re-aplica la configuración actual a todo lo guardado (conserva el estado)."""
    for fila in con.execute("SELECT url, raw FROM ofertas").fetchall():
        cl = clasificar(json.loads(fila["raw"]))
        con.execute(
            "UPDATE ofertas SET " + ", ".join(f"{c} = :{c}" for c in CAMPOS_CLASIF)
            + " WHERE url = :url", {**cl, "url": fila["url"]})
    con.commit()
    return Counter(r[0] for r in con.execute("SELECT categoria FROM ofertas"))


def _afectada_por_soporte_o_sap(fila) -> bool:
    """La regla (no una lista de URLs) de las ofertas que tocan las reglas de soporte y de SAP / ERP."""
    return fila["razon"] == "soporte / helpdesk" or re.search(r"\bsap\b", normalizar(fila["titulo"] or "")) is not None


def _afectada_por_genero_o_automatizacion(fila) -> bool:
    """Commit (c): títulos con formas de género ("ingeniero/a", "supervisor(a)") o con "automatización"."""
    t = normalizar(fila["titulo"] or "")
    return sin_genero(t) != t or "automatizacion" in t


SELECCIONES_DIRIGIDAS = {"soporte-sap": _afectada_por_soporte_o_sap, "genero-automatizacion": _afectada_por_genero_o_automatizacion}


def reclasificar_dirigida(con, escribir: bool = True, seleccion=_afectada_por_soporte_o_sap) -> list[dict]:
    """Re-aplica la clasificación SOLO a las ofertas de la selección, y solo escribe las que cambian. A diferencia de
    reclasificar(), no toca el resto (aunque el código actual las clasificara distinto). Nunca toca el estado ni las
    columnas de seguimiento. Devuelve los cambios [{url, titulo, antes, despues}]; con escribir=False solo simula."""
    def calcular():
        cambios = []
        for fila in con.execute("SELECT * FROM ofertas").fetchall():
            if not seleccion(fila):
                continue
            nueva = clasificar(json.loads(fila["raw"]))
            antes = {c: fila[c] for c in CAMPOS_CLASIF}
            despues = {c: nueva[c] for c in CAMPOS_CLASIF}
            if antes != despues:
                cambios.append({"url": fila["url"], "titulo": fila["titulo"], "antes": antes, "despues": despues})
                if escribir:
                    con.execute("UPDATE ofertas SET " + ", ".join(f"{c} = ?" for c in CAMPOS_CLASIF) + " WHERE url = ?",
                                [despues[c] for c in CAMPOS_CLASIF] + [fila["url"]])
        return cambios
    if not escribir:
        return calcular()
    with transaccion(con):              # todo o nada
        return calcular()


# ------------------------------------------------------------------ scraping
def a_raw(r, fuente="indeed") -> dict:
    """Extrae de una fila de JobSpy solo lo que necesita el clasificador."""
    remoto = r.get("is_remote")
    return {
        "job_url": texto(r.get("job_url")), "title": texto(r.get("title")),
        "company": texto(r.get("company")), "location": texto(r.get("location")),
        "description": texto(r.get("description")), "date_posted": texto(r.get("date_posted")),
        "is_remote": False if remoto is None or pd.isna(remoto) else bool(remoto),
        "min_amount": numero(r.get("min_amount")), "max_amount": numero(r.get("max_amount")),
        "currency": texto(r.get("currency")), "interval": texto(r.get("interval")),
        "fuente": fuente, **({"posted_at": texto(r.get("posted_at"))} if texto(r.get("posted_at")) else {}),
    }


def ventanas_efectivas(con, ahora: datetime) -> dict:
    """Días de antigüedad por fuente: el configurado, o más si pasaron días sin buscar (días desde el fin de la última
    búsqueda + 1, en fechas de Chile), con tope DIAS_MAXIMOS. Sin búsquedas previas, el configurado."""
    hueco = 0
    fila = con.execute("SELECT fin FROM corridas ORDER BY id DESC LIMIT 1").fetchone()
    if fila and fila["fin"]:
        try:
            fin = datetime.strptime(fila["fin"][:10], "%Y-%m-%d").date()
            hueco = (ahora.astimezone(ZONA).date() - fin).days + 1
        except ValueError:
            pass
    return {s: min(config.DIAS_MAXIMOS, max(config.MAX_ANTIGUEDAD_DIAS.get(s, 1), hueco)) for s in config.SITIOS}


def recientes(df: pd.DataFrame, fuente: str, ahora: datetime, dias: int) -> tuple[pd.DataFrame, int]:
    """Separa por antigüedad antes de clasificar: devuelve (las recientes y las sin fecha, cuántas antiguas se omiten)."""
    if df.empty:
        return df, 0
    viva = [antiguedad(a_raw(r, fuente), ahora, dias) != "antigua" for r in df.to_dict("records")]
    return df[viva], viva.count(False)


def procesar(df: pd.DataFrame, busqueda: str, fuente: str = "indeed") -> list[dict]:
    ahora = ahora_chile().strftime("%Y-%m-%d %H:%M")
    filas = []
    for _, r in df.iterrows():
        raw = a_raw(r, fuente)
        if not raw["job_url"] or not raw["title"]:
            continue
        filas.append({
            "url": raw["job_url"], "titulo": raw["title"], "empresa": raw["company"],
            "ubicacion": raw["location"], "publicada": raw["date_posted"], "fuente": fuente,
            "clave": clave_oferta(raw["title"], raw["company"], raw["location"]),
            "clave_base": base_oferta(raw["title"], raw["company"]),
            "ciudad": ciudad_de(raw["location"]),
            "raw": json.dumps(raw, ensure_ascii=False), **clasificar(raw),
            "busqueda": busqueda, "detectada_en": ahora,
        })
    return filas


REMOTO = "Chile (remoto)"


def consulta(sitio: str, termino: str, lugar: str, resultados: int | None = None, dias: int | None = None) -> dict:
    """Parámetros de scrape_jobs para cada fuente. Indeed filtra por horas exactas (24 por día); Glassdoor solo por días
    enteros y descarta su propio día límite, así que se le pide uno más para incluir "ayer"."""
    dias = dias or config.MAX_ANTIGUEDAD_DIAS.get(sitio, 1)
    remoto = lugar == REMOTO
    kw = dict(
        site_name=[sitio],
        search_term=f"{termino} remoto" if remoto else termino,
        location="Chile" if remoto else lugar,
        results_wanted=resultados or config.RESULTADOS_POR_BUSQUEDA,
        hours_old=24 * (dias + 1 if sitio == "glassdoor" else dias), verbose=0,
    )
    if sitio == "indeed":
        kw["country_indeed"] = "Chile"
    elif sitio == "glassdoor":
        kw["country_indeed"] = "usa"   # JobSpy no tiene dominio Glassdoor para Chile: rodeo vía glassdoor.com
    return kw


def _termino_recordado_404(con, sitio, termino) -> bool:
    fila = con.execute("SELECT hasta FROM terminos_no_disponibles WHERE sitio = ? AND termino = ?",
                       (sitio, termino)).fetchone()
    return bool(fila and fila["hasta"] >= datetime.now().strftime("%Y-%m-%d"))


def _recordar_404(con, sitio, termino):
    hasta = (datetime.now() + timedelta(days=config.DIAS_RECORDAR_404)).strftime("%Y-%m-%d")
    con.execute("INSERT OR REPLACE INTO terminos_no_disponibles VALUES (?, ?, ?)", (sitio, termino, hasta))
    con.commit()


def _terminos_portal(sitio):
    return {"bne": config.TERMINOS_BNE, "trabajando": config.TERMINOS_TRABAJANDO,
            "chiletrabajos": config.TERMINOS_CHILETRABAJOS}[sitio]


def _es_candidata(raw: dict) -> bool:
    """Una oferta nueva cuyo listado (recortado) todavía puede resultar útil con el detalle: ya sirve, o es un rol
    puente al que solo le faltan señales (que el texto completo puede aportar). Lo demás (senior, práctica, fuera de
    zona...) no cambia con más texto."""
    cl = clasificar(raw)
    return cl["categoria"] == "principal" or cl["razon"].startswith("rol puente con")


def _buscar_portal(con, sitio, st, avisos, cliente, robots, ahora: datetime | None = None, dias: int | None = None) -> int:
    """BNE / Trabajando / Chiletrabajos: lista términos, deja fuera las antiguas, abre el detalle de las nuevas
    candidatas (con tope) y guarda."""
    mod, nombre = PORTALES[sitio], config.NOMBRE_FUENTE[sitio]
    ahora, dias = ahora or ahora_chile(), dias or config.MAX_ANTIGUEDAD_DIAS.get(sitio, 1)
    terminos = _terminos_portal(sitio)
    frames, seguidos, sin_pagina = [], 0, []
    for i, termino in enumerate(terminos, start=1):
        if sitio == "trabajando" and _termino_recordado_404(con, sitio, termino):
            sin_pagina.append(termino)
            continue
        try:
            df = mod.listar(termino, cliente, robots)
        except Bloqueo as e:
            avisos.append(f"⚠ {nombre} se detuvo: {e}. No se reintenta ni se esquiva; revisa el sitio a mano.")
            break
        except NoEncontrada:
            _recordar_404(con, sitio, termino)
            sin_pagina.append(termino)
            _say(f"  [{sitio} {i}/{len(terminos)}] {termino}: sin página en el sitio "
                 f"(se recuerda {plural(config.DIAS_RECORDAR_404, 'día', 'días')})")
            continue
        except ErrorFuente as e:
            st["errores"] += 1
            seguidos += 1
            _say(f"  ! [{sitio}] {termino}: {e}")
            if seguidos >= config.ERRORES_SEGUIDOS_PARA_ABORTAR:
                avisos.append(f"⚠ {nombre}: {seguidos} errores seguidos; se dejó de insistir en esta corrida.")
                break
            continue
        seguidos = 0
        df, antiguas = recientes(df, sitio, ahora, dias)   # antes de clasificar y de abrir detalles
        st["encontradas"] += len(df)
        st["antiguas"] = st.get("antiguas", 0) + antiguas
        _say(f"  [{sitio} {i}/{len(terminos)}] {termino}: {plural(len(df), 'encontrada', 'encontradas')}"
             + (f" ({plural(antiguas, 'antigua omitida', 'antiguas omitidas')})" if antiguas else ""))
        frames.append(df)
    if sin_pagina:
        avisos.append(f"{nombre}: sin página para {', '.join(sin_pagina)}")
    if not frames:
        return 0

    # una fila por URL; las ya guardadas no se vuelven a pedir ni a clasificar
    filas = {}
    for df in frames:
        for r in df.to_dict("records"):
            filas.setdefault(r["job_url"], r)
    conocidas = {u for (u,) in con.execute("SELECT url FROM ofertas")}
    nuevas = [r for u, r in filas.items() if u not in conocidas]
    candidatas = [r for r in nuevas if _es_candidata(a_raw(r, sitio))]
    candidatas.sort(key=lambda r: texto(r.get("date_posted")), reverse=True)

    # detalle de las que alcanzan; las demás candidatas no se guardan (quedan para la próxima corrida)
    excluir, pendientes, cerradas, detenido = set(), 0, 0, False
    for n, r in enumerate(candidatas):
        if detenido or n >= config.MAX_DETALLES[sitio]:
            excluir.add(r["job_url"])
            pendientes += 1
            continue
        try:
            det = mod.detalle(r["job_url"], cliente, robots)
        except Bloqueo as e:
            avisos.append(f"⚠ {nombre} se detuvo al abrir un detalle: {e}. No se reintenta ni se esquiva.")
            detenido = True
            excluir.add(r["job_url"])
            pendientes += 1
            continue
        except ErrorFuente as e:
            st["errores"] += 1
            _say(f"  ! [{sitio}] detalle: {e}")
            excluir.add(r["job_url"])
            pendientes += 1
            continue
        if not mod.completar(r, det):      # el sitio dice que ya no está vigente
            excluir.add(r["job_url"])
            cerradas += 1
    if pendientes:
        avisos.append(f"{nombre}: {plural(pendientes, 'candidata espera', 'candidatas esperan')} a la próxima corrida "
                      "(tope de detalles por corrida)")
    if cerradas:
        avisos.append(f"{nombre}: {cerradas} avisos ya vencidos o finalizados, omitidos")

    guardar_filas = [r for u, r in filas.items() if u not in excluir]
    out = procesar(pd.DataFrame(guardar_filas, columns=mod.COLUMNAS), f"{sitio} | portal", sitio)
    nuevas_rel = guardar(con, out)
    st["relevantes"] += nuevas_rel
    st["sin_chile"] += sum(f["razon"].startswith("ubicación no reconocida") for f in out)
    return nuevas_rel


def buscar_ofertas(con) -> int:
    from jobspy import scrape_jobs  # import aquí: los tests no lo necesitan

    lugares = list(config.UBICACIONES) + ([REMOTO] if config.INCLUIR_REMOTO else [])
    plan = [(s, t, l) for s in config.SITIOS if s not in PORTALES
            for t in (config.TERMINOS_A + config.TERMINOS_B if s == "indeed" else config.TERMINOS_SECUNDARIOS)
            for l in (["Chile"] if s == "getonboard" else lugares)]   # la API de Get on Board no usa ubicación
    stats = {s: {"encontradas": 0, "antiguas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0} for s in config.SITIOS}
    total = 0
    avisos = []
    ahora = ahora_chile()
    inicio = ahora.strftime("%Y-%m-%d %H:%M")
    ventanas = ventanas_efectivas(con, ahora)
    ampliadas = [config.NOMBRE_FUENTE[s] for s in config.SITIOS if ventanas[s] > config.MAX_ANTIGUEDAD_DIAS.get(s, 1)]
    if ampliadas:
        avisos.append(f"Pasaron días sin buscar: ventana ampliada a {plural(max(ventanas.values()), 'día', 'días')} "
                      f"({', '.join(ampliadas)}) para no perder ofertas de ese hueco.")
    for n, (sitio, termino, lugar) in enumerate(plan, start=1):
        etiqueta = f"{termino} | {lugar}"
        st = stats[sitio]
        try:
            if sitio == "getonboard":
                df = getonboard.buscar(termino, config.RESULTADOS_POR_BUSQUEDA)
            else:
                df = scrape_jobs(**consulta(sitio, termino, lugar, dias=ventanas[sitio]))
        except Exception as e:
            st["errores"] += 1
            _say(f"  ! [{sitio}] {etiqueta}: {type(e).__name__}: {e}")
            continue
        df, antiguas = recientes(df, sitio, ahora, ventanas[sitio])   # antes de clasificar: no se guardan ni cuentan
        filas = procesar(df, f"{sitio} | {etiqueta}", sitio)
        nuevas = guardar(con, filas)
        total += nuevas
        st["encontradas"] += len(df)
        st["antiguas"] += antiguas
        st["relevantes"] += nuevas
        st["sin_chile"] += sum(f["razon"].startswith("ubicación no reconocida") for f in filas)
        _say(f"  [{n}/{len(plan)}] {sitio} | {etiqueta}: {plural(len(df), 'encontrada', 'encontradas')}, "
             f"{plural(nuevas, 'nueva relevante', 'nuevas relevantes')}"
             + (f", {plural(antiguas, 'antigua omitida', 'antiguas omitidas')}" if antiguas else ""))
        time.sleep(config.PAUSA_ENTRE_BUSQUEDAS)

    activos = [s for s in config.SITIOS if s in PORTALES]
    if activos:
        cliente, robots = ClienteHTTP(), GestorRobots(USER_AGENT_HTTP)
        for sitio in activos:
            total += _buscar_portal(con, sitio, stats[sitio], avisos, cliente, robots, ahora, ventanas[sitio])

    _say("\nPor fuente (encontradas / relevantes nuevas / descartadas por no ser Chile / errores / antiguas omitidas):")
    for sitio, st in stats.items():
        aviso = ""
        if st["encontradas"] and st["sin_chile"] == st["encontradas"]:
            aviso = "   <- ninguna reconocida como Chile: esta fuente no resuelve bien la ubicación"
        elif st["encontradas"] == 0 and st["errores"] == 0:
            aviso = "   <- sin resultados (¿bloqueo?)"
        _say(f"  {config.NOMBRE_FUENTE[sitio]}: {st['encontradas']} / {st['relevantes']} / "
              f"{st['sin_chile']} / {st['errores']} / {st['antiguas']}{aviso}")
    for a in avisos:
        _say("  " + a)
    detalle = {"fuentes": [{"fuente": config.NOMBRE_FUENTE[s], **st, "ventana_dias": ventanas[s]}
                           for s, st in stats.items()],
               "ventana_dias": ventanas, "avisos": avisos}
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES (?, ?, ?, ?)",
                (inicio, ahora_chile().strftime("%Y-%m-%d %H:%M"), total, json.dumps(detalle, ensure_ascii=False)))
    con.commit()
    return total


# ------------------------------------------------------------------ datos para la página
def ofertas_para_pagina(con) -> dict:
    """Lo que muestra la página: ofertas principales (ordenadas), fuera de perfil, sospechosas y descartadas recientes."""
    def filas(sql, args=()):
        return [dict(r) for r in con.execute(sql, args)]

    # una postulación en curso se ve siempre en Seguimiento, aunque una reclasificación la saque de 'principal'
    seguimiento = "estado IN ('postulada', 'entrevista')"
    principal = [_con_prioridad_mostrada(f) for f in filas(f"SELECT * FROM ofertas WHERE categoria = 'principal' OR {seguimiento}")]
    principal.sort(key=lambda f: f["publicada"] or "", reverse=True)   # más recientes primero
    principal.sort(key=lambda f: (f["estado"] in ESTADOS_CERRADOS,
                                  ORDEN_PRIORIDAD.get(f["prioridad"], 9),
                                  ORDEN_MODALIDAD.get(f["modalidad"], 9)))
    campos = "url, titulo, empresa, ubicacion, publicada, fuente, estado, detectada_en, razon, motivo"
    otra = f"NOT ({seguimiento})"              # las que ya están en principal no se repiten en otra lista
    datos = {
        "principal": principal,
        "fuera_perfil": filas(f"SELECT {campos} FROM ofertas WHERE categoria = 'fuera_perfil' AND {otra} "
                              "ORDER BY detectada_en DESC"),
        "sospechosas": filas(f"SELECT {campos} FROM ofertas WHERE categoria = 'sospechosa' AND {otra} "
                             "ORDER BY detectada_en DESC"),
        "descartadas": filas(f"SELECT {campos} FROM ofertas WHERE categoria = 'descartada' AND {otra} "
                             f"ORDER BY detectada_en DESC, publicada DESC LIMIT {LIMITE_DESCARTADAS}"),
    }
    incluir_soporte = leer_ajuste(con, "soporte")["incluir"]
    if not incluir_soporte:     # oculto: el soporte sin decisión tuya se ve en "Fuera de perfil", como antes
        ocultas = [o for o in principal if o.get("tipo") == config.SOPORTE_TIPO and o["estado"] in ("nueva", "revisada")]
        datos["principal"] = [o for o in principal if o not in ocultas]
        datos["fuera_perfil"] = [{**{c.strip(): o.get(c.strip()) for c in campos.split(",")}, "razon": "soporte / helpdesk (oculto)"}
                                 for o in ocultas] + datos["fuera_perfil"]
    corridas = historial_corridas(con)
    for lista in datos.values():
        for o in lista:
            o["corrida_id"] = corrida_de(o.get("detectada_en"), corridas)
    datos["total_descartadas"] = con.execute(
        f"SELECT COUNT(*) FROM ofertas WHERE categoria = 'descartada' AND {otra}").fetchone()[0]
    datos["corridas"] = corridas
    datos["soporte_incluido"] = incluir_soporte
    return datos


def historial_corridas(con) -> list[dict]:
    """Las búsquedas registradas, la más reciente primero: {id, inicio, fin, nuevas, fuentes}."""
    corridas = []
    for r in con.execute("SELECT id, inicio, fin, nuevas, detalle FROM corridas ORDER BY inicio DESC, id DESC"):
        try:
            detalle = json.loads(r["detalle"] or "{}")
        except ValueError:
            detalle = {}
        fuentes = detalle.get("fuentes") if isinstance(detalle, dict) else None
        corridas.append({"id": r["id"], "inicio": r["inicio"], "fin": r["fin"], "nuevas": r["nuevas"] or 0,
                         "fuentes": fuentes if isinstance(fuentes, list) else []})
    return corridas


def corrida_de(detectada_en, corridas: list[dict]):
    """id de la corrida con inicio <= detectada_en <= fin (textos "AAAA-MM-DD HH:MM"); None si ninguna la cubre."""
    d = (detectada_en or "")[:16]
    if not d:
        return None
    for c in corridas:
        if c["inicio"] and c["fin"] and c["inicio"][:16] <= d <= c["fin"][:16]:
            return c["id"]
    return None


class ErrorDatos(Exception):
    """Pedido inválido desde la página: lleva el código HTTP que debe responder el servidor."""
    def __init__(self, codigo: int, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo


LIMITE_NOTAS = 5000
LIMITE_SUELDO_MANUAL = 100
ESTADOS_CON_FECHA = {"postulada", "entrevista"}


def _fecha_valida(valor) -> bool:
    """'' (sin fecha) o una fecha real AAAA-MM-DD."""
    if valor == "":
        return True
    if not isinstance(valor, str) or len(valor) != 10:
        return False
    try:
        return datetime.strptime(valor, "%Y-%m-%d").strftime("%Y-%m-%d") == valor
    except ValueError:
        return False


def _seguimiento(con, url) -> dict:
    fila = con.execute("SELECT estado, fecha_postulacion FROM ofertas WHERE url = ?", (url,)).fetchone()
    if fila is None:
        raise ErrorDatos(404, "la oferta no existe")
    return {"estado": fila["estado"], "fecha_postulacion": fila["fecha_postulacion"] or ""}


def marcar(con, url: str, estado: str = None, restaurar: dict = None) -> dict:
    """Cambia el estado de una oferta y devuelve {anterior, actual} (estado y fecha_postulacion) para poder deshacer.

    - Al entrar a postulada/entrevista sin fecha, se pone la de hoy (hora de Chile). Ningún cambio posterior la borra.
    - Deshacer: restaurar = {estado, fecha_postulacion, si_actual: {estado, fecha_postulacion}}. Deja exactamente el
      estado y la fecha anteriores, pero SOLO si la oferta sigue como la dejó el cambio que se deshace (si_actual):
      si alguien la cambió entre medias, 409 y no se toca nada."""
    if not isinstance(url, str) or not url:
        raise ErrorDatos(400, "falta la oferta")
    if restaurar is not None:
        if not isinstance(restaurar, dict) or not isinstance(restaurar.get("si_actual"), dict):
            raise ErrorDatos(400, "restaurar debe traer estado, fecha_postulacion y si_actual")
        for d in (restaurar, restaurar["si_actual"]):
            if d.get("estado") not in ESTADOS or not _fecha_valida(d.get("fecha_postulacion")):
                raise ErrorDatos(400, "estado o fecha no válidos en restaurar")
    elif estado not in ESTADOS:
        raise ErrorDatos(400, "estado no válido")
    with transaccion(con):
        anterior = _seguimiento(con, url)
        if restaurar is not None:
            esperado = {k: restaurar["si_actual"][k] for k in ("estado", "fecha_postulacion")}
            if anterior != esperado:
                raise ErrorDatos(409, "la oferta cambió después; no se deshizo para no pisar ese cambio")
            actual = {"estado": restaurar["estado"], "fecha_postulacion": restaurar["fecha_postulacion"]}
        else:
            fecha = anterior["fecha_postulacion"]
            if estado in ESTADOS_CON_FECHA and not fecha:
                fecha = ahora_chile().strftime("%Y-%m-%d")
            actual = {"estado": estado, "fecha_postulacion": fecha}
        con.execute("UPDATE ofertas SET estado = ?, fecha_postulacion = ? WHERE url = ?",
                    (actual["estado"], actual["fecha_postulacion"], url))
    return {"anterior": anterior, "actual": actual}


def marcar_estado(con, url: str, estado: str) -> bool:
    """Compatibilidad: True si se cambió el estado; False si el estado no existe o la oferta no está."""
    try:
        marcar(con, url, estado)
        return True
    except ErrorDatos:
        return False


def actualizar_seguimiento(con, url: str, cambios: dict) -> dict:
    """Actualización PARCIAL de lo que escribe la usuaria (solo las claves presentes). Devuelve la oferta guardada."""
    if not isinstance(url, str) or not url:
        raise ErrorDatos(400, "falta la oferta")
    if not isinstance(cambios, dict) or not cambios:
        raise ErrorDatos(400, "no hay nada que guardar")
    validos = {"notas", "fecha_postulacion", "fase", "sueldo_manual", "prioridad_manual"}
    desconocidos = set(cambios) - validos
    if desconocidos:
        raise ErrorDatos(400, "campos no permitidos: " + ", ".join(sorted(desconocidos)))
    for campo, valor in cambios.items():
        if not isinstance(valor, str):
            raise ErrorDatos(400, f"{campo} debe ser texto")
    if len(cambios.get("notas", "")) > LIMITE_NOTAS:
        raise ErrorDatos(400, f"las notas tienen más de {LIMITE_NOTAS} caracteres")
    if len(cambios.get("sueldo_manual", "")) > LIMITE_SUELDO_MANUAL:
        raise ErrorDatos(400, f"el sueldo tiene más de {LIMITE_SUELDO_MANUAL} caracteres")
    if "fecha_postulacion" in cambios and not _fecha_valida(cambios["fecha_postulacion"]):
        raise ErrorDatos(400, "la fecha debe ser AAAA-MM-DD")
    if cambios.get("fase", "") not in FASES:
        raise ErrorDatos(400, "fase no válida")
    if cambios.get("prioridad_manual", "") not in [""] + PRIORIDADES:
        raise ErrorDatos(400, "prioridad no válida")
    columnas = sorted(cambios)                    # nombres de una lista cerrada: nunca vienen del pedido tal cual
    with transaccion(con):
        _seguimiento(con, url)
        con.execute(f"UPDATE ofertas SET {', '.join(c + ' = ?' for c in columnas)} WHERE url = ?",
                    [cambios[c] for c in columnas] + [url])
        fila = con.execute("SELECT url, estado, notas, fecha_postulacion, fase, sueldo_manual, prioridad_manual, "
                           "prioridad FROM ofertas WHERE url = ?", (url,)).fetchone()
    return _con_prioridad_mostrada(dict(fila))


def _con_prioridad_mostrada(o: dict) -> dict:
    """'prioridad' pasa a ser la que se muestra (la manual si existe); la calculada queda en 'prioridad_calculada'."""
    o["prioridad_calculada"] = o.get("prioridad") or ""
    if o.get("prioridad_manual"):
        o["prioridad"] = o["prioridad_manual"]
    return o


def ultima_corrida(con):
    fila = con.execute("SELECT * FROM corridas ORDER BY id DESC LIMIT 1").fetchone()
    if not fila:
        return None
    d = dict(fila)
    d["detalle"] = json.loads(d.pop("detalle") or "{}")
    return d


def resumen(principal: list[dict]) -> str:
    def cuenta(campo):
        return ", ".join(f"{k} {v}" for k, v in Counter(f[campo] for f in principal).most_common())
    return (f"Tipo: {cuenta('tipo')}\nPrioridad: {cuenta('prioridad')}\n"
            f"Modalidad: {cuenta('modalidad')}")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--reclasificar", action="store_true",
                    help="re-aplica config.py a las ofertas guardadas, sin buscar de nuevo")
    ap.add_argument("--reclasificar-dirigida", action="store_true",
                    help="re-aplica la clasificación solo a las ofertas de la regla elegida (--regla)")
    ap.add_argument("--simular", action="store_true", help="con --reclasificar-dirigida: muestra los cambios sin guardarlos")
    ap.add_argument("--regla", choices=sorted(SELECCIONES_DIRIGIDAS), default="soporte-sap",
                    help="con --reclasificar-dirigida: qué ofertas se revisan (por defecto soporte-sap)")
    args = ap.parse_args()

    con = conectar()
    if args.reclasificar_dirigida:
        cambios = reclasificar_dirigida(con, escribir=not args.simular, seleccion=SELECCIONES_DIRIGIDAS[args.regla])
        print(("SIMULACIÓN (no se guardó nada): " if args.simular else "Guardado: ")
              + plural(len(cambios), "oferta cambia", "ofertas cambian"))
        for c in cambios:
            a, d = c["antes"], c["despues"]
            print(f"  {c['titulo'][:60]} | {a['categoria']}/{a['razon'] or a['tipo'] + ' ' + a['prioridad']} -> "
                  f"{d['categoria']}/{d['razon'] or d['tipo'] + ' ' + d['prioridad']}")
        return
    if args.reclasificar:
        print("Reclasificando lo guardado con la configuración actual...")
        print("  " + ", ".join(f"{k}: {v}" for k, v in reclasificar(con).items()))
        return
    print("Buscando ofertas (varios minutos; se muestra el avance de cada búsqueda)...")
    nuevas = buscar_ofertas(con)
    principal = ofertas_para_pagina(con)["principal"]
    print(f"\nListo: {plural(nuevas, 'nueva relevante', 'nuevas relevantes')}. "
          f"{plural(len(principal), 'oferta', 'ofertas')} en total.\n{resumen(principal)}\n"
          "Míralas en la página: python servidor.py  (o docker compose up -d)")


if __name__ == "__main__":
    main()
