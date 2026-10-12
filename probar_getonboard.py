"""Verifica la API de Get on Board con datos reales. Uso:  python probar_getonboard.py

Muestra la respuesta cruda (para confirmar los nombres de campos) y cómo queda
traducida. Si algo sale vacío, pega la salida completa y lo ajusto.
"""
import json

import pandas as pd
import requests

import getonboard

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 50)

r = requests.get(f"{getonboard.BASE}/search/jobs", headers=getonboard.HEADERS, timeout=20,
                 params={"query": "QA", "per_page": 3, "page": 1, "expand[]": ["company", "seniority"]})
print("HTTP", r.status_code, r.headers.get("content-type"))
try:
    datos = r.json()
except ValueError:
    print(r.text[:500]); raise SystemExit
print("claves de primer nivel:", list(datos.keys()))
primero = (datos.get("data") or [None])[0]
if primero:
    attrs = primero.get("attributes", primero)
    print("claves de 'attributes':", sorted(attrs.keys()))
    resumen = {k: (str(v)[:80] if not isinstance(v, (dict, list)) else f"<{type(v).__name__}> {str(v)[:120]}")
               for k, v in attrs.items() if k not in ("description", "functions", "benefits", "desirable")}
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print("links:", primero.get("links"))
    print("relationships:", list((primero.get("relationships") or {}).keys()))

print("\n=== ya traducido por getonboard.buscar('QA') ===")
df = getonboard.buscar("QA", 20)
print(f"{len(df)} ofertas útiles (Chile o remoto global)")
if len(df):
    print(df[["title", "company", "location", "date_posted", "is_remote"]].head(8).to_string())
    print("\ncampos con datos (de", len(df), "filas):")
    for c in getonboard.COLUMNAS:
        llenos = int(df[c].astype(str).str.strip().replace({"None": "", "nan": ""}).ne("").sum())
        print(f"  {c}: {llenos}")
    print("\nejemplo de descripción:", df['description'].iloc[0][:300])


print("\n=== nivel (seniority) por oferta, con expand ===")
r2 = requests.get(f"{getonboard.BASE}/search/jobs", headers=getonboard.HEADERS, timeout=20,
                  params={"query": "QA", "per_page": 15, "page": 1, "expand[]": ["company", "seniority"]})
print("HTTP", r2.status_code)
if r2.ok:
    for it in r2.json().get("data", []):
        a = it.get("attributes", {})
        print(" ", repr(getonboard._nombre(a.get("seniority"))), "|", str(a.get("seniority"))[:90], "|", a.get("title"))
