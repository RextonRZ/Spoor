"use client";
import dynamic from "next/dynamic";
import { use, useState, useSyncExternalStore, Component, type ReactNode } from "react";
import { WorkspaceProvider, useWorkspace } from "@/components/workspace/context";
import { CaseOverview, TraceControls } from "@/components/workspace/CaseOverview";
import Timeline from "@/components/workspace/Timeline";
import SourcePanel from "@/components/workspace/SourcePanel";
import AgentPanel from "@/components/workspace/AgentPanel";
import FloorPlan2D from "@/components/workspace/FloorPlan2D";
import "@/components/workspace/workspace.css";

const Scene3D = dynamic(() => import("@/components/workspace/Scene3D"), {
  ssr: false,
  loading: () => <div className="sp-scene-note" role="status">Loading 3D scene</div>,
});

type MobileTab = "scene" | "timeline" | "source" | "case" | "agent";

export default function WorkspacePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  return (
    <WorkspaceProvider caseId={caseId}>
      <Workspace />
    </WorkspaceProvider>
  );
}

const noop = () => () => {};
let webglCache: boolean | null = null;
function webglAvailable() {
  if (webglCache !== null) return webglCache;
  webglCache = detectWebgl();
  return webglCache;
}

function detectWebgl() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function Workspace() {
  const { selection, mode, caps } = useWorkspace();
  const [chosenView, setView] = useState<"3d" | "plan" | null>(null);
  const hasWebgl = useSyncExternalStore(noop, webglAvailable, () => null);
  const view = chosenView ?? (hasWebgl === null ? null : hasWebgl ? "3d" : "plan");
  const [rightTab, setRightTab] = useState<"source" | "agent">("source");
  const [tab, setTab] = useState<MobileTab>("scene");
  const [prevSelection, setPrevSelection] = useState(selection);
  if (selection !== prevSelection) {
    // a new selection always opens its source (state adjusted during render, not in an effect)
    setPrevSelection(selection);
    if (selection) {
      setRightTab("source");
      if (typeof window !== "undefined" && window.matchMedia("(max-width: 1100px)").matches) setTab("source");
    }
  }

  const tabs: { k: MobileTab; label: string }[] = [
    { k: "scene", label: "Scene" }, { k: "timeline", label: "Timeline" }, { k: "source", label: "Source" },
    { k: "case", label: "Case" }, { k: "agent", label: "Agent" },
  ];
  return (
    <div className="sp-ws" data-tab={tab}>
      <nav className="sp-ws-tabs sp-seg" aria-label="Workspace sections">
        {tabs.map((t) => (
          <button key={t.k} aria-pressed={tab === t.k}
            onClick={() => { setTab(t.k); if (t.k === "source" || t.k === "agent") setRightTab(t.k); }}>{t.label}</button>
        ))}
      </nav>
      <aside className="sp-ws-left sp-panel" data-pane="case" aria-label="Case overview">
        <div className="sp-panel-body sp-stack" style={{ gap: 20 }}>
          <CaseOverview />
          <hr className="sp-divider" />
          <TraceControls />
        </div>
      </aside>
      <section className="sp-ws-scene sp-panel" data-pane="scene" aria-label="Hub scene">
        <div className="sp-panel-head">
          <span className="sp-micro">{view === "plan" ? "Floor plan" : "3D scene"} · synthetic hub</span>
          <div className="sp-seg" role="group" aria-label="Scene view">
            <button aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D</button>
            <button aria-pressed={view === "plan"} onClick={() => setView("plan")}>2D plan</button>
          </div>
        </div>
        <div className="sp-scene-wrap">
          {view === "3d" && (
            <SceneBoundary fallback={<><FloorPlan2D /><div className="sp-scene-note">3D failed to start; showing the 2D plan.</div></>}>
              <Scene3D />
            </SceneBoundary>
          )}
          {view === "plan" && <FloorPlan2D />}
          {mode !== "object" && !caps.data?.sam && (
            <div className="sp-scene-note" role="status" style={{ bottom: 48 }}>
              No anonymous person tracks: person segmentation needs SAM (no API key).{mode === "all" ? " Showing the parcel only." : ""}
            </div>
          )}
        </div>
      </section>
      <section className="sp-ws-right sp-panel" data-pane="source agent" aria-label="Source and agent" id="source-panel">
        <div className="sp-panel-head">
          <div className="sp-seg" role="tablist" aria-label="Right panel">
            <button role="tab" aria-selected={rightTab === "source"} onClick={() => { setRightTab("source"); setTab("source"); }}>Source</button>
            <button role="tab" aria-selected={rightTab === "agent"} onClick={() => { setRightTab("agent"); setTab("agent"); }}>Agent</button>
          </div>
        </div>
        <div className="sp-panel-body" data-right={rightTab}>
          <div className="sp-ws-source" hidden={rightTab !== "source"}><SourcePanel /></div>
          <div className="sp-ws-agent" hidden={rightTab !== "agent"}><AgentPanel /></div>
        </div>
      </section>
      <section className="sp-ws-time sp-panel" data-pane="timeline" aria-label="Timeline">
        <Timeline />
      </section>
    </div>
  );
}
