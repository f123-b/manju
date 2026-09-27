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
    env: { ...process.env, SHORT_DRAMA_DB: path.join(tempDir, "test.sqlite3"), SHORT_DRAMA_SEED_DEMO: "1", SHORT_DRAMA_ALLOW_MOCK_GENERATION: "1", SHORT_DRAMA_DEMO_DELAY: "0.05", SHORT_DRAMA_POLL_INTERVAL: "0.05" },
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

  const characterAssetResponse = await fetch(`http://127.0.0.1:${port}/api/projects/P001/assets/generate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ assetType: "characters", name: "测试人物", description: "黑发，冷静，电影感写实" }),
  });
  const characterAsset = await characterAssetResponse.json();
  assert.equal(characterAssetResponse.ok, true);
  assert.equal(characterAsset.asset.id, "C003");
  assert.equal(characterAsset.asset.image, null);

  const charactersResponse = await fetch(`http://127.0.0.1:${port}/api/projects/P001/characters`);
  const characters = await charactersResponse.json();
  assert.equal(characters.items[0].lookCount, 1);
  assert.equal(characters.items[0].identityLocked, true);

  const candidateResponse = await fetch(`http://127.0.0.1:${port}/api/characters/C001/generate-candidates`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ count: 4 }),
  });
  const candidates = await candidateResponse.json();
  assert.equal(candidateResponse.ok, true);
  assert.equal(candidates.referenceIds.length, 4);
  for (const taskId of candidates.taskIds) {
    let candidateTask;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      candidateTask = await (await fetch(`http://127.0.0.1:${port}/api/generation-tasks/${taskId}`)).json();
      if (["Success", "Failed"].includes(candidateTask.status)) break;
      await new Promise((resolve) => setTimeout(resolve, 80));
    }
    assert.equal(candidateTask.status, "Success");
    assert.equal(candidateTask.targetType, "character_reference");
  }
  const referencesResponse = await fetch(`http://127.0.0.1:${port}/api/characters/C001/references`);
  const references = await referencesResponse.json();
  const candidate = references.items.find((item) => item.id === candidates.referenceIds[0]);
  assert.equal(candidate.lifecycleStatus, "generated");
  const approveReference = await fetch(`http://127.0.0.1:${port}/api/character-references/${candidate.id}/approve`, { method: "POST" });
  assert.equal(approveReference.ok, true);
  const canonicalResponse = await fetch(`http://127.0.0.1:${port}/api/characters/C001/canonical`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ referenceId: candidate.id }) });
  assert.equal(canonicalResponse.ok, true);
  const masterResponse = await fetch(`http://127.0.0.1:${port}/api/characters/C001/generate-master-sheet`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({}) });
  const master = await masterResponse.json();
  assert.equal(masterResponse.ok, true);
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const masterTask = await (await fetch(`http://127.0.0.1:${port}/api/generation-tasks/${master.taskId}`)).json();
    if (["Success", "Failed"].includes(masterTask.status)) break;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  const approveMaster = await fetch(`http://127.0.0.1:${port}/api/character-references/${master.referenceId}/approve`, { method: "POST" });
  assert.equal(approveMaster.ok, true);
  const lockResponse = await fetch(`http://127.0.0.1:${port}/api/characters/C001/lock`, { method: "POST" });
  const lockedCharacter = await lockResponse.json();
  assert.equal(lockedCharacter.identityLocked, true);

  const lookResponse = await fetch(`http://127.0.0.1:${port}/api/characters/C001/looks`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: "天台夜戏", differences: { wardrobe: "黑色风衣" }, validFromSceneId: "SC03" }) });
  const look = await lookResponse.json();
  assert.equal(lookResponse.ok, true);
  const bindingResponse = await fetch(`http://127.0.0.1:${port}/api/shots/SH041/characters`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ items: [{ characterId: "C001", lookId: look.look.id, primaryReferenceId: "REF-C001-LEGACY", emotion: "克制" }, { characterId: "C002", lookId: "O002", primaryReferenceId: "REF-C002-LEGACY", emotion: "迟疑" }] }) });
  const bindings = await bindingResponse.json();
  assert.equal(bindingResponse.ok, true);
  assert.deepEqual(bindings.items.map((item) => item.lookId), [look.look.id, "O002"]);
  assert.deepEqual(bindings.items.map((item) => item.emotion), ["克制", "迟疑"]);
  const impactResponse = await fetch(`http://127.0.0.1:${port}/api/character-looks/${look.look.id}/affected-shots`);
  const impact = await impactResponse.json();
  assert.equal(impactResponse.ok, true);
  assert.ok(impact.shotIds.includes("SH041"));
  assert.ok(impact.items.some((item) => item.stale === true));

  const shotGenerateWithReferences = await fetch(`http://127.0.0.1:${port}/api/shots/SH041/generate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ prompt: "带角色参考的生成" }) });
  const shotRequest = await shotGenerateWithReferences.json();
  assert.equal(shotRequest.references.length, 2);
  assert.ok(shotRequest.references.every((item) => item.lifecycleStatus === "approved"));

  const locationAssetResponse = await fetch(`http://127.0.0.1:${port}/api/projects/P001/assets/generate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ assetType: "locations", name: "测试天台", description: "夜晚城市天台" }),
  });
  const locationAsset = await locationAssetResponse.json();
  assert.equal(locationAssetResponse.ok, true);
  assert.equal(locationAsset.asset.id, "L002");
  assert.equal(locationAsset.asset.image, null);

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
