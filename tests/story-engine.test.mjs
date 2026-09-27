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
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error("FastAPI did not start");
}

test("Story Engine keeps speaker identity structured and emits production storyboard fields", async (t) => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "manju-story-engine-"));
  const port = 8135;
  const server = spawn("python", ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: {
      ...process.env,
      SHORT_DRAMA_DB: path.join(tempDir, "story.sqlite3"),
      SHORT_DRAMA_SEED_DEMO: "1",
      SHORT_DRAMA_DEMO_DELAY: "0.02",
    },
    stdio: "ignore",
  });
  t.after(async () => {
    server.kill();
    await rm(tempDir, { recursive: true, force: true });
  });

  const base = `http://127.0.0.1:${port}`;
  await waitForHealth(base);

  const snapshotResponse = await fetch(`${base}/api/projects/P001/story-engine`);
  assert.equal(snapshotResponse.ok, true);
  const snapshot = await snapshotResponse.json();
  assert.equal(snapshot.projectId, "P001");
  assert.ok(snapshot.storyBible.logline);

  const scriptResponse = await fetch(`${base}/api/scenes/SC03/script`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      script: {
        summary: "林泽和苏晴完成一次不可逆的关系转折。",
        acceptanceCriteria: ["林泽明确拒绝回到旧关系", "苏晴的下一步目标发生变化"],
        flow: [
          { kind: "action", action: "林泽停在天台边，没有回头。" },
          { kind: "dialogue", speakerId: "C001", line: "到此为止吧。", delivery: "平静、明确" },
          { kind: "dialogue", speakerId: "C002", line: "你真的不想知道真相吗？", delivery: "压住慌张" },
        ],
        sound: "夜风和远处车流。",
      },
    }),
  });
  assert.equal(scriptResponse.ok, true);
  const scene = await scriptResponse.json();
  assert.equal(scene.script.flow.filter((beat) => beat.kind === "dialogue").length, 2);
  assert.deepEqual(scene.script.flow.filter((beat) => beat.kind === "dialogue").map((beat) => beat.speakerId), ["C001", "C002"]);

  const dialogueResponse = await fetch(`${base}/api/scenes/SC03/dialogue-lines/extract`);
  assert.equal(dialogueResponse.ok, true);
  const dialogue = await dialogueResponse.json();
  const matching = dialogue.items.filter((line) => ["到此为止吧。", "你真的不想知道真相吗？"].includes(line.text));
  assert.equal(matching.length, 2);
  assert.deepEqual(matching.map((line) => line.characterId), ["C001", "C002"]);

  const breakdownResponse = await fetch(`${base}/api/scenes/SC03/breakdown`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      replaceExisting: true,
      segments: [{
        blocking: "林泽画左，苏晴画右，保持轴线。",
        soundscape: "夜风",
        cuts: [
          { beatRefs: ["BT001"], seconds: 3, size: "wide", camera: "Static Shot", characters: ["C001", "C002"], frame: "双人天台全景", shot: "建立两人空间关系", lens: "35mm", cameraPosition: "双人平视", composition: "三分法", eyeline: "彼此", focus: "双人", stability: "stable" },
          { beatRefs: ["BT002"], seconds: 3, size: "close", camera: "Push In", characters: ["C001"], frame: "林泽近景", shot: "林泽说出决定", lens: "85mm", cameraPosition: "林泽平视正面", composition: "中心构图", eyeline: "苏晴", focus: "林泽面部", stability: "stable" },
        ],
      }],
    }),
  });
  assert.equal(breakdownResponse.ok, true);
  const breakdown = await breakdownResponse.json();
  assert.equal(breakdown.items.length, 2);
  assert.ok(breakdown.items.every((shot) => shot.segmentId));
  assert.equal(breakdown.items[1].cameraPosition, "林泽平视正面");
  assert.equal(breakdown.items[1].composition, "中心构图");

  const validationResponse = await fetch(`${base}/api/projects/P001/story/validate`, { method: "POST" });
  assert.equal(validationResponse.ok, true);
  const validation = await validationResponse.json();
  assert.ok(Array.isArray(validation.gates));
  assert.equal(validation.gates.find((gate) => gate.id === "speaker-integrity")?.status, "pass");
  assert.equal(validation.gates.find((gate) => gate.id === "segment-duration")?.status, "pass");

  const exportResponse = await fetch(`${base}/api/projects/P001/export`, { method: "POST" });
  assert.equal(exportResponse.ok, true);
  assert.ok((await exportResponse.arrayBuffer()).byteLength > 100);
});
