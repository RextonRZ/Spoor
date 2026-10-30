"use client";
import dynamic from "next/dynamic";
import { use, useEffect, useRef, useState, useSyncExternalStore, Component, type ReactNode } from "react";
import { WorkspaceProvider, useWorkspace } from "@/components/workspace/context";
import { CaseOverview, TraceControls } from "@/components/workspace/CaseOverview";
import Timeline from "@/components/workspace/Timeline";
import SourcePanel from "@/components/workspace/SourcePanel";
import AgentPanel from "@/components/workspace/AgentPanel";
import MissingMoment from "@/components/workspace/MissingMoment";
import FollowCam from "@/components/workspace/FollowCam";
import CameraStrip from "@/components/workspace/CameraStrip";
import HubPlan from "@/components/plan/HubPlan";
import { camId } from "@/lib/hub";
import { markerAt, clock } from "@/lib/journey";
import "@/components/workspace/workspace.css";

const Scene3D = dynamic(() => import("@/components/workspace/Scene3D"), {
  ssr: false,
  loading: () => <div className="sp-scene-note" role="status">Loading 3D scene</div>,
});

type MobileTab = "scene" | "timeline" | "source" | "moment" | "case" | "agent";

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
  // The 2D journey is the primary view (journey_view_0030 pass 2): any hub has a plan; 3D is optional.
  const view = chosenView ?? (hasWebgl === null ? null : "plan");
  const [rightTab, setRightTab] = useState<"source" | "moment" | "agent">("source");
  const rightTabRef = useRef(rightTab);
  useEffect(() => { rightTabRef.current = rightTab; }, [rightTab]);
  const [tab, setTab] = useState<MobileTab>("scene");
  const { journey, missing, select } = useWorkspace();
  const autoOpened = useRef(false);
  const firstCam = missing.data?.objects[0]?.last_confirmed?.frames?.[0]?.camera_id;
  const lcT = journey.data?.objects[0]?.last_confirmed?.t;
  useEffect(() => {
    // the hero opens on the camera frame at the last confirmed moment instead of "Nothing selected" (§2.2)
    if (autoOpened.current || selection || !firstCam || !lcT) return;
    autoOpened.current = true;
    if (rightTabRef.current !== "source") return; // the user moved on (e.g. to Agent): never pull them back
    select({ kind: "camera", cameraId: firstCam, time: Date.parse(lcT) });
  }, [firstCam, lcT, selection, select]);
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
    { k: "moment", label: "Moment" }, { k: "case", label: "Case" }, { k: "agent", label: "Agent" },
  ];
  return (
    <div className="sp-ws" data-tab={tab}>
      <nav className="sp-ws-tabs sp-seg" aria-label="Workspace sections">
        {tabs.map((t) => (
          <button key={t.k} aria-pressed={tab === t.k}
            onClick={() => { setTab(t.k); if (t.k === "source" || t.k === "agent" || t.k === "moment") setRightTab(t.k); }}>{t.label}</button>
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
            <button aria-pressed={view === "plan"} onClick={() => setView("plan")}>2D journey</button>
            <button aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D</button>
          </div>
        </div>
        <div className="sp-scene-wrap">
          {view === "3d" && (
            <SceneBoundary fallback={<><WorkspacePlan /><div className="sp-scene-note">3D failed to start; showing the 2D plan.</div></>}>
              <Scene3D />
            </SceneBoundary>
          )}
          {view === "plan" && <WorkspacePlan />}
          <ReplayStatus />
          {mode !== "object" && !caps.data?.sam && (
            <div className="sp-scene-note" role="status" style={{ bottom: 48 }}>
              No anonymous person tracks: person segmentation needs SAM (no API key).{mode === "all" ? " Showing the parcel only." : ""}
            </div>
          )}
        </div>
      </section>
      <section className="sp-ws-right sp-panel" data-pane="source moment agent" aria-label="Source and agent" id="source-panel">
        <div className="sp-panel-head">
          <div className="sp-seg" role="tablist" aria-label="Right panel">
            <button role="tab" aria-selected={rightTab === "source"} onClick={() => { setRightTab("source"); setTab("source"); }}>Source</button>
            <button role="tab" aria-selected={rightTab === "moment"} data-testid="tab-moment"
              onClick={() => { setRightTab("moment"); setTab("moment"); }}>Missing moment</button>
            <button role="tab" aria-selected={rightTab === "agent"} onClick={() => { setRightTab("agent"); setTab("agent"); }}>Agent</button>
          </div>
        </div>
        <div className="sp-panel-body" data-right={rightTab}>
          <div className="sp-ws-source" hidden={rightTab !== "source"}><FollowCam /><SourcePanel /></div>
          <div className="sp-ws-moment" hidden={rightTab !== "moment"}><MissingMoment /></div>
          <div className="sp-ws-agent" hidden={rightTab !== "agent"}><AgentPanel /></div>
        </div>
      </section>
      <div className="sp-ws-strip" data-pane="strip"><CameraStrip /></div>
      <section className="sp-ws-time sp-panel" data-pane="timeline" aria-label="Timeline">
        <Timeline />
      </section>
    </div>
  );
}

/** What the replay marker rests on at the playhead, in words (live region, so it is announced while playing). */
function ReplayStatus() {
  const { journey, playhead } = useWorkspace();
  const j = journey.data?.objects[0];
  if (!j || playhead === null) return null;
  const m = markerAt(j, playhead);
  const tone = m.kind === "observed" ? "observed" : m.kind === "inferred" ? "inferred" : m.kind === "scan" ? "scan" : "unknown";
  return (
    <div className="sp-replay-status" data-tone={tone} role="status" aria-live="polite" data-testid="replay-status">
      <span className="sp-replay-dot" aria-hidden />
      {m.kind === "unknown" && m.since ? `Unknown since ${clock(m.since, true)}: no scan and no sighting after it` : m.label}
    </div>
  );
}

/** The 2D journey (H2) in the architectural plan language: backend-typed journey + missing moment + replay marker. */
function WorkspacePlan() {
  const { journey, missing, playhead, select, selection, litCameras, mode } = useWorkspace();
  const j = journey.data?.objects[0];
  const mm = missing.data?.objects[0];
  const inPlay = [...new Set([...litCameras, ...(mm?.expected_next ?? []).filter((r) => r.result !== "no_footage").map((r) => camId.toHub(r.camera_id))])];
  return (
    <div className="sp-plan2">
      <HubPlan label={`Hub floor plan with the journey of ${j?.label ?? "the parcel"}`} journey={mode !== "people" ? j : undefined}
        missing={mm} marker={j && playhead !== null ? markerAt(j, playhead) : null} litCameras={inPlay}
        selectedScanId={selection?.kind === "scan" ? selection.scanId : null}
        onScan={(id) => select({ kind: "scan", scanId: id })} onObservation={(id) => select({ kind: "observation", observationId: id })} />
    </div>
  );
}
