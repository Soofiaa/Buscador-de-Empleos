from jobspy import scrape_jobs

print("Iniciando búsqueda...")

try:
    jobs = scrape_jobs(
        site_name=["indeed"],  # empezamos solo con Indeed (el más estable)
        search_term="QA analyst",
        location="Santiago, Chile",
        results_wanted=10,
        hours_old=72,
        country_indeed="Chile",
    )
except Exception as e:
    print(f"Error durante la búsqueda: {type(e).__name__}: {e}")
    raise

print(f"Ofertas encontradas: {len(jobs)}")

if len(jobs) > 0:
    print(jobs[["title", "company", "location", "job_url"]].head(10).to_string())
else:
    print("No se encontraron ofertas. Prueba con otro término (ej. 'analista QA') o más horas en hours_old.")
