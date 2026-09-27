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

test("discovers and classifies OpenAI-compatible models", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-model-discovery-"));
  const modelServer = createServer((request, response) => {
    if (request.url !== "/v1/models") {
      response.writeHead(404);
      response.end();
      return;
    }
    assert.equal(request.headers.authorization, "Bearer discovery-secret");
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ data: [
      { id: "MiniMaxAI/MiniMax-VL-01", capabilities: { text: true, vision: true } },
      { id: "deepseek-flash", name: "DeepSeek-V4.1-Flash", input_modalities: ["text", "image"], output_modalities: ["text"] },
      { id: "gpt-image-2.5-flare" },
      { id: "gpt-6-sol" },
      { id: "black-forest-labs/FLUX.1-schnell" },
      { id: "Wan-AI/Wan2.1-T2V-14B" },
      { id: "BAAI/bge-m3" },
    ] }));
  });
  await new Promise((resolve) => modelServer.listen(8132, "127.0.0.1", resolve));
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8131"], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "models.sqlite3"), SHORT_DRAMA_SEED_DEMO: "1", SHORT_DRAMA_ALLOW_MOCK_GENERATION: "1", SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await new Promise((resolve) => modelServer.close(resolve));
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = "http://127.0.0.1:8131";
  await waitForHealth(base);
  const response = await fetch(`${base}/api/settings/providers/discover-models`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "video", url: "http://127.0.0.1:8132/v1", apiKey: "discovery-secret", providerName: "测试 Provider" }),
  });
  const payload = await response.json();
  assert.equal(response.ok, true);
  assert.deepEqual(payload.models.find((item) => item.modelId.includes("FLUX"))?.type, "image");
  assert.deepEqual(payload.models.find((item) => item.modelId.includes("gpt-image"))?.type, "image");
  assert.deepEqual(payload.models.find((item) => item.modelId === "gpt-6-sol")?.type, "text");
  assert.deepEqual(payload.models.find((item) => item.modelId.includes("Wan2"))?.type, "video");
  assert.deepEqual(payload.models.find((item) => item.modelId.includes("MiniMax"))?.type, "vision");
  assert.deepEqual(payload.models.find((item) => item.modelId === "deepseek-flash")?.type, "vision");
  assert.equal(payload.models.find((item) => item.modelId === "deepseek-flash")?.capabilities.imageOutput, false);
  assert.deepEqual(payload.models.find((item) => item.modelId.includes("bge"))?.type, "embedding");
  assert.deepEqual(payload.groups.map((group) => group.type).sort(), ["embedding", "image", "text", "video", "vision"]);

  const catalogResponse = await fetch(`${base}/api/models`);
  const catalog = await catalogResponse.json();
  assert.ok(catalog.items.some((item) => item.provider === "测试 Provider" && item.modelId.includes("FLUX")));
});
