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
  return request("/project");
}

export function saveRemoteProject(project) {
  return request("/project", {
    method: "PUT",
    body: JSON.stringify(project),
  });
}

export function generateRemoteShot({ shotId, prompt }) {
  return request("/generations", {
    method: "POST",
    body: JSON.stringify({ shot_id: shotId, prompt }),
  });
}

export function getRemoteHealth() {
  return request("/health");
}
