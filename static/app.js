/* Tracey's Sentinel UI — QR scan, evidence view, timeline, actions */

const API_BASE = ''; // same-origin

let currentEvidenceId = null;
let qrScanner = null;

async function fetchJSON(url, opts = {}) {
    const r = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    return r.json();
}

function showSection(id) {
    document.querySelectorAll('main > section').forEach(s => s.style.display = 'none');
    document.getElementById(id).style.display = 'block';
}

function setScanResult(text, isError = false) {
    const el = document.getElementById('scan-result');
    el.textContent = text;
    el.style.display = 'block';
    el.classList.toggle('error', isError);
}

async function loadEvidence(evidenceId) {
    currentEvidenceId = evidenceId;
    try {
        const [timeline, report] = await Promise.all([
            fetchJSON(`/evidence/${evidenceId}/timeline`),
            fetchJSON(`/evidence/${evidenceId}/report`)
        ]);
        renderEvidence(report.report.evidence);
        renderTimeline(timeline.events);
        showSection('evidence');
    } catch (e) {
        setScanResult('Failed to load evidence: ' + e.message, true);
    }
}

function renderEvidence(ev) {
    const meta = document.getElementById('evidence-meta');
    meta.innerHTML = `
        <dl>
            <dt>Evidence ID</dt><dd>${ev.evidence_id}</dd>
            <dt>Case ID</dt><dd>${ev.case_id}</dd>
            <dt>Description</dt><dd>${ev.description}</dd>
            <dt>Source Device</dt><dd>${ev.source_device || 'N/A'}</dd>
            <dt>Acquisition Method</dt><dd>${ev.acquisition_method}</dd>
            <dt>File Name</dt><dd>${ev.file_name}</dd>
            <dt>SHA‑256</dt><dd><code>${ev.sha256}</code></dd>
            <dt>Created</dt><dd>${new Date(ev.created_at).toLocaleString()}</dd>
        </dl>
    `;
}

function renderTimeline(events) {
    const list = document.getElementById('timeline-list');
    list.innerHTML = events.map(e => {
        const endorsementCls = e.endorsement_status === 'FINAL' ? 'final' : 'pending';
        const endorsementText = e.endorsement_status === 'FINAL'
            ? `Endorsed by ${e.endorser_org_ids.join(', ')}`
            : `Pending (${e.unique_endorser_orgs}/${e.required_endorser_orgs} orgs)`;
        return `
            <div class="timeline-item">
                <h3>${e.action_type}</h3>
                <div class="meta">
                    ${e.actor_role} (${e.actor_org_id}) — ${new Date(e.timestamp).toLocaleString()}
                </div>
                ${e.details ? `<pre>${JSON.stringify(e.details, null, 2)}</pre>` : ''}
                ${e.action_type !== 'ENDORSE' ? `
                    <div class="endorsement ${endorsementCls}">
                        ${endorsementText}
                    </div>
                ` : ''}
                <details style="margin-top:0.5rem;">
                    <summary>Hash & Signature</summary>
                    <p><strong>prev_hash:</strong> <code>${e.prev_hash}</code></p>
                    <p><strong>record_hash:</strong> <code>${e.record_hash}</code></p>
                    <p><strong>signer_pubkey_b64:</strong> <code style="word-break:break-all;">${e.signer_pubkey_b64}</code></p>
                    <p><strong>signature_b64:</strong> <code style="word-break:break-all;">${e.signature_b64}</code></p>
                </details>
            </div>
        `;
    }).join('');
    showSection('timeline');
}

// QR Scanner
async function startScanner() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        const video = document.getElementById('video');
        video.srcObject = stream;
        video.play();
        qrScanner = new QrScanner(
            video,
            result => {
                stopScanner();
                const match = result.data.match(/^evidence:(.+)$/);
                if (match) {
                    setScanResult(`Evidence ID: ${match[1]}`);
                    loadEvidence(match[1]);
                } else {
                    setScanResult('Invalid QR code', true);
                }
            },
            { highlightScanRegion: false, highlightCodeOutline: false }
        );
        await qrScanner.start();
        document.getElementById('start-scan').disabled = true;
        document.getElementById('stop-scan').disabled = false;
    } catch (e) {
        setScanResult('Camera error: ' + e.message, true);
    }
}

function stopScanner() {
    if (qrScanner) {
        qrScanner.stop();
        qrScanner = null;
    }
    const video = document.getElementById('video');
    const stream = video.srcObject;
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        video.srcObject = null;
    }
    document.getElementById('start-scan').disabled = false;
    document.getElementById('stop-scan').disabled = true;
}

// Actions
document.getElementById('start-scan').addEventListener('click', startScanner);
document.getElementById('stop-scan').addEventListener('click', stopScanner);

document.getElementById('verify-integrity').addEventListener('click', async () => {
    if (!currentEvidenceId) return;
    try {
        const v = await fetchJSON(`/evidence/${currentEvidenceId}/verify`, { method: 'POST' });
        alert(`Integrity ${v.integrity_ok ? 'OK' : 'FAILED'}\nExpected: ${v.expected_sha256}\nActual: ${v.actual_sha256}`);
        // Refresh timeline to show ACCESS event
        loadEvidence(currentEvidenceId);
    } catch (e) {
        alert('Verification failed: ' + e.message);
    }
});

document.getElementById('download-report').addEventListener('click', async () => {
    if (!currentEvidenceId) return;
    try {
        const report = await fetchJSON(`/evidence/${currentEvidenceId}/report`);
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sentinel-report-${currentEvidenceId}.json`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('Download failed: ' + e.message);
    }
});

document.getElementById('download-bundle').addEventListener('click', async () => {
    if (!currentEvidenceId) return;
    try {
        const resp = await fetch(`/evidence/${currentEvidenceId}/bundle`);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sentinel-bundle-${currentEvidenceId}.zip`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('Bundle download failed: ' + e.message);
    }
});
