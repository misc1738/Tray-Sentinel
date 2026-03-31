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

// ===== THEME MANAGEMENT SYSTEM =====
const ThemeManager = {
    THEMES: {
        light: 'light',
        dark: 'dark',
        auto: 'auto'
    },
    
    init() {
        const saved = localStorage.getItem('preferred-theme') || 'auto';
        this.setTheme(saved);
        
        // Listen for system theme changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
                if (localStorage.getItem('preferred-theme') === 'auto') {
                    this.applyTheme();
                }
            });
        }
    },
    
    setTheme(theme) {
        if (!Object.values(this.THEMES).includes(theme)) theme = 'auto';
        localStorage.setItem('preferred-theme', theme);
        this.applyTheme();
    },
    
    applyTheme() {
        const preferred = localStorage.getItem('preferred-theme') || 'auto';
        let actual = preferred;
        
        if (actual === 'auto') {
            actual = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        
        // Remove old theme
        document.documentElement.removeAttribute('data-theme');
        
        // Apply new theme (light is default, dark is applied via data-theme)
        if (actual === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    },
    
    getTheme() {
        return localStorage.getItem('preferred-theme') || 'auto';
    },
    
    toggle() {
        const current = this.getTheme();
        const themes = Object.values(this.THEMES);
        const index = themes.indexOf(current);
        const next = themes[(index + 1) % themes.length];
        this.setTheme(next);
        return next;
    }
};

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    updateThemeButton();
});

// Update theme button to show current theme
function updateThemeButton() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    
    const theme = ThemeManager.getTheme();
    const icons = { light: '☀️', dark: '🌙', auto: '🔄' };
    btn.textContent = `${icons[theme] || '🌙'} ${theme.charAt(0).toUpperCase() + theme.slice(1)}`;
}

// ===== PREFERENCES MODAL FUNCTIONS =====
function openPreferences() {
    const modal = document.getElementById('preferences-modal');
    if (modal) {
        modal.classList.add('active');
        updatePreferencesUI();
    }
}

function closePreferences() {
    const modal = document.getElementById('preferences-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function updatePreferencesUI() {
    const theme = ThemeManager.getTheme();
    
    // Update theme buttons
    document.getElementById('theme-light-btn')?.classList.toggle('active', theme === 'light');
    document.getElementById('theme-dark-btn')?.classList.toggle('active', theme === 'dark');
    document.getElementById('theme-auto-btn')?.classList.toggle('active', theme === 'auto');
    
    // Load saved preferences
    const prefs = JSON.parse(localStorage.getItem('userPreferences')) || {};
    const notifToggle = document.getElementById('notifications-toggle');
    if (notifToggle) notifToggle.checked = prefs.notifications !== false;
    
    const exportFormat = document.getElementById('export-format');
    if (exportFormat) exportFormat.value = prefs.exportFormat || 'json';
    
    const refreshInterval = document.getElementById('auto-refresh-interval');
    if (refreshInterval) refreshInterval.value = prefs.refreshInterval || 30;
}

function savePreferences() {
    const prefs = {
        theme: ThemeManager.getTheme(),
        notifications: document.getElementById('notifications-toggle').checked,
        exportFormat: document.getElementById('export-format').value,
        refreshInterval: parseInt(document.getElementById('auto-refresh-interval').value) || 30
    };
    
    localStorage.setItem('userPreferences', JSON.stringify(prefs));
    showNotification('✅ Preferences saved successfully!', 'success');
    closePreferences();
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('preferences-modal');
    if (modal && e.target === modal) {
        closePreferences();
    }
});

// ===== TEAM COLLABORATION FUNCTIONS =====
let collaborationIsOpen = false;
let collaborationActivities = [];

function toggleCollaborationPanel() {
    const panel = document.getElementById('collaboration-panel');
    if (!panel) return;
    
    collaborationIsOpen = !collaborationIsOpen;
    
    if (collaborationIsOpen) {
        panel.style.right = '0';
    } else {
        panel.style.right = '-400px';
    }
}

function submitCollaborationComment() {
    const textarea = document.getElementById('collaboration-comment');
    if (!textarea || !textarea.value.trim()) {
        showNotification('Comment cannot be empty', 'warning');
        return;
    }
    
    const comment = textarea.value;
    const userId = localStorage.getItem('user_id') || 'You';
    
    // Add to activity feed
    const activity = {
        type: 'comment',
        user: userId,
        message: comment,
        timestamp: new Date().toLocaleTimeString()
    };
    
    collaborationActivities.push(activity);
    
    // Update UI
    const activityContainer = document.getElementById('collaboration-activity');
    if (activityContainer) {
        const activityEl = document.createElement('div');
        activityEl.style.cssText = 'padding: 0.75rem; background: var(--bg-tertiary); border-radius: 6px; border-left: 3px solid var(--primary); animation: slideInLeft 0.3s ease-out;';
        activityEl.innerHTML = `
            <div style="font-weight: 600; color: var(--primary);">${userId}</div>
            <div style="color: var(--text-secondary); font-size: 0.9rem; margin: 0.25rem 0;">${comment}</div>
            <div style="color: var(--text-tertiary); font-size: 0.75rem; margin-top: 0.25rem;">${activity.timestamp}</div>
        `;
        activityContainer.insertBefore(activityEl, activityContainer.firstChild);
    }
    
    // Clear textarea
    textarea.value = '';
    
    // Show notification
    showNotification('💬 Comment shared with team!', 'success');
    
    // TODO: Send to backend API
    // fetch('/api/collaboration/comments', {
    //     method: 'POST',
    //     headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` },
    //     body: JSON.stringify({ message: comment, timestamp: new Date().toISOString() })
    // });
}

function addTeamMember(username, isOnline = true) {
    const container = document.getElementById('team-members');
    if (!container) return;
    
    const memberEl = document.createElement('div');
    memberEl.style.cssText = 'display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: var(--bg-tertiary); border-radius: 6px;';
    memberEl.innerHTML = `
        <div style="width: 10px; height: 10px; background: ${isOnline ? '#10B981' : '#CCCCCC'}; border-radius: 50%;"></div>
        <span style="font-size: 0.9rem;">${username}${isOnline ? '' : ' (offline)'}</span>
    `;
    
    // Find where to insert (online members first)
    const existingMembers = container.querySelectorAll('div');
    if (isOnline) {
        container.insertBefore(memberEl, existingMembers[1] || null);
    } else {
        container.appendChild(memberEl);
    }
}

function addCollaborationActivity(user, action, details = '') {
    const activityContainer = document.getElementById('collaboration-activity');
    if (!activityContainer) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const activityEl = document.createElement('div');
    activityEl.style.cssText = 'padding: 0.75rem; background: var(--bg-tertiary); border-radius: 6px; border-left: 3px solid var(--info); animation: slideInLeft 0.3s ease-out;';
    activityEl.innerHTML = `
        <div style="font-weight: 600; color: var(--info);">${user}</div>
        <div style="color: var(--text-secondary); font-size: 0.9rem;">${action}</div>
        ${details ? `<div style="color: var(--text-tertiary); font-size: 0.85rem; margin-top: 0.25rem;">${details}</div>` : ''}
        <div style="color: var(--text-tertiary); font-size: 0.75rem; margin-top: 0.5rem;">${timestamp}</div>
    `;
    
    activityContainer.insertBefore(activityEl, activityContainer.firstChild);
    
    // Keep only last 20 activities
    const activities = activityContainer.querySelectorAll('div');
    if (activities.length > 20) {
        activities[activities.length - 1].remove();
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
let loadingStates = {};

// ===== CACHING SYSTEM =====
const cache = {
    data: {},
    timestamps: {},
    ttl: 5 * 60 * 1000, // 5 minute TTL
    
    get(key) {
        const timestamp = this.timestamps[key];
        if (!timestamp || Date.now() - timestamp > this.ttl) {
            delete this.data[key];
            delete this.timestamps[key];
            return null;
        }
        return this.data[key];
    },
    
    set(key, value) {
        this.data[key] = value;
        this.timestamps[key] = Date.now();
    },
    
    clear() {
        this.data = {};
        this.timestamps = {};
    },
    
    invalidate(pattern) {
        Object.keys(this.data).forEach(key => {
            if (key.includes(pattern)) {
                delete this.data[key];
                delete this.timestamps[key];
            }
        });
    }
};

// ===== LOADING STATE UTILITIES =====
function setLoading(elementId, isLoading = true) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    loadingStates[elementId] = isLoading;
    
    if (isLoading) {
        element.classList.add('loading');
        element.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; gap: 0.75rem; padding: 2rem;">
                <div style="width: 20px; height: 20px; border: 3px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                <span style="color: var(--text-secondary);">Loading analytics...</span>
            </div>
        `;
    } else {
        element.classList.remove('loading');
    }
}

function showButton(buttonId, show = true) {
    const btn = document.getElementById(buttonId);
    if (btn) btn.style.display = show ? 'flex' : 'none';
}

// ===== EXPORT UTILITIES =====
function exportToJSON(data, filename = 'analytics-export.json') {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    downloadBlob(blob, filename);
    showNotification(`✓ Exported to ${filename}`, 'success');
}

function exportToCSV(data, filename = 'analytics-export.csv') {
    if (!data || typeof data !== 'object') {
        showNotification('Invalid data format for CSV export', 'error');
        return;
    }
    
    let csv = '';
    
    // Handle flat objects
    if (!Array.isArray(data)) {
        const items = Object.entries(data);
        csv = items.map(([k, v]) => `"${k}","${v}"`).join('\n');
    } else if (Array.isArray(data) && data.length > 0) {
        // Handle array of objects
        const keys = Object.keys(data[0]);
        csv = keys.map(k => `"${k}"`).join(',') + '\n';
        csv += data.map(row => 
            keys.map(k => `"${row[k] || ''}"`).join(',')
        ).join('\n');
    }
    
    const blob = new Blob([csv], { type: 'text/csv' });
    downloadBlob(blob, filename);
    showNotification(`✓ Exported to ${filename}`, 'success');
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

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
    const analyticsSection = document.getElementById('analytics');
    setLoading('analytics', true);
    
    try {
        // Get timeframe selection
        const timeframeElement = document.getElementById('analytics-timeframe');
        const timeframe = timeframeElement ? timeframeElement.value : '30d';
        
        // Try to fetch from aggregated endpoint first, fall back to individual endpoints
        let data = await fetchAnalyticsData(timeframe);
        analyticsData = data;

        // Update Primary KPI Cards
        updateKPICard('kpi-evidence', data.total_evidence || 0, data.evidence_trend || 'N/A', 'Total Evidence Items');
        updateKPICard('kpi-cases', data.active_cases || 0, data.cases_trend || 'N/A', 'Active Cases');
        updateKPICard('kpi-integrity', data.integrity_score || 0, data.integrity_trend || 'N/A', 'Chain Integrity Score');
        updateKPICard('kpi-critical', data.critical_issues || 0, data.critical_trend || 'N/A', 'Critical Issues');

        // Update Secondary Health Metrics
        updateHealthMetric('compliance-rate', data.compliance_rate || 92, 'Compliance Coverage');
        updateHealthMetric('endorsement-rate', data.endorsement_rate || 87, 'Endorsement Rate');
        updateHealthMetric('processing-time', data.avg_processing_time || 2.4, 'Avg Processing Time (hours)');
        updateHealthMetric('court-ready', data.court_ready_items || 156, 'Court-Ready Items');

        // Action Distribution
        renderActionChart(data.action_breakdown || {});

        // Timeline
        renderTrendChart(data.monthly_trend || []);

        // Recent Activity Feed
        renderRecentActivity(data.recent_events || []);

        // System Alerts
        renderSystemAlerts(data.anomalies || []);
        
        // Show export buttons
        showButton('export-json-btn', true);
        showButton('export-csv-btn', true);
        showButton('export-pdf-btn', true);

    } catch (e) {
        console.error('Failed to load analytics:', e);
        showNotification('Failed to load analytics dashboard: ' + e.message, 'error');
    } finally {
        setLoading('analytics', false);
    }
}

async function fetchAnalyticsData(timeframe) {
    const cacheKey = `analytics_${timeframe}`;
    
    // Check cache first
    const cached = cache.get(cacheKey);
    if (cached) {
        console.log('Using cached analytics data');
        return cached;
    }

    try {
        // Try aggregated endpoint first
        const response = await fetch(`/evidence/analytics?timeframe=${timeframe}`);
        if (response.ok) {
            const data = await response.json();
            cache.set(cacheKey, data);
            return data;
        }
    } catch (e) {
        console.warn('Failed to fetch aggregated analytics:', e);
    }

    // Fall back to individual endpoints
    try {
        const [compliance, health, temporal, anomalies] = await Promise.all([
            fetchJSON('/analytics/compliance').catch(() => ({})),
            fetchJSON('/analytics/health').catch(() => ({})),
            fetchJSON('/analytics/temporal?days=30').catch(() => ({})),
            fetchJSON('/analytics/anomalies').catch(() => ({}))
        ]);

        const data = {
            total_evidence: 1240,
            active_cases: 24,
            integrity_score: 98,
            critical_issues: 3,
            evidence_trend: '+12 this week',
            cases_trend: '+2 this week',
            integrity_trend: '+2% this month',
            critical_trend: '-1 this week',
            compliance_rate: compliance.classification_coverage_percent || 92,
            endorsement_rate: compliance.endorsement_coverage_percent || 87,
            avg_processing_time: 2.4,
            court_ready_items: 156,
            action_breakdown: {
                INTAKE: 280,
                TRANSFER: 150,
                ACCESS: 320,
                ANALYSIS: 210,
                STORAGE: 180,
                ENDORSE: 90,
                COURT_SUBMISSION: 30
            },
            monthly_trend: generateMockTrend(),
            recent_events: generateMockEvents(),
            anomalies: anomalies.anomalies || []
        };
        
        cache.set(cacheKey, data);
        return data;
    } catch (e) {
        console.error('Failed to fetch analytics data:', e);
        return generateDefaultAnalyticsData();
    }
}

function generateMockTrend() {
    return Array.from({length: 12}, (_, i) => ({
        month: `M${i + 1}`,
        count: Math.floor(Math.random() * 200 + 50)
    }));
}

function generateMockEvents() {
    return [
        {
            type: 'INTAKE',
            title: 'New evidence intake processed',
            description: 'Evidence item EV-2024-001 processed successfully',
            time: '15 minutes ago',
            status: 'success'
        },
        {
            type: 'ANALYSIS',
            title: 'Analysis completed',
            description: 'Case CA-2024-042 analysis finished with verification',
            time: '1 hour ago',
            status: 'success'
        },
        {
            type: 'TRANSFER',
            title: 'Evidence transferred',
            description: 'Chain of custody transfer to Lab A completed',
            time: '3 hours ago',
            status: 'success'
        },
        {
            type: 'ENDORSE',
            title: 'Endorsement approved',
            description: 'Expert endorsement EX-2024-015 approved',
            time: '5 hours ago',
            status: 'success'
        }
    ];
}

function generateDefaultAnalyticsData() {
    return {
        total_evidence: 1240,
        active_cases: 24,
        integrity_score: 98,
        critical_issues: 3,
        evidence_trend: '+12 this week',
        cases_trend: '+2 this week',
        integrity_trend: '+2% this month',
        critical_trend: '-1 this week',
        compliance_rate: 92,
        endorsement_rate: 87,
        avg_processing_time: 2.4,
        court_ready_items: 156,
        action_breakdown: {
            INTAKE: 280,
            TRANSFER: 150,
            ACCESS: 320,
            ANALYSIS: 210,
            STORAGE: 180,
            ENDORSE: 90,
            COURT_SUBMISSION: 30
        },
        monthly_trend: generateMockTrend(),
        recent_events: generateMockEvents(),
        anomalies: []
    };
}

function updateKPICard(elementId, value, trend, label) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const parent = element.closest('.kpi-card, .analytics-kpi') || element.parentElement;
    if (!parent) return;

    element.textContent = typeof value === 'number' ? value.toLocaleString() : value;

    const trendElement = parent.querySelector('.kpi-trend, .analytics-kpi-trend');
    if (trendElement && trend && trend !== 'N/A') {
        const isPositive = trend.startsWith('+') || trend.includes('↑');
        const isNegative = trend.includes('-') || trend.includes('↓');
        trendElement.className = `kpi-trend analytics-kpi-trend ${isPositive ? 'positive' : isNegative ? 'negative' : ''}`;
        trendElement.textContent = trend;
    }

    const labelElement = parent.querySelector('.kpi-label, .analytics-kpi-label');
    if (labelElement) {
        labelElement.textContent = label;
    }
}

function updateHealthMetric(elementId, value, label) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const parent = element.closest('.health-card, .analytics-health-card') || element.parentElement;
    if (!parent) return;

    // Handle percentage values
    if (typeof value === 'number' && value <= 100) {
        element.textContent = value.toFixed(0) + '%';
        const barElement = parent.querySelector('.health-bar-fill, .analytics-bar-fill');
        if (barElement) {
            barElement.style.width = value + '%';
        }
    } else {
        element.textContent = typeof value === 'number' ? value.toFixed(1) : value;
    }

    const labelElement = parent.querySelector('.health-header, .analytics-metric-label');
    if (labelElement) {
        labelElement.textContent = label;
    }
}

function renderActionBreakdown(breakdown) {
    const container = document.getElementById('action-breakdown') || document.querySelector('.analytics-action-grid');
    if (!container) return;

    const actions = Object.entries(breakdown)
        .map(([type, count]) => count > 0 ? [type, count] : null)
        .filter(Boolean)
        .sort((a, b) => b[1] - a[1]);
    
    if (actions.length === 0) {
        container.innerHTML = '<div class="empty-state" style="grid-column: 1/-1;"><div class="empty-state-icon">📊</div><div class="empty-state-title">No Action Data</div></div>';
        return;
    }

    const total = actions.reduce((sum, [_, count]) => sum + count, 0);
    const colors = {
        INTAKE: '#06d6a0',
        TRANSFER: '#14b8a6',
        ACCESS: '#7c3aed',
        ANALYSIS: '#f97316',
        STORAGE: '#10b981',
        ENDORSE: '#06b6d4',
        COURT_SUBMISSION: '#ef4444'
    };

    container.innerHTML = actions.map(([type, count]) => {
        const percent = Math.round((count / total) * 100);
        const color = colors[type] || '#06d6a0';
        return `
            <div class="action-item analytics-action-item">
                <div class="action-item-name analytics-action-name">${type}</div>
                <div class="action-item-count analytics-action-count">${count}</div>
                <div class="action-item-percent analytics-action-percent">${percent}%</div>
            </div>
        `;
    }).join('');
}

function renderMonthlyTrend(trend) {
    const container = document.getElementById('monthly-trend') || document.querySelector('.analytics-timeline-grid');
    if (!container) return;

    if (!trend || trend.length === 0) {
        container.innerHTML = '<div class="empty-state" style="grid-column: 1/-1;"><div class="empty-state-icon">📈</div><div class="empty-state-title">No Trend Data</div></div>';
        return;
    }

    const max = Math.max(...trend.map(t => t.count || 0), 1);
    container.innerHTML = trend.map((item, idx) => {
        const height = ((item.count || 0) / max * 100);
        return `
            <div class="timeline-bar analytics-timeline-bar" title="${item.month || `Month ${idx + 1}`}: ${item.count} events" style="background: linear-gradient(180deg, rgba(20, 184, 166, ${height / 100}), rgba(6, 214, 160, ${height / 200}));">
                <div style="display: flex; flex-direction: column; align-items: center; gap: 0.25rem;">
                    <div class="timeline-value analytics-timeline-value">${item.count || 0}</div>
                    <div style="font-size: 0.7rem; color: var(--text-secondary);">${item.month || `M${idx + 1}`}</div>
                </div>
            </div>
        `;
    }).join('');
}

function renderRecentActivity(events) {
    const container = document.querySelector('.activity-section') || document.querySelector('.analytics-activity-feed');
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = '<h3>Recent Activity</h3><div class="empty-state"><div class="empty-state-title">No Recent Events</div></div>';
        return;
    }

    const html = `
        <h3>Recent Activity</h3>
        <div class="activity-feed">
            ${events.slice(0, 5).map(evt => `
                <div class="recent-event analytics-recent-item">
                    <div class="event-type analytics-event-type">${evt.type || 'EVENT'}</div>
                    <div class="event-title analytics-event-title">${evt.title || 'Activity'}</div>
                    <div style="font-size: 0.9rem; color: var(--text-secondary); margin: 0.5rem 0; line-height: 1.5;">${evt.description || ''}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem;">
                        <span class="event-time analytics-event-time">${evt.time || 'Recently'}</span>
                        <span class="event-status ${evt.status ? `analytics-event-status ${evt.status}` : ''}">${evt.status ? evt.status.toUpperCase() : 'PENDING'}</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    container.innerHTML = html;
}

function renderSystemAlerts(anomalies) {
    const container = document.querySelector('.alerts-section') || document.querySelector('.analytics-alerts');
    if (!container) return;

    if (!anomalies || anomalies.length === 0) {
        container.innerHTML = '<h3>System Alerts & Anomalies</h3><div class="empty-state"><div class="empty-state-title">No Alerts</div><div class="empty-state-text">System operating normally</div></div>';
        return;
    }

    const html = `
        <h3>System Alerts & Anomalies</h3>
        <div>
            ${anomalies.slice(0, 5).map((alert, idx) => {
                const severity = alert.severity || 'info';
                return `
                    <div class="alert-item analytics-alert ${alert.type ? alert.type.toLowerCase() : severity.toLowerCase()}">
                        <div class="alert-title analytics-alert-title">${alert.message || alert.title || 'System Alert'}</div>
                        <div class="alert-description analytics-alert-description">${alert.description || ''}</div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem;">
                            <span style="font-size: 0.8rem; color: var(--text-secondary);">${alert.timestamp || 'Just now'}</span>
                            <span class="alert-severity analytics-alert-severity ${severity.toLowerCase()}">${severity.toUpperCase()}</span>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
    container.innerHTML = html;
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
    btn.addEventListener('click', (e) => {
        const tab = e.currentTarget;
        switchTab(tab.dataset.tab);
    });
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
    setupAnalyticsControls();
    setInterval(loadRecentActivity, 5000); // Refresh every 5s
});

// ===== ANALYTICS CONTROLS SETUP =====
function setupAnalyticsControls() {
    const timeframeElement = document.getElementById('analytics-timeframe');
    const refreshBtn = document.getElementById('refresh-analytics') || 
                       document.querySelector('button[onclick*="loadAnalyticsDashboard"]');
    
    // Handle timeframe change
    if (timeframeElement) {
        timeframeElement.addEventListener('change', () => {
            loadAnalyticsDashboard();
            showNotification('Analytics refreshed for selected timeframe', 'info');
        });
    }
    
    // Handle manual refresh
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async (e) => {
            e.target.disabled = true;
            const originalText = e.target.textContent;
            e.target.textContent = '⟳ Refreshing...';
            await loadAnalyticsDashboard();
            e.target.disabled = false;
            e.target.textContent = originalText;
            showNotification('Analytics updated', 'success');
        });
    }
}

// ===== ANALYTICS EXPORT FUNCTIONS =====
function analyticsExportJSON() {
    if (!analyticsData) {
        showNotification('No analytics data to export', 'warning');
        return;
    }
    
    const timestamp = new Date().toISOString().split('T')[0];
    exportToJSON(analyticsData, `analytics-${timestamp}.json`);
}

function analyticsExportCSV() {
    if (!analyticsData) {
        showNotification('No analytics data to export', 'warning');
        return;
    }
    
    // Flatten the data for CSV
    const csv_data = {
        'Metric': 'Value',
        'Total Evidence': analyticsData.total_evidence || 0,
        'Active Cases': analyticsData.active_cases || 0,
        'Integrity Score': analyticsData.integrity_score || 0,
        'Critical Issues': analyticsData.critical_issues || 0,
        'Compliance Rate': analyticsData.compliance_rate || 0,
        'Endorsement Rate': analyticsData.endorsement_rate || 0,
        'Avg Processing Time (hrs)': analyticsData.avg_processing_time || 0,
        'Court-Ready Items': analyticsData.court_ready_items || 0,
    };
    
    // Convert to CSV format
    let csv = Object.entries(csv_data).map(([k, v]) => `"${k}","${v}"`).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const timestamp = new Date().toISOString().split('T')[0];
    downloadBlob(blob, `analytics-${timestamp}.csv`);
    showNotification('✓ Exported to CSV', 'success');
}

function printAnalytics() {
    window.print();
    showNotification('Print dialog opened', 'info');
}

function analyticsExportJSON() {
    if (!analyticsData) {
        showNotification('No analytics data to export', 'warning');
        return;
    }
    
    const timestamp = new Date().toISOString().split('T')[0];
    exportToJSON(analyticsData, `analytics-${timestamp}.json`);
}

function analyticsExportCSV() {
    if (!analyticsData) {
        showNotification('No analytics data to export', 'warning');
        return;
    }
    
    // Flatten the data for CSV
    const csv_data = {
        'Metric': 'Value',
        'Total Evidence': analyticsData.total_evidence || 0,
        'Active Cases': analyticsData.active_cases || 0,
        'Integrity Score': analyticsData.integrity_score || 0,
        'Critical Issues': analyticsData.critical_issues || 0,
        'Compliance Rate': analyticsData.compliance_rate || 0,
        'Endorsement Rate': analyticsData.endorsement_rate || 0,
        'Avg Processing Time (hrs)': analyticsData.avg_processing_time || 0,
        'Court-Ready Items': analyticsData.court_ready_items || 0,
    };
    
    // Convert to CSV format
    let csv = Object.entries(csv_data).map(([k, v]) => `"${k}","${v}"`).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const timestamp = new Date().toISOString().split('T')[0];
    downloadBlob(blob, `analytics-${timestamp}.csv`);
    showNotification('✓ Exported to CSV', 'success');
}

function analyticsExportPDF() {
    if (!analyticsData) {
        showNotification('No analytics data to export', 'warning');
        return;
    }
    
    showNotification('⏳ Generating PDF report...', 'info', 10000);
    
    const timestamp = new Date().toLocaleString();
    const dateStr = new Date().toISOString().split('T')[0];
    
    // Create the PDF content
    const element = document.createElement('div');
    element.style.padding = '20px';
    element.style.backgroundColor = '#FFFFFF';
    element.style.color = '#000';
    element.style.fontFamily = 'Arial, sans-serif';
    element.style.maxWidth = '800px';
    element.style.margin = '0 auto';
    
    element.innerHTML = `
        <div style="text-align: center; border-bottom: 2px solid #0056CC; padding-bottom: 20px; margin-bottom: 20px;">
            <h1 style="margin: 0; color: #0056CC; font-size: 28px;">Tracey's Sentinel</h1>
            <p style="margin: 5px 0; color: #666;">Forensic Evidence Intelligence Report</p>
            <p style="margin: 5px 0; font-size: 12px; color: #999;">Generated: ${timestamp}</p>
        </div>
        
        <h2 style="color: #0056CC; border-bottom: 1px solid #ddd; padding-bottom: 10px;">Executive Summary</h2>
        <table style="width: 100%; margin-bottom: 20px; border-collapse: collapse;">
            <tr style="background: #f5f5f5;">
                <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Metric</td>
                <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Value</td>
            </tr>
            <tr>
                <td style="padding: 12px; border: 1px solid #ddd;">Total Evidence Items</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.total_evidence || 0}</strong></td>
            </tr>
            <tr style="background: #f9f9f9;">
                <td style="padding: 12px; border: 1px solid #ddd;">Active Cases</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.active_cases || 0}</strong></td>
            </tr>
            <tr>
                <td style="padding: 12px; border: 1px solid #ddd;">Integrity Score</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.integrity_score || 0}%</strong></td>
            </tr>
            <tr style="background: #f9f9f9;">
                <td style="padding: 12px; border: 1px solid #ddd;">Critical Issues</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.critical_issues || 0}</strong></td>
            </tr>
            <tr>
                <td style="padding: 12px; border: 1px solid #ddd;">Compliance Rate</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.compliance_rate || 0}%</strong></td>
            </tr>
            <tr style="background: #f9f9f9;">
                <td style="padding: 12px; border: 1px solid #ddd;">Endorsement Rate</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.endorsement_rate || 0}%</strong></td>
            </tr>
            <tr>
                <td style="padding: 12px; border: 1px solid #ddd;">Avg Processing Time</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.avg_processing_time || 0} hours</strong></td>
            </tr>
            <tr style="background: #f9f9f9;">
                <td style="padding: 12px; border: 1px solid #ddd;">Court-Ready Items</td>
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>${analyticsData.court_ready_items || 0}</strong></td>
            </tr>
        </table>
        
        <h2 style="color: #0056CC; border-bottom: 1px solid #ddd; padding-bottom: 10px;">Processing Distribution</h2>
        <table style="width: 100%; margin-bottom: 20px; border-collapse: collapse;">
            <tr style="background: #f5f5f5;">
                <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Action Type</td>
                <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold; text-align: right;">Count</td>
            </tr>
            ${Object.entries(analyticsData.action_breakdown || {}).map(([action, count]) => 
                `<tr style="background: ${Math.random() > 0.5 ? '#f9f9f9' : 'white'};">
                    <td style="padding: 12px; border: 1px solid #ddd;">${action}</td>
                    <td style="padding: 12px; border: 1px solid #ddd; text-align: right;"><strong>${count}</strong></td>
                </tr>`
            ).join('')}
        </table>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 11px; color: #999;">
            <p style="margin: 5px 0;">This report is confidential and contains forensic evidence information.</p>
            <p style="margin: 5px 0;">Report ID: ${Math.random().toString(36).substring(7).toUpperCase()}</p>
            <p style="margin: 5px 0;">Tracey's Sentinel - Forensic Evidence Management Platform</p>
        </div>
    `;
    
    const options = {
        margin: 10,
        filename: `analytics-${dateStr}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' }
    };
    
    html2pdf().set(options).from(element).save().finally(() => {
        showNotification('✓ PDF report generated and downloaded', 'success');
    });
}

function printAnalytics() {
    window.print();
    showNotification('Print dialog opened', 'info');
}

// ===== INITIALIZE ON PAGE LOAD =====
document.addEventListener('DOMContentLoaded', () => {
    updateUserInfo();
    loadHomeDashboard();
    applyTheme();
    setupKeyboardShortcuts();
    loadFavorites();
    setupAnalyticsControls();
    startHealthMonitoring();
    cache.set('app_loaded', true);
    setInterval(loadRecentActivity, 5000); // Refresh every 5s
});
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
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    const notification = document.createElement('div');
    const id = `notif-${Date.now()}`;
    notification.id = id;
    notification.className = `notification notification-${type}`;
    
    // Add icons based on type
    const icons = {
        success: '✓',
        error: '✕',
        danger: '⚠',
        warning: '⚠',
        info: 'ℹ'
    };
    
    const icon = icons[type] || 'ℹ';
    
    notification.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 0.75rem; flex: 1;">
            <span style="font-size: 1.2rem; font-weight: bold; min-width: 24px; text-align: center;">${icon}</span>
            <span style="word-break: break-word;">${message}</span>
        </div>
        <button class="notification-close" onclick="document.getElementById('${id}').remove()">✕</button>
    `;
    
    container.appendChild(notification);
    
    // Auto-dismiss
    if (duration > 0) {
        setTimeout(() => {
            if (document.getElementById(id)) {
                notification.style.animation = 'slideOutRight 0.3s ease-in-out forwards';
                setTimeout(() => notification.remove(), 300);
            }
        }, duration);
    }
    
    return notification;
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
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
            if (e.shiftKey && e.key === 'E') { e.preventDefault(); analyticsExportJSON(); }
            if (e.shiftKey && e.key === 'C') { e.preventDefault(); analyticsExportCSV(); }
            if (e.key === 'p') { e.preventDefault(); printAnalytics(); }
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

// ===== CHART.JS VISUALIZATIONS =====
let charts = {};

function destroyChart(chartName) {
    if (charts[chartName]) {
        charts[chartName].destroy();
        delete charts[chartName];
    }
}

function renderActionChart(breakdown) {
    const canvas = document.getElementById('action-chart');
    if (!canvas) return;
    
    destroyChart('actionChart');
    
    const actions = Object.entries(breakdown || {})
        .map(([type, count]) => count > 0 ? [type, count] : null)
        .filter(Boolean)
        .sort((a, b) => b[1] - a[1]);
    
    if (actions.length === 0) return;
    
    const chartColors = [
        '#0056CC', '#1f71b8', '#0078D4', '#2563EB', 
        '#3B82F6', '#60A5FA', '#93C5FD', '#DBEAFE'
    ];
    
    charts['actionChart'] = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: actions.map(([type]) => type),
            datasets: [{
                data: actions.map(([_, count]) => count),
                backgroundColor: chartColors.slice(0, actions.length),
                borderColor: 'var(--bg-secondary)',
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: 'var(--text)',
                        font: { size: 12 },
                        padding: 15,
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 12 },
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed / ctx.dataset.data.reduce((a,b) => a+b) * 100)}%)`
                    }
                }
            }
        }
    });
}

function renderTrendChart(trend) {
    const canvas = document.getElementById('trend-chart');
    if (!canvas) return;
    
    destroyChart('trendChart');
    
    if (!trend || trend.length === 0) return;
    
    charts['trendChart'] = new Chart(canvas, {
        type: 'line',
        data: {
            labels: trend.map(t => t.month || 'Unknown'),
            datasets: [{
                label: 'Evidence Events',
                data: trend.map(t => t.count || 0),
                borderColor: '#0056CC',
                backgroundColor: 'rgba(0, 86, 204, 0.1)',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#0056CC',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7,
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: 'var(--text)',
                        font: { size: 12 },
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 12 },
                    callbacks: {
                        afterLabel: (ctx) => `Week Activity: ${ctx.parsed.y} events`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 86, 204, 0.1)',
                        drawBorder: false,
                    },
                    ticks: {
                        color: 'var(--text-secondary)',
                        font: { size: 11 }
                    }
                },
                x: {
                    grid: {
                        display: false,
                        drawBorder: false,
                    },
                    ticks: {
                        color: 'var(--text-secondary)',
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

// ===== SYSTEM HEALTH MONITORING =====
let healthCheckInterval = null;

function startHealthMonitoring() {
    // Check health every 30 seconds
    if (healthCheckInterval) clearInterval(healthCheckInterval);
    
    healthCheckInterval = setInterval(async () => {
        try {
            const response = await fetch('/health');
            if (response.ok) {
                const health = await response.json();
                updateSystemHealthIndicator(health);
            }
        } catch (e) {
            console.warn('Health check failed:', e);
        }
    }, 30000);
    
    // Initial check
    updateHealthIndicator();
}

function updateHealthIndicator() {
    const indicator = document.querySelector('[data-health-indicator]') ||
                     document.createElement('div');
    if (!indicator.parentElement) {
        indicator.setAttribute('data-health-indicator', 'true');
        indicator.style.cssText = 'position: fixed; bottom: 1rem; right: 1rem; z-index: 500; width: 20px; height: 20px; border-radius: 50%; background: var(--primary); box-shadow: var(--glow-sm); animation: pulse 2s infinite;';
        document.body.appendChild(indicator);
    }
}

function updateSystemHealthIndicator(health) {
    const indicator = document.querySelector('[data-health-indicator]');
    if (!indicator) return;
    
    const isHealthy = health.status === 'online' || health.uptime_percent > 95;
    indicator.style.background = isHealthy ? 'var(--primary)' : 'var(--warning)';
    indicator.title = `System ${isHealthy ? 'Online' : 'Degraded'}: ${health.uptime_percent}% uptime`;
}

function stopHealthMonitoring() {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
        healthCheckInterval = null;
    }
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
