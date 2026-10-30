# Notas del proyecto: estado actual

Este archivo solo lleva el estado vigente, la línea base y lo pendiente. El historial completo de despliegues,
hallazgos y decisiones (desde el 13-10-2026) está en `NOTAS_HISTORIAL.md`. Si algo aquí no cuadra con ese historial,
manda lo más reciente y corrige la nota.

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Vigente: textos de «Sin texto» (30-10-2026)**, commit `7042206` sobre la descripción de LinkedIn (`2492207`,
  `f348b48`; rama `feat/unificar-ofertas`, con push). Imagen `job-tracker-jobtracker:latest` =
  `sha256:6d225a2500ce12ec49a064bda0decc682baec8d0a9b1f6634ce4d1039d9e976d`, healthy en `127.0.0.1:8765`.
- Imagen anterior para volver atrás: `job-tracker:pre-textos-sintexto` (`sha256:6ed8d23e…`).
- Referencia: `ofertas_pre_textos_sintexto_20261030.db`, sha256 `6b498bdd64ec816f857325a8a0237ada8c8246b858b505777d3b4d21bc6c923c`,
  integrity_check ok. Procedimiento de reversión en `REVERSION_FASE_A.md`.
- Cambios: LinkedIn trae la descripción con JobSpy (`fetch_description`, decisión de Sofia pese a robots.txt); modelo
  de Groq `qwen/qwen3.8-27b`; se quitó la regla «Sin push»; la página y el tutorial ya no dicen que LinkedIn nunca
  trae descripción. Sin cambios de esquema ni reclasificación.
- Línea base vigente (30-10-2026): v7; 7125 ofertas, 82 corridas, 460 filas en `historial_estados`, 6 ajustes, 27
  `terminos_no_disponibles`; 44 postuladas; 6 POR VERIFICAR. Salida al detener: `0`.
- **Cambio de base (30-10-2026, commit `33653be`):** `rellenar_linkedin.py` guardó la descripción en las 14 postuladas
  de LinkedIn de «Sin texto», solo en `raw.description`, sin reclasificar (siguen en `sin_descripcion`). Huella de
  `ofertas` ahora `b091d8ea…`; el resto de la línea base igual. Referencia de ese cambio:
  `ofertas_pre_rellenar_linkedin_20261030.db`. Reversión en `REVERSION_FASE_A.md`.
- Respaldos: cualquier cambio de base se hace con referencia sha256, huellas antes y después, y reversión probada en
  copia (puerto 8767), según el skill `/desplegar`.

### Sin desplegar
- Ninguno.
- **A vigilar:** si LinkedIn empieza a responder 429 seguido (una petición extra por oferta), bajar
  `RESULTADOS_POR_BUSQUEDA` o `TERMINOS_LINKEDIN`.

## Pendientes

- **«informático junior» (activo desde 14-10):** criterio de salida: si en unas 10 corridas no llega ninguna oferta
  útil con el motivo «rol: informático junior», se quita el término. Detalle en el historial.
- **Diagnóstico de términos (15-10):** el plan de tres fases (contadores, retiros de términos y ubicaciones, términos
  nuevos) tiene la primera fase aprobada y las otras dos sin decidir. Detalle en el historial.
- **Falso positivo «Desarrollador de Negocios» → «rol: desarrollo»:** se revisa solo si el patrón se repite.
- **Avisos reales del sistema (notificaciones del navegador):** no se han probado con el navegador real; el flujo se
  probó simulado.
- **Pregunta abierta:** «Ofertas 0» con «2 relevantes nuevas» en la página (ya pasaba antes del despliegue de avisos).
- **Papelera de OneDrive:** los originales borrados el 14-10 siguen en la nube hasta que Sofia la vacíe a mano.
- **Base local en OneDrive:** `ofertas.db` en la carpeta del proyecto está dentro de OneDrive. Sin decisión aún.
