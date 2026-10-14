"""Fase C2: tablero de Seguimiento. Columnas, reglas de soltar (los 12 movimientos, O → E y P/C con fase final u oferta
→ E bloqueados, la fase nunca baja), "Mover a…" y "Descartar" con las mismas reglas, y los días en la tarjeta."""
import re
from pathlib import Path

from test_historial import correr_js

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")
ESTADOS = ["nueva", "revisada", "postulada", "entrevista", "descartada"]
FASES = ["", "postulacion", "rrhh", "tecnica", "final", "oferta"]
ORDEN_FASES = FASES                               # "" < postulacion < rrhh < tecnica < final < oferta
COMBOS = "const COMBOS = %s.flatMap(e => %s.map(f => ({url: e + '/' + f, estado: e, fase: f})));" % (ESTADOS, FASES)


def test_cada_combinacion_cae_en_exactamente_una_columna_o_fuera_del_tablero():
    r = correr_js(COMBOS + """
      return COMBOS.map(o => [o.estado, o.fase, columnaDe(o),
        COLUMNAS_TABLERO.filter(c => c.id === columnaDe(o)).length]);""")
    esperado = {"revisada": "P", "postulada": "C"}
    for estado, fase, col, veces in r:
        if estado in ("nueva", "descartada"):
            assert col is None and veces == 0, (estado, fase)        # descartada sale del tablero (pestaña Descartadas)
        elif estado == "entrevista":
            assert col == ("O" if fase in ("final", "oferta") else "E") and veces == 1, (estado, fase)
        else:
            assert col == esperado[estado] and veces == 1, (estado, fase)
    assert correr_js("return COLUMNAS_TABLERO.map(c => c.id);") == ["P", "C", "E", "O"]


# (estado, fase de la tarjeta, destino) -> {estado, fase} enviado
MOVIMIENTOS = [
    (("revisada", ""), "C", ("postulada", "postulacion")),            # P → C
    (("revisada", "rrhh"), "C", ("postulada", "rrhh")),
    (("revisada", ""), "E", ("entrevista", "rrhh")),                  # P → E
    (("revisada", "tecnica"), "E", ("entrevista", "tecnica")),
    (("revisada", ""), "O", ("entrevista", "final")),                 # P → O
    (("revisada", "oferta"), "O", ("entrevista", "oferta")),
    (("postulada", "postulacion"), "E", ("entrevista", "rrhh")),      # C → E
    (("postulada", ""), "O", ("entrevista", "final")),                # C → O
    (("postulada", "final"), "O", ("entrevista", "final")),
    (("entrevista", "tecnica"), "O", ("entrevista", "final")),        # E → O
    (("postulada", "postulacion"), "P", ("revisada", "postulacion")), # C → P
    (("entrevista", "rrhh"), "P", ("revisada", "rrhh")),              # E → P
    (("entrevista", ""), "C", ("postulada", "postulacion")),          # E → C
    (("entrevista", "rrhh"), "C", ("postulada", "rrhh")),
    (("entrevista", "final"), "P", ("revisada", "final")),            # O → P
    (("entrevista", "oferta"), "C", ("postulada", "oferta")),         # O → C
]


def test_los_movimientos_del_tablero():
    casos = [{"o": {"estado": e, "fase": f}, "d": d} for (e, f), d, _ in MOVIMIENTOS]
    r = correr_js("return %s.map(c => movimientoTablero(c.o, c.d));" % casos)
    for ((e, f), d, (estado, fase)), m in zip(MOVIMIENTOS, r):
        assert m == {"estado": estado, "fase": fase}, ((e, f), d, m)


def test_entrar_a_entrevistas_con_fase_final_u_oferta_se_bloquea_y_explica_el_motivo():
    r = correr_js("""return [["entrevista", "final"], ["entrevista", "oferta"], ["revisada", "final"], ["postulada", "oferta"]]
      .map(([estado, fase]) => movimientoTablero({estado, fase}, "E"));""")
    for m in r:
        assert set(m) == {"bloqueado"}
        assert "la fase no retrocede" in m["bloqueado"] and "Gestionar proceso" in m["bloqueado"]
    assert "«Entrevista Final»" in r[0]["bloqueado"] and "«Oferta / Cierre»" in r[1]["bloqueado"]


def test_soltar_en_la_misma_columna_no_envia_nada():
    r = correr_js(COMBOS + """
      return COMBOS.filter(o => columnaDe(o)).map(o => movimientoTablero(o, columnaDe(o)));""")
    assert r and all(m is None for m in r)


def test_la_fase_nunca_baja_desde_el_tablero():
    r = correr_js(COMBOS + """
      return COMBOS.filter(o => columnaDe(o)).flatMap(o => ["P", "C", "E", "O"].map(d => [o.fase, movimientoTablero(o, d)]));""")
    revisados = 0
    for fase, m in r:
        if m and "estado" in m:
            assert ORDEN_FASES.index(m["fase"]) >= ORDEN_FASES.index(fase), (fase, m)
            assert m["fase"] != "oferta" or fase == "oferta"                 # nunca se sube a 'oferta' desde el tablero
            revisados += 1
    assert revisados > 30


def test_descartar_cambia_solo_el_estado_y_la_saca_del_tablero():
    r = correr_js("""
      const o = {url: "u", estado: "entrevista", fase: "tecnica"};
      const m = movimientoTablero(o, "descartar");
      return [m.estado, "fase" in m && m.fase !== undefined, pedidoMarcar(o, m.estado, m.fase, "tablero"),
              columnaDe({...o, estado: m.estado}), movimientoTablero({...o, estado: "descartada"}, "descartar")];""")
    assert r == ["descartada", False, {"url": "u", "estado": "descartada", "origen": "tablero"}, None, None]


def test_mover_a_aplica_las_mismas_reglas():
    r = correr_js(COMBOS + """
      return COMBOS.filter(o => columnaDe(o)).map(o => [o, opcionesMoverA(o),
        ["P", "C", "E", "O"].map(d => { const m = movimientoTablero(o, d); return !m || !!m.bloqueado; })]);""")
    for o, opciones, bloqueadas in r:
        assert [x["valor"] for x in opciones] == ["P", "C", "E", "O", "descartar"]
        assert [x["deshabilitada"] for x in opciones[:4]] == bloqueadas, o
        assert opciones[4] == {"valor": "descartar", "texto": "❌ Descartar", "deshabilitada": False}
    o_fin = next(x for x in r if x[0]["estado"] == "entrevista" and x[0]["fase"] == "final")
    assert o_fin[1][2]["texto"].endswith("(la fase no retrocede)") and o_fin[1][3]["texto"].endswith("(aquí)")


def test_los_pedidos_del_tablero_van_por_marcar_con_origen_tablero():
    r = correr_js("""const o = {url: "u", estado: "revisada", fase: ""};
      const m = movimientoTablero(o, "C"); return pedidoMarcar(o, m.estado, m.fase, "tablero");""")
    assert r == {"url": "u", "estado": "postulada", "origen": "tablero", "fase": "postulacion"}
    cuerpo = re.search(r"async function moverEnTablero.*?\n}\n", PAGINA, re.S).group(0)
    assert 'cambiarSeguimiento(o, m.estado, m.fase, "tablero"' in cuerpo
    assert "pintarLista()" in cuerpo                                     # si falla, la tarjeta se repinta en su columna
    assert "/api/nota" not in cuerpo


def test_dias_en_la_tarjeta_sus_tres_casos():
    r = correr_js("""const hoy = "2026-10-20"; return [
      diasEnTarjeta({en_fase_desde: "2026-10-15T15:00:00+00:00", fecha_postulacion: "2026-10-01"}, hoy),
      diasEnTarjeta({en_fase_desde: null, fecha_postulacion: "2026-10-01"}, hoy),
      diasEnTarjeta({en_fase_desde: null, fecha_postulacion: ""}, hoy),
      diasEnTarjeta({}, hoy),
      diasEnTarjeta({en_fase_desde: "no es fecha", fecha_postulacion: "2026-10-18"}, hoy)];""")
    assert r == [{"dias": 5, "desde": "etapa"}, {"dias": 19, "desde": "postulacion"}, None, None,
                 {"dias": 2, "desde": "postulacion"}]


def test_dias_en_la_tarjeta_cerca_de_medianoche_en_santiago():
    r = correr_js("""return [
      diasEnTarjeta({en_fase_desde: "2026-10-14T02:30:00+00:00"}, "2026-10-14"),   // 23:30 del 13 en Chile (UTC-3)
      diasEnTarjeta({en_fase_desde: "2026-10-14T02:30:00+00:00"}, "2026-10-13"),
      diasEnTarjeta({en_fase_desde: "2026-10-14T03:30:00+00:00"}, "2026-10-14"),   // 00:30 del 14 en Chile
      diasEnTarjeta({en_fase_desde: "2026-07-15T03:30:00+00:00"}, "2026-07-15"),   // invierno (UTC-4): 23:30 del 14
      diaChile("2026-10-14T02:59:59+00:00"), diaChile("2026-10-14T03:00:00+00:00")];""")
    assert [x["dias"] for x in r[:4]] == [1, 0, 0, 1]
    assert r[4:] == ["2026-10-13", "2026-10-14"]


def test_textos_de_dias_en_la_tarjeta_con_singular_y_plural():
    r = correr_js("""return [textoDiasTarjeta({dias: 0, desde: "etapa"}), textoDiasTarjeta({dias: 1, desde: "etapa"}),
      textoDiasTarjeta({dias: 4, desde: "etapa"}), textoDiasTarjeta({dias: 1, desde: "postulacion"}), textoDiasTarjeta(null)];""")
    assert [x["texto"] for x in r[:4]] == ["🕒 En esta etapa desde hoy", "🕒 1 día en esta etapa", "🕒 4 días en esta etapa",
                                           "🌱 Hace 1 día"]
    assert r[4] is None


def test_tablero_en_el_dom_accesible_sin_innerhtml_y_vista_recordada():
    assert "innerHTML" not in PAGINA and "insertAdjacentHTML" not in PAGINA and "outerHTML" not in PAGINA
    col = re.search(r"function columnaTablero.*?\n}\n", PAGINA, re.S).group(0)
    assert 'h("section", { class: "kanban-col", "aria-label":' in col
    tarjeta = re.search(r"function tarjetaTablero.*?\n}\n", PAGINA, re.S).group(0)
    assert '"Mover a…"' in tarjeta and 'moverEnTablero(o, "descartar")' in tarjeta and "abrirDetalle(o" in tarjeta
    # el selector, los botones y los enlaces no inician un arrastre (Firefox no abre un <select> dentro de un draggable)
    assert 't.draggable = !e.target.closest("select, option, button, a, input, textarea")' in tarjeta
    assert 'S.vistaSeg = "tablero";' in PAGINA and 'localStorage.getItem("vistaSeguimiento") === "lista"' in PAGINA
    kpis = re.search(r"function kpisSeguimiento.*?\n}\n", PAGINA, re.S).group(0)
    assert "columnaDe(o)" in kpis and "o.estado ===" not in kpis           # indicadores = columnas del tablero
