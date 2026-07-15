import type { Category, DashboardResponse, Favorite, ProductAnalysis, ProductFamily, SearchResponse, User } from "./types";

// Server-only: Server Components run inside the Next.js server process, which
// can reach the backend directly (its own env var, never NEXT_PUBLIC_ - see
// getSearchProducts() below for why the browser can't use this same URL).
const SERVER_API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function getDashboard(): Promise<DashboardResponse> {
  const response = await fetch(`${SERVER_API_URL}/api/v1/products/dashboard`);

  if (!response.ok) {
    throw new Error(`Dashboard request failed: ${response.status}`);
  }

  return response.json();
}

// Client-only: the browser can never resolve the Docker-internal API hostname,
// so client components must go through the same-origin /backend/* proxy that
// next.config.ts rewrites to the real backend server-side.
const SEARCH_TIMEOUT_MS = 90_000;

export async function searchProducts(query: string): Promise<SearchResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), SEARCH_TIMEOUT_MS);

  try {
    const response = await fetch(
      `/backend/api/v1/search?q=${encodeURIComponent(query)}`,
      { signal: controller.signal },
    );

    if (!response.ok) {
      throw new Error(`Search request failed: ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

// "Paste a URL" quick-add: a single-page scrape, so it's much faster than a
// full 4-store keyword search but still a live Playwright navigation.
const TRACK_TIMEOUT_MS = 40_000;

export async function trackByUrl(url: string): Promise<ProductFamily> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TRACK_TIMEOUT_MS);

  try {
    const response = await fetch("/backend/api/v1/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail ?? `Track request failed: ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

// Analysis is cheap (reads already-persisted history, no live scraping), so
// it gets a much shorter timeout than searchProducts above.
const ANALYSIS_TIMEOUT_MS = 15_000;

export async function getProductAnalysis(productId: number): Promise<ProductAnalysis> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);

  try {
    const response = await fetch(`/backend/api/v1/products/${productId}/analysis`, {
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Analysis request failed: ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

// Outbound-click beacon: fires while the browser is already navigating away
// to the store, so it must never block or fail loudly - sendBeacon is built
// for exactly this, with keepalive-fetch as the fallback. Best-effort only.
export function reportOutboundClick(store: string, source: "dashboard" | "search" | "alert" | "web"): void {
  const body = JSON.stringify({ store, source });
  try {
    if (navigator.sendBeacon?.("/backend/api/v1/metrics/click", new Blob([body], { type: "application/json" }))) {
      return;
    }
    void fetch("/backend/api/v1/metrics/click", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // Metrics must never interfere with the user's click-out.
  }
}

// --- Auth ---------------------------------------------------------------
// All client-only, through the /backend proxy - same-origin, so the session
// cookie rides along automatically with no extra config on these calls.

export async function requestLogin(email: string): Promise<void> {
  const response = await fetch("/backend/api/v1/auth/request-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    throw new Error(`Login request failed: ${response.status}`);
  }
}

export async function confirmLogin(token: string): Promise<User> {
  const response = await fetch("/backend/api/v1/auth/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });

  if (!response.ok) {
    throw new Error(`Login confirm failed: ${response.status}`);
  }

  return response.json();
}

export async function logout(): Promise<void> {
  await fetch("/backend/api/v1/auth/logout", { method: "POST" });
}

export async function getMe(): Promise<User | null> {
  const response = await fetch("/backend/api/v1/auth/me");
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(`Me request failed: ${response.status}`);
  return response.json();
}

// "Continuar con Google" is a plain full-page navigation to this URL (see
// AuthMenu.tsx), never a fetch() - the backend replies with a 307 straight
// to accounts.google.com, and only a real browser navigation can follow
// that through Google's login UI, 2FA, etc.
export const GOOGLE_LOGIN_URL = "/backend/api/v1/auth/google/login";

export async function getAuthConfig(): Promise<{ google_login_enabled: boolean }> {
  const response = await fetch("/backend/api/v1/auth/config");
  if (!response.ok) throw new Error(`Auth config request failed: ${response.status}`);
  return response.json();
}

export async function getTelegramLinkCode(): Promise<{ deep_link: string }> {
  const response = await fetch("/backend/api/v1/auth/telegram/link-code", { method: "POST" });
  if (!response.ok) throw new Error(`Telegram link-code request failed: ${response.status}`);
  return response.json();
}

export async function unlinkTelegram(): Promise<void> {
  const response = await fetch("/backend/api/v1/auth/telegram/unlink", { method: "POST" });
  if (!response.ok) throw new Error(`Telegram unlink failed: ${response.status}`);
}

// --- Favorites & categories ----------------------------------------------

export async function getCategories(): Promise<Category[]> {
  const response = await fetch("/backend/api/v1/categories");
  if (!response.ok) throw new Error(`Categories request failed: ${response.status}`);
  const data = await response.json();
  return data.categories;
}

export async function getFavorites(): Promise<Favorite[]> {
  const response = await fetch("/backend/api/v1/favorites");
  if (!response.ok) throw new Error(`Favorites request failed: ${response.status}`);
  const data = await response.json();
  return data.favorites;
}

export type FavoriteInput = {
  producto_id?: number;
  categoria_id?: number;
  precio_maximo?: number | null;
  descuento_minimo_percent?: number | null;
};

export async function createFavorite(payload: FavoriteInput): Promise<Favorite> {
  const response = await fetch("/backend/api/v1/favorites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create favorite failed: ${response.status}`);
  }

  return response.json();
}

export async function deleteFavorite(id: number): Promise<void> {
  const response = await fetch(`/backend/api/v1/favorites/${id}`, { method: "DELETE" });
  if (!response.ok && response.status !== 404) {
    throw new Error(`Delete favorite failed: ${response.status}`);
  }
}
