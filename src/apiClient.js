const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (typeof FormData !== "undefined" && options.body instanceof FormData) delete headers["Content-Type"];
  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    const error = new Error(message || `API ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export function getRemoteProject() {
  return request("/projects/P001");
}

export function listRemoteTasks({ status, targetType, limit } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (targetType) params.set("targetType", targetType);
  if (limit) params.set("limit", String(limit));
  const query = params.toString();
  return request(`/projects/P001/tasks${query ? `?${query}` : ""}`).then((response) => response.items || []);
}

export function getRemoteCanvas() {
  return request("/projects/P001/canvas");
}

export function createRemoteCanvasNode(payload) {
  return request("/projects/P001/canvas/nodes", { method: "POST", body: JSON.stringify(payload) }).then((response) => response.node);
}

export function patchRemoteCanvasNode(nodeId, payload) {
  return request(`/canvas-nodes/${nodeId}`, { method: "PATCH", body: JSON.stringify(payload) }).then((response) => response.node);
}

export function deleteRemoteCanvasNode(nodeId) {
  return request(`/canvas-nodes/${nodeId}`, { method: "DELETE" });
}

export function createRemoteCanvasEdge(payload) {
  return request("/projects/P001/canvas/edges", { method: "POST", body: JSON.stringify(payload) }).then((response) => response.edge);
}

export function deleteRemoteCanvasEdge(edgeId) {
  return request(`/canvas-edges/${edgeId}`, { method: "DELETE" });
}

export function runRemoteCanvasNode(nodeId, payload = {}) {
  return request(`/canvas-nodes/${nodeId}/run`, { method: "POST", body: JSON.stringify(payload) });
}

export function listRemoteRunningHubWorkflows() {
  return request("/projects/P001/runninghub/workflows").then((response) => response.items || []);
}

export function createRemoteRunningHubWorkflow(payload) {
  return request("/projects/P001/runninghub/workflows", { method: "POST", body: JSON.stringify(payload) }).then((response) => response.workflow);
}

export function patchRemoteRunningHubWorkflow(workflowId, payload) {
  return request(`/runninghub/workflows/${workflowId}`, { method: "PATCH", body: JSON.stringify(payload) }).then((response) => response.workflow);
}

export function deleteRemoteRunningHubWorkflow(workflowId) {
  return request(`/runninghub/workflows/${workflowId}`, { method: "DELETE" });
}

export function runRemoteRunningHubWorkflow(workflowId, payload = {}) {
  return request(`/runninghub/workflows/${workflowId}/run`, { method: "POST", body: JSON.stringify(payload) });
}

export function uploadRemoteRunningHubFile(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/runninghub/upload", { method: "POST", body });
}

export function saveRemoteProject(project) {
  return request("/project", {
    method: "PUT",
    body: JSON.stringify(project),
  });
}

export function generateRemoteShot({ shotId, prompt }) {
  return request(`/shots/${shotId}/generate`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export function getRemoteHealth() {
  return request("/health");
}

export function getRemoteProviderSettings() {
  return request("/settings/providers").then((response) => response.settings || {});
}

export function saveRemoteProviderSettings(payload) {
  return request("/settings/providers", { method: "PATCH", body: JSON.stringify(payload) }).then((response) => response.settings || {});
}

export function testRemoteProviderSettings(payload = {}) {
  return request("/settings/providers/test", { method: "POST", body: JSON.stringify(payload) });
}

export function discoverRemoteModels(payload = {}) {
  return request("/settings/providers/discover-models", { method: "POST", body: JSON.stringify(payload) });
}

export function startRemoteAgentRun(payload) {
  return request("/agent/runs", { method: "POST", body: JSON.stringify(payload) }).then((response) => response.run);
}

export function getRemoteAgentRun(runId) {
  return request(`/agent/runs/${runId}`).then((response) => response.run);
}

export function listRemoteAgentRuns(episodeId) {
  const query = episodeId ? `?episodeId=${encodeURIComponent(episodeId)}` : "";
  return request(`/projects/P001/agent/runs${query}`).then((response) => response.items || []);
}

export function resumeRemoteAgentRun(runId) {
  return request(`/agent/runs/${runId}/resume`, { method: "POST" }).then((response) => response.run);
}

export function cancelRemoteAgentRun(runId) {
  return request(`/agent/runs/${runId}/cancel`, { method: "POST" }).then((response) => response.run);
}

export function runRemoteShotQC(shotId) {
  return request(`/shots/${shotId}/qc`, { method: "POST" }).then((response) => response.result);
}

export function runRemoteProjectQC() {
  return request("/projects/P001/qc", { method: "POST" }).then((response) => response.result);
}

export function runRemoteContinuityCheck() {
  return request("/projects/P001/continuity-check", { method: "POST" }).then((response) => response.result);
}

export function patchRemoteProject(patch) {
  return request("/projects/P001", { method: "PATCH", body: JSON.stringify(patch) });
}

export function patchRemoteStoryBible(patch) {
  return request("/projects/P001/story-bible", { method: "PATCH", body: JSON.stringify(patch) });
}

export function patchRemoteShot(shotId, patch) {
  return request(`/shots/${shotId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function createRemoteShot(sceneId, shot) {
  return request(`/scenes/${sceneId}/shots`, { method: "POST", body: JSON.stringify(shot) });
}

export function deleteRemoteShot(shotId) {
  return request(`/shots/${shotId}`, { method: "DELETE" });
}

export function patchRemoteAsset(assetId, patch) {
  return request(`/assets/${assetId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function createRemoteAsset(type, asset) {
  return request(`/projects/P001/${type}`, { method: "POST", body: JSON.stringify(asset) });
}

export function generateRemoteAsset(assetType, payload = {}) {
  return request("/projects/P001/assets/generate", {
    method: "POST",
    body: JSON.stringify({ ...payload, assetType }),
  });
}

export function listRemoteCharacters() {
  return request("/projects/P001/characters").then((response) => response.items || []);
}

export function createRemoteCharacter(payload) {
  return request("/projects/P001/characters", { method: "POST", body: JSON.stringify(payload) });
}

export function patchRemoteCharacter(characterId, patch) {
  return request(`/characters/${characterId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function extractRemoteAnchors(characterId, payload = {}) {
  return request(`/characters/${characterId}/extract-anchors`, { method: "POST", body: JSON.stringify(payload) });
}

export function generateRemoteCandidates(characterId, payload = {}) {
  return request(`/characters/${characterId}/generate-candidates`, { method: "POST", body: JSON.stringify(payload) });
}

export function generateRemoteMasterSheet(characterId, payload = {}) {
  return request(`/characters/${characterId}/generate-master-sheet`, { method: "POST", body: JSON.stringify(payload) });
}

export function setRemoteCanonical(characterId, referenceId) {
  return request(`/characters/${characterId}/canonical`, { method: "POST", body: JSON.stringify({ referenceId }) });
}

export function lockRemoteCharacter(characterId) {
  return request(`/characters/${characterId}/lock`, { method: "POST" });
}

export function unlockRemoteCharacter(characterId) {
  return request(`/characters/${characterId}/unlock`, { method: "POST" });
}

export function getRemoteCharacterLooks(characterId) {
  return request(`/characters/${characterId}/looks`).then((response) => response.items || []);
}

export function createRemoteCharacterLook(characterId, payload) {
  return request(`/characters/${characterId}/looks`, { method: "POST", body: JSON.stringify(payload) });
}

export function patchRemoteCharacterLook(lookId, patch) {
  return request(`/character-looks/${lookId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function getRemoteCharacterReferences(characterId) {
  return request(`/characters/${characterId}/references`).then((response) => response.items || []);
}

export function approveRemoteReference(referenceId) {
  return request(`/character-references/${referenceId}/approve`, { method: "POST" });
}

export function rejectRemoteReference(referenceId) {
  return request(`/character-references/${referenceId}/reject`, { method: "POST" });
}

export function getRemoteShotCharacters(shotId) {
  return request(`/shots/${shotId}/characters`).then((response) => response.items || []);
}

export function putRemoteShotCharacters(shotId, items) {
  return request(`/shots/${shotId}/characters`, { method: "PUT", body: JSON.stringify({ items }) });
}

export function patchRemoteScene(sceneId, patch) {
  return request(`/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function getRemoteScenes(episodeId) {
  return request(`/episodes/${episodeId}/scenes`).then((response) => response.items || []);
}

export function createRemoteScene(episodeId, scene) {
  return request(`/episodes/${episodeId}/scenes`, { method: "POST", body: JSON.stringify(scene) });
}

export function patchRemoteEpisode(episodeId, patch) {
  return request(`/episodes/${episodeId}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function generateRemoteMatrix(episodeId, payload = {}) {
  return request(`/episodes/${episodeId}/matrix`, { method: "POST", body: JSON.stringify(payload) });
}

export function generateRemoteSceneScript(sceneId, payload = {}) {
  return request(`/scenes/${sceneId}/script`, { method: "POST", body: JSON.stringify(payload) });
}

export function generateRemoteBreakdown(sceneId, payload = {}) {
  return request(`/scenes/${sceneId}/breakdown`, { method: "POST", body: JSON.stringify(payload) });
}

export function cancelRemoteTask(taskId) {
  return request(`/generation-tasks/${taskId}/cancel`, { method: "POST" });
}

export function retryRemoteTask(taskId) {
  return request(`/generation-tasks/${taskId}/retry`, { method: "POST" });
}

export function getRemoteTask(taskId) {
  return request(`/generation-tasks/${taskId}`);
}

export function exportRemoteProject() {
  return fetch(`${API_BASE}/projects/P001/export`, { method: "POST" }).then(async (response) => {
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.blob();
  });
}

export function getRemoteVoiceProfiles(characterId) {
  return request(`/characters/${characterId}/voice-profiles`).then((response) => response.items || []);
}

export function createRemoteVoiceProfile(characterId, payload) {
  return request(`/characters/${characterId}/voice-profiles`, { method: "POST", body: JSON.stringify(payload) }).then((response) => response.profile);
}

export function patchRemoteVoiceProfile(profileId, patch) {
  return request(`/voice-profiles/${profileId}`, { method: "PATCH", body: JSON.stringify(patch) }).then((response) => response.profile);
}

export function lockRemoteVoiceProfile(profileId) {
  return request(`/voice-profiles/${profileId}/lock`, { method: "POST" }).then((response) => response.profile);
}

export function unlockRemoteVoiceProfile(profileId) {
  return request(`/voice-profiles/${profileId}/unlock`, { method: "POST" }).then((response) => response.profile);
}

export function extractRemoteDialogueLines(sceneId) {
  return request(`/scenes/${sceneId}/dialogue-lines/extract`).then((response) => response.items || []);
}

export function getRemoteDialogueLines(sceneId) {
  return request(`/scenes/${sceneId}/dialogue-lines`).then((response) => response.items || []);
}

export function patchRemoteDialogueLine(lineId, patch) {
  return request(`/dialogue-lines/${lineId}`, { method: "PATCH", body: JSON.stringify(patch) }).then((response) => response.line);
}

export function directRemotePerformance(lineId, payload = {}) {
  return request(`/dialogue-lines/${lineId}/direct-performance`, { method: "POST", body: JSON.stringify(payload) }).then((response) => response.performance);
}

export function generateRemoteDialogueLine(lineId, payload = {}) {
  return request(`/dialogue-lines/${lineId}/generate`, { method: "POST", body: JSON.stringify(payload) });
}

export function generateRemoteEpisodeDialogue(episodeId, payload = {}) {
  return request(`/episodes/${episodeId}/generate-dialogue`, { method: "POST", body: JSON.stringify(payload) });
}

export function runRemoteTakeQC(takeId) {
  return request(`/voice-takes/${takeId}/run-qc`, { method: "POST" });
}

export function activateRemoteTake(takeId) {
  return request(`/voice-takes/${takeId}/activate`, { method: "POST" }).then((response) => response.take);
}

export function createRemoteAudioClip(payload) {
  return request("/projects/P001/audio-clips", { method: "POST", body: JSON.stringify(payload) }).then((response) => response.clip);
}

export function patchRemoteAudioClip(clipId, payload) {
  return request(`/audio-clips/${clipId}`, { method: "PATCH", body: JSON.stringify(payload) }).then((response) => response.clip);
}

export function deleteRemoteAudioClip(clipId) {
  return request(`/audio-clips/${clipId}`, { method: "DELETE" });
}

export function createRemoteVideoClip(payload) {
  return request("/projects/P001/video-clips", { method: "POST", body: JSON.stringify(payload) }).then((response) => response.clip);
}

export function patchRemoteVideoClip(clipId, payload) {
  return request(`/video-clips/${clipId}`, { method: "PATCH", body: JSON.stringify(payload) }).then((response) => response.clip);
}

export function deleteRemoteVideoClip(clipId) {
  return request(`/video-clips/${clipId}`, { method: "DELETE" });
}

export function mixdownRemoteEpisode(episodeId) {
  return request(`/episodes/${episodeId}/mixdown`, { method: "POST", body: JSON.stringify({}) }).then((response) => response.mixdown);
}

export function renderRemoteEpisode(episodeId, payload = {}) {
  return request(`/episodes/${episodeId}/render`, { method: "POST", body: JSON.stringify(payload) }).then((response) => response.render);
}
