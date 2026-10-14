# Notas del proyecto: decisiones y hallazgos

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Base real:** v7, integrity_check ok, 1143 ofertas, 6 corridas, 14 postuladas, 6 POR VERIFICAR (notas con
  "POR VERIFICAR").
  - `historial_estados` tiene 1 fila (id 1, origen `modal`: un cambio de fase a `postulacion` con fecha en una oferta
    principal), con sus 6 objetos.
  - Estados: descartada/nueva 1081 · principal/descartada 48 · principal/postulada 14.
  - sha256 por tabla: ofertas `bf4f46f55ad6fff401a14c6ebbc18a3b1179a82d3ee179f6009c378f2211a453` · historial_estados
    `9508c9fac38f09fd220ff89c3f12548be306444cbeb212ee95d32614aef5a9c2` · corridas
    `0f9522379daa29318a415041e7ec1453e9e370fb168f427239048ac00465bf57`.
  - Medido el 14-10-2026 a las 10:17, después del despliegue del 137 y del segundo stop/start (idéntico a la
    referencia). El archivo real no cambia desde el 13-10 22:50:35 (sha256 `b69f5aed…`, en modo WAL, sin -wal/-shm).
- **Última referencia:** `ofertas_pre_137_20261014.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker\`, fuera de
  OneDrive), sha256 `f42673e5451fd53891c4281fa9f0b67b0340f1ed3f846f933922bac209dbb1ec` (igual a
  `ofertas_auto_20261014-000439` y `ofertas_manual_20261013-233504`). La anterior, `ofertas_pre_c2_20261013.db`
  (`309228dd…`), se conserva.
- **En producción (14-10-2026, 10:15):** commit `a7339c1` (incluye `6660133` «informático junior», `9561c19` cierre
  con SIGTERM y `a7339c1` respaldos atómicos), imagen `job-tracker:137-respaldo-candidata`
  `sha256:ff5a2615845e1b7a57719015697166e31c319972ce6efbb3e3ac99809b1bbc3f`, desplegada sin reconstruir
  (`docker tag` + `docker compose up -d --no-build`). StopTimeout 15 s.
  - Primer stop (imagen vieja): SIGTERM → SIGKILL a los 3,0 s, código 137; integrity_check ok y sin -wal después. El
    contenedor viejo no tenía StopTimeout (se creó antes del `stop_grace_period`).
  - Segundo stop (imagen nueva): `docker compose stop` en 595 ms, SIGTERM → salida 0 en 343 ms, sin SIGKILL,
    «Servidor detenido.» en el log; integrity_check ok y huellas iguales.
- **Imágenes para volver atrás:** `job-tracker:c2` (= `:c2-candidata`, `f1943914…`; reversión en
  `REVERSION_FASE_A.md`, probada), `:c1` (`c461ada1…`), `:respaldo` (`ac00ce13…`), `:B1`, `:genero`, `:soporte`,
  `:faseA`, `:fase0`.
  - Siguen las candidatas viejas `:historial-candidata`, `:respaldo-candidata`, `:faseB1-candidata`,
    `:faseA-candidata` y `:137-candidata` (`f9b15255…`); se borran si Sofia lo aprueba.
  - Contenedores detenidos que esperan la limpieza (no se tocan sin aprobación): `jt_revision_c2` (255, por el apagado
    del 14-10), `jt_revision_137` y `jt_revision_137r` (0), con sus volúmenes.
- **Commits sin push:** no se anotan aquí; se cuentan siempre con `git rev-list --count origin/main..HEAD`.

### Hallazgos del 14-10-2026
- **Reinicio de Docker a las 09:47:** fue por el apagado del PC de Sofia, no por una falla. Los contenedores se
  cerraron sin cierre ordenado (la imagen vieja ignoraba SIGTERM; `docker events` no guardó el cierre porque los
  eventos viven en la memoria del daemon). La base quedó intacta: integrity_check ok y huellas idénticas al respaldo
  de las 00:04. Refuerza el arreglo del 137.
- **Respaldo automático del 14-10** (`ofertas_auto_20261014-000439`, el primero con `historial_estados`):
  `sha256sum -c` OK, integrity_check ok, un solo archivo y huellas iguales a la base real.
- **Un `.db` incompleto** (sin su `.sha256`) suele estar íntegro: se podría ofrecer «completar huella» a pedido
  (integrity_check y escribir el `.sha256`). No implementado.
- **Copias de solo lectura de la base real:** con el volumen en `:ro`, `mode=ro` falla si no hay -shm; si no hay
  -wal/-shm se usa `mode=ro&immutable=1` comprobando tamaño, mtime y sha256 antes y después. Si hay -wal: volumen
  en rw con `mode=ro` (como el respaldo del servidor), nunca `immutable`.

### Pendientes
- **Commit 3: orden de `listar()`** (aprobado para después del despliegue, con prueba; espera la orden). `listar()`
  ordena por nombre y deja todos los manuales antes que los auto, así que «Último respaldo» muestra el manual del
  13-10 23:35 aunque el auto del 14-10 00:04 es más nuevo. `_retener` no tiene el defecto: filtra solo los auto
  válidos y su nombre ordena por fecha; los manuales e incompletos no cuentan ni se borran.
- **«informático junior» ACTIVO** desde el 14-10-2026: término en Indeed, Glassdoor/Get on Board y Chiletrabajos
  (8 solicitudes más por corrida) y regla de último recurso A: TI, Baja. **Criterio de salida:** contar las ofertas
  que lleguen con el motivo «rol: informático junior»; si en unas 10 corridas no llega ninguna útil, se quita el
  término.
- **Limpieza** (espera aprobación): contenedores y volúmenes `jt_revision_c2`, `jt_revision_137`, `jt_revision_137r`
  (y sus `_respaldos`), las 5 candidatas viejas y las copias del scratchpad. Se conservan `:c2`, `:c2-candidata`,
  `:137-respaldo-candidata` (producción) y las etiquetas de vuelta atrás.
- **Referencias fuera de OneDrive (14-10-2026):** copiadas (no movidas) a
  `C:\Users\sofia\Respaldos\job-tracker-referencias\` (hermana de la que monta el contenedor; fuera de OneDrive y de su
  copia de seguridad), una por sha256 distinto, cada una con sha256 igual al origen e integrity_check ok:
  `ofertas_pre_fase0_20261013.db` (= pre_faseA, `a3d914a2…`), `ofertas_pre_B1_20261013.db` (= pre_respaldo,
  `c000a469…`), `ofertas_pre_soporte_20261013.db` (`027a0ea9…`), `ofertas_pre_genero_20261013.db` (`405a0e02…`),
  `ofertas_pre_historial_20261013.db` (`e1f849f6…`), `ofertas_pre_verificar_20261013.db` (`dfa9fcf8…`),
  `ofertas_unida_20261013.db` (`1c2a3256…`), `ofertas_unida_20261013_v2.db` (= unida_instalada, `fc299710…`),
  `ofertas_volumen_job-tracker_20261013-112247.db` (`bd69a22b…`) y `excepciones_union_20261013.json` (`8a54b739…`).
  Las bases Node (v5, 866 ofertas: volumen_buscador-de-empleos, node_docker-data = padre, final_node) no se copian:
  Sofia no las necesita y sus 2/6/6 ofertas con postulación (y las 5 excepciones de la unión) ya están en la base
  real con su estado y fecha.
- **OneDrive: originales borrados el 14-10-2026** (aprobado por Sofia), después de copiar y verificar las
  referencias: el contenido de `job-tracker\respaldos\` (21 archivos y la subcarpeta `final_node_20261013-113513\`;
  la carpeta queda vacía y ningún código depende de ella, solo la nombra la skill `/desplegar`),
  `C:\Users\sofia\OneDrive\OneDrive\` (solo tenía `Documentos\GitHub\Buscador-de-empleos\docker-compose.yml` y sus 4
  carpetas) y el volumen `buscador-de-empleos_jt_datos` (0 contenedores; solo una base Node v5). **La papelera de
  OneDrive la vacía Sofia a mano;** mientras no lo haga, lo borrado sigue en la nube.
- **C2 desplegada** el 13-10-2026. Sigue C3. B2 (importar) no se hará. Resiliencia/LinkedIn sin aprobar.

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

## codegraph (evaluado el 13-10-2026 sin instalar; NO se usa en job-tracker)

Evaluado `colbymchenry/codegraph` v1.6.2 (`@colbymchenry/codegraph`) leyendo su README y su instalador, sin instalar nada. Decisión: no se instala.

- `web/pagina.html` (donde viven C2 y C3) queda fuera del grafo: no soporta HTML con JavaScript embebido (solo `.js`, `.jsx`, `.mjs`).
- El instalador agrega el permiso `mcp__codegraph__*`, que aprueba sus herramientas sin preguntar.
- La telemetría queda encendida por defecto si se instala con `--yes`.
- Su base SQLite (`.codegraph/codegraph.db`) quedaría dentro de OneDrive y se reescribe con cada cambio.
- No se tocaron `~/.claude.json`, `~/.claude/settings.json`, `~/.claude/CLAUDE.md` ni `~/.codegraph/`.
- Se retoma solo si el servidor Python crece y el análisis de impacto lo justifica. Se probaría sobre una copia fuera de OneDrive, con `--no-permissions` y la telemetría apagada.

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
