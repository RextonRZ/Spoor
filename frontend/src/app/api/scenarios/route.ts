/**
 * Scenario index for the camera wall (review 007 #1). Server-only. Reads exactly two kinds of file:
 *   ml/evaluation/scenarios/manifest.json   (or SPOOR_SCENARIO_MANIFEST)
 *   ml/evaluation/scenarios/<S>/case_input.json
 * and stats/hashes the CAM_XX.mp4 renders in each scenario's clips folder. It never lists directories and never opens
 * any other file: scenario cards and the evaluator's reference data are out of reach by construction.
 * `?scenario=S2` adds the SHA-256 of that scenario's renders, so the wall can play the backend media with the same bytes.
 */
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import type { NextRequest } from "next/server";
import { CAMERA_ID, parseCaseInput, parseManifest, SCENARIO_ID, type ScenarioIndex, type WallClip } from "@/lib/scenarios";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const REPO = path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
const MANIFEST = path.resolve(/*turbopackIgnore: true*/ process.env.SPOOR_SCENARIO_MANIFEST ?? path.join(REPO, "ml", "evaluation", "scenarios", "manifest.json"));
const ALL_CAMERAS = Array.from({ length: 18 }, (_, i) => `CAM_${String(i + 1).padStart(2, "0")}`);
const shaCache = new Map<string, { size: number; mtimeMs: number; sha: string }>();

const rel = (p: string) => path.relative(REPO, p).split(path.sep).join("/");
const inside = (p: string, root: string) => {
  const r = path.relative(root, p);
  return !!r && !r.startsWith("..") && !path.isAbsolute(r);
};

async function readJson(p: string): Promise<unknown | null> {
  try {
    return JSON.parse(await readFile(p, "utf8"));
  } catch {
    return null;
  }
}

async function sha256(file: string, size: number, mtimeMs: number): Promise<string> {
  const hit = shaCache.get(file);
  if (hit && hit.size === size && hit.mtimeMs === mtimeMs) return hit.sha;
  const h = createHash("sha256");
  await new Promise<void>((resolve, reject) => {
    createReadStream(file).on("data", (b) => h.update(b)).on("end", () => resolve()).on("error", reject);
  });
  const sha = h.digest("hex");
  shaCache.set(file, { size, mtimeMs, sha });
  return sha;
}

export async function GET(req: NextRequest) {
  const want = req.nextUrl.searchParams.get("scenario");
  const index: ScenarioIndex = { manifest: rel(MANIFEST), found: false, scenarios: [] };
  const raw = await readJson(MANIFEST);
  if (raw === null) return Response.json(index);
  index.found = true;
  const base = path.dirname(MANIFEST);
  for (const item of parseManifest(raw)) {
    const input = parseCaseInput(await readJson(path.join(base, item.scenario, "case_input.json")));
    const dir = path.resolve(/*turbopackIgnore: true*/ base, item.clips);
    const safe = inside(dir, REPO);
    const cams = input?.cameras.length ? input.cameras : ALL_CAMERAS;
    const clipFiles: WallClip[] = [];
    for (const cam of cams) {
      if (!CAMERA_ID.test(cam)) continue;
      const file = path.join(dir, `${cam}.mp4`);
      let st: Awaited<ReturnType<typeof stat>> | null = null;
      if (safe) st = await stat(file).catch(() => null);
      const exists = !!st?.isFile() && st.size > 0;
      // without case_input.json, only cameras that actually have a render are listed
      if (!exists && !input?.cameras.length) continue;
      clipFiles.push({ camera: cam, file: rel(file), exists, bytes: exists ? Number(st!.size) : null,
        sha256: exists && want === item.scenario ? await sha256(file, Number(st!.size), Number(st!.mtimeMs)) : null });
    }
    index.scenarios.push({ ...item, input, clips_dir: safe ? rel(dir) : "(outside the repository: not read)",
      rendered: clipFiles.filter((c) => c.exists).length, clip_files: clipFiles });
  }
  if (want && !SCENARIO_ID.test(want)) index.error = "unknown scenario id";
  return Response.json(index, { headers: { "cache-control": "no-store" } });
}
