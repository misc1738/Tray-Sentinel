/* Case Dashboard for Tracey's Sentinel */
const API_BASE = '';

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

function setError(msg) {
    const el = document.getElementById('case-error');
    el.textContent = msg;
    el.style.display = 'block';
}

function clearError() {
    const el = document.getElementById('case-error');
    el.style.display = 'none';
}

document.getElementById('load-case').addEventListener('click', async () => {
    const caseId = document.getElementById('case-id').value.trim();
    if (!caseId) {
        setError('Case ID required');
        return;
    }
    clearError();
    try {
        const summary = await fetchJSON(`/case/${caseId}`, { headers: { 'X-User-Id': 'auditor1' } });
        renderCaseSummary(summary);
        showSection('case-summary');
    } catch (e) {
        setError('Failed to load case: ' + e.message);
    }
});

function renderCaseSummary(summary) {
    const tbody = document.querySelector('#evidence-table tbody');
    tbody.innerHTML = summary.evidence_items.map(ev => `
        <tr>
            <td><code>${ev.evidence_id}</code></td>
            <td>${ev.description}</td>
            <td>${ev.file_name}</td>
            <td><code style="word-break:break-all;">${ev.sha256}</code></td>
            <td>${new Date(ev.created_at).toLocaleString()}</td>
            <td>
                <button onclick="window.open('index.html#evidence:${ev.evidence_id}', '_blank')">View</button>
            </td>
        </tr>
    `).join('');
}
