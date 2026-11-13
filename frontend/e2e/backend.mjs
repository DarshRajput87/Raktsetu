// Starts a throwaway RaktSetu API for the Playwright tests: its own database
// (raktsetu_e2e), seeded with the fixed synthetic city (seed 42, as of
// 2026-11-13), on port 8001. The developer's database and API are not touched.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const backend = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "backend");
const python = [join(backend, ".venv", "Scripts", "python.exe"), join(backend, ".venv", "bin", "python")].find(existsSync) ?? "python";
const env = {
  ...process.env,
  DB_NAME: "raktsetu_e2e",
  AS_OF_DATE: "2026-11-13",
  ENVIRONMENT: "development",
  BACKGROUND_TASKS: "false",
  CITY_CACHE_CAPACITY: "2",
};

const seed = spawnSync(python, ["-m", "db.seed", "--reset", "--source", "output"], { cwd: backend, env, stdio: "inherit" });
if (seed.status !== 0) process.exit(seed.status ?? 1);

const server = spawn(python, ["-m", "uvicorn", "api.main:app", "--port", "8001"], { cwd: backend, env, stdio: "inherit" });
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
process.on("exit", stop);
server.on("exit", (code) => process.exit(code ?? 0));
