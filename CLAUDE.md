# job-tracker

Buscador de empleos personal de Sofia (Python + SQLite + página local). Responder SIEMPRE en español.

Al empezar una sesión, leer la sección "Estado actual" de `NOTAS.md`: línea base de la base de datos, lo que está
en producción, lo aprobado y lo pendiente.

## Reglas permanentes (no se negocian)
- Aprobación explícita en el chat antes de cualquier cambio importante: código que se despliega, base de datos,
  contenedor, configuración (~/.claude, settings.json), instalar algo. Una aprobación vale para ESE cambio.
- No leer correos. No ingresar credenciales. Solo herramientas gratuitas.
- Code no postula, no escribe cartas ni contacta empresas por Sofía; la app solo registra lo que ella hace.
- Sin push. El repositorio de GitHub es privado; aun así se trabaja por reglas, nunca por listas de URLs.
- Commits locales con autor 82609823+Soofiaa@users.noreply.github.com y la línea Co-Authored-By.
- Nunca tocar la base real ni el contenedor real fuera del procedimiento de despliegue (skill `/desplegar`).
- Sofia usa la página mientras se trabaja: detenerse si algo antes ≠ después o si cambia el estado de una oferta.

## Estructura
- `buscar.py`: base de datos (conectar, migraciones, transaccion), búsqueda, seguimiento (marcar, nota, manual),
  historial de estados, exportar. `VERSION_DB = 7`.
- `telemetria.py`: telemetría pasiva de corridas, solo contadores por fuente en `corridas.detalle` (sin URLs ni
  términos; JobSpy se mide como consultas).
- `filtros.py`: clasificar (tipos A/B/S/M, SAP/ERP, soporte), sin_genero, plural, ahora_chile.
- `config.py`: perfil, reglas de clasificación, rutas (`JT_DB`, `JT_RESPALDOS`).
- `servidor.py`: HTTP (ThreadingHTTPServer), rutas /api/*, Host/Origin locales, límites de cuerpo por ruta.
- `web/pagina.html`: la página (informe.PAGINA la lee). Funciones puras entre `// <puras>` y `// </puras>`.
- `respaldo.py`: respaldos (API de backup, sha256, retención 30). `unir_bases.py`: unión de una vez (exenta).
- Portales: `bne.py`, `trabajando.py`, `chiletrabajos.py`, `chumi.py`, `getonboard.py`; red: `red.py`, `robots.py`, `geo.py`.
  LinkedIn va por JobSpy (`config.SITIOS`); `linkedin.py` (endpoint de invitados) no está conectado, solo tiene tests.
- En pausa, fuera de `SITIOS` y `PORTALES` (ver NOTAS.md, 20-10): `computrabajo.py`, `laborum.py`, `buscojobs.py`,
  `empleospublicos.py`, `empleostech.py`. Ninguno funciona contra el sitio real.
- `tests/`: pytest (incluye funciones puras de la página corridas con Node).
- Notas: `NOTAS.md` (estado actual, decisiones y hallazgos), `REVERSION_FASE_A.md` (cómo volver atrás de cada
  despliegue). Skill de despliegue: `.claude/skills/desplegar/`.
- Scripts sueltos no desplegados: `diagnostico*.py`, `probar_*.py`, `prueba.py`.

## Pruebas
- `venv/Scripts/python.exe -m pytest -q` desde `job-tracker/`. Mostrar solo el resumen y los fallos.
- Todas en verde antes de cualquier commit. Pruebas nuevas para cada cambio.

## Reglas de código
- Página: todo el DOM con `h()`/`textContent`; nunca `innerHTML` con datos. CSP sin recursos externos
  (tipografías locales en `web/fuentes`, lista blanca).
- Base: escrituras con `transaccion(con)` (BEGIN IMMEDIATE); base ocupada → 503; errores de datos → `ErrorDatos`.
- **Solo `_cambiar_seguimiento()` escribe estado, fase y fecha_postulacion** (lo vigila tests/test_fase_c1.py).
- `historial_estados` es aditiva (la base sigue en v7) y solo de agregado (triggers). Una migración que reconstruya
  `ofertas` debe recrear sus triggers (`buscar.DDL_HISTORIAL`).
- Orígenes del historial: tablero, lista, modal (los envía la página); manual y deshacer (los pone el servidor).
- Rutas y carpetas fijadas por configuración, nunca por un pedido. Límites de cuerpo por ruta (413).
- Singular/plural con `plural()` (Python) y `TXT`/`plural()` (JS).

## Docker
- Real: contenedor `jobtracker`, 127.0.0.1:8765, compose `name: job-tracker`, volumen `job-tracker_jt_datos`
  (nunca `down -v`), respaldos en `C:/Users/sofia/Respaldos/job-tracker` (fuera de OneDrive).
- Candidata: 127.0.0.1:8766, contenedor y volumen `jt_revision_<nombre>`, sobre una COPIA hecha con la API de
  backup en solo lectura. Se borra después del despliegue.
- Imágenes etiquetadas para volver atrás: fase0, faseA, soporte, genero, B1, respaldo (y la de cada despliegue).

## Formato de los reportes
Resultado, tabla antes/después (completa: conteos, sha256, integrity_check, tablas) y preguntas abiertas.
Sin recapitular los pasos. Las verificaciones críticas nunca se resumen ni se cortan.

# Compact instructions

Al compactar, conservar SIEMPRE y textual:
- la línea base de la base de datos (versión, conteos por tabla, postuladas, sha256 de la última referencia);
- las aprobaciones: qué está aprobado, qué espera aprobación y las preguntas abiertas sin respuesta;
- los commits (hash y tema) desde el último push, y las etiquetas de imagen;
- el estado de candidatas y contenedores (qué corre, en qué puerto, sobre qué copia);
- las reglas permanentes de arriba y cualquier regla nueva que Sofia haya dado en la sesión.
Se puede descartar: salidas de pruebas en verde, lecturas de archivos, exploraciones que no llevaron a nada.
