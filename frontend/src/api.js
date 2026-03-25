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

export function resetState() {
  return request("/reset", { method: "POST" });
}

export function runIterations(iterations) {
  return request("/run", {
    method: "POST",
    body: JSON.stringify({ iterations }),
  });
}

export function reviewSubmission(payload) {
  return request("/review", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
