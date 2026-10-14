# Notas del proyecto: decisiones y hallazgos

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Base real:** v7, integrity_check ok, 1143 ofertas, 6 corridas, 14 postuladas, 6 POR VERIFICAR (notas con
  "POR VERIFICAR").
  - `historial_estados` está vacía, con sus 6 objetos.
  - Estados: descartada/nueva 1081 · principal/descartada 48 · principal/postulada 14.
  - Medido el 13-10-2026 a las 21:50, después del despliegue de C1.
- **Última referencia:** `ofertas_pre_historial_20261013.db` (volumen y `respaldos\`), sha256
  `e1f849f6932b2caa477f9b40f9e97984e1f80f89f6c6f127c98a869c02f38da5`.
- **En producción:** commit `b2a4c07` (C1 + historial + fecha editable), imagen
  `sha256:c461ada148c73309630793675c8b4c7b5e46777a99c4570df57f9b8e8fc6935f`.
- **Imágenes para volver atrás:** `job-tracker:respaldo` (la anterior a C1, `ac00ce13…`), `:B1`, `:genero`, `:soporte`,
  `:faseA`, `:fase0`.
  - Siguen las candidatas viejas `:historial-candidata`, `:respaldo-candidata`, `:faseB1-candidata` y
    `:faseA-candidata`, que se pueden borrar si Sofia lo aprueba.
- **Commits locales sin push:** `b2a4c07` C1 · `65325fe` reversión de C1 · `3c7da28` CLAUDE.md y notas ·
  `c7772ea` skill `/desplegar`, más el de esta sección. Antes de esos, los de las fases anteriores. `main` va adelante
  de `origin`.

### Pendientes
- **Comprobar el respaldo automático** `ofertas_auto_20261014-…`, el primero con el código de C1, en
  `C:\Users\sofia\Respaldos\job-tracker\`: sha256 OK (`sha256sum -c`), integrity_check ok, un solo archivo (journal
  `delete`, sin -wal/-shm) y `historial_estados` incluida con sus 6 objetos.
- **Código 137 al detener el contenedor** (diagnosticado, sin cambiar nada, espera aprobación):
  - Causa: el PID 1 es `python servidor.py`, sin init y sin manejador de SIGTERM (SigCgt = 2 y 33). Linux descarta
    ese SIGTERM y Docker mata el proceso a los 10 s.
  - Arreglo propuesto: `signal.signal(SIGTERM, signal.default_int_handler)` en `servidor.main`, y en el `finally` un
    `PRAGMA wal_checkpoint(TRUNCATE)`.
  - Prueba: un subproceso con `signal.raise_signal(SIGTERM)` debe salir con código 0 en menos de 3 s, con el -wal
    vacío. Al desplegar, `docker compose stop` debe dar 0 en 1–2 s.
- **C2 implementada** (commits `ba9f21c` tablero y `7a16eef` follow-up, 424 pruebas): candidata en 127.0.0.1:8766
  (`jt_revision_c2`, sobre copia), en revisión visual de Sofia. Sin desplegar. Luego C3. B2 (importar) no se hará.

### Reglas comunes de la Fase C
- **Un solo camino de escritura.** Estado y fase van siempre por `/api/marcar` (`pedidoMarcar` en la página), con
  `origen`; `/api/nota` los rechaza con 400.
  - Orígenes del historial: `tablero`, `lista` y `modal` los envía la página. `manual` (alta de una postulación) y
    `deshacer` los fija el servidor; si la página envía otro valor, 400.
- **Cada movimiento** muestra el aviso con "Deshacer" (`pedidoDeshacer`), que restaura exactamente estado, fase y
  fecha. Si la oferta cambió entre medias, 409.
- **La fase nunca baja** desde el tablero. `oferta` solo se marca en "Gestionar proceso", donde bajar la fase es una
  decisión explícita.
- **La fecha de postulación** solo se completa (hoy, hora de Chile) si estaba vacía al entrar a postulada o
  entrevista. Nunca se cambia ni se borra; solo se edita a mano en el modal, y nunca a futuro.

### C2: Kanban (en Seguimiento, selector "📊 Tablero / 📋 Lista" que se recuerda)

**Columnas.** Cada oferta de Seguimiento cae en **exactamente una**, calculada por una función pura con pruebas.
No hay columna de descartadas.

| Columna | Estado | Fase |
|---|---|---|
| **P** 📌 Por postular | revisada | cualquiera |
| **C** ✉️ CV enviado | postulada | cualquiera |
| **E** 🎯 Entrevistas | entrevista | vacía, postulacion, rrhh o tecnica |
| **O** 🏆 Oferta / Cierre | entrevista | final u oferta |

**Qué pasa al soltar en cada columna:**

| Soltar en | Estado | Fase | Fecha |
|---|---|---|---|
| P | revisada | no cambia | no cambia |
| C | postulada | vacía → `postulacion`; si tiene fase, no cambia | hoy, solo si vacía |
| E | entrevista | vacía o postulacion → `rrhh`; rrhh o tecnica → no cambia | hoy, solo si vacía |
| O | entrevista | final u oferta → no cambia; cualquier otra → `final` (nunca `oferta`) | hoy, solo si vacía |

**Los 12 movimientos.** "f" es la fase que tenía la tarjeta.

| Movimiento | Estado | Fase | Fecha |
|---|---|---|---|
| P → C | postulada | `postulacion` si f vacía; si no, f | hoy si vacía |
| P → E | entrevista | `rrhh` si f es vacía o postulacion; si no, f (ver punto abierto) | hoy si vacía |
| P → O | entrevista | `final` (se queda en `oferta` si f era oferta) | hoy si vacía |
| C → E | entrevista | `rrhh` si f es vacía o postulacion; si no, f (ver punto abierto) | hoy si vacía |
| C → O | entrevista | `final` (se queda en `oferta` si f era oferta) | hoy si vacía |
| E → O | entrevista | `final` | hoy si vacía (normalmente ya la tiene) |
| C → P | revisada | f | sin cambio |
| E → P | revisada | f | sin cambio |
| E → C | postulada | `postulacion` si f vacía; si no, f | sin cambio |
| O → P | revisada | f (final u oferta) | sin cambio |
| O → C | postulada | f (final u oferta) | sin cambio |
| O → E | **bloqueado** | — | — |

Soltar en la misma columna no envía ningún pedido.

**Decisiones de C2 (aprobadas por Sofia el 13-10-2026):**
- **Bloqueo con motivo.** O → E, y también P → E y C → E cuando la tarjeta conserva la fase `final` u `oferta` (volvió
  desde O), se bloquean sin enviar nada. El aviso explica el motivo: "No se puede mover a Entrevistas: tiene la fase
  «…» y desde el tablero la fase no retrocede. Si de verdad quieres bajarla, cámbiala en «Gestionar proceso»". En
  "Mover a…" esa opción aparece deshabilitada con "(la fase no retrocede)". Al decidirlo había 0 tarjetas reales en
  ese caso.
- **Descartar es una acción, no una zona.** Está como opción en "Mover a…" y como botón "❌ Descartar" en la tarjeta;
  no hay zona de soltado. Cambia solo el estado (la fase se mantiene), va por `/api/marcar` con `origen: "tablero"`,
  y el "Deshacer" del aviso lo revierte exacto.
- **Las descartadas quedan fuera del tablero.** `columnaDe` devuelve null para `descartada` y `nueva`; una tarjeta
  descartada sale del tablero y aparece en la pestaña «Descartadas».
- **Follow-up también con historial.** `avisoSeguimiento` es la MISMA regla en la Lista y en el tablero (postulada
  o entrevista, días desde `fecha_postulacion`). Con historial, las tarjetas de C y E muestran "🕒 N días en esta
  etapa" y además el aviso de follow-up en línea propia; O se comporta como la Lista (también lo muestra); P no
  muestra follow-up. Sin historial no se repiten los días: los dice el follow-up (o, en P, "🕒 Postulada hace N días").
- **Vista inicial:** Tablero la primera vez; después, lo guardado en el navegador (`vistaSeguimiento`).
- **Si `/api/marcar` falla** tras un arrastre, la tarjeta queda en su columna y se muestra el error. El tablero no
  mueve nada antes de la respuesta del servidor.
- **Arrastre y selector:** la tarjeta solo es arrastrable al presionar fuera del selector, los botones y los enlaces
  (en Firefox un `<select>` dentro de un elemento draggable no se abre). Verificado en Chrome; Firefox lo revisa Sofia.

**Accesibilidad y teclado:**
- Cada tarjeta mantiene el selector **"Mover a…"**, que aplica las mismas reglas (bloqueos incluidos), y el botón
  "Gestionar proceso".
- Arrastrar no es accesible con teclado ni funciona bien en pantallas táctiles: el selector es la alternativa.
- Las columnas son `section` con `aria-label`.

**Pantallas angostas:** las columnas se desplazan de lado (scroll horizontal dentro del tablero) y la página no se
desborda.

**Días en la tarjeta**, con `en_fase_desde`, que ya viene en `/api/ofertas`:
1. Si hay historial válido, los días desde el último cambio de estado o fase que la dejó como está. Deshacer anula el
   cambio revertido, editar solo la fecha no reinicia, y el orden es por `id`.
2. Si no hay historial (o hay un hueco del código anterior) pero sí fecha de postulación, los días desde la
   postulación.
3. Si no hay ninguna de las dos cosas, no se muestra nada.

**DOM:** solo con `h()`/`textContent`, sin `innerHTML`.

**Pruebas esperadas (~10):**
- funciones puras de la columna: cada combinación de estado y fase; ninguna oferta en dos columnas ni fuera de alguna;
- reglas de soltar: los 12 movimientos, O → E bloqueado, misma columna sin pedido, la fase nunca baja, la fecha solo
  se completa si está vacía;
- el selector "Mover a…" con las mismas reglas;
- los días en la tarjeta (los 3 casos);
- la página sin `innerHTML`;
- `origen: "tablero"` en los pedidos.

### C3: Métricas y embudo (pestaña nueva; solo lectura)

Se calcula en el navegador a partir de `/api/ofertas`, sin rutas nuevas. La **fase es "lo más lejos que llegó"** una
oferta: las que se descartaron después de postular siguen contando en el embudo.

**Embudo:**
1. Relevantes (principal).
2. Postuladas: fecha de postulación, o estado postulada o entrevista.
3. Llegaron a entrevista: fase rrhh, tecnica, final u oferta, o estado entrevista.
4. Final u oferta.

**Indicadores:**
- **Tasa de respuesta:** entrevistas sobre postuladas, con el divisor a la vista ("1 de 8"); sin datos, "0 de 0".
- **Días promedio** desde la postulación en los procesos activos.
- **Procesos activos.**
- **Descartadas después de postular.**

**Desgloses:** por fuente, modalidad y tipo (A, B, S, M, SAP).

**Actividad:** postulaciones por semana en las últimas 8 semanas, según la fecha de postulación.

**Barras:** con `h()`, y el ancho como `style.width` en %.

Con el historial ya se puede medir el tiempo entre cambios, pero solo desde el 13-10-2026. No se inventa nada hacia
atrás.

**Pruebas esperadas (~9):** funciones puras del embudo, los indicadores y las semanas, incluido el caso sin datos (sin
divisiones por cero); las descartadas con fecha cuentan como postuladas; singular y plural.

### Plan de trabajo y despliegue (cada parte por separado: C2 y luego C3)
1. Implementar con pruebas. `venv/Scripts/python.exe -m pytest -q` en verde (hoy hay 409).
2. Commit local, sin push.
3. Candidata en 127.0.0.1:8766 (`jt_revision_<nombre>`) sobre una copia hecha con la API de backup en solo lectura.
4. Revisión visual de Sofia.
5. Con su aprobación explícita, `/desplegar <etiqueta> <nombre>`: etiquetar, detener, referencia con sha256 e
   integrity_check, reconstruir, tabla antes/después fila por fila, solo POST rechazados, reversión documentada y
   probada, limpieza.
6. C2 y C3 no cambian el esquema: todas las tablas deben quedar idénticas.

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
