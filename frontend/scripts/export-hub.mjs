// Copies assets/hub/build/hub_dressed.blend to a temp file (the builder rewrites the original) and exports
// frontend/public/hub.glb from the copy, headless. Never writes any .blend. Never stops a running Blender.
import { copyFileSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const blender = process.env.BLENDER || "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe";
const src = join(root, "assets", "hub", "build", "hub_dressed.blend");
const tmp = mkdtempSync(join(tmpdir(), "spoor-hub-"));
const copy = join(tmp, "hub_copy.blend");
copyFileSync(src, copy);
console.log("copied", src, `(${(statSync(copy).size / 1e6).toFixed(1)} MB) ->`, copy);
const r = spawnSync(blender, ["-b", "--factory-startup", copy, "-P", join(root, "frontend", "scripts", "export_hub_glb.py"), "--",
  "--src-dir", join(root, "assets", "hub", "build"), "--spec", join(root, "assets", "hub", "hub_spec.json"),
  "--out", join(root, "frontend", "public", "hub.glb")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
const line = (r.stdout ?? "").split("\n").find((l) => l.startsWith("EXPORT "));
rmSync(tmp, { recursive: true, force: true });
if (r.status !== 0 || !line) {
  console.error(String(r.error ?? ""), r.status, (r.stderr ?? "") + (r.stdout ?? "").slice(-3000));
  process.exit(1);
}
console.log(line);
