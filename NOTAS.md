# Notas del proyecto: decisiones y hallazgos

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Base real — línea base OFICIAL (16-10-2026, 12:35, regla de antigüedad LinkedIn; vigente):** v7,
  integrity_check ok, 1967 ofertas, 17 corridas, 44 filas en `historial_estados`, 16 postuladas, 6 POR VERIFICAR;
  estados descartada/nueva 1838 · principal/descartada 88 · principal/entrevista 1 · principal/nueva 24 ·
  principal/postulada 16.
  - Medida con `huellas.py` sobre la referencia `ofertas_pre_mid_senior_20261016.db` (contenedor detenido) y
    repetida en la base real después del despliegue y después de las comprobaciones: idéntica las tres veces.
  - sha256 por tabla: ajustes (4) `8928191ee9f0b506cee48f285e4167b71105de6cf7871705417a6518c3797aec` ·
    alertas (0) `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` ·
    corridas (17) `9e63aa4dc92ae580793909ab087819dbe4b68590d36a9d21c36100cd59724732` ·
    historial_estados (44) `6bfad4c7e552194125988612975c4c3134a6fa8a0e9507f35c6193979904b838` ·
    ofertas (1967) `bfbeb12bb1816ec87416a319b70953bd35b435e6633ab81bc54b2a2207ec4480` ·
    pruebas_fuentes (0) `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` ·
    sqlite_sequence (2) `c2a2deef445e938e4c7058289fcb173ffad9af078e2aebae9df3561c89db3a3b` ·
    terminos_no_disponibles (2) `0821946c3a741fa08fe0d2d793030aa14a531e6bf00096b4aa102d92f1e6d8c5`.
- **Mediciones anteriores (no mezclar sus cifras con la oficial):** la línea base del 15-10-2026, 23:45, fue v7,
  1588 ofertas, 14 corridas, 15 filas en `historial_estados`, 16 postuladas y 6 POR VERIFICAR.
- **Medición del 15-10-2026, 18:53 (telemetría):** 1536 ofertas, 12 corridas, 14 historial, 15 postuladas.
  Referencia: `ofertas_pre_telemetria_20261015.db` (`844341c7…`).
- **Medición del 15-10-2026, mañana (solo conteos):** v7, integrity_check ok, 1321 ofertas, 9 corridas, 15 postuladas.
- **Medición del 14-10-2026:** 1223 ofertas, 7 corridas, 14 postuladas, `historial_estados` con 4 filas.
- **Última referencia (oficial):** `ofertas_pre_mid_senior_20261016.db` (volumen y
  `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256
  `e3856c8346f07a065c8bc65213d2aa674049012d38d01e78c65ba2e35ebc0dd3` en las dos copias, integrity_check ok.
  Tomada con el contenedor detenido (salida 0).
- **En producción (16-10-2026, 12:35):** commit local `a245ece` (rama `feat/contadores-ubicacion`, sin push);
  imagen `job-tracker-jobtracker:latest` y `job-tracker:linkedin-mid-senior`,
  `sha256:915bc9fd6217faac57431091bf4804844f5119592c15e52c5f989cc677ad6694`.
  - Reconstruida con `docker compose build` y levantada con `docker compose up -d`; health `healthy`.
  - Imagen anterior, del commit `23241ba`, etiquetada `job-tracker:linkedin-filtros-23241`
    (`sha256:d4d6b5347f13f5ced733f060f8ba3dad81f6ce2830f53714b4359eac6f8a45d9`); `docker compose stop` salió 0.
  - Comprobado sin escrituras de datos: GET 200; Host y Origin ajenos 403; POST rechazados con 403, 400 y 413.
    Huellas completas, conteos, estados y objetos de las 8 tablas idénticos antes/después. `GET /api/respaldo` sin
    `error_auto`; último: `ofertas_auto_20261016-000213.db`.
  - Candidata revisada: Associate aceptado y Mid-Senior descartado. Referencia y huellas completas idénticas.
    No reclasifica ofertas guardadas ni altera la base. Reversión probada sobre una copia; ver `REVERSION_FASE_A.md`.
- **Imágenes para volver atrás:** `job-tracker:linkedin-mid-senior` (`915bc9fd…`; producción actual),
  `job-tracker:linkedin-filtros-23241` (`d4d6b534…`; reversión inmediata),
  `job-tracker:linkedin-filtros` (`d4d6b534…`; etiqueta anterior del mismo artefacto),
  `job-tracker:linkedin-229f` (`d4529c34…`; anterior a los filtros),
  `job-tracker:telemetria` (`ad7b2b19ced7…`; reversión en `REVERSION_FASE_A.md`),
  `job-tracker:137` (`ff5a2615…`), `job-tracker:c2` (`f1943914…`), `:c1`, `:respaldo`, `:B1`, `:genero`, `:soporte`, `:faseA`, `:fase0`.
  - Siguen las candidatas viejas `:historial-candidata`, `:respaldo-candidata`, `:faseB1-candidata`,
    `:faseA-candidata` y `:137-candidata` (`f9b15255…`); se borran si Sofia lo aprueba.
  - Contenedores detenidos que esperan la limpieza (no se tocan sin aprobación): `jt_revision_c2` (255, por el apagado
    del 14-10), `jt_revision_137` y `jt_revision_137r` (0), `jt_revision_telemetria` y `jt_revision_telemetria_rev`
    (0, 15-10), con sus volúmenes.
- **Nombres de respaldo fuera de formato** (`481aab7`, desplegado el 15-10): los nombres que no
  calzan con `ofertas_(auto|manual)_AAAAMMDD-HHMMSS.db` se ignoran: no cuentan como «Último respaldo», no cuentan para
  la retención y nunca se borran.
- **Commits sin push:** no se anotan aquí; se cuentan siempre con `git rev-list --count origin/main..HEAD`.

### Hallazgos del 14-10-2026
- **Reinicio de Docker a las 09:47:** fue por el apagado del PC de Sofia, no por una falla. Los contenedores se
  cerraron sin cierre ordenado (la imagen vieja ignoraba SIGTERM; `docker events` no guardó el cierre porque los
  eventos viven en la memoria del daemon). La base quedó intacta: integrity_check ok y huellas idénticas al respaldo
  de las 00:04. Refuerza el arreglo del 137.
- **Respaldo automático del 14-10** (`ofertas_auto_20261014-000439`, el primero con `historial_estados`):
  `sha256sum -c` OK, integrity_check ok, un solo archivo y huellas iguales a la base real.
- **Corrida 7** (14-10, 10:55 → 11:02, 7 min; las corridas 1 a 6 duraron entre 6 y 8 min), la primera con
  «informático junior». 80 ofertas nuevas: Indeed 40, Chiletrabajos 20, BNE 9, Trabajando 9, Glassdoor 2, Get on
  Board 0. Principales 3 (Indeed 2, Chiletrabajos 1; A: TI, Media; Sofia las descartó desde la lista) y 77
  descartadas al clasificar (sin rol objetivo 54, práctica/estudiante 20, 2+ años 2, rol puente 1).
  - Ventana de 2 días (3 en BNE), por eso hubo más encontradas que en la corrida 6: Indeed 174 (126), Glassdoor 31
    (24), Get on Board 3 (3), BNE 29 (17), Trabajando 11 (1), Chiletrabajos 42 (29).
  - Errores 0 en las 6 fuentes, como en las corridas 1 a 6. `terminos_no_disponibles` sin cambios (los 2 de
    Trabajando, hasta el 10-11). El detalle de la corrida no guarda códigos HTTP (429/403/404) ni el número de
    solicitudes: `red.py` las cuenta en memoria y no las registra, así que las «8 extra» no se pueden medir.
  - «informático junior», corrida 1 de ~10: 0 ofertas con el motivo «rol: informático junior»; el término trajo 1
    oferta (Glassdoor), descartada como práctica/estudiante.
  - Una de las 3 principales era un cargo comercial clasificado como «rol: desarrollo» (falso positivo de la palabra
    «desarrollador»).
- **Un `.db` incompleto** (sin su `.sha256`) suele estar íntegro: se podría ofrecer «completar huella» a pedido
  (integrity_check y escribir el `.sha256`). No implementado.
- **Copias de solo lectura de la base real:** con el volumen en `:ro`, `mode=ro` falla si no hay -shm; si no hay
  -wal/-shm se usa `mode=ro&immutable=1` comprobando tamaño, mtime y sha256 antes y después. Si hay -wal: volumen
  en rw con `mode=ro` (como el respaldo del servidor), nunca `immutable`.
- **Decisión (14-10-2026): datos de postulaciones en el historial de git.** NOTAS solo lleva conteos y estados
  agregados, sin títulos, empresas ni fechas de las postulaciones. Un título con su fecha quedó en el historial ya
  empujado (desde `812ccf3`); Sofia lo acepta porque el repositorio es privado y no se usa `--force`. Si el repositorio
  se hace público, se publica una copia limpia (sin ese historial).

### Pendientes
- **Commit 3: orden de `listar()`** (`09409f3`) — **desplegado el 15-10-2026** con la telemetría. `listar()` ordenaba
  por nombre y dejaba todos los manuales antes que los auto, así que «Último respaldo» mostraba un manual más viejo
  aunque hubiera un auto más nuevo; ahora ordena por la fecha del nombre. Los nombres siempre son
  `ofertas_{auto|manual}_AAAAMMDD-HHMMSS.db` (un solo lugar los genera, `respaldo.respaldar`, sin sufijo por
  colisión). `_retener` no cambia: filtra solo los auto válidos; los manuales e incompletos no cuentan ni se borran.
- **Telemetría pasiva de corridas** (`e754ff6`) — **desplegada el 15-10-2026, 18:53**. Las corridas 1 a 12 no la
  traen (la imagen anterior no la tenía); la primera corrida con telemetría la lanza Sofia. Solo contadores por fuente
  en `corridas.detalle.fuentes[i].telemetria` (solicitudes, códigos 200/403/404/429/5xx/otros/conexión, vacías) y una
  línea `[corrida]` en stderr; sin URLs, parámetros ni términos, sin DDL (v7), las corridas antiguas no cambian. No
  cambia pausas, reintentos ni orden.
  - Es **por fuente, no por término**: no dice qué término falló.
  - **Indeed y Glassdoor** (JobSpy) se miden como «consultas» (llamadas, vacías y errores); JobSpy no expone sus
    solicitudes y no se intercepta `requests` dentro de la librería. Un 429 que JobSpy traga aparece como vacía, así
    que **un bloqueo se detecta cuando todas las consultas de una corrida salen vacías en una fuente que antes
    devolvía resultados**.
- **«informático junior» ACTIVO** desde el 14-10-2026: término en Indeed, Glassdoor/Get on Board y Chiletrabajos
  (8 solicitudes más por corrida) y regla de último recurso A: TI, Baja. **Criterio de salida:** contar las ofertas
  que lleguen con el motivo «rol: informático junior»; si en unas 10 corridas no llega ninguna útil, se quita el
  término.
  - Cuenta como «oferta útil» una que entre como principal con el motivo «rol: informático junior». Corridas medidas
    con el término: 6 (7 a 12), 0 ofertas útiles; el término trajo 1 oferta (corrida 7, descartada por práctica /
    estudiante) y 0 en las corridas 8 a 12. «Traídas por el término» cuenta solo ofertas NUEVAS guardadas, atribuidas
    al primer término que las encontró (las repetidas de otro término no aparecen): esos 0 son un piso, no una
    medición exacta. Medido en la referencia oficial `ofertas_pre_telemetria_20261015.db`.
- **Diagnóstico de términos (15-10-2026, solo lectura; plan PENDIENTE de aprobación, nada decidido salvo la fase a).**
  Sobre la referencia oficial (corridas 1 a 12) y una copia de solo lectura de la base viva (corrida 13). «Traídas»
  cuenta solo ofertas NUEVAS atribuidas al primer término que las encontró: es un piso.
  - Indeed: 13 de 30 términos nunca dieron una principal (datos maestros, master data, key user, asistente de
    proyectos, PMO, analista de operaciones, analista SAP, analista de datos junior, tester, BPMN, desarrollador
    junior, desarrollador frontend, informático junior); «desarrollador junior» y «desarrollador frontend» devuelven 0.
    Mantener pese a llevar 6+ corridas sin útil: analista funcional (3 en seguimiento), usuario clave (2), testing.
  - Get on Board: 0 principales en toda la historia (sobre todo por senior). Glassdoor: solo «analista de sistemas» y
    «analista de procesos» dieron alguna.
  - Ubicaciones: Viña (30 consultas de Indeed por corrida) 0 principales en toda la historia; remoto 0 desde la
    corrida 1; Glassdoor remoto 0 traídas. Ninguna de las 75 principales está en la Región de Valparaíso; las 12
    remotas vienen de Chiletrabajos (11) y de la consulta de Santiago de Indeed (1).
  - Cobertura: QA/testing llega sobre todo por Chiletrabajos («analista qa»); en Indeed faltan «analista QA»,
    automatización de pruebas, RPA y «programador». No hay términos de soporte (unas 0,6 ofertas de soporte por
    corrida llegan por otros términos, 41 % principales).
  - Clasificador (si se agregan términos de soporte): «Soporte Funcional» queda descartada (sin rol); «Operario
    Nivel 1» entra como S (falso positivo de `nivel 1`); call center, soporte en terreno y «soporte» sin contexto TI
    entran como S.
  - **Plan propuesto, por fases, cada una con su diff, pruebas, candidata y despliegue:** (a) contadores —
    `"200": null` («no medido») y `por_ubicacion` en Indeed/Glassdoor; **aprobada el 15-10 y en curso en la rama
    `feat/contadores-ubicacion`, sin desplegar**; (b) retiros de términos y ubicaciones (opciones A: solo Santiago, B:
    Viña y remoto solo para 6 términos, C: sin Viña, D: sin cambios) — **pendiente**; (c) términos nuevos (analista
    QA, automatización de pruebas, programador, RPA) y de soporte, con los ajustes del clasificador — **pendiente**.
- **Falso positivo «Desarrollador de Negocios» → «rol: desarrollo»** (corrida 7; un cargo comercial clasificado como
  A: TI por la palabra «desarrollador»). Pendiente, sin cambiar la regla: se revisa solo si el patrón se repite en
  las próximas corridas.
- **Limpieza** (espera aprobación): contenedores y volúmenes `jt_revision_c2`, `jt_revision_137`, `jt_revision_137r`,
  `jt_revision_telemetria` y `jt_revision_telemetria_rev` (y sus `_respaldos`), las 5 candidatas viejas, la referencia
  en caliente `ofertas_ref_etapa1_telemetria_20261015.db` (igual a la oficial), `/tmp/huellas.py` dentro de
  `jobtracker` y las copias del scratchpad. Se conservan `:telemetria-candidata` (producción), `:137` (=
  `:137-respaldo-candidata`), `:c2`, `:c2-candidata` y las etiquetas de vuelta atrás.
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
- **C2 desplegada** el 13-10-2026. Sigue C3. B2 (importar) no se hará. Resiliencia sin aprobar.
- **Filtro de LinkedIn y exclusión de BairesDev (16-10-2026; desplegado en `a245ece`):** no reclasifica ofertas
  guardadas ni modifica estados. Se aceptan Santiago, Viña del Mar y Valparaíso si la ubicación identifica Chile.
  Si LinkedIn no indica ciudad, se busca una ciudad objetivo en la descripción; otras ciudades se descartan.
  Se acepta cualquier país si el aviso indica remoto. En experiencia se acepta un máximo de 2 años; rangos que
  superen 2 y requisitos abiertos con «+» se descartan. En el nivel LinkedIn, Associate se acepta y Mid-Senior se
  descarta. BairesDev/Baires Dev queda excluida en todas las fuentes. Sofia pidió push, pero no se hará por la regla
  permanente de no publicar al remoto.

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
