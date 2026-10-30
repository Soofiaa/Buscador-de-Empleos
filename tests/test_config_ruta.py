"""La base local por defecto no vive dentro de OneDrive (la nube la sincroniza y puede corromper un SQLite abierto)."""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _ruta_por_defecto():
    entorno = {k: v for k, v in os.environ.items() if k != "JT_DB"}
    salida = subprocess.run([sys.executable, "-c", "import config; print(config.DB_PATH)"],
                            cwd=RAIZ, env=entorno, capture_output=True, text=True, check=True)
    return salida.stdout.strip()


def test_ruta_por_defecto_fuera_de_onedrive():
    ruta = os.path.abspath(os.path.join(RAIZ, _ruta_por_defecto()))   # relativa = la carpeta del proyecto (OneDrive)
    assert "onedrive" not in ruta.lower()
    assert ruta.endswith("ofertas.db")


def test_jt_db_sigue_mandando_si_se_fija(monkeypatch):
    monkeypatch.setenv("JT_DB", "/datos/ofertas.db")
    entorno = dict(os.environ)
    salida = subprocess.run([sys.executable, "-c", "import config; print(config.DB_PATH)"],
                            cwd=RAIZ, env=entorno, capture_output=True, text=True, check=True)
    assert salida.stdout.strip() == "/datos/ofertas.db"
