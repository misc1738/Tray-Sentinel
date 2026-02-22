import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api } from "./api";

const ACTION_TYPES = [
  "INTAKE",
  "TRANSFER",
  "ACCESS",
  "ANALYSIS",
  "STORAGE",
  "COURT_SUBMISSION",
  "ENDORSE",
];

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

const fadeUp = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] } },
};

const stagger = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.08,
    },
  },
};

const panelAnim = {
  hidden: { opacity: 0, y: 18, scale: 0.985 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.55, ease: [0.2, 0.8, 0.2, 1] },
  },
};

export default function App() {
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState("auditor1");
  const [health, setHealth] = useState(null);
  const [securityPosture, setSecurityPosture] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

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

  const roleLabel = useMemo(() => users.find((u) => u.user_id === userId)?.role || "", [users, userId]);

  useEffect(() => {
    (async () => {
      try {
        const [healthResp, usersResp] = await Promise.all([api.health(), api.users()]);
        setHealth(healthResp);
        setUsers(usersResp.users || []);
        if ((usersResp.users || []).length && !usersResp.users.find((u) => u.user_id === userId)) {
          setUserId(usersResp.users[0].user_id);
        }
      } catch (e) {
        setError(`Initialization failed: ${e.message}`);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const posture = await api.securityPosture(userId);
        setSecurityPosture(posture);
      } catch {
        setSecurityPosture(null);
      }
    })();
  }, [userId]);

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

  return (
    <div className="shell">
      <div className="ambient a1" />
      <div className="ambient a2" />

      <motion.header
        className="nav-wrap"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="logo">◆</div>
        <nav>
          <motion.a href="#" whileHover={{ y: -2, opacity: 1 }} whileTap={{ scale: 0.98 }}>
            Home
          </motion.a>
          <motion.a href="#console" whileHover={{ y: -2, opacity: 1 }} whileTap={{ scale: 0.98 }}>
            Operations
          </motion.a>
          <motion.a href="#timeline" whileHover={{ y: -2, opacity: 1 }} whileTap={{ scale: 0.98 }}>
            Timeline
          </motion.a>
          <motion.a href="#case" whileHover={{ y: -2, opacity: 1 }} whileTap={{ scale: 0.98 }}>
            Case Audit
          </motion.a>
          <motion.a href="#security" whileHover={{ y: -2, opacity: 1 }} whileTap={{ scale: 0.98 }}>
            Security
          </motion.a>
        </nav>
        <div className="nav-actions">
          <motion.button className="ghost" whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}>
            Login
          </motion.button>
          <motion.button className="pill" whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}>
            Sign up
          </motion.button>
        </div>
      </motion.header>

      <motion.section
        className="hero"
        variants={stagger}
        initial="hidden"
        animate="show"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
      >
        <motion.div className="hero-copy" variants={stagger}>
          <motion.span className="chip" variants={fadeUp}>
            New • Tamper-evident chain of custody
          </motion.span>
          <motion.h1 variants={fadeUp}>
            Build trusted
            <br />
            digital evidence protocol
          </motion.h1>
          <motion.p variants={fadeUp}>
            Tracey&apos;s Sentinel secures evidence intake, custody movement, endorsements, and court-ready artifacts on a
            cryptographic ledger.
          </motion.p>
          <motion.div className="hero-cta" variants={fadeUp}>
            <motion.a href="#console" className="cta-main" whileHover={{ y: -3, scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              Open Control Center
            </motion.a>
            <span className="cta-sub">Chain valid: {String(health?.ledger_chain_valid ?? "unknown")}</span>
          </motion.div>
        </motion.div>
        <div className="hero-art" aria-hidden="true">
          <motion.div className="cube c1" animate={{ y: [0, -10, 0], rotate: [-18, -12, -18] }} transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }} />
          <motion.div className="cube c2" animate={{ y: [0, 12, 0], rotate: [16, 10, 16] }} transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 0.35 }} />
          <motion.div className="cube c3" animate={{ y: [0, -14, 0], rotate: [18, 24, 18] }} transition={{ duration: 7.6, repeat: Infinity, ease: "easeInOut", delay: 0.6 }} />
          <motion.div className="cube c4" animate={{ y: [0, 8, 0], rotate: [-20, -14, -20] }} transition={{ duration: 8.4, repeat: Infinity, ease: "easeInOut", delay: 0.2 }} />
          <motion.div className="cube c5" animate={{ y: [0, -9, 0], rotate: [22, 16, 22] }} transition={{ duration: 9.2, repeat: Infinity, ease: "easeInOut", delay: 0.8 }} />
        </div>
      </motion.section>

      <motion.main id="console" className="console-grid" variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.1 }}>
        <motion.section className="panel highlight" variants={panelAnim} whileHover={{ y: -3 }}>
          <h2>Control Center</h2>
          <div className="operator-row">
            <div className="operator-field">
              <label>Operator</label>
              <select value={userId} onChange={(e) => setUserId(e.target.value)}>
                {users.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.user_id} — {u.role}
                  </option>
                ))}
              </select>
            </div>
            <div className="badges">
              <span className="stat">Role: {roleLabel || "unknown"}</span>
              <span className="stat">Ledger: {health?.status || "unknown"}</span>
            </div>
          </div>
          {message && <p className="ok">{message}</p>}
          {error && <p className="bad">{error}</p>}
          {!message && !error && <p className="muted">All systems ready.</p>}
        </motion.section>

        <motion.section className="panel" variants={panelAnim} whileHover={{ y: -3 }}>
          <h3>Evidence Intake</h3>
          <form onSubmit={handleIntake}>
            <input
              placeholder="Case ID"
              value={intakeForm.case_id}
              onChange={(e) => setIntakeForm((prev) => ({ ...prev, case_id: e.target.value }))}
              required
            />
            <input
              placeholder="Description"
              value={intakeForm.description}
              onChange={(e) => setIntakeForm((prev) => ({ ...prev, description: e.target.value }))}
              required
            />
            <input
              placeholder="Source Device"
              value={intakeForm.source_device}
              onChange={(e) => setIntakeForm((prev) => ({ ...prev, source_device: e.target.value }))}
            />
            <input
              placeholder="Acquisition Method"
              value={intakeForm.acquisition_method}
              onChange={(e) => setIntakeForm((prev) => ({ ...prev, acquisition_method: e.target.value }))}
              required
            />
            <input type="file" onChange={(e) => setIntakeFile(e.target.files?.[0] || null)} required />
            <button type="submit">Register Evidence</button>
          </form>
        </motion.section>

        <motion.section className="panel" variants={panelAnim} whileHover={{ y: -3 }}>
          <h3>Custody Event</h3>
          <form onSubmit={handleEvent}>
            <input
              placeholder="Evidence ID"
              value={eventForm.evidence_id}
              onChange={(e) => setEventForm((prev) => ({ ...prev, evidence_id: e.target.value }))}
              required
            />
            <select
              value={eventForm.action_type}
              onChange={(e) => setEventForm((prev) => ({ ...prev, action_type: e.target.value }))}
            >
              {ACTION_TYPES.filter((a) => a !== "INTAKE").map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
            <textarea
              rows={4}
              value={eventForm.details}
              onChange={(e) => setEventForm((prev) => ({ ...prev, details: e.target.value }))}
            />
            <input
              placeholder="Presented SHA256 (optional)"
              value={eventForm.presented_sha256}
              onChange={(e) => setEventForm((prev) => ({ ...prev, presented_sha256: e.target.value }))}
            />
            <label className="inline">
              <input
                type="checkbox"
                checked={eventForm.endorse}
                onChange={(e) => setEventForm((prev) => ({ ...prev, endorse: e.target.checked }))}
              />
              Endorse with this event
            </label>
            <button type="submit">Record Event</button>
          </form>
        </motion.section>

        <motion.section className="panel" variants={panelAnim} whileHover={{ y: -3 }}>
          <h3>Endorsement</h3>
          <form onSubmit={handleEndorse}>
            <input
              placeholder="Evidence ID"
              value={endorseForm.evidence_id}
              onChange={(e) => setEndorseForm((prev) => ({ ...prev, evidence_id: e.target.value }))}
              required
            />
            <input
              placeholder="Target TX ID"
              value={endorseForm.tx_id}
              onChange={(e) => setEndorseForm((prev) => ({ ...prev, tx_id: e.target.value }))}
              required
            />
            <button type="submit">Endorse Transaction</button>
          </form>
        </motion.section>

        <motion.section className="panel" variants={panelAnim} whileHover={{ y: -3 }}>
          <h3>Evidence Operations</h3>
          <div className="row">
            <input placeholder="Evidence ID" value={evidenceId} onChange={(e) => setEvidenceId(e.target.value)} />
            <button onClick={() => loadEvidence()}>Load</button>
          </div>
          <div className="row wrap">
            <button onClick={handleVerify} disabled={!evidenceId}>
              Verify Integrity
            </button>
            <button onClick={handleDownloadReport} disabled={!evidenceId}>
              Download Report
            </button>
            <button onClick={handleDownloadBundle} disabled={!evidenceId}>
              Download Bundle
            </button>
            {evidenceId && (
                <motion.a
                  href={api.qrUrl(evidenceId)}
                  target="_blank"
                  rel="noreferrer"
                  className="button-link"
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.98 }}
                >
                Open QR
                </motion.a>
            )}
          </div>
        </motion.section>

        <motion.section id="timeline" className="panel wide" variants={panelAnim} whileHover={{ y: -2 }}>
          <h3>Evidence Timeline</h3>
          {!timeline?.events?.length && <p className="muted">No evidence loaded.</p>}
          {timeline?.events?.map((ev) => (
            <motion.article
              className="event"
              key={ev.tx_id}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ duration: 0.35 }}
              whileHover={{ scale: 1.01 }}
            >
              <div className="event-head">
                <strong>{ev.action_type}</strong>
                <span>{new Date(ev.timestamp).toLocaleString()}</span>
              </div>
              <div className="event-meta">
                <span>{ev.actor_user_id}</span>
                <span>{ev.actor_role}</span>
                <span>{ev.actor_org_id}</span>
              </div>
              <div className="event-meta">
                <span>Integrity: {String(ev.integrity_ok)}</span>
                <span>
                  Endorsement: {ev.endorsement_status} ({ev.unique_endorser_orgs}/{ev.required_endorser_orgs})
                </span>
              </div>
              <details>
                <summary>Hashes</summary>
                <p>TX: {ev.tx_id}</p>
                <p>record_hash: {ev.record_hash}</p>
                <p>prev_hash: {ev.prev_hash}</p>
              </details>
            </motion.article>
          ))}
        </motion.section>

        <motion.section id="case" className="panel wide" variants={panelAnim} whileHover={{ y: -2 }}>
          <h3>Case Audit</h3>
          <div className="row">
            <input placeholder="Case ID" value={caseId} onChange={(e) => setCaseId(e.target.value)} />
            <button onClick={handleLoadCase} disabled={!caseId}>
              Load Case
            </button>
          </div>

          {caseAudit && (
            <div className="audit-grid">
              <p>Total Evidence: {caseAudit.evidence_count}</p>
              <p>Total Events: {caseAudit.total_events}</p>
              <p>Integrity Failures: {caseAudit.integrity_failures}</p>
              <p>Pending Endorsements: {caseAudit.pending_endorsements}</p>
              <p>Compliant Evidence: {caseAudit.compliant_evidence_count}</p>
              <p>Chain Valid: {String(caseAudit.chain_valid)}</p>
            </div>
          )}

          {caseSummary?.evidence_items?.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Evidence ID</th>
                    <th>Description</th>
                    <th>File</th>
                    <th>Created</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {caseSummary.evidence_items.map((item) => (
                    <tr key={item.evidence_id}>
                      <td>{item.evidence_id}</td>
                      <td>{item.description}</td>
                      <td>{item.file_name}</td>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td>
                        <button onClick={() => loadEvidence(item.evidence_id)}>Open</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.section>

        <motion.section id="security" className="panel wide" variants={panelAnim} whileHover={{ y: -2 }}>
          <h3>Security Posture</h3>
          {!securityPosture && <p className="muted">Security posture unavailable for selected operator.</p>}
          {securityPosture && (
            <>
              <div className="audit-grid">
                <p>Evidence Integrity: {securityPosture.cryptographic_measures?.evidence_integrity}</p>
                <p>Ledger Integrity: {securityPosture.cryptographic_measures?.ledger_integrity}</p>
                <p>Event Signatures: {securityPosture.cryptographic_measures?.ledger_event_signatures}</p>
                <p>
                  At-rest Encryption: {String(
                    securityPosture.cryptographic_measures?.evidence_at_rest_encryption?.enabled ?? false
                  )}
                </p>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Data Asset</th>
                      <th>Storage Path</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Evidence Files</td>
                      <td>{securityPosture.data_locations?.evidence_store}</td>
                    </tr>
                    <tr>
                      <td>Evidence Metadata DB</td>
                      <td>{securityPosture.data_locations?.metadata_db}</td>
                    </tr>
                    <tr>
                      <td>Ledger JSONL</td>
                      <td>{securityPosture.data_locations?.ledger_file}</td>
                    </tr>
                    <tr>
                      <td>User Signing Keys</td>
                      <td>{securityPosture.data_locations?.user_signing_keys}</td>
                    </tr>
                    <tr>
                      <td>Evidence Encryption Key</td>
                      <td>{securityPosture.cryptographic_measures?.evidence_at_rest_encryption?.key_path}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </motion.section>

        {report?.report && (
          <motion.section className="panel wide" variants={panelAnim} whileHover={{ y: -2 }}>
            <h3>Report Snapshot</h3>
            <div className="audit-grid">
              <p>Generated: {new Date(report.generated_at).toLocaleString()}</p>
              <p>Evidence: {report.report.evidence?.evidence_id}</p>
              <p>Case: {report.report.evidence?.case_id}</p>
              <p>Chain Valid: {String(report.report.ledger_validation?.chain_valid)}</p>
            </div>
          </motion.section>
        )}
      </motion.main>
    </div>
  );
}
