/**
 * Server-side proxy to the Spoor FastAPI backend. The browser never sees a bearer token: the token for the active
 * demo role (cookie `spoor_role`) is added here from server-only env vars (.env.local, see scripts/setup-local.mjs).
 * Only /v1/* and /healthz are forwarded. Streaming bodies (SSE job events, PNG frames) pass straight through.
 */
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const API = process.env.SPOOR_API_URL ?? "http://127.0.0.1:8000";
const TOKENS: Record<string, string | undefined> = {
  investigator: process.env.SPOOR_TOKEN_INVESTIGATOR,
  reviewer: process.env.SPOOR_TOKEN_REVIEWER,
  site_admin: process.env.SPOOR_TOKEN_SITE_ADMIN,
};

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const joined = path.join("/");
  if (!(joined === "healthz" || joined.startsWith("v1/"))) {
    return Response.json({ detail: "not a Spoor API path" }, { status: 404 });
  }
  const role = (await cookies()).get("spoor_role")?.value ?? "investigator";
  const token = TOKENS[role];
  if (!token) {
    return Response.json({ detail: `no token configured for role ${role}; run scripts/setup-local.mjs` },
      { status: 503 });
  }
  const url = `${API}/${joined}${req.nextUrl.search}`;
  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer(),
      cache: "no-store",
      signal: req.signal,
    });
  } catch {
    return Response.json({ detail: "Spoor backend is not reachable. Start it with: npm run backend" }, { status: 502 });
  }
  const out = new Headers();
  for (const h of ["content-type", "cache-control", "x-spoor-asset-kind", "content-disposition"]) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  if (upstream.headers.get("content-type")?.includes("text/event-stream")) {
    out.set("cache-control", "no-cache, no-transform");
    out.set("x-accel-buffering", "no");
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
