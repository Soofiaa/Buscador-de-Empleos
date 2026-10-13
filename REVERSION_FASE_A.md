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

---

# Reversión de SAP / ERP y Soporte TI (volver a la Fase A)

Despliegue del 13-10-2026 (commits `8cb6681` y `007a772`, reclasificación dirigida de 25 ofertas). Esta vez **no
cambia el esquema** (la base sigue en v7), así que la imagen de la Fase A puede abrir la base restaurada sin renombrarla.

| Pieza | Dónde |
|---|---|
| Imagen de la Fase A | etiqueta `job-tracker:faseA` |
| Base anterior al despliegue | `/datos/ofertas_pre_soporte_20261013.db` en el volumen y copia en `respaldos\`, sha256 `027a0ea92023ee9a7314a82b60f833d8ae2d97af472b80c43dedd708649c918e` |

Los pasos son los mismos de arriba, cambiando tres cosas:

- en el paso 2, el archivo es `ofertas_pre_soporte_20261013.db`, el sha256 es el de esta tabla y el prefijo de la base
  apartada es `retirada_soporte_` en vez de `retirada_faseA_`;
- en el paso 3, la imagen es `job-tracker:faseA` (`docker tag job-tracker:faseA job-tracker-jobtracker:latest`);
- en el paso 4, la versión esperada es **7** (no 6) y los números son los del momento del despliegue: 1123 ofertas,
  5 corridas, 11 postuladas.

Probado sobre una copia: la base restaurada queda idéntica (todas las filas y columnas) a la de antes del despliegue y
la página vuelve a ser la de la Fase A (sin el interruptor de soporte). Lo hecho después del despliegue (estados, notas,
el ajuste del interruptor) queda en la base apartada `retirada_soporte_*`.
