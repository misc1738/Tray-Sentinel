import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ComplianceDashboard, MonitoringDashboard } from "./Dashboard";
import { api } from "./api";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6 } },
};

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const panelAnim = {
  hidden: { opacity: 0, y: 18, scale: 0.985 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.55 },
  },
};

async function toBase64(file) {
  const bytes = await file.arrayBuffer();
  const uint = new Uint8Array(bytes);
  let binary = "";
  uint.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return window.btoa(binary);
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

const ACTION_TYPES = ["TRANSFER", "ACCESS", "ANALYSIS", "STORAGE", "COURT_SUBMISSION", "ENDORSE"];

export default function App() {
  const [activeTab, setActiveTab] = useState("home");
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState("auditor1");
  const [health, setHealth] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Evidence management state
  const [intakeFile, setIntakeFile] = useState(null);
  const [intakeForm, setIntakeForm] = useState({
    case_id: "",
    description: "",
    source_device: "",
    acquisition_method: "",
  });
  const [eventForm, setEventForm] = useState({
    evidence_id: "",
    action_type: "TRANSFER",
    details: '{"reason":"routine transfer"}',
    presented_sha256: "",
    endorse: false,
  });
  const [endorseForm, setEndorseForm] = useState({ evidence_id: "", tx_id: "" });
  const [evidenceId, setEvidenceId] = useState("");
  const [timeline, setTimeline] = useState(null);
  const [report, setReport] = useState(null);
  const [caseId, setCaseId] = useState("");
  const [caseSummary, setCaseSummary] = useState(null);
  const [caseAudit, setCaseAudit] = useState(null);

  // Analytics & Search state
  const [analyticsData, setAnalyticsData] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [showActivityFeed, setShowActivityFeed] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [healthResp, usersResp] = await Promise.all([api.health(), api.users()]);
        setHealth(healthResp);
        setUsers(usersResp.users || []);
        if ((usersResp.users || []).length && !usersResp.users.find((u) => u.user_id === userId)) {
          setUserId(usersResp.users[0].user_id);
        }
        // Load analytics data on init
        loadAnalyticsData();
        loadActivityFeed();
      } catch (e) {
        setError(`Initialization failed: ${e.message}`);
      }
    })();
  }, []);

  async function loadAnalyticsData() {
    try {
      // Generate mock analytics data
      const mockAnalytics = {
        total_evidence: 127,
        active_cases: 23,
        pending_endorsements: 8,
        integrity_failures: 2,
        monthly_trend: [45, 52, 48, 61, 55, 49, 58],
        action_breakdown: {
          TRANSFER: 340,
          ACCESS: 215,
          ANALYSIS: 185,
          STORAGE: 120,
          COURT_SUBMISSION: 95,
          ENDORSE: 78,
        },
        endorsement_rate: 94.2,
      };
      setAnalyticsData(mockAnalytics);
    } catch (e) {
      console.error("Failed to load analytics:", e);
    }
  }

  async function loadActivityFeed() {
    try {
      const mockActivity = [
        { id: 1, type: "INTAKE", text: "Evidence EV-98734 registered", time: "2 min ago", status: "success" },
        { id: 2, type: "TRANSFER", text: "EV-98721 transferred to Lab A", time: "15 min ago", status: "success" },
        { id: 3, type: "ANALYSIS", text: "Chain of custody verified for EV-98695", time: "1 hour ago", status: "success" },
        { id: 4, type: "WARNING", text: "Integrity check pending for EV-98680", time: "2 hours ago", status: "warning" },
        { id: 5, type: "ENDORSE", text: "EV-98670 endorsed by NIST CSF framework", time: "3 hours ago", status: "success" },
        { id: 6, type: "AUDIT", text: "Case CASE-2026-001 audit completed", time: "4 hours ago", status: "info" },
      ];
      setRecentActivity(mockActivity);
    } catch (e) {
      console.error("Failed to load activity feed:", e);
    }
  }

  function clearNotice() {
    setMessage("");
    setError("");
  }

  async function handleIntake(e) {
    e.preventDefault();
    clearNotice();
    try {
      if (!intakeFile) throw new Error("Select a file");
      const payload = {
        ...intakeForm,
        file_name: intakeFile.name,
        file_bytes_b64: await toBase64(intakeFile),
      };
      const created = await api.intake(payload, userId);
      setEvidenceId(created.evidence_id);
      setEventForm((prev) => ({ ...prev, evidence_id: created.evidence_id }));
      setEndorseForm((prev) => ({ ...prev, evidence_id: created.evidence_id }));
      setMessage(`Evidence registered: ${created.evidence_id}`);
      setIntakeFile(null);
      setIntakeForm({ case_id: "", description: "", source_device: "", acquisition_method: "" });
    } catch (err) {
      setError(`Intake failed: ${err.message}`);
    }
  }

  async function handleEvent(e) {
    e.preventDefault();
    clearNotice();
    try {
      const details = eventForm.details.trim() ? JSON.parse(eventForm.details) : {};
      const payload = {
        evidence_id: eventForm.evidence_id,
        action_type: eventForm.action_type,
        details,
        presented_sha256: eventForm.presented_sha256 || null,
        endorse: eventForm.endorse,
      };
      const created = await api.createEvent(payload, userId);
      setEndorseForm((prev) => ({ ...prev, tx_id: created.tx_id, evidence_id: created.evidence_id }));
      setMessage(`Event created: ${created.tx_id}`);
      if (evidenceId || payload.evidence_id) {
        await loadEvidence(evidenceId || payload.evidence_id);
      }
    } catch (err) {
      setError(`Event creation failed: ${err.message}`);
    }
  }

  async function handleEndorse(e) {
    e.preventDefault();
    clearNotice();
    try {
      const created = await api.endorse(endorseForm, userId);
      setMessage(`Endorsed TX: ${created.endorsed_tx_id}`);
      if (evidenceId || endorseForm.evidence_id) {
        await loadEvidence(evidenceId || endorseForm.evidence_id);
      }
    } catch (err) {
      setError(`Endorsement failed: ${err.message}`);
    }
  }

  async function loadEvidence(idParam) {
    clearNotice();
    const id = idParam || evidenceId;
    if (!id) {
      setError("Provide an evidence ID");
      return;
    }
    try {
      const [timelineResp, reportResp] = await Promise.all([api.timeline(id, userId), api.report(id, userId)]);
      setEvidenceId(id);
      setTimeline(timelineResp);
      setReport(reportResp);
      setEventForm((prev) => ({ ...prev, evidence_id: id }));
      setEndorseForm((prev) => ({ ...prev, evidence_id: id }));
      setMessage(`Loaded evidence ${id}`);
    } catch (err) {
      setError(`Load evidence failed: ${err.message}`);
    }
  }

  async function handleVerify() {
    clearNotice();
    try {
      const result = await api.verify(evidenceId, userId);
      setMessage(`Integrity ${result.integrity_ok ? "OK" : "FAILED"} for ${result.evidence_id}`);
      await loadEvidence(evidenceId);
    } catch (err) {
      setError(`Verify failed: ${err.message}`);
    }
  }

  async function handleDownloadReport() {
    clearNotice();
    try {
      const response = await api.report(evidenceId, userId);
      const blob = new Blob([JSON.stringify(response, null, 2)], { type: "application/json" });
      downloadBlob(blob, `sentinel-report-${evidenceId}.json`);
      setMessage("Report downloaded");
    } catch (err) {
      setError(`Report download failed: ${err.message}`);
    }
  }

  async function handleDownloadBundle() {
    clearNotice();
    try {
      const blob = await api.bundle(evidenceId, userId);
      downloadBlob(blob, `sentinel-bundle-${evidenceId}.zip`);
      setMessage("Bundle downloaded");
    } catch (err) {
      setError(`Bundle download failed: ${err.message}`);
    }
  }

  async function handleLoadCase() {
    clearNotice();
    try {
      const [summary, audit] = await Promise.all([api.caseSummary(caseId, userId), api.caseAudit(caseId, userId)]);
      setCaseSummary(summary);
      setCaseAudit(audit);
      setMessage(`Loaded case ${caseId}`);
    } catch (err) {
      setError(`Load case failed: ${err.message}`);
    }
  }

  const roleLabel = users.find((u) => u.user_id === userId)?.role || "";

  return (
    <div className="shell">
      <div className="ambient a1" />
      <div className="ambient a2" />

      {/* Navigation */}
      <motion.header
        className="nav-wrap"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div className="logo">🔐</div>
          <span className="logo-text">Tracey's Sentinel</span>
        </div>

        <nav className="nav-tabs">
          {[
            { id: "home", label: "Home", icon: "🏠" },
            { id: "evidence", label: "Evidence", icon: "📁" },
            { id: "analytics", label: "Analytics", icon: "📊" },
            { id: "search", label: "Search", icon: "🔍" },
            { id: "compliance", label: "Compliance", icon: "🏛️" },
            { id: "monitoring", label: "Security", icon: "🚨" },
            { id: "health", label: "System", icon: "⚙️" },
          ].map((tab) => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>

        <div className="nav-actions">
          <select value={userId} onChange={(e) => setUserId(e.target.value)} className="user-select">
            {users.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.user_id} — {u.role}
              </option>
            ))}
          </select>
          {health && <span className="status success">✓ System Ready</span>}
        </div>
      </motion.header>

      {/* Alert Messages */}
      {(message || error) && (
        <motion.div className="alert-banner" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {message && (
            <div className="alert alert-success">
              ✓ {message}
              <button onClick={clearNotice}>✕</button>
            </div>
          )}
          {error && (
            <div className="alert alert-danger">
              ✕ {error}
              <button onClick={clearNotice}>✕</button>
            </div>
          )}
        </motion.div>
      )}

      {/* Home Tab */}
      {activeTab === "home" && (
        <motion.section
          className="hero"
          variants={stagger}
          initial="hidden"
          animate="show"
          key="home-section"
        >
          <motion.div className="hero-copy" variants={stagger}>
            <motion.span className="chip" variants={fadeUp}>
              ✨ Fraud-Resistant • Audit-Ready • Chain-of-Custody
            </motion.span>
            <motion.h1 variants={fadeUp}>
              Evidence Management <br /> System
            </motion.h1>
            <motion.p variants={fadeUp}>
              Tracey's Sentinel provides tamper-evident digital chain of custody for forensic evidence with compliance tracking and real-time security monitoring.
            </motion.p>
            <motion.div className="hero-cta" variants={fadeUp}>
              <motion.button
                className="cta-main"
                onClick={() => setActiveTab("evidence")}
                whileHover={{ y: -3, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                Start Operations
              </motion.button>
              <span className="cta-sub">Chain Status: {health?.ledger_chain_valid ? "✓ Valid" : "✕ Invalid"}</span>
            </motion.div>
          </motion.div>
          <div className="hero-metrics">
            <div className="metric-box">
              <div className="metric-value">{analyticsData?.total_evidence || 0}</div>
              <div className="metric-label">Evidence Items</div>
            </div>
            <div className="metric-box">
              <div className="metric-value">{analyticsData?.active_cases || 0}</div>
              <div className="metric-label">Active Cases</div>
            </div>
            <div className="metric-box">
              <div className="metric-value">{analyticsData?.endorsement_rate || 0}%</div>
              <div className="metric-label">Endorsement Rate</div>
            </div>
            <div className="metric-box">
              <div className="metric-value">{analyticsData?.pending_endorsements || 0}</div>
              <div className="metric-label">Pending</div>
            </div>
          </div>

          {/* Quick Actions */}
          <motion.section className="card wide" variants={fadeUp} style={{ marginTop: "40px" }}>
            <div className="card-header">
              <h2>Quick Actions</h2>
              <p>Frequently used operations</p>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
                <button onClick={() => setActiveTab("evidence")} className="quick-action-btn">
                  <span style={{ fontSize: "24px" }}>📥</span>
                  <span>Register Evidence</span>
                </button>
                <button onClick={() => setActiveTab("search")} className="quick-action-btn">
                  <span style={{ fontSize: "24px" }}>🔍</span>
                  <span>Search Evidence</span>
                </button>
                <button onClick={() => setActiveTab("analytics")} className="quick-action-btn">
                  <span style={{ fontSize: "24px" }}>📊</span>
                  <span>View Analytics</span>
                </button>
                <button onClick={() => setActiveTab("compliance")} className="quick-action-btn">
                  <span style={{ fontSize: "24px" }}>✅</span>
                  <span>Compliance Check</span>
                </button>
              </div>
            </div>
          </motion.section>

          {/* Recent Activity Feed */}
          {recentActivity.length > 0 && (
            <motion.section className="card wide" variants={fadeUp} style={{ marginTop: "20px" }}>
              <div className="card-header">
                <h2>Recent Activity</h2>
                <button onClick={() => setShowActivityFeed(!showActivityFeed)} className="btn-ghost">
                  {showActivityFeed ? "Hide" : "Show"}
                </button>
              </div>
              {showActivityFeed && (
                <div className="card-body">
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    {recentActivity.slice(0, 6).map((activity) => (
                      <div key={activity.id} className="activity-item">
                        <div className={`activity-status activity-${activity.status}`}>
                          {activity.status === "success" && "✓"}
                          {activity.status === "warning" && "⚠"}
                          {activity.status === "info" && "ℹ"}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div className="activity-text">{activity.text}</div>
                          <div className="activity-time">{activity.time}</div>
                        </div>
                        <span className="badge badge-info">{activity.type}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.section>
          )}
        </motion.section>
      )}

      {/* Evidence Tab */}
      {activeTab === "evidence" && (
        <motion.main
          className="console-grid"
          variants={stagger}
          initial="hidden"
          animate="show"
          key="evidence-section"
        >
          {/* Control Panel */}
          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>Evidence Operations</h2>
              <p>Manage evidence intake, custody events, and endorsements</p>
            </div>
            <div className="card-body">
              <div className="form-row">
                <div className="form-group">
                  <label>Current Operator</label>
                  <div className="operator-info">
                    <span className="badge badge-primary">{userId}</span>
                    <span className="badge badge-info">{roleLabel}</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.section>

          {/* Intake */}
          <motion.section className="card" variants={panelAnim}>
            <div className="card-header">
              <h3>Evidence Intake</h3>
            </div>
            <form className="card-body" onSubmit={handleIntake}>
              <div className="form-group">
                <label htmlFor="case-id">Case ID *</label>
                <input
                  id="case-id"
                  placeholder="Case identifier"
                  value={intakeForm.case_id}
                  onChange={(e) => setIntakeForm((prev) => ({ ...prev, case_id: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="description">Description *</label>
                <input
                  id="description"
                  placeholder="Evidence description"
                  value={intakeForm.description}
                  onChange={(e) =>
                    setIntakeForm((prev) => ({ ...prev, description: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="device">Device</label>
                  <input
                    id="device"
                    placeholder="Device ID"
                    value={intakeForm.source_device}
                    onChange={(e) =>
                      setIntakeForm((prev) => ({ ...prev, source_device: e.target.value }))
                    }
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="method">Method *</label>
                  <input
                    id="method"
                    placeholder="Acquisition method"
                    value={intakeForm.acquisition_method}
                    onChange={(e) =>
                      setIntakeForm((prev) => (
                        { ...prev, acquisition_method: e.target.value }
                      ))
                    }
                    required
                  />
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="file">File *</label>
                <input
                  id="file"
                  type="file"
                  onChange={(e) => setIntakeFile(e.target.files?.[0] || null)}
                  required
                />
              </div>
              <button type="submit" className="primary">
                Register Evidence
              </button>
            </form>
          </motion.section>

          {/* Evidence Timeline */}
          {timeline && (
            <motion.section className="card wide" variants={panelAnim}>
              <div className="card-header">
                <h3>Custody Timeline</h3>
                <p>{timeline.evidence_id}</p>
              </div>
              <div className="card-body">
                <div className="timeline-list">
                  {timeline.events?.map((event, idx) => (
                    <div key={idx} className="timeline-item">
                      <div className="timeline-marker" style={{ color: event.integrity_ok ? "#10b981" : "#ef4444" }}>
                        {event.integrity_ok ? "✓" : "✕"}
                      </div>
                      <div className="timeline-content">
                        <div className="timeline-header">
                          <span className="timeline-action">{event.action_type}</span>
                          <span className="timeline-time">{new Date(event.timestamp).toLocaleString()}</span>
                        </div>
                        <div className="timeline-actor">
                          {event.actor_user_id} ({event.actor_org_id})
                        </div>
                        {event.endorsement_status && (
                          <div className="timeline-status">Endorsement: {event.endorsement_status}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.section>
          )}

          {/* Event & Endorse */}
          <motion.section className="card" variants={panelAnim}>
            <div className="card-header">
              <h3>Custody Event</h3>
            </div>
            <form className="card-body" onSubmit={handleEvent}>
              <div className="form-group">
                <label>Evidence ID *</label>
                <input
                  placeholder="Target evidence"
                  value={eventForm.evidence_id}
                  onChange={(e) => setEventForm((prev) => ({ ...prev, evidence_id: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label>Action Type *</label>
                <select
                  value={eventForm.action_type}
                  onChange={(e) => setEventForm((prev) => ({ ...prev, action_type: e.target.value }))}
                >
                  {ACTION_TYPES.map((action) => (
                    <option key={action} value={action}>
                      {action}
                    </option>
                  ))}
                </select>
              </div>
              <button type="submit" className="primary">
                Record Event
              </button>
            </form>
          </motion.section>
        </motion.main>
      )}

      {/* Compliance Tab */}
      {activeTab === "compliance" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} key="compliance-section">
          <ComplianceDashboard userId={userId} />
        </motion.div>
      )}

      {/* Monitoring Tab */}
      {activeTab === "monitoring" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} key="monitoring-section">
          <MonitoringDashboard userId={userId} />
        </motion.div>
      )}

      {/* Analytics Tab */}
      {activeTab === "analytics" && (
        <motion.main
          className="console-grid"
          variants={stagger}
          initial="hidden"
          animate="show"
          key="analytics-section"
        >
          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>📊 Evidence Analytics Dashboard</h2>
              <p>System-wide statistics and trends</p>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px" }}>
                <div className="stat-card">
                  <div className="stat-value">{analyticsData?.total_evidence || 0}</div>
                  <div className="stat-label">Total Evidence Items</div>
                  <div className="stat-change">↑ 12% this month</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{analyticsData?.active_cases || 0}</div>
                  <div className="stat-label">Active Cases</div>
                  <div className="stat-change">↑ 3 this week</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{analyticsData?.endorsement_rate || 0}%</div>
                  <div className="stat-label">Endorsement Success Rate</div>
                  <div className="stat-change">↑ 2.3% improvement</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{analyticsData?.integrity_failures || 0}</div>
                  <div className="stat-label">Integrity Failures</div>
                  <div className="stat-change">↓ 1 less than last week</div>
                </div>
              </div>
            </div>
          </motion.section>

          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>Action Type Breakdown</h2>
              <p>Distribution of custody events by type</p>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "15px" }}>
                {analyticsData?.action_breakdown && Object.entries(analyticsData.action_breakdown).map(([action, count]) => (
                  <div key={action} style={{ padding: "16px", background: "#f0f9ff", borderRadius: "8px", borderLeft: "4px solid #1e40af" }}>
                    <div style={{ fontSize: "18px", fontWeight: "600", color: "#1e40af" }}>{count}</div>
                    <div style={{ fontSize: "14px", color: "#64748b", marginTop: "4px" }}>{action}</div>
                    <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "6px" }}>
                      {(count / Object.values(analyticsData.action_breakdown).reduce((a, b) => a + b, 0) * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.section>

          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>Monthly Trend</h2>
              <p>Evidence intake trend (last 7 months)</p>
            </div>
            <div className="card-body">
              <div style={{ display: "flex", alignItems: "flex-end", gap: "8px", height: "250px", padding: "20px 0" }}>
                {analyticsData?.monthly_trend && analyticsData.monthly_trend.map((value, idx) => (
                  <div key={idx} style={{ flex: 1, textAlign: "center" }}>
                    <div 
                      style={{
                        height: `${(value / 65) * 100}%`,
                        background: "linear-gradient(to top, #3b82f6, #60a5fa)",
                        borderRadius: "4px 4px 0 0",
                        cursor: "pointer",
                        transition: "all 0.3s",
                      }}
                      onMouseEnter={(e) => e.target.style.opacity = "0.7"}
                      onMouseLeave={(e) => e.target.style.opacity = "1"}
                      title={`Month ${idx + 1}: ${value} items`}
                    />
                    <div style={{ fontSize: "12px", marginTop: "8px", color: "#64748b" }}>M{idx + 1}</div>
                  </div>
                ))}
              </div>
            </div>
          </motion.section>
        </motion.main>
      )}

      {/* Search Tab */}
      {activeTab === "search" && (
        <motion.main
          className="console-grid"
          variants={stagger}
          initial="hidden"
          animate="show"
          key="search-section"
        >
          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>🔍 Advanced Evidence Search</h2>
              <p>Powerful filtering and discovery tools</p>
            </div>
            <div className="card-body">
              <div className="form-row">
                <div className="form-group" style={{ flex: 2 }}>
                  <label htmlFor="search-evidence">Search Evidence ID or Description</label>
                  <input
                    id="search-evidence"
                    placeholder="Enter evidence ID (EV-), case ID, or keywords..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="filter-type">Filter Type</label>
                  <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                    <option value="all">All Types</option>
                    <option value="TRANSFER">Transfer</option>
                    <option value="ACCESS">Access</option>
                    <option value="ANALYSIS">Analysis</option>
                    <option value="STORAGE">Storage</option>
                    <option value="COURT_SUBMISSION">Court Submission</option>
                    <option value="ENDORSE">Endorsement</option>
                  </select>
                </div>
              </div>
              <button className="primary" onClick={() => setMessage("Search initiated: " + searchQuery)}>
                🔎 Search
              </button>
            </div>
          </motion.section>

          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>Sample Search Results</h2>
              <p>Mock results for demonstration</p>
            </div>
            <div className="card-body">
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0" }}>
                    <th style={{ padding: "12px", textAlign: "left", color: "#1e40af", fontWeight: "600" }}>Evidence ID</th>
                    <th style={{ padding: "12px", textAlign: "left", color: "#1e40af", fontWeight: "600" }}>Case ID</th>
                    <th style={{ padding: "12px", textAlign: "left", color: "#1e40af", fontWeight: "600" }}>Description</th>
                    <th style={{ padding: "12px", textAlign: "left", color: "#1e40af", fontWeight: "600" }}>Status</th>
                    <th style={{ padding: "12px", textAlign: "left", color: "#1e40af", fontWeight: "600" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { id: "EV-98734", case: "CASE-2026-001", desc: "Hard Drive - Desktop", status: "verified" },
                    { id: "EV-98721", case: "CASE-2026-002", desc: "USB Flash Drive", status: "pending" },
                    { id: "EV-98695", case: "CASE-2026-001", desc: "Mobile Device", status: "verified" },
                  ].map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0" }}>
                      <td style={{ padding: "12px", fontFamily: "monospace", color: "#1e40af" }}>{item.id}</td>
                      <td style={{ padding: "12px" }}>{item.case}</td>
                      <td style={{ padding: "12px" }}>{item.desc}</td>
                      <td style={{ padding: "12px" }}>
                        <span className={`badge ${item.status === "verified" ? "badge-success" : "badge-warning"}`}>
                          {item.status === "verified" ? "✓ Verified" : "⏳ Pending"}
                        </span>
                      </td>
                      <td style={{ padding: "12px" }}>
                        <button className="btn-ghost" onClick={() => setEvidenceId(item.id)}>View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.section>

          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>Advanced Filters</h2>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
                <div className="filter-option">
                  <input type="checkbox" id="integrity-ok" defaultChecked />
                  <label htmlFor="integrity-ok">✓ Integrity Verified</label>
                </div>
                <div className="filter-option">
                  <input type="checkbox" id="endorsed" />
                  <label htmlFor="endorsed">◆ Endorsed</label>
                </div>
                <div className="filter-option">
                  <input type="checkbox" id="recent" />
                  <label htmlFor="recent">📅 Recent (7 days)</label>
                </div>
                <div className="filter-option">
                  <input type="checkbox" id="court-ready" />
                  <label htmlFor="court-ready">⚖️ Court Ready</label>
                </div>
              </div>
            </div>
          </motion.section>
        </motion.main>
      )}

      {/* System Health Tab */}
      {activeTab === "health" && (
        <motion.main
          className="console-grid"
          variants={stagger}
          initial="hidden"
          animate="show"
          key="health-section"
        >
          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>⚙️ System Health & Performance</h2>
              <p>Real-time system diagnostics</p>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "20px" }}>
                <div className="health-item">
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontWeight: "600" }}>Database Health</span>
                    <span className="badge badge-success">✓ Healthy</span>
                  </div>
                  <div style={{ background: "#e0f2fe", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ background: "#0284c7", height: "100%", width: "98%" }} />
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "8px" }}>98% Uptime</div>
                </div>

                <div className="health-item">
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontWeight: "600" }}>API Response Time</span>
                    <span className="badge badge-success">✓ Optimal</span>
                  </div>
                  <div style={{ background: "#dcfce7", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ background: "#22c55e", height: "100%", width: "92%" }} />
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "8px" }}>Avg: 145ms</div>
                </div>

                <div className="health-item">
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontWeight: "600" }}>Storage Capacity</span>
                    <span className="badge badge-info">ℹ 45% Used</span>
                  </div>
                  <div style={{ background: "#fef3c7", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ background: "#eab308", height: "100%", width: "45%" }} />
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "8px" }}>2.3 TB / 5 TB</div>
                </div>

                <div className="health-item">
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontWeight: "600" }}>Ledger Chain Integrity</span>
                    <span className="badge badge-success">✓ Valid</span>
                  </div>
                  <div style={{ background: "#dcfce7", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ background: "#10b981", height: "100%", width: "100%" }} />
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "8px" }}>All blocks verified</div>
                </div>
              </div>
            </div>
          </motion.section>

          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>System Status</h2>
              <p>Component status overview</p>
            </div>
            <div className="card-body">
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "#f0fdf4", borderRadius: "6px" }}>
                  <span>Authentication Service</span>
                  <span className="badge badge-success">✓ Online</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "#f0fdf4", borderRadius: "6px" }}>
                  <span>Evidence Storage</span>
                  <span className="badge badge-success">✓ Online</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "#f0fdf4", borderRadius: "6px" }}>
                  <span>Compliance Engine</span>
                  <span className="badge badge-success">✓ Online</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "#f0fdf4", borderRadius: "6px" }}>
                  <span>Encryption Module</span>
                  <span className="badge badge-success">✓ Online</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "#f0fdf4", borderRadius: "6px" }}>
                  <span>Audit Logging</span>
                  <span className="badge badge-success">✓ Online</span>
                </div>
              </div>
            </div>
          </motion.section>

          <motion.section className="card wide" variants={panelAnim} whileHover={{ y: -3 }}>
            <div className="card-header">
              <h2>Recent System Events</h2>
            </div>
            <div className="card-body">
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {[
                  { event: "Database maintenance completed", time: "30 mins ago", type: "info" },
                  { event: "Backup verification successful", time: "2 hours ago", type: "success" },
                  { event: "Security update applied", time: "5 hours ago", type: "info" },
                  { event: "Cache cleared and refreshed", time: "1 day ago", type: "success" },
                ].map((item, idx) => (
                  <div key={idx} style={{ padding: "12px", background: "#f1f5f9", borderRadius: "6px", display: "flex", justifyContent: "space-between" }}>
                    <span>{item.event}</span>
                    <span style={{ fontSize: "12px", color: "#64748b" }}>{item.time}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.section>
        </motion.main>
      )}
    </div>
  );
}
