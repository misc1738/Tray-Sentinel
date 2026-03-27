/* Tracey's Sentinel UI — Advanced Multi-Dashboard Platform with Export, Themes, & Notifications */

const API_BASE = ''; // same-origin

// ===== AUTHENTICATION CHECK =====
function checkAuthAndRedirect() {
    const token = localStorage.getItem('auth_token');
    const userId = localStorage.getItem('user_id');
    
    if (!token || !userId) {
        window.location.href = '/auth.html';
        return false;
    }
    return true;
}

// Redirect if not authenticated
if (!checkAuthAndRedirect()) {
    throw new Error('Not authenticated');
}

// ===== LOGOUT FUNCTION =====
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_id');
        localStorage.removeItem('user_role');
        localStorage.removeItem('org_id');
        window.location.href = '/auth.html';
    }
}

// ===== UPDATE USER INFO IN HEADER =====
function updateUserInfo() {
    const userId = localStorage.getItem('user_id');
    const userRole = localStorage.getItem('user_role');
    const orgId = localStorage.getItem('org_id');
    
    const userInfoEl = document.getElementById('user-info');
    if (userInfoEl && userId) {
        userInfoEl.innerHTML = `
            <span>👤 ${userId}</span>
            <span style="margin: 0 0.5rem; color: var(--text-secondary);">•</span>
            <span>${userRole || 'User'}</span>
            <span style="margin: 0 0.5rem; color: var(--text-secondary);">•</span>
            <span>${orgId || 'N/A'}</span>
            <button onclick="logout()" class="ghost" style="margin-left: 1rem;">Logout</button>
        `;
    }
}

let currentEvidenceId = null;
let qrScanner = null;
let analyticsData = null;
let favorites = JSON.parse(localStorage.getItem('favorites')) || [];
let userPreferences = JSON.parse(localStorage.getItem('userPreferences')) || { theme: 'dark', notifications: true };
let notifications = [];
let currentPage = { search: 1, cases: 1 };
const ITEMS_PER_PAGE = 10;

// ===== UTILITY FUNCTIONS =====
async function fetchJSON(url, opts = {}) {
    const token = localStorage.getItem('auth_token');
    const headers = {
        'Content-Type': 'application/json',
        'X-User-Id': localStorage.getItem('user_id') || 'unknown',
        ...opts.headers
    };
    
    const r = await fetch(url, {
        headers,
        ...opts,
    });
    
    if (r.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_id');
        window.location.href = '/auth.html';
        throw new Error('Session expired');
    }
    
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    return r.json();
}

function switchTab(tabName) {
    const sections = document.querySelectorAll('.tab-section');
    sections.forEach(s => s.style.display = 'none');
    const el = document.getElementById(tabName);
    if (el) el.style.display = 'block';

    const buttons = document.querySelectorAll('.nav-tab');
    buttons.forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`[data-tab="${tabName}"]`);
    if (btn) btn.classList.add('active');

    // Load data if needed
    if (tabName === 'analytics') loadAnalyticsDashboard();
    if (tabName === 'health') loadHealthMonitor();
}

// ===== HOME DASHBOARD =====
async function loadHomeDashboard() {
    try {
        // Fetch summary stats
        const response = await fetch('/evidence/summary');
        if (response.ok) {
            const data = await response.json();
            document.getElementById('total-evidence').textContent = data.total_evidence || 0;
            document.getElementById('active-cases').textContent = data.active_cases || 0;
            document.getElementById('success-rate').textContent = `${data.endorsement_success_rate || 0}%`;
            document.getElementById('pending-endorsements').textContent = data.pending_endorsements || 0;
        }
    } catch (e) {
        console.error('Failed to load dashboard:', e);
    }

    loadRecentActivity();
}

async function loadRecentActivity() {
    try {
        const response = await fetch('/evidence/recent?limit=6');
        if (response.ok) {
            const data = await response.json();
            const feed = document.getElementById('activity-feed');
            
            if (!data || data.length === 0) {
                feed.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">No recent activity</div>';
                return;
            }

            feed.innerHTML = data.map((activity, idx) => `
                <div class="activity-item" style="animation: slideIn 0.3s ease-out; animation-delay: ${idx * 0.05}s;">
                    <div class="activity-header">
                        <span class="activity-type">${activity.action_type || 'ACTION'}</span>
                        <span class="activity-time">${new Date(activity.timestamp || Date.now()).toLocaleString()}</span>
                    </div>
                    <div class="activity-content">${activity.description || activity.evidence_id || 'Evidence processed'}</div>
                    <div class="activity-status ${activity.status?.toLowerCase() || 'info'}">✓ ${activity.status || 'COMPLETED'}</div>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('Failed to load activities:', e);
    }
}

// ===== ANALYTICS DASHBOARD =====
async function loadAnalyticsDashboard() {
    try {
        const response = await fetch('/evidence/analytics');
        if (response.ok) {
            const data = await response.json();
            analyticsData = data;

            // Update KPIs
            document.getElementById('kpi-evidence').textContent = data.total_evidence || 0;
            document.getElementById('kpi-cases').textContent = data.active_cases || 0;
            document.getElementById('kpi-verified').textContent = `${data.verified_percentage || 0}%`;
            document.getElementById('kpi-failures').textContent = data.integrity_failures || 0;

            // Action Type Breakdown
            renderActionBreakdown(data.action_breakdown || {});

            // Monthly Trend
            renderMonthlyTrend(data.monthly_trend || []);
        }
    } catch (e) {
        console.error('Failed to load analytics:', e);
    }
}

function renderActionBreakdown(breakdown) {
    const container = document.getElementById('action-breakdown');
    const actions = Object.entries(breakdown).map(([type, count]) => (count > 0 ? [type, count] : null)).filter(Boolean);
    
    if (actions.length === 0) {
        container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary);">No action data available</div>';
        return;
    }

    const total = actions.reduce((sum, [_, count]) => sum + count, 0);
    container.innerHTML = actions.map(([type, count]) => {
        const percent = Math.round((count / total) * 100);
        const colors = { TRANSFER: '#00d9ff', ACCESS: '#7c3aed', ANALYSIS: '#f97316', STORAGE: '#10b981', ENDORSE: '#06b6d4', COURT_SUBMISSION: '#ef4444' };
        return `
            <div class="breakdown-card" style="border-left: 4px solid ${colors[type] || '#00d9ff'};">
                <div style="font-weight: 600; font-size: 0.9rem;">${type}</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: ${colors[type] || '#00d9ff'}; margin: 0.5rem 0;">${count}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">${percent}% of total</div>
            </div>
        `;
    }).join('');
}

function renderMonthlyTrend(trend) {
    const container = document.getElementById('monthly-trend');
    if (!trend || trend.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">No trend data available</div>';
        return;
    }

    const max = Math.max(...trend.map(t => t.count || 0), 1);
    container.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(60px, 1fr)); gap: 1rem; padding: 1rem 0;">
            ${trend.map((item, idx) => {
                const height = (item.count || 0) / max * 100;
                return `
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 0.5rem;">
                        <div style="width: 100%; height: 120px; background: var(--bg-secondary); border-radius: 4px; position: relative; overflow: hidden;">
                            <div style="position: absolute; bottom: 0; width: 100%; height: ${height}%; background: linear-gradient(to top, #00d9ff, #7c3aed); border-radius: 4px;"></div>
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">M${idx + 1}</div>
                        <div style="font-size: 0.85rem; font-weight: 600;">${item.count || 0}</div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// ===== SEARCH & FILTER =====
async function performSearch() {
    const searchInput = document.getElementById('search-input').value.trim();
    const actionFilter = document.getElementById('action-filter').value;
    const filterVerified = document.getElementById('filter-verified').checked;
    const filterEndorsed = document.getElementById('filter-endorsed').checked;
    const filterRecent = document.getElementById('filter-recent').checked;
    
    if (!searchInput && !actionFilter && !filterVerified && !filterEndorsed && !filterRecent) {
        document.getElementById('search-table-body').innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">Enter search criteria</td></tr>';
        return;
    }

    try {
        const params = new URLSearchParams();
        if (searchInput) params.append('q', searchInput);
        if (actionFilter) params.append('action', actionFilter);
        if (filterVerified) params.append('verified', 'true');
        if (filterRecent) params.append('recent_days', '7');

        const response = await fetch(`/evidence/search?${params}`);
        if (response.ok) {
            const results = await response.json();
            analyticsData.lastSearchResults = results;
            renderSearchResults(results);
            showNotification(`Found ${results.length} results ✓`, 'success');
        } else {
            document.getElementById('search-table-body').innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--danger);">Search failed</td></tr>';
            showNotification('Search failed', 'error');
        }
    } catch (e) {
        console.error('Search error:', e);
        showNotification('Search error: ' + e.message, 'error');
    }
}

function renderSearchResults(results) {
    const tbody = document.getElementById('search-table-body');
    if (!results || results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No results found</td></tr>';
        return;
    }

    currentPage.search = 1;
    renderPaginatedResults(results, 'search');
}

function renderPaginatedResults(results, type) {
    const tbody = document.getElementById(type === 'search' ? 'search-table-body' : 'evidence-table');
    const page = currentPage[type] || 1;
    const start = (page - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const paged = results.slice(start, end);

    tbody.innerHTML = paged.map(result => `
        <tr>
            <td><code>${result.evidence_id}</code></td>
            <td><code>${result.case_id}</code></td>
            <td>${result.description || 'N/A'}</td>
            <td><span class="status-badge ${result.integrity_verified ? 'verified' : 'pending'}">${result.integrity_verified ? '✓ Verified' : '⏳ Pending'}</span></td>
            <td>${new Date(result.created_at).toLocaleDateString()}</td>
            <td>
                <button onclick="toggleFavorite('${result.evidence_id}'); updateFavoriteButtons();" data-evidence-id="${result.evidence_id}" data-favorite-btn class="action-btn">☆ Add</button>
            </td>
            <td><button onclick="loadEvidence('${result.evidence_id}'); switchTab('scanner');" class="action-btn">View</button></td>
        </tr>
    `).join('');

    // Add pagination controls
    const totalPages = Math.ceil(results.length / ITEMS_PER_PAGE);
    if (totalPages > 1) {
        const paginationDiv = document.getElementById(type + '-pagination') || createPaginationControls(type);
        paginationDiv.innerHTML = `
            <div style="text-align: center; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
                <small style="color: var(--text-secondary);">Page ${page} of ${totalPages} (${results.length} results)</small>
                <div style="margin-top: 0.5rem; display: flex; gap: 0.5rem; justify-content: center;">
                    ${page > 1 ? `<button onclick="goToPage('${type}', ${page - 1});" class="ghost" style="padding: 0.5rem 1rem;">← Previous</button>` : ''}
                    ${page < totalPages ? `<button onclick="goToPage('${type}', ${page + 1});" class="ghost" style="padding: 0.5rem 1rem;">Next →</button>` : ''}
                </div>
            </div>
        `;
    }

    updateFavoriteButtons();
}

function createPaginationControls(type) {
    const div = document.createElement('div');
    div.id = type + '-pagination';
    const container = document.getElementById('search-results') || document.getElementById('case-summary');
    if (container) container.appendChild(div);
    return div;
}

function goToPage(type, page) {
    currentPage[type] = page;
    const results = type === 'search' ? analyticsData.lastSearchResults : analyticsData.lastCaseResults;
    if (results) renderPaginatedResults(results, type);
}

// ===== SYSTEM HEALTH MONITOR =====
async function loadHealthMonitor() {
    try {
        const startTime = performance.now();
        const response = await fetch('/health');
        const endTime = performance.now();
        
        if (response.ok) {
            const health = await response.json();
            document.getElementById('api-response-time').textContent = Math.round(endTime - startTime) + 'ms';
            document.getElementById('api-uptime').textContent = '99.9%';
            document.getElementById('db-records').textContent = health.total_records || 0;
            document.getElementById('db-size').textContent = (health.db_size_mb || 0).toFixed(2);
            document.getElementById('query-time').textContent = Math.round(health.avg_query_time || 45) + 'ms';
            document.getElementById('cache-rate').textContent = (health.cache_hit_rate || 92) + '%';
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
}

// ===== EVIDENCE MANAGEMENT =====
async function loadEvidence(evidenceId) {
    currentEvidenceId = evidenceId;
    try {
        const [timeline, report] = await Promise.all([
            fetchJSON(`/evidence/${evidenceId}/timeline`),
            fetchJSON(`/evidence/${evidenceId}/report`)
        ]);
        renderEvidence(report.report.evidence);
        renderTimeline(timeline.events);
        switchTab('evidence');
    } catch (e) {
        alert('Failed to load evidence: ' + e.message);
    }
}

function renderEvidence(ev) {
    const meta = document.getElementById('evidence-meta');
    meta.innerHTML = `
        <dl style="display: grid; grid-template-columns: 200px 1fr; gap: 1rem; margin: 1rem 0;">
            <dt>Evidence ID</dt><dd><code>${ev.evidence_id}</code></dd>
            <dt>Case ID</dt><dd><code>${ev.case_id}</code></dd>
            <dt>Description</dt><dd>${ev.description}</dd>
            <dt>Source Device</dt><dd>${ev.source_device || 'N/A'}</dd>
            <dt>Acquisition Method</dt><dd>${ev.acquisition_method}</dd>
            <dt>File Name</dt><dd>${ev.file_name}</dd>
            <dt>SHA-256</dt><dd><code style="word-break: break-all; font-size: 0.85rem;">${ev.sha256}</code></dd>
            <dt>Created</dt><dd>${new Date(ev.created_at).toLocaleString()}</dd>
        </dl>
    `;
}

function renderTimeline(events) {
    const display = document.getElementById('timeline-display');
    display.innerHTML = `<h3>⏱️ Chain of Custody Timeline</h3>` + events.map(e => {
        const endorsementCls = e.endorsement_status === 'FINAL' ? 'final' : 'pending';
        const endorsementText = e.endorsement_status === 'FINAL'
            ? `Endorsed by ${e.endorser_org_ids.join(', ')}`
            : `Pending (${e.unique_endorser_orgs}/${e.required_endorser_orgs} orgs)`;
        return `
            <div class="timeline-item">
                <h4>${e.action_type}</h4>
                <div class="meta">${e.actor_role} (${e.actor_org_id}) — ${new Date(e.timestamp).toLocaleString()}</div>
                ${e.details ? `<pre style="background: var(--bg-secondary); padding: 0.5rem; border-radius: 4px; overflow-x: auto; font-size: 0.8rem;">${JSON.stringify(e.details, null, 2)}</pre>` : ''}
                ${e.action_type !== 'ENDORSE' ? `<div class="endorsement ${endorsementCls}">${endorsementText}</div>` : ''}
                <details style="margin-top:0.5rem; font-size: 0.9rem;">
                    <summary>🔐 Hash & Signature</summary>
                    <p><strong>prev_hash:</strong> <code style="word-break:break-all; font-size: 0.75rem;">${e.prev_hash}</code></p>
                    <p><strong>record_hash:</strong> <code style="word-break:break-all; font-size: 0.75rem;">${e.record_hash}</code></p>
                </details>
            </div>
        `;
    }).join('');
}

// ===== QR SCANNER =====
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
                    loadEvidence(match[1]);
                } else {
                    alert('Invalid QR code format');
                }
            },
            { highlightScanRegion: false, highlightCodeOutline: false }
        );
        await qrScanner.start();
        document.getElementById('start-scan').disabled = true;
        document.getElementById('stop-scan').disabled = false;
    } catch (e) {
        alert('Camera error: ' + e.message);
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

// ===== FILE UPLOAD =====
let selectedFiles = [];

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function getFileIcon(fileName) {
    const ext = fileName.toLowerCase().split('.').pop();
    const iconMap = {
        // Documents
        'pdf': '📄', 'doc': '📝', 'docx': '📝', 'txt': '📋',
        // Images
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'bmp': '🖼️', 'svg': '🖼️',
        // Archives
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        // Video
        'mp4': '🎥', 'avi': '🎥', 'mov': '🎥', 'mkv': '🎥', 'wmv': '🎥',
        // Audio
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵', 'm4a': '🎵', 'aac': '🎵',
        // Code
        'js': '⚙️', 'py': '⚙️', 'json': '⚙️', 'xml': '⚙️', 'html': '⚙️',
        // Default
        'other': '📎'
    };
    return iconMap[ext] || iconMap['other'];
}

function updateFilesList() {
    const list = document.getElementById('upload-files-list');
    const statsDiv = document.getElementById('upload-stats');
    const uploadBtn = document.getElementById('upload-btn');
    const clearBtn = document.getElementById('clear-uploads');
    
    if (selectedFiles.length === 0) {
        list.innerHTML = '';
        statsDiv.style.display = 'none';
        uploadBtn.style.display = 'none';
        clearBtn.style.display = 'none';
        return;
    }
    
    // Calculate statistics
    let totalSize = 0;
    let largestSize = 0;
    selectedFiles.forEach(file => {
        totalSize += file.size;
        largestSize = Math.max(largestSize, file.size);
    });
    
    // Update stats display
    document.getElementById('stat-file-count').textContent = selectedFiles.length;
    document.getElementById('stat-total-size').textContent = formatFileSize(totalSize);
    document.getElementById('stat-largest').textContent = formatFileSize(largestSize);
    statsDiv.style.display = 'grid';
    
    // Update file list
    list.innerHTML = selectedFiles.map((file, idx) => `
        <div class="upload-file-item">
            <div class="upload-file-left">
                <div class="upload-file-icon">${getFileIcon(file.name)}</div>
                <div class="upload-file-info">
                    <div class="upload-file-name">${file.name}</div>
                    <div class="upload-file-size">${formatFileSize(file.size)}</div>
                </div>
            </div>
            <div class="upload-file-actions">
                <button class="upload-file-remove" onclick="removeFile(${idx})">Remove</button>
            </div>
        </div>
    `).join('');
    
    // Show action buttons
    uploadBtn.style.display = 'flex';
    clearBtn.style.display = 'flex';
}

function removeFile(idx) {
    selectedFiles.splice(idx, 1);
    updateFilesList();
    showNotification('File removed from upload', 'info');
}

function handleFileSelect(files) {
    selectedFiles = Array.from(files);
    updateFilesList();
    
    if (selectedFiles.length > 0) {
        showNotification(`${selectedFiles.length} file(s) selected for upload`, 'success');
    }
}

async function uploadFiles() {
    if (selectedFiles.length === 0) {
        showNotification('No files selected', 'warning');
        return;
    }

    const caseId = document.getElementById('upload-case-id').value.trim();
    const description = document.getElementById('upload-description').value.trim();

    if (!caseId) {
        showNotification('Case ID is required', 'danger');
        return;
    }

    const progressDiv = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-percentage');
    progressDiv.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = '0%';

    try {
        let completed = 0;
        const total = selectedFiles.length;

        for (const file of selectedFiles) {
            try {
                // Read file as base64
                const fileContent = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = (e) => resolve(e.target.result);
                    reader.onerror = reject;
                    reader.readAsArrayBuffer(file);
                });

                // Convert to base64 string
                const uint8Array = new Uint8Array(fileContent);
                const binaryString = String.fromCharCode.apply(null, uint8Array);
                const base64String = btoa(binaryString);

                // Send to backend
                const response = await fetch('/evidence/intake', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Operator': 'upload-system'
                    },
                    body: JSON.stringify({
                        case_id: caseId,
                        description: description || file.name,
                        file_name: file.name,
                        file_bytes_b64: base64String,
                        source_device: 'web-upload',
                        acquisition_method: 'file_upload'
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    completed++;
                    const percent = Math.round((completed / total) * 100);
                    progressBar.style.width = percent + '%';
                    progressText.textContent = percent + '%';
                    
                    showNotification(`✓ ${file.name} uploaded (ID: ${data.evidence_id.substring(0, 8)}...)`, 'success');
                } else {
                    const errorText = await response.text();
                    showNotification(`✗ Failed to upload ${file.name}: ${response.statusText}`, 'danger');
                }
            } catch (e) {
                showNotification(`✗ Error uploading ${file.name}: ${e.message}`, 'danger');
            }
        }

        if (completed === total) {
            showNotification('All files uploaded successfully!', 'success');
            selectedFiles = [];
            updateFilesList();
            document.getElementById('upload-case-id').value = '';
            document.getElementById('upload-description').value = '';
        }

        setTimeout(() => {
            progressDiv.style.display = 'none';
        }, 2000);
    } catch (e) {
        showNotification('Upload error: ' + e.message, 'danger');
        progressDiv.style.display = 'none';
    }
}

// ===== EVENT LISTENERS =====
document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', (e) => switchTab(e.target.dataset.tab));
});

document.getElementById('start-scan').addEventListener('click', startScanner);
document.getElementById('stop-scan').addEventListener('click', stopScanner);

// File Upload Event Listeners
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const browseBtn = document.getElementById('browse-files');
const uploadBtn = document.getElementById('upload-btn');
const clearBtn = document.getElementById('clear-uploads');

browseBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    handleFileSelect(e.target.files);
});

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    handleFileSelect(e.dataTransfer.files);
});

uploadBtn.addEventListener('click', uploadFiles);
clearBtn.addEventListener('click', () => {
    selectedFiles = [];
    updateFilesList();
    fileInput.value = '';
    showNotification('Files cleared', 'info');
});

document.getElementById('verify-integrity').addEventListener('click', async () => {
    if (!currentEvidenceId) return;
    try {
        const v = await fetchJSON(`/evidence/${currentEvidenceId}/verify`, { method: 'POST' });
        alert(`Integrity ${v.integrity_ok ? 'OK ✓' : 'FAILED ✗'}\nExpected: ${v.expected_sha256}\nActual: ${v.actual_sha256}`);
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

document.getElementById('back-scan').addEventListener('click', () => switchTab('scanner'));

document.getElementById('search-btn').addEventListener('click', performSearch);
document.getElementById('search-input').addEventListener('keypress', (e) => e.key === 'Enter' && performSearch());

// Case ID input - add listener
const caseIdInput = document.getElementById('case-id-input');
if (caseIdInput) {
    caseIdInput.addEventListener('keypress', (e) => e.key === 'Enter' && loadCase());
}

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    updateUserInfo();
    loadHomeDashboard();
    applyTheme();
    setupKeyboardShortcuts();
    loadFavorites();
    setInterval(loadRecentActivity, 5000); // Refresh every 5s
});

// ===== THEME MANAGEMENT =====
function applyTheme() {
    const theme = userPreferences.theme || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
}

function toggleTheme() {
    userPreferences.theme = userPreferences.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('userPreferences', JSON.stringify(userPreferences));
    applyTheme();
    showNotification('Theme changed to ' + userPreferences.theme.toUpperCase(), 'info');
}

// ===== NOTIFICATIONS =====
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    const id = Date.now();
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" style="background: none; border: none; color: inherit; cursor: pointer; margin-left: 1rem;">✕</button>
    `;
    container.appendChild(notification);
    
    setTimeout(() => notification.remove(), 5000);
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    container.style.cssText = 'position: fixed; top: 80px; right: 1rem; z-index: 1000; max-width: 400px;';
    document.body.appendChild(container);
    return container;
}

// ===== KEYBOARD SHORTCUTS =====
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd shortcuts
        if (e.ctrlKey || e.metaKey) {
            if (e.key === 's') { e.preventDefault(); switchTab('search'); }
            if (e.key === 'a') { e.preventDefault(); switchTab('analytics'); }
            if (e.key === 'h') { e.preventDefault(); switchTab('home'); }
            if (e.key === 'e') { e.preventDefault(); switchTab('scanner'); }
            if (e.key === 'k') { e.preventDefault(); switchTab('cases'); }
            if (e.key === '/') { e.preventDefault(); showKeyboardHelp(); }
        }
        
        // Single key shortcuts
        if (e.key === 'Escape') { closeAllModals(); }
        if (e.key === '?') { e.preventDefault(); showKeyboardHelp(); }
        if (e.key === 'g' && !e.ctrlKey && !e.metaKey) { switchTab('home'); }
        if (e.key === 'G' && !e.ctrlKey && !e.metaKey) { switchTab('home'); }
        if (e.key === 'l' && !e.ctrlKey && !e.metaKey) { logout(); }
        if (e.key === 'L' && !e.ctrlKey && !e.metaKey) { logout(); }
        if (e.key === 't' && !e.ctrlKey && !e.metaKey) { toggleTheme(); }
        if (e.key === 'T' && !e.ctrlKey && !e.metaKey) { toggleTheme(); }
    });
}

function showKeyboardHelp() {
    window.location.href = '/help.html';
}

function closeAllModals() {
    document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
}

// ===== FAVORITES SYSTEM =====
function toggleFavorite(evidenceId) {
    if (favorites.includes(evidenceId)) {
        favorites = favorites.filter(id => id !== evidenceId);
        showNotification('Removed from favorites ✕', 'info');
    } else {
        favorites.push(evidenceId);
        showNotification('Added to favorites ★', 'success');
    }
    localStorage.setItem('favorites', JSON.stringify(favorites));
    updateFavoriteButtons();
}

function updateFavoriteButtons() {
    document.querySelectorAll('[data-favorite-btn]').forEach(btn => {
        const id = btn.dataset.evidenceId;
        if (favorites.includes(id)) {
            btn.textContent = '★ Favorite';
            btn.style.color = '#f59e0b';
        } else {
            btn.textContent = '☆ Add to Favorites';
            btn.style.color = 'inherit';
        }
    });
}

function loadFavorites() {
    const container = document.getElementById('favorites-list');
    if (!container) return;
    
    if (favorites.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">No favorites yet. ★ Add evidence to your favorites!</div>';
        return;
    }
    
    container.innerHTML = favorites.map(id => `
        <div class="favorite-chip">
            <code>${id}</code>
            <button onclick="toggleFavorite('${id}'); loadFavorites();" style="background: none; border: none; cursor: pointer; color: #f59e0b;">✕</button>
        </div>
    `).join('');
}

// ===== EXPORT FUNCTIONALITY =====
function exportAsJSON() {
    const data = {
        timestamp: new Date().toISOString(),
        theme: userPreferences.theme,
        favorites: favorites,
        analytics: analyticsData,
        exportedBy: 'Tracey\'s Sentinel v3.0'
    };
    downloadFile(JSON.stringify(data, null, 2), `sentinel-export-${new Date().getTime()}.json`, 'application/json');
    showNotification('Data exported as JSON ✓', 'success');
}

function exportAsCSV() {
    // Export favorites and analytics
    let csv = 'Field,Value\n';
    csv += `Export Date,"${new Date().toISOString()}"\n`;
    csv += `Theme,"${userPreferences.theme}"\n`;
    csv += `Favorites Count,${favorites.length}\n`;
    csv += `Total Evidence,${analyticsData?.total_evidence || 0}\n`;
    csv += `Active Cases,${analyticsData?.active_cases || 0}\n`;
    csv += `Verified Rate,${analyticsData?.verified_percentage || 0}%\n`;
    
    if (analyticsData?.action_breakdown) {
        csv += '\nAction Type,Count\n';
        Object.entries(analyticsData.action_breakdown).forEach(([type, count]) => {
            csv += `${type},${count}\n`;
        });
    }
    
    downloadFile(csv, `sentinel-export-${new Date().getTime()}.csv`, 'text/csv');
    showNotification('Data exported as CSV ✓', 'success');
}

function downloadFile(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function printDashboard() {
    const printContent = document.querySelector('.tab-section:not([style*="display: none"])');
    if (!printContent) {
        showNotification('No dashboard to print', 'warning');
        return;
    }
    
    const printWindow = window.open('', '', 'height=600,width=800');
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Tracey's Sentinel - Dashboard Print</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 2rem; color: #333; }
                h1, h2 { color: #00d9ff; }
                .stat-card { border: 1px solid #ccc; padding: 1rem; margin: 0.5rem 0; }
                table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
                th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
                th { background: #f0f0f0; }
                code { background: #f5f5f5; padding: 0.25rem 0.5rem; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>Tracey's Sentinel Dashboard</h1>
            <p>Printed: ${new Date().toLocaleString()}</p>
            ${printContent.innerHTML}
        </body>
        </html>
    `);
    printWindow.document.close();
    setTimeout(() => printWindow.print(), 250);
    showNotification('Print dialog opened ✓', 'info');
}

// ===== USER PREFERENCES =====
function openPreferences() {
    const modal = document.getElementById('preferences-modal') || createPreferencesModal();
    modal.style.display = 'block';
}

function createPreferencesModal() {
    const modal = document.createElement('div');
    modal.id = 'preferences-modal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <span class="close" onclick="document.getElementById('preferences-modal').style.display='none';">&times;</span>
            <h2>⚙️ User Preferences</h2>
            
            <div style="margin: 1.5rem 0;">
                <h3>Display</h3>
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer; margin: 0.5rem 0;">
                    <input type="checkbox" id="pref-notifications" ${userPreferences.notifications ? 'checked' : ''} 
                           onchange="userPreferences.notifications = this.checked; savePreferences();">
                    Enable Notifications
                </label>
            </div>
            
            <div style="margin: 1.5rem 0;">
                <h3>Account</h3>
                <button onclick="clearAllData();" style="background: #ef4444; margin-top: 0.5rem;">Clear All Data</button>
                <button onclick="exportAsJSON();" style="background: #06b6d4; margin-top: 0.5rem;">Export as JSON</button>
                <button onclick="exportAsCSV();" style="background: #06b6d4; margin-top: 0.5rem;">Export as CSV</button>
            </div>
            
            <div style="margin-top: 2rem; text-align: right;">
                <button onclick="document.getElementById('preferences-modal').style.display='none';" class="ghost">Close</button>
            </div>
        </div>
    `;
    
    modal.style.cssText = `display: none; position: fixed; z-index: 999; left: 0; top: 0; width: 100%; height: 100%; 
                           background-color: rgba(0,0,0,0.5);`;
    document.body.appendChild(modal);
    return modal;
}

function savePreferences() {
    localStorage.setItem('userPreferences', JSON.stringify(userPreferences));
    showNotification('Preferences saved ✓', 'success');
}

function clearAllData() {
    if (confirm('⚠️ Clear all data? This includes favorites, preferences, and cache. THIS CANNOT BE UNDONE.')) {
        localStorage.clear();
        favorites = [];
        userPreferences = { theme: 'dark', notifications: true };
        applyTheme();
        showNotification('All data cleared', 'warning');
        location.reload();
    }
}

// ===== CASE MANAGEMENT =====
async function loadCase() {
    const caseIdInput = document.getElementById('case-id-input');
    const caseId = caseIdInput.value.trim();
    
    if (!caseId) {
        showNotification('Please enter a case ID', 'warning');
        return;
    }

    try {
        const response = await fetch(`/case/${caseId}`);
        if (!response.ok) {
            showNotification('Case not found', 'error');
            document.getElementById('case-results').innerHTML = `
                <div style="background: var(--bg-white); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; text-align: center; color: var(--danger);">
                    Case ID "${caseId}" not found in the system.
                </div>
            `;
            return;
        }

        const caseData = await response.json();
        analyticsData.lastCaseResults = caseData.evidence || [];
        
        const html = `
            <div style="background: var(--bg-white); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;">
                <h3>${caseData.case_id}</h3>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; font-size: 0.9rem;">
                    <div><strong>Status:</strong> ${caseData.status || 'Active'}</div>
                    <div><strong>Opened:</strong> ${new Date(caseData.created_at).toLocaleDateString()}</div>
                    <div><strong>Lead Investigator:</strong> ${caseData.lead_investigator || 'N/A'}</div>
                    <div><strong>Total Evidence Items:</strong> ${(caseData.evidence || []).length}</div>
                </div>
            </div>

            <h3>Evidence Items</h3>
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Evidence ID</th>
                        <th>Description</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="evidence-table">
                    ${(caseData.evidence || []).length === 0 ? '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No evidence items for this case</td></tr>' : ''}
                </tbody>
            </table>
            <div id="case-pagination"></div>
        `;
        
        document.getElementById('case-results').innerHTML = html;
        
        if (caseData.evidence && caseData.evidence.length > 0) {
            currentPage.cases = 1;
            renderPaginatedResults(caseData.evidence, 'cases');
        }
        
        showNotification(`Loaded case ${caseId} with ${(caseData.evidence || []).length} evidence items ✓`, 'success');
    } catch (e) {
        console.error('Case load error:', e);
        showNotification('Error loading case: ' + e.message, 'error');
    }
}
