# Búsqueda de empleo (job-tracker)

Busca ofertas en Indeed, Glassdoor, LinkedIn, Get on Board, BNE, Trabajando, Chiletrabajos y Chumi; las clasifica según tu perfil y las
muestra en una página local, con estados de seguimiento (nueva, revisada, postulada, entrevista, descartada).

## Con Docker (siempre encendida)
Requisito: Docker Desktop (gratis para uso personal) y, en sus ajustes, "Start Docker Desktop when you sign in".

    docker compose up -d --build        # construye y deja la página encendida
    # abre http://127.0.0.1:8765

- La página queda disponible aunque reinicies el PC (`restart: unless-stopped`). La búsqueda NO corre sola: se lanza con el botón «Buscar empleos».
- El puerto se publica solo en tu PC (127.0.0.1); no es accesible desde la red.
- La base de datos vive en un volumen de Docker (`jt_datos`), no dentro del contenedor, así que sobrevive a actualizaciones.
- Ver el registro: `docker compose logs -f`. Apagar: `docker compose down` (no borra tus datos).
- Actualizar tras cambiar código: `docker compose up -d --build`.

### Traer tu base de datos actual (ofertas.db) al volumen — una sola vez
    docker compose create
    docker compose cp ofertas.db jobtracker:/datos/ofertas.db
    docker compose up -d

### Copia de seguridad
    docker compose cp jobtracker:/datos/ofertas.db ./ofertas_respaldo.db

## Sin Docker
    python servidor.py        # abre http://127.0.0.1:8765
    python buscar.py          # búsqueda por consola (sin la página)
    python buscar.py --reclasificar
    python -m pytest -q

Todo se ajusta en `config.py`.

## Créditos y licencias
- Las ofertas de Indeed, Glassdoor y LinkedIn se obtienen con [JobSpy](https://github.com/speedyapply/JobSpy)
  (`python-jobspy`), software de código abierto bajo licencia MIT, © 2023 Cullen Watson. Se usa como dependencia,
  sin modificar su código.
- Get on Board se consulta con su API oficial. BNE, Trabajando, Chiletrabajos y Chumi se leen con código propio, respetando
  robots.txt.
- El texto completo de la licencia MIT se instala junto con el paquete (python_jobspy-1.3.0.dist-info).
