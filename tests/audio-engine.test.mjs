import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function waitForTask(base, taskId) {
  let task;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    task = await (await fetch(`${base}/api/generation-tasks/${taskId}`)).json();
    if (["Success", "Failed"].includes(task.status)) return task;
    await new Promise((resolve) => setTimeout(resolve, 70));
  }
  return task;
}

test("audio engine extracts lines, persists takes, runs QC and mixdown", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "short-drama-audio-"));
  const port = 8124;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "audio.sqlite3"), SHORT_DRAMA_SEED_DEMO: "1", SHORT_DRAMA_ALLOW_MOCK_GENERATION: "1", SHORT_DRAMA_DEMO_DELAY: "0.03", SHORT_DRAMA_POLL_INTERVAL: "0.03" },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${base}/api/health`)).ok) break;
    } catch {
      // Wait for FastAPI startup.
    }
    await new Promise((resolve) => setTimeout(resolve, 80));
  }

  const linesResponse = await fetch(`${base}/api/scenes/SC03/dialogue-lines`);
  const lines = await linesResponse.json();
  assert.equal(linesResponse.ok, true);
  assert.ok(lines.items.length >= 2);
  const line = lines.items[0];

  const profileResponse = await fetch(`${base}/api/characters/C001/voice-profiles`);
  const profiles = await profileResponse.json();
  assert.equal(profileResponse.ok, true);
  assert.equal(profiles.items[0].consentStatus, "unknown");
  const consentResponse = await fetch(`${base}/api/voice-profiles/${profiles.items[0].id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ consentStatus: "user_owned" }) });
  assert.equal(consentResponse.ok, true);
  const lockResponse = await fetch(`${base}/api/voice-profiles/${profiles.items[0].id}/lock`, { method: "POST" });
  assert.equal(lockResponse.ok, true);

  const directionResponse = await fetch(`${base}/api/dialogue-lines/${line.id}/direct-performance`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ emotion: "坚定", speed: 1.05 }) });
  const direction = await directionResponse.json();
  assert.equal(directionResponse.ok, true);
  assert.equal(direction.performance.emotion, "坚定");

  const generateResponse = await fetch(`${base}/api/dialogue-lines/${line.id}/generate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({}) });
  const generated = await generateResponse.json();
  assert.equal(generateResponse.ok, true);
  const task = await waitForTask(base, generated.taskId);
  assert.equal(task.status, "Success");
  assert.equal(task.targetType, "voice_take");

  const takesResponse = await fetch(`${base}/api/dialogue-lines/${line.id}/takes`);
  const takes = await takesResponse.json();
  const take = takes.items[0];
  assert.equal(take.status, "success");
  assert.match(take.outputUrl, /generated-media\/.*\.wav/);

  const qcResponse = await fetch(`${base}/api/voice-takes/${take.id}/run-qc`, { method: "POST" });
  const qc = await qcResponse.json();
  assert.equal(qcResponse.ok, true);
  assert.equal(qc.status, "pass");
  assert.equal(qc.durationFit.decision, "pass");

  const activateResponse = await fetch(`${base}/api/voice-takes/${take.id}/activate`, { method: "POST" });
  assert.equal(activateResponse.ok, true);
  const clipResponse = await fetch(`${base}/api/projects/P001/audio-clips`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ takeId: take.id, episodeId: "EP08", sceneId: "SC03", trackType: "dialogue" }) });
  assert.equal(clipResponse.ok, true);
  const clip = (await clipResponse.json()).clip;
  const patchClipResponse = await fetch(`${base}/api/audio-clips/${clip.id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ timelineStartMs: 1200, durationMs: 1800, gainDb: -2 }) });
  const patchedClip = await patchClipResponse.json();
  assert.equal(patchClipResponse.ok, true);
  assert.equal(patchedClip.clip.timelineStartMs, 1200);
  assert.equal(patchedClip.clip.gainDb, -2);
  const mixResponse = await fetch(`${base}/api/episodes/EP08/mixdown`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
  const mix = await mixResponse.json();
  assert.equal(mixResponse.ok, true);
  assert.match(mix.mixdown.outputUrl, /generated-media\/.*\.wav/);
  const deleteClipResponse = await fetch(`${base}/api/audio-clips/${clip.id}`, { method: "DELETE" });
  assert.equal(deleteClipResponse.ok, true);
});
