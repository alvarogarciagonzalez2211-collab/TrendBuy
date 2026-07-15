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

## 8. Login, favoritos y endurecimiento pre-PMV (sesión 2026-07-15)

**Login/usuarios** (migraciones `0006`/`0007`): enlace mágico por email (sin contraseña).
`api/auth.py` + `services/auth.py`. Token de un solo uso, caduca en 15 min, y el frontend
(`/auth/confirm`) exige un clic explícito antes de consumirlo — así un escáner de email que
pre-visite el link no quema el token del usuario real. Sesión vía cookie `HttpOnly` +
`SameSite=Lax` guardada en la tabla `sesiones` (no JWT, revocable al instante en logout).

**Favoritos** (`favoritos`, `categorias` — 8 categorías sembradas en la migración, taxonomía
de palabras clave en `services/categories.py`): un usuario puede favoritar un producto
concreto o una categoría entera, con `precio_maximo`/`descuento_minimo_percent` opcionales.
`services/favorite_notifier.py` decide a quién avisar por email en cada bajada de precio —
independiente del broadcast de Telegram/push que ya existía (umbral fijo 15%), no lo toca.

**Telegram por usuario — hecho (sesión 2026-07-15, tras el túnel de Cloudflare).** El bot de
Telegram original (broadcast, `TELEGRAM_CHAT_ID` fijo, `services/notifier.py::send_telegram_alert`)
sigue intacto y sin tocar. Añadido, aditivo, sin romper eso:
- Migración `0008`: `usuarios.telegram_chat_id` (BIGINT UNIQUE), `telegram_link_code` +
  `telegram_link_code_expira_en` (código de un solo uso, TTL 10 min).
- `services/auth.py`: `generate_telegram_link_code`/`consume_telegram_link_code`/`unlink_telegram`
  — vincular un chat ya usado por otra cuenta se lo transfiere (no falla el `UNIQUE`).
- `services/notifier.py`: `send_telegram_message` genérico (usado por el broadcast y por lo
  nuevo), `get_bot_username()` (cacheado, vía `getMe`), `set_telegram_webhook()`.
- `api/telegram.py` (nuevo router, `/api/v1`): `POST /auth/telegram/link-code` (autenticado,
  devuelve `t.me/<bot>?start=<code>`), `POST /auth/telegram/unlink`, `POST /telegram/webhook`
  (valida `X-Telegram-Bot-Api-Secret-Token` contra `TELEGRAM_WEBHOOK_SECRET`; procesa `/start
  <code>` para vincular y `/stop` para desactivar `notificaciones_activas` desde el propio
  chat). Los envíos de respuesta del webhook van envueltos en try/except (`_reply`) — un fallo
  de Telegram al mandar mensaje (usuario bloqueó el bot, chat inválido) no debe tirar un 500,
  o Telegram reintentaría el mismo update sin parar.
- `api/main.py`: en el `lifespan`, `_configure_telegram_webhook()` llama a `setWebhook` en
  cada arranque apuntando a `{FRONTEND_URL}/backend/api/v1/telegram/webhook` — se salta solo
  si `FRONTEND_URL` es `localhost` (Telegram exige HTTPS público) o si falta
  `TELEGRAM_WEBHOOK_SECRET`. Como `FRONTEND_URL` hoy es la URL del túnel de Cloudflare (cambia
  cada vez que se relanza `cloudflared`), esto es lo que mantiene el webhook sincronizado sin
  tocarlo a mano — mismo patrón que ya usaba el enlace mágico de login.
- `services/favorite_notifier.py`: si `usuario.telegram_chat_id` está vinculado, manda el aviso
  de bajada por Telegram (`send_telegram_deal_alert`) en vez de email — sin link de "darse de
  baja" (el `/stop` del bot hace ese papel).
- Frontend: `User.telegram_linked` (de `GET /auth/me`), `TelegramLinkPanel.tsx` en
  `/favoritos` — botón que pide el código, abre el deep-link, y hace polling a `getMe()` cada
  3s (aparte de `useAuth().refresh()`, para no parpadear el header entero) hasta detectar la
  vinculación o agotar ~2 min.
- El proxy (`frontend-trendbuy/.../backend/[...path]/route.ts`) reenvía ahora también la
  cabecera `x-telegram-bot-api-secret-token` — antes solo pasaba `cookie`, y sin esto el
  webhook nunca habría visto el secreto y todo update habría dado 401.
- **Probado en vivo**: migración aplicada limpia, `getWebhookInfo` confirma la URL del túnel,
  401 correcto sin secreto/sin sesión, 24 tests de pytest existentes siguen en verde tras el
  cambio de schema. **Pendiente de confirmar por el usuario**: el ciclo completo pulsando
  "Vincular Telegram" en el navegador real y enviando `/start <code>` desde la app de Telegram.

**Endurecimiento antes del PMV (esta sesión)**:
- `services/rate_limit.py`: límite en `/api/v1/auth/request-login` (5/email/hora,
  20/IP/hora vía Redis) — protege la cuenta de Gmail de envíos contra abuso. Detrás del
  proxy actual todas las peticiones llegan con la misma IP interna, así que el límite por
  IP hoy es efectivamente un tope global, no por visitante real — revisar si el tráfico
  crece.
- Baja de un clic: `GET /api/v1/auth/unsubscribe?token=` (token HMAC firmado con
  `SECRET_KEY`, sin estado en BD, no caduca). Cada email de aviso de bajada de precio la
  incluye. **`SECRET_KEY` debe fijarse en `.env` en producción** — si no, cada reinicio
  invalida todos los enlaces ya enviados (hay un fallback aleatorio por proceso solo para
  no romper en local).
- `backend-trendbuy/tests/` (pytest): cubre `matching.py`, `parse_price`/`parse_price_lines`
  de `scrapers.py`, `categories.py` y los tokens de `auth.py` — son regresiones directas de
  bugs reales encontrados en pruebas en vivo anteriores (separador de miles, badges de
  descuento, orden de la regex de tamaño de pantalla, fusión de colores/capacidad). Correr
  con `pytest` desde `backend-trendbuy/` (instalar `requirements-dev.txt`).
- `db_backup` en `docker-compose.yml`: `pg_dump` diario a un volumen separado
  (`trendbuy_backups`), retención 14 días. Es una red de seguridad local (mismo host), no
  sustituye una copia fuera del servidor para desastre real.
- `Caddyfile` + `docker-compose.prod.yml` (overlay): HTTPS automático vía Let's Encrypt.
  Uso: `DOMAIN=tudominio.com docker compose -f docker-compose.yml -f docker-compose.prod.yml
  up -d --build`. Deja `api`/`db`/`redis`/`frontend` sin puerto publicado — solo Caddy
  (80/443) queda expuesto. Antes de usarlo, en `.env`: `FRONTEND_URL=https://tudominio.com`,
  `COOKIE_SECURE=true`, `SECRET_KEY` fijo. **No probado en vivo** (sin dominio real
  disponible en este entorno) — solo verificado que el merge de compose resuelve bien.
- Pendiente, no bloqueante: rotar el app password de Gmail y el token de Telegram (se
  pegaron en texto plano en la conversación en algún momento de la sesión).

## 9. Si hay una sesión de Claude Code en paralelo

Hay (o puede haber) otra sesión trabajando en este mismo repo a la vez. Esta sección existe
para repartir el trabajo sin pisarse.

**Ahora mismo ocupado por la sesión "principal" (dominio/despliegue) — no tocar en paralelo:**
- `docker-compose.yml`, `docker-compose.prod.yml`, `Caddyfile`, cualquier `.env*`.
- `backend-trendbuy/services/auth.py`, `api/auth.py`, `api/telegram.py`, `api/main.py`,
  `services/notifier.py`, `services/favorite_notifier.py`, `services/rate_limit.py`
  (login/favoritos/Telegram-por-usuario, recién tocados — ver sección 8, Telegram-por-usuario
  probado contra el túnel pero pendiente de confirmación del usuario en el navegador real).
- `backend-trendbuy/services/affiliate.py` (nuevo), `services/search.py`, `api/main.py`,
  `services/tasks.py`, `frontend-trendbuy/src/lib/api.ts`,
  `frontend-trendbuy/src/components/SearchBar.tsx` — ver sección 10, puntos 1 y 2.
- `frontend-trendbuy/src/lib/AppProviders.tsx`, `lib/api.ts`, `lib/types.ts`,
  `components/TelegramLinkPanel.tsx`, `app/favoritos/page.tsx`,
  `app/backend/[...path]/route.ts` (mismo motivo).

**Libre para coger en paralelo sin conflicto, de más a menos autocontenido:**
1. **App móvil** (`app-trendbuy/`, no existe todavía — ver sección 4). Carpeta nueva,
   cero solape de archivos con el resto. React Native/Expo recomendado. Debe consumir la
   misma API REST (`/api/v1/search`, `/api/v1/products/dashboard`, `/api/v1/auth/*`,
   `/api/v1/favorites`) — no dupliques lógica de ranking/rebaja en el cliente (regla 4).
2. ~~Telegram por usuario~~ **Hecho** (ver sección 8) — ya no es tarea libre, ver el bloque
   de archivos ocupados arriba.
3. **Más tests pytest**: hoy solo hay unitarios puros (`matching.py`, `scrapers.py`,
   `categories.py`, tokens de `auth.py`). Faltan tests de integración con BD (persistencia,
   `services/search.py`, `services/persistence.py`) usando `sqlite+aiosqlite` en memoria —
   sin tocar los archivos que la sesión principal tiene abiertos (arriba).
4. **Paginación** en `/api/v1/products/dashboard` y `/api/v1/search` (roadmap desde hace
   tiempo, `api/main.py` — coordinar si la sesión principal también anda por ahí).
5. **Mejoras visuales pendientes** de una conversación anterior: sparkline de precio en las
   cards del dashboard (aparte del gráfico al expandir, que ya existe), skeleton loading
   durante la búsqueda en vez de solo texto. Toca `frontend-trendbuy/src/components/`.

Antes de empezar cualquiera de estos, `git pull`/revisa `git status` primero — si la sesión
principal ya ha hecho commits, puede que alguno de estos ya esté hecho o haya cambiado de
alcance.

## 10. Roadmap de producto y monetización (sesión 2026-07-15, tras auditoría comparativa)

Auditoría completa comparando TrendBuy contra Keepa, CamelCamelCamel, Idealo/PriceRunner,
Honey y PCPartPicker — resultado completo en un artifact de esa conversación (tabla de
capacidades + tabla de prioridades + tabla de monetización). Resumen ejecutable aquí para
que sobreviva a la sesión que lo generó:

**Conclusión de la auditoría:** TrendBuy ya está por delante en varias cosas (señal
"comprar/esperar" vía Prophet — ni Keepa lo tiene, solo heurísticas — y alertas
multicanal). Los dos gaps reales frente a los competidores que la gente usa a diario:
cero monetización (todo enlace sale a la tienda sin afiliado) y no se puede "trackear"
pegando una URL directa (todo pasa primero por búsqueda por palabra clave).

**Secuencia decidida (no en paralelo, en este orden):**

1. ~~Etiquetado de afiliados~~ **Hecho** (esta sesión). `services/affiliate.py::tag_url()`
   — Amazon Associates (`?tag=`) + deep-link por red de afiliación para PcComponentes/
   MediaMarkt/Worten. **Verificado por búsqueda web que no todas usan la misma red**
   (corrección sobre la primera versión de este plan, que asumía Awin para las tres):
   PcComponentes → Awin (merchant id público `20982` para España, ya puesto por
   defecto). MediaMarkt.es → **Tradedoubler**, no Awin. Worten.es → sin confirmar a
   fecha 2026-07-15 (solo se confirmó Worten Portugal en Awin, no España) — el módulo
   soporta ambas redes para Worten, se activa la que corresponda solo con rellenar su
   variable. Aplicado en los 4 puntos donde una URL de tienda llega a un humano:
   `services/search.py::_store_offers` (y su llamada a `notify_matching_favorites`),
   `api/main.py::get_products_dashboard`/`serialize_api_product`,
   `services/tasks.py::scrape_all_tracked_prices` (Telegram broadcast + push + favoritos).
   **No-op mientras las variables de entorno estén vacías** (ver bloque comentado en
   `.env.example`) — verificado en vivo contra el dashboard real que las URLs no
   cambian sin credenciales. **Pendiente del usuario, no de código:** darse de alta en
   Amazon Associates España, en Awin (para PcComponentes, y para Worten si resulta ser
   esa red) y en Tradedoubler (para MediaMarkt, y para Worten si resulta ser esa red),
   y rellenar las variables en `.env` — en cuanto estén, empieza a monetizar sin tocar
   nada más.
2. ~~"Trackear por URL"~~ **Hecho** (esta sesión). Pegar la URL de un producto de
   cualquiera de las 4 tiendas directamente en el buscador (`SearchBar.tsx` detecta que
   empieza por `http(s)://` y llama a `trackByUrl` en vez de `searchProducts`) añade ese
   producto a seguimiento sin pasar por búsqueda por keyword primero.
   `POST /api/v1/track` (`api/main.py`) → `services/search.py::track_url()`, que
   reutiliza `scraper/scrapers.py::scrape_store_url` (ya usado por `services/tasks.py`)
   y el mismo `persist_family`/`_family_payload` que ya usaba la búsqueda por keyword —
   la respuesta tiene la forma exacta de una `ProductFamily`, así que el frontend
   reutiliza `ProductFamilyCard`/`SearchResults` sin componente nuevo. Rechaza con 400
   URLs de tiendas no soportadas (`services/search.py::is_supported_store_url`) antes
   de lanzar Playwright, y con 422 si no se pudo leer el precio.
3. **Plan Pro — solo cuando haya usuarios recurrentes reales**, no antes. Palanca
   propuesta: refresco más rápido (horario en vez de diario/12h) para productos
   favoritos + favoritos ilimitados. Reutiliza la infraestructura de Celery ya existente
   (`services/tasks.py`), no necesita capacidad de scraping nueva — necesitaría Stripe
   (o similar) + una columna de "plan"/entitlement en `Usuario` + gating en
   `favorite_notifier.py`/el beat schedule. **No empezar sin que el usuario confirme
   pasarela de pago.**
4. **Anuncios — descartado por ahora, no reevaluar hasta ~100x el tráfico actual.**
   Rompen el posicionamiento "sin ruido" frente a sitios tipo Slickdeals y con el
   tráfico actual (pruebas vía túnel, sin dominio) no compensan el CPM.
5. **Extensión de navegador y API pública para desarrolladores — ideas reales, después
   de 1-3.** La extensión es la palanca de mayor impacto de toda la comparativa (es el
   producto entero de Keepa y de Honey), pero alto esfuerzo — si se aborda, empezar con
   un MVP mínimo (badge de estado + enlace de vuelta a TrendBuy), no un overlay completo.
6. Ideas descartadas conscientemente (no perseguir salvo que cambie el contexto):
   capa de cupones (cultura de códigos de descuento débil en Amazon.es/PcComponentes/
   MediaMarkt/Worten frente a EEUU, no justifica el coste de scraping/legal), capa
   social/votos estilo Slickdeals (necesita efecto de red que TrendBuy no tiene aún).

**Archivos que tocan los puntos 1 y 2** (añadir a la lista de "ocupados" de la sección 9
si se está trabajando en ello en paralelo): `services/affiliate.py` (nuevo),
`services/search.py`, `api/main.py`, `frontend-trendbuy/src/lib/api.ts`,
`frontend-trendbuy/src/components/SearchBar.tsx`.

## 11. Sesión 2026-07-15 (rama `claude/trendbuys-monetization-stores-v1yun5`) — monetización completa, más tiendas, filtro por interés

**Bug corregido — "todo es mínimo histórico en la primera búsqueda":** la causa era que
un producto recién scrapeado tiene un único punto de precio, así que su precio actual ES
su mínimo trivialmente. Ahora `classify_best_moment` (predictor.py) devuelve
`days_tracked` (días DISTINTOS con registros, no registros — un scrape de N tiendas es 1
día) y `has_price_history` (≥2 días, `MIN_HISTORY_DAYS_FOR_LOW`); tanto
`services/search.py::_family_payload` como el dashboard lo AND-ean en `is_historic_low`.
El frontend muestra en su lugar un hint azul "Nuevo en seguimiento — histórico en
construcción" (`TrackingSinceHint.tsx`). Verificado en vivo con BD sembrada (sqlite):
producto de 1 día sin badge, producto de 5 días en mínimo con badge. Tests en
`tests/test_predictor.py`.

**Monetización (punto 1 del roadmap, ampliado):**
- `services/affiliate.py` ahora es genérico: escanea TODAS las env
  `AFFILIATE_AWIN_MID_<TIENDA>` / `AFFILIATE_TRADEDOUBLER_PID_<TIENDA>` al importar —
  monetizar una tienda nueva es solo rellenar una variable (`<TIENDA>` = hostname sin
  puntos: DECATHLON, CASADELLIBRO...). Defaults previos intactos (PcComponentes→Awin
  20982). El hint de tienda quita espacios para casar "Casa del Libro"→casadellibro.
- Métricas de clics salientes: `POST /api/v1/metrics/click` (beacon del frontend vía
  `navigator.sendBeacon`, siempre 204, Redis hash por día+tienda, TTL 90 días, fallo de
  Redis silencioso) y `GET /api/v1/metrics/clicks?days=` (protegido con header
  `X-Admin-Key` == `SECRET_KEY`). `services/metrics.py`. Sin datos de usuario — solo
  tienda+superficie+día, para decidir qué programa de afiliación priorizar.
- Disclosure de afiliados en el footer (`SiteFooter.tsx`, requisito legal y de
  confianza) — en todas las páginas.

**Tiendas (de 4 → 11 en el registro):**
- `scraper/scrapers.py::KNOWN_STORES` es ahora LA fuente única de tiendas conocidas
  (marker de hostname → nombre visible). `services/search.py` deriva de ahí las URLs
  soportadas por `/api/v1/track`.
- **Scraper de detalle genérico `scrape_generic_product`** (JSON-LD schema.org Product →
  microdata itemprop fallback; `extract_jsonld_product` es función pura con tests). Esto
  arregla un hueco real: los enlaces de IKEA/Vinted/Druni que entraban por búsqueda NUNCA
  se refrescaban en la tarea de 12h (scrape_store_url no los soportaba) — ahora cualquier
  tienda del registro se refresca y se puede seguir por URL. OJO: los precios JSON-LD son
  formato máquina ("659.99") — `parse_jsonld_price`, NO `parse_price` (es-ES).
- Nuevas búsquedas por sección: **Decathlon + Sprinter** (deportes, Sprinter también en
  ropa), **Primor** (belleza, junto a Druni), **Casa del Libro** (libros). Implementadas
  con `StoreSearchConfig` + `search_store_by_config` (declarativo, cadenas de selectores
  con fallback) — añadir la próxima tienda son ~10 líneas de config.
- ⚠️ **Selectores de Decathlon/Sprinter/Primor/Casa del Libro SIN verificar en vivo**: el
  entorno de esta sesión tenía bloqueada la salida de red a las tiendas (403 del proxy).
  Fallan SUAVE (lista vacía, la búsqueda sigue con el resto). Primera sesión con red:
  lanzar una búsqueda real por sección y ajustar selectores contra el DOM real, como se
  hizo con las 4 originales. El scraper genérico de detalle NO depende de estos selectores.
- Secciones nuevas en `STORE_SECTION_KEYWORDS`: `deportes`, `libros`.

**Categorías y filtro por interés:**
- `services/categories.py`: + Deportes, Libros, Juguetes (14 categorías).
- Migración `0009`: siembra en `categorias` las que faltaban desde 0006 (Ropa, Hogar,
  Belleza — existían en la taxonomía pero no se podían favoritar por tema) + las 3 nuevas.
  Idempotente (solo inserta las ausentes). **Sin probar contra Postgres real en esta
  sesión** (no había BD) — sintaxis estándar, revisar en el primer `alembic upgrade head`.
- Frontend: chips de interés (`InterestChips.tsx` + `INTERESTS` en `lib/filters.ts`):
  Todo / Tecnología / Ropa y moda / Hogar / Belleza / Deportes / Libros y ocio. Un tap
  filtra dashboard y resultados de búsqueda (agrupa categorías del backend, no recalcula
  nada — regla 4). Integrado en `FilterableDeals` y `SearchBar`.

**Frontend además:** sparkline SVG del mínimo diario en las cards (`Sparkline.tsx`,
datos nuevos `history_spark`/`days_tracked` en dashboard y search — el dashboard ya
cargaba el historial por producto, coste cero), hero actualizado a "más de diez tiendas",
mensaje de búsqueda que explica que las tiendas dependen de la categoría. Probado en vivo
(build standalone + backend sqlite sembrado + Playwright): chips filtran bien, sparkline y
hint renderizan, `next build` limpio.

**También:** arreglado test flaky `test_unsubscribe_token_tampered_signature_rejected`
(~1/16 runs el "tamper" reproducía la firma original). Suite: 76 tests en verde.

**Pendiente que quedó de aquí:**
- Verificar en vivo los 4 scrapers nuevos (arriba) y qué red de afiliación usan
  Decathlon/Sprinter/Primor/Casa del Libro antes de rellenar sus variables.
- `alembic upgrade head` contra Postgres real (migración 0009).
- El plan Pro (punto 3 del roadmap) sigue bloqueado por decisión de pasarela de pago.
