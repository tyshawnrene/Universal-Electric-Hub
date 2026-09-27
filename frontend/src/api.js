// Production is served by Flask, so API requests must stay on the public
// origin. During development, Vite proxies /api to the backend.
const API_BASE = import.meta.env.PROD ? "" : (import.meta.env.VITE_API_URL ?? "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (error) {
    throw new Error(`Unable to reach the API at ${API_BASE || window.location.origin}. ${error.message}`);
  }
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
