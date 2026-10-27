"""We Work Remotely: filtro por región, mapeo del RSS y errores (sin red real)."""
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import buscar
import config
import weworkremotely as wwr

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss">
<channel><title>WWR</title>
  <item>
    <title>Klue: Senior Software Engineer</title>
    <link>https://weworkremotely.com/remote-jobs/klue-senior</link>
    <region>Anywhere in the World</region><country></country>
    <pubDate>Tue, 27 Oct 2026 01:00:00 +0000</pubDate>
    <category>Programming</category>
    <description>resumen corto</description>
    <media:content><p>Descripción <strong>completa</strong> del puesto.</p></media:content>
  </item>
  <item>
    <title>Acme: QA Tester</title>
    <link>https://weworkremotely.com/remote-jobs/acme-qa</link>
    <region>Americas Only</region><country></country>
    <pubDate>Mon, 26 Oct 2026 10:00:00 +0000</pubDate>
    <description>x</description>
  </item>
  <item>
    <title>Euro: Data Analyst</title>
    <link>https://weworkremotely.com/remote-jobs/euro-data</link>
    <region>Europe Only</region><country></country>
    <pubDate>Mon, 26 Oct 2026 09:00:00 +0000</pubDate>
    <description>x</description>
  </item>
  <item>
    <title>Chile: Analista Funcional</title>
    <link>https://weworkremotely.com/remote-jobs/chile-funcional</link>
    <region>Americas Only</region><country>Chile</country>
    <pubDate>Sun, 25 Oct 2026 09:00:00 +0000</pubDate>
    <description>x</description>
  </item>
  <item>
    <title>Sin datos: Practicante</title>
    <link>https://weworkremotely.com/remote-jobs/sin-datos</link>
    <pubDate>Sun, 25 Oct 2026 08:00:00 +0000</pubDate>
    <description>x</description>
  </item>
</channel></rss>"""


class Respuesta:
    def __init__(self, status=200, contenido=b""):
        self.status_code = status
        self.content = contenido

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


@pytest.fixture
def feed(monkeypatch):
    monkeypatch.setattr(wwr.requests, "get", lambda *a, **k: Respuesta(200, RSS.encode("utf-8")))


def test_registrada_en_config_y_api():
    assert "weworkremotely" in config.SITIOS and config.NOMBRE_FUENTE["weworkremotely"] == "We Work Remotely"
    assert "weworkremotely" in buscar.APIS_REMOTAS and buscar.APIS_REMOTAS["weworkremotely"] is wwr
    assert config.MAX_ANTIGUEDAD_DIAS.get("weworkremotely") == 2


@pytest.mark.parametrize("region,country,esperado", [
    ("Anywhere in the World", "", True),
    ("Worldwide", "", True),
    ("Americas Only", "", True),
    ("Europe Only", "", False),
    ("USA Only", "", False),
    ("", "", True),                     # sin restricción declarada
    ("Europe Only", "Chile", True),      # Chile manda
])
def test_acepta_por_region(region, country, esperado):
    assert wwr.acepta(region, country) is esperado


def test_buscar_filtra_y_mapea(feed):
    df = wwr.buscar(resultados=100)
    assert isinstance(df, pd.DataFrame) and list(df.columns) == wwr.COLUMNAS
    urls = list(df["job_url"])
    assert "https://weworkremotely.com/remote-jobs/klue-senior" in urls
    assert "https://weworkremotely.com/remote-jobs/acme-qa" in urls
    assert "https://weworkremotely.com/remote-jobs/chile-funcional" in urls
    assert "https://weworkremotely.com/remote-jobs/euro-data" not in urls      # Europe Only
    fila = df[df["job_url"].str.endswith("klue-senior")].iloc[0]
    assert (fila["title"], fila["company"]) == ("Senior Software Engineer", "Klue")
    assert fila["date_posted"] == "2026-10-27" and bool(fila["is_remote"]) is True
    assert "completa" in fila["description"] and "<" not in fila["description"]
    assert df[df["job_url"].str.endswith("chile-funcional")].iloc[0]["location"] == "Chile"
    assert set(df["location"]) <= {"Chile", "Remoto (global)"}


def test_respeta_el_tope(feed):
    assert len(wwr.buscar(resultados=2)) == 2


def test_error_http_se_propaga(monkeypatch):
    monkeypatch.setattr(wwr.requests, "get", lambda *a, **k: Respuesta(503, b""))
    with pytest.raises(requests.HTTPError):
        wwr.buscar(resultados=10)


def test_la_telemetria_recibe_el_status(feed):
    vistos = []
    wwr.buscar(resultados=10, al_responder=vistos.append)
    assert vistos == [200]
