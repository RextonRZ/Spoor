"use client";
/**
 * App chrome, ported from review/refs/flow (owner 09:22: follow the prototype 100 %): one top bar with the logo,
 * Hub · Cases · Cameras, the tracking-number search, one "Synthetic demo hub" chip and the avatar menu (demo role
 * switch + model status). No sidebar.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { setSiteToRenderer } from "@/lib/frames";
import type { Capabilities, CaseListRow, Me, Site } from "@/lib/types";
import "./shell.css";

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const caps = useResource<Capabilities>("/v1/capabilities");
  useEffect(() => {
    if (caps.data) setSiteToRenderer(caps.data.site_to_renderer);
  }, [caps.data]);
  const nav = [
    { href: "/hub", label: "Hub", on: path.startsWith("/hub") },
    { href: "/", label: "Cases", on: path === "/" || path.startsWith("/cases") },
    { href: "/wall", label: "Cameras", on: path.startsWith("/wall") },
  ];
  return (
    <div className="tb-app">
      <a className="sp-skip" href="#main">Skip to content</a>
      <header className="tb">
        <Link href="/hub" className="tb-brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/spoor-mark-dark.svg" alt="" width={28} height={28} />
          <span>Spoor</span>
        </Link>
        <nav aria-label="Main" className="tb-nav">
          {nav.map((n) => <Link key={n.href} href={n.href} className="tb-link" aria-current={n.on ? "page" : undefined}>{n.label}</Link>)}
        </nav>
        <Find />
        <span className="tb-chip">Synthetic demo hub</span>
        <Account caps={caps.data} />
      </header>
      <main id="main" tabIndex={-1} className="tb-main">{children}</main>
    </div>
  );
}

/** Find a parcel by tracking number: an open case opens; else its scans at this hub and "Open a case". */
function Find() {
  const router = useRouter();
  const sites = useResource<Site[]>("/v1/sites");
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const [q, setQ] = useState("");
  const [hit, setHit] = useState<{ waybill: string; scans: number } | "none" | null>(null);
  const [busy, setBusy] = useState(false);
  const siteId = sites.data?.[0]?.site_id;
  async function go(e: React.FormEvent) {
    e.preventDefault();
    const v = q.trim().toUpperCase();
    if (!siteId || !/^[A-Z0-9]{6,40}$/.test(v)) return;
    const found = cases.data?.find((c) => c.case.target_description.toUpperCase().endsWith(v));
    if (found) { setQ(""); return router.push(`/cases/${found.case.case_id}`); }
    try {
      const r = await api<{ scans: unknown[] }>(`/v1/sites/${siteId}/parcels/carrier_waybill/${v}`);
      setHit(r.scans.length ? { waybill: v, scans: r.scans.length } : "none");
    } catch {
      setHit("none");
    }
  }
  async function open(waybill: string) {
    if (!siteId) return;
    setBusy(true);
    try {
      const r = await api<{ case: { case_id: string } }>("/v1/cases", { method: "POST", json: {
        site_id: siteId, question: `Where did parcel ${waybill} go after its last scan?`, target_description: `parcel ${waybill}`,
        identifiers: [{ scheme: "carrier_waybill", value: waybill }] } });
      invalidate("/v1/cases");
      setHit(null);
      setQ("");
      router.push(`/cases/${r.case.case_id}/investigate`);
    } finally { setBusy(false); }
  }
  return (
    <form className="tb-find" onSubmit={go} role="search">
      <label htmlFor="find" className="sp-sr">Find a parcel by tracking number</label>
      <input id="find" type="search" placeholder="Find a parcel by tracking number" value={q} autoComplete="off" spellCheck={false}
        onChange={(e) => { setQ(e.target.value); setHit(null); }} />
      {hit && (
        <div className="tb-hit" role="status">
          {hit === "none" ? "This tracking number has no scans at this hub." : (
            <>{hit.scans} scans of {hit.waybill}. No case yet.{" "}
              <button type="button" className="tb-hit-btn" disabled={busy} onClick={() => open(hit.waybill)}>{busy ? "Opening" : "Investigate"}</button></>
          )}
        </div>
      )}
    </form>
  );
}

/** The avatar: the one demo user (a supervisor who can do everything), Settings and the model status. No role switch. */
function Account({ caps }: { caps: Capabilities | undefined }) {
  const me = useResource<Me>("/v1/me");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="tb-account" ref={box}>
      <button type="button" className="tb-avatar" aria-label="Account menu" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        SV
      </button>
      {open && (
        <div className="tb-menu" role="menu" aria-label="Account">
          <p className="tb-menu-head">{me.error ? "Backend offline" : "Hub supervisor"}</p>
          <Link href="/operator" className="tb-menu-row" role="menuitem" onClick={() => setOpen(false)}>Settings &amp; data</Link>
          {caps && <p className="tb-menu-note">{caps.sam || caps.spark ? "Model keys connected" : "No model keys: model steps are off"}</p>}
        </div>
      )}
    </div>
  );
}

export async function postJson<T>(path: string, json?: unknown) {
  return api<T>(path, { method: "POST", json });
}
