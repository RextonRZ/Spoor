import { chromium } from "playwright";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
p.on("console", (m) => console.log("console", m.type(), m.text().slice(0, 200)));
await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
for (let i = 0; i < 8; i++) {
  await p.waitForTimeout(2500);
  const s = await p.evaluate(() => ({
    views: document.querySelectorAll(".lp-view").length,
    video: [...document.querySelectorAll(".lp-view video")].map((v) => [v.src.split("/").pop(), +v.currentTime.toFixed(2), v.paused, v.readyState]),
    live: [...new Set([...document.querySelectorAll(".lp-feed-card.is-live")].map((c) => c.dataset.cam))],
    paused: document.querySelector(".lp-feed-hero")?.classList.contains("is-paused"),
    phase: document.querySelector(".lp-feed-hero")?.dataset.phase,
  }));
  console.log(JSON.stringify(s));
}
await b.close();
