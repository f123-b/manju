import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function waitForHealth(base) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      if ((await fetch(`${base}/api/health`)).ok) return;
    } catch {
      // FastAPI is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error("FastAPI did not start in time");
}

async function waitForTask(base, taskId) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const response = await fetch(`${base}/api/generation-tasks/${taskId}`);
    const task = await response.json();
    if (["Success", "Failed", "Cancelled"].includes(task.status)) return task;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error("generation task did not finish");
}

test("normalizes common image API responses and rejects false successes", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-http-provider-"));
  const provider = createServer((request, response) => {
    if (request.method === "POST" && request.url === "/image") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ data: [{ url: "http://127.0.0.1:8134/generated.png" }] }));
      return;
    }
    if (request.method === "POST" && request.url === "/bad") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ status: "success", message: "accepted" }));
      return;
    }
    response.writeHead(404);
    response.end();
  });
  await new Promise((resolve) => provider.listen(8134, "127.0.0.1", resolve));
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8133"], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "provider.sqlite3"), SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await new Promise((resolve) => provider.close(resolve));
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = "http://127.0.0.1:8133";
  await waitForHealth(base);
  const save = async (url) => fetch(`${base}/api/settings/providers`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ providerUrl: `http://127.0.0.1:8134${url}`, providerName: "Test Image API", providerModel: "test-image", providerApiKey: "secret" }) });
  assert.equal((await save("/image")).ok, true);
  const created = await (await fetch(`${base}/api/projects/P001/assets/generate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ assetType: "locations", name: "API 场景", prompt: "夜晚天台" }) })).json();
  const task = await waitForTask(base, created.taskId);
  assert.equal(task.status, "Success");
  const project = await (await fetch(`${base}/api/projects/P001`)).json();
  assert.equal(project.assets.locations.find((item) => item.id === created.asset.id).image, "http://127.0.0.1:8134/generated.png");

  assert.equal((await save("/bad")).ok, true);
  const failedCreated = await (await fetch(`${base}/api/projects/P001/assets/generate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ assetType: "locations", name: "错误响应", prompt: "没有输出地址" }) })).json();
  const failedTask = await waitForTask(base, failedCreated.taskId);
  assert.equal(failedTask.status, "Failed");
  assert.match(failedTask.error, /没有找到|未返回/);
});
