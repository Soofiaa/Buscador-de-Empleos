import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import buscar
import config
import filtros
from filtros import (clasificar, detectar_modalidad, es_senior, extraer_experiencia,
                     normalizar)

SENALES_TODAS = ("Manejo de SQL y reportes con KPI. Levantamiento de procesos y modelado BPMN. "
                 "Uso de ERP SAP. Trabajo con areas usuarias. Detección de errores y validación.")


def oferta(titulo, desc="", empresa="Empresa X", ubic="Santiago de Chile, RM, Chile", **kw):
    return {"title": titulo, "company": empresa, "location": ubic, "description": desc,
            "is_remote": False, "min_amount": None, "max_amount": None,
            "currency": "", "interval": "", **kw}


# ------------------------------------------------------------ exclusiones absolutas
def test_accenture_se_excluye_siempre():
    r = clasificar(oferta("Analista Funcional", empresa="Accenture Chile"))
    assert r["categoria"] == "descartada"


@pytest.mark.parametrize("titulo", ["Práctica QA", "Practicante Desarrollo", "Memorista TI",
                                    "Pasantía Analista de Sistemas"])
def test_practicas_excluidas(titulo):
    assert clasificar(oferta(titulo))["categoria"] == "descartada"


def test_exige_ser_estudiante_en_descripcion():
    r = clasificar(oferta("QA Tester", "Buscamos alumno regular para práctica profesional"))
    assert r["categoria"] == "descartada"


def test_trainee_solo_si_es_para_titulados():
    assert clasificar(oferta("Trainee QA", "para estudiantes"))["categoria"] == "descartada"
    assert clasificar(oferta("Trainee QA", "dirigido a egresados y titulados"))["categoria"] == "principal"


# ------------------------------------------------------------ soporte -> lista aparte
@pytest.mark.parametrize("titulo", ["Analista de Soporte Cloud", "Mesa de Ayuda Nivel 1",
                                    "Técnico Help Desk", "Service Desk Analyst"])
def test_soporte_va_a_fuera_de_perfil(titulo):
    assert clasificar(oferta(titulo))["categoria"] == "fuera_perfil"


def test_soporte_con_rol_funcional_no_es_fuera_de_perfil():
    assert clasificar(oferta("Analista Funcional Soporte SAP"))["categoria"] == "principal"


# ------------------------------------------------------------ tipo A
def test_tester_junior_es_a_alta():
    r = clasificar(oferta("Analista de Calidad / Tester Junior"))
    assert (r["categoria"], r["tipo"], r["prioridad"]) == ("principal", "A: TI", "Alta")


@pytest.mark.parametrize("titulo,prio", [
    ("Analista Funcional", "Alta"), ("QA Automation Engineer", "Alta"),
    ("Python Developer", "Alta"), ("Desarrollador Backend Junior", "Alta"),
    ("Desarrollador Full Stack", "Media"), ("Developer Front-end", "Media"),
    ("Analista de Datos Junior", "Media"), ("Ingeniero de Redes", "Baja"),
])
def test_prioridades_tipo_a(titulo, prio):
    r = clasificar(oferta(titulo))
    assert r["categoria"] == "principal" and r["prioridad"] == prio


def test_rol_ambiguo_necesita_contexto_ti_para_ser_a():
    ti = clasificar(oferta("Analista de Calidad", "pruebas funcionales, testing y SQL"))
    assert (ti["tipo"], ti["prioridad"]) == ("A: TI", "Alta")
    industrial = clasificar(oferta("Analista de Calidad", "planta de producción, normas ISO"))
    assert industrial["categoria"] == "descartada"


def test_un_solo_termino_de_contexto_no_basta():
    assert clasificar(oferta("Analista de Calidad", "manejo de SQL"))["categoria"] == "descartada"


# ------------------------------------------------------------ tipo B
def test_analista_de_procesos_con_contexto_ti_es_tipo_a():
    r = clasificar(oferta("Analista de Procesos", SENALES_TODAS))   # menciona SQL y BPMN
    assert (r["tipo"], r["prioridad"]) == ("A: TI", "Alta")
    assert "contexto TI" in r["motivo"]


def test_b_puro_sin_contexto_ti():
    desc = "Excel avanzado, KPI e indicadores. Mapeo de procesos y procedimientos. Sistema ERP. Contrato indefinido."
    r = clasificar(oferta("Analista de Procesos", desc))
    assert (r["tipo"], r["prioridad"]) == ("B: Puente", "Alta")
    assert "señales 3/5" in r["motivo"] and "aporta:" in r["motivo"]
    assert r["contrato"] == "Indefinido"


def test_b_con_menos_de_3_senales_se_descarta():
    r = clasificar(oferta("Analista de Operaciones", "Seguimiento de despachos y rutas."))
    assert r["categoria"] == "descartada" and "señales" in r["razon"]


def test_b_plazo_fijo_se_descarta():
    desc = "Excel avanzado, KPI. Mapeo de procesos. ERP. Contrato a plazo fijo."
    assert clasificar(oferta("Analista de Procesos", desc))["categoria"] == "descartada"


def test_b_contrato_no_especificado_se_incluye_marcado():
    desc = "Excel avanzado, KPI. Mapeo de procesos. Sistema ERP."
    assert clasificar(oferta("Analista de Procesos", desc))["contrato"] == "Contrato no especificado"


def test_b_ventas_y_call_center_excluidos():
    desc = "Excel avanzado, KPI. Mapeo de procesos. Sistema ERP."
    assert clasificar(oferta("Analista de Operaciones Ventas", desc))["categoria"] == "descartada"


def test_b_media_vs_alta():
    desc = "Excel avanzado, KPI. Mapeo de procesos. Sistema ERP."
    assert clasificar(oferta("Analista de Operaciones", desc))["prioridad"] == "Media"
    assert clasificar(oferta("Especialista Datos Maestros", desc))["prioridad"] == "Alta"


def test_analista_generico_no_entra():
    assert clasificar(oferta("Analista Contable", "Excel avanzado, KPI, ERP, procesos"))["categoria"] == "descartada"


# ------------------------------------------------------------ nivel, modalidad, sueldo, zona
@pytest.mark.parametrize("desc", [
    "Se requieren 2 años de experiencia en el cargo.", "Mínimo 3 años de experiencia.",
    "Experiencia de 2 a 4 años en testing.", "5 años de experiencia demostrable.",
])
def test_dos_o_mas_anos_de_experiencia_se_descarta(desc):
    r = clasificar(oferta("Analista Funcional", desc))
    assert r["categoria"] == "descartada" and "años de experiencia" in r["razon"]


@pytest.mark.parametrize("desc", ["1 año de experiencia", "0 a 2 años de experiencia",
                                  "1 a 2 años de experiencia", "sin experiencia previa", ""])
def test_hasta_un_ano_o_rango_que_parte_en_menos_de_2_se_mantiene(desc):
    assert clasificar(oferta("Analista Funcional", desc))["categoria"] == "principal"


@pytest.mark.parametrize("titulo", ["QA Senior", "QA Semi Senior", "QA SSR", "QA Semisenior",
                                    "Sr. Backend Engineer", "QA Automation Engineer Lead",
                                    "Jefe de QA", "Arquitecto Backend", "Gerente de Testing"])
def test_semi_senior_y_senior_se_descartan(titulo):
    r = clasificar(oferta(titulo))
    assert r["categoria"] == "descartada" and r["razon"] == "nivel semi senior / senior"


def test_nivel_senior_declarado_en_la_descripcion():
    assert clasificar(oferta("Analista QA", "Buscamos perfil semi senior con SQL"))["categoria"] == "descartada"
    assert clasificar(oferta("Analista QA", "Trabajarás junto a un senior que te guiará"))["categoria"] == "principal"


def test_es_senior():
    assert es_senior(normalizar("QA Semi Senior")) and es_senior(normalizar("QA SSR"))
    assert es_senior(normalizar("QA Senior")) and not es_senior(normalizar("QA Junior"))


def test_extraer_experiencia():
    assert extraer_experiencia("minimo 2 años de experiencia")[0] == 2
    assert extraer_experiencia("1 a 2 años de experiencia")[0] == 1
    assert extraer_experiencia("sin experiencia previa")[0] == 0
    assert extraer_experiencia("empresa con 20 años en el mercado")[0] is None


@pytest.mark.parametrize("desc, texto", [
    ("Experiencia: 1 años en desarrollo React", "1 año"),            # el aviso de Chiletrabajos escribe "1 años"
    ("1 año de experiencia", "1 año"),
    ("1 ano de experiencia", "1 año"),
    ("Experiencia mínima (BNE): 1 Años.", "1 año"),
    ("2 año de experiencia", "2 años"),
    ("3 años de experiencia", "3 años"),
    ("1 a 2 años de experiencia", "1 a 2 años"),
    ("0 a 1 año de experiencia", "0 a 1 año"),
    ("1+ años de experiencia", "1+ años"),
])
def test_texto_de_experiencia_singular_y_plural(desc, texto):
    assert extraer_experiencia(desc)[1] == texto


def test_modalidad():
    assert detectar_modalidad("", "trabajo hibrido 3 dias", False)[0] == "Híbrido"
    assert detectar_modalidad("", "100% remoto", False)[0] == "Remoto"
    assert detectar_modalidad("", "", True) == ("Remoto", "marcada remota por Indeed")
    assert detectar_modalidad("", "modalidad presencial", False)[0] == "Presencial"
    assert detectar_modalidad("", "", False)[0] == "No indicada"
    assert detectar_modalidad("", "hibrido con dias remotos", False)[0] == "Híbrido"


def test_una_mencion_suelta_de_remoto_no_basta():
    assert detectar_modalidad("", "incluye monitoreo remoto de equipos", False)[0] != "Remoto"
    assert detectar_modalidad("analista qa remoto", "", False)[0] == "Remoto"


def test_fuera_de_zona_se_descarta_salvo_remoto():
    lejos = "Antofagasta, AN, Chile"
    assert clasificar(oferta("QA", ubic=lejos))["categoria"] == "descartada"
    assert clasificar(oferta("QA", "100% remoto", ubic=lejos))["categoria"] == "principal"
    assert clasificar(oferta("QA", ubic="Viña del Mar, VS, Chile"))["categoria"] == "principal"


def test_sueldo_desde_columnas_y_alerta_en_b():
    desc = "Excel avanzado, KPI. Mapeo de procesos. Sistema ERP. Contrato indefinido."
    r = clasificar(oferta("Analista de Procesos", desc, min_amount=900000, max_amount=1100000,
                          currency="CLP", interval="monthly"))
    assert "900.000" in r["sueldo"] and "revisar" in r["sueldo"]
    assert clasificar(oferta("Analista de Procesos", desc))["sueldo"] == "No indicado"


def test_oferta_sospechosa():
    r = clasificar(oferta("Analista Funcional", "Para postular debes pagar inscripción de capacitación"))
    assert r["categoria"] == "sospechosa"
    assert clasificar(oferta("QA", "contáctanos solo por WhatsApp"))["categoria"] == "sospechosa"


def test_nan_en_campos_no_rompe():
    r = clasificar({"title": "QA", "company": float("nan"), "location": None,
                    "description": pd.NA, "is_remote": None})
    assert r["categoria"] == "principal"


# ------------------------------------------------------------ persistencia y Excel
def df_de(*filas):
    base = {"company": "X", "location": "Santiago de Chile, RM, Chile", "description": "",
            "date_posted": None, "is_remote": False, "min_amount": None, "max_amount": None,
            "currency": None, "interval": None}
    return pd.DataFrame([{**base, **f} for f in filas])


def test_dedupe_por_url_y_por_clave(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = df_de({"job_url": "http://1", "title": "Tester Junior"},
               {"job_url": "http://2", "title": "Tester  Junior"},   # misma oferta, otra URL
               {"job_url": "http://1", "title": "Tester Junior"})    # misma URL
    assert buscar.guardar(con, buscar.procesar(df, "t")) == 1
    assert buscar.guardar(con, buscar.procesar(df, "t")) == 0


def test_guarda_descartadas_con_razon(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(df_de({"job_url": "http://p", "title": "Práctica QA"}), "t"))
    fila = con.execute("SELECT categoria, razon FROM ofertas").fetchone()
    assert (fila["categoria"], fila["razon"]) == ("descartada", "práctica / estudiante")


def test_base_antigua_se_respalda(tmp_path):
    ruta = str(tmp_path / "v1.db")
    viejo = sqlite3.connect(ruta)
    viejo.execute("CREATE TABLE ofertas (url TEXT PRIMARY KEY, titulo TEXT)")
    viejo.commit(); viejo.close()
    con = buscar.conectar(ruta)
    assert "raw" in [r[1] for r in con.execute("PRAGMA table_info(ofertas)")]
    assert len(list(tmp_path.glob("v1_antigua_*.db"))) == 1
    buscar.conectar(ruta)  # una base ya actual no se vuelve a respaldar
    assert len(list(tmp_path.glob("v1_antigua_*.db"))) == 1


def _base_v5(ruta, columnas_node=False):
    """Una base v5 real (como la del volumen), opcionalmente con las columnas que agregaba la app Node."""
    con = buscar.conectar(ruta)
    con.execute("PRAGMA user_version = 5")
    con.commit(); con.close()
    v5 = sqlite3.connect(ruta)
    v5.execute("DROP TABLE ofertas")      # tabla v5 tal cual, sin las columnas de seguimiento
    v5.execute("""CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT UNIQUE, titulo TEXT, empresa TEXT,
        ubicacion TEXT, publicada TEXT, raw TEXT, categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT,
        modalidad TEXT, contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT,
        estado TEXT DEFAULT 'nueva', busqueda TEXT, detectada_en TEXT, fuente TEXT DEFAULT 'indeed',
        clave_base TEXT, ciudad TEXT DEFAULT ''""" + (", notas TEXT DEFAULT '', fecha_postulacion TEXT DEFAULT '',"
                                                     " fase TEXT DEFAULT ''" if columnas_node else "") + ")")
    v5.execute("INSERT INTO ofertas (url, clave, titulo, estado, sueldo) VALUES ('a', 'k1', 'QA', 'postulada', '$1')")
    v5.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-11 10:58', '2026-10-11 11:06', 7, '{}')")
    v5.commit(); v5.close()


@pytest.mark.parametrize("columnas_node", [False, True])
def test_migracion_v5_a_v6_agrega_columnas_sin_respaldar_ni_perder(tmp_path, columnas_node):
    ruta = str(tmp_path / "v5.db")
    _base_v5(ruta, columnas_node)
    for _ in range(2):                    # idempotente: una segunda conexión no cambia nada
        con = buscar.conectar(ruta)
        cols = [r[1] for r in con.execute("PRAGMA table_info(ofertas)")]
        assert all(cols.count(c) == 1 for c in buscar.COLUMNAS_SEGUIMIENTO)
        f = con.execute("SELECT * FROM ofertas").fetchone()
        assert (f["estado"], f["sueldo"], f["notas"], f["fecha_postulacion"], f["fase"], f["sueldo_manual"]) == \
            ("postulada", "$1", "", "", "", "")
        assert con.execute("SELECT COUNT(*) FROM corridas").fetchone()[0] == 1
        assert con.execute("PRAGMA user_version").fetchone()[0] == buscar.VERSION_DB == 6
        con.close()
    assert list(tmp_path.glob("v5_antigua_*.db")) == []    # migración, no respaldo


def test_base_nueva_trae_columnas_de_seguimiento(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    cols = {r[1] for r in con.execute("PRAGMA table_info(ofertas)")}
    assert set(buscar.COLUMNAS_SEGUIMIENTO) <= cols


def test_datos_de_la_pagina_orden_listas_y_estado(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = df_de(
        {"job_url": "http://front", "title": "Developer Front-end", "company": "A"},
        {"job_url": "http://qa-presencial", "title": "QA Analyst", "company": "B"},
        {"job_url": "http://qa-remoto", "title": "QA Tester", "company": "C", "is_remote": True},
        {"job_url": "http://soporte", "title": "Mesa de Ayuda", "company": "D"},
        {"job_url": "http://estafa", "title": "Analista Funcional", "company": "E",
         "description": "solo por whatsapp"},
        {"job_url": "http://acc", "title": "QA", "company": "Accenture"})
    buscar.guardar(con, buscar.procesar(df, "t"))
    d = buscar.ofertas_para_pagina(con)
    assert [f["url"] for f in d["principal"]] == ["http://qa-remoto", "http://qa-presencial", "http://front"]
    assert [f["url"] for f in d["fuera_perfil"]] == ["http://soporte"]
    assert [f["url"] for f in d["sospechosas"]] == ["http://estafa"]
    assert [f["url"] for f in d["descartadas"]] == ["http://acc"] and d["total_descartadas"] == 1
    assert d["descartadas"][0]["razon"] == "empresa excluida"

    assert buscar.marcar_estado(con, "http://qa-remoto", "postulada")
    assert not buscar.marcar_estado(con, "http://qa-remoto", "inventado")
    assert not buscar.marcar_estado(con, "http://no-existe", "revisada")
    # una oferta ya postulada baja al final de la lista
    assert buscar.ofertas_para_pagina(con)["principal"][-1]["url"] == "http://qa-remoto"


def test_reclasificar_conserva_estado_y_aplica_config(tmp_path, monkeypatch):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(df_de({"job_url": "http://a", "title": "Developer Front-end"}), "t"))
    con.execute("UPDATE ofertas SET estado='revisada'"); con.commit()
    monkeypatch.setattr(buscar.config, "ROLES_A_MEDIA", [])
    cuentas = buscar.reclasificar(con)
    fila = con.execute("SELECT categoria, estado FROM ofertas").fetchone()
    assert (fila["categoria"], fila["estado"]) == ("descartada", "revisada")
    assert cuentas["descartada"] == 1


# ------------------------------------------------------------ errores detectados en datos reales
def test_anos_de_la_empresa_no_son_experiencia():
    assert extraer_experiencia("somos una empresa con 47 años de trayectoria y experiencia")[0] is None
    assert extraer_experiencia("35 años de experiencia en energia renovable, buscamos analista")[0] is None
    assert extraer_experiencia("2 años de experiencia en el cargo")[0] == 2


def test_fuera_de_zona_requiere_remoto_firme_no_solo_la_marca_de_indeed():
    antof = "Antofagasta, AN, Chile"
    assert clasificar(oferta("QA", is_remote=True, ubic=antof))["categoria"] == "descartada"
    assert clasificar(oferta("QA", "trabajo 100% remoto", ubic=antof))["categoria"] == "principal"


def test_infraestructura_fisica_no_es_ti():
    assert clasificar(oferta("Planificador de Mantenimiento de Infraestructura",
                             "obras civiles y mantencion de edificios"))["categoria"] == "descartada"
    ti = clasificar(oferta("Ingeniero Infraestructura", "servidores, bases de datos, SQL y Python"))
    assert (ti["tipo"], ti["prioridad"]) == ("A: TI", "Baja")


def test_ciberseguridad_sigue_entrando_sin_contexto():
    assert clasificar(oferta("Analista de Ciberseguridad"))["prioridad"] == "Baja"


def test_automatizacion_industrial_no_es_ti_pero_rpa_si():
    desc = "SQL, Python, API, desarrollo de software"
    assert clasificar(oferta("Jefe de Recepción y Automatización", desc))["categoria"] == "descartada"
    assert clasificar(oferta("Ingeniero de Automatización e IA", desc))["categoria"] == "descartada"
    assert clasificar(oferta("Analista RPA", desc))["categoria"] == "principal"
    assert clasificar(oferta("Analista de Automatización de Procesos", desc))["categoria"] == "principal"


def test_tecnico_de_mantenimiento_no_es_rol_puente():
    desc = "Excel avanzado, KPI, ERP SAP, mapeo de procesos, areas usuarias"
    assert clasificar(oferta("Técnico(a) Implementación y Mantenimiento", desc))["categoria"] == "descartada"


def test_palabras_genericas_ya_no_cuentan_como_senales():
    generica = "Detectar errores en la plataforma, seguir procedimientos y cumplir requerimientos de la jefatura."
    r = clasificar(oferta("Analista de Operaciones", generica))
    assert r["categoria"] == "descartada" and "0/5" in r["razon"]


def test_motivo_explica_modalidad_y_contrato():
    r = clasificar(oferta("QA Tester", "Contrato a plazo fijo. Modalidad híbrida."))
    assert "modalidad: Híbrido por 'hibrida'" in r["motivo"]
    assert "plazo fijo por 'plazo fijo' en descripción" in r["motivo"]


# ------------------------------------------------------------ varias fuentes (Indeed, Google, Glassdoor)
def test_parametros_por_fuente():
    ind = buscar.consulta("indeed", "QA", "Santiago, Chile")
    assert ind["country_indeed"] == "Chile" and ind["site_name"] == ["indeed"]
    gd = buscar.consulta("glassdoor", "QA", "Viña del Mar, Chile")
    assert gd["country_indeed"] == "usa" and gd["location"] == "Viña del Mar, Chile"   # rodeo: glassdoor.com
    go = buscar.consulta("google", "QA", "Santiago, Chile")
    assert "country_indeed" not in go
    rem = buscar.consulta("google", "QA", buscar.REMOTO)
    assert rem["search_term"] == "QA remoto" and rem["location"] == "Chile"


def test_misma_oferta_en_dos_fuentes_se_guarda_una_vez(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    indeed = df_de({"job_url": "https://cl.indeed.com/1", "title": "Tester Junior", "company": "Axity",
                    "location": "Santiago de Chile, RM, Chile"})
    google = df_de({"job_url": "https://axity.com/empleo/9", "title": "Tester Junior", "company": "Axity",
                    "location": "Santiago, Santiago Metropolitan Region, Chile"})
    assert buscar.guardar(con, buscar.procesar(indeed, "t", "indeed")) == 1
    assert buscar.guardar(con, buscar.procesar(google, "t", "google")) == 0
    assert con.execute("SELECT fuente FROM ofertas").fetchone()[0] == "indeed"


def test_ciudades_distintas_no_se_fusionan():
    from filtros import clave_oferta
    assert clave_oferta("QA", "X", "Las Condes, RM, Chile") != clave_oferta("QA", "X", "Providencia, RM, Chile")
    assert clave_oferta("QA", "X", "Santiago de Chile, RM, Chile") == clave_oferta("QA", "X", "Santiago, Chile")


@pytest.mark.parametrize("ubic", ["Santiago, Spain", "Santiago de Compostela", "Santiago, Dominican Republic", ""])
def test_fuentes_externas_con_ubicacion_que_no_es_chile_se_descartan(ubic):
    r = clasificar(oferta("QA Tester", ubic=ubic, fuente="glassdoor"))
    assert r["categoria"] == "descartada" and "no reconocida como Chile" in r["razon"]


@pytest.mark.parametrize("ubic", ["Santiago, Santiago Metropolitan Region, Chile", "Las Condes, Chile",
                                  "Viña del Mar, Valparaíso, Chile", "Santiago, RM, CL"])
def test_fuentes_externas_con_ubicacion_chilena_pasan(ubic):
    assert clasificar(oferta("QA Tester", ubic=ubic, fuente="google"))["categoria"] == "principal"


def test_fuente_externa_remota_firme_pasa_aunque_la_ubicacion_sea_vaga():
    r = clasificar(oferta("QA Tester", "Trabajo 100% remoto", ubic="Remote", fuente="google"))
    assert r["categoria"] == "principal"


def test_indeed_no_exige_pista_de_chile():
    assert clasificar(oferta("QA Tester", ubic="Santiago", fuente="indeed"))["categoria"] == "principal"


def test_ofertas_viejas_no_se_guardan_ni_cuentan_como_descartadas(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = df_de({"job_url": "http://nueva", "title": "QA Tester", "date_posted": "2026-10-11"},
               {"job_url": "http://vieja", "title": "Práctica QA", "date_posted": "2026-10-01"},
               {"job_url": "http://sinfecha", "title": "QA Engineer", "date_posted": None})
    recientes, antiguas = buscar.recientes(df, "indeed", AHORA, 1)
    assert antiguas == 1
    buscar.guardar(con, buscar.procesar(recientes, "t", "indeed"))
    filas = {r["url"]: r for r in con.execute("SELECT url, publicada, categoria FROM ofertas")}
    assert set(filas) == {"http://nueva", "http://sinfecha"}            # la vieja (que sería descartada) no está
    assert filas["http://sinfecha"]["publicada"] == ""                  # la página la muestra como "sin fecha"
    assert buscar.ofertas_para_pagina(con)["total_descartadas"] == 0


# ------------------------------------------------------------ antigüedad (ventana de días)
from datetime import datetime as _dtm, timedelta as _td, timezone as _tzu
AHORA = _dtm(2026, 10, 11, 12, 0, tzinfo=filtros.ZONA)


@pytest.mark.parametrize("fecha, esperado", [
    ("2026-10-11", "reciente"), ("2026-10-10", "reciente"), ("2026-10-09", "antigua"),
    ("2026-10-12", "reciente"),                     # día UTC adelantado respecto de Chile
    ("", "sin_fecha"), (None, "sin_fecha"), ("hace 3 días", "sin_fecha"),
])
def test_antiguedad_solo_con_dia(fecha, esperado):
    assert filtros.antiguedad({"date_posted": fecha, "fuente": "bne"}, AHORA, 1) == esperado


def test_antiguedad_con_hora_corta_exacto_en_24_horas():
    def con_hora(horas):
        return {"posted_at": (AHORA - _td(hours=horas)).astimezone(_tzu.utc).isoformat(),
                "date_posted": "2026-10-11", "fuente": "getonboard"}
    assert filtros.antiguedad(con_hora(23), AHORA, 1) == "reciente"
    assert filtros.antiguedad(con_hora(25), AHORA, 1) == "antigua"   # la hora manda sobre el día
    assert filtros.antiguedad(con_hora(70), AHORA, 3) == "reciente"


def test_antiguedad_trabajando_hora_sin_zona_con_margen():
    def hace(horas):
        return {"posted_at": (AHORA - _td(hours=horas)).replace(tzinfo=None).isoformat(timespec="minutes"),
                "fuente": "trabajando"}
    assert filtros.antiguedad(hace(27), AHORA, 1) == "reciente"   # 24 h + 4 h de margen por si fuera UTC
    assert filtros.antiguedad(hace(29), AHORA, 1) == "antigua"


def test_corte_usa_fecha_de_chile_cerca_de_medianoche_utc(tmp_path):
    ahora_utc = _dtm(2026, 10, 12, 1, 30, tzinfo=_tzu.utc)   # en Chile (UTC-3) aún es 11/10, 22:30
    assert filtros.antiguedad({"date_posted": "2026-10-10"}, ahora_utc, 1) == "reciente"   # con fecha UTC sería antigua
    assert filtros.antiguedad({"date_posted": "2026-10-09"}, ahora_utc, 1) == "antigua"
    con = buscar.conectar(str(tmp_path / "t.db"))
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES "
                "('2026-10-11 19:00', '2026-10-11 20:00', 0, '{}')")
    assert buscar.ventanas_efectivas(con, ahora_utc)["indeed"] == 1   # mismo día en Chile: sin ampliar


def test_ventana_efectiva_crece_si_se_salta_dias(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    v = buscar.ventanas_efectivas(con, AHORA)                          # primera búsqueda: la configurada
    assert v["bne"] == 3 and v["indeed"] == v["trabajando"] == 1
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-08 09:00', '2026-10-08 09:20', 0, '{}')")
    v = buscar.ventanas_efectivas(con, AHORA)                          # 3 días sin buscar -> 3 + 1
    assert v["indeed"] == v["bne"] == 4
    con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-08-01 09:00', '2026-08-01 09:20', 0, '{}')")
    assert buscar.ventanas_efectivas(con, AHORA)["indeed"] == config.DIAS_MAXIMOS   # la última por id; con tope


def test_hours_old_por_fuente():
    assert buscar.consulta("indeed", "QA", "Santiago, Chile")["hours_old"] == 24
    assert buscar.consulta("glassdoor", "QA", "Santiago, Chile")["hours_old"] == 48   # días enteros: incluye "ayer"
    assert buscar.consulta("indeed", "QA", "Santiago, Chile", dias=3)["hours_old"] == 72
    assert buscar.consulta("glassdoor", "QA", "Santiago, Chile", dias=3)["hours_old"] == 96


def _corrida_falsa(tmp_path, monkeypatch, filas_previas=()):
    """buscar_ofertas con un JobSpy falso (sin red) para Indeed: devuelve una oferta reciente y una antigua."""
    import types
    pedidos = []

    def scrape_jobs(**kw):
        pedidos.append(kw)
        return df_de({"job_url": "http://hoy", "title": "QA Tester", "date_posted": "2026-10-11"},
                     {"job_url": "http://vieja", "title": "QA Analyst", "date_posted": "2026-09-20"})
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=scrape_jobs))
    for k, v in {"SITIOS": ["indeed"], "TERMINOS_A": ["QA"], "TERMINOS_B": [], "UBICACIONES": ["Santiago, Chile"],
                 "INCLUIR_REMOTO": False, "PAUSA_ENTRE_BUSQUEDAS": 0}.items():
        monkeypatch.setattr(config, k, v)
    monkeypatch.setattr(buscar, "ahora_chile", lambda: AHORA)
    con = buscar.conectar(str(tmp_path / "t.db"))
    for fin in filas_previas:
        con.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES (?, ?, 0, '{}')", (fin, fin))
    buscar.buscar_ofertas(con)
    return con, pedidos, buscar.ultima_corrida(con)["detalle"]


def test_corrida_cuenta_encontradas_despues_del_corte(tmp_path, monkeypatch):
    con, pedidos, detalle = _corrida_falsa(tmp_path, monkeypatch)
    assert pedidos[0]["hours_old"] == 24
    f = detalle["fuentes"][0]
    assert (f["encontradas"], f["antiguas"], f["relevantes"], f["ventana_dias"]) == (1, 1, 1, 1)
    assert detalle["ventana_dias"] == {"indeed": 1}
    assert [r["url"] for r in con.execute("SELECT url FROM ofertas")] == ["http://hoy"]


def test_corrida_tras_dias_sin_buscar_amplia_la_ventana(tmp_path, monkeypatch):
    con, pedidos, detalle = _corrida_falsa(tmp_path, monkeypatch, ["2026-10-08 20:00"])
    assert pedidos[0]["hours_old"] == 96 and detalle["ventana_dias"] == {"indeed": 4}
    assert any("ventana ampliada a 4 días" in a for a in detalle["avisos"])


def test_la_fuente_llega_a_la_pagina(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.guardar(con, buscar.procesar(df_de({"job_url": "http://g", "title": "QA Tester"}), "t", "google"))
    assert buscar.ofertas_para_pagina(con)["principal"][0]["fuente"] == "google"


def test_migracion_v2_a_v3_conserva_estados_y_une_duplicados(tmp_path):
    ruta = str(tmp_path / "v2.db")
    v2 = sqlite3.connect(ruta)
    v2.execute("""CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT UNIQUE, titulo TEXT, empresa TEXT,
        ubicacion TEXT, publicada TEXT, raw TEXT, categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT,
        modalidad TEXT, contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT,
        estado TEXT DEFAULT 'nueva', busqueda TEXT, detectada_en TEXT)""")
    filas = [  # (url, clave vieja, ubicación, estado, detectada)
        ("u1", "tester|axity|santiago de chile rm chile", "Santiago de Chile, RM, Chile", "nueva", "2026-10-01"),
        ("u2", "tester|axity|santiago rm chile", "Santiago, RM, Chile", "postulada", "2026-10-02"),
        ("u3", "qa|bice|las condes rm chile", "Las Condes, RM, Chile", "nueva", "2026-10-03"),
    ]
    titulos = {"u1": "Tester", "u2": "Tester", "u3": "QA"}
    empresas = {"u1": "Axity", "u2": "Axity", "u3": "Bice"}
    for url, clave, ubic, estado, det in filas:
        v2.execute("INSERT INTO ofertas (url, clave, titulo, empresa, ubicacion, estado, detectada_en, categoria) "
                   "VALUES (?,?,?,?,?,?,?, 'principal')", (url, clave, titulos[url], empresas[url], ubic, estado, det))
    v2.execute("PRAGMA user_version = 2"); v2.commit(); v2.close()

    con = buscar.conectar(ruta)
    cols = [r[1] for r in con.execute("PRAGMA table_info(ofertas)")]
    assert "fuente" in cols and con.execute("PRAGMA user_version").fetchone()[0] == buscar.VERSION_DB
    urls = {r["url"]: r["estado"] for r in con.execute("SELECT url, estado FROM ofertas")}
    assert urls == {"u2": "postulada", "u3": "nueva"}      # se conserva la que ya marcaste
    assert con.execute("SELECT fuente FROM ofertas WHERE url='u3'").fetchone()[0] == "indeed"
    assert list(tmp_path.glob("v2_antigua_*.db")) == []    # migración, no respaldo


# ------------------------------------------------------------ casos reales de probar_fuentes.py (Glassdoor)
def test_glassdoor_con_ubicacion_solo_chile_se_une_a_la_de_indeed(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    indeed = df_de({"job_url": "https://cl.indeed.com/a", "title": "Analista de Calidad/ Tester junior",
                    "company": "Axity", "location": "Las Condes, RM, Chile"},
                   {"job_url": "https://cl.indeed.com/b", "title": "QA Analyst", "company": "GASCO",
                    "location": "Santiago de Chile, RM, Chile"})
    glassdoor = df_de({"job_url": "https://glassdoor.com/1", "title": "Analista de Calidad/ Tester junior",
                       "company": "Axity", "location": "Las Condes, Chile"},      # misma ciudad
                      {"job_url": "https://glassdoor.com/2", "title": "QA Analyst", "company": "GASCO",
                       "location": "Chile"},                                       # sin ciudad
                      {"job_url": "https://glassdoor.com/3", "title": "QA Engineer", "company": "Otra",
                       "location": "Chile"})                                       # oferta nueva
    assert buscar.guardar(con, buscar.procesar(indeed, "t", "indeed")) == 2
    assert buscar.guardar(con, buscar.procesar(glassdoor, "t", "glassdoor")) == 1
    assert con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 3


def test_misma_oferta_en_otra_ciudad_no_se_une_si_ambas_tienen_ciudad(tmp_path):
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = df_de({"job_url": "http://1", "title": "QA Tester", "company": "Falabella", "location": "Las Condes, RM, Chile"},
               {"job_url": "http://2", "title": "QA Tester", "company": "Falabella", "location": "Cerrillos, RM, Chile"})
    assert buscar.guardar(con, buscar.procesar(df, "t", "indeed")) == 2


def test_ciudad_de():
    from filtros import ciudad_de
    assert ciudad_de("Santiago de Chile, RM, Chile") == ciudad_de("Santiago, Santiago Metropolitan Region, Chile") == "santiago"
    assert ciudad_de("Chile") == ciudad_de("") == ciudad_de(None) == ""
    assert ciudad_de("Providencia, Chile") == "providencia"


def test_ubicacion_imprecisa_de_glassdoor_se_marca():
    r = clasificar(oferta("QA Tester", ubic="Chile", fuente="glassdoor"))
    assert r["categoria"] == "principal" and "ubicación imprecisa" in r["motivo"]
    assert "ubicación imprecisa" not in clasificar(oferta("QA Tester", ubic="Providencia, Chile",
                                                          fuente="glassdoor"))["motivo"]
    assert "ubicación imprecisa" not in clasificar(oferta("QA Tester", fuente="indeed"))["motivo"]


def test_semi_senior_de_glassdoor_se_descarta():
    r = clasificar(oferta("Desarrollador(a) de Software Semi Senior Santiago - Proyecto CENABAST",
                          ubic="Chile", fuente="glassdoor"))
    assert r["categoria"] == "descartada" and r["razon"] == "nivel semi senior / senior"


def test_google_esta_desactivado_por_defecto():
    assert "google" not in buscar.config.SITIOS and "glassdoor" in buscar.config.SITIOS


def test_migracion_v3_a_v4(tmp_path):
    ruta = str(tmp_path / "v3.db")
    v3 = sqlite3.connect(ruta)
    v3.execute("""CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT UNIQUE, titulo TEXT, empresa TEXT,
        ubicacion TEXT, publicada TEXT, raw TEXT, categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT,
        modalidad TEXT, contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT,
        estado TEXT DEFAULT 'nueva', busqueda TEXT, detectada_en TEXT, fuente TEXT DEFAULT 'indeed')""")
    v3.execute("INSERT INTO ofertas (url, clave, titulo, empresa, ubicacion, estado) VALUES "
               "('u1','k','Tester Junior','Axity','Las Condes, RM, Chile','postulada')")
    v3.execute("PRAGMA user_version = 3"); v3.commit(); v3.close()

    con = buscar.conectar(ruta)
    fila = con.execute("SELECT clave_base, ciudad, estado FROM ofertas").fetchone()
    assert (fila["clave_base"], fila["ciudad"], fila["estado"]) == ("tester junior|axity", "las condes", "postulada")
    assert con.execute("PRAGMA user_version").fetchone()[0] == buscar.VERSION_DB
    gd = df_de({"job_url": "http://g", "title": "Tester Junior", "company": "Axity", "location": "Chile"})
    assert buscar.guardar(con, buscar.procesar(gd, "t", "glassdoor")) == 0   # reconocida como duplicada


# ------------------------------------------------------------ Get on Board (formato supuesto; ver getonboard.py)
import getonboard
import time as _time
from datetime import datetime as _dt, timezone as _tz

EPOCH_RECIENTE = int(_time.time()) - 2 * 86400   # hace 2 días (procesar ya no corta por antigüedad: eso es recientes())


def item_gob(**attrs):
    base = {"title": "QA Analyst", "description": "<p>Pruebas <b>funcionales</b> con SQL</p>",
            "functions": "<ul><li>Diseñar casos de prueba</li></ul>", "desirable": "Python",
            "remote": False, "remote_modality": "hybrid", "countries": ["Chile"],
            "min_salary": 1500, "max_salary": 2500, "published_at": EPOCH_RECIENTE,
            "seniority": {"data": {"id": 2, "type": "seniority", "attributes": {"name": "Junior"}}},
            "company": {"data": {"id": "acme", "type": "company", "attributes": {"name": "Acme SpA"}}}}
    base.update(attrs)
    return {"id": "qa-analyst-acme", "type": "job", "attributes": base,
            "links": {"public_url": "https://www.getonbrd.com/jobs/qa-analyst-acme"}}


def test_gob_traduce_los_campos_principales():
    f = getonboard.a_fila(item_gob())
    assert f["job_url"].endswith("qa-analyst-acme") and f["title"] == "QA Analyst"
    assert f["company"] == "Acme SpA" and f["location"] == "Chile"
    assert "<" not in f["description"] and "Nivel Junior." in f["description"]
    assert "Modalidad híbrida." in f["description"]
    assert f["date_posted"] == _dt.fromtimestamp(EPOCH_RECIENTE, tz=_tz.utc).date().isoformat()
    assert (f["min_amount"], f["max_amount"], f["currency"], f["interval"]) == (1500, 2500, "USD", "monthly")


def test_gob_empresa_en_formas_alternativas():
    assert getonboard.a_fila(item_gob(company="Solo Texto Ltda"))["company"] == "Solo Texto Ltda"
    assert getonboard.a_fila(item_gob(company={"name": "Otra"}))["company"] == "Otra"
    plano = item_gob(company=None)
    plano["relationships"] = {"company": {"data": {"attributes": {"name": "Rel SA"}}}}
    assert getonboard.a_fila(plano)["company"] == "Rel SA"


def test_gob_solo_chile_o_remoto_global():
    assert getonboard.a_fila(item_gob(countries=["Colombia"], remote_modality="remote_local", remote=True)) is None
    assert getonboard.a_fila(item_gob(countries=["Colombia", "Mexico"], remote_modality="hybrid")) is None
    glob = getonboard.a_fila(item_gob(countries=[], remote_modality="remote_global", remote=True))
    assert glob["location"] == "Remoto (global)" and "Modalidad 100% remota." in glob["description"]
    assert getonboard.a_fila(item_gob(countries=["Colombia", "Chile"]))["location"] == "Chile"
    assert getonboard.a_fila(item_gob(countries=[{"name": "Chile"}]))["location"] == "Chile"


def test_gob_tolera_campos_faltantes():
    f = getonboard.a_fila({"attributes": {"title": "Dev", "countries": ["Chile"]}})
    assert f["title"] == "Dev" and f["job_url"] == "" and f["company"] == "" and f["date_posted"] == ""


def test_gob_nivel_y_modalidad_llegan_al_clasificador():
    senior = getonboard.a_fila(item_gob(seniority={"data": {"attributes": {"name": "Senior"}}}))
    r = clasificar({**senior, "title": senior["title"], "fuente": "getonboard"})
    assert r["categoria"] == "descartada" and r["razon"] == "nivel semi senior / senior"

    junior = getonboard.a_fila(item_gob())
    r = clasificar({**junior, "fuente": "getonboard"})
    assert (r["categoria"], r["prioridad"], r["modalidad"]) == ("principal", "Alta", "Híbrido")

    remoto = getonboard.a_fila(item_gob(remote=True, remote_modality="remote_local"))
    assert clasificar({**remoto, "fuente": "getonboard"})["modalidad"] == "Remoto"


def test_gob_integrado_en_el_flujo(tmp_path, monkeypatch):
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = pd.DataFrame([getonboard.a_fila(item_gob())], columns=getonboard.COLUMNAS)
    assert buscar.guardar(con, buscar.procesar(df, "gob", "getonboard")) == 1
    fila = con.execute("SELECT fuente, empresa, modalidad FROM ofertas").fetchone()
    assert (fila["fuente"], fila["empresa"], fila["modalidad"]) == ("getonboard", "Acme SpA", "Híbrido")


def test_gob_buscar_usa_la_api_y_filtra(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"data": [item_gob(), item_gob(countries=["Peru"], remote_modality="hybrid"),
                                         item_gob(title="")]}
    monkeypatch.setattr(getonboard.requests, "get", lambda *a, **k: Resp())
    df = getonboard.buscar("QA", 10)
    assert len(df) == 1 and list(df.columns) == getonboard.COLUMNAS


def test_get_on_board_esta_en_las_fuentes_por_defecto():
    assert "getonboard" in buscar.config.SITIOS and "getonboard" in buscar.config.NOMBRE_FUENTE


def test_gob_buscar_reintenta_sin_expandir_nivel_si_la_api_lo_rechaza(monkeypatch):
    llamadas = []

    class Resp:
        def __init__(self, code): self.status_code = code; self.ok = code == 200
        def raise_for_status(self):
            if self.status_code >= 400: raise RuntimeError("http")
        def json(self): return {"data": [item_gob()]}

    def falso(url, params=None, **k):
        llamadas.append(params["expand[]"])
        return Resp(422 if "seniority" in params["expand[]"] else 200)
    monkeypatch.setattr(getonboard.requests, "get", falso)
    assert len(getonboard.buscar("QA", 10)) == 1
    assert llamadas == [["company", "seniority"], ["company"]]


def test_gob_seniority_solo_id_no_inventa_nivel():
    f = getonboard.a_fila(item_gob(seniority={"data": {"id": 3, "type": "seniority"}}))
    assert "Nivel" not in f["description"]


# ------------------------------------------------------------ SAC / personas, empresas con sufijo, migración v4->v5
def test_calidad_de_atencion_al_cliente_no_es_ti_aunque_mencione_python_y_sql():
    r = clasificar(oferta("Analista de Calidad, Gerencia SAC",
                                  "Control de calidad de atención. Python, SQL, scrum, bases de datos."))
    assert r["categoria"] != "principal"


def test_gestion_de_personas_no_es_datos_ti():
    assert clasificar(oferta("Analista de Datos y Gestión de Personas", "Excel, SQL"))["categoria"] != "principal"


def test_titulo_tecnico_con_palabra_de_personas_se_salva():
    r = clasificar(oferta("QA Tester para plataforma de Recursos Humanos", "pruebas funcionales, casos de prueba"))
    assert r["categoria"] == "principal"


def test_empresa_con_sufijos_es_la_misma():
    assert filtros.base_oferta("Dev", "Empresas HumanNet - Chile") == filtros.base_oferta("Dev", "HumanNet")
    assert filtros.base_oferta("Dev", "Falabella Retail Chile") == filtros.base_oferta("Dev", "Falabella")
    assert filtros.base_oferta("Dev", "Acme SpA") != filtros.base_oferta("Dev", "Beta SpA")
    assert filtros.base_oferta("Dev", "Chile") != ""    # si todo es sufijo, se conserva


def test_migracion_v4_a_v5_une_empresas_con_sufijo_y_conserva_estado(tmp_path):
    ruta = str(tmp_path / "v4.db")
    v4 = sqlite3.connect(ruta)
    v4.execute("""CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT UNIQUE, titulo TEXT, empresa TEXT,
        ubicacion TEXT, publicada TEXT, raw TEXT, categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT,
        modalidad TEXT, contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT,
        estado TEXT DEFAULT 'nueva', busqueda TEXT, detectada_en TEXT, fuente TEXT DEFAULT 'indeed',
        clave_base TEXT, ciudad TEXT DEFAULT '')""")
    v4.execute("INSERT INTO ofertas (url, clave, titulo, empresa, ubicacion, estado, detectada_en) VALUES "
               "('a','k1','Programador','HumanNet','Santiago, Chile','nueva','2026-10-01')")
    v4.execute("INSERT INTO ofertas (url, clave, titulo, empresa, ubicacion, estado, detectada_en) VALUES "
               "('b','k2','Programador','Empresas HumanNet - Chile','Santiago, Chile','postulada','2026-10-02')")
    v4.execute("PRAGMA user_version = 4"); v4.commit(); v4.close()

    con = buscar.conectar(ruta)
    filas = con.execute("SELECT url, estado FROM ofertas").fetchall()
    assert [(f["url"], f["estado"]) for f in filas] == [("b", "postulada")]
    assert con.execute("PRAGMA user_version").fetchone()[0] == buscar.VERSION_DB


def test_los_terminos_de_busqueda_no_incluyen_los_que_daban_cero():
    todos = set(config.TERMINOS_A + config.TERMINOS_B + config.TERMINOS_SECUNDARIOS)
    for malo in ("developer junior python", "desarrollador backend junior", "PMO junior", "BPMN UML",
                 "analista funcional ERP", "desarrollador frontend junior react"):
        assert malo not in todos


def test_migracion_v4_a_v5_une_oferta_sin_ciudad_con_la_que_si_la_tiene(tmp_path):
    ruta = str(tmp_path / "v4b.db")
    v4 = sqlite3.connect(ruta)
    v4.execute("""CREATE TABLE ofertas (url TEXT PRIMARY KEY, clave TEXT UNIQUE, titulo TEXT, empresa TEXT,
        ubicacion TEXT, publicada TEXT, raw TEXT, categoria TEXT, razon TEXT, tipo TEXT, prioridad TEXT,
        modalidad TEXT, contrato TEXT, sueldo TEXT, experiencia TEXT, motivo TEXT,
        estado TEXT DEFAULT 'nueva', busqueda TEXT, detectada_en TEXT, fuente TEXT DEFAULT 'indeed',
        clave_base TEXT, ciudad TEXT DEFAULT '')""")
    v4.execute("INSERT INTO ofertas (url, clave, titulo, empresa, ubicacion, detectada_en) VALUES "
               "('i','k1','Programador','HumanNet','Santiago de Chile, RM, Chile','2026-10-01')")
    v4.execute("INSERT INTO ofertas (url, clave, titulo, empresa, ubicacion, detectada_en) VALUES "
               "('g','k2','Programador','Empresas HumanNet - Chile','Chile','2026-10-02')")
    v4.execute("PRAGMA user_version = 4"); v4.commit(); v4.close()
    con = buscar.conectar(ruta)
    assert [r["url"] for r in con.execute("SELECT url FROM ofertas")] == ["i"]


def test_gob_entrega_la_hora_y_corta_en_24_horas():
    ahora = _dt.now(_tz.utc)
    def fila(horas):
        return getonboard.a_fila(item_gob(published_at=int((ahora - _td(hours=horas)).timestamp())))
    assert fila(1)["posted_at"].endswith("+00:00")
    df = pd.DataFrame([{**fila(23), "job_url": "http://23h"}, {**fila(25), "job_url": "http://25h"}],
                      columns=getonboard.COLUMNAS)
    recientes, antiguas = buscar.recientes(df, "getonboard", ahora, 1)
    assert list(recientes["job_url"]) == ["http://23h"] and antiguas == 1
