import type { NextConfig } from "next";

// The /backend/* proxy is a custom Route Handler (src/app/backend/[...path]/route.ts),
// NOT next.config.ts rewrites(): rewrites() to an external destination has an
// undocumented ~30s hard timeout in this Next.js version - confirmed by live
// testing, it kills the connection ("socket hang up"/ECONNRESET) well before a
// real uncached search (30-49s against 4 live stores) finishes. A Route Handler
// uses a plain fetch() with its own timeout instead.
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
