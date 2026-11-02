import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // NEXT_DIST lets a production build sit beside a running dev server (both would use .next)
  distDir: process.env.NEXT_DIST || ".next",
  poweredByHeader: false,
  devIndicators: false,
  // The browser only ever talks to this Next.js server; /api/spoor/* proxies to FastAPI with a server-side token.
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "no-referrer" },
      ],
    }];
  },
};

export default config;
