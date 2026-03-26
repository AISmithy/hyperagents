const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.detail ?? (await response.text());
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export function fetchState() {
  return request("/state");
}

export function resetState(mode = "hyperagent") {
  return request("/reset", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export function fetchMetricsCsv() {
  const base = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";
  return fetch(`${base}/metrics/csv`).then((r) => {
    if (!r.ok) throw new Error(`Export failed with status ${r.status}`);
    return r.text();
  });
}

export function runIterations(iterations) {
  return request("/run", {
    method: "POST",
    body: JSON.stringify({ iterations }),
  });
}

export function reviewRepository(repoUrl) {
  return request("/review-repo", {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

export function fetchRuns() {
  return request("/runs");
}

export function loadRun(runId) {
  return request(`/runs/${runId}/load`, { method: "POST" });
}

export function deleteRun(runId) {
  return request(`/runs/${runId}`, { method: "DELETE" });
}

// ── Account management ────────────────────────────────────────────────────────

export function fetchAccounts() {
  return request("/accounts");
}

export function addAccount(name, platform, profile, nRepos) {
  return request("/accounts", {
    method: "POST",
    body: JSON.stringify({ name, platform, profile, n_repos: nRepos }),
  });
}

export function fetchAccountRepos(accountId) {
  return request(`/accounts/${accountId}/repos`);
}

export function deleteAccount(accountId) {
  return request(`/accounts/${accountId}`, { method: "DELETE" });
}

export function applyAllAccounts() {
  return request("/accounts/apply-all", { method: "POST" });
}
