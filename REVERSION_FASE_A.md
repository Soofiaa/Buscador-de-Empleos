# Reversión del filtro LinkedIn Senior/Experto (volver a Mid-Senior)

Despliegue del 16-10-2026, commit local `eb3a33e`. No cambia el esquema ni reclasifica ofertas guardadas.

| Pieza | Valor |
|---|---|
| Imagen desplegada | `job-tracker:linkedin-senior-experto`, `sha256:da1024401f2cd33609bf5934a2293ce56873872b633d69c335d0234b9ca31369` |
| Imagen anterior | `job-tracker:linkedin-senior-anterior-20261016`, `sha256:915bc9fd6217faac57431091bf4804844f5119592c15e52c5f989cc677ad6694` |
| Base de referencia | `ofertas_pre_linkedin_senior_experto_20261016.db`, en el volumen y en `C:\Users\sofia\Respaldos\job-tracker-referencias\` |
| SHA-256 de la referencia | `6a43f4cddac9fddbdf66d75a40738f629b9b28457049c4822e87188a83152a83` en ambas copias; `integrity_check=ok` |
| Línea base | SQLite v7; 2046 ofertas, 18 corridas, 77 filas en `historial_estados`, 18 postuladas y 6 POR VERIFICAR |

## Procedimiento

No restaurar la base: este despliegue no la modificó. Para volver a la imagen anterior:

```powershell
docker compose stop jobtracker
docker tag job-tracker:linkedin-senior-anterior-20261016 job-tracker-jobtracker:latest
docker compose up -d --no-build
docker inspect jobtracker --format "{{.State.Health.Status}}"
```

Comprobar GET `/api/estado` y comparar las huellas de `/datos/ofertas.db` con la referencia de la tabla. La base v7
debe conservar todos sus datos, estados, notas y postulaciones. Se pierde únicamente el filtro nuevo para el nivel
LinkedIn `Nivel: Senior` y `Expert/Experto`; los filtros previos permanecen. Un cargo con «Senior» en el título puede
seguir siendo descartado por la regla senior que ya existía.

## Prueba de reversión

Probada con la imagen anterior sobre una copia de la referencia en el volumen temporal
`jt_revision_reversion_linkedin_senior_experto_20261016`, puerto `127.0.0.1:8767`: health `healthy`, GET
`/api/estado` 200, SQLite v7 e `integrity_check=ok`. Las ocho tablas, sus conteos y SHA-256, las postuladas, POR
VERIFICAR y estados coincidieron con la referencia. El contenedor y volumen temporales se eliminaron.

---

# Reversión de la Fase A (volver a la Fase 0)

La Fase A migra la base de la versión 6 a la 7 al arrancar. **El código de la Fase 0 trata una base v7 como "versión
desconocida" y la renombra a `ofertas_antigua_*.db`**, así que para volver atrás NO basta con levantar la imagen
anterior: hay que restaurar también la base respaldada antes del despliegue.

Piezas que deben existir antes de desplegar la Fase A:

| Pieza | Dónde | Cómo se comprueba |
|---|---|---|
| Imagen de la Fase 0 | etiqueta `job-tracker:fase0` | `docker image inspect job-tracker:fase0` |
| Base anterior a la migración | `/datos/ofertas_pre_faseA_20261013.db` en el volumen `job-tracker_jt_datos`; copia fuera de OneDrive en `C:\Users\sofia\Respaldos\job-tracker-referencias\ofertas_pre_fase0_20261013.db` (mismo archivo: pre_faseA = pre_fase0) | sha256 `a3d914a29dd03616ebb13c38ef22ac300e8cb4328c9661747c9dd453d9ae096d` + `PRAGMA integrity_check` = ok |

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
| Base anterior al despliegue | `/datos/ofertas_pre_soporte_20261013.db` en el volumen y copia en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, sha256 `027a0ea92023ee9a7314a82b60f833d8ae2d97af472b80c43dedd708649c918e` |

Los pasos son los mismos de arriba, cambiando tres cosas:

- en el paso 2, el archivo es `ofertas_pre_soporte_20261013.db`, el sha256 es el de esta tabla y el prefijo de la base
  apartada es `retirada_soporte_` en vez de `retirada_faseA_`;
- en el paso 3, la imagen es `job-tracker:faseA` (`docker tag job-tracker:faseA job-tracker-jobtracker:latest`);
- en el paso 4, la versión esperada es **7** (no 6) y los números son los del momento del despliegue: 1123 ofertas,
  5 corridas, 11 postuladas.

Probado sobre una copia: la base restaurada queda idéntica (todas las filas y columnas) a la de antes del despliegue y
la página vuelve a ser la de la Fase A (sin el interruptor de soporte). Lo hecho después del despliegue (estados, notas,
el ajuste del interruptor) queda en la base apartada `retirada_soporte_*`.

---

# Reversión de formas de género y "analista de automatización" (volver a SAP / Soporte)

Despliegue del 13-10-2026 (commit `3fbaed0`, reclasificación dirigida `--regla genero-automatizacion`: 9 ofertas). No
cambia el esquema (v7). Mismo procedimiento de arriba, con:

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:soporte` (`docker tag job-tracker:soporte job-tracker-jobtracker:latest`) |
| Base anterior | `ofertas_pre_genero_20261013.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `405a0e02aeaf4fbb943d37f5ad9a16586744ba7685e033242c789c4202ec1ad2` |
| Prefijo de la base apartada | `retirada_genero_` |
| Verificación | versión 7; al desplegar había 1123 ofertas, 5 corridas, 11 postuladas |

Igual que antes, lo hecho en la página después del despliegue queda solo en la base apartada.

---

# Reversión de la Fase B1 (postulación manual y exportar)

Despliegue del 13-10-2026 (commit `3844a39`). No cambia el esquema (v7) ni reclasifica nada: al desplegar, la base quedó
idéntica en todas sus tablas. Mismo procedimiento de arriba, con:

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:genero` (`docker tag job-tracker:genero job-tracker-jobtracker:latest`) |
| Base anterior | `ofertas_pre_B1_20261013.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `c000a4696dde9dbe509a85d727b39c03f7e0466323b39bc9e865d6620bb82ade` |
| Prefijo de la base apartada | `retirada_B1_` |
| Verificación | versión 7; al desplegar había 1123 ofertas, 5 corridas, 14 postuladas |

Como la B1 no cambia datos existentes, también se puede volver solo con la imagen (`docker tag` + `compose up --no-build`)
y conservar la base actual: las postulaciones manuales que hayas creado siguen ahí, con tipo "M: Manual", y la imagen
anterior las muestra como cualquier otra oferta principal (sin el botón para crear nuevas).

---

# Respaldo automático (despliegue del 13-10-2026, commits `68d6ce6` y `55757e7`)

Los respaldos quedan en **`C:\Users\sofia\Respaldos\job-tracker\`** (fuera de OneDrive), montada en `/respaldos`:
`ofertas_auto_AAAAMMDD-HHMMSS.db` (uno por día, se guardan los últimos 30) y `ofertas_manual_…db` (botón
"💾 Respaldar ahora", nunca se borran solos), cada uno con su `.sha256`.

## (a) Volver a la imagen anterior (sin respaldo automático)

Este despliegue no cambió la base (todas las tablas quedaron idénticas), así que basta con la imagen:

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:B1` |
| Base anterior (por si acaso) | `ofertas_pre_respaldo_20261013.db` (volumen; fuera de OneDrive está como `C:\Users\sofia\Respaldos\job-tracker-referencias\ofertas_pre_B1_20261013.db`, mismo archivo), sha256 `c000a4696dde9dbe509a85d727b39c03f7e0466323b39bc9e865d6620bb82ade` |

```
docker compose stop jobtracker
docker tag job-tracker:B1 job-tracker-jobtracker:latest
docker compose up -d --no-build
```

La imagen B1 ignora `JT_RESPALDOS` y el montaje: simplemente deja de hacer respaldos. Los que ya están en la carpeta
no se tocan.

## (b) Restaurar un respaldo, paso a paso

Úsalo si la base se dañó o si quieres volver a un día anterior. Lo hecho después de ese respaldo se pierde de la base
activa, pero queda en la base apartada (`retirada_restauracion_*`).

1. **Elegir el respaldo** en `C:\Users\sofia\Respaldos\job-tracker\` y verificarlo (Git Bash):

   ```
   cd /c/Users/sofia/Respaldos/job-tracker
   sha256sum -c ofertas_auto_AAAAMMDD-HHMMSS.db.sha256          # debe decir OK
   ```

2. **Detener** el contenedor (nunca `down -v`):

   ```
   docker compose stop jobtracker
   ```

3. **Copiar el respaldo al volumen**, apartando la base actual (no se borra) y verificando el sha256 dentro del volumen
   (reemplaza `ARCHIVO` por el nombre elegido):

   ```
   ARCHIVO=ofertas_auto_AAAAMMDD-HHMMSS.db
   SHA=$(cut -c1-64 /c/Users/sofia/Respaldos/job-tracker/$ARCHIVO.sha256)
   MSYS_NO_PATHCONV=1 docker run --rm --network none -v job-tracker_jt_datos:/datos \
     -v "C:\Users\sofia\Respaldos\job-tracker":/src:ro ubuntu:latest sh -ec "
       cd /datos
       sello=\$(date +%Y%m%d-%H%M%S)
       for f in ofertas.db ofertas.db-wal ofertas.db-shm; do [ -e \"\$f\" ] && mv \"\$f\" \"retirada_restauracion_\${sello}_\$f\"; done
       cp /src/$ARCHIVO ofertas.db
       test \"\$(sha256sum ofertas.db | cut -c1-64)\" = $SHA
       chown root:root ofertas.db && chmod 0644 ofertas.db
       ls -1"
   ```

   Si el `test` del sha256 falla, el comando se detiene: no levantes el contenedor y avísame.

4. **Levantar** y esperar a que quede sano:

   ```
   docker compose up -d --no-build
   docker inspect jobtracker --format "{{.State.Health.Status}}"      # healthy (puede tardar ~1 minuto)
   ```

5. **Comprobar los conteos** (deben coincidir con los del día del respaldo):

   ```
   docker exec jobtracker python -c "import sqlite3; c=sqlite3.connect('file:/datos/ofertas.db?mode=ro',uri=True); q=lambda s: c.execute(s).fetchone()[0]; print('versión', q('pragma user_version'), '| integridad', q('pragma integrity_check'), '| ofertas', q('select count(*) from ofertas'), '| corridas', q('select count(*) from corridas'), '| postuladas', q(\"select count(*) from ofertas where estado='postulada'\"))"
   ```

   Y en la página (`http://127.0.0.1:8765/`, Ctrl+F5): el pie "SQLite Conectado · N ofertas" y Seguimiento.

Probado sobre una copia (volumen temporal) con el primer respaldo automático, `ofertas_auto_20261013-182831.db`.

# Fase C1 + historial de estados + fecha editable (despliegue del 13-10-2026, commit `b2a4c07`)

Qué cambia:
- `/api/marcar` escribe estado y fase juntos y exige `origen` (tablero, lista o modal).
- `/api/nota` ya no acepta estado ni fase, y la fecha de postulación no puede ser futura.
- La tabla `historial_estados` es **aditiva**: la base sigue en v7, así que la imagen anterior la abre igual y solo la
  ignora.

## (a) Volver a la imagen anterior (sin historial)

Basta con la imagen: **la base no se restaura** y no se pierde nada de lo hecho en la página.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:respaldo` (`sha256:ac00ce130d5460e89713e5e0021786691d48d6685d41ba2f6b7d34bacc27c610`) |
| Imagen desplegada | `job-tracker-jobtracker:latest` (`sha256:c461ada148c73309630793675c8b4c7b5e46777a99c4570df57f9b8e8fc6935f`) |
| Base anterior (por si acaso) | `ofertas_pre_historial_20261013.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\ofertas_pre_historial_20261013.db`), sha256 `e1f849f6932b2caa477f9b40f9e97984e1f80f89f6c6f127c98a869c02f38da5` |

Probado sobre una copia de la base ya desplegada: la imagen `job-tracker:respaldo` la abrió sin renombrarla (v7,
integridad ok, los 6 objetos del historial intactos) y sus escrituras funcionaron, sin quedar en el historial.

```
docker compose stop jobtracker
docker tag job-tracker:respaldo job-tracker-jobtracker:latest
docker compose up -d --no-build
```

**Qué se pierde mientras corra la imagen anterior:**
- Los cambios de estado, fase y fecha **no se registran** en el historial. Quedan huecos, y no se rellenan después,
  para no inventar datos.
- Al volver a la imagen nueva, el historial sigue desde ahí. En una oferta con hueco, "días en la fase" no se inventa:
  se usan los días desde la postulación o no se muestra nada.

La tabla, el índice y los 4 triggers se quedan en la base. Los triggers no molestan al código anterior: nunca cambia la
url de una oferta ni borra ofertas, como se comprobó con la imagen v7 real sobre una copia del respaldo.

## (b) Borrar A PROPÓSITO una oferta que tiene historial (p. ej. una manual creada por error)

Los triggers lo impiden a propósito: así ningún error deja filas huérfanas. Para un borrado consciente, hay que
desactivarlos de forma controlada, **dentro de una transacción**. En SQLite, `DROP TRIGGER` también es transaccional:
si algo falla, todo vuelve atrás y los triggers siguen ahí. No está automatizado a propósito.

1. **Respaldo previo:** "💾 Respaldar ahora" en la página. Anota el archivo y verifica su `.sha256` con el paso 1 de
   la sección "Restaurar un respaldo".
2. **Copia la url exacta** de la oferta (Exportar → CSV, columna `url`; las manuales sin URL empiezan con `manual:`).
3. **Detén el contenedor:** `docker compose stop jobtracker`.
4. **Borra** en un contenedor desechable, sin red. Reemplaza `URL_A_BORRAR`:

   ```
   MSYS_NO_PATHCONV=1 docker run --rm --network none -v job-tracker_jt_datos:/datos --entrypoint python \
     job-tracker-jobtracker -c "
   import sqlite3, sys
   sys.path.insert(0, '/app'); import buscar
   URL = 'URL_A_BORRAR'
   con = sqlite3.connect('/datos/ofertas.db', isolation_level=None)
   con.execute('BEGIN IMMEDIATE')
   try:
       f = con.execute('SELECT titulo, empresa, estado FROM ofertas WHERE url = ?', (URL,)).fetchone()
       assert f, 'esa url no existe: no se borró nada'
       print('Se borra:', f)
       con.execute('DROP TRIGGER ofertas_sin_borrar_con_historial')
       con.execute('DROP TRIGGER historial_sin_delete')
       h = con.execute('DELETE FROM historial_estados WHERE url = ?', (URL,)).rowcount
       con.execute('DELETE FROM alertas WHERE url = ?', (URL,))
       o = con.execute('DELETE FROM ofertas WHERE url = ?', (URL,)).rowcount
       con.execute(buscar.DDL_HISTORIAL['historial_sin_delete'])
       con.execute(buscar.DDL_HISTORIAL['ofertas_sin_borrar_con_historial'])
       assert o == 1
       con.execute('COMMIT')
   except BaseException:
       con.execute('ROLLBACK'); print('ROLLBACK: no se borró nada'); raise
   faltan = [n for n in buscar.DDL_HISTORIAL if not con.execute('SELECT 1 FROM sqlite_master WHERE name = ?', (n,)).fetchone()]
   print('borrada: 1 oferta,', h, 'filas de historial | triggers que faltan:', faltan or 'ninguno',
         '| integridad', con.execute('PRAGMA integrity_check').fetchone()[0])
   "
   ```

   Debe terminar con "triggers que faltan: ninguno" e "integridad ok". Aunque faltara alguno, `conectar()` recrea al
   arrancar los objetos que falten.
5. **Levanta:** `docker compose up -d --no-build`, y comprueba en la página que la oferta ya no está.

# Fase C2: tablero de Seguimiento (despliegue del 13-10-2026, commit `7a16eef`)

Qué cambia: solo la página (`web/pagina.html`). El tablero "📊 Tablero / 📋 Lista" en Seguimiento, con las mismas
escrituras de siempre (`/api/marcar` con `origen: "tablero"`). El servidor, el esquema y la base no cambian.

## Volver a la imagen anterior (sin tablero)

Basta con la imagen: **la base no se restaura** y no se pierde nada de lo hecho en la página. Las filas de historial
con origen `tablero` se quedan; la imagen de C1 ya acepta ese origen.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:c1` (`sha256:c461ada148c73309630793675c8b4c7b5e46777a99c4570df57f9b8e8fc6935f`) |
| Imagen desplegada | `job-tracker:c2-candidata` = `job-tracker-jobtracker:latest` (`sha256:f1943914dee8b150c76e69973d65124cc7f0d7c76fa3f6df3c53c010e7203180`), sin reconstruir |
| Base anterior (por si acaso) | `ofertas_pre_c2_20261013.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker\`), sha256 `309228dd26ea1610e7160065e5fe624b9e578d0dc2bcd9ae32461a95be05a16d` |

```
docker compose stop jobtracker
docker tag job-tracker:c1 job-tracker-jobtracker:latest
docker compose up -d --no-build
```

Probado sobre una copia de la referencia en un volumen temporal: la imagen `job-tracker:c1` quedó healthy, `GET /`
respondió 200 sin el tablero, y las huellas de la base fueron idénticas a la referencia. El volumen se borró.

**Qué se pierde mientras corra la imagen anterior:** solo la vista de tablero (Seguimiento vuelve a la lista). Lo
guardado en el navegador (`vistaSeguimiento`) se ignora y se vuelve a usar al regresar a C2.

# Código 137 + respaldos atómicos + «informático junior» (despliegue del 14-10-2026, commits `6660133`, `9561c19` y `a7339c1`)

Qué cambia: `servidor.py` (SIGTERM → cierre ordenado: espera un respaldo en curso y hace el checkpoint del -wal con
límite), `respaldo.py` (el `.sha256` se escribe al final y de forma atómica; un `.db` sin `.sha256` es «incompleto» y
se informa), `web/pagina.html` (aviso de incompletos), `docker-compose.yml` (`stop_grace_period: 15s`) y
`config.py`/`filtros.py` (término «informático junior» y regla de último recurso A: TI, Baja). El esquema no cambia
(v7, sin tablas ni triggers nuevos).

## Volver a la imagen anterior

Basta con la imagen: **la base no se restaura**. Los respaldos hechos con el código nuevo (`.db` + `.sha256`) son los
mismos archivos que entiende la imagen anterior.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:c2` = `job-tracker:c2-candidata` (`sha256:f1943914dee8b150c76e69973d65124cc7f0d7c76fa3f6df3c53c010e7203180`) |
| Imagen desplegada | `job-tracker:137-respaldo-candidata` = `job-tracker-jobtracker:latest` (`sha256:ff5a2615845e1b7a57719015697166e31c319972ce6efbb3e3ac99809b1bbc3f`), sin reconstruir |
| Base anterior (por si acaso) | `ofertas_pre_137_20261014.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker\`), sha256 `f42673e5451fd53891c4281fa9f0b67b0340f1ed3f846f933922bac209dbb1ec` |

```
docker compose stop jobtracker
docker tag job-tracker:c2 job-tracker-jobtracker:latest
docker compose up -d --no-build
```

Probado sobre una copia de la referencia en un volumen temporal (`jt_reversion_prueba`, 127.0.0.1:8767): la imagen
`job-tracker:c2` quedó healthy, `GET /` respondió 200 y las huellas de la base fueron idénticas a la referencia. El
contenedor y el volumen se borraron.

**Qué se pierde mientras corra la imagen anterior:** el cierre ordenado (cada `stop` vuelve a terminar con 137, ahora
tras 15 s por el `stop_grace_period`, que se queda en el compose), el `.sha256` atómico y el aviso de incompletos, y el
término «informático junior» con su regla (las ofertas ya clasificadas así se quedan como están).

# Telemetría pasiva + orden de respaldos + nombres de respaldo (despliegue del 15-10-2026, 18:53; código de `f9cef86`)

Qué cambia: `buscar.py`, `getonboard.py`, `red.py`, `robots.py` y `telemetria.py` (nuevo): contadores por fuente en
`corridas.detalle.fuentes[i].telemetria` y una línea `[corrida]` en stderr (`e754ff6`); `respaldo.py`: «Último
respaldo» por la fecha del nombre (`09409f3`) y los nombres fuera de `ofertas_(auto|manual)_AAAAMMDD-HHMMSS.db` se
ignoran (`481aab7`). Sin DDL: la base sigue en v7, sin tablas, índices ni triggers nuevos, y no se reclasifica nada.

## Volver a la imagen anterior

Basta con la imagen: **la base no se restaura**. Las corridas nuevas guardan la clave `telemetria` en su detalle; la
imagen anterior la ignora (la página no la lee). Los respaldos tienen el mismo formato en las dos imágenes.

| Pieza | Valor |
|---|---|
| Imagen anterior (etiqueta estable, 15-10-2026) | `job-tracker:137` = `job-tracker:137-respaldo-candidata` (`sha256:ff5a2615845e1b7a57719015697166e31c319972ce6efbb3e3ac99809b1bbc3f`) |
| Imagen desplegada | `job-tracker:telemetria-candidata` = `job-tracker-jobtracker:latest` (`sha256:ad7b2b19ced76563f80620cceca3a5ea29f1896991edfa3ff1ca3ced64389683`), construida desde la carpeta de trabajo limpia en `f9cef86` y desplegada sin reconstruir (`docker tag` + `docker compose up -d --no-build`) |
| Base anterior (referencia oficial, por si acaso) | `ofertas_pre_telemetria_20261015.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `844341c7d2bc057f79b42e117e065f18910083249e8afb2c5ac34e06ed8b87b2`, integrity_check ok; tomada con el contenedor detenido (salida 0) |

```
docker compose stop jobtracker
docker tag job-tracker:137 job-tracker-jobtracker:latest
docker compose up -d --no-build
```

Probado el 15-10-2026 (etapa 1): la imagen `job-tracker:137` levantada con `docker run` sobre una copia de la
referencia (`jt_revision_telemetria_rev`, 127.0.0.1:8767) quedó healthy; `/`, `/api/estado`, `/api/ofertas`,
`/api/respaldo` y `/api/exportar` respondieron 200, los conteos de la API coincidieron con la copia y las huellas
por tabla fueron idénticas antes y después. **Los tres comandos de arriba (con `docker compose`) siguen sin
probarse:** el despliegue del 15-10 usó la misma forma (`docker tag` + `docker compose up -d --no-build`) en el
sentido contrario, pero la vuelta atrás en sí no se ha ejecutado. El contenedor y los volúmenes de la prueba
(`jt_revision_telemetria_rev`) quedaron detenidos, sin borrar, a la espera de la limpieza.

**Qué se pierde mientras corra la imagen anterior:** la telemetría de las corridas nuevas (las ya guardadas conservan
su clave), el orden de «Último respaldo» (vuelve a mostrar primero el manual más reciente aunque haya un automático más
nuevo) y el filtro de nombres de respaldo fuera de formato.

# LinkedIn (portal público sin cuenta) + Contadores por ubicación (despliegue del 15-10-2026, 23:45; código de `62dc59d`)

Qué cambia: `linkedin.py` (nuevo portal), `config.py` (SITIOS, NOMBRE_FUENTE, TERMINOS_LINKEDIN), `buscar.py` (PORTALES),
`web/pagina.html` (NOMBRE_FUENTE) y telemetría por ubicación. Sin DDL: la base sigue en v7, sin tablas nuevas.

## Volver a la imagen anterior

Basta con la imagen: **la base no se restaura**.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:telemetria` (`sha256:ad7b2b19ced76563f80620cceca3a5ea29f1896991edfa3ff1ca3ced64389683`) |
| Imagen desplegada | `job-tracker-jobtracker:latest` (`sha256:22c86fa2872dad7cb9f7d4a7ab27539e6f79e3b0c552fa69fe6f549e5440a83c`) |
| Base anterior (referencia, por si acaso) | `ofertas_pre_linkedin_20261015.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `dce49a107791bc8c2a65b5d382cfab1e43d8341fa507cd73ebcfc823440e895d`, integrity_check ok |

```
docker compose stop jobtracker
docker tag job-tracker:telemetria job-tracker-jobtracker:latest
docker compose up -d --no-build
```

**Qué se pierde mientras corra la imagen anterior:** la recopilación de ofertas de LinkedIn y los contadores por ubicación.

# Filtro de LinkedIn y exclusión de BairesDev (despliegue del 16-10-2026; commit `23241ba`)

La base no cambia de esquema ni se reclasifica durante el despliegue; para volver atrás basta con usar la imagen
anterior y **no restaurar la base**.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:linkedin-229f` (`sha256:d4529c349a47a830c421a161b64dd58cf31ce47486e7f9104e4eb7d16d5f5c1a`) |
| Imagen desplegada | `job-tracker:linkedin-filtros` = `job-tracker-jobtracker:latest` (`sha256:d4d6b5347f13f5ced733f060f8ba3dad81f6ce2830f53714b4359eac6f8a45d9`) |
| Referencia de la base | `ofertas_pre_linkedin_filtros_20261016.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `e3856c8346f07a065c8bc65213d2aa674049012d38d01e78c65ba2e35ebc0dd3`, integrity_check `ok` |

```
docker compose stop jobtracker
docker tag job-tracker:linkedin-229f job-tracker-jobtracker:latest
docker compose up -d --no-build
```

Probado con la imagen anterior en `jt_revision_linkedin_reversion` (127.0.0.1:8767), sobre una copia de la referencia:
quedó healthy; `/api/estado`, `/api/ofertas` y `/api/respaldo` respondieron 200; la versión, integrity_check, postuladas,
POR VERIFICAR, objetos del esquema y las huellas de las ocho tablas coincidieron con la referencia.

**Qué se pierde mientras corra la imagen anterior:** la restricción de LinkedIn a Santiago, Viña del Mar y Valparaíso
(o remoto internacional), el límite de hasta 2 años, el criterio de antigüedad (Associate se acepta y Mid-Senior se
descarta) y la exclusión de BairesDev. No se pierden ni se reclasifican ofertas ya guardadas; futuras búsquedas
vuelven a usar los filtros de la imagen anterior.

# Rechazar nivel Mid-Senior en LinkedIn (despliegue del 16-10-2026; commit `a245ece`)

Qué cambia: se descartan ofertas de LinkedIn que indiquen nivel Mid-Senior; Associate sigue aceptándose. Sin cambios
de esquema ni reclasificación de ofertas existentes: para volver atrás basta con usar la imagen anterior y **no
restaurar la base**.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:linkedin-filtros-23241` (`sha256:d4d6b5347f13f5ced733f060f8ba3dad81f6ce2830f53714b4359eac6f8a45d9`) |
| Imagen desplegada | `job-tracker:linkedin-mid-senior` = `job-tracker-jobtracker:latest` (`sha256:915bc9fd6217faac57431091bf4804844f5119592c15e52c5f989cc677ad6694`) |
| Referencia de la base | `ofertas_pre_mid_senior_20261016.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `e3856c8346f07a065c8bc65213d2aa674049012d38d01e78c65ba2e35ebc0dd3`, integrity_check `ok` |

```
docker compose stop jobtracker
docker tag job-tracker:linkedin-filtros-23241 job-tracker-jobtracker:latest
docker compose up -d --no-build
```

Probado sobre una copia de la referencia en un volumen temporal: la imagen anterior quedó healthy; `/`,
`/api/estado`, `/api/ofertas` y `/api/respaldo` respondieron 200; las huellas de las ocho tablas y los conteos
coincidieron con la referencia. El contenedor y volumen temporales se borraron.

**Qué se pierde mientras corra la imagen anterior:** la regla que descarta explícitamente nivel Mid-Senior. No se
pierden ni se reclasifican ofertas guardadas; Associate y los demás filtros de LinkedIn de la imagen anterior
permanecen.

# Chumi, Laborum (Playwright) y regla de experiencia (despliegue del 20-10-2026; commit `e8abeee`)

Qué cambia: Chumi y Laborum entran a `SITIOS` (Laborum con Chromium sin ventana: la imagen pasa de 484 MB a ~1,6 GB);
se borran Computrabajo, Buscojobs, Empleos Públicos y EmpleosTech (rechazan a la app o no existen); un portal que falla
ya no corta la corrida; las antiguas cuya fecha llega con el detalle no se guardan; regla de experiencia en todas las
fuentes («hasta N» = 0 a N); sección «Buscar a mano» en la página. Sin cambios de esquema ni reclasificación: para
volver atrás basta con usar la imagen anterior y **no restaurar la base**.

La imagen anterior NO es la de `linkedin-senior-experto`: el 19-10 a las 20:45 se reconstruyó y desplegó fuera del
procedimiento una versión intermedia (hasta `326f427`, con Computrabajo, Laborum y Buscojobs rotos). Es la que se
etiquetó aquí.

| Pieza | Valor |
|---|---|
| Imagen anterior | `job-tracker:pre-laborum-20261020` (`sha256:6353e0b5950fb12634c0dc720d6d315c922e01591c99a44273111872ad27b707`; desplegada el 19-10 sin registro) |
| Imagen desplegada | `job-tracker:laborum` = `job-tracker-jobtracker:latest` (`sha256:39378b0be7aaf453732037cb27fa6caad93ae7d9f6c99d5d739cc7e05315a5d3`) |
| Referencia de la base | `ofertas_pre_laborum_20261020.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256 `c40c50f5a99b1450f86bc260e7a2c33b7ba5f28f64b891cfd3edd5909130b472`, integrity_check `ok` |

```
docker compose stop jobtracker
docker tag job-tracker:pre-laborum-20261020 job-tracker-jobtracker:latest
docker compose up -d --no-build
```

Probado sobre una copia de la referencia en un volumen temporal (8767): la imagen anterior quedó healthy; `/`,
`/api/estado`, `/api/ofertas` y `/api/respaldo` respondieron 200; las huellas completas coincidieron con la referencia.
El contenedor y el volumen temporales se borraron.

**Qué se pierde mientras corra la imagen anterior:** Chumi, Laborum, la sección «Buscar a mano», el aislamiento de un
portal que falla y la regla «hasta N años». Vuelven los intentos contra Computrabajo, Laborum y Buscojobs (se detienen
solos por 403 o por errores). No se pierden ni se reclasifican ofertas guardadas.