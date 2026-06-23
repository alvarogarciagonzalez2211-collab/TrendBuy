# CONTEXTO: PRICE TRACKER Y PREDICCIÓN DE MERCADO

**Objetivo:** Plataforma para rastrear, comparar y predecir precios en e-commerces, con alertas de momento ideal de compra.

## 1. STACK TECNOLÓGICO
* **Backend/API:** Python 3.11+, FastAPI (asíncrono).
* **Scraping:** Playwright (emulación real para evitar bloqueos).
* **Datos y ML:** Pandas, Numpy, Prophet (predicción de series temporales).
* **DB:** PostgreSQL (relacional e historial temporal).
* **Tareas/Colas:** Celery + Redis (Message Broker).
* **Frontend:** Next.js (React)

## 2. FUNCIONES CORE
* **F1. Comparador y Normalización:**
  * Uso de *Fuzzy Match* (`FuzzyWuzzy`/`RapidFuzz`) y/o códigos universales (EAN/UPC) para mapear el mismo producto en distintas tiendas.
* **F2. "Mejor Momento" y Predicción:**
  * *Evaluación:* Precio actual en percentil < 25 del historial = "Buena Compra". Cerca del mínimo histórico = "Óptimo".
  * *Predicción:* Modelo `Prophet` para detectar estacionalidad (ej. Black Friday) y predecir precios a 15-30 días con intervalo de confianza.
* **F3. Alertas (Chollos):**
  * *Cron jobs* vía Celery para scraping cadenciado.
  * *Gatillo de Bajada:* `((Precio_Ant - Precio_Act) / Precio_Ant) * 100` > Umbral (ej. 15%).
  * *Notificación:* API Telegram (prioridad inicial) o Email.

## 3. SCHEMA POSTGRESQL (MÍNIMO)
```sql
CREATE TABLE productos (id SERIAL PRIMARY KEY, nombre VARCHAR(255) NOT NULL, ean VARCHAR(13) UNIQUE);
CREATE TABLE enlaces_tiendas (id SERIAL PRIMARY KEY, producto_id INT REFERENCES productos(id) ON DELETE CASCADE, tienda VARCHAR(100), url TEXT, sku VARCHAR(100), precio_actual NUMERIC(10,2), actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE historial_precios (id BIGSERIAL PRIMARY KEY, enlace_id INT REFERENCES enlaces_tiendas(id) ON DELETE CASCADE, precio NUMERIC(10,2), fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
```

## 4. REGLAS DE CÓDIGO PARA AGENTES
1. **Estructura:** Modularizar en `/scraper`, `/api`, `/models`, `/services`.
2. **Resiliencia:** Playwright con rotación de User-Agent, timeouts manejados vía `try-except` y esperas explícitas.
3. **Rendimiento:** Uso estricto de `async/await` para I/O y FastAPI.
4. **Precisión Financiera:** Precios siempre en `Decimal` (o float redondeado a 2 decimales).
5. **Fase 1 (Actual):** Crear PoC (Prueba de Concepto) aislada con Playwright enfocada en extraer (Nombre, Precio, URL) de 1 producto en 2 tiendas específicas.