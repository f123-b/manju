import assert from "node:assert/strict";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("FastAPI boots a relational demo and completes a durable generation task", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-api-"));
  const port = 8123;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "test.sqlite3"), SHORT_DRAMA_DEMO_DELAY: "0.05", SHORT_DRAMA_POLL_INTERVAL: "0.05" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  let health;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      health = await fetch(`http://127.0.0.1:${port}/api/health`);
      if (health.ok) break;
    } catch {
      // The worker needs a short moment to import FastAPI and seed SQLite.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  assert.equal(health?.ok, true);

  const projectResponse = await fetch(`http://127.0.0.1:${port}/api/projects/P001`);
  const project = await projectResponse.json();
  assert.equal(project.schemaVersion, 2);
  assert.equal(project.episodes.length, 24);
  assert.equal(project.shots.length, 6);
  assert.equal(project.assets.characters.length, 2);

  const createResponse = await fetch(`http://127.0.0.1:${port}/api/shots/SH046/generate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt: "测试持久化任务" }),
  });
  const created = await createResponse.json();
  assert.equal(createResponse.ok, true);

  let task;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await fetch(`http://127.0.0.1:${port}/api/generation-tasks/${created.task.id}`);
    task = await response.json();
    if (["Success", "Failed"].includes(task.status)) break;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  assert.equal(task.status, "Success");
  assert.equal(task.progress, 100);

  const exportResponse = await fetch(`http://127.0.0.1:${port}/api/projects/P001/export`, { method: "POST" });
  assert.equal(exportResponse.ok, true);
  assert.match(exportResponse.headers.get("content-type"), /application\/zip/);
  assert.ok((await exportResponse.arrayBuffer()).byteLength > 100);
});
