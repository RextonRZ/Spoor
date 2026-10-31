import { defineConfig } from "@playwright/test";

/** Review pack for the flow (review/refs/flow): every screen at 1440x900 and 390x844. */
const args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"];
export default defineConfig({
  testDir: "tests/review",
  timeout: 300_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3000", launchOptions: { args } },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true } },
  ],
  webServer: { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: true, timeout: 180_000 },
});
