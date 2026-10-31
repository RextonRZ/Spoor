"use client";
/**
 * App shell, on Reelism's workspace sidebar (Rexton 08:50: "make the sidebar like Reelism", fewer noisy words): a
 * floating panel with the logo alone, plain rows (no group eyebrows), the open case as one context row with its steps
 * named by the user's question, and a foot with Settings (admin), Collapse and the account. The demo role switch and
 * the model-key status live in the account menu, not on screen. "Synthetic demo hub" is said once, under the account.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { setSiteToRenderer } from "@/lib/frames";
import type { Capabilities, CaseState, Me, Role } from "@/lib/types";
import { Icon } from "./ui";

const ROLE_LABEL: Record<Role, string> = { investigator: "Investigator", reviewer: "Reviewer", site_admin: "Site admin" };

interface Row { href: string; label: string; icon: () => ReactNode; current: boolean }

function NavRow({ r }: { r: Row }) {
  return (
    <li>
      <Link href={r.href} className="rl-item" aria-current={r.current ? "page" : undefined} title={r.label}>
        <span className="rl-icon"><r.icon /></span><span className="rl-label">{r.label}</span>
      </Link>
    </li>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const caseId = /^\/cases\/([^/]+)/.exec(path)?.[1];
  const inWorkspace = !!caseId && /^\/cases\/[^/]+\/?$/.test(path);
  const [rail, setRail] = useState<"open" | "collapsed" | null>(null);
  const [menu, setMenu] = useState(false);
  const me = useResource<Me>("/v1/me");
  const caps = useResource<Capabilities>("/v1/capabilities");
  const state = useResource<CaseState>(caseId ? `/v1/cases/${caseId}/state` : null);
  const effectiveRail = rail ?? (inWorkspace ? "collapsed" : "open");
  const admin = me.data?.role === "site_admin";

  useEffect(() => {
    if (caps.data) setSiteToRenderer(caps.data.site_to_renderer);
  }, [caps.data]);
  const [prevPath, setPrevPath] = useState(path);
  if (path !== prevPath) {
    setPrevPath(path);
    setMenu(false);
  }

  const main: Row[] = [
    { href: "/hub", label: "Hub", icon: Icon.scan, current: path.startsWith("/hub") },
    { href: "/", label: "Cases", icon: Icon.cases, current: path === "/" },
    { href: caseId ? `/wall?case=${caseId}` : "/wall", label: "Cameras", icon: Icon.camera, current: path.startsWith("/wall") },
  ];
  const steps: Row[] = caseId ? [
    { href: `/cases/${caseId}/summary`, label: "Answer", icon: Icon.report, current: path.endsWith("/summary") },
    { href: `/cases/${caseId}`, label: "Proof", icon: Icon.scene, current: inWorkspace },
    { href: `/cases/${caseId}/search`, label: "Where to look", icon: Icon.search, current: path.endsWith("/search") },
    { href: `/cases/${caseId}/report`, label: "Report", icon: Icon.doc, current: path.endsWith("/report") || path.endsWith("/graph") },
  ] : [];
  const waybill = state.data?.objects[0]?.object.identifiers?.[0]?.value ?? state.data?.objects[0]?.object.label;

  return (
    <div className="sp-shell" data-rail={effectiveRail} data-menu={menu ? "open" : "closed"}>
      <a className="sp-skip" href="#main">Skip to content</a>
      {menu && <div className="sp-scrim" onClick={() => setMenu(false)} aria-hidden />}
      <aside className="sp-side rl" aria-label="Main navigation">
        <div className="rl-panel">
          <Link href="/hub" className="rl-brand" aria-label="Spoor home">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="rl-logo-full" src="/brand/spoor-logo-dark.svg" alt="" height={26} />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="rl-logo-mark" src="/brand/spoor-mark-dark.svg" alt="" width={28} height={28} />
          </Link>
          <nav className="rl-nav" aria-label="Spoor">
            <ul>{main.map((r) => <NavRow key={r.href} r={r} />)}</ul>
            {caseId && (
              <>
                <div className="rl-group" id="rl-case" title={waybill ? `Parcel ${waybill}` : "This case"}>
                  <span className="rl-avatar" aria-hidden><Icon.parcel /></span>
                  <span className="rl-group-name sp-num">{waybill ?? "This case"}</span>
                </div>
                <ul aria-labelledby="rl-case">{steps.map((r) => <NavRow key={r.href} r={r} />)}</ul>
              </>
            )}
          </nav>
          <div className="rl-foot">
            {admin && (
              <ul>
                <NavRow r={{ href: "/operator", label: "Settings & data", icon: Icon.operator, current: path.startsWith("/operator") }} />
              </ul>
            )}
            <button type="button" className="rl-item rl-toggle" onClick={() => setRail(effectiveRail === "open" ? "collapsed" : "open")}
              aria-expanded={effectiveRail === "open"} title={effectiveRail === "open" ? "Collapse" : "Expand"}>
              <span className="rl-icon">{effectiveRail === "open" ? <Icon.collapse /> : <Icon.expand />}</span>
              <span className="rl-label">{effectiveRail === "open" ? "Collapse" : "Expand"}</span>
            </button>
            <Account me={me.data} offline={!!me.error} caps={caps.data} />
          </div>
        </div>
      </aside>
      <div className="sp-main">
        <header className="sp-topbar">
          <button className="sp-btn sp-btn-ghost sp-iconbtn" aria-label="Open menu" aria-expanded={menu}
            onClick={() => setMenu(true)}><Icon.menu /></button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/spoor-logo-dark.svg" alt="Spoor" height={20} />
        </header>
        <main id="main" tabIndex={-1} style={{ outline: "none", minWidth: 0, flex: 1, display: "flex", flexDirection: "column" }}>
          {children}
        </main>
      </div>
    </div>
  );
}

/** The account (Reelism's ws-user): avatar, role, one quiet line. Its menu holds the demo role switch and the model status. */
function Account({ me, offline, caps }: { me: Me | undefined; offline: boolean; caps: Capabilities | undefined }) {
  const router = useRouter();
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
  async function switchRole(role: Role) {
    await fetch("/api/session", { method: "POST", body: JSON.stringify({ role }) });
    setOpen(false);
    invalidate("/v1/");
    router.refresh();
  }
  const role = me?.role ?? "investigator";
  const models = caps ? (caps.sam || caps.spark ? "Model keys connected" : "No model keys: analysis steps are off") : null;
  return (
    <div className="rl-account" ref={box}>
      {open && (
        <div className="rl-menu" role="menu" aria-label="Account">
          <p className="rl-menu-head">View the demo as</p>
          {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
            <button key={r} type="button" role="menuitemradio" aria-checked={r === role} className="rl-menu-row" onClick={() => switchRole(r)}>
              {ROLE_LABEL[r]}{r === role && <span className="rl-check" aria-hidden><Icon.check /></span>}
            </button>
          ))}
          {models && <p className="rl-menu-note">{models}</p>}
        </div>
      )}
      <button type="button" className="rl-user" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}
        title={ROLE_LABEL[role]}>
        <span className="rl-user-avatar" aria-hidden>{ROLE_LABEL[role].split(" ").map((w) => w[0].toUpperCase()).join("").slice(0, 2)}</span>
        <span className="rl-user-text">
          <b>{offline ? "Backend offline" : ROLE_LABEL[role]}</b>
          <small>Synthetic demo hub</small>
        </span>
        <span className="rl-user-chev" aria-hidden><Icon.expand /></span>
      </button>
    </div>
  );
}

export async function postJson<T>(path: string, json?: unknown) {
  return api<T>(path, { method: "POST", json });
}
