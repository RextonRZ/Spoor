/**
 * Scenario inputs for the camera wall (review 007 #1, QUEUE F1). The builder writes ONE manifest,
 * ml/evaluation/scenarios/manifest.json, plus <S>/case_input.json per scenario (question, waybill, complaint, cameras,
 * clips). Those two files are the only scenario files the app reads; the per-scenario card and everything the
 * evaluator scores against stay evaluator-only. Pure helpers here (no fs) so they can be unit-tested.
 */

export const SCENARIO_ID = /^S\d{1,2}$/;
export const CAMERA_ID = /^CAM_\d{2}$/;

/** One manifest entry, inputs only (paths relative to the manifest's folder). */
export interface ManifestItem {
  scenario: string;
  title: string;
  parcel: string | null;
  subject_kind: "parcel" | "container";
  clips: string;
  clip_start: string | null;
}

/** The fields of <S>/case_input.json the app uses: what an investigator is asked and given, never an answer. */
export interface CaseInput {
  question: string | null;
  waybill: string | null;
  complaint: string | null;
  cameras: string[];
  subject_id: string | null;
  subject_kind: "parcel" | "container";
  synthetic: boolean;
}

export interface WallClip {
  camera: string;
  /** repo-relative path, for display */
  file: string;
  exists: boolean;
  bytes: number | null;
  /** SHA-256 of the render file; the wall plays the backend media with the same hash (same bytes, same evidence) */
  sha256: string | null;
}

export interface WallScenario extends ManifestItem {
  input: CaseInput | null;
  clips_dir: string;
  rendered: number;
  clip_files: WallClip[];
}

export interface ScenarioIndex {
  manifest: string;
  found: boolean;
  error?: string;
  scenarios: WallScenario[];
}

const str = (v: unknown): string | null => (typeof v === "string" && v.length > 0 ? v : null);

export function parseManifest(raw: unknown): ManifestItem[] {
  if (!Array.isArray(raw)) return [];
  const out: ManifestItem[] = [];
  for (const r of raw) {
    if (!r || typeof r !== "object") continue;
    const o = r as Record<string, unknown>;
    const id = str(o.scenario);
    const clips = str(o.clips);
    if (!id || !SCENARIO_ID.test(id) || !clips) continue;
    out.push({ scenario: id, title: str(o.title) ?? id, parcel: str(o.parcel),
      subject_kind: o.subject_kind === "container" ? "container" : "parcel", clips, clip_start: str(o.clip_start) });
  }
  return out;
}

export function parseCaseInput(raw: unknown): CaseInput | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const cams = Array.isArray(o.cameras) ? o.cameras.filter((c): c is string => typeof c === "string" && CAMERA_ID.test(c)) : [];
  return { question: str(o.question), waybill: str(o.waybill), complaint: str(o.complaint), cameras: cams,
    subject_id: str(o.subject_id), subject_kind: o.subject_kind === "container" ? "container" : "parcel",
    synthetic: o.synthetic !== false };
}

export type TileState = "not_rendered" | "not_imported" | "ready";

export function tileState(clip: Pick<WallClip, "exists" | "sha256">, mediaId: string | undefined): TileState {
  if (!clip.exists) return "not_rendered";
  return mediaId ? "ready" : "not_imported";
}
