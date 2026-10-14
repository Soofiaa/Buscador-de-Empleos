# Notas del proyecto: decisiones y hallazgos

## Graphify (probado el 13-10-2026 en una copia; NO se usa en job-tracker)

Probado con graphifyy 0.9.53 (`graphify update`, solo AST, sin LLM ni red), sobre una copia fuera de OneDrive. Decisión: no activarlo aquí.

- No ve el SQL embebido en los textos ni las clases definidas dentro de funciones (el `Handler` de `servidor.py`). Por eso omitió 3 de los 4 escritores de estado, fase y fecha, y casi todas las rutas que llegan a `conectar()`.
- De sus 21 aristas inferidas, 8 eran falsas: confundió el módulo `buscar` con la función `getonboard.buscar`.
- El hook post-commit suma unos 1,4 s a cada commit. Si una reconstrucción falla, el grafo queda desactualizado sin avisar hasta un `graphify update .` manual.
- `hook install` escribe en `.gitattributes`, que está versionado.
- grep resultó más rápido y más completo para este proyecto (33 archivos).

## Historial de estados (Fase C)

- `historial_estados` es aditiva: la base sigue en v7, y volver atrás es solo cambiar la imagen
  (ver `REVERSION_FASE_A.md`).
- **Solo `_cambiar_seguimiento()` escribe estado, fase y fecha_postulacion.** `tests/test_fase_c1.py` escanea el código
  y falla si aparece otra escritura.
  - `unir_bases.unir` está exenta: fue una herramienta de una vez y se niega a correr si la base ya tiene historial.
- **Cualquier migración futura que reconstruya la tabla `ofertas`** (CREATE nueva + DROP + RENAME) se lleva sus dos
  triggers (`ofertas_url_fija_con_historial` y `ofertas_sin_borrar_con_historial`). Esa migración debe recrearlos en
  su misma transacción con `buscar.DDL_HISTORIAL`. Como red de seguridad, `conectar()` recrea al arrancar los objetos
  que falten, pero entre la migración y el siguiente arranque la base quedaría sin protección.
- Los orígenes están cerrados por un CHECK: tablero, modal, lista, manual y deshacer. Agregar uno obliga a reconstruir
  la tabla y sus triggers.
