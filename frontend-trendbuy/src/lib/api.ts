import type { DashboardResponse, SearchResponse } from "./types";

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
