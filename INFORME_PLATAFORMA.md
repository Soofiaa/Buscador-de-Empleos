# Informe Completo: Viabilidad, Costos y Riesgos de Evolución SaaS para JobTracker

**Fecha:** 31 de octubre de 2026  
**Objetivo:** Analizar en detalle la transformación de `job-tracker` a una plataforma multi-usuario, incluyendo estimaciones de costos de infraestructura y un análisis exhaustivo de riesgos operativos (como el bloqueo por IP compartida).

---

## 1. Diagnóstico del Estado Actual
- **Arquitectura:** Aplicación local en Python y SQLite, con un servidor HTTP embebido (`servidor.py`) y una interfaz de archivo único (`web/pagina.html`).
- **Configuración:** Fija y basada en un perfil único (`config.py`), lo que impide que otros usuarios busquen perfiles tecnológicos diferentes sin modificar código directamente.
- **Privacidad y Datos:** Base de datos local (`ofertas.db`) totalmente aislada en el equipo del usuario.

---

## 2. Propuesta para Uso Abierto por Terceros (Self-Hosted)
Para permitir que otros informáticos utilicen la herramienta bajo sus propios términos sin interferir con la instancia original:
1. **Puestos y Términos Dinámicos:** La interfaz web incluye la gestión de puestos personalizados guardados en la base de datos (tabla `ajustes`), permitiendo ingresar términos libres.
2. **Ubicaciones y Remoto Configurables:** Gestión de ubicaciones personalizadas y preferencias de trabajo remoto por usuario.
3. **Independencia por Instancia:** Cada usuario ejecuta su propia copia local o contenedor Docker, manteniendo su archivo `ofertas.db` totalmente privado y adaptado a sus propias reglas.

---

## 3. Hoja de Ruta para un Futuro Modelo SaaS
Si en el futuro se decide centralizar la plataforma bajo un modelo de servicio web comercial (SaaS), la arquitectura recomendada es:
- **Backend:** Migrar a **FastAPI (Python)** para reutilizar todo el motor de negocio existente (`buscar.py`, filtros y clasificadores) con soporte asíncrono y documentación automática.
- **Base de Datos:** Migrar de SQLite a **PostgreSQL** implementando **Row-Level Security (RLS)** para garantizar que cada usuario acceda únicamente a sus propios datos.
- **Autenticación y Pagos:** Integrar **Auth0 o Clerk** para el control de identidad y **Stripe** para la gestión de planes de suscripción y límites de cuotas.
- **Infraestructura:** Desplegar en plataformas PaaS como **Railway, Render o Fly.io**.

---

## 4. Estimación de Costos de Infraestructura (SaaS)

Para un MVP o una base inicial de hasta ~500 usuarios activos, los costos estimados mensuales son:

| Componente | Proveedor Recomendado | Nivel / Plan Inicial | Costo Mensual Estimado |
| :--- | :--- | :--- | :--- |
| **Hosting (Backend/API)** | Render / Railway | Plan de desarrollo / Starter | $7.00 - $10.00 USD |
| **Base de Datos (PostgreSQL)** | Render / Supabase / Neon | Base de datos gestionada pequeña | $0.00 - $15.00 USD |
| **Autenticación** | Auth0 / Clerk | Capa gratuita (hasta 7,000 MAU) | $0.00 USD |
| **Monetización (Pagos)** | Stripe | Comisión por transacción (2.9% + $0.30) | Variable por venta |
| **Total Estimado Inicial** | | | **~$7.00 – $25.00 USD / mes** |

A medida que la plataforma escale a miles de usuarios activos diarios, los costos aumentarán principalmente por el consumo de cómputo en el backend (ejecución de hilos de scraping) y almacenamiento en PostgreSQL, escalando a rangos de $50 - $150+ USD mensuales.

---

## 5. Análisis de Riesgos Operativos: El Desafío del Bloqueo por IP Compartida

En una aplicación local (monousuario), las peticiones a portales como Indeed, LinkedIn o Glassdoor se realizan desde la propia dirección IP residencial del usuario, lo que raramente genera bloqueos masivos. Sin embargo, **en un modelo SaaS centralizado**, surge el riesgo más crítico del sistema:

### El Problema
Si múltiples usuarios ejecutan búsquedas automatizadas simultáneamente desde un servidor centralizado en la nube (ej. una IP de AWS, Render o DigitalOcean), **todos compartirán la misma dirección IP pública**. 
- Los sistemas anti-bot de LinkedIn, Glassdoor e Indeed detectarán decenas o cientos de consultas concurrentes desde una sola IP de centro de datos.
- El resultado inmediato será un **bloqueo por *Rate Limiting* (código HTTP 429)** o la aparición de CAPTCHAs permanentes que inutilizarán la fuente para todos los usuarios de la plataforma.

### Estrategias de Mitigación (Obligatorias para SaaS)
1. **Rotación de Proxies Residenciales:** Enrutar las solicitudes de JobSpy a través de un pool de proxies residenciales pagados (ej. Bright Data o Oxylabs), lo que encarece la infraestructura.
2. **Límites Estrictos de Frecuencia (Rate Limiting por Usuario):** Restringir las búsquedas automáticas a una vez al día por usuario o requerir que el usuario active la búsqueda manualmente de forma espaciada.
3. **Delegación de Credenciales / APIs Propias:** Fomentar que el usuario configure sus propias claves de API (como Jooble o tokens de acceso permitidos) o que las fuentes pesadas (como LinkedIn) sean opcionales y corran del lado del cliente mediante extensiones o tokens individuales.
