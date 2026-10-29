"use client";
/**
 * Browser-side API access. Everything goes through the Next.js proxy (/api/spoor/*), which adds the bearer token.
 * A tiny shared cache keyed by path gives every panel explicit loading / error / data states and one `reload`.
 * A request that fails on the network is retried once automatically; a second failure is shown, never hidden.
 */
import { useCallback, useEffect, useSyncExternalStore } from "react";

export const API_BASE = "/api/spoor";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

function detailOf(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => (x && typeof x === "object" && "msg" in x ? String(x.msg) : String(x)))
      .join("; ");
  }
  return `request failed (${status})`;
}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const opts: RequestInit = { ...rest, cache: "no-store" };
  if (json !== undefined) {
    opts.body = JSON.stringify(json);
    opts.headers = { ...(rest.headers ?? {}), "content-type": "application/json" };
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, opts);
  } catch {
    if ((opts.method ?? "GET") !== "GET") throw new ApiError(0, "Network error. Nothing was changed; try again.");
    res = await fetch(`${API_BASE}${path}`, opts); // safe to repeat a read once
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) throw new ApiError(res.status, detailOf(body, res.status));
  return body as T;
}

/** URL for an image the backend serves through a signed link (frame_url values start with /v1/signed/...). */
export function signedUrl(path: string): string {
  return `${API_BASE}${path}`;
}

// --- shared resource cache --------------------------------------------------------------------------------------

interface Entry<T = unknown> {
  data?: T;
  error?: ApiError;
  loading: boolean;
  promise?: Promise<void>;
  at: number;
}

const cache = new Map<string, Entry>();
const listeners = new Map<string, Set<() => void>>();
const EMPTY: Entry = { loading: true, at: 0 };

function notify(key: string) {
  listeners.get(key)?.forEach((l) => l());
}

function load(key: string, force = false): Promise<void> {
  const cur = cache.get(key);
  if (cur?.promise && !force) return cur.promise;
  const entry: Entry = { ...(cur ?? { at: 0 }), loading: true };
  const p = api<unknown>(key)
    .then((data) => {
      cache.set(key, { data, loading: false, at: Date.now() });
    })
    .catch((e: unknown) => {
      const err = e instanceof ApiError ? e : new ApiError(0, String(e));
      cache.set(key, { data: cache.get(key)?.data, error: err, loading: false, at: Date.now() });
    })
    .finally(() => notify(key));
  entry.promise = p;
  cache.set(key, entry);
  notify(key);
  return p;
}

export function invalidate(prefix: string) {
  for (const key of cache.keys()) if (key.startsWith(prefix)) void load(key, true);
}

export function useResource<T>(path: string | null) {
  const subscribe = useCallback(
    (cb: () => void) => {
      if (!path) return () => {};
      if (!listeners.has(path)) listeners.set(path, new Set());
      listeners.get(path)!.add(cb);
      return () => listeners.get(path)?.delete(cb);
    },
    [path],
  );
  const snap = useSyncExternalStore(
    subscribe,
    () => (path ? (cache.get(path) ?? EMPTY) : EMPTY),
    () => EMPTY,
  ) as Entry<T>;
  useEffect(() => {
    if (path && !cache.get(path)?.at && !cache.get(path)?.promise) void load(path);
  }, [path]);
  const reload = useCallback(() => (path ? load(path, true) : Promise.resolve()), [path]);
  return { data: snap.data, error: snap.error, loading: path ? snap.loading && !snap.data : false, reload };
}
