import { initialProject } from "./projectData.js";

export const STORAGE_KEY = "short-drama-os.project.v1";

export function cloneProject(project = initialProject) {
  return JSON.parse(JSON.stringify(project));
}

export function loadProject(storage = globalThis.localStorage) {
  if (!storage) return cloneProject();
  try {
    const saved = storage.getItem(STORAGE_KEY);
    if (!saved) return cloneProject();
    const parsed = JSON.parse(saved);
    return parsed?.schemaVersion === 1 ? parsed : cloneProject();
  } catch {
    return cloneProject();
  }
}

export function saveProject(project, storage = globalThis.localStorage) {
  if (!storage) return;
  storage.setItem(STORAGE_KEY, JSON.stringify(project));
}

export function updateShot(project, shotId, patch) {
  return {
    ...project,
    shots: project.shots.map((shot) => shot.id === shotId ? { ...shot, ...patch } : shot),
  };
}

export function addShot(project, episodeId = project.currentEpisodeId, sceneId = project.currentScene.id) {
  const nextNumber = Math.max(...project.shots.map((shot) => Number(shot.id.replace(/\D/g, ""))), 0) + 1;
  const id = `SH${String(nextNumber).padStart(3, "0")}`;
  const relatedShots = project.shots.filter((shot) => shot.episodeId === episodeId && shot.sceneId === sceneId);
  const previous = relatedShots.at(-1) || project.shots[0];
  const start = relatedShots.reduce((sum, shot) => sum + Number(shot.duration || 0), 0);
  const duration = 4;
  const formatTime = (value) => `00:${String(value).padStart(2, "0")}`;
  const shot = {
    ...previous,
    id,
    episodeId,
    sceneId,
    time: `${formatTime(start)} – ${formatTime(start + duration)}`,
    description: "新镜头",
    status: "待生成",
    qcScore: null,
    reviewed: false,
    cost: 0,
    versions: [],
  };
  return { project: { ...project, shots: [...project.shots, shot] }, shot };
}

export function duplicateShot(project, shotId) {
  const source = project.shots.find((shot) => shot.id === shotId);
  if (!source) return { project, shot: null };
  const added = addShot(project, source.episodeId, source.sceneId);
  const copy = { ...source, id: added.shot.id, description: `${source.description}（副本）`, status: "待生成", qcScore: null, reviewed: false, cost: 0, versions: [] };
  return { project: { ...project, shots: [...project.shots, copy] }, shot: copy };
}

export function removeShot(project, shotId) {
  if (project.shots.length <= 1) return project;
  return {
    ...project,
    shots: project.shots.filter((shot) => shot.id !== shotId),
    tasks: project.tasks.filter((task) => task.shotId !== shotId),
  };
}

export function queueGeneration(project, shotId, prompt, taskId, createdAt) {
  const task = { id: taskId, shotId, type: "视频", model: "Auto", status: "Running", cost: 0.73, createdAt };
  return {
    ...updateShot(project, shotId, { prompt, status: "生成中" }),
    tasks: [task, ...project.tasks],
  };
}

export function completeGeneration(project, taskId, completedAt) {
  const task = project.tasks.find((item) => item.id === taskId);
  if (!task || task.status === "Success") return project;
  const shot = project.shots.find((item) => item.id === task.shotId);
  const wasGenerated = shot?.status === "已生成";
  const versionNumber = (shot?.versions?.length || 0) + 1;
  const next = updateShot(project, task.shotId, {
    status: "已生成",
    qcScore: shot?.qcScore || 91,
    cost: Number(((shot?.cost || 0) + task.cost).toFixed(2)),
    versions: [...(shot?.versions || []).map((version) => ({ ...version, active: false })), { id: `V${versionNumber}`, createdAt: completedAt, active: true }],
  });
  return {
    ...next,
    spent: Number((project.spent + task.cost).toFixed(2)),
    production: { ...project.production, generatedShots: project.production.generatedShots + (wasGenerated ? 0 : 1) },
    tasks: project.tasks.map((item) => item.id === taskId ? { ...item, status: "Success" } : item),
  };
}

export function cancelTask(project, taskId) {
  const task = project.tasks.find((item) => item.id === taskId);
  if (!task || task.status !== "Running") return project;
  return {
    ...updateShot(project, task.shotId, { status: "待生成" }),
    tasks: project.tasks.map((item) => item.id === taskId ? { ...item, status: "Cancelled" } : item),
  };
}

export function retryTask(project, taskId, nextTaskId, createdAt) {
  const task = project.tasks.find((item) => item.id === taskId);
  if (!task) return project;
  return queueGeneration(project, task.shotId, project.shots.find((shot) => shot.id === task.shotId)?.prompt || "", nextTaskId, createdAt);
}

export function updateStoryBible(project, field, value) {
  return { ...project, storyBible: { ...project.storyBible, [field]: value } };
}

export function addStoryRule(project, value) {
  const rule = value.trim();
  if (!rule) return project;
  return { ...project, storyBible: { ...project.storyBible, rules: [...project.storyBible.rules, rule] } };
}

export function removeStoryRule(project, index) {
  return { ...project, storyBible: { ...project.storyBible, rules: project.storyBible.rules.filter((_, itemIndex) => itemIndex !== index) } };
}

export function getProjectStats(project) {
  const running = project.tasks.filter((task) => task.status === "Running").length;
  const failed = project.tasks.filter((task) => task.status === "Failed").length;
  const pending = project.shots.filter((shot) => shot.status === "待生成").length;
  const review = project.shots.filter((shot) => shot.status === "已生成" && !shot.reviewed).length;
  return { running, failed, pending, review };
}
