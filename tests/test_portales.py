"""BNE, Trabajando y Chiletrabajos (portados de la app 'Busca Empleo'). Todo con HTML/JSON real guardado, sin red."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import buscar
import bne
import chiletrabajos
import chumi
import config
import geo
import laborum
import linkedin
import trabajando
from filtros import ZONA, clasificar, extraer_experiencia, extraer_sueldo, normalizar
from red import Bloqueo, ClienteHTTP, ErrorFuente, NoEncontrada, Respuesta, pedir
from robots import Robots

FIX = Path(__file__).parent / "fixtures"


def leer(nombre):
    return (FIX / nombre).read_text(encoding="utf-8")


class RobotsLibre:
    def bloqueo(self, u): return ""
    def no_disponible(self, u): return False
    def permitido(self, u): return True


class Falso:
    """Cliente que responde según un diccionario {trozo_de_url: (status, texto)}."""
    def __init__(self, respuestas):
        self.respuestas, self.pedidas = respuestas, []

    def get(self, url, datos=None):
        self.pedidas.append(url)
        for trozo, (status, texto) in self.respuestas.items():
            if trozo in url:
                return Respuesta(status, texto, "" if status == 200 else f"HTTP {status}")
        return Respuesta(404, "", "HTTP 404")


# ---- geo
def test_geo_normaliza_a_formato_indeed():
    assert geo.ubicacion_indeed("Providencia", "Región Metropolitana de Santiago") == "Providencia, RM, Chile"
    assert geo.ubicacion_indeed("Viña del Mar", "Región de Valparaíso") == "Viña del Mar, VS, Chile"
    assert geo.ubicacion_indeed("Colina") == "Colina, RM, Chile"
    assert geo.ubicacion_indeed("Antofagasta") == "Antofagasta, XX, Chile"      # comuna desconocida = fuera de zona
    assert geo.ubicacion_indeed("Puerto Varas", "Región de Los Lagos") == "Puerto Varas, LL, Chile"


# ---- parsers con fixtures reales
def test_bne_listado():
    df = bne.parsear_busqueda(leer("bne_busqueda.json"))
    assert len(df) == 24 and list(df.columns) == bne.COLUMNAS
    assert df["job_url"].str.fullmatch(r"https://www\.bne\.gob\.cl/ofertas/\d+").all()
    assert df["date_posted"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert df["location"].str.endswith(", Chile").all()
    assert df["company"].iloc[0] == "Confidencial"                  # el sitio ya oculta el nombre


def test_bne_detalle_y_experiencia_llega_al_clasificador():
    det = bne.parsear_detalle(leer("bne_detalle.json"))
    assert det["experiencia"] == "5 años" and det["contrato"] == "Contrato indefinido"
    fila = {"description": "Analista de calidad"}
    assert bne.completar(fila, det)
    assert "Experiencia mínima (BNE): 5 años." in fila["description"]
    assert "Tipo de contrato (BNE): Contrato indefinido." in fila["description"]
    assert extraer_experiencia(fila["description"])[0] == 5
    assert bne.parsear_detalle('{"descripcion": "x", "experienciaRequerida": 0}')["experiencia"] == "No requerida"
    fila2 = {"description": "x"}
    bne.completar(fila2, {"descripcion": "", "experiencia": "3 años", "contrato": "Contrato a plazo Fijo"})
    assert extraer_experiencia(fila2["description"])[0] == 3 and "plazo Fijo" in fila2["description"]


def test_bne_respuesta_inesperada_es_error_de_fuente():
    with pytest.raises(ErrorFuente):
        bne.parsear_busqueda("<html>no es json</html>")
    with pytest.raises(ErrorFuente):
        bne.parsear_busqueda('{"otra": 1}')


def test_trabajando_listado_y_detalle():
    df = trabajando.parsear_listado(leer("trabajando_busqueda.html"))
    assert len(df) == 15 and df["job_url"].str.contains("/trabajo/").all()
    assert df["location"].str.contains(r", [A-Z]{2}, Chile").all()
    det = trabajando.parsear_detalle(leer("trabajando_detalle.html"))
    assert det["anios"] == 2 and det["operador"] == "Desde" and det["estado"] == "PUBLICADA"
    fila = {"description": "x", "is_remote": False}
    assert trabajando.completar(fila, det, datetime(2026, 10, 6))
    assert "Experiencia mínima: 2 años" in fila["description"]
    assert extraer_experiencia(fila["description"])[0] == 2


def test_trabajando_aviso_vencido_o_finalizado_se_omite():
    det = trabajando.parsear_detalle(leer("trabajando_detalle.html"))
    assert not trabajando.completar({"description": "x"}, det, datetime(2027, 1, 1))     # ya venció
    det["estado"] = "FINALIZADA"
    assert not trabajando.completar({"description": "x"}, det, datetime(2026, 10, 6))


def test_trabajando_modalidad_por_jornada():
    assert trabajando._modalidad("Mixta (Teletrabajo + Presencial)") == "hibrido"
    assert trabajando._modalidad("Teletrabajo") == "remoto"
    assert trabajando._modalidad("Jornada Completa") == ""


def test_chiletrabajos_listado_y_detalle():
    df = chiletrabajos.parsear_listado(leer("chiletrabajos_busqueda.html"))
    assert len(df) == 17 and df["job_url"].str.startswith("https://www.chiletrabajos.cl/trabajo/").all()
    det = chiletrabajos.parsear_detalle(leer("chiletrabajos_detalle.html"))
    fila = {"description": "x", "is_remote": False}
    assert chiletrabajos.completar(fila, det, datetime(2026, 10, 6))
    assert fila["is_remote"] is True                                  # TELECOMMUTE
    # la "Duración: Plazo Fijo después indefinido" del sitio no se agrega como plazo fijo a secas
    assert "duración: contrato inicial y luego indefinido" in fila["description"]
    assert not chiletrabajos.completar({"description": "x"}, det, datetime(2027, 6, 1))   # vencido


def test_chiletrabajos_por_proyecto_queda_en_el_texto():
    det = chiletrabajos.parsear_detalle(leer("chiletrabajos_detalle_por_proyecto.html"))
    fila = {"description": "x"}
    chiletrabajos.completar(fila, det, datetime(2026, 10, 6))
    assert "Por proyecto" in fila["description"]


# ---- red: robots y bloqueos
def test_pedir_se_detiene_ante_bloqueos():
    robots = RobotsLibre()
    for status in (401, 403, 429):
        with pytest.raises(Bloqueo):
            pedir("https://x.cl/a", Falso({"x.cl": (status, "")}), robots)
    with pytest.raises(Bloqueo):                                   # 200 pero es un desafío anti-bots
        pedir("https://x.cl/a", Falso({"x.cl": (200, "<html>Just a moment... cf-chl</html>")}), robots)
    with pytest.raises(NoEncontrada):
        pedir("https://x.cl/a", Falso({"x.cl": (404, "")}), robots)
    with pytest.raises(ErrorFuente):
        pedir("https://x.cl/a", Falso({"x.cl": (500, "")}), robots)


def test_pedir_respeta_robots():
    class Prohibe(RobotsLibre):
        def permitido(self, u): return False
    class Rechaza(RobotsLibre):
        def bloqueo(self, u): return "HTTP 403"
    cli = Falso({"x.cl": (200, "ok")})
    with pytest.raises(ErrorFuente):
        pedir("https://x.cl/a", cli, Prohibe())
    with pytest.raises(Bloqueo):
        pedir("https://x.cl/a", cli, Rechaza())
    assert cli.pedidas == []                                       # nunca se pidió la página


def test_cliente_http_pausa_entre_peticiones():
    dormidas = []
    class Ctx:
        status = 200
        headers = type("H", (), {"get_content_charset": lambda s: "utf-8"})()
        def read(self): return b"ok"
        def __enter__(self): return self
        def __exit__(self, *a): return False
    c = ClienteHTTP(dormir=dormidas.append, azar=lambda a, b: 4.0, abrir=lambda req, timeout: Ctx())
    c.get("https://x.cl/1"); c.get("https://x.cl/2")
    assert dormidas == [4.0] and c.peticiones == 2                 # sin pausa antes de la primera


# ---- flujo completo con red falsa
@pytest.fixture
def con(tmp_path):
    return buscar.conectar(str(tmp_path / "t.db"))


def test_portal_bloqueado_se_detiene_y_avisa(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643", "tester"])
    cli = Falso({"bne.gob.cl": (403, "")})
    avisos = []
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0}
    buscar._buscar_portal(con, "bne", st, avisos, cli, RobotsLibre())
    assert len(cli.pedidas) == 1                                   # al primer 403 no se pide nada más
    assert any("se detuvo" in a for a in avisos)


def test_trabajando_404_se_recuerda_y_no_se_vuelve_a_pedir(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_TRABAJANDO", ["desarrollador-junior"])
    cli = Falso({})
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0}
    buscar._buscar_portal(con, "trabajando", st, [], cli, RobotsLibre())
    buscar._buscar_portal(con, "trabajando", st, [], cli, RobotsLibre())
    assert len(cli.pedidas) == 1 and st["errores"] == 0


def test_bne_flujo_completo_detalle_con_tope_y_guardado(con, monkeypatch):
    ahora = datetime(2026, 9, 15, 12, 0, tzinfo=ZONA)
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643"])
    monkeypatch.setitem(config.MAX_DETALLES, "bne", 2)
    cli = Falso({"busqueda": (200, leer("bne_busqueda.json")),
                 "/api/ofertas/publica/": (200, leer("bne_detalle.json"))})
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0, "antiguas": 0}
    avisos = []
    buscar._buscar_portal(con, "bne", st, avisos, cli, RobotsLibre(), ahora, 10)
    detalles = [u for u in cli.pedidas if "/api/ofertas/publica/" in u]
    assert len(detalles) <= 2
    filas = con.execute("SELECT url, fuente, publicada FROM ofertas").fetchall()
    assert filas and all(f["fuente"] == "bne" for f in filas)
    # segunda corrida: lo ya guardado no se vuelve a pedir
    cli2 = Falso({"busqueda": (200, leer("bne_busqueda.json"))})
    buscar._buscar_portal(con, "bne", st, [], cli2, RobotsLibre(), ahora, 10)
    assert len([u for u in cli2.pedidas if "/api/ofertas/publica/" in u]) <= 2


def test_portal_no_abre_detalle_de_ofertas_antiguas(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_BNE", ["ocupacion:7643"])
    cli = Falso({"busqueda": (200, leer("bne_busqueda.json")),
                 "/api/ofertas/publica/": (200, leer("bne_detalle.json"))})
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0, "antiguas": 0}
    buscar._buscar_portal(con, "bne", st, [], cli, RobotsLibre(), datetime(2026, 12, 31, 12, 0, tzinfo=ZONA), 1)
    assert not [u for u in cli.pedidas if "/api/ofertas/publica/" in u]
    assert con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 0


def test_trabajando_trae_hora_de_publicacion():
    df = trabajando.parsear_listado(leer("trabajando_busqueda.html"))
    assert df["posted_at"].iloc[0] == "2026-09-07T15:57"            # sin zona: se entiende hora de Chile
    assert df["posted_at"].str.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}").all()


def test_linkedin_listado():
    df = linkedin.parsear_listado(leer("linkedin_listado.html"))
    assert len(df) == 10 and list(df.columns) == linkedin.COLUMNAS
    assert df["job_url"].str.contains("linkedin.com/jobs/view/").all()
    assert (df["title"] != "").all()
    assert (df["company"] != "").all()
    assert df["date_posted"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()


def test_linkedin_detalle_y_completar():
    det = linkedin.parsear_detalle(leer("linkedin_detalle.html"))
    assert "Oracle Fusion Cloud" in det["descripcion"]
    assert "nivel de antiguedad" in det["criterios"]
    fila = {"description": "Consultor Funcional", "location": "Santiago, Chile", "is_remote": False}
    assert linkedin.completar(fila, det)
    assert "Nivel: Algo de responsabilidad." in fila["description"]
    assert "Oracle Fusion Cloud" in fila["description"]


def test_linkedin_extrae_job_id():
    url = "https://cl.linkedin.com/jobs/view/analista-funcional-at-lisit-4464585712?position=1&pageNum=0"
    assert linkedin._job_id(url) == "4464585712"


def test_linkedin_respuesta_vacia_es_error_de_fuente():
    with pytest.raises(ErrorFuente):
        linkedin.parsear_listado("")


def test_linkedin_listar_con_red():
    cli = Falso({"seeMoreJobPostings": (200, leer("linkedin_listado.html"))})
    df = linkedin.listar("analista funcional", cli, RobotsLibre())
    assert len(df) == 10 and list(df.columns) == linkedin.COLUMNAS
    assert (df["title"] != "").all()


def test_linkedin_en_consulta_y_config():
    assert "linkedin" in config.SITIOS
    assert "linkedin" in config.NOMBRE_FUENTE
    kw = buscar.consulta("linkedin", "QA", "Santiago, Chile", dias=2)
    assert kw["site_name"] == ["linkedin"]
    assert kw["search_term"] == "QA"
    assert kw["location"] == "Santiago, Chile"
    assert kw["hours_old"] == 48



def test_los_portales_estan_en_las_fuentes_y_tienen_nombre():
    for s in ("bne", "trabajando", "chiletrabajos"):
        assert s in config.SITIOS and s in config.NOMBRE_FUENTE and s in config.MAX_DETALLES
    assert "linkedin" in config.SITIOS and "linkedin" in config.NOMBRE_FUENTE
    assert "ocupacion:7643" in config.TERMINOS_BNE


# ---- portales del 19-10 que rechazan a la app (403 incluso con navegador real, 20-10): fuera del proyecto
@pytest.mark.parametrize("sitio", ["computrabajo", "buscojobs", "empleospublicos", "empleostech"])
def test_los_portales_que_rechazan_a_la_app_no_estan(sitio):
    assert sitio not in config.SITIOS and sitio not in buscar.PORTALES and sitio not in config.NOMBRE_FUENTE
    assert not (Path(__file__).resolve().parent.parent / f"{sitio}.py").exists()


# ---- Laborum (respuesta real de searchV2 del 20-10-2026; el navegador se reemplaza por una función falsa)
ROBOTS_LABORUM = """User-agent: *
Disallow: /*recientes=true
Disallow: /*relevantes=true
Disallow: /empleos-busquedaext-
Disallow: /*?localidades=*
"""


def test_laborum_url_y_robots():
    assert laborum.url_busqueda("Análisis de Datos") == "https://www.laborum.cl/empleos-busqueda-analisis-de-datos.html"
    rob = Robots(ROBOTS_LABORUM)
    assert all(rob.permitido(laborum.url_busqueda(t)) for t in config.TERMINOS_LABORUM)
    assert not rob.permitido("https://www.laborum.cl/empleos-busqueda-qa.html?recientes=true")
    assert "laborum" in config.SITIOS and "laborum" in buscar.PORTALES and laborum.SIN_DETALLE


def test_laborum_parsea_la_busqueda():
    df = laborum.parsear_busqueda(leer("laborum_busqueda.json"))
    assert len(df) == 20 and list(df.columns) == laborum.COLUMNAS
    assert df["job_url"].str.fullmatch(r"https://www\.laborum\.cl/empleos/[^/]+-\d{6,}\.html").all()
    assert df["date_posted"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert df["location"].str.endswith(", Chile").all()
    primera = df.iloc[0]
    assert primera["location"] == "Providencia, RM, Chile" and primera["company"] == ""     # aviso confidencial
    assert primera["description"].startswith("Modalidad: Presencial.") and "🚀" in primera["description"]
    with pytest.raises(ErrorFuente):
        laborum.parsear_busqueda('{"otra": 1}')


def test_laborum_usa_el_enlace_del_html_si_esta():
    df = laborum.parsear_busqueda(leer("laborum_busqueda.json"), {"1118486638": "https://www.laborum.cl/empleos/x-1118486638.html"})
    assert df["job_url"].iloc[0] == "https://www.laborum.cl/empleos/x-1118486638.html"


class ClienteFalso:
    def __init__(self):
        self.turnos, self.status = 0, []
        self.al_responder = self.status.append
    def esperar_turno(self):
        self.turnos += 1


def test_laborum_listar_respeta_reglas():
    datos = json.loads(leer("laborum_busqueda.json"))
    cli = ClienteFalso()
    df = laborum.listar("analista de datos", cli, RobotsLibre(), abrir=lambda url: (200, 200, datos, {}))
    assert len(df) == 20 and cli.turnos == 1 and cli.status == [200, 200]   # pausa y telemetría como cualquier petición
    for s in (403, 429):
        with pytest.raises(Bloqueo):
            laborum.listar("x", ClienteFalso(), RobotsLibre(), abrir=lambda url, s=s: (s, 0, None, {}))
    with pytest.raises(Bloqueo):                                              # la API de la página rechaza
        laborum.listar("x", ClienteFalso(), RobotsLibre(), abrir=lambda url: (200, 403, None, {}))
    abiertas = []
    class Prohibe(RobotsLibre):
        def permitido(self, u): return False
    with pytest.raises(ErrorFuente):
        laborum.listar("x", ClienteFalso(), Prohibe(), abrir=lambda url: abiertas.append(url))
    assert abiertas == []                                                     # sin permiso no se abre el navegador


def test_laborum_sin_playwright_se_detiene(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(Bloqueo, match="Playwright"):
        laborum._abrir_busqueda("https://www.laborum.cl/empleos-busqueda-qa.html")


def test_laborum_flujo_sin_detalles_y_solo_recientes(con, monkeypatch):
    datos = json.loads(leer("laborum_busqueda.json"))
    monkeypatch.setattr(config, "TERMINOS_LABORUM", ["analista de datos"])
    monkeypatch.setattr(laborum, "_abrir_busqueda", lambda url: (200, 200, datos, {}))
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0}
    avisos = []
    buscar._buscar_portal(con, "laborum", st, avisos, ClienteFalso(), RobotsLibre(), datetime(2026, 10, 20, 12, 0, tzinfo=ZONA), 1)
    assert (st["encontradas"], st["antiguas"], st["errores"]) == (3, 17, 0)   # 19 y 20-10: hoy y ayer
    filas = con.execute("SELECT fuente, publicada FROM ofertas").fetchall()
    assert len(filas) == 3 and all(f["fuente"] == "laborum" and f["publicada"] >= "2026-10-19" for f in filas)
    assert not avisos                                                          # sin "candidatas esperan": no hay detalles


def test_cliente_http_esperar_turno():
    dormidas = []
    c = ClienteHTTP(dormir=dormidas.append, azar=lambda a, b: 3.5)
    c.esperar_turno(); c.esperar_turno()
    assert dormidas == [3.5] and c.peticiones == 2


# ---- Chumi (fixtures reales del 20-10-2026)
def test_chumi_esta_conectado():
    assert "chumi" in config.SITIOS and "chumi" in buscar.PORTALES and "chumi" in config.MAX_DETALLES
    assert chumi.url_busqueda("página 2") == "https://chumi-it.com/trabajos?page=2"
    assert all(chumi.url_busqueda(t).startswith("https://chumi-it.com/trabajos?page=") for t in config.TERMINOS_CHUMI)


def test_chumi_listado():
    df = chumi.parsear_listado(leer("chumi_trabajos.html"))
    assert len(df) == 25 and list(df.columns) == chumi.COLUMNAS
    assert df["job_url"].str.startswith("https://chumi-it.com/trabajos/").all()
    assert not df["title"].str.match(r"[A-Z]{2,5}\d{3,5} ").any()             # sin el código interno "ROS1001 - "
    assert chumi._RX_CODIGO.sub("", "MIA0802 Desarrollador(a) Banner") == "Desarrollador(a) Banner"
    assert (df["company"] != "").all()
    assert (df["location"] == "Chile").sum() == 23                              # "Chile" a secas, sin región XX
    assert (df["location"] == "Mexico (México)").sum() == 2
    assert set(df["description"]) <= {"Modalidad presencial.", "Modalidad híbrida.", "Modalidad remota."}


def test_chumi_listado_vacio_o_ajeno():
    assert chumi.parsear_listado("<html><title>Empleos | CHUMI-IT</title><body></body></html>").empty
    with pytest.raises(ErrorFuente):
        chumi.parsear_listado("<html><title>Otra cosa</title></html>")


def test_chumi_detalle_y_completar():
    det = chumi.parsear_detalle(leer("chumi_detalle.html"))
    assert det["publicada"] == "2026-10-19" and det["empresa"] == "IT-Talent"
    assert det["sueldo"] == "USD 2.000 a 2.500 al mes"
    fila = {"description": "Modalidad presencial.", "location": "Chile", "company": "", "date_posted": "", "is_remote": False}
    assert chumi.completar(fila, det, datetime(2026, 10, 20))
    assert fila["date_posted"] == "2026-10-19" and fila["company"] == "IT-Talent"
    assert fila["description"].startswith("Modalidad presencial.") and "Mínimo 3 a 5 año" in fila["description"]
    assert "Sueldo informado (Chumi): USD" in fila["description"]
    assert extraer_sueldo(fila, normalizar(fila["description"]))[1] == 2000000                # el de la descripción, en pesos
    linea_usd = "Sueldo informado (Chumi): %s." % det["sueldo"]
    assert extraer_sueldo({}, normalizar(linea_usd)) == ("No indicado", None)                # USD no se lee como pesos
    assert not chumi.completar({"description": ""}, det, datetime(2026, 11, 21))                # vencido


def test_chumi_detalle_sin_jobposting_es_error_de_fuente():
    with pytest.raises(ErrorFuente):
        chumi.parsear_detalle("<html><body>sin datos</body></html>")


def test_chumi_flujo_completo(con, monkeypatch):
    monkeypatch.setattr(config, "TERMINOS_CHUMI", ["página 1"])
    monkeypatch.setitem(config.MAX_DETALLES, "chumi", 3)
    cli = Falso({"trabajos?page=": (200, leer("chumi_trabajos.html")),
                 "/trabajos/": (200, leer("chumi_detalle.html"))})
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0}
    avisos = []
    buscar._buscar_portal(con, "chumi", st, avisos, cli, RobotsLibre(), datetime(2026, 10, 20, 12, 0, tzinfo=ZONA), 1)
    detalles = [u for u in cli.pedidas if "/trabajos/" in u]
    assert 0 < len(detalles) <= 3 and st["encontradas"] == 25 and st["errores"] == 0
    filas = con.execute("SELECT url, fuente FROM ofertas").fetchall()
    assert filas and all(f["fuente"] == "chumi" and f["url"].startswith("https://chumi-it.com/trabajos/") for f in filas)
    assert any("esperan a la próxima corrida" in a or "espera a la próxima" in a for a in avisos)


def test_chumi_detalle_antiguo_no_se_guarda_ni_se_vuelve_a_pedir(con, monkeypatch):
    # el detalle dice 2026-10-19 y vence el 20-11: el 10-11 sigue vigente pero ya es antiguo para una ventana de 1 día
    monkeypatch.setattr(config, "TERMINOS_CHUMI", ["página 1"])
    monkeypatch.setitem(config.MAX_DETALLES, "chumi", 2)
    ahora = datetime(2026, 11, 10, 12, 0, tzinfo=ZONA)
    respuestas = {"trabajos?page=": (200, leer("chumi_trabajos.html")), "/trabajos/": (200, leer("chumi_detalle.html"))}
    st = {"encontradas": 0, "relevantes": 0, "sin_chile": 0, "errores": 0}
    cli = Falso(respuestas)
    buscar._buscar_portal(con, "chumi", st, [], cli, RobotsLibre(), ahora, 1)
    abiertas = [u for u in cli.pedidas if "/trabajos/" in u]
    assert len(abiertas) == 2 and st["antiguas"] == 2
    guardadas = {u for (u,) in con.execute("SELECT url FROM ofertas")}
    assert guardadas and not guardadas & set(abiertas)
    cli2 = Falso(respuestas)
    buscar._buscar_portal(con, "chumi", st, [], cli2, RobotsLibre(), ahora, 1)
    assert not set(abiertas) & set(cli2.pedidas)                               # no se gastan detalles en ellas otra vez


def test_jobspy_pausa_por_fuente_y_se_detiene_ante_429(con, monkeypatch):
    import logging
    import pandas as pd
    llamadas, pausas = [], []
    def scrape_jobs(**kw):
        sitio = kw["site_name"][0]
        llamadas.append(sitio)
        if sitio == "linkedin":                            # como JobSpy: no lanza error, solo lo registra en su logger
            logging.getLogger("JobSpy:LinkedIn").error("LinkedIn response status code 429")
        return pd.DataFrame()
    monkeypatch.setitem(sys.modules, "jobspy", type(sys)("jobspy"))
    sys.modules["jobspy"].scrape_jobs = scrape_jobs
    monkeypatch.setattr(config, "SITIOS", ["linkedin", "glassdoor"])
    monkeypatch.setattr(config, "TERMINOS_SECUNDARIOS", ["qa", "tester"])
    monkeypatch.setattr(config, "UBICACIONES", ["Santiago, Chile"])
    monkeypatch.setattr(config, "INCLUIR_REMOTO", False)
    monkeypatch.setattr(buscar.time, "sleep", pausas.append)
    monkeypatch.setattr(buscar, "_say", lambda m: None)
    buscar.buscar_ofertas(con)
    assert llamadas == ["linkedin", "glassdoor", "glassdoor"]        # tras el 429, LinkedIn no se vuelve a consultar
    assert 6.0 <= pausas[0] <= 10.0 and all(3.0 <= p <= 5.0 for p in pausas[1:])
    detalle = json.loads(con.execute("SELECT detalle FROM corridas").fetchone()[0])
    assert any("LinkedIn respondió 429" in a for a in detalle["avisos"])
    assert next(f for f in detalle["fuentes"] if f["fuente"] == "LinkedIn")["errores"] == 1
    assert buscar._pausa_jobspy("indeed") == config.PAUSA_ENTRE_BUSQUEDAS


def test_un_portal_que_falla_no_corta_la_corrida(con, monkeypatch):
    monkeypatch.setitem(sys.modules, "jobspy", type(sys)("jobspy"))    # sin consultas JobSpy: solo portales
    sys.modules["jobspy"].scrape_jobs = None
    monkeypatch.setattr(config, "SITIOS", ["bne", "chiletrabajos"])
    llamados = []
    def falso(con, sitio, st, avisos, *a, **k):
        llamados.append(sitio)
        if sitio == "bne":
            raise TypeError("expected string or bytes-like object, got 'Tag'")
        return 2
    monkeypatch.setattr(buscar, "_buscar_portal", falso)
    monkeypatch.setattr(buscar, "_say", lambda m: None)
    assert buscar.buscar_ofertas(con) == 2
    assert llamados == ["bne", "chiletrabajos"]                        # siguió con el portal siguiente
    detalle = json.loads(con.execute("SELECT detalle FROM corridas").fetchone()[0])   # la corrida quedó registrada
    bne_st = next(f for f in detalle["fuentes"] if f["fuente"] == "BNE")
    assert bne_st["errores"] == 1
    assert any("BNE falló: TypeError" in a for a in detalle["avisos"])


