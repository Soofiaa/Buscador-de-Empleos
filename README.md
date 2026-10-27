# Búsqueda de empleo · job-tracker

Aplicación local en Python + SQLite con interfaz web integrada (`web/pagina.html`) para la búsqueda y el seguimiento de ofertas laborales en Chile y en modalidad remota global.

## Fuentes y Portales Activos (15 en total)

- **Portales y APIs chilenas / remotas**: BNE, Trabajando, Chiletrabajos, Chumi, Laborum, Get on Board, Himalayas, Jobicy, Remote First Jobs, We Work Remotely, Arbeitnow, Jooble.
- **Motores con JobSpy**: Indeed, Glassdoor, LinkedIn (con consultas intercaladas para evitar límites de tasa/429).

## Características Principales

1. **Clasificación Automática**: Filtros estrictos de seniority, experiencia, exclusiones por palabras clave y región (Santiago, Viña del Mar/Valparaíso y remoto global).
2. **Postulaciones Manuales**: Permite registrar ofertas fuera de la búsqueda automática, revivir descartadas conservando su historial, y confirmar o consultar ante posibles duplicados (mismo cargo y empresa).
3. **Sección «Sin texto»**: Ofertas cuyo listado no incluye descripción completa (ej. LinkedIn), permitiendo al usuario pegar el texto desde el navegador para su reclasificación posterior.
4. **Seguimiento y Métricas**: Tablero Kanban (Por postular, CV enviado, Entrevistas, Ofertas/Cierre), notas, fechas de postulación, sueldos manuales/calculados y estadísticas de conversión.
5. **Respaldo Automático**: Respaldos diarios de la base de datos con verificación SHA-256 y control de retención.

## Estructura del Repositorio

- `web/pagina.html`: Interfaz web completa de un solo archivo (HTML/CSS/JS).
- `servidor.py`: Servidor HTTP local con API REST y restricciones de origen (bloqueo de CSRF/orígenes ajenos).
- `buscar.py`, `filtros.py`, `red.py`: Motor central de base de datos, lógica de negocio, clasificación y conexión HTTP con manejo de `robots.txt`.
- `*.py` (módulos específicos): Conectores para cada fuente (`jooble.py`, `weworkremotely.py`, `arbeitnow.py`, `bne.py`, `trabajando.py`, etc.).
- `tests/`: Suite completa de pruebas unitarias y de integración (más de 850 pruebas).
- `NOTAS.md`: decisiones, hallazgos y estado de producción. Leer al empezar cada sesión.
- `TUTORIAL.md`: guía de uso de la aplicación.
- `.claude/skills/desplegar/SKILL.md`: procedimiento estándar para desplegar a producción.

## Configuración

- **Jooble** necesita una clave gratuita (uso no comercial) en la variable `JOOBLE_KEY`. Guárdala en un archivo `.env` en la raíz del proyecto (ya está en `.gitignore`, nunca se sube al repositorio); `docker-compose.yml` la pasa al contenedor. Sin clave, Jooble no devuelve ofertas.
- Las fuentes activas, los términos de búsqueda, las ubicaciones y las ventanas de antigüedad están en `config.py`.

## Ejecución de Pruebas

Las pruebas se ejecutan con pytest:

```bash
venv\Scripts\python.exe -m pytest -q
```

Las pruebas que leen `web/pagina.html` comprueban su estructura, así que conviene correrlas después de cualquier cambio en la interfaz.

## Despliegue

La aplicación corre en un contenedor Docker (`jobtracker`, en `127.0.0.1:8765`) con la base de datos en un volumen persistente.

El despliegue a producción no se hace a mano. Sigue el procedimiento de `.claude/skills/desplegar/SKILL.md`: referencia de la base con sha256, huellas antes y después, comprobaciones HTTP y reversión documentada. Nunca se despliega sin aprobación explícita.
