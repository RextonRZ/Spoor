// Converts the Playwright recording (webm) to H.264 MP4 <= 1280 px wide, <= 60 s, into review_pack/.
import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const dir = "test-results";
const webms = [];
const walk = (d) => readdirSync(d).forEach((f) => {
  const p = join(d, f);
  if (statSync(p).isDirectory()) walk(p); else if (p.endsWith(".webm") && p.includes("recording")) webms.push(p);
});
walk(dir);
if (!webms.length) { console.error("no recording found; run: npx playwright test --config playwright.review.config.ts --project recording"); process.exit(1); }
const src = webms.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs)[0];
const out = "review_pack/signature_interaction.mp4";
const r = spawnSync("ffmpeg", ["-v", "error", "-y", "-i", src, "-t", "60", "-vf", "scale='min(1280,iw)':-2,fps=25",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", out], { stdio: "inherit" });
if (r.status !== 0) process.exit(r.status ?? 1);
console.log("wrote", out, `${(statSync(out).size / 1e6).toFixed(1)} MB from`, src);
