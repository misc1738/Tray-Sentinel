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
  // Core operations
  health: () => request("/health"),
  users: () => request("/auth/users"),
  securityPosture: (userId) => request("/security/posture", {}, userId),

  // Evidence operations
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

  // Case operations
  caseSummary: (caseId, userId) => request(`/case/${caseId}`, {}, userId),
  caseAudit: (caseId, userId) => request(`/case/${caseId}/audit`, {}, userId),

  // Compliance endpoints
  complianceDashboard: (userId) => request("/compliance/dashboard", {}, userId),
  frameworks: (userId) => request("/compliance/frameworks", {}, userId),
  frameworkControls: (frameworkId, userId) => request(`/compliance/${frameworkId}/controls`, {}, userId),
  frameworkStatus: (frameworkId, userId) => request(`/compliance/${frameworkId}/status`, {}, userId),

  // Monitoring & Security endpoints
  monitoringDashboard: (userId) => request("/monitoring/dashboard", {}, userId),
  securityAlerts: (userId, status, severity, limit) => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (severity) params.append("severity", severity);
    if (limit) params.append("limit", limit);
    const query = params.toString();
    return request(`/security/alerts${query ? "?" + query : ""}`, {}, userId);
  },
  acknowledgeAlert: (alertId, userId) => request(`/security/alerts/${alertId}/acknowledge`, { method: "POST" }, userId),
  resolveAlert: (alertId, userId, markFalsePositive) => request(`/security/alerts/${alertId}/resolve?mark_false_positive=${markFalsePositive}`, { method: "POST" }, userId),
  securityMetrics: (userId) => request("/security/metrics", {}, userId),
  securityPostureAssessment: (userId) => request("/security/posture-assessment", {}, userId),
  auditLogs: (userId, userId_filter, limit) => {
    const params = new URLSearchParams();
    if (userId_filter) params.append("user_id", userId_filter);
    if (limit) params.append("limit", limit);
    const query = params.toString();
    return request(`/security/audit-logs${query ? "?" + query : ""}`, {}, userId);
  },

  // Generic GET helper for flexibility
  get: (path, userId) => request(path, {}, userId),
  post: (path, payload, userId) => request(path, { method: "POST", body: JSON.stringify(payload) }, userId),
};

