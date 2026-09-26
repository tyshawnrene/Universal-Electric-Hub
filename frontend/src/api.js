// All data goes through the Flask backend. URLs are relative: in dev, Vite proxies
// /api to Flask (see vite.config.js); in production, Flask serves this app itself.
// Set VITE_API_URL only if the backend is hosted somewhere else.
const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.message || `Request failed (${response.status})`);
  }
  return data;
}

export function fetchProjects() {
  return request("/api/projects");
}

export function fetchOverlaps({ maxKm = 40, crossUtilityOnly = false } = {}) {
  return request(`/api/analysis/overlaps?max_km=${maxKm}&cross_utility_only=${crossUtilityOnly}`);
}

export function runCoordinationReport(projectIds) {
  return request("/api/analysis/report", {
    method: "POST",
    body: JSON.stringify({ project_ids: projectIds }),
  });
}
