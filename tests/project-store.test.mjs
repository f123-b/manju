import assert from "node:assert/strict";
import test from "node:test";
import {
  addShot,
  addStoryRule,
  cancelTask,
  cloneProject,
  completeGeneration,
  getProjectStats,
  loadProject,
  queueGeneration,
  removeShot,
  saveProject,
  updateShot,
} from "../src/projectStore.js";

test("shot edits remain immutable", () => {
  const project = cloneProject();
  const next = updateShot(project, "SH041", { description: "新的镜头描述" });
  assert.equal(project.shots[0].description, "林泽看着苏晴，眼神复杂");
  assert.equal(next.shots[0].description, "新的镜头描述");
});

test("adding a shot creates a new pending shot in the current episode", () => {
  const project = cloneProject();
  const result = addShot(project);
  assert.equal(result.shot.id, "SH047");
  assert.equal(result.shot.episodeId, "EP08");
  assert.equal(result.shot.status, "待生成");
  assert.equal(result.project.shots.length, project.shots.length + 1);
});

test("generation queue produces a version and records cost", () => {
  const project = cloneProject();
  const queued = queueGeneration(project, "SH045", "prompt", "T100", "2026-09-26 10:00");
  assert.equal(queued.tasks[0].status, "Running");
  assert.equal(queued.shots.find((shot) => shot.id === "SH045").status, "生成中");
  const completed = completeGeneration(queued, "T100", "2026-09-26 10:01");
  const shot = completed.shots.find((item) => item.id === "SH045");
  assert.equal(completed.tasks[0].status, "Success");
  assert.equal(shot.status, "已生成");
  assert.equal(shot.versions.length, 1);
  assert.equal(completed.spent, 53.09);
});

test("running tasks can be cancelled", () => {
  const project = queueGeneration(cloneProject(), "SH046", "prompt", "T101", "2026-09-26 10:00");
  const cancelled = cancelTask(project, "T101");
  assert.equal(cancelled.tasks[0].status, "Cancelled");
  assert.equal(cancelled.shots.find((shot) => shot.id === "SH046").status, "待生成");
});

test("removing a shot also removes its tasks", () => {
  const project = queueGeneration(cloneProject(), "SH046", "prompt", "T102", "2026-09-26 10:00");
  const next = removeShot(project, "SH046");
  assert.equal(next.shots.some((shot) => shot.id === "SH046"), false);
  assert.equal(next.tasks.some((task) => task.shotId === "SH046"), false);
});

test("story rules and dashboard stats update", () => {
  const project = addStoryRule(cloneProject(), "新规则");
  assert.equal(project.storyBible.rules.at(-1), "新规则");
  assert.deepEqual(getProjectStats(project), { running: 0, failed: 1, pending: 2, review: 3 });
});

test("project state persists through storage", () => {
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  const project = cloneProject();
  project.title = "持久化测试";
  saveProject(project, storage);
  assert.equal(loadProject(storage).title, "持久化测试");
});
