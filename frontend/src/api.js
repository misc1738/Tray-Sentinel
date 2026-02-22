const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}, userId) {
  const headers = {
    ...(options.headers || {}),
  };

  if (userId) {
    headers["X-User-Id"] = userId;
  }

  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const data = JSON.parse(text);
      detail = data?.detail || text;
    } catch {
      detail = text;
    }
    throw new Error(`${response.status} ${detail}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response;
}

export const api = {
  health: () => request("/health"),
  users: () => request("/auth/users"),
  intake: (payload, userId) => request("/evidence/intake", { method: "POST", body: JSON.stringify(payload) }, userId),
  createEvent: (payload, userId) => request("/evidence/event", { method: "POST", body: JSON.stringify(payload) }, userId),
  endorse: (payload, userId) => request("/evidence/endorse", { method: "POST", body: JSON.stringify(payload) }, userId),
  verify: (evidenceId, userId) => request(`/evidence/${evidenceId}/verify`, { method: "POST" }, userId),
  timeline: (evidenceId, userId) => request(`/evidence/${evidenceId}/timeline`, {}, userId),
  report: (evidenceId, userId) => request(`/evidence/${evidenceId}/report`, {}, userId),
  qrUrl: (evidenceId) => `${API_BASE}/evidence/${evidenceId}/qr`,
  bundle: async (evidenceId, userId) => {
    const response = await request(`/evidence/${evidenceId}/bundle`, {}, userId);
    return response.blob();
  },
  caseSummary: (caseId, userId) => request(`/case/${caseId}`, {}, userId),
  caseAudit: (caseId, userId) => request(`/case/${caseId}/audit`, {}, userId),
};
