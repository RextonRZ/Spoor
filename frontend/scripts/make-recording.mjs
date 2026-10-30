// Converts the Playwright recording (webm) to H.264 MP4 <= 1280 px wide, <= 60 s, into review_pack/.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

// node scripts/make-recording.mjs [spec-dir-filter] [out.mp4]: defaults = the signature interaction recording.
const [filter = "recording.spec", outArg] = process.argv.slice(2);
const dir = "test-results";
const webms = [];
const walk = (d) => readdirSync(d).forEach((f) => {
  const p = join(d, f);
  if (statSync(p).isDirectory()) walk(p); else if (p.endsWith(".webm") && p.includes(filter.replace(/\.spec$/, "")) && (outArg || !p.includes("journey-recording"))) webms.push(p);
});
walk(dir);
if (!webms.length) { console.error("no recording found; run: npx playwright test --config playwright.review.config.ts --project recording"); process.exit(1); }
const src = webms.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs)[0];
const out = outArg ?? "review_pack/signature_interaction.mp4";
// Loading spans recorded by the spec are cut so the video has no dead air (review 005 #3).
let cuts = [];
try { if (!outArg) cuts = JSON.parse(readFileSync("test-results/recording-cuts.json", "utf8")); } catch { /* no cuts */ }
const keep = cuts.filter(([a, b]) => b > a).map(([a, b]) => `between(t,${a.toFixed(2)},${b.toFixed(2)})`).join("+");
const vf = "fps=25," + (keep ? `select='not(${keep})',setpts=N/25/TB,` : "") + "scale='min(1280,iw)':-2";
// REC_START (seconds): drop a warm-up at the start of the video (pages loaded once so the take has no spinners)
const start = process.env.REC_START ? ["-ss", process.env.REC_START] : [];
const r = spawnSync("ffmpeg", ["-v", "error", "-y", ...start, "-i", src, "-t", "60", "-vf", vf,
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", out], { stdio: "inherit" });
if (r.status !== 0) process.exit(r.status ?? 1);
console.log("wrote", out, `${(statSync(out).size / 1e6).toFixed(1)} MB from`, src);
