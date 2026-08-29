import type { NextConfig } from "next";
import path from "path";

// `output: "export"` produces a static bundle that FastAPI serves from the same
// origin (see backend/app/main.py), so in production the browser calls /api/... on
// that same host and needs no proxy.
//
// `rewrites()` is NOT supported by a static export -- Next warns and drops it at
// build time. It was previously declared unconditionally, which made it look as
// though production traffic was being proxied to 127.0.0.1:8000 when nothing of the
// sort was happening. It is now scoped to `next dev`, which is the only mode that
// can honour it and the only mode that needs it (dev server on :3000, API on :8000).
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
  output: isDev ? undefined : "export",
  images: {
    unoptimized: true,
  },
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination:
                process.env.NEXT_PUBLIC_API_PROXY ?? "http://127.0.0.1:8000/api/:path*",
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
