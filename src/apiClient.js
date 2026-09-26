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

export function patchRemoteScene(sceneId, patch) {
  return request(`/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(patch) });
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
