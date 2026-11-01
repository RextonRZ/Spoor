// Prints /hub to PDF the way a browser does by default (no background graphics). node scripts/topbar-pdf.mjs <out.pdf>
import { chromium } from "playwright";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await p.pdf({ path: process.argv[2], format: "A4", landscape: true, printBackground: false, pageRanges: "1" });
await b.close();
