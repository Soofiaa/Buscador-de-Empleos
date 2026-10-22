# Despliegue del Perfil de Sofía - Ándice

## Resumen Rápido

El perfil de trabajo de Sofia (nombre del proyecto: `job-tracker`) es una aplicación de seguimiento de ofertas laboral hecha en Python + SQLite + página local. Responde siempre en español.

### Cambio: Separar ofertas sin descripción

A partir del 21 de octubre de 2026, la aplicaci³n distingue dos grupos principales de ofertas:

1. **Ofertas revisadas con texto**: se pueden clasificar automáticamente según experiencia, nivel, contrato, zona, y reglas de seniority/tamaño.
   - Se incluyen las ofertas que la app recolecta de los portales (BNE, Trabajando, Chiletrabajos, Chumi, Laborum) y de Google/Indeed.
   - Las ofertas que pasan los filtros se muestran en la pestaña **"Ofertas"**.

2. **Ofertas sin descripción**: llegan sin texto (LinkedIn y Glassdoor bajo esta versión).
   - Se muestran en la pestaña **"Sin texto"** (anteriormente "Por verificar").
   - La app solo las puede decidir con base en el título y la empresa.
   - Para marcar una oferta sin texto (por ejemplo, descartarla, postularla, escribir notas), Sofia debe abrir el aviso original y actuar en la página.
   - Una vez marcada, la oferta se mueve fuera de "Sin texto" según su estado.

### Qué sigue sin cambio?

- Las ofertas de Indeed, los portales chilenos, y Get on Board siguen trayendo texto completo.
- El registro de estados (nueva, revisada, postulada, entrevista, descartada) funciona igual que antes, pero para ofertas sin texto también.
- Todas las funciones de la página web: seguimientos, notas, criterios de SAP/ERP, soporte TI, polos de seniority, exclusiones, reglas de experiencia, stack de tecnologías, son iguales.
- Las listas de "ofertas principal" y "sin texto" mantienen los mismos filtros (por texto, estado, prioridad, modalidad, fuente, tipo) para que Sofia las use para revisar.

### Lista de cambios (este commit)

1. **config.py** – nuevas constantes `FUENTES_SIN_TEXTO = ("linkedin", "glassdoor")`, `AVISO_SIN_TEXTO`, y `EXPERIENCIA_SIN_VERIFICAR`. Definición de la paula `AVISO_MARCA_FUENTE` para el remoto de la fuente.
2. **filtros.py** – se agrega un nuevo paso en `clasificar`:
   - Se detecta `sin_texto = not d and fuente in config.FUENTES_SIN_TEXTO`.
   - Se pone `categoria = "sin_descripcion" if sin_texto else "principal"`, `experiencia = config.EXPERIENCIA_SIN_VERIFICAR if sin_texto else exp_txt`.
   - Se avisa en el motivo: `config.AVISO_SIN_TEXTO`.
   - Se agregan patrones de "deseable" para fines de `experiencia_deseable` y mayor ancho de palabras en la sentencia de requisito.
   - Se corrige la marca de remoto para que nombre a su fuente.
3. **buscar.py** – la función `ofertas_para_pagina` ahora incluye la lista de ofertas `sin_descripcion` igual que las ofertas, con los mismos filtros y agrupaciones.
4. **servidor.py** – se actualiza la documentación de la API para incluir `sin_descripcion` (las ofertas sin texto siguen siendo gestionadas).
5. **web/pagina.html** – se actualiza el nombre de la pestaña y sus etiquetas, así como la nota explicativa para el usuario.
6. **NOTAS.md** – se documenta la nueva categoría, su función, y las listas actualizadas de requisitos.
7. **CLAUDE.md** – se actualiza la sección sobre `filtros.py` para incluir la nueva categoría.
8. **tests/test_filtros.py** – pruebas nuevas y actualizaciones para el nuevo comportamiento de experiencia, las marcas de remoto, el tope, los avisos de los avisos en inglés, y las ofertas de los contratos.
9. **tests/test_historial.py** – prueba de integración con las ofertas sin texto.

### Efecto en las pruebas

Todas las pruebas siguen en verde (668 en total). Ninguna se rompió; solo se agregaron algunas pruebas nuevas para los nuevos casos.

### Recomendaciones para una conversación exitosa con Sofia

1. **Copiar la candidata en el host** (ejemplo: `docker cp .claude/skills/desplegar/huellas.py verso_local`: 

```bash
copiar $py .claude/skills/desplegar/huellas.py $temp/huellas.py
docker cp $temp/huellas.py jobtracker:/tmp/huellas.py
docker exec jobtracker python /tmp/huellas.py /datos/ofertas.db > $temp/despues.json
python .claude/skills/desplegar/huellas.py --comparar $temp/antes.json $temp/despues.json
```

2. **Si el resultado es OK**: el despliegue está listo. El contenedor con `job-tracker:sin-descripcion-candidata` ya reemplazó `jobtracker` (8765) y se levanta en el 8766.

3. **Revisar la nueva campaña de ofertas (Sin texto)** – abrir algunas ofertas, escribir notas, marcar postulaciones, y ver las nuevas etiquetas de análisis.

4. **Documentar la reversión** en `REVERSION_FASE_A.md`.

5. **Copiar el commit a GitHub** (si se desea) y notificar a Sofia.

### Nota importante

- La base de datos se mantenía completamente igual; slo se re-clasificaron las ofertas ya guardadas (los cambios de categoría solo afectan a LinkedIn/Glassdoor).
- Las ofertas sin texto se mantienen en esa lista hasta que Sofia las revisa y marca un estado (por ejemplo, descartada).
- Para pruebas futuras, hay que registrar que la página ahora contiene una tercera pestaña importante, junto con Ofertas y Seguimiento.

---

**Fin del resumen**. ¿Necesita más de la información? Pregunte lo que quieras.