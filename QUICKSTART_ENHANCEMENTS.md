# Tracey's Sentinel - Quick Start Guide for New Features

## Overview

Tracey's Sentinel now includes two powerful new dashboards:
1. **Compliance Dashboard** - Track compliance with 4 major frameworks
2. **Monitoring Dashboard** - Real-time security alerts and metrics

---

## Getting Started

### 1. Start the Application

#### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://localhost:5173`

---

## Using the Compliance Dashboard

### Accessing the Dashboard
1. Click the **🏛️ Compliance** tab in the navigation
2. You'll see the overall compliance posture

### Understanding the Compliance View

#### Overall Compliance Summary (Top Card)
Shows:
- **Compliance Score**: Percentage of passing controls across all frameworks
- **Passing Controls**: Count of controls meeting requirements
- **Total Controls**: Total controls across all frameworks
- **Critical Findings**: Number of critical-level violations
- **Trend**: Is compliance improving, stable, or declining?

#### Framework Cards
For each framework (ISO 27001, SOC 2, HIPAA, PCI DSS):
- **Compliance Percentage**: Visual progress bar
- **Risk Level**: Color-coded status badge
  - 🔴 CRITICAL: Foundation-level failures
  - 🟠 HIGH: Multiple significant gaps
  - 🔵 MEDIUM: Some attention needed
  - 🟢 LOW: Excellent posture
- **Control Breakdown**: Count of Passing/Failing/Needs Changes

#### Viewing Specific Controls
1. Click on a framework card to load its controls
2. See detailed list of each control
3. Status indicators show current compliance level
4. Controls are color-coded by status

### Framework Focus

#### ISO 27001 (Information Security Management)
- **Best for**: Organizations managing information security
- **Key Areas**: Access control, encryption, incident response
- **Status**: 16/18 controls passing

#### SOC 2 Type 2 (Service Organization Controls)
- **Best for**: Service providers and cloud platforms
- **Key Areas**: Logical access, monitoring, security incidents
- **Status**: 8/10 controls passing

#### HIPAA (Healthcare Security)
- **Best for**: Healthcare organizations and HIPAA-covered entities
- **Key Areas**: Access controls, encryption, audit trails
- **Status**: 8/10 controls passing

#### PCI DSS (Payment Card Industry)
- **Best for**: Organizations processing payment cards
- **Key Areas**: Network security, encryption, access control
- **Status**: 8/10 controls passing

---

## Using the Monitoring Dashboard

### Accessing the Dashboard
1. Click the **🚨 Security** tab in the navigation
2. You'll see real-time security metrics

### Understanding the Monitoring View

#### Status Cards (Top Row)
Quick KPI overview:
- **Alerts Today**: Count of alerts created today
- **Critical**: Number of critical incidents
- **Uptime**: System availability percentage
- **Chain Valid**: Verification that evidence chain is intact

#### Security Metrics Panel
Detailed metrics including:
- **Open Alerts**: Currently active alerts requiring attention
- **Resolved Today**: Alerts resolved in the last 24 hours
- **Integrity Violations**: Evidence hash mismatches
- **Unauthorized Access**: Access denial events
- **Avg Resolution Time**: How quickly alerts are typically resolved

#### Recent Alerts List
Shows latest security alerts with ability to:
- **Filter by Status**: OPEN, ACKNOWLEDGED, or RESOLVED
- **View Severity**: Color-coded severity levels
  - 🔴 CRITICAL: Immediate action required
  - 🟠 HIGH: Significant security concern
  - 🔵 MEDIUM: Should be reviewed
  - 🟢 LOW: Informational

- **Acknowledge Alert**: Mark alert as acknowledged (status: ACKNOWLEDGED)
- **View Details**: Check alert title and description
- **Timestamp**: See when alert was generated

---

## Common Workflows

### Workflow 1: Reviewing Daily Compliance
1. Navigate to **Compliance** dashboard
2. Review overall compliance score
3. Check for any frameworks with CRITICAL risk
4. Click on CRITICAL frameworks to see failing controls
5. Prioritize remediation of FAILING controls

### Workflow 2: Monitoring Security Alerts
1. Navigate to **Security** dashboard
2. Check status cards for immediate issues
3. Filter alerts to see OPEN items
4. Click "Acknowledge" to mark alert as reviewed
5. Monitor resolution time metrics

### Workflow 3: Investigating Evidence Integrity
1. Go to **Evidence** tab
2. Load evidence using evidence ID
3. If integrity violation alert appears in **Security** dashboard
4. Check the evidence's custody timeline for the issue
5. Verify the actual hash matches expected hash

### Workflow 4: Compliance Audit Preparation
1. Access **Compliance** dashboard
2. Document current status for each framework
3. Export compliance metrics (via API: `/compliance/dashboard`)
4. Review failing controls
5. Plan remediation activities

---

## API Usage (For Developers)

### Get Compliance Dashboard
```bash
curl -H "X-User-Id: auditor1" \
  http://localhost:8000/compliance/dashboard
```

### Get Security Alerts
```bash
# Get all open alerts
curl -H "X-User-Id: auditor1" \
  "http://localhost:8000/security/alerts?status=OPEN&limit=10"

# Get critical alerts
curl -H "X-User-Id: auditor1" \
  "http://localhost:8000/security/alerts?severity=CRITICAL"
```

### Get Security Metrics
```bash
curl -H "X-User-Id: auditor1" \
  http://localhost:8000/security/metrics
```

### Get Audit Logs
```bash
curl -H "X-User-Id: auditor1" \
  "http://localhost:8000/security/audit-logs?limit=100"
```

### Acknowledge Alert
```bash
curl -X POST \
  -H "X-User-Id: auditor1" \
  http://localhost:8000/security/alerts/{alert_id}/acknowledge
```

---

## Understanding the Color Coding

### Compliance Framework Cards

| Color | Status | Meaning |
|-------|--------|---------|
| 🟢 Green | LOW Risk | Excellent compliance posture |
| 🔵 Blue | MEDIUM Risk | Some controls need attention |
| 🟠 Orange | HIGH Risk | Multiple control failures |
| 🔴 Red | CRITICAL Risk | Foundation-level failures |

### Alert Severity

| Severity | Color | Example |
|----------|-------|---------|
| CRITICAL | 🔴 Red | Integrity violation detected |
| HIGH | 🟠 Orange | Unauthorized access attempt |
| MEDIUM | 🔵 Blue | Configuration drift |
| LOW | 🟢 Green | Informational event |

---

## Key Metrics Explained

### Compliance Percentage
- Calculated as: (Passing Controls / Total Controls) × 100
- Higher is better
- Shows per-framework and overall

### Risk Level
Determined by:
- Number of FAILING controls
- Number of controls NEEDING CHANGES
- Framework maturity requirements

### Mean Time To Resolution (MTTR)
- Average time from alert creation to resolution
- Calculated from: (resolved_at - timestamp) for resolved alerts
- Indicates how quickly the team responds to issues

### Integrity Violations
- Count of evidence hash mismatches
- Should be 0 in a healthy system
- Indicates possible tampering or system errors

---

## Troubleshooting

### Compliance Dashboard Not Loading
1. Verify you're logged in with correct user ID
2. Check browser console for errors
3. Ensure backend is running on port 8000
4. Check API permissions for your user role

### No Alerts Showing
1. Alerts are only created when events occur
2. Filter might be hiding alerts (try resetting filter)
3. Check if system has been running long enough to generate alerts
4. Verify your user role allows viewing security alerts

### Compliance Score Seems Wrong
1. Score is recalculated in real-time
2. Check individual framework statuses
3. Controls might have been updated recently
4. Clear browser cache if numbers seem stale

### Metrics Not Updating
1. Monitoring dashboard auto-refreshes every 30 seconds
2. Manual refresh: Reload the page
3. Check browser network tab for API errors
4. Verify backend database is not locked

---

## Tips & Best Practices

### For Compliance Officers
- Review compliance dashboard weekly
- Track trend (improving/stable/declining)
- Create action plans for FAILING controls
- Document remediation efforts in audit trail
- Use this data for compliance reports

### For Security Teams
- Monitor security alerts daily
- Aim to resolve CRITICAL alerts within 4 hours
- Track MTTR as a KPI
- Investigate integrity violations immediately
- Use audit logs to trace user actions

### For Auditors
- Use compliance dashboard for audit readiness
- Export compliance metrics regularly
- Cross-reference evidence timeline with audit logs
- Verify chain integrity regularly
- Document compliance posture over time

---

## Advanced Configuration

### Adding Custom Compliance Controls (Future Feature)
Currently, controls are predefined. Custom framework support is planned.

### Setting Alert Thresholds (Future Feature)
Currently, all violations create alerts. Configurable thresholds planned.

### Building Custom Reports (Future Feature)
API endpoints support data extraction for custom reporting integration.

---

## Support & Documentation

- **Full Documentation**: See `ENHANCEMENTS.md`
- **API Reference**: See README.md
- **Architecture**: See `COMPONENT_GUIDE.md`
- **Test Cases**: See `tests/` directory

---

## Quick Reference

### Navigation Shortcuts
- **Home**: Click logo or "Home" tab for overview
- **Evidence**: Manage evidence intake and custody
- **Compliance**: View framework and control status
- **Security**: Monitor alerts and security metrics

### Common URLs
- **Application**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints
```
GET  /compliance/dashboard
GET  /compliance/frameworks
GET  /compliance/{framework_id}/controls
GET  /monitoring/dashboard
GET  /security/alerts
POST /security/alerts/{id}/acknowledge
GET  /security/metrics
GET  /security/audit-logs
```

---

**Version**: 2.0 Enhanced Edition  
**Last Updated**: March 2026  
**For Support**: Refer to ENHANCEMENTS.md for technical details
