# Tutorial: cómo usar job-tracker

job-tracker es una aplicación local para buscar ofertas de empleo, revisarlas y hacerles seguimiento hasta la entrevista o la oferta. Corre en tu propio computador: tus datos no salen de tu equipo.

> **Antes de empezar:** la configuración viene hecha para un perfil concreto (TI junior en Chile, con búsqueda en Santiago y Viña del Mar). Si tu perfil es otro, lee la sección [Adaptar la búsqueda a tu perfil](#adaptar-la-búsqueda-a-tu-perfil) antes de buscar. Si no, verás ofertas que no te sirven.

---

## 1. Requisitos

Hay dos formas de correrlo:

- **Con Docker (recomendada).** Necesitas Docker Desktop. Es la forma en que se usa en producción.
- **Con Python.** Necesitas Python 3.12 o superior y las dependencias de `requirements.txt`.

## 2. Instalación con Docker

1. Descarga el proyecto y entra a su carpeta.
2. Abre una terminal en esa carpeta y ejecuta:

   ```
   docker compose up -d
   ```

3. Espera a que el contenedor quede sano:

   ```
   docker inspect jobtracker --format "{{.State.Health.Status}}"
   ```

   Debe responder `healthy`.

4. Abre **http://127.0.0.1:8765/** en tu navegador.

La base de datos vive en un volumen de Docker, así que no se borra al reiniciar el contenedor.

## 3. Instalación con Python

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python servidor.py
```

Luego abre **http://127.0.0.1:8765/**. La base se guarda en `ofertas.db`, en la carpeta del proyecto.

## 4. Recorrido de la pantalla

La pantalla tiene un menú a la izquierda y, a la derecha, el apartado que elijas.

**Menú izquierdo**
- **Apartados:** Ofertas, Seguimiento, Métricas y Ajustes. Ofertas y Seguimiento muestran cuántas hay. Cada apartado tiene su dirección (`#ofertas`, `#seguimiento`, `#metricas`, `#ajustes`), así que puedes guardarla en favoritos.
- **Buscar empleos:** lanza una búsqueda en los portales. Tarda unos 15 a 20 minutos. Mientras corre, la barra muestra el avance.
- **Buscar a mano:** enlaces a sitios que no admiten búsquedas automáticas (Computrabajo y Empleos Públicos). Se abren en tu navegador.
- **Historial:** las búsquedas anteriores, agrupadas por día. Elige una para ver en Ofertas solo lo que trajo.

**Ofertas**
- **Pestañas:** Ofertas, Fuera de perfil, Sospechosas, Descartadas y Descartadas por filtros. Las ofertas *Sin texto* aparecen al final de Ofertas (ver más abajo).
- **Filtros:** búsqueda por texto (busca en cargo, empresa, lugar, motivo y notas; cada palabra debe aparecer) y estado. Los filtros de prioridad, modalidad, tipo y fuente están en **«Más filtros»**; cuando uno está activo, el resumen lo indica (por ejemplo, «Más filtros · 2 activos»). **«Limpiar filtros»** los quita todos.
- **Agrupar:** en Ofertas, por prioridad (Alta, Media, Baja) o por fuente.
- **Vista:** Tarjetas (con detalle) o Compacta (una línea por oferta). La vista y los filtros que eliges se recuerdan en tu navegador.
- **Atajo:** «/» o Ctrl+K llevan al buscador.
- **Ayuda de esta pantalla:** el botón ❓ explica la pestaña o el apartado en el que estás.

**Métricas** (solo lectura, sobre todas tus ofertas relevantes, sin importar la búsqueda que elijas en el historial):
- **Indicadores:** cuántas postulaciones tienes, cuántas tuvieron respuesta, cuántos procesos siguen activos y cuántos días promedio tardan.
- **Embudo:** cuatro etapas: *Relevantes*, *Postuladas*, *Llegaron a entrevista* y *Final u oferta*. Cada una cuenta las ofertas que llegaron hasta ahí, así que una oferta puede estar en varias.
- **Desgloses:** por fuente, por modalidad y por tipo de contrato.
- **Actividad:** postulaciones por semana, de las últimas 8.

Las fechas de cambio de etapa existen desde el 13-10-2026; antes no se inventan.

**Ajustes**
- **Qué busco:** los puestos que se buscan en Indeed y las exclusiones (lo que nunca debe aparecer). Los puestos se usan en la próxima búsqueda; las exclusiones se aplican al clasificar las ofertas.
- **Datos:** exportar a CSV o JSON y hacer un respaldo de la base (ver la sección 9).
- **Apariencia y avisos:** el tema, el contraste reforzado (viene activado) y los avisos del navegador cuando entran ofertas nuevas. Todo se recuerda en tu navegador. Hay seis temas:
  - Suaves: 🌷 **Primavera** (claro) y 🌹 **Rosa nocturna** (oscuro).
  - Frescos: 🌊 **Océano** (claro) y 🌌 **Medianoche** (oscuro).
  - Neutros: 🏔️ **Niebla** (claro) y 🌑 **Carbón** (oscuro).

## 5. Buscar empleos

1. Pulsa **«Buscar empleos»**.
2. Espera. La barra avanza y el texto dice en qué portal va.
3. Al terminar, las ofertas nuevas aparecen en **Ofertas**, y la búsqueda queda en el historial.

Una búsqueda registra cuántas ofertas encontró cada portal y cuántas son nuevas y relevantes. Si un portal falla, el resultado lo muestra en el panel **«Resultado de la última búsqueda por fuente»**.

## 6. Revisar una oferta

Cada tarjeta muestra el cargo, la empresa, la ubicación, la fuente, la prioridad, el tipo de contrato, la experiencia pedida y el sueldo, si se indica.

- **Título:** abre el aviso original en una pestaña nueva.
- **↗:** lo mismo, con un icono más pequeño.
- **Estado:** elige en la tarjeta entre *Nueva*, *Revisada*, *Postulada*, *En entrevista* o *Descartada*.
- **⚡ Gestionar proceso:** abre el detalle de la oferta, donde puedes fijar la fecha de postulación, escribir notas, marcar la fase del proceso, poner un sueldo propio o cambiar la prioridad.

Las ofertas de **Ofertas** son las que la app considera relevantes. Si una te interesa y no te convence, márcala como descartada: sale de la lista y queda en **Descartadas**, donde puedes recuperarla.

### Sin texto

Algunas fuentes (hoy, LinkedIn) no entregan la descripción del aviso. La app no puede revisar su experiencia ni su nivel, así que las marca como **Sin texto** y las muestra al final de Ofertas.

Para decidirlas:
1. Abre el aviso con ↗.
2. Copia la descripción completa.
3. Pégala en el cuadro de la tarjeta y pulsa **«Guardar descripción»**.

La app la revisa y, si cumple, la pasa a **Ofertas**. Si no cumple, queda descartada.

## 7. Seguimiento de postulaciones

El apartado **Seguimiento** muestra las ofertas que revisaste, postulaste o en las que vas en proceso. Arriba eliges cómo verlas:

- **Tablero:** cuatro columnas: *Por postular*, *CV enviado*, *Entrevistas* y *Oferta / Cierre*. Arrastra una tarjeta a otra columna para cambiar su etapa. Si no puedes arrastrar (pantalla táctil o teclado), usa el selector **«Mover a…»** de la tarjeta.
- **Tarjetas:** la misma información en una lista de tarjetas detalladas, útil para buscar.
- **Compacta:** una fila por oferta.
- **Resumen:** arriba aparece cuántas ofertas hay en cada columna.
- **Historial:** igual que en Ofertas, puedes elegir una búsqueda para ver solo sus ofertas. Si la eliges estando en otro apartado, la app te lleva a Ofertas con esa búsqueda.
- **Atajo:** «/» o Ctrl+K enfocan el buscador de Seguimiento.

Cada movimiento muestra un aviso con **«Deshacer»**, que vuelve exactamente al estado anterior.

Las tarjetas muestran cuántos días llevan desde la postulación. Hasta 3 días aparece en verde; de 4 a 5, un aviso para revisar; desde 6 días, un aviso de seguimiento.

> La fase de un proceso no retrocede desde el tablero. Para bajarla, usa **«Gestionar proceso»**.

## 8. Agregar una postulación manual

Si postulaste a una oferta que la búsqueda no trajo, pulsa **«➕ Agregar postulación manual»**. Pide el cargo y la empresa como obligatorios; el enlace, la ubicación y el resto son opcionales.

Si ya tienes esa oferta registrada, la app reacciona según el caso:

- **Mismo enlace**: no crea nada nuevo; te muestra la existente con «Ver la existente».
- **Mismo cargo y empresa** (en la misma ciudad, o si dejas la ubicación vacía): te avisa y ofrece dos botones. «Ver la existente» abre su ficha, y «Guardar de todas formas» crea la postulación como una oferta aparte. Úsalo si es otra oferta de la misma empresa y cargo.
- **Estaba descartada**: la reactiva con la nueva postulación (la misma fila, con su historial), sin preguntar.

## 9. Respaldos y exportación

Todo está en **Ajustes > Datos**.

- **Respaldar ahora:** copia la base completa a la carpeta de respaldos. Se puede usar cada minuto como máximo.
- **Respaldo automático:** la app guarda una copia por día y conserva las últimas 30.
- **CSV de Ofertas** y **CSV de Seguimiento:** cada uno exporta lo suyo, para abrir en Excel.
- **Todo en JSON:** exporta todas las ofertas en un archivo legible.

Con Docker, la carpeta de respaldos se define en `docker-compose.yml`. Conviene elegir una carpeta **fuera de OneDrive** o de cualquier servicio que sincronice archivos, para que la base no se copie a medias.

## 10. Adaptar la búsqueda a tu perfil

Todo lo que define qué ofertas aparecen está en **`config.py`**. Los cambios más importantes:

| Qué cambiar | Dónde | Qué hace |
|---|---|---|
| Cargos que buscas | `TERMINOS_A` (roles TI) y `TERMINOS_B` (roles puente) | Las frases que se buscan en cada portal |
| Ciudades | `UBICACIONES` y `REGIONES_VALIDAS` | Dónde se considera válida una oferta presencial |
| Remoto | `INCLUIR_REMOTO` | Si se aceptan ofertas remotas |
| Experiencia | `EXPERIENCIA_DESCARTA_DESDE` y `EXPERIENCIA_MAXIMA` | Desde qué años de experiencia se descarta una oferta |
| Empresas excluidas | `EXCLUIR_EMPRESAS` | Empresas que nunca aparecen |
| Prácticas y estudiantes | `EXCLUIR_PRACTICA_TITULO` y `EXCLUIR_PRACTICA_DESC` | Se descartan automáticamente |
| Portales | `SITIOS` | Qué portales se consultan |

Después de cambiar `config.py`, corre las pruebas para comprobar que nada se rompió:

```
venv\Scripts\python.exe -m pytest -q
```

> Los valores actuales son de un perfil de TI junior en Chile. Si los dejas tal cual, tendrás resultados de ese perfil, no del tuyo.

## 11. Análisis con IA

La aplicación incluye un asistente de IA para ayudarte a evaluar si una oferta encaja con tu perfil.

- **Requisito:** necesitas una clave API de **Groq**. Consíguela gratis en [groq.com](https://groq.com/).
- **Configuración:** guarda tu clave en la variable de entorno `GROQ_API_KEY` (puedes añadirla a tu archivo `.env`).
- **Uso:** en el detalle de una oferta, la app puede analizar la descripción y darte una puntuación de compatibilidad y puntos fuertes.

## 12. Preguntas frecuentes

**¿La app manda mis datos a algún servidor?**
No. La base vive en tu equipo. Solo se consultan los portales de empleo, para buscar las ofertas.

**¿Por qué la búsqueda tarda tanto?**
Las pausas entre consultas son deliberadas, para no ser bloqueado por los portales. Una búsqueda completa toma unos 15 a 20 minutos.

**Un portal aparece con errores en la búsqueda. ¿Qué hago?**
Es normal que algún portal falle de vez en cuando. La búsqueda sigue con los demás. Si falla siempre, revisa el panel de resultados por fuente: el detalle dice qué pasó.

**¿Cómo vuelvo a una versión anterior?**
Si actualizas el proyecto y algo no te gusta, la carpeta `REVERSION_INTERFAZ.md` (y los demás `REVERSION_*.md`) explica cómo volver a la imagen anterior sin perder datos.

**Borré algo por error.**
Las ofertas descartadas se pueden recuperar: aparecen en **Descartadas**, y desde su tarjeta cambias el estado a otro. Si borraste la base, restaura el último respaldo desde tu carpeta de respaldos.

---

Si tienes dudas o encuentras un error, revisa `NOTAS.md`, que documenta las decisiones y los hallazgos del proyecto.
