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
- `tests/`: Suite completa de pruebas unitarias e de integración (más de 850 pruebas).
- `NOTAS.md` y `TUTORIAL.md`: Documentación detallada de decisiones técnicas, flujos y guía de uso.

## Ejecución de Pruebas

Las pruebas se ejecutan con pytest:

```bash
venv\Scripts\python.exe -m pytest -q
```

## Despliegue con Docker

El proyecto corre habitualmente en un contenedor Docker con volumen persistente para la base de datos:

```bash
docker compose up -d --build
```
