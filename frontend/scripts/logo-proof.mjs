// Logo proof sheet (owner_final_0815): the PNGs next to the SVG rebuild, marks at 16/32/64/256 px on both themes.
// node scripts/logo-proof.mjs <repo root> <out.png>
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import path from "node:path";
const root = process.argv[2], out = process.argv[3];
const b64 = (p) => "data:" + (p.endsWith(".png") ? "image/png" : "image/svg+xml") + ";base64," + readFileSync(path.join(root, p)).toString("base64");
const L = b64("frontend/public/brand/spoor-logo.svg"), D = b64("frontend/public/brand/spoor-logo-dark.svg");
const M = b64("frontend/public/brand/spoor-mark.svg"), MD = b64("frontend/public/brand/spoor-mark-dark.svg");
const S = b64("frontend/public/brand/spoor-mark-small.svg"), I = b64("frontend/public/brand/spoor-icon.svg");
const PL = b64("assets/brand/spoor_logo_fingerprint_light.png"), PD = b64("assets/brand/spoor_logo_fingerprint_dark.png");
const sizes = (src, bg) => [16, 32, 64, 256].map(s => `<div style="display:inline-block;margin:8px;text-align:center;font:11px sans-serif;color:#888"><img src="${s <= 32 ? S : src}" width="${s}" height="${s}" style="background:${bg}"/><br>${s}px${s <= 32 ? " (small)" : ""}</div>`).join("");
const html = `<html><body style="margin:0;font:13px sans-serif">
<div style="display:flex">
 <div style="background:#fff;padding:20px;width:50%"><b>Rexton PNG (light)</b><br><img src="${PL}" height="110"><br><b>SVG rebuild (light)</b><br><img src="${L}" height="110"></div>
 <div style="background:#0B0C10;color:#ddd;padding:20px;width:50%"><b>Rexton PNG (dark)</b><br><img src="${PD}" height="110"><br><b>SVG rebuild (dark)</b><br><img src="${D}" height="110"></div>
</div>
<div style="display:flex"><div style="background:#fff;padding:12px;width:50%">${sizes(M, "#fff")}</div><div style="background:#0B0C10;padding:12px;width:50%">${sizes(MD, "#0B0C10")}</div></div>
<div style="padding:12px;background:#f3f4f6">favicon / app icon: <img src="${I}" width="16"> <img src="${I}" width="32"> <img src="${I}" width="64"></div>
</body></html>`;
const br = await chromium.launch(); const pg = await br.newPage({ viewport: { width: 1500, height: 900 } });
await pg.setContent(html); await pg.waitForTimeout(300);
await pg.screenshot({ path: out, fullPage: true }); await br.close(); console.log("wrote", out);
