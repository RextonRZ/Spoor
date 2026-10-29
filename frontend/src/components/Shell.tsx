"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { setSiteToRenderer } from "@/lib/frames";
import type { Capabilities, Me, Role } from "@/lib/types";
import { Icon } from "./ui";

const ROLE_LABEL: Record<Role, string> = { investigator: "Investigator", reviewer: "Reviewer", site_admin: "Site admin" };

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const caseId = /^\/cases\/([^/]+)/.exec(path)?.[1];
  const inWorkspace = !!caseId && !path.endsWith("/graph") && !path.endsWith("/report");
  const [rail, setRail] = useState<"open" | "collapsed" | null>(null);
  const [menu, setMenu] = useState(false);
  const me = useResource<Me>("/v1/me");
  const caps = useResource<Capabilities>("/v1/capabilities");
  const effectiveRail = rail ?? (inWorkspace ? "collapsed" : "open");

  useEffect(() => {
    if (caps.data) setSiteToRenderer(caps.data.site_to_renderer);
  }, [caps.data]);
  const [prevPath, setPrevPath] = useState(path);
  if (path !== prevPath) {
    setPrevPath(path);
    setMenu(false);
  }

  async function switchRole(role: Role) {
    await fetch("/api/session", { method: "POST", body: JSON.stringify({ role }) });
    invalidate("/v1/");
    router.refresh();
  }

  const nav = [
    { href: "/", label: "Cases", icon: Icon.cases, current: path === "/" },
    ...(caseId
      ? [
          { href: `/cases/${caseId}`, label: "Workspace", icon: Icon.scene, current: inWorkspace },
          { href: `/cases/${caseId}/graph`, label: "Evidence graph", icon: Icon.graph, current: path.endsWith("/graph") },
          { href: `/cases/${caseId}/report`, label: "Report", icon: Icon.report, current: path.endsWith("/report") },
        ]
      : []),
  ];
  const noModels = caps.data && !caps.data.sam && !caps.data.spark;

  return (
    <div className="sp-shell" data-rail={effectiveRail} data-menu={menu ? "open" : "closed"}>
      <a className="sp-skip" href="#main">Skip to content</a>
      {menu && <div className="sp-scrim" onClick={() => setMenu(false)} aria-hidden />}
      <aside className="sp-side" aria-label="Main navigation">
        <div className="sp-brand">
          <span className="sp-brand-mark" aria-hidden>S</span>
          <div className="sp-brand-text">
            <div className="sp-brand-name">Spoor</div>
            <div className="sp-brand-site">CONTOH Express hub · fictional</div>
          </div>
        </div>
        <p className="sp-micro sp-navgroup">Investigate</p>
        <nav className="sp-stack" style={{ gap: 2 }}>
          {nav.map((n) => (
            <Link key={n.href} href={n.href} className="sp-nav" aria-current={n.current ? "page" : undefined}
              title={n.label}>
              <n.icon /><span className="sp-nav-label">{n.label}</span>
            </Link>
          ))}
        </nav>
        <p className="sp-micro sp-navgroup">Showcase</p>
        <Link href={caseId ? `/wall?case=${caseId}` : "/wall"} className="sp-nav" aria-current={path.startsWith("/wall") ? "page" : undefined}
          title="Camera wall">
          <Icon.camera /><span className="sp-nav-label">Camera wall</span>
        </Link>
        <Link href="/operator" className="sp-nav" aria-current={path.startsWith("/operator") ? "page" : undefined}
          title="Operator">
          <Icon.operator /><span className="sp-nav-label">Operator</span>
        </Link>
        <div className="sp-side-foot">
          {noModels && (
            <span className="sp-chip sp-chip-warn sp-side-foot-text" style={{ alignSelf: "flex-start" }}
              title="The backend runs without Meta API keys: model steps show 'analysis unavailable'">
              No model keys
            </span>
          )}
          <label className="sp-field sp-side-foot-text">
            <span className="sp-micro">Signed in as</span>
            <select className="sp-select" value={me.data?.role ?? "investigator"} aria-label="Demo role"
              onChange={(e) => switchRole(e.target.value as Role)}>
              {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
            <span className="sp-caption">{me.data ? me.data.user_id : me.error ? "backend offline" : "…"}</span>
          </label>
          <button className="sp-btn sp-btn-ghost sp-iconbtn" aria-label={effectiveRail === "open" ? "Collapse sidebar" : "Expand sidebar"}
            onClick={() => setRail(effectiveRail === "open" ? "collapsed" : "open")} style={{ alignSelf: "flex-start" }}>
            {effectiveRail === "open" ? <Icon.collapse /> : <Icon.expand />}
          </button>
        </div>
      </aside>
      <div className="sp-main">
        <header className="sp-topbar">
          <button className="sp-btn sp-btn-ghost sp-iconbtn" aria-label="Open menu" aria-expanded={menu}
            onClick={() => setMenu(true)}><Icon.menu /></button>
          <span className="sp-brand-name">Spoor</span>
          <span className="sp-muted" style={{ fontSize: 12 }}>CONTOH Express · fictional hub</span>
        </header>
        <main id="main" tabIndex={-1} style={{ outline: "none", minWidth: 0, flex: 1, display: "flex", flexDirection: "column" }}>
          {children}
        </main>
      </div>
    </div>
  );
}

export async function postJson<T>(path: string, json?: unknown) {
  return api<T>(path, { method: "POST", json });
}
