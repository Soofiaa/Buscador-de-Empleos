from jobspy import scrape_jobs

# Combinaciones a probar: (término, ubicación, horas)
pruebas = [
    ("analista QA", "Santiago, Chile", 720),
    ("QA", "Santiago, Chile", 720),
    ("analista funcional", "Santiago, Chile", 720),
    ("desarrollador python", "Santiago, Chile", 720),
    ("desarrollador", "Chile", 720),
]

for termino, ubicacion, horas in pruebas:
    print(f"\n=== '{termino}' | {ubicacion} | últimas {horas} h ===")
    try:
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term=termino,
            location=ubicacion,
            results_wanted=10,
            hours_old=horas,
            country_indeed="Chile",
            verbose=2,  # muestra el log interno de JobSpy
        )
        print(f"Resultados: {len(jobs)}")
        if len(jobs) > 0:
            print(jobs[["title", "company", "location"]].head(5).to_string())
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
