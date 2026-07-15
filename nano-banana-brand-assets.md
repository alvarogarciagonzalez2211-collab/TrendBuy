# TrendBuy — brief de imágenes corporativas para Nano Banana

> **Estado: generadas e integradas (2026-07-15).** Las 6 imágenes de la sección 2 ya se
> generaron con estos prompts y están en `imgs/` (originales) y procesadas/integradas en:
> `frontend-trendbuy/src/app/icon.png` + `apple-icon.png` (favicon/app icon, detectados
> automáticamente por Next.js), `frontend-trendbuy/src/app/opengraph-image.jpg` (OG,
> idem), `frontend-trendbuy/public/empty-state.png` (estados vacíos de `DealsGrid`/
> `SearchResults`, ver `EmptyState.tsx`), `frontend-trendbuy/public/hero-pattern.png`
> (fondo del hero en `page.tsx`, solo modo claro) y `frontend-trendbuy/public/
> wordmark-lockup.png` (`auth/confirm/page.tsx`, solo modo claro). `imgs/Banner.png` se
> usa como cabecera de `README.md`. `imgs/Banner.png` **no** se conectó a los emails: hoy
> `services/email_sender.py` envía texto plano (`MIMEText(..., "plain")`), no HTML, así
> que no hay dónde insertar una imagen sin construir primero una plantilla HTML — se dejó
> fuera para no meter ese cambio de infraestructura sin pedirlo explícitamente. Si en algún
> momento se generan más assets con estos mismos prompts (variantes, tamaños nuevos), este
> documento sigue siendo la referencia de marca a seguir.

Este documento es un prompt-pack listo para pegar en **Nano Banana** (el generador de
imágenes Gemini 2.5 Flash Image de Google) para producir el set de identidad visual de
TrendBuy: logo, favicon/app icon, imagen social (OG) y algunos elementos de apoyo para que
la web se sienta más cuidada. Todavía no existe ningún asset de marca real en el repo —
`frontend-trendbuy/public/` solo tiene los SVG de ejemplo de Next.js y `imgs/favicon.png`
es un placeholder genérico — así que todo lo de abajo es nuevo.

**Nota de idioma:** los prompts están en inglés a propósito. Los modelos de generación de
imágenes (Nano Banana incluido) siguen mejor instrucciones detalladas en inglés que en
español; el texto de alrededor sí está en español para que sea fácil de seguir.

**No generar:** logos de Amazon, PcComponentes, MediaMarkt o Worten. La app ya los
representa con badges de color de marca (`StoreBadge.tsx`), no con logos — fabricar una
versión "parecida" de un logo ajeno es un problema de marca registrada. Todo lo de este
documento es exclusivamente para la identidad propia de TrendBuy.

---

## 1. Resumen de marca (para que todas las imágenes sean coherentes)

- **Nombre:** TrendBuy
- **Concepto:** comparador de precios que detecta el mejor momento de compra. La idea
  central es "tendencia de precio bajando en el momento justo" — no es solo un carrito de
  compra, es timing.
- **Icono ya en uso** (`src/components/Logo.tsx`): un cuadrado redondeado con degradado
  verde y una línea de tendencia descendente con una pequeña flecha en ángulo recto en la
  esquina, sobre fondo blanco. Cualquier logo nuevo debe poder convivir con este icono o
  sustituirlo manteniendo la misma idea (trend line + price drop), no introducir un
  concepto visual distinto.
- **Paleta** (Tailwind, tal cual se usa hoy en la UI):
  - Verde esmeralda (marca / positivo / "Óptimo"): `#10b981` (500), `#34d399` (400),
    `#059669` (600)
  - Zinc neutro (texto/fondo): `#18181b` (zinc-900, texto/dark bg), `#fafafa` (zinc-50)
  - Ámbar (mínimo histórico): `#f59e0b`
  - Rosa/rojo (badge de descuento): `#e11d48`
  - Azul cielo ("Buena Compra" / previsión): `#0ea5e9`
- **Tipografía de la UI:** Geist Sans — una geométrica/humanista moderna, no serif. Las
  imágenes no necesitan reproducir esta fuente exacta (los modelos de imagen no renderizan
  tipografía real de forma fiable), pero cualquier texto que aparezca en una imagen debe
  leerse como sans-serif moderno, no como script ni serif clásica.
- **Mood:** minimalista, confiable tipo fintech, mucho aire en blanco, esquinas
  redondeadas, sombras suaves, nada de ilustración recargada o mascotas.
- **Fondo:** todas las piezas deben funcionar tanto en fondo claro (`#ffffff`) como en
  fondo oscuro (`#0a0a0a`) — pedir siempre variante para ambos o un fondo transparente.

---

## 2. Lista de assets a generar

| # | Asset | Uso | Ruta destino sugerida | Tamaño |
|---|---|---|---|---|
| 1 | Icono/logomark cuadrado | Favicon, app icon, avatar | `frontend-trendbuy/public/icon.png` → derivar favicon | 512×512 |
| 2 | Lockup horizontal (icono + wordmark) | Cabeceras de email, README, redes | `imgs/logo-horizontal.png` | 1200×400 |
| 3 | Imagen Open Graph / social preview | `og:image` al compartir el link | `frontend-trendbuy/public/og-image.png` | 1200×630 |
| 4 | Ilustración vacío/"sin resultados" | Estados vacíos del buscador y favoritos | `frontend-trendbuy/public/empty-state.png` | 800×800, fondo transparente |
| 5 | Banner de email (magic link / alertas) | Cabecera de los correos de `services/favorite_notifier.py` | `imgs/email-banner.png` | 1200×300 |
| 6 | Textura/patrón de fondo sutil (opcional) | Fondo del hero de la home | `frontend-trendbuy/public/hero-pattern.png` | 1600×900, muy sutil |

---

## 3. Prompts

### 3.1 Icono/logomark cuadrado (asset #1)

```
Minimal flat vector-style app icon for a price-comparison product called
"TrendBuy". Rounded-square icon, generous corner radius (like a modern iOS/
Android app icon). Background: smooth diagonal gradient from emerald green
#34d399 (top-left) to #059669 (bottom-right). Centered on top of the
gradient: a simple white line-art glyph combining a downward price-trend
line with a small right-angle arrowhead at the bottom, evoking "price going
down" — clean geometric strokes, rounded line caps, no gradient on the
glyph itself, pure white. No text, no other elements, no drop shadow, no
mascot, no photorealism. Flat modern fintech app-icon style, crisp edges,
centered composition, plenty of padding around the glyph. Square canvas,
solid background all the way to the edges (no transparency).
```

### 3.2 Lockup horizontal — icono + wordmark (asset #2)

```
Horizontal logo lockup for a brand called "TrendBuy". On the left, a small
rounded-square icon with an emerald green gradient (#34d399 to #059669)
containing a simple white downward price-trend line glyph with a right-
angle arrowhead. To the right of the icon, the wordmark "TrendBuy" in a
bold, modern geometric sans-serif typeface, dark charcoal color #18181b,
tight letter spacing. Icon and text vertically centered and aligned.
Plenty of negative space around the lockup. Background: solid white.
Flat minimal vector style, no shadows, no textures, no extra decoration.
```

Pide también una segunda pasada con **fondo transparente** y otra en **texto blanco sobre
fondo `#0a0a0a`** para la variante oscura — Nano Banana no siempre exporta alfa real, así
que si sale con fondo sólido, generar la versión clara y la oscura por separado en vez de
depender de recortar transparencia.

### 3.3 Imagen Open Graph / social preview (asset #3)

```
Wide social-media preview image (1200x630, 1.91:1 landscape) for a price-
comparison web app called "TrendBuy". Background: soft off-white #fafafa
with a very subtle light emerald green gradient glow in one corner. Left
third: the TrendBuy logomark, a rounded-square emerald gradient icon with a
white downward price-trend line glyph, sitting above the bold wordmark
"TrendBuy" in dark charcoal geometric sans-serif. Right two-thirds: a
clean, minimal flat illustration of a price tag with a downward arrow and
a small circular badge showing a percentage discount shape (no real
numbers or text needed, just the abstract shape of a discount badge and
price tag). Generous white space, soft rounded shapes, no photorealism, no
clutter, corporate-clean fintech style, flat vector illustration.
```

### 3.4 Ilustración de estado vacío (asset #4)

```
Simple, friendly flat vector illustration for an empty state on a price-
tracking app, transparent background. A minimal magnifying glass icon
tilted slightly, outlined in dark charcoal #18181b with a thin emerald
green #10b981 accent line inside the lens forming a small downward price-
trend squiggle. Very minimal, few shapes, generous line weight, rounded
line caps, no color fill besides the emerald accent, no text, no
background shapes, no shadow. Centered composition with padding on all
sides, square canvas.
```

### 3.5 Banner de cabecera de email (asset #5)

```
Wide email header banner (1200x300, 4:1 landscape), solid emerald green
background #059669 with a subtle diagonal gradient to #10b981. Centered:
the TrendBuy logomark in white — a rounded-square outline containing a
white downward price-trend line glyph — next to the wordmark "TrendBuy" in
bold white geometric sans-serif. Minimal, corporate, flat design, no
photography, no clutter, plenty of even padding around the centered
lockup, suitable as an email header image.
```

### 3.6 Patrón de fondo sutil para el hero (asset #6, opcional)

```
Extremely subtle, low-contrast abstract background pattern, 1600x900,
mostly solid white #ffffff with faint (under 8% opacity) thin diagonal
lines suggesting ascending/descending price-trend charts, in emerald green
#10b981. Very minimal and quiet, meant to sit behind text without ever
competing with it for attention. No sharp shapes, no icons, no text, no
strong gradients — almost imperceptible texture only.
```

---

## 4. Después de generar

1. **Favicon multi-tamaño:** a partir del asset #1 (512×512), generar `favicon.ico`
   (16/32/48 embebidos), `apple-touch-icon.png` (180×180) y `icon-192.png`/`icon-512.png`
   si en algún momento se añade un manifest PWA. Cualquier herramienta de conversión
   local sirve (Nano Banana no genera `.ico` directamente).
2. **Transparencia:** para los assets que necesitan fondo transparente (#1 variante icon,
   #4) y Nano Banana no la entregue limpia, quitar el fondo con una herramienta de
   remoción de fondo antes de usarlos en `public/`.
3. **Optimizar antes de commitear:** son PNG de generación de IA, suelen pesar más de lo
   necesario — pasar por un compresor (ej. `oxipng`/`pngquant`) antes de meterlos en
   `frontend-trendbuy/public/` u `imgs/`.
4. **Vectorizar si hace falta un SVG real:** el logomark (#1/#2) es candidato a tener
   también una versión SVG a mano (o vectorizada) para usarlo nítido en `Logo.tsx` en vez
   de un PNG — un SVG a partir del mismo trazo que ya usa `Logo.tsx` hoy es más barato que
   vectorizar la imagen generada.
5. **Sustituir en el código** una vez generados y optimizados:
   - `frontend-trendbuy/src/app/layout.tsx` → añadir `icons` en el `Metadata` apuntando al
     favicon nuevo.
   - `frontend-trendbuy/src/app/layout.tsx` → añadir `openGraph.images` apuntando a
     `og-image.png`.
   - `frontend-trendbuy/src/components/Logo.tsx` → si se sustituye el SVG inline por el
     logomark nuevo, mantener el mismo tamaño (`h-9 w-9`) y el mismo gradiente para no
     romper la coherencia con el resto de la UI.
