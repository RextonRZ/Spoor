"use client";
/**
 * App chrome, ops-console style (owner 31 Oct: enterprise, dark): a left sidebar (logo, Hub · Cases · Cameras,
 * Settings, the account at the foot) and, over each page, a thin header with the page's name and the tracking-number
 * search ("/" focuses it; keyboard actions never animate). The current page carries a small indigo marker. Phones: the
 * sidebar folds into a top bar with the same links as icons.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { setSiteToRenderer } from "@/lib/frames";
import type { Capabilities, CaseListRow, Me, Site } from "@/lib/types";
import { STAGES, stageOf } from "@/lib/places";
import { hhmm } from "@/lib/words";
import "./shell.css";

const ICONS: Record<string, ReactNode> = {
  hub: <path d="M10 3.2 3 6.6v6.8l7 3.4 7-3.4V6.6zM3 6.6l7 3.4 7-3.4M10 10v6.8" />,
  cases: <path d="M3.5 6.5h13v9a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1zM7.5 6.5V4.8a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.7M3.5 10.5h13" />,
  cams: <path d="M3 6.5h9.5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1zM13.5 9l4-2.2v6.4l-4-2.2" />,
  settings: <path d="M10 12.4a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8zM16 10c0-.5 0-.9-.1-1.3l1.6-1.3-1.5-2.6-2 .7a6 6 0 0 0-2.2-1.3L11.5 2h-3l-.3 2.2A6 6 0 0 0 6 5.5l-2-.7-1.5 2.6 1.6 1.3a6 6 0 0 0 0 2.6l-1.6 1.3 1.5 2.6 2-.7a6 6 0 0 0 2.2 1.3l.3 2.2h3l.3-2.2a6 6 0 0 0 2.2-1.3l2 .7 1.5-2.6-1.6-1.3c.1-.4.1-.8.1-1.3z" />,
};
// collapsed or expanded: a per-viewer convenience, remembered in this browser (blocked storage: expanded)
const SB_KEY = "spoor.sidebar";
const readCollapsed = () => { try { return localStorage.getItem(SB_KEY) === "rail"; } catch { return false; } };
const onCollapsedChange = (cb: () => void) => {
  window.addEventListener(SB_KEY, cb);
  window.addEventListener("storage", cb);
  return () => { window.removeEventListener(SB_KEY, cb); window.removeEventListener("storage", cb); };
};

const Icon = ({ name }: { name: string }) => (
  <svg className="sb-icon" viewBox="0 0 20 20" aria-hidden="true">{ICONS[name]}</svg>
);

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const caps = useResource<Capabilities>("/v1/capabilities");
  const sites = useResource<Site[]>("/v1/sites");
  useEffect(() => {
    if (caps.data) setSiteToRenderer(caps.data.site_to_renderer);
  }, [caps.data]);
  const nav = [
    { href: "/hub", label: "Hub", icon: "hub", on: path.startsWith("/hub") || path.startsWith("/cases") }, // cases live on the Hub
    { href: "/wall", label: "Cameras", icon: "cams", on: path.startsWith("/wall") },
  ];
  const settings = { href: "/operator", label: "Settings", icon: "settings", on: path.startsWith("/operator") };
  const page = [...nav, settings].find((n) => n.on)?.label ?? "Spoor";
  const collapsed = useSyncExternalStore(onCollapsedChange, readCollapsed, () => false);
  const toggle = () => {
    try { localStorage.setItem(SB_KEY, collapsed ? "full" : "rail"); } catch { /* storage blocked */ }
    window.dispatchEvent(new Event(SB_KEY));
  };
  if (path === "/") return <>{children}</>; // the landing page (before the app) has its own header
  return (
    <div className="tb-app sb-app" data-rail={collapsed ? "" : undefined}>
      <a className="sp-skip" href="#main">Skip to content</a>
      <aside className="sb" aria-label="Spoor">
        <Link href="/hub" className="sb-brand" aria-label="Spoor, the hub">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="tb-logo tb-logo-dark" src="/brand/spoor-logo-dark.png" alt="Spoor" width={93} height={30} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="tb-logo tb-logo-light" src="/brand/spoor-logo-light.png" alt="" aria-hidden="true" width={94} height={30} />
        </Link>
        <nav aria-label="Main" className="sb-nav">
          <p className="sb-group">Workspace</p>
          {nav.map((n) => (
            <Link key={n.href} href={n.href} className="sb-link" aria-current={n.on ? "page" : undefined} title={collapsed ? n.label : undefined}>
              <Icon name={n.icon} /><span>{n.label}</span>
            </Link>
          ))}
          <span className="sb-rule" aria-hidden="true" />
          <Link href={settings.href} className="sb-link" aria-current={settings.on ? "page" : undefined} title={collapsed ? settings.label : undefined}>
            <Icon name={settings.icon} /><span>{settings.label}</span>
          </Link>
        </nav>
        <button type="button" className="sb-toggle" onClick={toggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand" : "Collapse"}>
          <svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="4" width="14" height="12" rx="2" /><path d="M8 4v12" />{collapsed ? <path d="m11.5 8 2 2-2 2" /> : <path d="m13.5 8-2 2 2 2" />}</svg>
          <span>Collapse</span>
        </button>
        <Account caps={caps.data} />
      </aside>
      <div className="sb-main">
        <header className="sb-top">
          <p className="sb-title">{page}</p>
          <Find siteId={sites.data?.[0]?.site_id} />
        </header>
        <main id="main" tabIndex={-1} className="tb-main">{children}</main>
      </div>
    </div>
  );
}

interface Sugg { id: string; last: { t: string; point: string } | null; case_id: string | null }

/** Find a parcel by tracking number: an open case opens; else its scans at this hub and "Investigate". From 3 characters,
 *  the parcels scanned today that match drop down (GET /sites/{id}/parcels?q=, 140 ms after typing stops): arrow keys
 *  and Enter, or click; a parcel in a case opens the case, any other opens in the Hub's Parcels tab. */
function Find({ siteId }: { siteId: string | undefined }) {
  const router = useRouter();
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const input = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [hit, setHit] = useState<{ waybill: string; scans: number } | "none" | null>(null);
  const [busy, setBusy] = useState(false);
  const [sugg, setSugg] = useState<Sugg[]>([]);
  const [active, setActive] = useState(-1);
  const timer = useRef(0);
  function suggest(v: string) {
    window.clearTimeout(timer.current);
    const t = v.trim().toUpperCase();
    if (!siteId || t.length < 3) { setSugg([]); setActive(-1); return; }
    timer.current = window.setTimeout(async () => {
      try {
        const r = await api<{ parcels: Sugg[] }>(`/v1/sites/${siteId}/parcels?q=${encodeURIComponent(t)}&limit=6`);
        if (input.current?.value.trim().toUpperCase() === t) { setSugg(r.parcels); setActive(r.parcels.length ? 0 : -1); }
      } catch { setSugg([]); }
    }, 140);
  }
  function choose(r: Sugg) {
    setQ(""); setSugg([]); setActive(-1); setHit(null);
    input.current?.blur();
    router.push(r.case_id ? `/cases/${r.case_id}` : `/hub?parcel=${encodeURIComponent(r.id)}`);
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(t.tagName) && !t.isContentEditable) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  async function go(e: React.FormEvent) {
    e.preventDefault();
    if (sugg.length && active >= 0) return choose(sugg[active]);
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
      <span className="tb-find-box">
        <svg className="tb-find-icon" viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="m12.6 12.6 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input id="find" ref={input} type="search" placeholder="Find a parcel by tracking number" value={q} autoComplete="off" spellCheck={false}
          role="combobox" aria-expanded={sugg.length > 0} aria-controls="find-sugg" aria-autocomplete="list"
          aria-activedescendant={active >= 0 && sugg[active] ? `find-opt-${sugg[active].id}` : undefined}
          onChange={(e) => { setQ(e.target.value); setHit(null); suggest(e.target.value); }}
          onKeyDown={(e) => {
            if (!sugg.length) return;
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (a + 1) % sugg.length); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (a - 1 + sugg.length) % sugg.length); }
            if (e.key === "Escape") { setSugg([]); setActive(-1); }
          }}
          onBlur={() => window.setTimeout(() => setSugg([]), 120)} />
        <kbd className="tb-kbd" aria-hidden="true">/</kbd>
      </span>
      {sugg.length > 0 && !hit && (
        <ul className="tb-sugg" id="find-sugg" role="listbox" aria-label="Parcels scanned today">
          {sugg.map((r, i) => {
            const n = r.last ? stageOf(r.last.point) : 0, v = q.trim().toUpperCase(), at = r.id.toUpperCase().indexOf(v);
            return (
              <li key={r.id} id={`find-opt-${r.id}`} role="option" aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); choose(r); }} onMouseEnter={() => setActive(i)}>
                <span className="tb-sugg-id">{at >= 0 ? <>{r.id.slice(0, at)}<mark>{r.id.slice(at, at + v.length)}</mark>{r.id.slice(at + v.length)}</> : r.id}</span>
                <span className="tb-sugg-meta">{n ? `${n} · ${STAGES[n - 1].label}` : "No scans"}{r.last ? ` · ${hhmm(r.last.t)}` : ""}</span>
                {r.case_id && <i className="tb-sugg-case">In a case</i>}
              </li>
            );
          })}
        </ul>
      )}
      {hit && (
        <div className="tb-hit" role="status">
          {hit === "none" ? "This tracking number has no scans at this hub." : (
            <>{hit.scans} scans of <b>{hit.waybill}</b>. No case yet.
              <button type="button" className="tb-hit-btn" disabled={busy} onClick={() => open(hit.waybill)}>{busy ? "Opening" : "Investigate"}</button></>
          )}
        </div>
      )}
    </form>
  );
}

/** The account, at the foot of the sidebar: the one demo user, Settings and the model status (the menu opens upward). */
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
  const offline = !!me.error;
  const keyed = !!(caps?.sam || caps?.spark);
  return (
    <div className="tb-account sb-account" ref={box}>
      <button type="button" className="tb-me" aria-label="Account menu" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="tb-avatar" aria-hidden="true">SV</span>
        <span className="tb-me-text">
          <span className="tb-me-name">Hub supervisor</span>
          <span className="tb-me-role"><span className="tb-menu-dot" data-on={!offline && keyed ? "" : undefined} />{offline ? "Backend offline" : keyed ? "Models on" : "Models off"}</span>
        </span>
        <svg className="tb-chev" viewBox="0 0 12 12" aria-hidden="true"><path d="m3 7.5 3-3 3 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {open && (
        <div className="tb-menu" role="menu" aria-label="Account">
          <p className="tb-menu-head">Hub supervisor</p>
          <p className="tb-menu-sub">{offline ? "Backend offline" : "Can open cases, send staff and close them"}</p>
          <Link href="/operator" className="tb-menu-row" role="menuitem" onClick={() => setOpen(false)}>Settings &amp; data</Link>
          {caps && (
            <p className="tb-menu-note">
              <span className="tb-menu-dot" data-on={keyed ? "" : undefined} aria-hidden="true" />
              {keyed ? "Model keys connected" : "No model keys: model steps are off"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export async function postJson<T>(path: string, json?: unknown) {
  return api<T>(path, { method: "POST", json });
}
