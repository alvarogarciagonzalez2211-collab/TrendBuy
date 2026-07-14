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
    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers: hasBody ? { "Content-Type": "application/json" } : undefined,
      body: hasBody ? await request.text() : undefined,
      signal: controller.signal,
    });

    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
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
