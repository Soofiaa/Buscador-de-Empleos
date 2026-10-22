# Reversión de la interfaz (puntos 1 a 7 de la revisión de la página)

Despliegue del 22-10-2026, commit `00b5312` (`main`). Solo cambia la página (`web/pagina.html`) y las pruebas que la leen.
No cambia el esquema ni reclasifica ofertas guardadas.

| Pieza | Valor |
|---|---|
| Imagen desplegada | `job-tracker-jobtracker:latest`, `sha256:7edd2576c6894c2c3f30cfe873eec019b26ebf2e4af57ab8c44187412f8aa40a` |
| Imagen anterior | `job-tracker:pre-interfaz-20261022`, `sha256:76bb6cb17d745056b3ae5d70a69ea0037972bdf836a9920edfb2d79ac952a2bf` (la que estaba en producción; también `job-tracker:pausa-jobspy`) |
| Base de referencia | `ofertas_pre_interfaz_20261022.db`, en `C:\Users\sofia\Respaldos\job-tracker-referencias\` |
| SHA-256 de la referencia | `0F226768536D30B288FACD7147A67830D0BAF5E2823D97B45D42D89A59A5D39C`; `integrity_check=ok` |
| Línea base | SQLite v7; 4193 ofertas, 41 corridas, 275 filas en `historial_estados`, 34 postuladas y 6 POR VERIFICAR |

## Qué incluye

- Color de texto de acción separado (`--accion-texto`) y ancho máximo de 1280 px.
- Historial plegado en pantallas de 860 px o menos.
- Filtros secundarios en «Más filtros».
- Tarjetas con datos secundarios tenues y tecnologías al pie.
- Contraste reforzado (WCAG AA) activo por defecto, con interruptor en la columna izquierda.
- Retiro de la maqueta `vista_previa/nueva_interfaz.html` (su historia está en `850f396`).

## Procedimiento

No restaurar la base: este despliegue no la modificó. Para volver a la imagen anterior:

```powershell
docker compose stop jobtracker
docker tag job-tracker:pre-interfaz-20261022 job-tracker-jobtracker:latest
docker compose up -d --no-build
docker inspect jobtracker --format "{{.State.Health.Status}}"
```

Comprobar `GET /api/estado` y comparar las huellas de `/datos/ofertas.db` con la referencia de la tabla. La base v7
debe conservar todos sus datos, estados, notas y postulaciones.

## Qué se pierde al volver

Solo la interfaz nueva: el contraste reforzado, el historial plegado, «Más filtros» y la jerarquía de tarjetas vuelven
a la versión anterior. Los datos no cambian.

## Probado

- Reversión probada sobre una copia en un volumen temporal (`jt_reversion_prueba_datos`), con la imagen anterior en el
  puerto 8767: healthy, `GET /` 200 y huellas idénticas a las de antes (`RESULTADO: OK`). Después se borró.
