/** Shapes of the backend read models (backend/src/spoor/api/app.py). Records come from the generated contracts. */
import type { Camera, Case, ClockDomain, Hypothesis, MediaAsset, Site, VerifiedFinding } from "@/contracts/generated";

export type { Camera, Case, Hypothesis, MediaAsset, Site, VerifiedFinding };

export type Role = "investigator" | "reviewer" | "site_admin";

export interface Capabilities {
  sam: boolean;
  spark: boolean;
  agents: boolean;
  agent_backend: string;
  multiview_xyz: boolean;
  cross_camera_association: boolean;
  site_frame: string;
  site_to_renderer: number[][];
}

export interface Me {
  user_id: string;
  role: Role;
  site_ids: string[];
}

export interface SyncView {
  sync_id: string;
  offset_ms: number;
  drift_ppm: number;
  uncertainty_ms: number;
  method: string;
  anchor_count: number;
  residual_ms_p95: number | null;
  created_at: string;
}

export interface CoverageView {
  coverage_id?: string;
  media_id?: string;
  start_utc: string;
  end_utc: string;
  sync_id: string;
  time_uncertainty_ms: number;
}

export interface CameraRow {
  camera: Camera;
  clock_sync: SyncView | null;
  calibration: null | {
    calibration_id: string;
    rig_state: string;
    version: number;
    holdout_error_median_m: number | null;
    holdout_error_p95_m: number | null;
    invalidated: boolean;
  };
  coverage: CoverageView[];
}

export interface MediaRow {
  media: MediaAsset;
  recording_kind: string;
  purged: boolean;
  coverage: CoverageView[];
}

export interface ClockDomainRow {
  domain: ClockDomain;
  sync: SyncView | null;
}

export interface ScanRow {
  scan_event_id: string;
  time: string;
  synced: boolean;
  time_uncertainty_ms: number | null;
  event_kind: string;
  read_outcome: string;
  identity_keys: string[];
  device_id: string;
  device_kind: string;
  station_id: string | null;
  zone_id: string | null;
  sort_destination_actual: string | null;
  source_type: string;
  import_batch: string;
  raw_code?: string | null;
  raw_description?: string | null;
}

export interface CaseListRow {
  case: Case;
  revision_at: string | null;
  report_status: "draft" | "approved" | null;
}

export interface VisibilitySpan {
  state: string;
  start_ms: number;
  end_ms: number;
  zone_id: string | null;
  camera_ids: string[];
  track_ids: string[];
  observation_ids: string[];
}

export interface HistoryEntry {
  from_status: string;
  to_status: string;
  reason: string;
  at: string;
  actor: { kind: string; id: string };
  evidence_ids: string[];
}

export interface CaseState {
  case: Case;
  revision: { case_revision_id: string; at: string; reason: string } | null;
  objects: {
    object: { object_instance_id: string; label: string; identifiers?: { scheme: string; value: string }[] };
    timeline: VisibilitySpan[];
    tracks: Record<string, string>;
  }[];
  findings: (VerifiedFinding & { invalidated: boolean })[];
  hypotheses: (Hypothesis & { history: HistoryEntry[] })[];
  evidence_requests: {
    evidence_request_id: string;
    camera_id: string | null;
    start_utc: string | null;
    end_utc: string | null;
    reason: string;
    hypothesis_ids: string[];
    at: string;
  }[];
}

export interface Sighting {
  class: "fixed_scan" | "handheld_scan" | "video" | "candidate_video" | "inherited_container";
  time: string;
  label: string;
  evidence_id: string;
  where: string;
  time_uncertainty_ms: number | null;
}

export interface LastSeenRow {
  object_instance_id: string;
  label: string;
  last_confident: Sighting | null;
  confident: Sighting[];
  leads: Sighting[];
}

export interface ReplayPoint {
  t: string;
  observation_id: string;
  spatial_mode: string;
  floor_xy_m: [number, number] | null;
  zone_id: string | null;
  uncertainty_radius_m: number | null;
  renderer_xyz_y_up: [number, number, number] | null;
}

export interface ReplaySegment {
  kind: "observed";
  style: "solid";
  camera_id: string;
  track_id: string;
  start: string;
  end: string;
  points: ReplayPoint[];
}

export interface ReplayLink {
  kind: "hypothesized";
  style: "dashed";
  from: string;
  to: string;
  start: string;
  end: string;
}

export interface ReplayGap {
  kind: "unknown";
  style: "grey";
  start: string;
  end: string;
  reason: string;
  covering_camera_ids: string[];
}

export interface ReplayObject {
  object_instance_id: string;
  label: string;
  segments: ReplaySegment[];
  links: ReplayLink[];
  gaps: ReplayGap[];
}

export interface Replay {
  case_id: string;
  contract: string;
  objects: ReplayObject[];
}

export interface ParcelScan {
  scan_event_id: string;
  site_id: string;
  event_kind: string;
  time: string;
  synced: boolean;
  time_uncertainty_ms: number | null;
  device_id: string;
  device_kind: string;
  station_id: string | null;
  zone_id: string | null;
  late_upload: boolean;
  source_type: string;
  read_outcome?: string;
  raw_code?: string | null;
  raw_description?: string | null;
  sort_destination_actual?: string | null;
}

export interface ParcelLookup {
  identifier: { scheme: string; value: string };
  aliases: string[];
  visit: { status: string; label: string; closed_by: string | null; opened_at: string | null; notes: string[] };
  scans: ParcelScan[];
  container_chain: { container: string; since: string; until: string | null; basis: string; label: string }[];
  excluded: { corrected: string[]; duplicates: string[] };
}

export interface EvidenceView {
  observation: {
    observation_id: string;
    source_type: string;
    camera_id: string | null;
    label: string;
    source_frame: {
      media_id: string;
      frame_index: number;
      pts_ms: number;
      normalized_utc?: string | null;
      time_uncertainty_ms?: number | null;
    } | null;
    bbox_xyxy_px: [number, number, number, number] | null;
    quality_flags: string[];
    provenance: { model: string; model_version: string; provider: string } | null;
    confidence_raw: number | null;
    confidence_calibrated: number | null;
  };
  invalidated: boolean;
  estimate: {
    spatial_mode: string;
    floor_xy_m: [number, number] | null;
    uncertainty_radius_m: number | null;
    zone_id: string | null;
    method: string;
  } | null;
  media: { media_id: string; sha256: string; kind: string; flags: string[] };
  frame_url: string;
  annotated_frame_url: string;
  asset_label: string;
}

export interface FrameAt {
  media_id: string;
  camera_id: string;
  frame_index: number;
  pts_ms: number;
  delta_ms: number;
  time_uncertainty_ms: number;
  frame_count: number;
  frame_url: string;
  label: string;
}

export interface JobEvent {
  at: string;
  message: string;
  [k: string]: unknown;
}

export interface InvestigationResult {
  status: "answered" | "abstained";
  answer: string;
  revision_id: string | null;
  findings: string[];
  hypotheses: { id: string; claim: string; status: string; reasons: string[] }[];
  evidence_requests: string[];
  rejected: unknown[];
  agent_runs: Record<string, unknown>;
}

export interface JobStatus {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "done" | "failed";
  events: JobEvent[];
  result: InvestigationResult | null;
  error: string | null;
}

export interface CaseDiff {
  from_revision: string | null;
  to_revision: string;
  new_findings: { finding_id: string; statement: string; observation_ids: string[]; invalidated: boolean }[];
  invalidated_findings: string[];
  status_changes: { hypothesis_id: string; claim: string; from: string; to: string }[];
  new_hypotheses: { hypothesis_id: string; claim: string }[];
  new_evidence_requests: { reason: string; camera_id: string | null }[];
  last_seen_changed: { object: string; before: string | null; after: string }[];
}

export interface ReportRow {
  report_id: string;
  status: "draft" | "approved";
  sha256: string;
  approved_by: string | null;
  case_revision_id: string | null;
  at: string;
}

export interface OperatorTrace {
  models: Record<
    string,
    { calls: number; cache_hits: number; input_tokens: number; output_tokens: number; billed_frames: number;
      errors: number }
  >;
  calls: Record<string, unknown>[];
  agent_steps: {
    request_id: string;
    seq: number;
    role: string;
    kind: string;
    content: Record<string, unknown>;
    at: string;
  }[];
}
