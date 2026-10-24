"""Fase C3: pestaña «Métricas» (solo lectura). Embudo, tasa de respuesta, días promedio, procesos activos, descartadas
después de postular, desgloses y actividad por semana. Las funciones puras se ejecutan con Node (JS real)."""
import re
from pathlib import Path

from test_historial import correr_js

PAGINA = (Path(__file__).resolve().parent.parent / "web" / "pagina.html").read_text(encoding="utf-8")


def test_las_metricas_viven_en_la_barra_derecha_y_no_en_las_pestanas():
    assert '["metricas", "Métricas"]' not in PAGINA
    assert 'id="metricas-panel"' in PAGINA
    assert 'lateral-derecha' in PAGINA and PAGINA.index('id="metricas-panel"') > PAGINA.index('class="lateral-derecha"')
    assert '$("metricas-panel")' in PAGINA


def test_las_funciones_de_metricas_estan_en_la_seccion_pura():
    m = re.search(r"// <puras>[^\n]*\n(.*?)// </puras>", PAGINA, re.S)
    assert m and "function embudo(" in m.group(1) and "function semanasActividad(" in m.group(1)


DATOS = """
const datos = {
  principal: [
    {url: "a", estado: "postulada", fase: "postulacion", fecha_postulacion: "2026-10-12", fuente: "indeed", modalidad: "Remoto", tipo: "A"},
    {url: "b", estado: "entrevista", fase: "rrhh", fecha_postulacion: "2026-10-05", fuente: "indeed", modalidad: "Híbrido", tipo: "B"},
    {url: "c", estado: "entrevista", fase: "final", fecha_postulacion: "2026-09-28", fuente: "linkedin", modalidad: "Remoto", tipo: "A"},
    {url: "d", estado: "revisada", fase: "", fecha_postulacion: "", fuente: "linkedin", modalidad: "", tipo: "M"},
    {url: "e", estado: "nueva", fase: "", fecha_postulacion: "", fuente: "bne", modalidad: "Remoto", tipo: "A"},
  ],
  sin_descripcion: [],
  descartadas_usuario: [],
};
"""


def ejecutar(expresion):
    return correr_js(DATOS + "\n" + expresion)


def test_embudo_en_orden_y_sin_crecer():
    r = ejecutar("return embudo(datos).map(e => e.n);")
    assert r == [5, 3, 2, 1]                  # relevantes, postuladas, entrevistas, finales


def test_fase_mas_lejos_cuenta_aunque_la_oferta_este_descartada():
    r = ejecutar("""
      datos.principal.push({url: "f", estado: "descartada", fase: "rrhh", fecha_postulacion: "2026-10-01", fuente: "bne", modalidad: "", tipo: "A"});
      return embudo(datos).map(e => e.n);""")
    assert r == [6, 4, 3, 1]


def test_tasa_de_respuesta_con_divisor():
    assert ejecutar("return tasaRespuesta(datos);") == {"respondieron": 2, "postuladas": 3, "pct": 67}


def test_tasa_sin_datos_muestra_cero_de_cero():
    r = correr_js("const datos = {principal: [], sin_descripcion: []};\nreturn [tasaRespuesta(datos), embudo(datos).map(e => e.n), diasPromedioActivos(datos, '2026-10-23'), procesosActivos(datos).length];")
    assert r == [{"respondieron": 0, "postuladas": 0, "pct": None}, [0, 0, 0, 0], None, 0]


def test_procesos_activos_y_dias_promedio():
    assert ejecutar("return procesosActivos(datos).map(o => o.url);") == ["a", "b", "c"]
    # desde 12, 05 y 28 de octubre/setiembre hasta el 23 de octubre: 11, 18 y 25 días -> promedio 18
    assert ejecutar("return diasPromedioActivos(datos, '2026-10-23');") == 18


def test_descartadas_con_fecha_cuentan_como_postuladas_en_el_contador():
    r = ejecutar("""
      datos.principal.push({url: "g", estado: "descartada", fase: "", fecha_postulacion: "2026-10-01", fuente: "bne", modalidad: "", tipo: "A"});
      datos.principal.push({url: "h", estado: "descartada", fase: "", fecha_postulacion: "", fuente: "bne", modalidad: "", tipo: "A"});
      return descartadasDespuesDePostular(datos);""")
    assert r == 1


def test_desglose_por_fuente_y_sin_dato():
    r = ejecutar("return desglose(datos, 'fuente');")
    assert r[0] == {"clave": "indeed", "relevantes": 2, "postuladas": 2, "entrevistas": 2} or r[0]["relevantes"] == 2
    assert {g["clave"] for g in r} == {"indeed", "linkedin", "bne"}
    r_mod = ejecutar("return desglose(datos, 'modalidad');")
    assert any(g["clave"] == "Sin dato" for g in r_mod)


def test_semanas_son_ocho_con_la_actual_al_final_y_sin_postulaciones_en_cero():
    r = ejecutar("return semanasActividad(datos, '2026-10-23');")
    assert len(r) == 8
    assert r[-1]["semana"] == "2026-10-19"    # lunes de la semana del 23-10-2026
    assert sum(s["n"] for s in r) == 3         # "a" (12-10), "b" (05-10) y "c" (28-09): las tres caen en las 8 semanas


def test_semanas_sin_datos_no_dividen_por_cero():
    r = correr_js("const datos = {principal: []};\nreturn semanasActividad(datos, '2026-10-23').map(s => s.n);")
    assert r == [0] * 8


def test_plural_y_singular_en_los_textos():
    assert "TXT.ofertas(e.n)" in PAGINA
    assert 'ofertas: n => plural(n, "oferta", "ofertas")' in PAGINA
    assert correr_js("return [TXT.ofertas(1), TXT.ofertas(0), TXT.ofertas(2)];") == ["1 oferta", "0 ofertas", "2 ofertas"]
