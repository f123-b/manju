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

async function waitForRun(base, runId) {
  let run;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const response = await fetch(`${base}/api/agent/runs/${runId}`);
    assert.equal(response.ok, true);
    run = (await response.json()).run;
    if (["success", "failed", "cancelled"].includes(run.status)) return run;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  return run;
}

async function waitForTask(base, taskId) {
  let task;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const response = await fetch(`${base}/api/generation-tasks/${taskId}`);
    assert.equal(response.ok, true);
    task = await response.json();
    if (["Success", "Failed", "Cancelled"].includes(task.status)) return task;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  return task;
}

test("persistent agent runs and project visual QC can be resumed through the API", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-agent-qc-"));
  const port = 8126;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "agent.sqlite3"), SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  await waitForHealth(base);

  const settingsResponse = await fetch(`${base}/api/settings/providers`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ llmProviderUrl: "", llmProviderName: "Test LLM", llmModel: "test-model", llmApiKey: "secret-llm-key" }) });
  const settings = await settingsResponse.json();
  assert.equal(settingsResponse.ok, true);
  assert.equal(settings.settings.llmApiKey, "");
  assert.equal(settings.settings.llmApiKeySet, true);

  const assetResponse = await fetch(`${base}/api/projects/P001/assets/generate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ assetType: "locations", name: "测试天台", description: "夜晚的城市天台", prompt: "电影感城市天台" }) });
  const assetQueued = await assetResponse.json();
  assert.equal(assetResponse.ok, true);
  assert.equal(assetQueued.queued, true);
  const assetTask = await waitForTask(base, assetQueued.taskId);
  assert.equal(assetTask.status, "Success");
  const afterAsset = await (await fetch(`${base}/api/projects/P001`)).json();
  assert.equal(afterAsset.assets.locations.find((item) => item.id === assetQueued.asset.id).status, "已生成");
  assert.ok(afterAsset.timeline.videoClips.length >= 1);
  const videoClip = afterAsset.timeline.videoClips[0];
  const patchVideoResponse = await fetch(`${base}/api/video-clips/${videoClip.id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ timelineStartMs: 500, durationMs: 2500 }) });
  const patchedVideo = await patchVideoResponse.json();
  assert.equal(patchVideoResponse.ok, true);
  assert.equal(patchedVideo.clip.timelineStartMs, 500);
  assert.equal(patchedVideo.clip.durationMs, 2500);
  const removeVideoResponse = await fetch(`${base}/api/video-clips/${videoClip.id}`, { method: "DELETE" });
  assert.equal(removeVideoResponse.ok, true);
  const restoreVideoResponse = await fetch(`${base}/api/projects/P001/video-clips`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ shotId: videoClip.shotId }) });
  assert.equal(restoreVideoResponse.ok, true);

  const runResponse = await fetch(`${base}/api/agent/runs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ projectId: "P001", episodeId: "EP08", goal: "把这一集整理成可生成的连续镜头，并补齐对白" }) });
  const created = await runResponse.json();
  assert.equal(runResponse.ok, true);
  const run = await waitForRun(base, created.run.id);
  assert.equal(run.status, "success");
  assert.equal(run.steps.length, 5);
  assert.ok(run.steps.every((step) => step.status === "success"));
  assert.ok(run.steps[0].output.goalSpec.deliverables.includes("shot_breakdown"));
  const historyResponse = await fetch(`${base}/api/projects/P001/agent/runs?episodeId=EP08`);
  const history = await historyResponse.json();
  assert.equal(historyResponse.ok, true);
  assert.equal(history.items[0].id, run.id);

  const qcResponse = await fetch(`${base}/api/projects/P001/qc`, { method: "POST" });
  const qc = await qcResponse.json();
  assert.equal(qcResponse.ok, true);
  assert.ok(qc.result.visual.length >= 1);
  assert.ok(qc.result.visual[0].checks.some((check) => check.type === "visual_decode"));
  assert.ok(qc.result.continuity.findings.length >= 1);

  const continuityResponse = await fetch(`${base}/api/projects/P001/continuity-check`, { method: "POST" });
  const continuity = await continuityResponse.json();
  assert.equal(continuityResponse.ok, true);
  assert.equal(continuity.result.projectId, "P001");

  const renderResponse = await fetch(`${base}/api/episodes/EP08/render`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
  const render = await renderResponse.json();
  assert.equal(renderResponse.ok, true);
  assert.ok(["ready", "blocked", "failed"].includes(render.render.status));
  if (render.render.status === "ready") {
    const mediaResponse = await fetch(`${base}${render.render.outputUrl}`);
    assert.equal(mediaResponse.ok, true);
    assert.match(mediaResponse.headers.get("content-type") || "", /video\/mp4/);
  }
  if (render.render.status === "blocked") assert.match(render.render.error, /FFmpeg/);
});

test("configured LLM vision QC sends an image and persists semantic findings", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-vision-qc-"));
  let requestBody;
  const llmServer = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    requestBody = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ status: "warning", score: 86, findings: [{ type: "composition", severity: "warning", score: 86, confidence: 0.91, message: "人物与对白意图基本匹配，建议人工确认视线方向" }] }) } }] }));
  });
  await new Promise((resolve) => llmServer.listen(0, "127.0.0.1", resolve));
  const llmPort = llmServer.address().port;
  const port = 8127;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "vision.sqlite3"), SHORT_DRAMA_DEMO_DELAY: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await new Promise((resolve) => llmServer.close(resolve));
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  await waitForHealth(base);
  const settingsResponse = await fetch(`${base}/api/settings/providers`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ llmProviderUrl: `http://127.0.0.1:${llmPort}`, llmProviderName: "Vision Test", llmModel: "vision-test" }) });
  assert.equal(settingsResponse.ok, true);

  const qcResponse = await fetch(`${base}/api/shots/SH041/qc`, { method: "POST" });
  const qc = await qcResponse.json();
  assert.equal(qcResponse.ok, true);
  assert.equal(qc.result.vision.status, "success");
  assert.equal(qc.result.vision.provider, "Vision Test");
  assert.ok(qc.result.checks.some((check) => check.type === "vision_semantic" && check.message.includes("视线方向")));
  assert.equal(Array.isArray(requestBody.messages[1].content), true);
  const imagePart = requestBody.messages[1].content.find((item) => item.type === "image_url");
  assert.match(imagePart.image_url.url, /^data:image\/png;base64,/);

  const recordsResponse = await fetch(`${base}/api/projects/P001/qc`);
  const records = await recordsResponse.json();
  assert.equal(recordsResponse.ok, true);
  assert.ok(records.items.some((item) => item.type === "vision_semantic" && item.shot_id === "SH041"));
});
