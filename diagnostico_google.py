"""Diagnóstico de Google Jobs: ¿qué página recibe JobSpy y por qué no trae empleos?
Uso:  python diagnostico_google.py     (guarda google_*.html para revisarlo)
"""
import re

import requests
from jobspy.google.constant import headers_initial

CONSULTAS = {
    "consulta que arma JobSpy": "QA jobs near Santiago, Chile in the last month",
    "inglés, sin ubicación": "QA analyst jobs Chile",
}
SENALES = {
    "página de consentimiento": r"consent\.google|before you continue",
    "bloqueo anti-bots": r"unusual traffic|captcha|recaptcha|/sorry/",
    "pide activar JavaScript": r"enablejs|enable javascript|<noscript",
    "tiene el bloque que busca JobSpy (data-async-fc)": r'data-async-fc="',
    "tiene el contenedor de empleos (Yust4d)": r'jsname="Yust4d"',
}
for i, (nombre, q) in enumerate(CONSULTAS.items(), 1):
    print(f"\n=== {nombre}: {q!r} ===")
    try:
        r = requests.get("https://www.google.com/search", headers=headers_initial,
                         params={"q": q, "udm": "8"}, timeout=20)
    except requests.RequestException as e:
        print("ERROR de red:", e); continue
    html = r.text
    print(f"HTTP {r.status_code} | {len(html)} caracteres | url final: {r.url[:100]}")
    for etiqueta, patron in SENALES.items():
        print(f"  {'SÍ ' if re.search(patron, html, re.I) else 'no '} {etiqueta}")
    titulo = re.search(r"<title>(.*?)</title>", html, re.S)
    print("  título de la página:", (titulo.group(1).strip()[:80] if titulo else "(sin título)"))
    archivo = f"google_{i}.html"
    open(archivo, "w", encoding="utf-8").write(html)
    print(f"  guardado en {archivo}")
print("\nSi 'tiene el bloque que busca JobSpy' sale en 'no' en ambas, Google no está entregando"
      "\nel listado a este cliente y JobSpy no lo arregla desde su lado.")
