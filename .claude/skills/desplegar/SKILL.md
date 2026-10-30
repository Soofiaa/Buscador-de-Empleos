---
name: desplegar
description: Procedimiento estándar para desplegar en el contenedor real de job-tracker una versión ya aprobada.
disable-model-invocation: true
argument-hint: <etiqueta-imagen-actual> <nombre-referencia> [tablas-nuevas]   (ej.: respaldo historial historial_estados)
---

# Despliegue estándar de job-tracker

Solo con aprobación EXPLÍCITA de Sofia en el chat para ESTE despliegue. Si falta, detenerse y preguntar.
Argumentos: $ARGUMENTS -> ETIQUETA (para la imagen actual), NOMBRE (ofertas_pre_<NOMBRE>_<AAAAMMDD>.db) y, si el
despliegue crea tablas, su lista separada por comas (NUEVAS). Todo desde `job-tracker/`, en Git Bash.
Script de huellas: `.claude/skills/desplegar/huellas.py` (solo lectura, solo biblioteca estándar).

## 0. Precondiciones (si una falla, detenerse)
- Candidata revisada y aprobada por Sofia.
- `venv/Scripts/python.exe -m pytest -q` en verde (mostrar solo el resumen y los fallos).
- Commit hecho y `git status` sin cambios del despliegue.
- sha256 de TODOS los respaldos anteriores (`C:/Users/sofia/Respaldos/job-tracker-referencias`, volumen y
  `C:/Users/sofia/Respaldos/job-tracker`), guardado para compararlo al final.

## 1. Etiquetar la imagen actual
    docker tag job-tracker-jobtracker:latest job-tracker:<ETIQUETA>

## 2. Detener el contenedor ANTES de la referencia
    docker compose stop jobtracker            # nunca `down -v`
    docker inspect jobtracker --format '{{.State.ExitCode}}'
Anotar el código de salida. Si es 137 (Docker lo cortó con SIGKILL), el integrity_check del paso 3 es obligatorio
antes de seguir, y el 137 va en el reporte.

## 3. Referencia: respaldo con sha256 e integrity_check
En un contenedor desechable sin red (`--network none`, imagen `job-tracker:<ETIQUETA>`), con la API de backup de
SQLite: `/datos/ofertas_pre_<NOMBRE>_<AAAAMMDD>.db` en el volumen, en `PRAGMA journal_mode = DELETE` (un solo
archivo), y una copia en `C:/Users/sofia/Respaldos/job-tracker-referencias/` (fuera de OneDrive; nunca en
`respaldos\` del repo, que queda vacía). Mostrar el sha256 COMPLETO de ambas (deben coincidir) y el integrity_check.
Si no es `ok`: detenerse, volver a levantar la imagen <ETIQUETA> y avisar.

## 4. Huellas ANTES
    python .claude/skills/desplegar/huellas.py \
        C:/Users/sofia/Respaldos/job-tracker-referencias/ofertas_pre_<NOMBRE>_<AAAAMMDD>.db > <tmp>/antes.json

## 5. Reconstruir y levantar
    docker compose build && docker compose up -d
Esperar `healthy` (`docker inspect jobtracker --format '{{.State.Health.Status}}'`).

## 6. Huellas DESPUÉS y comparación
Copiar huellas.py al contenedor y leer la base real en solo lectura:
    docker cp .claude/skills/desplegar/huellas.py jobtracker:/tmp/huellas.py
    docker exec jobtracker python /tmp/huellas.py /datos/ofertas.db > <tmp>/despues.json
    python .claude/skills/desplegar/huellas.py --comparar <tmp>/antes.json <tmp>/despues.json --nuevas <NUEVAS>
Mostrar la tabla COMPLETA. Si el resultado no es OK (una tabla anterior cambió, falta un objeto, aparece una tabla
no declarada, o cambian versión, integrity_check, postuladas o POR VERIFICAR): DETENERSE, volver a la imagen
<ETIQUETA> y avisar. No "arreglar" en caliente.

## 7. Comprobar sin escribir
- GET `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo` -> 200; con Host u Origin ajeno -> 403.
- Solo POST que DEBEN ser rechazados (400, 403 o 413) antes de tocar la base: origen inválido o ausente, campos no
  permitidos, Origin ajeno, cuerpo demasiado grande. Ninguno que pueda modificar datos.
- Repetir el paso 6 (sin `--nuevas` contra `despues.json`) para demostrar que la base no cambió.
- Respaldo automático: `GET /api/respaldo` sin `error_auto`; que el código nuevo sepa respaldar (en la candidata).

## 8. Reversión documentada y probada
- Agregar a `REVERSION_FASE_A.md`: la imagen anterior (<ETIQUETA> y su id), la imagen desplegada, la referencia con
  su sha256 completo y qué se pierde al volver.
- Probar la reversión tal como quedó escrita, sobre una copia en un volumen temporal; luego borrarlo.
- Confirmar que los respaldos anteriores siguen intactos (mismos sha256 del paso 0).
- Actualizar "Estado actual" en `NOTAS.md`. Commit y push.

## 9. Limpieza
Borrar el contenedor y el volumen de la candidata y las copias temporales; listar para confirmar que no quedan.

## Reporte
Resultado, la tabla antes/después COMPLETA (conteos, sha256, integrity_check, lista de tablas, código de salida al
detener) y las preguntas abiertas. Sin recapitular los pasos.
