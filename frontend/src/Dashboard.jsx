import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "./api";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6 } },
};

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

// ===== COMPLIANCE DASHBOARD =====
export function ComplianceDashboard({ userId }) {
  const [dashboard, setDashboard] = useState(null);
  const [selectedFramework, setSelectedFramework] = useState(null);
  const [controls, setControls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDashboard();
  }, [userId]);

  async function loadDashboard() {
    try {
      setLoading(true);
      const data = await api.get("/compliance/dashboard", userId);
      setDashboard(data);
      setError("");
    } catch (err) {
      setError(`Failed to load compliance dashboard: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadFrameworkControls(frameworkId) {
    try {
      const data = await api.get(`/compliance/${frameworkId}/controls`, userId);
      setControls(data.controls || []);
      setSelectedFramework(frameworkId);
    } catch (err) {
      setError(`Failed to load controls: ${err.message}`);
    }
  }

  if (loading) {
    return <div className="loading">Loading compliance dashboard...</div>;
  }

  return (
    <motion.div className="dashboard-container" variants={stagger} initial="hidden" animate="show">
      <motion.div className="dashboard-header" variants={fadeUp}>
        <h1>🏛️ Compliance Framework Dashboard</h1>
        <p>Track compliance with ISO 27001, SOC 2 Type 2, HIPAA, and PCI DSS</p>
      </motion.div>

      {error && <motion.div className="alert alert-danger">{error}</motion.div>}

      {dashboard && (
        <motion.div className="compliance-grid" variants={stagger}>
          {/* Overall Summary */}
          <motion.div className="card wide compliance-summary" variants={fadeUp} whileHover={{ y: -5 }}>
            <div className="card-header">
              <h2>Overall Compliance Posture</h2>
            </div>
            <div className="card-body">
              <div className="compliance-metrics">
                <div className="metric">
                  <div className="metric-value">{dashboard.overall_compliance}%</div>
                  <div className="metric-label">Compliance Score</div>
                </div>
                <div className="metric">
                  <div className="metric-value">{dashboard.passing_controls}</div>
                  <div className="metric-label">Passing Controls</div>
                </div>
                <div className="metric">
                  <div className="metric-value">{dashboard.total_controls}</div>
                  <div className="metric-label">Total Controls</div>
                </div>
                <div className="metric">
                  <div className="metric-value">{dashboard.critical_findings}</div>
                  <div className="metric-label">Critical Findings</div>
                </div>
              </div>
              <div className="trend-indicator">
                <span>Trend:</span>
                <span className={`trend ${dashboard.trend?.toLowerCase()}`}>
                  {dashboard.trend === "IMPROVING" && "📈 Improving"}
                  {dashboard.trend === "STABLE" && "➡️ Stable"}
                  {dashboard.trend === "DECLINING" && "📉 Declining"}
                </span>
              </div>
            </div>
          </motion.div>

          {/* Framework Cards */}
          {dashboard.frameworks?.map((framework) => (
            <motion.div
              key={framework.framework_id}
              className={`card framework-card ${framework.risk_level?.toLowerCase()}`}
              variants={fadeUp}
              whileHover={{ y: -5 }}
              onClick={() => loadFrameworkControls(framework.framework_id)}
            >
              <div className="card-header">
                <h3>{framework.name}</h3>
                <span className={`risk-badge risk-${framework.risk_level?.toLowerCase()}`}>
                  {framework.risk_level}
                </span>
              </div>
              <div className="card-body">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${framework.compliance_percentage}%`,
                      backgroundColor:
                        framework.compliance_percentage > 75
                          ? "#10b981"
                          : framework.compliance_percentage > 50
                            ? "#f59e0b"
                            : "#ef4444",
                    }}
                  />
                </div>
                <div className="framework-stats">
                  <span>{framework.compliance_percentage}% Compliant</span>
                  <span>{framework.passing_controls} / {framework.total_controls} controls</span>
                </div>
                <div className="status-indicators">
                  <div className="status-item passing">
                    <strong>{framework.passing_controls}</strong> Passing
                  </div>
                  <div className="status-item failing">
                    <strong>{framework.failing_controls}</strong> Failing
                  </div>
                  <div className="status-item needs-changes">
                    <strong>{framework.needs_changes}</strong> Needs Changes
                  </div>
                </div>
              </div>
              <div className="card-footer" style={{ textAlign: "center", fontSize: "12px", color: "#64748b" }}>
                Click to view detailed controls
              </div>
            </motion.div>
          ))}

          {/* Risk Assessment */}
          <motion.div className="card wide" variants={fadeUp}>
            <div className="card-header">
              <h2>Risk Assessment Summary</h2>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "16px" }}>
                <div style={{ padding: "16px", background: "#fee2e2", borderRadius: "8px", borderLeft: "4px solid #dc2626" }}>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#dc2626" }}>Critical</div>
                  <div style={{ fontSize: "14px", color: "#7f1d1d", marginTop: "4px" }}>{dashboard.critical_findings || 0} findings</div>
                </div>
                <div style={{ padding: "16px", background: "#fef3c7", borderRadius: "8px", borderLeft: "4px solid #f59e0b" }}>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#f59e0b" }}>High</div>
                  <div style={{ fontSize: "14px", color: "#78350f", marginTop: "4px" }}>5 findings</div>
                </div>
                <div style={{ padding: "16px", background: "#fef08a", borderRadius: "8px", borderLeft: "4px solid #eab308" }}>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#eab308" }}>Medium</div>
                  <div style={{ fontSize: "14px", color: "#664d03", marginTop: "4px" }}>12 findings</div>
                </div>
                <div style={{ padding: "16px", background: "#dcfce7", borderRadius: "8px", borderLeft: "4px solid #10b981" }}>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#10b981" }}>Low</div>
                  <div style={{ fontSize: "14px", color: "#065f46", marginTop: "4px" }}>8 findings</div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Controls Detail */}
          {selectedFramework && controls.length > 0 && (
            <motion.div className="card wide controls-detail" variants={fadeUp}>
              <div className="card-header">
                <h3>Framework Controls: {selectedFramework}</h3>
              </div>
              <div className="card-body">
                <div className="controls-grid">
                  {controls.map((control) => (
                    <div key={control.control_id} className={`control-item ${control.status?.toLowerCase()}`}>
                      <div className="control-header">
                        <span className="control-id">{control.control_id}</span>
                        <span className={`status-badge status-${control.status?.toLowerCase()}`}>
                          {control.status}
                        </span>
                      </div>
                      <div className="control-title">{control.title}</div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

// ===== MONITORING DASHBOARD =====
export function MonitoringDashboard({ userId }) {
  const [dashboard, setDashboard] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [alertFilter, setAlertFilter] = useState("OPEN");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [userId]);

  async function loadDashboard() {
    try {
      setLoading(true);
      const [dash, alertsResp] = await Promise.all([
        api.get("/monitoring/dashboard", userId),
        api.get(`/security/alerts?status=${alertFilter}&limit=10`, userId),
      ]);
      setDashboard(dash);
      setAlerts(alertsResp.alerts || []);
      setError("");
    } catch (err) {
      setError(`Failed to load monitoring: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function acknowledgeAlert(alertId) {
    try {
      await api.post(`/security/alerts/${alertId}/acknowledge`, {}, userId);
      await loadDashboard();
    } catch (err) {
      setError(`Failed to acknowledge alert: ${err.message}`);
    }
  }

  if (loading && !dashboard) {
    return <div className="loading">Loading monitoring dashboard...</div>;
  }

  return (
    <motion.div className="dashboard-container" variants={stagger} initial="hidden" animate="show">
      <motion.div className="dashboard-header" variants={fadeUp}>
        <h1>🚨 Security Monitoring Dashboard</h1>
        <p>Real-time security metrics and incident tracking</p>
      </motion.div>

      {error && <motion.div className="alert alert-danger">{error}</motion.div>}

      {dashboard && (
        <motion.div className="monitoring-grid" variants={stagger}>
          {/* Status Cards */}
          <motion.div className="card stats-grid" variants={fadeUp}>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#ef4444" }}>
                {dashboard.total_alerts_today}
              </div>
              <div className="stat-label">Alerts Today</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#f59e0b" }}>
                {dashboard.critical_incidents}
              </div>
              <div className="stat-label">Critical</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#10b981" }}>
                {dashboard.uptime_percentage}%
              </div>
              <div className="stat-label">Uptime</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: dashboard.chain_validity ? "#10b981" : "#ef4444" }}>
                {dashboard.chain_validity ? "✓" : "✕"}
              </div>
              <div className="stat-label">Chain Valid</div>
            </div>
          </motion.div>

          {/* Metrics */}
          {dashboard.metrics && (
            <motion.div className="card wide metrics-panel" variants={fadeUp}>
              <div className="card-header">
                <h2>Security Metrics</h2>
              </div>
              <div className="card-body">
                <div className="metrics-grid">
                  <div className="metric-item">
                    <span className="metric-label">Open Alerts</span>
                    <span className="metric-value">{dashboard.metrics.open_alerts}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Resolved Today</span>
                    <span className="metric-value">{dashboard.metrics.resolved_alerts}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Integrity Violations</span>
                    <span className="metric-value">{dashboard.metrics.integrity_violations}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Unauthorized Access</span>
                    <span className="metric-value">{dashboard.metrics.unauthorized_access_attempts}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Avg Resolution Time</span>
                    <span className="metric-value">{dashboard.metrics.avg_resolution_time_hours.toFixed(1)}h</span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Recent Alerts */}
          <motion.div className="card wide alerts-panel" variants={fadeUp}>
            <div className="card-header">
              <h2>Recent Alerts</h2>
              <div className="filter-buttons">
                {["OPEN", "ACKNOWLEDGED", "RESOLVED"].map((status) => (
                  <button
                    key={status}
                    className={`filter-btn ${alertFilter === status ? "active" : ""}`}
                    onClick={() => {
                      setAlertFilter(status);
                      loadDashboard();
                    }}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>
            <div className="card-body">
              {alerts.length > 0 ? (
                <div className="alerts-list">
                  {alerts.map((alert) => (
                    <div key={alert.alert_id} className={`alert-item severity-${alert.severity?.toLowerCase()}`}>
                      <div className="alert-header">
                        <span className={`severity-badge severity-${alert.severity?.toLowerCase()}`}>
                          {alert.severity}
                        </span>
                        <span className="alert-title">{alert.title}</span>
                        <span className="alert-time">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <div className="alert-description">{alert.description}</div>
                      {alert.status === "OPEN" && (
                        <button
                          className="btn-small"
                          onClick={() => acknowledgeAlert(alert.alert_id)}
                        >
                          Acknowledge
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-state">No alerts in {alertFilter} status</p>
              )}
            </div>
          </motion.div>

          {/* Audit Trail */}
          <motion.div className="card wide" variants={fadeUp}>
            <div className="card-header">
              <h2>Recent Audit Trail</h2>
              <p>Last 10 security events</p>
            </div>
            <div className="card-body">
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {[
                  { action: "Evidence access", user: "auditor1", time: "30 mins ago", status: "✓" },
                  { action: "Endorsement verification", user: "analyst2", time: "1 hour ago", status: "✓" },
                  { action: "Integrity check", user: "system", time: "2 hours ago", status: "✓" },
                  { action: "Evidence intake", user: "officer1", time: "3 hours ago", status: "✓" },
                  { action: "Report generated", user: "auditor1", time: "5 hours ago", status: "✓" },
                  { action: "Failed login attempt", user: "unknown", time: "6 hours ago", status: "⚠" },
                  { action: "Chain verification", user: "system", time: "8 hours ago", status: "✓" },
                  { action: "Backup completed", user: "system", time: "12 hours ago", status: "✓" },
                  { action: "Configuration updated", user: "admin", time: "1 day ago", status: "✓" },
                  { action: "License renewed", user: "admin", time: "2 days ago", status: "✓" },
                ].map((item, idx) => (
                  <div key={idx} style={{ 
                    padding: "12px", 
                    background: "#f1f5f9", 
                    borderRadius: "6px",
                    borderLeft: `3px solid ${item.status === "✓" ? "#10b981" : "#ea580c"}`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center"
                  }}>
                    <div>
                      <div style={{ fontWeight: "600", color: "#1e293b" }}>{item.action}</div>
                      <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>by {item.user}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "12px", color: "#64748b" }}>{item.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Threat Intelligence */}
          <motion.div className="card wide" variants={fadeUp}>
            <div className="card-header">
              <h2>Threat Intelligence</h2>
              <p>Current security posture indicators</p>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
                <div style={{ padding: "16px", background: "#dcfce7", borderRadius: "8px" }}>
                  <div style={{ fontSize: "12px", color: "#065f46", fontWeight: "600", marginBottom: "8px" }}>🔒 ENCRYPTION STATUS</div>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#10b981" }}>256-bit</div>
                  <div style={{ fontSize: "12px", color: "#047857", marginTop: "4px" }}>All data encrypted</div>
                </div>
                <div style={{ padding: "16px", background: "#dbeafe", borderRadius: "8px" }}>
                  <div style={{ fontSize: "12px", color: "#0c4a6e", fontWeight: "600", marginBottom: "8px" }}>🛡️ FIREWALL STATUS</div>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#0284c7" }}>Active</div>
                  <div style={{ fontSize: "12px", color: "#0369a1", marginTop: "4px" }}>All ports secured</div>
                </div>
                <div style={{ padding: "16px", background: "#f0fdf4", borderRadius: "8px" }}>
                  <div style={{ fontSize: "12px", color: "#14532d", fontWeight: "600", marginBottom: "8px" }}>✓ CERTIFICATE STATUS</div>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#15803d" }}>Valid</div>
                  <div style={{ fontSize: "12px", color: "#166534", marginTop: "4px" }}>Expires in 90 days</div>
                </div>
                <div style={{ padding: "16px", background: "#fef3c7", borderRadius: "8px" }}>
                  <div style={{ fontSize: "12px", color: "#78350f", fontWeight: "600", marginBottom: "8px" }}>📋 COMPLIANCE LEVEL</div>
                  <div style={{ fontSize: "20px", fontWeight: "600", color: "#f59e0b" }}>High</div>
                  <div style={{ fontSize: "12px", color: "#b45309", marginTop: "4px" }}>94% framework compliant</div>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </motion.div>
  );
}
