/* global process, console, setTimeout, clearTimeout */
import { spawn } from "node:child_process";
import { createServer } from "vite";

// Use an isolated browser profile so tests never touch an existing session.
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const profile = await mkdtemp(join(tmpdir(), "airroute-auth-"));
const server = await createServer({
  cacheDir: join(profile, "vite-cache"),
  server: { host: "127.0.0.1", port: 0 },
});
try {
  await server.listen();
  const chrome = process.env.CHROME_PATH ?? (process.platform === "darwin"
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : "google-chrome");
  const output = await new Promise((resolve, reject) => {
    const child = spawn(chrome, [
      "--headless", "--disable-gpu", `--user-data-dir=${profile}`,
      "--dump-dom", "--virtual-time-budget=10000",
      `${server.resolvedUrls.local[0]}tests/auth.html`,
    ]);
    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error("Authentication browser tests timed out"));
    }, 30000);
    child.stdout.on("data", (data) => { stdout += data; });
    child.stderr.on("data", (data) => { stderr += data; });
    child.on("error", (error) => { clearTimeout(timeout); reject(error); });
    child.on("close", (code) => {
      clearTimeout(timeout);
      if (code !== 0) reject(new Error(`Chrome exited with ${code}: ${stderr}`));
      else resolve(stdout);
    });
  });
  console.log(output.match(/<pre id="results">([\s\S]*?)<\/pre>/)?.[1] ?? output);
  if (!output.includes('data-test-status="passed"')) process.exitCode = 1;
} finally {
  await server.close();
  await rm(profile, { recursive: true, force: true });
}
