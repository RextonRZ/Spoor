// Starts the Spoor FastAPI backend for the frontend. Default NO-KEY mode: no Meta / Baseten keys, deterministic agents.
// Model-backed steps answer "analysis unavailable"; nothing is simulated in their place.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const local = join(root, ".local");
const port = process.env.SPOOR_API_PORT ?? "8000";
// `--keys` (npm run backend:keys): keep the keys from backend/.env (spoor.config reads it) instead of blanking them.
const withKeys = process.argv.includes("--keys");
const noKeys = withKeys ? {} : {
  MODEL_API_KEY: "", // blank = not configured (spoor.config treats blank as unset)
  BASETEN_API_KEY: "",
  BASETEN_MODEL_ID: "",
  AGENT_BACKEND: "none",
};
const env = {
  ...process.env,
  ...noKeys,
  // SPOOR_DATA=s2 (or `--data s2`): the S2 demo store (.local/backend-data-s2); default: the Thursday QA store the tests use
  DATA_DIR: join(local, (() => { const i = process.argv.indexOf("--data"); const d = i > 0 ? process.argv[i + 1] : process.env.SPOOR_DATA; return d ? `backend-data-${d}` : "backend-data"; })()),
  USERS_FILE: join(local, "users.json"),
  URL_SIGNING_SECRET: readFileSync(join(local, "signing.secret"), "utf8").trim(),
  RATE_LIMIT_PER_MINUTE: "2000",
};
const child = spawn("uv", ["run", "uvicorn", "spoor.api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", port],
  { cwd: join(root, "..", "backend"), env, stdio: "inherit", shell: process.platform === "win32" });
child.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
