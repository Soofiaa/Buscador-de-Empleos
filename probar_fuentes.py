"""Prueba rápida de cada fuente ANTES de la corrida larga.

Hace una búsqueda por fuente y muestra cómo llega la ubicación. Sirve para saber
si Google y Glassdoor funcionan con Chile. Uso:  python probar_fuentes.py
"""
import pandas as pd
from jobspy import scrape_jobs

import buscar

PRUEBAS = [
    ("indeed", "QA", "Santiago, Chile"),
    ("google", "QA", "Santiago, Chile"),
    ("glassdoor", "QA", "Santiago, Chile"),
    ("glassdoor", "QA", "Viña del Mar, Chile"),
]
COLUMNAS = ["title", "company", "location", "date_posted", "largo_descripcion"]

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 45)
for sitio, termino, lugar in PRUEBAS:
    print(f"\n=== {sitio} | {termino} | {lugar} ===")
    try:
        df = scrape_jobs(**buscar.consulta(sitio, termino, lugar, resultados=10))
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        continue
    print(f"{len(df)} resultados")
    if len(df):
        # el clasificador necesita la descripción (experiencia, modalidad, contrato, señales)
        df["largo_descripcion"] = df.get("description", pd.Series([""] * len(df))).fillna("").str.len()
        print(f"descripciones con texto: {(df['largo_descripcion'] > 0).sum()} de {len(df)}")
        print(df.reindex(columns=COLUMNAS).head(5).to_string())
