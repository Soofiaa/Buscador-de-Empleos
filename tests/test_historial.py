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

# "Sin descripción": ofertas que llegan sin texto (LinkedIn). Se gestionan como las de Ofertas, en su propia lista.
DATOS_SIN_DESCRIPCION = """
const datos = {
  corridas: [{id: 1, inicio: "2026-10-21 09:00", fin: "2026-10-21 09:05", nuevas: 3, fuentes: []}],
  principal: [{url: "p1", estado: "nueva", corrida_id: 1}],
  sin_descripcion: [
    {url: "v1", estado: "nueva", corrida_id: 1}, {url: "v2", estado: "revisada", corrida_id: 1},
    {url: "v3", estado: "descartada", corrida_id: 1}, {url: "v4", estado: "postulada", corrida_id: 1}],
};
const ver = p => listaDe(datos, p, {tipo: "todas"}).map(o => o.url);
"""


def test_sin_descripcion_muestra_las_abiertas_y_no_se_mezcla_con_ofertas():
    r = correr_js(DATOS_SIN_DESCRIPCION + 'return {pv: ver("sin_descripcion"), of: ver("ofertas")};')
    assert r["pv"] == ["v1", "v2"] and r["of"] == ["p1"]   # descartada y postulada salen de la cola


def test_lo_que_decides_en_sin_descripcion_se_ve_en_seguimiento_y_descartadas():
    r = correr_js(DATOS_SIN_DESCRIPCION + 'return {seg: ver("seguimiento"), desc: ver("descartadas_usuario")};')
    assert r["seg"] == ["v2", "v4"] and r["desc"] == ["v3"]


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


def test_seguimiento_y_descartadas_no_se_filtran_ni_pierden_decisiones():
    """Reemplaza a test_seguimiento_no_se_filtra. Antes Seguimiento mostraba postuladas, entrevistas y descartadas; ahora
    las descartadas tienen su propia pestaña (como en el diseño original) y "revisada" pasa a Seguimiento como "Por
    postular". La garantía es la misma: ninguna de las dos pestañas depende de la búsqueda elegida en el historial, y
    toda oferta con una decisión tuya (revisada, postulada, entrevista o descartada) aparece en una de ellas."""
    r = correr_js(DATOS + """
      const sels = [{tipo: "todas"}, {tipo: "hora", id: 2}, {tipo: "dia", dia: "2026-10-11"}, {tipo: "antes"}];
      const urls = (p, s) => listaDe(datos, p, s).map(o => o.url);
      const decididas = datos.principal.filter(o => o.estado !== "nueva").map(o => o.url).sort();
      return sels.map(s => {
        const seg = urls("seguimiento", s), desc = urls("descartadas_usuario", s);
        return {seg, desc, cubre: [...seg, ...desc].sort().join() === decididas.join(), comunes: seg.filter(u => desc.includes(u))};
      });""")
    assert r == [{"seg": ["p2", "s1", "s2"], "desc": ["s3"], "cubre": True, "comunes": []}] * 4


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
    assert r == ["p4"]                                    # s3 (descartada por ti, sin corrida) va a Descartadas


def test_el_buscador_de_la_pagina_tambien_mira_las_notas():
    r = correr_js("""
        const ofertas = [
          {url: "a", titulo: "Data analyst", empresa: "Falabella", notas: "[unión 2026-10-13] POR VERIFICAR: estados previos"},
          {url: "b", titulo: "Analista QA", empresa: "Axity", notas: ""},
          {url: "c", titulo: "Tester", empresa: "Uno", motivo: "verificación de calidad"},
          {url: "d", titulo: "Desarrollador", empresa: "Dos"}];
        const buscar = t => ofertas.filter(o => coincideTexto(o, t)).map(o => o.url);
        return [buscar("verificar"), buscar("UNION falabella"), buscar("axity qa"), buscar("verificación"), buscar("")];""")
    assert r == [["a"], ["a"], ["b"], ["c"], ["a", "b", "c", "d"]]   # sin tildes ni mayúsculas; todas las palabras


def test_el_buscador_de_la_pagina_acepta_fragmentos_de_palabra():
    """Coincidencia PARCIAL (subcadena), como siempre: "falab" encuentra Falabella y "verif" las POR VERIFICAR."""
    r = correr_js("""
        const o = {titulo: "Data analyst", empresa: "Falabella", ubicacion: "Las Condes", motivo: "rol de datos",
                   notas: "[unión 2026-10-13] POR VERIFICAR: estados previos"};
        return ["falab", "analy", "verif", "conde dat", "ion 2026", "LÁS", "falabellas"].map(t => coincideTexto(o, t));""")
    assert r == [True, True, True, True, True, True, False]   # un texto más largo que la palabra no calza


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


# ------------------------------------------------------------------ funciones de la interfaz (Fase 0)
def test_fechas_y_dias_desde_la_postulacion():
    r = correr_js("""return {
        cl: ["2026-10-12", "2026-10-12 09:30", "", "sin fecha"].map(fechaCL),
        dias: [["2026-10-13", "2026-10-13"], ["2026-10-12", "2026-10-13"], ["2026-09-30", "2026-10-13"],
               ["2026-12-31", "2027-01-01"], ["", "2026-10-13"], ["2026-10-20", "2026-10-13"]].map(([f, h]) => diasDesde(f, h)),
        seg: [null, 0, 1, 3, 4, 5, 6, 30].map(d => { const s = textoSeguimiento(d); return s && [s.texto, s.clase]; })};""")
    assert r["cl"] == ["12/10/2026", "12/10/2026", "", "sin fecha"]
    assert r["dias"] == [0, 1, 13, 1, None, 0]                         # una fecha futura no da días negativos
    assert r["seg"] == [None, ["⚡ Postulada hoy", "ok"], ["🌱 Hace 1 día", "ok"], ["🌱 Hace 3 días", "ok"],
                        ["⏱️ Hace 4 días (Revisar)", "aviso"], ["⏱️ Hace 5 días (Revisar)", "aviso"],
                        ["⚠️ Hace 6 días · Toca follow-up", "alerta"], ["⚠️ Hace 30 días · Toca follow-up", "alerta"]]


def test_sueldo_destacado_y_tecnologias():
    r = correr_js("""return {
        sueldo: ["$1.200.000", "No indicado", "A convenir", "no especificado", "Asignacion de colación", "", null].map(esSueldoDestacado),
        skills: [{titulo: "Analista QA", motivo: "Cypress, Postman y API REST; SQL"},
                 {titulo: "JavaScript Developer", motivo: "React y Node.js, CI/CD"},
                 {titulo: "Desarrollador", motivo: "javascript"},
                 {titulo: "Analista", tipo: "Power BI", motivo: "python sql jira docker git excel"}].map(extraerSkills)};""")
    assert r["sueldo"] == [True, False, False, False, False, False, False]
    assert r["skills"] == [["SQL", "REST", "Cypress", "QA", "Postman"], ["JavaScript", "React", "Node.js", "CI/CD"],
                           ["JavaScript"], ["Python", "SQL", "Jira", "Docker", "Git"]]   # "Java" no calza dentro de "JavaScript"; tope 5


def test_temas_y_pie_de_la_base():
    r = correr_js("""return {
        temas: ["girly-claro", "girly-oscuro", "hombre-claro", "hombre-oscuro", "neutro-claro", "neutro-oscuro",
                "girly", "hombre", "claro", "oscuro", null, "inventado"].map(normalizarTema),
        pie: [0, 1, 1017].map(textoTotalOfertas)};""")
    assert r["temas"] == ["girly-claro", "girly-oscuro", "hombre-claro", "hombre-oscuro", "neutro-claro", "neutro-oscuro",
                          "girly-claro", "hombre-oscuro", "neutro-claro", "neutro-oscuro", "girly-claro", "girly-claro"]
    assert r["pie"] == ["SQLite Conectado · 0 ofertas", "SQLite Conectado · 1 oferta", "SQLite Conectado · 1017 ofertas"]


def test_todos_los_textos_con_contador_concuerdan_en_singular_y_plural():
    r = correr_js("""
      const textos = Object.fromEntries(Object.entries(TXT).map(([k, f]) => [k, [0, 1, 2].map(f)]));
      textos.antiguas = [0, 1, 2].map(textoAntiguas);
      textos.ventana = [1, 2].map(n => textoVentana({ventana_dias: n}));
      textos.pie = [0, 1, 2].map(textoTotalOfertas);
      textos.seguimiento = [1, 2].map(d => textoSeguimiento(d).texto);
      return textos;""")
    assert r == {
        "activas": ["0 activas", "1 activa", "2 activas"],
        "relevantesNuevas": ["0 relevantes nuevas", "1 relevante nueva", "2 relevantes nuevas"],
        "ofertasRelevantesNuevas": ["0 ofertas relevantes nuevas", "1 oferta relevante nueva", "2 ofertas relevantes nuevas"],
        "busquedas": ["0 búsquedas", "1 búsqueda", "2 búsquedas"],
        "busquedasRegistradas": ["0 búsquedas registradas", "1 búsqueda registrada", "2 búsquedas registradas"],
        "encontradas": ["0 encontradas", "1 encontrada", "2 encontradas"],
        "nuevasRelevantes": ["0 nuevas relevantes", "1 nueva relevante", "2 nuevas relevantes"],
        "errores": ["0 errores", "1 error", "2 errores"],
        "antiguasOmitidas": ["0 antiguas omitidas", "1 antigua omitida", "2 antiguas omitidas"],
        "dias": ["0 días", "1 día", "2 días"],
        "diasAnteriores": ["0 días anteriores", "1 día anterior", "2 días anteriores"],
        "ofertas": ["0 ofertas", "1 oferta", "2 ofertas"],
        "masRecientes": ["0 más recientes", "1 más reciente", "2 más recientes"],
        "descartadasMasRecientes": ["0 descartadas más recientes", "1 descartada más reciente", "2 descartadas más recientes"],
        "respaldosIncompletos": ["0 respaldos incompletos", "1 respaldo incompleto", "2 respaldos incompletos"],
        "antiguas": ["0 antiguas omitidas", "1 antigua omitida", "2 antiguas omitidas"],
        "ventana": ["Ventana de antigüedad: hoy y ayer", "Ventana de antigüedad: hoy y los 2 días anteriores"],
        "pie": ["SQLite Conectado · 0 ofertas", "SQLite Conectado · 1 oferta", "SQLite Conectado · 2 ofertas"],
        "seguimiento": ["🌱 Hace 1 día", "🌱 Hace 2 días"],
    }


def test_la_pagina_no_arma_plurales_a_mano():
    """Todo contador pasa por plural()/TXT: no puede quedar un número pegado a una palabra en plural fija."""
    script = PAGINA.split("<script>")[1]
    palabras = r"(activas?|relevantes?|ofertas?|encontradas?|nuevas?|errore?s?|antiguas?|días?|búsquedas?|descartadas?|más recientes?)"
    assert not re.search(r'\+\s*"\s' + palabras + r"\b", script)             # n + " ofertas…"
    assert not re.search(r'===\s*1\s*\?\s*"\s?' + palabras + r"\b", script)  # n === 1 ? " oferta" : …


# ------------------------------------------------------------------ detalle y deshacer (Fase A)
def test_fases_de_la_pagina_son_las_del_servidor():
    import buscar
    r = correr_js('return {ids: FASES_PIPELINE.map(f => f.id), estados: ["postulacion", "rrhh", "oferta", "", "cv"].map(estadoDeFase)};')
    assert r["ids"] == [f for f in buscar.FASES if f]
    assert r["estados"] == ["postulada", "entrevista", "entrevista", None, None]


def test_prioridad_manual_se_nota_y_cambios_son_parciales():
    r = correr_js("""
      const o = {prioridad: "Media", prioridad_calculada: "Media", prioridad_manual: "", notas: "a", fecha_postulacion: "", fase: "", sueldo_manual: ""};
      const m = {prioridad: "Alta", prioridad_calculada: "Media", prioridad_manual: "Alta"};
      return {
        auto: etiquetaPrioridad(o), manual: etiquetaPrioridad(m),
        nada: cambiosSeguimiento(o, {notas: "a", fecha_postulacion: "", sueldo_manual: "", prioridad_manual: ""}),
        algo: cambiosSeguimiento(o, {notas: "a" + String.fromCharCode(10) + "b", fecha_postulacion: "2026-10-13", sueldo_manual: "", prioridad_manual: "Baja"}),
        errores: [[0, {}], [503, {}], [409, {}], [400, {error: "fase no válida"}], [500, null]].map(([s, j]) => mensajeError(s, j))};""")
    assert r["auto"] == {"texto": "Media", "titulo": None}
    assert r["manual"] == {"texto": "✍️ Alta", "titulo": "Prioridad puesta a mano (la calculada es Media)"}
    assert r["nada"] == {}
    assert r["algo"] == {"notas": "a\nb", "fecha_postulacion": "2026-10-13", "prioridad_manual": "Baja"}
    assert r["errores"] == ["Sin conexión con el servidor.", "La base está ocupada; reintenta en unos segundos.",
                            "La oferta cambió mientras tanto; no se aplicó para no pisar ese cambio.",
                            "No se pudo guardar: fase no válida", "No se pudo guardar."]


# ------------------------------------------------------------------ Fase B1
def test_textos_de_la_postulacion_manual_y_alcance_del_csv():
    r = correr_js("""return {
        msj: [[409, {error: "ya tienes esa URL"}], [413, {}], [503, {}], [400, {error: "falta titulo"}]].map(([s, j]) => mensajeManual(s, j)),
        alcance: ["seguimiento", "ofertas", "descartadas_usuario", "fuera_perfil"].map(alcanceExportar),
        sinUrl: [urlSegura("manual:abc"), urlSegura("javascript:alert(1)"), urlSegura("https://x.cl")]};""")
    assert r["msj"] == ["Ya la tienes registrada (ya tienes esa URL).", "El texto es demasiado largo.",
                        "La base está ocupada; reintenta en unos segundos.", "No se pudo guardar: falta titulo"]
    assert r["alcance"] == ["seguimiento", "principal", "principal", "principal"]
    assert r["sinUrl"] == ["#", "#", "https://x.cl"]


def test_linea_de_estado_del_respaldo():
    r = correr_js("""
      const ult = f => ({configurado: true, disponible: true, error_auto: "", ultimo: {fecha: f}});
      return [null, {configurado: false}, {configurado: true, disponible: false, error: "no montada"},
              {configurado: true, disponible: true, error_auto: "SinEspacio: disco lleno"}, {configurado: true, disponible: true, ultimo: null},
              ult("2026-10-13 09:30"), ult("2026-10-12 23:05"), ult("2026-10-01 08:00")].map(x => textoRespaldo(x, "2026-10-13"));""")
    assert r == [{"texto": "Respaldo automático no configurado", "clase": "apagado"},
                 {"texto": "Respaldo automático no configurado", "clase": "apagado"},
                 {"texto": "⚠️ Carpeta de respaldos no disponible", "clase": "error"},
                 {"texto": "⚠️ Falló el respaldo automático: SinEspacio: disco lleno", "clase": "error"},
                 {"texto": "Aún no hay respaldos", "clase": ""},
                 {"texto": "Último respaldo: hoy 09:30 ✓", "clase": "ok"},
                 {"texto": "Último respaldo: ayer 23:05 ✓", "clase": "ok"},
                 {"texto": "Último respaldo: 01/10/2026 08:00 ✓", "clase": "ok"}]
    con_incompletos = correr_js("""
      const r = (n, ult) => ({configurado: true, disponible: true, error_auto: "", incompletos: n, ultimo: ult});
      return [r(1, {fecha: "2026-10-13 09:30"}), r(2, null), r(null, {fecha: "2026-10-13 09:30"}), r(0, null)]
        .map(x => textoRespaldo(x, "2026-10-13"));""")
    assert con_incompletos == [
        {"texto": "Último respaldo: hoy 09:30 ✓ · ⚠️ 1 respaldo incompleto (sin huella .sha256)", "clase": "error"},
        {"texto": "Aún no hay respaldos válidos · ⚠️ 2 respaldos incompletos (sin huella .sha256)", "clase": "error"},
        {"texto": "Último respaldo: hoy 09:30 ✓", "clase": "ok"},              # con un respaldo en curso: null, sin aviso
        {"texto": "Aún no hay respaldos", "clase": ""}]

def test_busquedas_manuales_arman_urls_reales():
    r = correr_js("return busquedasManuales();")
    assert [b["sitio"] for b in r] == ["Computrabajo", "Empleos Públicos"]
    urls = [e["url"] for e in r[0]["enlaces"]]
    assert "https://cl.computrabajo.com/trabajo-de-analista-funcional" in urls
    assert "https://cl.computrabajo.com/trabajo-de-control-de-gestion" in urls          # sin tilde ni espacios
    assert all(re.fullmatch(r"https://cl\.computrabajo\.com/trabajo-de-[a-z0-9-]+", u) for u in urls)
    assert r[1]["enlaces"][0]["url"].startswith("https://www.empleospublicos.cl/")
