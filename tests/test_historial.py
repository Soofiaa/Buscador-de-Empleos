"""Historial de búsquedas: asignación de corrida_id (Python) y filtro por día/hora de la página (JS real, con Node)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import buscar
from informe import PAGINA


def df_de(*filas):
    base = {"title": "", "company": "X", "location": "Santiago de Chile, RM, Chile", "description": "",
            "date_posted": None, "is_remote": False, "min_amount": None, "max_amount": None,
            "currency": "", "interval": ""}
    return pd.DataFrame([{**base, **f} for f in filas])


# ------------------------------------------------------------------ corrida_id (Python)
CORRIDAS = [{"id": 3, "inicio": "2026-10-11 13:40", "fin": "2026-10-11 13:45"},
            {"id": 2, "inicio": "2026-10-10 20:44", "fin": "2026-10-10 20:49"},
            {"id": 1, "inicio": "2026-10-10 09:00", "fin": "2026-10-10 09:05"}]


@pytest.mark.parametrize("detectada, esperado", [
    ("2026-10-10 20:44", 2),            # borde: igual al inicio
    ("2026-10-10 20:49", 2),            # borde: igual al fin
    ("2026-10-10 20:46", 2),
    ("2026-10-11 13:41", 3),
    ("2026-10-10 09:03:59", 1),         # con segundos: se compara "AAAA-MM-DD HH:MM"
    ("2026-10-10 20:50", None),         # justo después del fin
    ("2026-10-10 12:00", None),         # entre dos corridas
    ("2026-10-09 23:00", None),         # antes de la primera
    ("", None), (None, None),
])
def test_corrida_de(detectada, esperado):
    assert buscar.corrida_de(detectada, CORRIDAS) == esperado


def test_corrida_de_sin_historial():
    assert buscar.corrida_de("2026-10-10 20:44", []) is None


def test_ofertas_para_pagina_trae_corridas_y_corrida_id(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(df_de(
        {"job_url": "http://a", "title": "QA Tester", "is_remote": True},
        {"job_url": "http://b", "title": "QA Analyst", "is_remote": True},
        {"job_url": "http://c", "title": "QA Engineer", "is_remote": True},
        {"job_url": "http://d", "title": "QA Automation", "is_remote": True}), "t"))
    for url, cuando, cat in [("http://a", "2026-10-10 20:45", "principal"), ("http://b", "2026-10-11 13:40", "principal"),
                             ("http://c", "2026-10-01 08:00", "principal"), ("http://d", "2026-10-11 13:45", "descartada")]:
        con.execute("UPDATE ofertas SET detectada_en = ?, categoria = ? WHERE url = ?", (cuando, cat, url))
    fuentes = [{"fuente": "Indeed", "encontradas": 40, "relevantes": 9, "sin_chile": 0, "errores": 0}]
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES (?, ?, ?, ?)",
                ("2026-10-10 20:44", "2026-10-10 20:49", 1, json.dumps({"fuentes": fuentes, "avisos": []})))
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES (?, ?, ?, ?)",
                ("2026-10-11 13:40", "2026-10-11 13:45", 2, "no es json"))
    con.commit()
    d = buscar.ofertas_para_pagina(con)
    assert [c["id"] for c in d["corridas"]] == [2, 1]                       # la más reciente primero
    assert d["corridas"][1] == {"id": 1, "inicio": "2026-10-10 20:44", "fin": "2026-10-10 20:49", "nuevas": 1, "fuentes": fuentes}
    assert d["corridas"][0]["fuentes"] == []                                # detalle ilegible: sin fuentes, sin romper
    ids = {o["url"]: o["corrida_id"] for o in d["principal"] + d["descartadas"]}
    assert ids == {"http://a": 1, "http://b": 2, "http://c": None, "http://d": 2}
    con.close()


# ------------------------------------------------------------------ filtro de la página (JS con Node)
def correr_js(prueba: str):
    if not shutil.which("node"):
        pytest.skip("Node no está instalado")
    puras = re.search(r"// <puras>[^\n]*\n(.*?)// </puras>", PAGINA, re.S)
    assert puras, "la página debe marcar sus funciones puras con // <puras> ... // </puras>"
    codigo = puras.group(1) + "\nconsole.log(JSON.stringify((() => {" + prueba + "})()));"
    r = subprocess.run(["node", "-"], input=codigo, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


DATOS = """
const datos = {
  corridas: [
    {id: 3, inicio: "2026-10-11 13:40", fin: "2026-10-11 13:45", nuevas: 9, fuentes: []},
    {id: 2, inicio: "2026-10-10 20:44", fin: "2026-10-10 20:49", nuevas: 4, fuentes: []},
    {id: 1, inicio: "2026-10-10 09:00", fin: "2026-10-10 09:05", nuevas: 2, fuentes: []}],
  principal: [
    {url: "p1", estado: "nueva", corrida_id: 1}, {url: "p2", estado: "revisada", corrida_id: 2},
    {url: "p3", estado: "nueva", corrida_id: 3}, {url: "p4", estado: "nueva", corrida_id: null},
    {url: "s1", estado: "postulada", corrida_id: 1}, {url: "s2", estado: "entrevista", corrida_id: 3},
    {url: "s3", estado: "descartada", corrida_id: null}],
  fuera_perfil: [{url: "f1", corrida_id: 2}, {url: "f3", corrida_id: 3}],
  sospechosas: [{url: "x1", corrida_id: 1}, {url: "x0", corrida_id: null}],
  descartadas: [{url: "d1", corrida_id: 1}, {url: "d2", corrida_id: 2}, {url: "d3", corrida_id: 3}],
};
const PEST = ["ofertas", "seguimiento", "fuera_perfil", "sospechosas", "descartadas"];
const ver = sel => Object.fromEntries(PEST.map(p => [p, listaDe(datos, p, sel).map(o => o.url)]));
"""


def test_filtro_por_hora():
    r = correr_js(DATOS + 'return ver({tipo: "hora", id: 2});')
    assert r["ofertas"] == ["p2"] and r["fuera_perfil"] == ["f1"] and r["sospechosas"] == [] and r["descartadas"] == ["d2"]


def test_filtro_por_dia_incluye_todas_sus_corridas():
    r = correr_js(DATOS + 'return ver({tipo: "dia", dia: "2026-10-10"});')
    assert r["ofertas"] == ["p1", "p2"] and r["fuera_perfil"] == ["f1"]
    assert r["sospechosas"] == ["x1"] and r["descartadas"] == ["d1", "d2"]
    r = correr_js(DATOS + 'return ver({tipo: "dia", dia: "2026-10-11"});')
    assert r["ofertas"] == ["p3"] and r["descartadas"] == ["d3"] and r["sospechosas"] == []


def test_todas_y_antes_del_historial():
    r = correr_js(DATOS + 'return [ver({tipo: "todas"}), ver({tipo: "antes"})];')
    todas, antes = r
    assert todas["ofertas"] == ["p1", "p2", "p3", "p4"] and len(todas["descartadas"]) == 3
    assert antes["ofertas"] == ["p4"] and antes["sospechosas"] == ["x0"] and antes["descartadas"] == []


def test_seguimiento_no_se_filtra():
    r = correr_js(DATOS + 'return [{tipo: "todas"}, {tipo: "hora", id: 2}, {tipo: "dia", dia: "2026-10-11"}, {tipo: "antes"}]'
                          '.map(s => listaDe(datos, "seguimiento", s).map(o => o.url));')
    assert r == [["s1", "s2", "s3"]] * 4


def test_dias_franjas_titulos_y_progreso():
    r = correr_js(DATOS + """
      return {
        dias: agruparPorDia(datos.corridas).map(g => [g.dia, g.total, g.corridas.map(c => c.id)]),
        etiquetas: ["2026-10-11", "2026-10-10", "2026-10-08", "2026-09-30"].map(d => etiquetaDia(d, "2026-10-11")),
        ayerCambioDeMes: etiquetaDia("2026-09-30", "2026-10-01"),
        franjas: ["00:09", "05:59", "06:00", "12:00", "12:01", "19:59", "20:00", "23:53"].map(franja),
        titulos: [{tipo: "todas"}, {tipo: "dia", dia: "2026-10-10"}, {tipo: "hora", id: 2}, {tipo: "antes"}].map(s => tituloSeleccion(s, datos.corridas)),
        progreso: ["[12/40] indeed | qa: 5 encontradas", "  [bne 2/5] tester: 3 encontradas", "Iniciando la búsqueda...", "[0/0]"].map(progresoDe),
      };""")
    assert r["dias"] == [["2026-10-11", 9, [3]], ["2026-10-10", 6, [2, 1]]]
    assert r["etiquetas"] == ["Hoy", "Ayer", "Jueves 8 de octubre", "Miércoles 30 de septiembre"]
    assert r["ayerCambioDeMes"] == "Ayer"
    assert r["franjas"] == ["noche", "noche", "mañana", "mañana", "tarde", "tarde", "noche", "noche"]
    assert r["titulos"] == ["Todas las ofertas", "Sábado 10 de octubre", "Búsqueda de las 20:44", "Antes del historial"]
    assert r["progreso"] == [{"n": 12, "total": 40, "pct": 30}, {"n": 2, "total": 5, "pct": 40}, None, None]


def test_ultima_busqueda_relativa():
    r = correr_js('return ["2026-10-11 00:11", "2026-10-10 23:53", "2026-10-08 10:05"].map(f => terminoRelativo(f, "2026-10-11"));')
    assert r == ["hoy, terminó a las 00:11", "ayer, terminó a las 23:53", "el jueves 8 de octubre, terminó a las 10:05"]


def test_antes_del_historial_cuenta_solo_ofertas_activas():
    r = correr_js(DATOS + 'return listaDe(datos, "ofertas", {tipo: "antes"}).map(o => o.url);')
    assert r == ["p4"]                                    # s3 (descartada por ti, sin corrida) va a Seguimiento


def test_texto_de_progreso():
    r = correr_js("""return [
        "  [3/40] indeed | qa tester | Santiago: 25 encontradas, 2 nuevas relevantes",
        "[12/40] getonboard | analista de datos | Chile: 4 encontradas, 0 nuevas relevantes",
        "  [bne 2/5] tester: 3 encontradas",
        "  ! [indeed] qa | Santiago: HTTPError: 429",
        "Iniciando la búsqueda...", ""].map(textoProgreso);""")
    assert r == ["Buscando en Indeed · qa tester · 3 de 40",
                 "Buscando en Get on Board · analista de datos · 12 de 40",
                 "  [bne 2/5] tester: 3 encontradas",              # no calza: texto original
                 "  ! [indeed] qa | Santiago: HTTPError: 429",
                 "Iniciando la búsqueda...", ""]
