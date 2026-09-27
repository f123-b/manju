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

test("RunningHub workflow records persist and protect API keys", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-runninghub-"));
  const port = 8130;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "runninghub.sqlite3"), SHORT_DRAMA_SEED_DEMO: "1", SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  await waitForHealth(base);

  const settingsResponse = await fetch(`${base}/api/settings/providers`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ runninghubBaseUrl: "https://www.runninghub.cn", runninghubApiKey: "test-secret" }) });
  const settingsPayload = await settingsResponse.json();
  assert.equal(settingsResponse.ok, true);
  assert.equal(settingsPayload.settings.runninghubApiKey, "");
  assert.equal(settingsPayload.settings.runninghubApiKeySet, true);

  const clearSettingsResponse = await fetch(`${base}/api/settings/providers`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ runninghubApiKey: "__CLEAR__" }) });
  assert.equal(clearSettingsResponse.ok, true);

  const createResponse = await fetch(`${base}/api/projects/P001/runninghub/workflows`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: "测试工作流", workflowId: "wf-test-1", apiJson: { "6": { class_type: "CLIPTextEncode", inputs: { text: "hello" } } } }) });
  const createdPayload = await createResponse.json();
  assert.equal(createResponse.ok, true);
  assert.equal(createdPayload.workflow.apiJson["6"].inputs.text, "hello");

  const patchResponse = await fetch(`${base}/api/runninghub/workflows/${createdPayload.workflow.id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ apiJson: { "6": { class_type: "CLIPTextEncode", inputs: { text: "updated" } } } }) });
  const patchedPayload = await patchResponse.json();
  assert.equal(patchResponse.ok, true);
  assert.equal(patchedPayload.workflow.apiJson["6"].inputs.text, "updated");

  const runResponse = await fetch(`${base}/api/runninghub/workflows/${createdPayload.workflow.id}/run`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ nodeInfoList: [{ nodeId: "6", fieldName: "text", fieldValue: "updated" }] }) });
  assert.equal(runResponse.status, 422);
  const runPayload = await runResponse.json();
  assert.match(runPayload.detail, /RunningHub API Key/);

  const deleteResponse = await fetch(`${base}/api/runninghub/workflows/${createdPayload.workflow.id}`, { method: "DELETE" });
  assert.equal(deleteResponse.ok, true);
});
