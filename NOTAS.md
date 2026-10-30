# Notas del proyecto: estado actual

Este archivo solo lleva el estado vigente, la línea base y lo pendiente. El historial completo de despliegues,
hallazgos y decisiones (desde el 13-10-2026) está en `NOTAS_HISTORIAL.md`. Si algo aquí no cuadra con ese historial,
manda lo más reciente y corrige la nota.

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Vigente: despliegue de optimización de LinkedIn (28-10-2026, ~21:15)**, commit `3e94443`. Imagen
  `job-tracker-jobtracker:latest` = `sha256:395825fbd2a5104e039fe76465957a75ae037dac60e7e0e4552873d6b355989c`, healthy
  en `127.0.0.1:8765`.
- Imagen anterior para volver atrás: `job-tracker:pre-linkedin-opt-20261028` (`sha256:835dc75d…`).
- Referencia: `ofertas_pre_linkedin_opt_20261028.db`, sha256 `018ef42f…`, integrity_check ok. Procedimiento de
  reversión en `REVERSION_FASE_A.md`.
- Cambio: la lista corta de puestos (`TERMINOS_LINKEDIN`) y la pausa de 4–6 s bajan la búsqueda completa de ~38 min a
  unos 8–10 min. Sin reclasificar las ofertas guardadas.
- Última línea base medida (28-10-2026, despliegue de «Explorar remotos»): v7; 6222 ofertas, 63 búsquedas, 385 filas
  en `historial_estados`, 6 ajustes, 27 `terminos_no_disponibles`; 42 postuladas; 6 POR VERIFICAR.
- Respaldos: cualquier cambio de base se hace con referencia sha256, huellas antes y después, y reversión probada en
  copia (puerto 8767), según el skill `/desplegar`.

### Sin desplegar
- Ninguno. El último commit (`682cc6a`) es la nota del despliegue vigente y el árbol de trabajo está limpio.

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
