import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFileSync, spawn } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function waitForHealth(base) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(`${base}/api/health`);
      if (response.ok) return;
    } catch {
      // Wait for FastAPI startup.
    }
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error("FastAPI did not start in time");
}

test("provider settings persist safely and test a configured endpoint", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-settings-"));
  const port = 8125;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "settings.sqlite3"), SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  await waitForHealth(base);

  const initialResponse = await fetch(`${base}/api/settings/providers`);
  const initial = await initialResponse.json();
  assert.equal(initialResponse.ok, true);
  assert.equal(initial.settings.apiKeySet, false);
  assert.equal(initial.settings.providerApiKey, "");
  assert.equal(initial.settings.secretStorage.encrypted, true);

  const healthResponse = await fetch(`${base}/api/health`);
  const health = await healthResponse.json();
  assert.equal(healthResponse.ok, true);
  assert.equal(health.providers.image.provider, "Local Demo");
  assert.equal(health.providers.video.model, "mock-video");
  assert.equal(health.providers.llm.configured, false);

  const sessionResponse = await fetch(`${base}/api/session`);
  const session = await sessionResponse.json();
  assert.equal(sessionResponse.ok, true);
  assert.equal(session.workspace.id, "local");
  assert.equal(session.user.role, "owner");

  const saveResponse = await fetch(`${base}/api/settings/providers`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ providerName: "Test Gateway", providerModel: "test-model", providerApiKey: "secret-value", voiceProvider: "mock" }),
  });
  const saved = await saveResponse.json();
  assert.equal(saveResponse.ok, true);
  assert.equal(saved.settings.providerName, "Test Gateway");
  assert.equal(saved.settings.providerApiKey, "");
  assert.equal(saved.settings.apiKeySet, true);
  assert.equal(saved.settings.providerApiKeyMasked, "••••••••");
  const rawSecret = execFileSync("python", ["-c", "import os, sqlite3; print(sqlite3.connect(os.environ['TEST_DB']).execute(\"SELECT value FROM runtime_settings WHERE key='providerApiKey'\").fetchone()[0])"], { env: { ...process.env, TEST_DB: path.join(tempDir, "settings.sqlite3") }, encoding: "utf8" }).trim();
  assert.doesNotMatch(rawSecret, /secret-value/);
  assert.match(rawSecret, /^(dpapi|file):v1:/);

  const testResponse = await fetch(`${base}/api/settings/providers/test`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "video", providerUrl: `${base}/api/health` }),
  });
  const tested = await testResponse.json();
  assert.equal(testResponse.ok, true);
  assert.equal(tested.ok, true);
  assert.equal(tested.status, "reachable");

  const llmTestResponse = await fetch(`${base}/api/settings/providers/test`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "llm", llmProviderUrl: `${base}/api/health`, llmProviderName: "Test LLM", llmApiKey: "secret-llm" }),
  });
  const llmTested = await llmTestResponse.json();
  assert.equal(llmTestResponse.ok, true);
  assert.equal(llmTested.ok, true);
  assert.equal(llmTested.status, "reachable");

  const clearResponse = await fetch(`${base}/api/settings/providers`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ providerUrl: "", providerApiKey: "__CLEAR__", providerName: "External Video API", providerModel: "video-default" }),
  });
  const cleared = await clearResponse.json();
  assert.equal(clearResponse.ok, true);
  assert.equal(cleared.settings.apiKeySet, false);

  const auditResponse = await fetch(`${base}/api/audit-events`);
  const audit = await auditResponse.json();
  assert.equal(auditResponse.ok, true);
  assert.ok(audit.items.some((item) => item.action === "settings.updated"));
});
