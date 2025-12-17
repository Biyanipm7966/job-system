const API_BASE = "http://localhost:8003";

export async function createJob(type, payload, max_retries = 3) {
  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, payload, max_retries }),
  });
  if (!res.ok) throw new Error("Failed to create job");
  return res.json();
}

export async function listJobs(limit = 50) {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to list jobs");
  return res.json();
}

export function wsUrl() {
  return "ws://localhost:8003/ws";
}
