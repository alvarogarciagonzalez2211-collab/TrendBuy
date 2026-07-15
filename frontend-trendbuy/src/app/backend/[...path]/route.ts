import { NextRequest, NextResponse } from "next/server";

// Custom proxy instead of next.config.ts rewrites(): rewrites() to an external
// destination has an undocumented ~30s hard timeout in this Next.js version
// (confirmed live - a real uncached search takes 30-49s against 4 stores and
// rewrites() killed the connection with ECONNRESET every time). A plain
// fetch() here has no such ceiling; SEARCH_TIMEOUT_MS bounds it explicitly
// instead, matching the client-side timeout in src/lib/api.ts.
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const PROXY_TIMEOUT_MS = 100_000;

async function proxy(request: NextRequest, path: string[]): Promise<NextResponse> {
  const targetUrl = `${API_URL}/${path.join("/")}${request.nextUrl.search}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  try {
    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    const cookie = request.headers.get("cookie");
    const headers: HeadersInit = hasBody ? { "Content-Type": "application/json" } : {};
    // The session cookie is same-origin from the browser's point of view
    // (it only ever talks to /backend/...) - the browser sends it here
    // automatically, but this proxy is a separate hop to API_URL and needs
    // to forward it by hand, or every authenticated request would silently
    // look logged-out to the actual backend.
    if (cookie) headers["cookie"] = cookie;

    // Telegram signs webhook calls with this header (api/telegram.py verifies
    // it against TELEGRAM_WEBHOOK_SECRET) - it has to survive this hop too,
    // same reasoning as the cookie forwarding above.
    const telegramSecret = request.headers.get("x-telegram-bot-api-secret-token");
    if (telegramSecret) headers["x-telegram-bot-api-secret-token"] = telegramSecret;

    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: hasBody ? await request.text() : undefined,
      signal: controller.signal,
    });

    const body = await upstream.text();
    const response = new NextResponse(body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });

    // Same idea in reverse: a Set-Cookie from the backend (login, logout)
    // has to be relayed to the browser as if this proxy weren't there.
    // Set-Cookie can't be safely read via a single header.get() (multiple
    // cookies can't be comma-joined), hence getSetCookie().
    for (const setCookie of upstream.headers.getSetCookie()) {
      response.headers.append("set-cookie", setCookie);
    }

    return response;
  } catch {
    return NextResponse.json({ error: "El backend no respondió a tiempo." }, { status: 504 });
  } finally {
    clearTimeout(timeout);
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}
