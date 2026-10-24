# Búsqueda de empleo · job-tracker

El perfil de trabajo de Sofía (nombre del proyecto: `job-tracker`) es una aplicación de seguimiento de ofertas laborales hecha en Python + SQLite + una página local (`web/pagina.html`). Responde siempre en español.

## Cómo está organizado

- `web/pagina.html`: la interfaz completa (un solo archivo con CSS y JavaScript).
- `servidor.py`: la API local y la página. Escucha solo en `127.0.0.1`.
- `buscar.py`, `filtros.py`, `red.py`: búsqueda, clasificación y conexión a la base.
- `tests/`: pruebas. Se ejecutan con `venv\Scripts\python.exe -m pytest -q`.
- `NOTAS.md`: decisiones, hallazgos y estado de producción. Leer al empezar cada sesión.
- `.claude/skills/desplegar/SKILL.md`: procedimiento estándar para desplegar a producción. Requiere aprobación explícita.

## Ofertas sin texto

A partir del 21 de octubre de 2026, la aplicación distingue dos grupos principales de ofertas:

1. **Ofertas revisadas con texto**: se clasifican automáticamente según experiencia, nivel, contrato, zona y reglas de seniority.
   - Vienen de los portales (BNE, Trabajando, Chiletrabajos, Chumi, Laborum), de Indeed y de Get on Board.
   - Las que pasan los filtros se muestran en la pestaña **«Ofertas»**.

2. **Ofertas sin texto**: llegan sin descripción (hoy, LinkedIn).
   - Se muestran al final de la pestaña **«Ofertas»**, bajo el título «Sin texto».
   - La app solo puede decidir con base en el título y la empresa.
   - Para decidirlas, abre el aviso con ↗ y pega su descripción en la tarjeta. Así el servidor la reclasifica solo a esa oferta.

### Qué no cambia

- Las ofertas de Indeed, los portales chilenos y Get on Board siguen trayendo texto completo.
- El registro de estados (nueva, revisada, postulada, entrevista, descartada) funciona igual para las ofertas sin texto.
- Las demás funciones (seguimiento, notas, tablero, criterios de SAP/ERP, soporte TI, seniority, exclusiones y reglas de experiencia) siguen igual.
- Las ofertas «Ofertas» y «Sin texto» usan los mismos filtros.

## Pruebas

Las pruebas del proyecto se ejecutan con:

```
venv\Scripts\python.exe -m pytest -q
```

Las pruebas que leen `web/pagina.html` comprueban su estructura, así que conviene correrlas después de cualquier cambio en la interfaz.

## Despliegue

El despliegue a producción no se hace a mano. Sigue el procedimiento de `.claude/skills/desplegar/SKILL.md`: referencia de la base con sha256, huellas antes y después, comprobaciones HTTP y reversión documentada. Nunca se despliega sin aprobación explícita.
