# TrendBuy

TrendBuy es una plataforma para rastrear, comparar y analizar precios en e-commerce. El proyecto esta dividido en backend FastAPI y frontend Next.js.

## Estructura

```text
TrendBuy/
  backend-trendbuy/      # FastAPI, Playwright, SQLAlchemy, Celery, Prophet
  frontend-trendbuy/     # Next.js
  docker-compose.yml     # PostgreSQL + Redis para desarrollo
  context.md             # Contexto funcional y tecnico del proyecto
```

## Requisitos

- Python 3.11+
- Node.js 20+
- Docker Desktop
- PowerShell en Windows

Si `python` abre Microsoft Store, desactiva los alias en:

```text
Configuracion > Aplicaciones > Configuracion avanzada de aplicaciones > Alias de ejecucion de aplicaciones
```

Desactiva `python.exe` y `python3.exe`, instala Python desde `python.org` y marca `Add python.exe to PATH`.

## Infraestructura

Desde la raiz del proyecto:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy
docker compose up -d
```

Esto levanta:

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Backend

Configura variables de entorno:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy\backend-trendbuy
Copy-Item .env.example .env
```

Edita `.env` si necesitas cambiar credenciales:

```env
DATABASE_URL=postgresql+asyncpg://trendbuy:trendbuy@localhost:5432/trendbuy
REDIS_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
TELEGRAM_BOT_TOKEN=123456789:replace_me
TELEGRAM_CHAT_ID=123456789
```

Instala dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Arranca la API:

```powershell
uvicorn api.main:app --reload
```

API local:

```text
http://127.0.0.1:8000
```

Documentacion interactiva:

```text
http://127.0.0.1:8000/docs
```

### Endpoints principales

```http
GET /api/search?q=iphone-15
GET /api/v1/products/compare?query=iphone-15
GET /api/v1/products/dashboard
GET /api/v1/products/{product_id}/analysis
```

## Celery

Con Docker, Redis y PostgreSQL levantados, abre una terminal para el worker:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy\backend-trendbuy
.\.venv\Scripts\Activate.ps1
celery -A services.celery_app.celery_app worker --loglevel=info --pool=solo
```

Abre otra terminal para el scheduler:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy\backend-trendbuy
.\.venv\Scripts\Activate.ps1
celery -A services.celery_app.celery_app beat --loglevel=info
```

Ejecutar tarea manualmente:

```powershell
celery -A services.celery_app.celery_app call services.tasks.scrape_prices
```

## Frontend

Configura variables:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy\frontend-trendbuy
Copy-Item .env.local.example .env.local
```

Contenido esperado:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_USE_MOCKS=false
```

Instala y arranca:

```powershell
npm install
npm run dev
```

Frontend local:

```text
http://localhost:3000
```

## Verificacion

Backend:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy\backend-trendbuy
.\.venv\Scripts\Activate.ps1
python .\scraper_poc.py
```

Frontend:

```powershell
cd C:\Users\alvro\Documents\proyectos\TrendBuy\frontend-trendbuy
npm run lint
```

## Notas

- Los precios se manejan como `Decimal` en backend y como string decimal en JSON.
- El endpoint `/api/search` existe para ser compatible con el contrato actual del frontend.
- Telegram no enviara alertas si faltan `TELEGRAM_BOT_TOKEN` o `TELEGRAM_CHAT_ID`.
- En Windows, Celery debe ejecutarse con `--pool=solo`.
