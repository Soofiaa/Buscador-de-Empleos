# Notas del proyecto: estado actual

Este archivo solo lleva el estado vigente, la línea base y lo pendiente. El historial completo de despliegues,
hallazgos y decisiones (desde el 13-10-2026) está en `NOTAS_HISTORIAL.md`. Si algo aquí no cuadra con ese historial,
manda lo más reciente y corrige la nota.

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Vigente: despliegue de mejoras de sesión (29-10-2026)**, commits `b723f1f`, `cdf5c0c`, `72ca06a` (rama
  `feat/unificar-ofertas`). Imagen `job-tracker-jobtracker:latest` =
  `sha256:1f7f7e89d394c120b926b17e93014ff4c4c85405efa5f47dfc2e420862ec7ce7`, healthy en `127.0.0.1:8765`.
- Imagen anterior para volver atrás: `job-tracker:pre-fase4-20261029` (`sha256:14c69db1…`).
- Referencia: `ofertas_pre_fase4_20261029.db`, sha256 `a8bddcf343d6479a3a19762602598990d32fe13fe89e5991511ecdbfb09c54ef`,
  integrity_check ok. Procedimiento de reversión en `REVERSION_FASE_A.md`.
- Cambios: NOTAS.md compacto (historial en NOTAS_HISTORIAL.md); avisos de Jooble sin clave y fuentes en 0 llegan a la
  página; base local por defecto fuera de OneDrive. Sin cambios de esquema ni reclasificación.
- Línea base vigente (29-10-2026): v7; 6770 ofertas, 75 corridas, 421 filas en `historial_estados`, 6 ajustes, 27
  `terminos_no_disponibles`; 44 postuladas; 6 POR VERIFICAR. Salida al detener: `0`.
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
