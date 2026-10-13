# Reversión de la Fase A (volver a la Fase 0)

La Fase A migra la base de la versión 6 a la 7 al arrancar. **El código de la Fase 0 trata una base v7 como "versión
desconocida" y la renombra a `ofertas_antigua_*.db`**, así que para volver atrás NO basta con levantar la imagen
anterior: hay que restaurar también la base respaldada antes del despliegue.

Piezas que deben existir antes de desplegar la Fase A:

| Pieza | Dónde | Cómo se comprueba |
|---|---|---|
| Imagen de la Fase 0 | etiqueta `job-tracker:fase0` | `docker image inspect job-tracker:fase0` |
| Base anterior a la migración | `/datos/ofertas_pre_faseA_20261013.db` en el volumen `job-tracker_jt_datos` y una copia en `respaldos\` | sha256 anotado al crearla + `PRAGMA integrity_check` = ok |

## Procedimiento (PowerShell o Git Bash, desde la carpeta `job-tracker`)

1. **Detener** el contenedor (no borrar el volumen; nunca `down -v`):

   ```
   docker compose stop jobtracker
   ```

2. **Restaurar la base** dentro del volumen. La base v7 no se borra: se aparta con otro nombre.
   Reemplaza `SHA_PRE_FASE_A` por el sha256 anotado al crear el respaldo:

   ```
   docker run --rm --network none -v job-tracker_jt_datos:/datos ubuntu:latest sh -ec '
     cd /datos
     test "$(sha256sum ofertas_pre_faseA_20261013.db | cut -c1-64)" = SHA_PRE_FASE_A
     sello=$(date +%Y%m%d-%H%M%S)
     for f in ofertas.db ofertas.db-wal ofertas.db-shm; do [ -e "$f" ] && mv "$f" "retirada_faseA_${sello}_$f"; done
     cp ofertas_pre_faseA_20261013.db ofertas.db
     chown root:root ofertas.db && chmod 0644 ofertas.db
     ls -la'
   ```

3. **Levantar la imagen de la Fase 0** sin reconstruir:

   ```
   docker tag job-tracker:fase0 job-tracker-jobtracker:latest
   docker compose up -d --no-build
   ```

   (Si después se reconstruye con `docker compose build`, volverá el código que haya en la carpeta. Para que el código
   también vuelva a la Fase 0: `git revert` de los commits de la Fase A, o `git checkout 71d3017 -- .` en una rama.)

4. **Verificar**:

   ```
   docker exec jobtracker python -c "import sqlite3; c=sqlite3.connect('file:/datos/ofertas.db?mode=ro',uri=True); q=lambda s: c.execute(s).fetchone()[0]; print(q('pragma user_version'), q('pragma integrity_check'), q('select count(*) from ofertas'), q('select count(*) from corridas'), q(\"select count(*) from ofertas where estado='postulada'\"))"
   docker exec jobtracker ls /datos          # no debe aparecer ningún ofertas_antigua_*
   docker inspect jobtracker --format "{{.State.Health.Status}}"
   ```

   Debe dar versión **6**, integridad **ok** y los mismos números que había antes de desplegar la Fase A
   (al 13-10-2026: 1071 ofertas, 4 corridas, 11 postuladas). Lo que se haya hecho en la página después de desplegar la
   Fase A (estados, notas, fases) queda en la base apartada `retirada_faseA_*`, no en la restaurada.
