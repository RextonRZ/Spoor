// Starts the Spoor FastAPI backend in NO-KEY mode for the frontend: no Meta / Baseten keys, deterministic agents.
// Model-backed steps answer "analysis unavailable"; nothing is simulated in their place.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const local = join(root, ".local");
const port = process.env.SPOOR_API_PORT ?? "8000";
const env = {
  ...process.env,
  MODEL_API_KEY: "", // blank = not configured (spoor.config treats blank as unset)
  BASETEN_API_KEY: "",
  BASETEN_MODEL_ID: "",
  AGENT_BACKEND: "none",
  DATA_DIR: join(local, "backend-data"),
  USERS_FILE: join(local, "users.json"),
  URL_SIGNING_SECRET: readFileSync(join(local, "signing.secret"), "utf8").trim(),
  RATE_LIMIT_PER_MINUTE: "2000",
};
const child = spawn("uv", ["run", "uvicorn", "spoor.api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", port],
  { cwd: join(root, "..", "backend"), env, stdio: "inherit", shell: process.platform === "win32" });
child.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
