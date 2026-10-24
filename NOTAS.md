# Notas del proyecto: decisiones y hallazgos

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Despliegue del rediseño por apartados (23-10-2026, ~23:40; vigente):** commits `7aad48a`, `73ab2db`, `10fc78e`,
  `26a23a5` (menú izquierdo con Ofertas, Seguimiento, Métricas y Ajustes; navegación por #hash; sin barra derecha;
  Datos y Apariencia en Ajustes) y `a677529` (selector único «Tablero · Tarjetas · Compacta» en Seguimiento y
  tutorial al día). Solo cambia `web/pagina.html`. Imagen `job-tracker-jobtracker:latest` =
  `sha256:0602873e29fc21f596f8284d2775afd439d14b8425ead41eaae651843bec0503`, healthy en `127.0.0.1:8765`.
  Imagen anterior: `job-tracker:pre-rediseno-20261023` (= `sha256:57a22899…`, la de los avisos).
  Referencia `ofertas_pre_rediseno_20261023.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`),
  sha256 `ba4b3db5…` (idéntica a la de los avisos), integrity_check ok; salida al detener 0.
  - Línea base sin cambios: v7; ofertas 4452, corridas 45, historial_estados 290, ajustes 5,
    terminos_no_disponibles 16; postuladas 36; POR VERIFICAR 6.
  - Huellas antes, después y después de las comprobaciones: RESULTADO OK, todas las tablas idénticas.
  - HTTP: `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo` 200; Host y Origin ajenos 403; POST sin origen, con campo
    no permitido o estado inválido 400; Origin ajeno 403; cuerpo grande 413. `error_auto` vacío.
  - **Sin candidata en 8766:** Sofia pidió desplegar directo. Se revisó antes con un servidor local sobre una copia
    de la referencia, y después en producción solo leyendo (los cuatro apartados cargan). Reversión probada en copia
    (8767): healthy, huellas idénticas. 113 respaldos anteriores con el mismo sha256.
  - Subido a GitHub (rama `feat/unificar-ofertas`, hasta `a677529`) con aprobación de Sofia, antes de desplegar.
  - Pendiente: los avisos reales del sistema siguen sin probarse (el navegador integrado los bloquea).
- **Despliegue de métricas en la barra derecha y avisos del navegador, fase 3 (23-10-2026; anterior):** commits
  `d519ed2` (fase 1: recordar pestaña y filtros), `6c6c664` + `7751107` (métricas, en la barra derecha), `2cb86e0`
  (avisos), `ca1e4f0` (estilos compactos). Imagen `job-tracker-jobtracker:latest` =
  `sha256:57a228999bd97a737b9e4ce841cfdf988561183158d7a7a11c698abc9c1f2a9a`, healthy en `127.0.0.1:8765`.
  Imagen anterior: `job-tracker:pre-avisos-20261023` (= `sha256:c2207ae0…`, la de las exclusiones).
  Referencia `ofertas_pre_avisos_20261023.db` (volumen y `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256
  `ba4b3db52e761560b73caf34970055ce2b960e459dee6a2a5663bea602b755d2`, integrity_check ok; salida al detener 0.
  - Línea base: v7; ofertas 4452, corridas 45, historial_estados 290, ajustes 5, terminos_no_disponibles 16,
    alertas 0, pruebas_fuentes 0; postuladas 36; POR VERIFICAR 6.
  - Huellas antes, después y después de las comprobaciones: RESULTADO OK, todas las tablas idénticas.
  - HTTP: `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo` 200; Host y Origin ajenos 403; POST sin origen, con
    origen inválido o campo no permitido 400; cuerpo grande 413. `error_auto` vacío.
  - Candidata `jt_revision_avisos` (8766, sobre copia de la base) revisada por Sofia antes. Reversión probada en copia
    (8767): healthy, huellas idénticas. 111 respaldos anteriores con el mismo sha256.
  - Pendiente: los avisos reales del sistema no se probaron (el navegador integrado los bloquea); el flujo se probó
    simulado. Pregunta abierta: «Ofertas 0» con «2 relevantes nuevas» (ya pasaba antes de este despliegue).
- **Despliegue NO registrado de las exclusiones (23-10-2026, ~20:17 hora de Chile; anterior):** encontrado el 23-10 al
  preparar la fase 3. Imagen `job-tracker-jobtracker:latest` = `sha256:c2207ae0b52e34f945515856f7fac5375e6651b519e8ec9ccde45bec2e81b95f`,
  healthy en `127.0.0.1:8765`. `buscar.py`, `config.py`, `exclusiones.py`, `filtros.py` y `servidor.py` tenían el
  mismo sha256 que el árbol de trabajo (los de `446a22c`), pero `web/pagina.html` era otra versión: con exclusiones y
  barra derecha, SIN la fase 1 (`d519ed2`, recordar pestaña y filtros) y SIN métricas (`6c6c664`). No corresponde a
  ningún commit; se construyó desde un árbol de trabajo intermedio.
  - Imagen anterior: `job-tracker:pre-puestos-20261023` = `sha256:2509d984…` (la de la reclasificación). Es lo único
    que dejó ese despliegue.
  - **Sin referencia de la base** (no hay `ofertas_pre_*_20261023.db` en el volumen ni en `job-tracker-referencias`),
    sin huellas antes/después y sin entrada en `REVERSION_FASE_A.md`. No se puede demostrar que la base no cambió.
  - Estado de la base al encontrarlo (copia con la API de backup, conexión `mode=ro`): integrity_check ok, 4452
    ofertas, 36 postuladas, 45 corridas; sha256 de la copia `ba4b3db52e761560b73caf34970055ce2b960e459dee6a2a5663bea602b755d2`.
  - Quedaron candidatas sin borrar (`jt_revision_metricas` corriendo en 8766 y `jt_revision_excl` detenida); se
    borraron el 23-10 con sus volúmenes.
  - Para volver atrás: `docker compose stop jobtracker`, `docker tag job-tracker:pre-puestos-20261023
    job-tracker-jobtracker:latest`, `docker compose up -d --no-build`.
- **Reclasificación de lo guardado, APLICADA (22-10-2026; vigente):** `python buscar.py --reclasificar` sobre la base real.
  Referencia previa `ofertas_pre_reclasif_20261022.db` (sha256 `da3a88e9…`, integrity ok, 4245 ofertas, 34 postuladas,
  6 POR VERIFICAR); imagen anterior `job-tracker:pre-reclasif-20261022` (= `sha256:2509d984…`).
  - Huellas después: RESULTADO OK, idénticas a la referencia en todas las tablas; el estado de ninguna oferta cambió
    (postuladas 34, POR VERIFICAR 6, historial 280 sin cambios). La reclasificación no cambió nada de estado, según la
    simulación previa (0 cambios).
  - **Incidente:** el contenedor quedó con salida 137 (SIGKILL) al detenerlo. Se verificó la base con una copia hecha con
    la API de respaldo (integrity ok, mismos conteos) y el contenedor se levantó luego: healthy, rutas 200, Host/Origin
    ajenos 403, huellas RESULTADO OK. Un comando previo dejó el contenedor detenido sin querer; se corrigió levantándolo.
  - Para volver atrás: `docker compose stop jobtracker`, `docker tag job-tracker:pre-reclasif-20261022
    job-tracker-jobtracker:latest`, `docker compose up -d --no-build`, y si hace falta la referencia
    `ofertas_pre_reclasif_20261022.db`.
- **Reclasificación de lo guardado, simulada (22-10-2026):** la simulación dio 0 cambios. Con las reglas actuales, la simulación sobre la
  referencia `ofertas_pre_redespliegue_20261022.db` dio 0 cambios de 4240 ofertas revisadas (sin las manuales), incluidas
  las de seguimiento. Como no cambia nada, no se hizo la escritura real. Control: el clasificador sí reconoce soporte
  (categoría S, motivo «rol: soporte / helpdesk»).
- **Redespliegue con la misma versión de código (22-10-2026; vigente):** commit `de42a51` (rama `feat/unificar-ofertas`,
  subida a GitHub). Código idéntico al del despliegue de abajo (sha256 de los archivos que entran a la imagen iguales en
  el contenedor y en el árbol de trabajo). Imagen `job-tracker-jobtracker:latest` =
  `sha256:2509d984b4ada5ecac0df265735f94496f3d4ec58d5ee6650f85802c38fc39b1`, healthy en `127.0.0.1:8765`.
  Imagen anterior inmediata: `job-tracker:pre-redespliegue-20261022` (`sha256:ba0cc916…`, la de «Puestos que busco»).
  Referencia `ofertas_pre_redespliegue_20261022.db`, sha256 `da3a88e9e1d3218dd616de2e641564adc2c39c2f2dabe44af0ca27e52f0c18c9`
  en `C:\Users\sofia\Respaldos\job-tracker-referencias\` y en el volumen; integrity_check ok; 4245 ofertas, 34 postuladas,
  6 POR VERIFICAR.
  - Huellas antes y después idénticas (`huellas.py --comparar`: RESULTADO OK, sin objetos agregados ni faltantes).
  - Comprobaciones HTTP: `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo` y `GET /api/ajustes/puestos`: 200;
    Host ajeno y Origin ajeno: 403.
  - Reversión: `job-tracker:pre-redespliegue-20261022` (y, para volver aún más atrás, `job-tracker:pre-puestos-20261022`).
- **Despliegue de la sección «Puestos que busco» (22-10-2026; anterior):** commits `866faf3` (validación, paso 1),
  `dd55d0d` (guardado en ajustes y rutas, paso 2), `775a077` (sección en la barra lateral, paso 3) y `6eed95f` (CSS de
  filtros, ya en producción). Imagen `job-tracker-jobtracker:latest` = `sha256:ba0cc91630d5f60b9b5f89dd5341b781fb00863e44b366ce43ce3f3af5549d41`,
  healthy en `127.0.0.1:8765`. Imagen anterior inmediata: `job-tracker:pre-puestos-20261022`
  (`sha256:acff94b872624420ee6d8fbef127e328bda26e449e505c604b1ac992b033da04`).
  Referencia `ofertas_pre_puestos_20261022.db`, sha256 `da3a88e9e1d3218dd616de2e641564adc2c39c2f2dabe44af0ca27e52f0c18c9`
  en `C:\Users\sofia\Respaldos\job-tracker-referencias\` y en el volumen; integrity_check ok; 4245 ofertas, 34 postuladas,
  6 POR VERIFICAR.
  - Huellas después: RESULTADO OK sin objetos agregados ni faltantes. Diferencias en `ofertas` y `corridas`: la corrida 42
    (22:32) terminó después de tomar la referencia (21:57 - 22:32) y dejó 4 ofertas nuevas. No la causó este despliegue.
    Las 4 nuevas quedaron en «principal/nueva» (3) y «sin_descripcion/nueva» (1). Las postuladas, las POR VERIFICAR y el
    historial no cambiaron.
  - Comprobaciones HTTP: `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo` y `GET /api/ajustes/puestos`: 200;
    Host ajeno y Origin ajeno: 403.
  - Probado antes en candidata con navegador (agregar, rechazar inválido y repetido, guardar, recargar, quitar).
  - Reversión: `job-tracker:pre-puestos-20261022`.
- **Despliegue de soporte TI y fuentes remotas (22-10-2026; anterior):** commits `f96c301` (Himalayas y Jobicy, APIs
  públicas de empleo remoto), `f296a14` (términos «soporte TI» y «help desk») y `76ee255` (se quita el check de soporte
  de la página; el ajuste `soporte` de la base queda sin uso). Imagen `job-tracker-jobtracker:latest` =
  `sha256:acff94b872624420ee6d8fbef127e328bda26e449e505c604b1ac992b033da04`, healthy en `127.0.0.1:8765`.
  Imagen anterior inmediata: `job-tracker:pre-soporte-20261022` (`sha256:4ad9e68f…`, la de la ayuda).
  Referencia `ofertas_pre_soporte_20261022.db`, sha256 `8949bb8f158b2e6f7e7873e929286e8ceedc9d42c988b3b4754a573aac135583`
  en `C:\Users\sofia\Respaldos\job-tracker-referencias\` y en el volumen; integrity_check ok.
  - Línea base: v7, 4193 ofertas, 41 corridas, 280 filas de `historial_estados`, 34 postuladas, 6 POR VERIFICAR.
    Huellas antes y después idénticas (`huellas.py --comparar`: RESULTADO OK). Candidata en 8766 verificada antes
    (healthy; 200 en `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo`; Host y Origin ajenos 403) y borrada después.
  - Las fuentes nuevas (Himalayas, Jobicy) no se han probado todavía con una corrida real: la primera búsqueda dirá
    cuántas ofertas entran. Remotive queda pendiente.
  - Pendiente: el ajuste `soporte` de la base (`ajustes`) ya no tiene efecto; borrarlo toca la base real y necesita
    aprobación aparte.
  - Reversión: `job-tracker:pre-soporte-20261022` con `docker tag` + `docker compose up -d --no-build`.
- **Despliegue de la ayuda por pantalla (22-10-2026; anterior):** commit `200e021` (`main`; botón «❓ Ayuda de esta pantalla» junto a «Agregar postulación manual», con texto según la pestaña).
  Imagen `job-tracker-jobtracker:latest` = `sha256:4ad9e68fd0797a80cd02390cec8dd197bc4af0831c0d15a6ba9e0c475b0d0e7d`, healthy en `127.0.0.1:8765`. Imagen anterior inmediata: `job-tracker:pre-ayuda-20261022` (`e0069601…`).
  Referencia `ofertas_pre_ayuda_20261022.db`, sha256 `54CAF78E…849EE`, integrity_check ok.
  - Antes de desplegar, la base había cambiado desde la referencia del tutorial: una oferta de LinkedIn se descartó a mano a las 20:04 (hora de Chile). Se tomó una referencia nueva de la base real y se comparó contra ella: RESULTADO OK. El contenedor se había dejado detenido mientras se revisaba; se levantó antes de seguir.
  - Huellas antes y después idénticas; 66 archivos de respaldo y referencia conservan su sha256; `error_auto` vacío.
  - Reversión probada en copia (8767), healthy con huellas idénticas; luego borrada. Detalle en `REVERSION_AYUDA.md`.
- **Despliegue del tutorial (22-10-2026; anterior):** commit `b5d4f98` (`main`; `TUTORIAL.md` y el botón «❓ Cómo usar esta app»).
  Imagen `job-tracker-jobtracker:latest` = `sha256:e0069601e6486041b1974cea62acfb1241a1becdaa80ab8a6a46a6e688c501b4`,
  healthy en `127.0.0.1:8765`. Imagen anterior inmediata: `job-tracker:pre-tutorial-20261022` (`7edd2576…`).
  Referencia `ofertas_pre_tutorial_20261022.db`, integrity_check ok (mismo contenido que la de la interfaz: la base no cambió).
  - Huellas antes y después idénticas (RESULTADO OK); 63 archivos de respaldo y referencia conservan su sha256.
  - Comprobaciones HTTP como en el despliegue anterior; `error_auto` vacío.
  - Reversión probada en copia (8767), healthy con huellas idénticas; luego borrada.
- **Despliegue de la interfaz (22-10-2026; anterior):** commit `00b5312` (`main`, integra `feat/revision-interfaz`).
  Imagen `job-tracker-jobtracker:latest` = `sha256:7edd2576c6894c2c3f30cfe873eec019b26ebf2e4af57ab8c44187412f8aa40a`,
  healthy en `127.0.0.1:8765`. Imagen anterior inmediata: `job-tracker:pre-interfaz-20261022` (`76bb6cb1…`).
  Referencia `ofertas_pre_interfaz_20261022.db`, sha256 `0F226768…5D39C`, integrity_check ok.
  - Huellas antes y después idénticas (`huellas.py --comparar`: RESULTADO OK); 62 respaldos y referencias previos conservan su sha256.
  - Comprobaciones HTTP: GET 200; Host/Origin ajenos 403; POST sin Origin 400; campo no permitido 400; cuerpo grande 413.
  - Reversión probada en copia (8767) con huellas idénticas y luego borrada. Detalle en `REVERSION_INTERFAZ.md`.
  - Línea base: v7, 4193 ofertas, 41 corridas, 275 filas de `historial_estados`, 34 postuladas, 6 POR VERIFICAR.
- **Despliegue «Sin texto: pegar descripción» (22-10-2026; anterior a la interfaz):** commits `9181c66` y `3bad360` (rama
  `feat/contadores-ubicacion`, subidos a GitHub). Imagen `job-tracker-jobtracker:latest` =
  `sha256:76bb6cb17d745056b3ae5d70a69ea0037972bdf836a9920edfb2d79ac952a2bf`, healthy en `127.0.0.1:8765`.
  Imagen anterior inmediata: `job-tracker:pre-pegar-descripcion-20261022` = `sha256:4c165dda…` (la que estaba en
  producción, ver el hallazgo abajo). Detalle y reversión: `REVERSION_PEGAR_DESCRIPCION.md`.
  - Referencia `ofertas_pre_pegar_descripcion_20261022.db`, sha256 `16772cbbcb18a88fdf1863288379b54a7ae8e199e28bafa4a3e2a826cb26c8c9`
    en el volumen y en `C:\Users\sofia\Respaldos\job-tracker-referencias\`; integrity_check ok.
  - **Línea base (22-10-2026):** v7, integrity_check ok, 4143 ofertas, 40 corridas, 269 filas en `historial_estados`,
    34 postuladas, 6 POR VERIFICAR. Huellas idénticas antes y después (`huellas.py --comparar`: RESULTADO OK).
  - Las 61 referencias y respaldos previos conservaron su sha256; la reversión se probó sobre copia (8767) con huellas
    idénticas y luego se borró.
  - **Hallazgo:** entre el 21 y el 22-10, producción corrió `job-tracker-jobtracker:latest` = `sha256:4c165dda…`
    (construida el 22-10 a las 11:55), con el código de «Sin texto» y la regla de experiencia, sin registro en esta
    sección ni en `REVERSION_FASE_A.md`. Se etiquetó como `job-tracker:pre-pegar-descripcion-20261022` antes de
    reemplazarla. Es el mismo tipo de error que el del 19-10: un despliegue fuera del procedimiento.
  - **Pendiente:** reclasificar las ofertas guardadas con la regla nueva de oficio no TI (requiere aprobación aparte;
    toca la base real).
- **Despliegue de la pausa JobSpy (20-10-2026, 19:4x; vigente):** commit `3c98064`, imagen `job-tracker:pausa-jobspy`
  = `job-tracker-jobtracker:latest` (`sha256:d40d7a992fc3aab51dc3cfb41a6777c671cef3df9483c64fbbe2a58c33b61fe4`),
  healthy en `127.0.0.1:8765`. Imagen anterior inmediata: `job-tracker:pre-pausa-20261020` = `job-tracker:laborum`
  (`39378b0b…`). Referencia `ofertas_pre_pausa_20261020.db`, sha256
  `c40c50f5a99b1450f86bc260e7a2c33b7ba5f28f64b891cfd3edd5909130b472` en las dos copias (igual a la de Laborum: sin
  corridas entre ambos), integrity_check ok, contenedor detenido con salida 0. La línea base de abajo sigue siendo la
  vigente: huellas idénticas antes, después y tras las comprobaciones HTTP (mismas respuestas 200/403/400/413). La
  candidata `jt_revision_pausa` hizo 2 consultas reales a LinkedIn (37 s, sin 429) y respaldó bien. Los 81 respaldos y
  referencias anteriores conservaron su sha256. Reversión probada en copia (8767) y documentada en `REVERSION_FASE_A.md`.
  - **Corrección del despliegue de Laborum:** el archivo `/datos/=ro` vino de `'file:/datos/$ref?mode=ro'` en una
    cadena de PowerShell (`$ref?mode` se leyó como una variable vacía), así que el `integrity_check` que se mostró en
    su paso 3 fue el de ese archivo vacío. La referencia sí quedó verificada: `huellas.py` dio integrity_check ok
    sobre la copia externa y el sha256 coincidió. En este despliegue se usó `${ref}` y se verificó el archivo correcto.
- **Base real — línea base OFICIAL (20-10-2026, despliegue de Chumi, Laborum y regla de experiencia; vigente):** v7,
  integrity_check ok, 3150 ofertas, 34 corridas, 163 filas en `historial_estados`, 25 postuladas, 6 POR VERIFICAR;
  estados descartada/nueva 2902 · principal/descartada 196 · principal/nueva 27 · principal/postulada 25.
  - Medida con `huellas.py` sobre `ofertas_pre_laborum_20261020.db`, en la base real después del despliegue y otra vez
    después de las comprobaciones HTTP: idéntica las tres veces.
  - sha256 por tabla: ajustes (4) `8928191ee9f0b506cee48f285e4167b71105de6cf7871705417a6518c3797aec` ·
    alertas (0) `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` ·
    corridas (34) `f8049202517d2607d2da00f4fcf6c8f4dfdeb882e3f4d5cfc7827e59f2dbc87b` ·
    historial_estados (163) `7d6a3de93dc88df927ac509c6e41a107b865df01113021694fff144dc41eb61e` ·
    ofertas (3150) `26baf54b986d6481ed80451e74714e06d09534be3c555b81fc409de339a48629` ·
    pruebas_fuentes (0) `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` ·
    sqlite_sequence (2) `d0c4f1bdd2faf75f20ca7608fd23baf71f6899b09e387a55594a6f659c7ef285` ·
    terminos_no_disponibles (2) `0821946c3a741fa08fe0d2d793030aa14a531e6bf00096b4aa102d92f1e6d8c5`.
- **Última referencia (oficial):** `ofertas_pre_laborum_20261020.db` (volumen y
  `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256
  `c40c50f5a99b1450f86bc260e7a2c33b7ba5f28f64b891cfd3edd5909130b472` en las dos copias, integrity_check ok, journal
  delete. Tomada con el contenedor detenido (salida 0).
- **Desplegado el 20-10-2026 (Chumi y Laborum; reemplazado ese mismo día por la pausa JobSpy):** commit `e8abeee` (rama `feat/contadores-ubicacion`, sin push); imagen
  `job-tracker-jobtracker:latest` = `job-tracker:laborum`
  (`sha256:39378b0be7aaf453732037cb27fa6caad93ae7d9f6c99d5d739cc7e05315a5d3`, ~1,6 GB por Chromium); healthy en
  `127.0.0.1:8765`. Imagen anterior inmediata: `job-tracker:pre-laborum-20261020` (`6353e0b5…`).
  - GET `/`, `/api/estado`, `/api/ofertas`, `/api/respaldo`: 200; Host/Origin ajenos: 403; POST con origen inválido,
    sin origen o con campo no permitido: 400; Origin ajeno: 403; cuerpo sobredimensionado: 413; respaldo sin
    `error_auto`. La candidata respaldó bien (201, `sha256sum -c` OK). Los 79 respaldos y referencias anteriores
    conservaron su sha256. Reversión probada en copia (8767) y documentada en `REVERSION_FASE_A.md`.
  - Durante el paso 3 se creó por error un archivo vacío `/datos/=ro` en el volumen real; se comprobó vacío y se
    borró. No afectó la base (huellas idénticas).
  - **Decisión de Sofia (20-10):** regla de experiencia igual en TODAS las fuentes: rango con máximo de 2 o menos se
    muestra («0 a 2», «0-2», «1 a 2», «hasta 2»); un número solo, como mucho 1 año; lo demás se descarta. Ratifica
    `f8465ea`.
- **Despliegue del 19-10 sin registro (hallado el 20-10):** el 19-10 a las 20:45 se reconstruyó y levantó producción
  fuera del procedimiento (sin referencia, sin candidata, sin anotarlo), con el código hasta `326f427`: términos jr y
  junior nuevos, regla de experiencia generalizada y Computrabajo, Laborum y Buscojobs (que fallaban solos, sin cortar
  la corrida). Corrieron con esa versión las corridas 33 y 34. La base quedó sana.
- **Línea base anterior (16-10-2026, LinkedIn Senior/Experto; ya no vigente):** v7,
  integrity_check ok, 2046 ofertas, 18 corridas, 77 filas en `historial_estados`, 18 postuladas, 6 POR VERIFICAR;
  estados descartada/nueva 1908 · principal/descartada 119 · principal/entrevista 1 · principal/postulada 18.
  - Medida con `huellas.py` sobre `ofertas_pre_linkedin_senior_experto_20261016.db` y repetida en la base real
    después del despliegue y después de las comprobaciones HTTP: idéntica las tres veces.
  - sha256 por tabla: ajustes (4) `8928191ee9f0b506cee48f285e4167b71105de6cf7871705417a6518c3797aec` ·
    alertas (0) `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` ·
    corridas (18) `d0f41ce3679b057709e0c7d03bc16ef262e45ca61bfeb6008c148d5f630cccf7` ·
    historial_estados (77) `54cfb36f57bb84f27dc84ab0c6eda9663c2435188e9c2750745c144707fc4e05` ·
    ofertas (2046) `b983a93197af79447dee18ac5a2d98fa46de16e9b4fdc3d4ad776549ae5137bb` ·
    pruebas_fuentes (0) `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` ·
    sqlite_sequence (2) `982ad5fb96a03e4322ac57897c80df055d4dad26224ea78698d5cb8425e48d4c` ·
    terminos_no_disponibles (2) `0821946c3a741fa08fe0d2d793030aa14a531e6bf00096b4aa102d92f1e6d8c5`.
- **Mediciones anteriores (no mezclar sus cifras con la oficial):** la línea base del 16-10-2026, 12:35, fue v7,
  1967 ofertas, 17 corridas, 44 filas en `historial_estados`, 16 postuladas y 6 POR VERIFICAR; la del 15-10-2026,
  23:45, fue v7,
  1588 ofertas, 14 corridas, 15 filas en `historial_estados`, 16 postuladas y 6 POR VERIFICAR.
- **Medición del 15-10-2026, 18:53 (telemetría):** 1536 ofertas, 12 corridas, 14 historial, 15 postuladas.
  Referencia: `ofertas_pre_telemetria_20261015.db` (`844341c7…`).
- **Medición del 15-10-2026, mañana (solo conteos):** v7, integrity_check ok, 1321 ofertas, 9 corridas, 15 postuladas.
- **Medición del 14-10-2026:** 1223 ofertas, 7 corridas, 14 postuladas, `historial_estados` con 4 filas.
- **Referencia anterior (16-10; ya no es la última):** `ofertas_pre_linkedin_senior_experto_20261016.db` (volumen y
  `C:\Users\sofia\Respaldos\job-tracker-referencias\`), sha256
  `6a43f4cddac9fddbdf66d75a40738f629b9b28457049c4822e87188a83152a83` en las dos copias, integrity_check ok.
  Tomada con el contenedor detenido (salida 0); la copia de candidata y la referencia tienen huellas completas iguales.
- **Desplegado el 16-10-2026, 13:06 (reemplazado el 19-10 y luego el 20-10):** commit local `eb3a33e` (rama `feat/contadores-ubicacion`, sin push);
  imagen `job-tracker-jobtracker:latest` y `job-tracker:linkedin-senior-experto`,
  `sha256:da1024401f2cd33609bf5934a2293ce56873872b633d69c335d0234b9ca31369`.
  - Reconstruida con `docker compose build` y levantada con `docker compose up -d`; `jobtracker` healthy en
    `127.0.0.1:8765`.
  - Imagen anterior inmediata: `job-tracker:linkedin-senior-anterior-20261016`
    (`sha256:915bc9fd6217faac57431091bf4804844f5119592c15e52c5f989cc677ad6694`).
  - GET `/`, `/api/estado`, `/api/ofertas` y `/api/respaldo`: 200; Host/Origin ajenos: 403; POST sin Origin y con
    campos no permitidos: 400; cuerpo sobredimensionado: 413. `GET /api/respaldo` sin `error_auto`.
    Las huellas completas, conteos, estados y los ocho objetos/tablas quedaron idénticos antes/después y tras las
    comprobaciones. Los 59 archivos previos de referencias y respaldos externos/en volumen conservaron sus hashes.
  - Filtro LinkedIn: descarta Senior y Experto/Expert; Associate sigue aceptándose. Se mantiene el descarte si el
    máximo requerido supera 2 años. No reclasifica ofertas guardadas ni altera datos/esquema. Reversión a la imagen
    anterior probada en copia, healthy y con huellas idénticas; ver `REVERSION_FASE_A.md`.
- **Imágenes para volver atrás:** `job-tracker:pausa-jobspy` (`d40d7a99…`; producción actual),
  `job-tracker:laborum` = `:pre-pausa-20261020` (`39378b0b…`; reversión inmediata), `job-tracker:pre-laborum-20261020` (`6353e0b5…`; la versión del 19-10),
  `job-tracker:linkedin-senior-experto` (`da102440…`; la última desplegada por procedimiento antes del 19-10), `job-tracker:linkedin-senior-anterior-20261016`
  (`915bc9fd…`; reversión inmediata), `job-tracker:linkedin-mid-senior` (`915bc9fd…`),
  `job-tracker:linkedin-filtros-23241` (`d4d6b534…`; anterior a esos filtros),
  `job-tracker:linkedin-filtros` (`d4d6b534…`; etiqueta anterior del mismo artefacto),
  `job-tracker:linkedin-229f` (`d4529c34…`; anterior a los filtros),
  `job-tracker:telemetria` (`ad7b2b19ced7…`; reversión en `REVERSION_FASE_A.md`),
  `job-tracker:137` (`ff5a2615…`), `job-tracker:c2` (`f1943914…`), `:c1`, `:respaldo`, `:B1`, `:genero`, `:soporte`,
  `:faseA`, `:fase0`.
- **Candidata y reversión (20-10):** la candidata `jt_revision_laborum` (8766), sus volúmenes y la reversión en 8767
  se borraron después del despliegue.
- **Limpieza aprobada y hecha (20-10):** las 10 etiquetas `*-candidata`, los contenedores `jt_revision_c2`, `_137`,
  `_137r`, `_telemetria`, `_telemetria_rev` y sus 9 volúmenes. Se borró por etiqueta: las imágenes de reversión que
  compartían id (`telemetria`, `137`, `c2`) siguen. No quedan candidatas ni contenedores de revisión.
- **Pausa JobSpy (desplegada el 20-10):** LinkedIn 6-10 s, Glassdoor 3-5 s; ante un 429 la fuente se deja por el
  resto de la corrida. Suma ~8 min por corrida.
- **Push autorizado por Sofia el 20-10** (rama `feat/contadores-ubicacion`, sin forzar; `main` no se tocó). La regla
  permanente sigue siendo «sin push» salvo que ella lo pida.
- **Candidata y reversión (16-10):** la candidata `jt_revision_linkedin_senior_experto` (8766) y su volumen se eliminaron
  después del despliegue; la reversión sobre copia en 8767 también quedó healthy y se limpió. No quedan recursos
  temporales de este despliegue.
- **Decisiones aprobadas:** LinkedIn descarta Senior y Experto/Expert, mantiene Associate, y descarta requisitos cuyo
  máximo supera 2 años. Ubicación, remoto y exclusión de BairesDev siguen como antes. Despliegue autorizado y hecho;
  sin preguntas abiertas. Sin push.
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

### LinkedIn y Glassdoor llegan sin descripción (21-10-2026; commit local, SIN desplegar)

**Hallazgo.** Sofia avisó que seguían apareciendo ofertas que piden años de experiencia. No era la regla de
experiencia: `clasificar()` lee los años de `description`, y **LinkedIn y Glassdoor llegaban sin descripción**.
Medido sobre el respaldo `ofertas_manual_20261021-124153.db` (3500 ofertas, solo lectura): LinkedIn 1138 ofertas,
las 1138 sin texto; Glassdoor 102 de 102; las demás fuentes, 0 sin texto (Indeed trae 3140 caracteres de media).
De las 286 ofertas visibles, **180 eran de LinkedIn/Glassdoor y las 180 mostraban experiencia «No indicada»**.
Causa: `consulta()` no le pasaba `fetch_description` a JobSpy, y ese parámetro viene en `False` por omisión
(`jobspy/linkedin/__init__.py:147`, `jobspy/glassdoor/__init__.py:98`). Sin texto tampoco actuaban `SENIORITY_DESC`,
`SOSPECHOSA_DESC`, contrato, sueldo, señales del tipo B ni los tres chequeos propios de LinkedIn
(`_linkedin_nivel_mid_senior`, `_linkedin_nivel_senior`, `_linkedin_experto`: eran código muerto, se escribieron
para `linkedin.py`, que no está conectado).

**Cuánto se colaba.** Se tomaron las 2258 ofertas que sí traen texto, se les tapó la descripción y se reclasificaron:
pasan el filtro a ciegas 197, de las cuales **107 (54 %) con el texto se habrían descartado** (31 «exige 2+ años»,
23 «3+», 22 práctica/estudiante, 13 semi senior/senior, 7 «5+», y hasta 9+ años). Es decir, de las 182 visibles sin
texto, ~100 no correspondían y ~70 por años de experiencia.

**Por qué LinkedIn no se arregla pidiendo el detalle.** Su `robots.txt` termina en `User-agent: *` / `Disallow: /`
(y `Disallow: /jobs-guest/` para cada buscador con nombre). Conectar `linkedin.py` lo bloquearía `robots.py`, y
`fetch_description=True` en JobSpy serían ~2000 solicitudes por corrida a `/jobs-guest/` (una por oferta: 23 términos
× 3 lugares × hasta 30) en vez de 69. **Nota para decidir:** JobSpy ya pide hoy ese endpoint prohibido para el
listado (`jobspy/linkedin/__init__.py:75`); al ir dentro de la librería nunca pasó por `robots.py`. Queda abierto si
LinkedIn se mantiene así o pasa a «Buscar a mano» como Computrabajo y Empleos Públicos.

**Qué no sirvió** (medido, no supuesto): el título no suple al texto. Ninguna señal paga (`full stack` sin «junior»
corta 9 malas y pierde 8 buenas; `consultor` 5 y 3; `especialista` 1 y 3) y exigir «junior/jr» en el título cortaría
102 malas perdiendo 71 de las 90 buenas. Cruzar cada oferta ciega con su gemela de otra fuente (misma empresa, título
parecido) encontró **4 gemelas en 182**, una de ellas falso positivo: las ofertas de LinkedIn casi no se repiten en
las otras fuentes.

**Cambios hechos (tres, aprobados por Sofia el 21-10).**
1. **Categoría `sin_descripcion`** (pestaña «Sin texto»): la oferta pasa todo lo que se puede revisar con el
   título (empresa excluida, práctica, rol, zona, seniority del título) y queda en su propia lista, con
   `experiencia = "Sin verificar"` y el aviso `config.AVISO_SIN_TEXTO` en el motivo. Se gestiona igual que Ofertas
   (estado, fases, notas); «❌ Descartada» la saca de la cola y la oferta ya no vuelve a entrar como nueva.
   El nombre NO es «por verificar»: esa marca ya existe en `notas` (unión de bases) y `huellas.py` la vigila.
   Decide por dato, no por fuente: `not description and fuente in config.FUENTES_SIN_TEXTO`.
2. **Glassdoor pide la descripción** (`fetch_description=True` en `consulta()`): su `robots.txt` no tiene
   `Disallow: /` general y el detalle va por el mismo endpoint `/graph` del listado, uno por cada 25 ofertas
   (~80 solicitudes más por corrida). A LinkedIn no se le pasa.
3. **Regla de experiencia más completa**: manda la mención **más exigente**, no la primera («1 año en mesa de ayuda
   y 5 años en redes» pide 5); se reconocen «3 años en cargos similares» (sin la palabra experiencia), «tres años»,
   «cinco (5) años», «exp.» y «yrs»; el contexto es la frase del número, sin cruzar el punto; los años de la empresa
   («12 años en el mercado») no cuentan; y **lo deseable no descarta** pero se avisa en el motivo con
   «⚠ experiencia deseable (no exigida): N años».

**Antes/después** (mismo `raw`, código de `HEAD` vs. el nuevo, 3498 ofertas del respaldo): principal 264 → 97,
`sin_descripcion` 0 → 169 (164 LinkedIn + 5 Glassdoor), descartada 3234 → 3232. Cambian 171: 169
principal → `sin_descripcion` y 2 descartada → principal (las dos por «deseable»: «se valorará experiencia de 5 años
o más» en BNE y «experiencia deseable de 1 a 3 años» en Laborum; ahora se ven con el aviso). **Ninguna oferta pasa a
descartada por la regla nueva** y ningún texto de experiencia cambia: los avisos de las fuentes con texto ya venían
escritos de la forma que la regla vieja reconocía. En la página: Ofertas 22 → 8, «Sin descripción» 0 → 16 (las 16 de
LinkedIn, todas nuevas), Seguimiento 23 → 23.

**Arreglos de la revisión de la candidata (21-10, pedidos por Sofia).**
- La pestaña se llama **«Sin texto»**, no «Sin descripción»: el aviso SÍ tiene descripción en LinkedIn; lo vacío es
  lo que recibe la app (`description = ''` en las 16 de la cola). El nombre describía el aviso y se leía al revés.
- **El tope se dice:** «hasta 2 años» en vez de «2 años». El chip de «recién titulado o con hasta 2 años» se leía
  como si el aviso exigiera 2 años. Al hacerlo salió un error anterior: `al menos de 1 año` entraba por `menos de`
  y se leía como tope; ahora `_TOPE` lo excluye (3 avisos de Chiletrabajos lo decían así).
- **La marca de remoto nombra a su fuente:** una oferta de LinkedIn decía «marcada remota por Indeed». La constante
  pasó a ser `EVIDENCIA_MARCA_FUENTE` (la lógica de `remoto_firme` la sigue comparando igual) y el nombre se pone al
  mostrarla. En la base: 17 de LinkedIn y 5 de Chiletrabajos; **ninguna de las 22 era de Indeed**.
- **Avisos en inglés** (75 de 1795 con texto; 73 ya se descartaban): se agregó `similar role/position`,
  `in the field/industry` al contexto de los años, y al contrato `fixed-term`, `N months` y `temporary`. Efecto en
  la base: 2 ofertas de LinkedIn «Python Full Stack Engineer (3 month-long)» pasan a Plazo fijo / temporal; ninguna
  oferta nueva se descarta.

**Pendiente de este cambio:** no está desplegado. El despliegue necesita `reclasificar` para que las ofertas de
LinkedIn/Glassdoor ya guardadas que hoy están como `principal` pasen a `sin_descripcion` (169 de las 1240 de esas dos
fuentes; el resto ya estaba descartado por título, zona o empresa), y hay que fijarse en que
`huellas.py` cuenta `por_verificar` por la marca en `notas` (debe seguir en 6), no por esta categoría nueva.
El ajuste «Incluir soporte TI» no toca esta pestaña: la cola muestra todo lo que necesita tus ojos.

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

## Exploración de fuentes de empleo adicionales (16-10-2026; sin cambios en el proyecto)

Sofia pidió evaluar otras fuentes chilenas antes de decidir si conviene incorporarlas. Esta exploración fue manual,
con páginas públicas en navegador y consultas informativas de `robots.txt`; no se inició sesión, no se usaron enlaces
de postulación ni se intentó sortear bloqueos. No se cambió código, configuración, base, contenedores ni imágenes, y
no se hizo push. Jooble se descartó por decisión de Sofia. FirstJob se dejó abajo en prioridad porque lo observado
estaba centrado en prácticas.

### Alcance y método de la revisión del 16-10

- Se tomaron como referencia los 29 términos configurados en `TERMINOS_A` y `TERMINOS_B`:
  `analista funcional`, `QA`, `testing`, `tester`, `analista de pruebas`, `business analyst`,
  `análisis de requerimientos`, `BPMN`, `automatización de procesos`, `desarrollador python`,
  `desarrollador backend`, `desarrollador junior`, `desarrollador frontend`, `analista de sistemas`,
  `analista de datos junior`, `reportería BI`, `informático junior`, `analista de procesos`, `mejora continua`,
  `datos maestros`, `master data`, `analista de reportería`, `control de gestión`, `usuario clave`, `key user`,
  `analista SAP`, `analista de implementación`, `analista de operaciones`, `PMO` y `asistente de proyectos`.
- En Talent.com se probaron los 29 en Santiago y Viña del Mar. En Computrabajo se probaron los 29 en Santiago y
  Valparaíso. Los portales devuelven coincidencias por relevancia, pueden presentar resultados repetidos o fuera de
  la ciudad consultada y la revisión se limitó a los resultados visibles; no es un rastreo exhaustivo de todas las
  páginas ni de todas las ofertas.
- Empleos Públicos se revisó mediante sugerencias del buscador para los 29 términos; la búsqueda de convocatoria
  completa no pudo validarse como un proceso estable. Laborum no se pudo probar con todos los términos de forma
  compatible con sus restricciones.
- Un rótulo como «actualizado hace X horas» no demuestra que el aviso se haya publicado en ese plazo. Se priorizó
  la fecha explícita del detalle cuando fue posible y se distinguió entre publicación y actualización.
- No se compararon las ofertas resultantes con la base real ni se pudo medir cuántas serían nuevas frente a Indeed,
  Glassdoor, Get on Board, BNE, Trabajando, Chiletrabajos y LinkedIn. Por tanto, los conteos de resultados no
  representan aportes incrementales deduplicados.

### Resultados por fuente candidata

**Computrabajo Chile (`cl.computrabajo.com`)**

- La página de resultados se pudo leer con navegador; una descarga directa/consulta simple había devuelto 403. El
  `robots.txt` se leyó desde el navegador: permite las páginas base de búsqueda probadas, pero prohíbe rutas de
  ofertas con parámetros como `pubdate=`, además de rutas de perfiles y servicios. No usar las rutas prohibidas ni
  intentar eludirlas.
- La búsqueda de Santiago devolvió ofertas recientes, pero buena parte de las coincidencias examinadas no servía:
  cargos Senior o con 3–5+ años, prácticas, funciones comerciales o resultados que solo coincidían por texto.
  Ejemplos: QA Automation actualizado hace 9 horas pedía 3 años; QA Engineer senior pedía 4+; Full Stack remoto
  pedía 2 años o más (el criterio vigente descarta requisitos cuyo máximo supera 2).
- En la búsqueda amplia de Valparaíso apareció **Desarrollador/a Power Platform Jr – Casablanca, V Región**
  (Kibernum), publicado/actualizado «Ayer»; el detalle acepta experiencia laboral inicial, práctica o proyectos
  académicos y el portal declara 1 año de experiencia. Es presencial en Casablanca. Puede ser pertinente por rol y
  experiencia, pero no cumple literalmente las ciudades objetivo actuales (Santiago, Valparaíso o Viña); tampoco se
  autorizó ampliar ubicaciones a Casablanca.
- También apareció **Encargado(a) de Soporte Informático – Concón**, con 5 años de experiencia, por lo que se
  descarta. Los listados de Valparaíso incluyeron avisos de Santiago y otras localidades; el filtro del portal no
  garantiza ubicación exacta.
- Evaluación: técnicamente consultable en navegador y con alguna oferta junior potencial, pero no se confirmó un
  aporte compatible con las ubicaciones aprobadas ni se deduplicó con producción. Mantener como candidata
  exploratoria; no integrar.

**Talent.com (`cl.talent.com`)**

- Se pudieron leer páginas públicas de resultados y algunos detalles. El `robots.txt` prohíbe `/search-jobs/*`,
  `/services/api-new/search`, redirecciones de postulación y otras rutas; no usarlas. Las páginas públicas
  `/jobs?...` consultadas no fueron bloqueadas en esta prueba. Respetar siempre las reglas vigentes del sitio.
- Santiago: de los resultados recientes visibles para los 29 términos hubo mucho solapamiento y ruido. Ejemplos
  potencialmente afines: **QA Automatizador COD:MET044** (Santiago, actualizado hace 1 hora; la ficha visible no
  detalló años de experiencia) y **Técnico de Centro de Datos, DCO** (Santiago, hace 3 horas; sus requisitos
  incluyen experiencia práctica en hardware, Linux y redes; no se confirmó ajuste junior). **Analista de Datos de
  Negocio** de Tenpo pedía entre 2 y 4 años, así que excede el máximo admitido.
- Viña/Valparaíso: los términos devolvieron coincidencias repetidas y contenido irrelevante, además de puestos
  remotos con ubicación etiquetada Valparaíso. **Associate Forward Deployed Engineer – Remote** de YO AI Labs
  (hace 7 horas; el detalle anuncia trabajo remoto de tiempo completo para ingenieros junior y no especifica años)
  es potencialmente afín, pero su elegibilidad geográfica/país no quedó confirmada. No asumir que por indicar
  Valparaíso como ubicación el puesto esté abierto a Chile.
- Evaluación: candidata más prometedora para observación por el posible puesto remoto junior; aún no hay prueba de
  elegibilidad local ni de ofertas incrementales frente a las fuentes actuales. No integrar por ahora.

**Empleos Públicos (`empleospublicos.cl`)**

- La descarga directa del inicio y de `robots.txt` devolvió 403, pero el navegador mostró el portal público. El
  listado inicial contenía convocatorias de múltiples áreas. Las sugerencias de los 29 términos dieron algunos
  cargos de procesos, sistemas y automatización; la mayoría no produjo sugerencias directas o trajo puestos de
  otras regiones/funciones.
- Se había localizado una convocatoria técnica de Gendarmería en Puente Alto relacionada con estadísticas y un
  sistema informático, con cierre el 19-10-2026; no se confirmó que sus tareas ni el perfil fueran adecuados.
  Algunos títulos detectados por sugerencias eran de analista de procesos en Santiago, pero no se validaron sus
  bases, antigüedad ni requisitos contra el criterio de experiencia.
- El formulario completo no se pudo probar de manera repetible; escribir en el autocompletado no equivale a
  verificar todos los resultados. La fecha de esta revisión es histórica y las convocatorias pueden haber vencido.
- Evaluación: puede contener cargos TI públicos, pero pertinencia junior, ubicación y consulta completa quedan sin
  validar. Mantener como referencia manual, no como conector.

**Laborum (`laborum.cl`)**

- La página necesita JavaScript: la descarga HTML simple solo mostró que hacía falta JavaScript. El `robots.txt`
  permite determinados sitemaps/listados, pero bloquea rutas/parámetros de búsqueda, incluidos `recientes=true`,
  `relevantes=true` y `localidades`. Un endpoint observado en la página devolvió 403 al consultarlo directamente;
  no se probaron cabeceras, cookies ni otras formas de evadirlo.
- En una prueba anterior, en listados permitidos de Santiago y Las Condes se observaron avisos potencialmente
  pertinentes, pero varios tenían muchos días. **Desarrollador/a Full Stack Junior** tenía requisito de 0–2 años,
  pero fecha de publicación 22-09-2026; el rótulo «actualizado hace 2 horas» no lo hacía nuevo. Dos avisos de
  automatización/IA publicados el 08-10 y 10-10 no especificaban un máximo de años.
- No se recorrieron los 29 términos: robots/403 impiden afirmar que la fuente se haya evaluado exhaustivamente.
- Evaluación: no integrar mientras no exista una vía pública permitida y verificable para buscar.

**Mipleo Chile (`mipleo.cl`)**

- La página principal indicó 0 trabajos. Su `robots.txt` prohíbe búsquedas con el parámetro `q`; no se consultaron
  rutas de búsqueda bloqueadas.
- Evaluación: no aportó resultados y se deja fuera de la evaluación adicional por ahora.

**FirstJob (`firstjob.me`)**

- La página revisada mostraba un programa de prácticas. No se recorrieron los 29 términos; se dejó en baja
  prioridad porque las prácticas no son el objetivo de búsqueda actual.

### Decisión y preguntas abiertas

- No se aprueba ni se inicia la integración de ninguna fuente nueva; no se hicieron cambios de código, configuración,
  base de datos o Docker. Jooble queda descartado por preferencia de Sofia.
- Talent.com y Computrabajo pueden quedar en observación, pero antes de proponer integración habría que confirmar
  una muestra mayor de avisos que cumplan fechas, requisitos y ubicaciones, y medir la deduplicación contra la base
  real solo mediante el procedimiento autorizado (sin tocar la base real fuera del despliegue).
- Empleos Públicos queda para consulta manual; Laborum requiere una vía de lectura permitida; Mipleo no mostró
  ofertas; FirstJob parece centrado en prácticas.
- **Pendiente de decisión:** si se amplía el criterio territorial para aceptar Casablanca y otras comunas de la
  Región de Valparaíso. La regla documentada/configurada hasta ahora es Santiago, Viña del Mar y Valparaíso; no se
  amplió con esta exploración.
- Esta nota registra una investigación exploratoria, no una autorización de implementación, despliegue o push.

## Portales del 19-10 en pausa (20-10-2026; commit local, sin desplegar)

- Los commits fc2ec30, 326f427 y f3c1510 (19-10) integraron Computrabajo, Laborum, Buscojobs, Empleos Públicos,
  Chumi y EmpleosTech sin aprobación, sin tests y con selectores y URLs supuestos («requiere verificación»), contra
  la decisión del 16-10. Además, los seis parsers lanzaban `TypeError` con cualquier tarjeta que trajera empresa o
  ubicación (`_limpio` recibía el elemento HTML), y como nada lo capturaba, abortaban la corrida entera sin registrarla.
- Aprobado por Sofia (opción B de la revisión del 20-10):
  - los seis salen de `config.SITIOS` y `buscar.PORTALES`; sus módulos y términos quedan en el repositorio;
  - se corrige el error de `_limpio` en los seis (probado solo con una tarjeta sintética, NO con el sitio real);
  - `buscar_ofertas` captura el fallo inesperado de un portal: anota el error y un aviso, sigue con los demás
    y la corrida se registra igual;
  - se completan las variantes «jr» de los términos «junior» agregados el 19-10 (test en rojo);
  - typo `TERMINOS_EMPLOSTECH` -> `TERMINOS_EMPLEOSTECH`.
- LinkedIn no cambia: va por JobSpy desde 229f120 (16-10) por el `Disallow: /` de su `robots.txt`; `linkedin.py`
  queda solo con sus tests de parseo.
- Para reactivar un portal, uno a la vez y con aprobación: confirmar que su `robots.txt` y sus condiciones lo
  permiten (Laborum y Computrabajo tenían restricciones), guardar HTML real en `tests/fixtures`, ajustar selectores
  y URL, y escribir su test de parseo y de flujo.
- Hecho después: imports sin uso eliminados (los seis y `linkedin.py`); `CLAUDE.md` y `README.md` al día.
- Los términos con guion de estos portales no se corrigieron: las URLs de búsqueda que usan son inventadas, así
  que corregir el formato no arregla nada. Se rehacen junto con el módulo, si alguno se aprueba.

### ¿Se pueden implementar? (sondeo del 20-10-2026)

Método: una lectura de `robots.txt` y de una o dos páginas por sitio con `red.ClienteHTTP` y `robots.GestorRobots`,
es decir, el mismo User-Agent, las mismas pausas y la misma regla de detenerse ante 401/403/429 que usa la app. Sin
sesión, sin navegador, sin reintentos. También se leyeron las condiciones de uso cuando se encontraron. Los HTML
quedaron fuera del repositorio (en %TEMP%\jt-sondeo).

| Fuente | Resultado | ¿Implementable? |
|---|---|---|
| Computrabajo | `robots.txt` responde 403 → `GestorRobots` lo trata como bloqueo | No, con las reglas actuales |
| Empleos Públicos | dominio real `www.empleospublicos.cl` (el módulo usa `.gob.cl`); `robots.txt` responde 403 | No; queda para consulta manual |
| Buscojobs | `robots.txt` se lee, la portada responde 403 | No, con las reglas actuales |
| Laborum | `robots.txt` permite `/empleos-busqueda-*.html`, pero la página solo dice «You need to enable JavaScript» | No sin navegador o sin la API interna (no documentada) |
| EmpleosTech | el dominio `empleostech.cl` no existe (DNS) | No: el sitio no existe |
| Chumi (chumi-it.com) | `robots.txt` permite todo salvo áreas privadas. `/jobs?q=` no trae ofertas en el HTML, pero `/trabajos?page=1..5` lista ~25 ofertas por página con enlace `/trabajos/<slug>` (23 de 25 en Chile), y el detalle trae JSON-LD `JobPosting` con `datePosted`, `validThrough`, empresa, sueldo y descripción completa | Sí técnicamente, reescribiendo el módulo. Sus Condiciones de Uso (punto 2) prohíben «copiar, descargar, distribuir… por completo o en parte» el sitio: decide Sofia |
| Talent.com (en observación desde el 16-10) | `/jobs?k=…&l=…` y `/view?id=` permitidos por `robots.txt` y con tarjetas en el HTML | No: sus Terms of Service prohíben el «scraping» «for any purpose» |

- Chumi también lista avisos ajenos (de LinkedIn, empleosit.com.ar) en sus páginas por categoría; en `/trabajos`
  los enlaces son propios. Si se implementa, solo se abrirían detalles de `chumi-it.com`.
- Chumi: implementación aprobada por Sofia el 20-10 (ver abajo). Pendiente de decisión: si se borran los cinco
  módulos que no pueden funcionar (computrabajo, laborum, buscojobs, empleospublicos, empleostech).

### Chumi integrado (20-10-2026; commit local, sin desplegar)

- `chumi.py` rehecho sobre el HTML real: lee `/trabajos?page=1..3` (`TERMINOS_CHUMI` son páginas: el sitio no tiene
  búsqueda en HTML) y abre el detalle (JSON-LD `JobPosting`) de las candidatas, con tope `MAX_DETALLES["chumi"] = 10`.
  Fixtures reales: `tests/fixtures/chumi_trabajos.html` y `chumi_detalle.html`.
- La tarjeta no trae fecha y el listado no va por fecha (mezcla avisos de agosto). `_buscar_portal` ahora revisa la
  antigüedad DESPUÉS del detalle: una candidata antigua no se guarda, cuenta como antigua y su URL se recuerda 30 días
  en `terminos_no_disponibles` para no gastar el tope en ella cada corrida. Las no candidatas se guardan sin fecha
  (como cualquier oferta sin fecha).
- Ubicación: casi siempre «Chile» a secas; se deja así (como Glassdoor), sin región. El sueldo en USD va como texto
  («Sueldo informado (Chumi)»), no en min/max_amount, para que no se compare en pesos con `SUELDO_ALERTA`.
- Corrida real sobre una base temporal (no la real): 13 peticiones, 75 ofertas, 0 errores, 9 detalles antiguos
  omitidos, 0 relevantes nuevas. Casi todo es de IT-Talent (headhunter) y de nivel senior: aporte esperado bajo.

### Computrabajo, Laborum y Empleos Públicos: ¿automatizables? (20-10-2026)

- Computrabajo y Empleos Públicos responden 403 a la app, que se identifica como bot, ya desde el `robots.txt`;
  en un navegador abren. Automatizarlos exigiría hacerse pasar por navegador: contra la regla de `red.py`
  («no se disfraza; nunca se esquiva»).
- Laborum no bloquea: su `robots.txt` permite la búsqueda, pero búsqueda y detalle exigen JavaScript (la misma
  página vacía de 63.603 bytes). Publica `sitemap_avisos_bum.xml` (16.399 avisos el 20-10) con el título en la URL,
  pero sin empresa, ubicación ni fecha (`lastmod` es la fecha del sitemap). Sus términos no se pudieron leer (también
  exigen JavaScript). Vías posibles: navegador sin ventana (Playwright: instalar algo, requiere aprobación) o su API
  interna (no documentada).
- Empleos Públicos: existe un espejo de terceros con API (Governance_Lab, govlab.cl, en una Raspberry Pi); no es
  oficial.

### Playwright: Laborum integrado; los demás, a mano (20-10-2026; commit local, sin desplegar)

- Aprobado por Sofia: instalar Playwright (1.64.0 + Chromium headless shell en el venv), integrar Laborum, botones de
  búsqueda manual y probar los demás con Playwright.
- Prueba con Playwright y el MISMO User-Agent de la app (`BuscaEmpleo/0.1`): Computrabajo (robots.txt y búsqueda),
  Buscojobs y Empleos Públicos (robots.txt y convocatorias) responden **403 Forbidden** también con navegador real.
  Rechazan al visitante que se declara bot; solo pasarían con un User-Agent de navegador, y eso no se hace. Los
  módulos `computrabajo.py`, `buscojobs.py`, `empleospublicos.py` y `empleostech.py` se borraron (quedan en git,
  commit 537367c y anteriores).
- Laborum (`laborum.py`): con Playwright la página responde 200 y pide `POST /api/avisos/searchV2`; se lee esa
  respuesta (la de la propia página, no una llamada aparte), que trae la descripción completa: no se abren detalles
  (`SIN_DETALLE`, `MAX_DETALLES["laborum"] = 0`). Se cortan los recursos de otros dominios (rastreadores), las
  imágenes y las tipografías. Respeta robots.txt, la pausa de `ClienteHTTP.esperar_turno()` y se detiene ante
  401/403/429. Orden por relevancia (ordenar por fecha usa `recientes=true`, prohibido por su robots.txt), así que
  muchas de las 20 de cada término son antiguas y se omiten.
- Corrida real (base temporal): 3 términos en 17 s, todas las respuestas 200, 3 recientes guardadas (descartadas por
  experiencia o señales), 28 antiguas omitidas. Con los 13 términos de `TERMINOS_LABORUM`: ~75 s más por corrida.
- Docker: `requirements.txt` incluye playwright y el `Dockerfile` instala Chromium con sus librerías
  (`playwright install --with-deps --only-shell chromium`). **Imagen sin construir ni probar**; crecerá varios
  cientos de MB. Va en el próximo despliegue, con su candidata.
- Página: sección «🔎 Buscar a mano» bajo el botón Buscar, con enlaces a Computrabajo (6 términos,
  `trabajo-de-<término>`, formato comprobado) y a las convocatorias de Empleos Públicos.
