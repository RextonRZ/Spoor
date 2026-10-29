import { defineConfig } from "@playwright/test";

/** Review pack (QUEUE C7): screenshots of every surface at 1440x900 and 390x844, plus the interaction recording. */
const args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"];
export default defineConfig({
  testDir: "tests/review",
  timeout: 300_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3000", launchOptions: { args } },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 }, testIgnore: /recording|new-evidence/ },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      testIgnore: /recording|new-evidence/ },
    { name: "new-evidence", testMatch: /new-evidence/, use: { viewport: { width: 1280, height: 800 },
      video: { mode: "on", size: { width: 1280, height: 800 } } } },
    { name: "recording", testMatch: /recording/, use: { viewport: { width: 1280, height: 800 },
      video: { mode: "on", size: { width: 1280, height: 800 } } } },
  ],
  webServer: { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: true, timeout: 180_000 },
});
