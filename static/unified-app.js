/* Tracey's Sentinel - Unified App Navigation & Page Management */

// Page HTML templates
const PAGE_TEMPLATES = {
    dashboard: `
        <div class="dashboard-grid">
            <!-- Key Metrics Row -->
            <div class="metric-card">
                <div class="metric-label">Total Evidence</div>
                <div class="metric-value" id="metric-total-evidence">0</div>
                <div class="metric-change positive">↑ 12% this month</div>
                <div class="metric-icon"><i class="bi bi-collection"></i></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Active Cases</div>
                <div class="metric-value" id="metric-active-cases">0</div>
                <div class="metric-change positive">↑ 8% this month</div>
                <div class="metric-icon"><i class="bi bi-folder-check"></i></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Pending Endorsements</div>
                <div class="metric-value" id="metric-pending-endorsements">0</div>
                <div class="metric-change negative">↑ 3 awaiting</div>
                <div class="metric-icon"><i class="bi bi-hourglass-split"></i></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Chain Integrity</div>
                <div class="metric-value">100%</div>
                <div class="metric-change positive">All verified</div>
                <div class="metric-icon"><i class="bi bi-shield-check"></i></div>
            </div>
        </div>

        <!-- Compliance Overview -->
        <div class="card dashboard-col-full">
            <div class="card-header">
                <i class="bi bi-clipboard-check"></i>
                Compliance Program Overview
            </div>
            <div class="card-body">
                <ul class="nav nav-tabs mb-4" role="tablist">
                    <li class="nav-item">
                        <a class="nav-link active" data-bs-toggle="tab" href="#overview-tab">Overview</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-bs-toggle="tab" href="#controls-tab">Controls</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-bs-toggle="tab" href="#frameworks-tab">Frameworks</a>
                    </li>
                </ul>

                <div class="tab-content">
                    <div id="overview-tab" class="tab-pane fade show active">
                        <div class="row">
                            <div class="col-md-8">
                                <div class="progress-item">
                                    <div class="progress-info">
                                        <div class="progress-label">Access Control & Authorization</div>
                                        <div class="progress-bar">
                                            <div class="progress-fill" style="width: 78%;"></div>
                                        </div>
                                    </div>
                                    <div class="progress-percentage">78%</div>
                                </div>
                                <div class="progress-item">
                                    <div class="progress-info">
                                        <div class="progress-label">Infrastructure Security</div>
                                        <div class="progress-bar">
                                            <div class="progress-fill" style="width: 45%;"></div>
                                        </div>
                                    </div>
                                    <div class="progress-percentage">45%</div>
                                </div>
                                <div class="progress-item">
                                    <div class="progress-info">
                                        <div class="progress-label">Data Management & Protection</div>
                                        <div class="progress-bar">
                                            <div class="progress-fill" style="width: 92%;"></div>
                                        </div>
                                    </div>
                                    <div class="progress-percentage">92%</div>
                                </div>
                            </div>
                            <div class="col-md-4 d-flex align-items-center justify-content-center">
                                <div style="text-align: center;">
                                    <div style="font-size: 3rem; font-weight: 700; color: var(--primary-color);">73%</div>
                                    <div style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.5rem;">Overall Compliance</div>
                                    <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem;">65/89 controls passing</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="controls-tab" class="tab-pane fade">
                        <div class="row">
                            <div class="col-12 mb-3">
                                <span class="badge badge-success">8 Passing</span>
                                <span class="badge badge-warning">2 Needs work</span>
                                <span class="badge badge-danger">3 Failing</span>
                            </div>
                            <div class="col-12">
                                <h6>Control Grid</h6>
                                <div class="control-grid">
                                    ${Array(20).fill().map((_, i) => {
                                        const status = i % 5 === 0 ? 'failing' : i % 3 === 0 ? 'pending' : 'passing';
                                        return \`<div class="control-box \${status}" title="Control \${i+1}"></div>\`;
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="frameworks-tab" class="tab-pane fade">
                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="card border-0 bg-light">
                                    <div class="card-body">
                                        <h6><i class="bi bi-check-circle text-success"></i> ISO 27001</h6>
                                        <p class="text-muted small mb-2">Information Security Management</p>
                                        <div class="progress-item">
                                            <div class="progress-info">
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width: 89%;"></div>
                                                </div>
                                            </div>
                                            <div class="progress-percentage">89%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card border-0 bg-light">
                                    <div class="card-body">
                                        <h6><i class="bi bi-check-circle text-success"></i> SOC 2 Type 2</h6>
                                        <p class="text-muted small mb-2">Security, Availability, Processing Integrity</p>
                                        <div class="progress-item">
                                            <div class="progress-info">
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width: 76%;"></div>
                                                </div>
                                            </div>
                                            <div class="progress-percentage">76%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="row mt-4">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header">
                        <i class="bi bi-clock-history"></i>
                        Recent Activity
                    </div>
                    <div class="card-body">
                        <div class="activity-feed">
                            <div class="activity-item" style="padding-bottom: 1rem; border-bottom: 1px solid var(--border-color); margin-bottom: 1rem;">
                                <div style="display: flex; gap: 1rem; align-items: flex-start;">
                                    <div style="width: 40px; height: 40px; border-radius: 50%; background-color: var(--primary-light); display: flex; align-items: center; justify-content: center; color: var(--primary-color);">
                                        <i class="bi bi-check-circle"></i>
                                    </div>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 600; color: var(--text-primary);">Evidence Endorsed</div>
                                        <div style="font-size: 0.9rem; color: var(--text-secondary);">Case KPS-2024-001 received endorsement from ODPP</div>
                                        <div style="font-size: 0.85rem; color: var(--text-tertiary); margin-top: 0.25rem;">2 hours ago</div>
                                    </div>
                                </div>
                            </div>
                            <div class="activity-item" style="padding-bottom: 1rem; border-bottom: 1px solid var(--border-color); margin-bottom: 1rem;">
                                <div style="display: flex; gap: 1rem; align-items: flex-start;">
                                    <div style="width: 40px; height: 40px; border-radius: 50%; background-color: #FFF3D5; display: flex; align-items: center; justify-content: center; color: #664D03;">
                                        <i class="bi bi-exclamation-circle"></i>
                                    </div>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 600; color: var(--text-primary);">Audit Log Created</div>
                                        <div style="font-size: 0.9rem; color: var(--text-secondary);">System audit performed and logged for compliance review</div>
                                        <div style="font-size: 0.85rem; color: var(--text-tertiary); margin-top: 0.25rem;">1 day ago</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header">
                        <i class="bi bi-info-circle"></i>
                        System Status
                    </div>
                    <div class="card-body">
                        <div style="margin-bottom: 1.5rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span style="font-weight: 600;">Database Connection</span>
                                <span class="badge badge-success">Connected</span>
                            </div>
                        </div>
                        <div style="margin-bottom: 1.5rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span style="font-weight: 600;">Ledger Status</span>
                                <span class="badge badge-success">Valid</span>
                            </div>
                        </div>
                        <div style="margin-bottom: 1.5rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span style="font-weight: 600;">Encryption</span>
                                <span class="badge badge-success">Active</span>
                            </div>
                        </div>
                        <div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span style="font-weight: 600;">Last Backup</span>
                                <span class="badge badge-info">2 hours ago</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,

    cases: `
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-folder-check"></i> Case Management</span>
                <button class="btn btn-sm btn-primary"><i class="bi bi-plus-circle"></i> New Case</button>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>Case ID</th>
                                <th>Title</th>
                                <th>Evidence Count</th>
                                <th>Status</th>
                                <th>Created Date</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>KPS-2024-001</strong></td>
                                <td>Traffic Incident Investigation</td>
                                <td>12</td>
                                <td><span class="badge badge-success">Active</span></td>
                                <td>2024-01-15</td>
                                <td><a href="#" class="btn btn-sm btn-outline-secondary">View</a></td>
                            </tr>
                            <tr>
                                <td><strong>KPS-2024-002</strong></td>
                                <td>Property Crime Investigation</td>
                                <td>8</td>
                                <td><span class="badge badge-success">Active</span></td>
                                <td>2024-01-18</td>
                                <td><a href="#" class="btn btn-sm btn-outline-secondary">View</a></td>
                            </tr>
                            <tr>
                                <td><strong>KPS-2024-003</strong></td>
                                <td>Fraud Investigation</td>
                                <td>15</td>
                                <td><span class="badge badge-warning">In Review</span></td>
                                <td>2024-02-01</td>
                                <td><a href="#" class="btn btn-sm btn-outline-secondary">View</a></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `,

    evidence: `
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-collection"></i> Evidence Inventory</span>
                <button class="btn btn-sm btn-primary"><i class="bi bi-plus-circle"></i> Add Evidence</button>
            </div>
            <div class="card-body">
                <div class="dashboard-grid">
                    <div class="metric-card">
                        <div class="metric-label">Total Evidence Items</div>
                        <div class="metric-value">1,247</div>
                        <div class="metric-icon"><i class="bi bi-collection"></i></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Encrypted</div>
                        <div class="metric-value">100%</div>
                        <div class="metric-icon"><i class="bi bi-lock"></i></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Last 24h Intake</div>
                        <div class="metric-value">23</div>
                        <div class="metric-icon"><i class="bi bi-upload"></i></div>
                    </div>
                </div>
            </div>
        </div>
    `,

    compliance: `
        <div class="card">
            <div class="card-header">
                <i class="bi bi-shield-check"></i>
                Compliance Framework Status
            </div>
            <div class="card-body">
                <ul class="nav nav-tabs mb-4" role="tablist">
                    <li class="nav-item">
                        <a class="nav-link active" data-bs-toggle="tab" href="#iso-tab">ISO 27001</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-bs-toggle="tab" href="#soc2-tab">SOC 2 Type 2</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-bs-toggle="tab" href="#hipaa-tab">HIPAA</a>
                    </li>
                </ul>

                <div class="tab-content">
                    <div id="iso-tab" class="tab-pane fade show active">
                        <h6>ISO 27001 - Information Security Management</h6>
                        <div class="progress-item mt-3">
                            <div class="progress-info">
                                <div class="progress-label">A.5 - Organizational Controls</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: 100%;"></div>
                                </div>
                            </div>
                            <div class="progress-percentage">100%</div>
                        </div>
                        <div class="progress-item">
                            <div class="progress-info">
                                <div class="progress-label">A.6 - People Controls</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: 75%;"></div>
                                </div>
                            </div>
                            <div class="progress-percentage">75%</div>
                        </div>
                        <div class="progress-item">
                            <div class="progress-info">
                                <div class="progress-label">A.7 - Technology Controls</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: 92%;"></div>
                                </div>
                            </div>
                            <div class="progress-percentage">92%</div>
                        </div>
                    </div>

                    <div id="soc2-tab" class="tab-pane fade">
                        <h6>SOC 2 Type 2 - Security, Availability, Processing Integrity</h6>
                        <p class="text-muted">SOC 2 Type 2 audit scheduled for Q3 2024</p>
                    </div>

                    <div id="hipaa-tab" class="tab-pane fade">
                        <h6>HIPAA - Health Insurance Portability and Accountability Act</h6>
                        <p class="text-muted">Review compliance requirements for healthcare evidence</p>
                    </div>
                </div>
            </div>
        </div>
    `,

    audit: `
        <div class="card">
            <div class="card-header">
                <i class="bi bi-shield-lock"></i>
                Audit Log
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Actor</th>
                                <th>Action</th>
                                <th>Resource</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>2024-02-15 14:32:10</td>
                                <td>officer1@lapd.gov</td>
                                <td>EVIDENCE_INTAKE</td>
                                <td>EV-2024-001-A</td>
                                <td><span class="badge badge-success">SUCCESS</span></td>
                            </tr>
                            <tr>
                                <td>2024-02-15 14:15:43</td>
                                <td>analyst1@odpp.gov</td>
                                <td>ENDORSEMENT</td>
                                <td>EV-2024-001-A</td>
                                <td><span class="badge badge-success">SUCCESS</span></td>
                            </tr>
                            <tr>
                                <td>2024-02-15 13:42:15</td>
                                <td>judge1@judiciary.gov</td>
                                <td>VERIFICATION</td>
                                <td>EV-2024-001-A</td>
                                <td><span class="badge badge-success">SUCCESS</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `
};

// Initialize page navigation
document.addEventListener('DOMContentLoaded', function() {
    // Setup nav link clicks
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.getAttribute('data-page');
            if (page) {
                loadPage(page);
            }
        });
    });

    // Load default dashboard
    loadPage('dashboard');

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');
            const newMode = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            localStorage.setItem('theme', newMode);
        });
    }

    // Logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to logout?')) {
                // Clear auth and redirect
                localStorage.removeItem('auth_token');
                window.location.href = '/auth.html';
            }
        });
    }

    // Load user info
    loadUserInfo();
});

function loadPage(pageName) {
    const pageContainer = document.getElementById('page-container');
    const template = PAGE_TEMPLATES[pageName] || '<div>Page not found</div>';
    
    pageContainer.innerHTML = template;

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-page') === pageName) {
            link.classList.add('active');
        }
    });

    // Update page title
    const titles = {
        'dashboard': { title: 'Dashboard', subtitle: 'Welcome back' },
        'cases': { title: 'Cases', subtitle: 'Manage all cases' },
        'evidence': { title: 'Evidence', subtitle: 'Evidence inventory' },
        'compliance': { title: 'Compliance', subtitle: 'Compliance frameworks' },
        'audit': { title: 'Audit Logs', subtitle: 'System audit trail' }
    };

    const pageInfo = titles[pageName] || { title: 'Page', subtitle: '' };
    document.getElementById('page-title').textContent = pageInfo.title;
    document.getElementById('page-subtitle').textContent = pageInfo.subtitle;
}

function loadUserInfo() {
    // Try to get user info from API
    const token = localStorage.getItem('auth_token');
    if (token) {
        // Fetch user info
        fetch('/auth/users', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(r => r.json())
        .then(data => {
            if (data.users && data.users.length > 0) {
                const user = data.users[0];
                document.getElementById('sidebar-user-name').textContent = user.user_id || 'User';
            }
        })
        .catch(e => console.log('User info could not be loaded'));
    }
}
