# Reversión: pegar descripción en «Sin texto» y regla de oficio no TI

Despliegue del 22-10-2026, commits `9181c66` (pegar descripción) y `3bad360` (oficio técnico no TI). No cambia el
esquema. No reclasifica ofertas guardadas: solo las que se clasifiquen de ahora en adelante, y las que pegues a mano.

| Pieza | Valor |
|---|---|
| Imagen desplegada | `job-tracker-jobtracker:latest` = `sha256:76bb6cb17d745056b3ae5d70a69ea0037972bdf836a9920edfb2d79ac952a2bf` |
| Imagen anterior (reversión inmediata) | `job-tracker:pre-pegar-descripcion-20261022` = `sha256:4c165ddaf6ee8d67824b2efa2534a18b7a80d37e1b800a4dd432e9d010966d29` |
| Imagen anterior (la de producción antes del 22-10 sin registro) | `job-tracker:pausa-jobspy` = `sha256:d40d7a992fc3aab51dc3cfb41a6777c671cef3df9483c64fbbe2a58c33b61fe4` (no es la que corría) |
| Base de referencia | `ofertas_pre_pegar_descripcion_20261022.db`, en el volumen y en `C:\Users\sofia\Respaldos\job-tracker-referencias\` |
| SHA-256 de la referencia | `16772cbbcb18a88fdf1863288379b54a7ae8e199e28bafa4a3e2a826cb26c8c9` en ambas copias; `integrity_check=ok` |
| Línea base | SQLite v7; 4143 ofertas, 40 corridas, 269 filas en `historial_estados`, 34 postuladas, 6 POR VERIFICAR |

## Procedimiento

No restaurar la base: este despliegue no la modificó. Para volver a la imagen anterior:

```powershell
docker compose stop jobtracker
docker tag job-tracker:pre-pegar-descripcion-20261022 job-tracker-jobtracker:latest
docker compose up -d --no-build
docker inspect jobtracker --format "{{.State.Health.Status}}"
```

Comprobar GET `/api/estado` y las huellas de `/datos/ofertas.db` contra la referencia. Las tablas deben quedar
idénticas. Se pierde únicamente la función de pegar descripción y la regla de oficio no TI; las ofertas que se
guardaron con ellas conservan su clasificación.

## Verificación del despliegue

- Huellas antes y después: las 8 tablas idénticas (`ofertas` 4143 filas, `historial_estados` 269, `corridas` 40).
- `huellas.py --comparar`: RESULTADO OK.
- GET `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo`: 200. Host ajeno: 403. Origin ajeno en POST: 403.
  Campo no permitido en `/api/nota`: 400. Cuerpo de 70 000 bytes en `/api/descripcion`: 413.
- Candidata `jt_revision_pegar_descripcion` (8766): probada con una oferta de Glassdoor sin texto; pasó a
  «descartada» con «exige 3+ años de experiencia»; un segundo envío respondió 400.

## Hallazgo del despliegue

Antes de este despliegue, producción corría `job-tracker-jobtracker:latest` = `4c165dda…` (construida el 22-10 a las
11:55), que contenía el código de «Sin texto» y la regla de experiencia, pero no está registrada en `NOTAS.md`.
Esta reversión la deja como imagen anterior inmediata.
