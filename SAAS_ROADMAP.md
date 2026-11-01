# Roadmap: Evolución a SaaS (Futuro)

Documento de referencia para cuando `job-tracker` evolucione de una herramienta personal/multi-instancia a un modelo SaaS multi-usuario.

**Estado actual (31-10-2026):** Job-tracker es una herramienta local con soporte para multi-instancia independiente (cada usuario clona, configura sus puestos/ubicaciones, y maneja su propia BD). Aún no es SaaS centralizado.

---

## 1. Arquitectura de Stack Propuesta

### Backend
- **FastAPI (Python)**
  - Reemplaza `servidor.py` (HTTP local)
  - Mantiene intacto: `buscar.py`, `filtros.py`, clasificadores, conectores con portales
  - Setup: `pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-jose`
  - Razón: Async nativo, Swagger auto, Pydantic validation, 10x más rápido que Django

### Base de Datos
- **PostgreSQL** (reemplaza SQLite)
  - Row-Level Security (RLS): usuario A nunca ve ofertas de usuario B, a nivel de BD
  - JSONB: guarda `ajustes` (puestos, ubicaciones, exclusiones) sin cambiar schema
  - Escalable: soporta 1.000+ usuarios sin refactor
  - Setup: Railway/Render gestiona todo, 0 DevOps

### Autenticación
- **Auth0 o Clerk** (no custom login)
  - Gratis hasta 7.000 usuarios
  - OAuth: Google, GitHub, email
  - MFA incluido
  - JWT tokens validados en FastAPI middleware
  - Setup: 2h de integración, 0 código de contraseñas/sesiones

### Infraestructura
- **Railway, Render o Fly.io** (no AWS/GCP)
  - `git push` → automático despliegue
  - PostgreSQL gestionado incluido
  - HTTPS/TLS automático
  - ~$7-30/mes por usuario pequeño
  - Backups automáticos

### Monetización
- **Stripe**
  - Suscripciones mensuales/anuales
  - Webhooks → crear/cancelar acceso
  - Compliance de impuestos
  - Setup: 3h de integración

---

## 2. Pasos de Migración (Fases)

### Fase A: Backend FastAPI (1-2 meses)
Objetivo: misma funcionalidad pero en API HTTP.

```python
# servidor_saas.py (reemplaza servidor.py)
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "postgresql://user:pass@localhost/jobtracker"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

# CORS: permitir el frontend desde tudominio.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tudominio.com", "https://app.tudominio.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependencia: validar token JWT y obtener user_id
def get_current_user(token: str = Header(...)) -> int:
    """Valida token de Auth0/Clerk y retorna user_id"""
    try:
        payload = jwt.decode(token, CLERK_PUBLIC_KEY, algorithms=["RS256"])
        user_id = payload.get("sub")  # Auth0/Clerk pone el ID en 'sub'
        if not user_id:
            raise HTTPException(status_code=401, detail="invalid token")
        return int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="unauthorized")

# Endpoints (iguales a los actuales, pero con user_id)
@app.get("/api/ofertas")
async def ofertas(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna las ofertas del usuario (RLS ya filtra en BD)"""
    return buscar.ofertas_para_pagina(db, user_id)

@app.post("/api/buscar")
async def buscar_ofertas(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Inicia búsqueda para este usuario"""
    # Chequear cuota por plan
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if user.searches_this_month >= PLAN_LIMITS[user.plan]["searches"]:
        raise HTTPException(status_code=429, detail="search limit reached")
    # ... resto igual
    return {"ok": True}

@app.post("/api/ajustes/ubicaciones")
async def guardar_ubicaciones(
    datos: dict,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Guardar ubicaciones del usuario (RLS garantiza que solo ve las suyas)"""
    return buscar.guardar_ubicaciones(db, user_id, datos)

# ... resto de endpoints igual
```

### Fase B: Capa de Datos (PostgreSQL + RLS) (1 mes)
Objetivo: migrar de SQLite a Postgres con aislamiento de seguridad.

```sql
-- Crear tablas con usuario_id

CREATE TABLE usuarios (
  id SERIAL PRIMARY KEY,
  auth0_id TEXT UNIQUE NOT NULL,  -- o clerk_id
  email TEXT UNIQUE NOT NULL,
  plan TEXT DEFAULT 'free',       -- free, pro, enterprise
  searches_this_month INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ofertas (
  id SERIAL PRIMARY KEY,
  usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  titulo TEXT,
  empresa TEXT,
  ubicacion TEXT,
  estado VARCHAR(20),
  detectada_en TIMESTAMP,
  -- ... resto de columnas
  UNIQUE(usuario_id, url)  -- cada usuario no puede tener la misma URL dos veces
);

CREATE TABLE ajustes (
  id SERIAL PRIMARY KEY,
  usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  clave TEXT NOT NULL,  -- 'puestos', 'ubicaciones', 'exclusiones', etc.
  valor JSONB,
  UNIQUE(usuario_id, clave)
);

CREATE TABLE historial_estados (
  id SERIAL PRIMARY KEY,
  usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  oferta_id INT REFERENCES ofertas(id) ON DELETE CASCADE,
  estado TEXT,
  fecha_cambio TIMESTAMP,
  nota TEXT
);

-- Row-Level Security: cada usuario ve solo SUS datos

ALTER TABLE ofertas ENABLE ROW LEVEL SECURITY;

CREATE POLICY ofertas_aisladas ON ofertas
  FOR ALL
  USING (usuario_id = current_setting('app.current_user_id')::INT);

ALTER TABLE ajustes ENABLE ROW LEVEL SECURITY;

CREATE POLICY ajustes_aislados ON ajustes
  FOR ALL
  USING (usuario_id = current_setting('app.current_user_id')::INT);

-- Similar para historial_estados, etc.

-- Funciones de trigger para actualizar searches_this_month
CREATE OR REPLACE FUNCTION registrar_busqueda()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE usuarios
  SET searches_this_month = searches_this_month + 1
  WHERE id = NEW.usuario_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_busqueda
AFTER INSERT ON corridas
FOR EACH ROW
EXECUTE FUNCTION registrar_busqueda();

-- Reset mensual (cron o trigger)
CREATE OR REPLACE FUNCTION reset_searches_mensual()
RETURNS void AS $$
BEGIN
  UPDATE usuarios
  SET searches_this_month = 0
  WHERE DATE_TRUNC('month', created_at) < DATE_TRUNC('month', NOW());
END;
$$ LANGUAGE plpgsql;
```

**En FastAPI, antes de cada consulta:**
```python
def get_db():
    db = SessionLocal()
    user_id = get_current_user()  # desde JWT
    db.execute("SET app.current_user_id = :user_id", {"user_id": user_id})
    try:
        yield db
    finally:
        db.close()
```

### Fase C: Autenticación y Límites (1 mes)
Objetivo: usuarios reales, cuotas por plan, Stripe integrado.

```python
# models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True)
    auth0_id = Column(String, unique=True)  # o clerk_id
    email = Column(String, unique=True)
    plan = Column(String, default="free")
    stripe_customer_id = Column(String)
    searches_this_month = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

# stripe_config.py
PLAN_LIMITS = {
    "free": {
        "searches_per_month": 10,
        "max_offers_stored": 500,
        "max_users_per_instance": 1,
        "price_usd": 0,
    },
    "pro": {
        "searches_per_month": 100,
        "max_offers_stored": 50000,
        "max_users_per_instance": 5,
        "price_usd": 9.99,
    },
    "enterprise": {
        "searches_per_month": None,  # unlimited
        "max_offers_stored": None,
        "price_usd": "custom",
    },
}

# main.py
@app.post("/api/buscar")
async def buscar_ofertas(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    limits = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
    
    if limits["searches_per_month"] is not None:
        if user.searches_this_month >= limits["searches_per_month"]:
            raise HTTPException(
                status_code=429,
                detail=f"Límite alcanzado. Plan {user.plan}: {limits['searches_per_month']} búsquedas/mes"
            )
    
    # ... resto
    user.searches_this_month += 1
    db.commit()
    return buscar.buscar_ofertas(db, user_id)

# stripe_webhook.py
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Webhook: Stripe notifica cambios de suscripción"""
    event = json.loads(await request.body())
    
    if event["type"] == "customer.subscription.updated":
        customer_id = event["data"]["object"]["customer"]
        plan = event["data"]["object"]["items"]["data"][0]["plan"]["lookup_key"]
        
        user = db.query(Usuario).filter(Usuario.stripe_customer_id == customer_id).first()
        user.plan = plan
        db.commit()
    
    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"]["customer"]
        user = db.query(Usuario).filter(Usuario.stripe_customer_id == customer_id).first()
        user.plan = "free"  # o marcar como inactivo
        db.commit()
    
    return {"status": "ok"}
```

---

## 3. Frontend (Sin cambios)
El `web/pagina.html` actual necesita **2 cambios mínimos:**

```javascript
// Cambio 1: URL de la API
const API_BASE = typeof window !== "undefined" && window.location.origin === "http://localhost:8765"
  ? "http://localhost:8765"  // local
  : "https://api.tudominio.com";  // SaaS

// Cambio 2: Token JWT en headers
async function api(ruta, datos = null, metodo = "GET") {
  const token = localStorage.getItem("auth_token");  // guardado por Auth0/Clerk
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
  };
  // ... resto igual
}
```

---

## 4. Lo que se preserva (INTACTO)
- ✅ `buscar.py`: Lógica de raspado, clasificación, estado
- ✅ `filtros.py`: Reglas de exclusión, normalización
- ✅ Clasificadores (roles TI, puente, exploraciones)
- ✅ Conectores (`bne.py`, `trabajando.py`, `linkedin.py`, etc.)
- ✅ Tests (siguen pasando sin cambios)

**Cambios mínimos necesarios:**
- `buscar.conexion()`: cambiar de sqlite3.connect() a SQLAlchemy session
- Funciones `leer_puestos()`, `leer_ubicaciones()`: pasar `user_id` como parámetro

---

## 5. Despliegue (Railway.app)

```bash
# 1. Crear repositorio en GitHub
git init
git add -A
git commit -m "saas: initial setup with fastapi"
git push -u origin main

# 2. En Railway.app: conectar repo → crear PostgreSQL → deploy
# Automatizado: cualquier push a main redeploya

# 3. Variables de entorno
DATABASE_URL=postgresql://...
AUTH0_DOMAIN=xxxx.auth0.com
AUTH0_CLIENT_ID=xxxxx
STRIPE_SECRET_KEY=sk_live_xxxxx
```

---

## 6. Timeline Estimado

| Fase | Duración | Esfuerzo | Nota |
|------|----------|----------|------|
| A: FastAPI | 4-6 semanas | Alto | Copiar endpoints, agregar user_id |
| B: PostgreSQL + RLS | 2-3 semanas | Medio | Migrar datos, configurar políticas |
| C: Auth + Stripe | 2-3 semanas | Medio | Integrar Auth0/Clerk + webhooks |
| Testing + polish | 2 semanas | Bajo | Tests pasan, UI compatible |
| **Total** | **~3 meses** | - | Tiempo real de dev, no planificación |

---

## 7. Presupuesto Inicial (Recurrente)

| Servicio | Costo | Notas |
|----------|-------|-------|
| Railway PostgreSQL | $7-20/mes | Escalable, backups automáticos |
| Railway FastAPI | $5-10/mes | Incluido en uso estándar |
| Auth0 (Clerk) | Gratis hasta 7K users | Luego $99/mes |
| Stripe | 2.9% + $0.30/transacción | Solo si hay cobro |
| **Total** | **$12-30/mes** (hasta 100 usuarios) | Negligible comparado con ingresos |

---

## 8. Preguntas Abiertas (Para decidir cuando llegue el momento)

1. **¿Freemium o modelo de pago?** Gratis con limitaciones (10 búsquedas/mes) o de pago desde el día 1?
2. **¿B2C o B2B?** Usuarios individuales o empresas?
3. **¿Integraciones?** Slack, email, webhook custom para notificaciones?
4. **¿Exportación de datos?** ¿Qué usuarios pueden hacer con sus datos?
5. **¿Soporte multi-idioma?** ¿Solo español o más?
6. **¿Portales adicionales?** Seguir añadiendo fuentes de empleo o mantener las 15 actuales?

---

## Referencia Rápida

- **Setup local actual:** `python servidor.py` + SQLite → OK para 1 usuario
- **Multi-instancia (actual):** Cada usuario clona + corre su instancia → OK para <100 informáticos amigos
- **SaaS (futuro):** 1 servidor FastAPI + PostgreSQL + Auth0 → OK para miles de usuarios, escalable

Este documento se actualiza cuando el proyecto tome decisiones sobre la vía SaaS.
