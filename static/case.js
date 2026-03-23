/* Case Dashboard for Tracey's Sentinel — Enhanced */
const API_BASE = '';

async function fetchJSON(url, opts = {}) {
    const r = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    return r.json();
}

document.getElementById('load-case').addEventListener('click', loadCase);
document.getElementById('case-id').addEventListener('keypress', (e) => e.key === 'Enter' && loadCase());

async function loadCase() {
    const caseId = document.getElementById('case-id').value.trim();
    if (!caseId) {
        showError('Case ID required');
        return;
    }

    clearError();
    try {
        const summary = await fetchJSON(`/case/${caseId}`, { headers: { 'X-User-Id': 'auditor1' } });
        renderCaseSummary(summary);
        document.getElementById('case-summary').style.display = 'block';
    } catch (e) {
        showError('Failed to load case: ' + e.message);
    }
}

function renderCaseSummary(summary) {
    const tbody = document.getElementById('evidence-table');
    if (!summary.evidence_items || summary.evidence_items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No evidence items found</td></tr>';
        return;
    }

    tbody.innerHTML = summary.evidence_items.map(ev => `
        <tr>
            <td><code style="word-break: break-all;">${ev.evidence_id}</code></td>
            <td>${ev.description || 'N/A'}</td>
            <td>${ev.file_name || 'N/A'}</td>
            <td>${new Date(ev.created_at).toLocaleString()}</td>
            <td>
                <button class="action-btn" onclick="viewEvidence('${ev.evidence_id}')">📋 View</button>
            </td>
        </tr>
    `).join('');
}

function viewEvidence(evidenceId) {
    // Navigate to scanner and load evidence
    switchTab('scanner');
    loadEvidence(evidenceId);
}

function showError(msg) {
    const el = document.getElementById('case-error');
    el.textContent = msg;
    el.style.display = 'block';
}

function clearError() {
    document.getElementById('case-error').style.display = 'none';
}
