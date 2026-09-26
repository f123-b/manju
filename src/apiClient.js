const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
