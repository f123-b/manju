import assert from "node:assert/strict";
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

test("production canvas persists seeded nodes, edges, edits, and cleanup", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-canvas-"));
  const port = 8129;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "canvas.sqlite3"), SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  await waitForHealth(base);

  const initialResponse = await fetch(`${base}/api/projects/P001/canvas`);
  const initial = await initialResponse.json();
  assert.equal(initialResponse.ok, true);
  assert.equal(initial.nodes.length, 7);
  assert.equal(initial.edges.length, 6);
  assert.ok(initial.nodes.some((node) => node.type === "agent"));

  const createdResponse = await fetch(`${base}/api/projects/P001/canvas/nodes`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ type: "text", title: "测试输入", x: 80, y: 120, data: { content: "测试工作流" } }),
  });
  const createdPayload = await createdResponse.json();
  const created = createdPayload.node;
  assert.equal(createdResponse.ok, true);
  assert.equal(created.title, "测试输入");

  const patchedResponse = await fetch(`${base}/api/canvas-nodes/${created.id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ x: 260, y: 180, title: "已编辑输入" }),
  });
  const patchedPayload = await patchedResponse.json();
  const patched = patchedPayload.node;
  assert.equal(patchedResponse.ok, true);
  assert.equal(patched.x, 260);
  assert.equal(patched.title, "已编辑输入");

  const agent = initial.nodes.find((node) => node.type === "agent");
  const edgeResponse = await fetch(`${base}/api/projects/P001/canvas/edges`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ source: created.id, target: agent.id, label: "测试输入" }),
  });
  const edgePayload = await edgeResponse.json();
  const edge = edgePayload.edge;
  assert.equal(edgeResponse.ok, true);
  assert.equal(edge.source, created.id);
  assert.equal(edge.target, agent.id);

  const deleteEdgeResponse = await fetch(`${base}/api/canvas-edges/${edge.id}`, { method: "DELETE" });
  assert.equal(deleteEdgeResponse.ok, true);
  const deleteNodeResponse = await fetch(`${base}/api/canvas-nodes/${created.id}`, { method: "DELETE" });
  assert.equal(deleteNodeResponse.ok, true);

  const finalResponse = await fetch(`${base}/api/projects/P001/canvas`);
  const final = await finalResponse.json();
  assert.equal(final.nodes.length, 7);
  assert.equal(final.edges.length, 6);
});
