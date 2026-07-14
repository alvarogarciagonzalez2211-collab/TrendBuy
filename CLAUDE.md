# CLAUDE.md — Contexto TrendBuy (leer esto ANTES de explorar el repo)

> Este archivo existe para que Claude Code no tenga que recorrer todo el proyecto en cada
> sesión. Contiene la arquitectura real, qué está implementado de verdad vs. qué es solo un
> esqueleto, y la especificación de las 2 features nuevas pedidas por el usuario.
> **Si necesitas confirmar algo puntual, abre solo el archivo concreto listado abajo — no
> hace falta re-escanear `backend-trendbuy/` ni `frontend-trendbuy/` enteros.**

## 0. Qué es TrendBuy
Plataforma para comparar precios de productos en varias tiendas online, detectar el mejor
momento de compra (percentil histórico) y avisar cuando hay un chollo (bajada de precio).

## 1. Estado REAL del código (importante, no asumir más de lo que hay)

| Pieza | Estado | Detalle |
|---|---|---|
| `backend-trendbuy/api/main.py` | Funcional | Endpoints originales (`GET /api/search`, `GET /api/v1/products/compare`, `GET /api/v1/products/dashboard`, `GET /api/v1/products/{id}/analysis`) **+ nuevos** `GET /api/v1/search?q=` y `POST /api/v1/devices`. |
| `backend-trendbuy/scraper/scrapers.py` | **Funcional, verificado en vivo (2026-07-14)** | Scraper genérico multi-tienda por keyword: **Amazon.es, PcComponentes, MediaMarkt.es, Worten.es** (El Corte Inglés y Fnac se probaron en vivo y devuelven 403 "Access Denied" de su WAF — bloqueo de red, no de selectores — se descartaron y Worten los sustituye). `scrape_search_all(keyword)` lanza los 4 en paralelo. Selectores confirmados contra HTML real, no adivinados. Contexto Playwright con bloqueo de recursos (imágenes/fuentes/media) + parche `navigator.webdriver` para acelerar y reducir detección. Los scrapers de detalle originales (`scrape_amazon`/`scrape_pccomponentes`) siguen intactos para no romper `services/tasks.py`. |
| `models/database.py` | Funcional | 4 tablas: `productos`, `enlaces_tiendas`, `historial_precios`, **`dispositivos`** (push tokens). Migraciones con **Alembic** (`alembic/`, ya no usa `create_all`) — probado con `alembic upgrade head` limpio contra una BD nueva. |
| `services/matching.py` | **Nuevo, funcional** | Fuzzy matching (RapidFuzz) para agrupar variantes del mismo producto entre tiendas sin EAN. La señal de familia usa 4 componentes: `base` (fuzzy), y 3 sets de coincidencia EXACTA — `variants` (Pro/Max/Plus...), `numbers` (generación: 13/14/15...) y `colors`/`storage` (color y capacidad, que SÍ cambian el precio real y no deben fusionarse). Verificado contra datos reales de las 4 tiendas — cualquier cambio aquí, probar con búsquedas reales, no solo casos sintéticos. |
| `services/search.py` + `services/persistence.py` | **Nuevo, funcional** | Orquesta scrape → agrupar por familia → persistir (fuzzy, no exact-match) → `is_historic_low` con tolerancia 0 → ordenar. Cachea la respuesta completa en Redis 15 min (evita re-scrapear las 4 tiendas en cada búsqueda repetida; si Redis no responde, no rompe la búsqueda, solo se salta el caché). |
| `services/predictor.py` | Funcional | Clasifica "Óptimo / Buena Compra / Esperar" por percentil 25 e histórico mínimo. Prophet para forecast 30 días. Reutilizado tal cual por `services/search.py`. |
| `services/notifier.py` + `services/tasks.py` | Funcional | Telegram sin tocar (regla dura). **+ push aditivo**: `services/push_notifier.py` (Expo) se dispara junto a Telegram en el mismo umbral de bajada >15%, sin modificar la ruta de Telegram. |
| `frontend-trendbuy/` | **Funcional, probado en vivo (2026-07-14)** | Next.js 16 (App Router, TS, Tailwind 4), `output: 'standalone'`. Pantalla principal: `SearchBar` (submit, no autocompletado — una búsqueda real tarda 30-49s sin caché) + `DealsGrid` (dashboard SSR). **OJO con el proxy**: no usa `next.config.ts` `rewrites()` — probado en vivo y tiene un timeout ~30s no documentado que corta búsquedas reales con ECONNRESET. El proxy es un Route Handler a mano en `src/app/backend/[...path]/route.ts` con su propio `fetch`/timeout (100s). El navegador SIEMPRE llama a `/backend/...` (same-origin); nunca a `API_URL` directo (ese hostname es interno de Docker, no resoluble desde el navegador) — variable server-only, sin prefijo `NEXT_PUBLIC_`. |
| App móvil | **No existe** | Sigue sin crear — fuera de alcance de esta sesión. |

**Conclusión clave:** el gap #1 (búsqueda genérica multi-tienda) y la pantalla principal
del frontend **están cerrados y probados en vivo** (build + `node .next/standalone/server.js`
contra el backend real, dashboard SSR y búsqueda vía proxy confirmados con datos reales).
Lo que falta ahora es la app móvil (ver roadmap de la sesión de 2026-07-14 para ideas de
hardening del backend: observabilidad/tests automatizados/proxy rotation si el bloqueo de
tiendas se vuelve un problema).

**Nota de integridad del repo:** `frontend-trendbuy/` estaba commiteado río arriba como una
referencia de submódulo git huérfana (`160000 commit ...`, sin `.gitmodules`) — por eso
`git clone` siempre lo dejaba vacío. Se arregló con `git rm --cached frontend-trendbuy` +
`git add` normal antes de commitear el Next.js real. Si alguna vez `frontend-trendbuy`
vuelve a aparecer vacío tras un clone, comprobar `git ls-tree HEAD -- frontend-trendbuy`
por si reaparece el modo `160000`.

## 2. Las 2 cosas que quiere el usuario

1. **Web (la original)**: se queda tal cual en su rol de notificar por **Telegram**. No
   hay que quitar ni tocar `services/notifier.py` / `services/tasks.py`. La web además
   necesita el frontend (hoy vacío) con la UI descrita en la sección 3.
2. **App (nueva)**: mismo backend, pero en vez de (o además de) Telegram, manda
   **notificaciones push nativas** directamente al móvil (FCM/APNs o Expo Notifications).
   Debe consumir la misma API REST de `backend-trendbuy`.

Ambas comparten backend y lógica de scraping/ranking — no se duplica lógica de negocio,
solo el canal de notificación y la capa de presentación.

## 3. Especificación funcional (pantalla principal + buscador)

### Pantalla principal
- Grid/lista de **mejores ofertas actuales** obtenidas por el scraping (las que ya
  superan el umbral de rebaja o están en zona "Óptimo"/"Buena Compra" según
  `classify_best_moment`). Viene de una versión ampliada de `/api/v1/products/dashboard`.

### Buscador (justo encima de las ofertas, en la misma pantalla)
Búsqueda por palabra clave (ej. `iphone`) que debe:
1. Encontrar **todos los modelos relacionados** (iPhone 13, 14, 15, 16, 17...), no solo
   coincidencia exacta.
2. Para cada modelo, listar **todas las tiendas donde se vende**, cada una con su precio.
3. Ordenar los resultados por **% de rebaja** y por si es **mínimo histórico**, no por
   relevancia de texto.
4. Dentro de cada modelo, las tiendas se ordenan **precio más barato primero**.
5. Marcar con una anotación visible cuándo el precio actual **es el mínimo histórico real**
   (comparado contra `historial_precios`, no una estimación) — reutilizar
   `classify_best_moment` / `historic_min` de `services/predictor.py`, y solo mostrar el
   badge si `current_price <= historic_min` (con tolerancia 0, no el 5% que usa "Óptimo").
6. Cada resultado lleva enlace de compra directo (`url` de `enlaces_tiendas`).

### Gaps técnicos — estado a 2026-07-14
- ~~Scraper genérico multi-tienda~~ **Hecho.** Amazon, PcComponentes, MediaMarkt, Worten.
  No usa `familia_id` en la tabla `productos` — el agrupamiento se hace en tiempo de
  petición vía fuzzy matching (`services/matching.py`) contra `Producto.nombre`, sin
  necesidad de columna nueva ni migración para esto en concreto.
- ~~Matching difuso (F1 de `context.md`)~~ **Hecho** con RapidFuzz, no FuzzyWuzzy (más
  rápido, misma idea). Ver `services/matching.py` para el diseño de la señal.
- ~~Endpoint `GET /api/v1/search?q=`~~ **Hecho**, con caché Redis de 15 min.
- ~~Tabla de dispositivos/push~~ **Hecho**, `dispositivos` + `services/push_notifier.py`
  (Expo), broadcast-only (igual que Telegram, sin suscripción por producto).
- Pendiente (no hecho esta sesión, ver roadmap): tests automatizados (pytest) para
  `matching.py`/`parse_price`, observabilidad (logs estructurados, métricas de
  éxito/fallo por tienda), rotación de proxies si Amazon/MediaMarkt empiezan a bloquear
  con más frecuencia, paginación en `/api/v1/search` y `/api/v1/products/dashboard`.

## 4. Dónde tocar cada cosa (evitar abrir todo el repo)
- Nuevo endpoint de búsqueda → `backend-trendbuy/api/main.py` + nuevo módulo
  `backend-trendbuy/services/search.py` (crear).
- Lógica de "es mínimo histórico" → ya existe en `backend-trendbuy/services/predictor.py`
  (`classify_best_moment`), reutilizar, no reescribir.
- Notificaciones Telegram (web) → `backend-trendbuy/services/notifier.py` +
  `backend-trendbuy/services/tasks.py` (no tocar salvo bugs).
- Notificaciones push (app) → nuevo módulo `backend-trendbuy/services/push_notifier.py` +
  nueva tabla `dispositivos` en `models/database.py`.
- Scraper multi-tienda/multi-modelo → reescribir `backend-trendbuy/scraper/scrapers.py`
  (hoy `AMAZON_URL`/`PCCOMPONENTES_URL` están hardcodeadas al inicio del archivo).
- Frontend web → `frontend-trendbuy/` (vacío, crear proyecto Next.js nuevo).
- App móvil → nueva carpeta en la raíz, ej. `app-trendbuy/` (React Native/Expo recomendado
  por reutilizar TypeScript con el frontend si se hace en Next.js).

## 5. Stack y convenciones (del `context.md` original del repo, resumido)
- Backend: Python 3.11+, FastAPI async, SQLAlchemy async, Playwright, Celery + Redis,
  Pandas/Prophet, PostgreSQL.
- Precios siempre en `Decimal`, redondeo `ROUND_HALF_UP` a 2 decimales.
- Async/await estricto para I/O.
- Estructura modular: `/scraper`, `/api`, `/models`, `/services`.

## 6. Comandos útiles
```powershell
# Backend
cd backend-trendbuy; .\.venv\Scripts\Activate.ps1; uvicorn api.main:app --reload
# Celery
celery -A services.celery_app.celery_app worker --loglevel=info --pool=solo
celery -A services.celery_app.celery_app beat --loglevel=info
# Docker (Postgres + Redis)
docker compose up -d
```

## 7. Reglas para Claude Code en este proyecto
1. No reescribir `notifier.py`/`tasks.py` (Telegram) salvo que se pida explícitamente.
2. Antes de crear el buscador genérico, confirmar con el usuario qué tiendas soportar
   además de Amazon y PcComponentes (impacta selectores Playwright).
3. Cualquier cambio de schema en `models/database.py` requiere migración (hoy usa
   `Base.metadata.create_all`, no hay Alembic — valorar añadirlo si el schema crece).
4. Frontend y app deben consumir la misma API; no dupliques lógica de ranking/rebaja en
   el cliente, que se calcule en backend y se sirva ya ordenado.
