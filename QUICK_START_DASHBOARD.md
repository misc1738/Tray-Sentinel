# Quick Action Guide - Next Steps

**Your Dashboard is Ready!** 🎉 Here's what to do now:

---

## 🚀 Right Now - Test Your New Dashboard

### Step 1: Start the Application
```bash
# Open terminal in project directory
cd "Tracey's Sentinel"
python -m uvicorn app.main:app --reload
```

### Step 2: Visit the Dashboard
```
http://localhost:8000
```

### Step 3: Login with Demo Account
```
Username: officer1
Password: pass123
```

### Step 4: Explore the Sidebar Navigation
- Click on **Dashboard** - See overview with metrics
- Click on **Cases** - View case management page
- Click on **Evidence** - View evidence inventory
- Click on **Compliance** - Check compliance tracker
- Click on **Audit** - View audit logs
- Try the **Theme Toggle** in top bar

---

## ✨ What You'll See

### Dashboard Overview
- 4 key metric cards (Evidence, Cases, Endorsements, Integrity)
- Compliance program status with tabs
- Recent activity feed
- Professional light theme with blue sidebar

### Sidebar Navigation
```
MAIN
├── Dashboard
├── Cases  
└── Evidence

OPERATIONS
├── Intake Scanner
├── Advanced Search
└── Endorsements

COMPLIANCE
├── Compliance Status
├── Audit Logs
└── Reports

ANALYTICS
├── Analytics
└── Admin Panel
```

### Top Bar Features
- Search bar (not yet wired)
- Theme toggle button
- Notifications area
- User profile menu
- Settings icon

---

## 🎨 Customization Options (Easy)

### Change Primary Color
**File:** `static/unified-style.css` (line 2)

Find this:
```css
:root {
    --primary-color: #0056CC;  /* ← Change this */
```

Change `#0056CC` to any color you want:
- Red: `#DC3545`
- Green: `#28A745`
- Purple: `#6F42C1`
- Orange: `#FD7E14`

### Add New Navigation Item
**File:** `static/base.html` (around line 30)

Add after existing nav items:
```html
<a href="#" class="nav-link" data-page="mypage">
    <i class="bi bi-star"></i>
    <span>My New Page</span>
</a>
```

### Add New Page
**File:** `static/unified-app.js` (around line 50)

Add to `PAGE_TEMPLATES`:
```javascript
PAGE_TEMPLATES['mypage'] = `
    <div class="card">
        <h1>My New Page</h1>
        <p>Add your content here</p>
    </div>
`;
```

---

## 📊 Wire Up Real Data (Medium Effort)

### Option 1: Dashboard Metrics from Backend
Current: Mock data showing "1,247 Total Evidence"  
Target: Real count from database

**Replace in `unified-app.js` (Dashboard template):**

From:
```javascript
<div class="metric-value">1,247</div>
```

To:
```javascript
<div class="metric-value" id="evidence-count">Loading...</div>
```

Then add after template:
```javascript
// Fetch real data
fetch('/health')
    .then(r => r.json())
    .then(data => {
        document.getElementById('evidence-count').textContent = data.evidence_count;
    });
```

### Option 2: Compliance Dashboard from Backend
Current: Mock "73% ISO 27001"  
Target: Real compliance percentage from `/compliance/dashboard`

```javascript
fetch('/compliance/dashboard')
    .then(r => r.json())
    .then(data => {
        document.querySelector('.progress-fill').style.width = data.compliance_percentage + '%';
        document.querySelector('.progress-percentage').textContent = data.compliance_percentage + '%';
    });
```

### Option 3: Cases Table from Backend
Current: Hardcoded table with 3 rows  
Target: Real cases from `/case` endpoint

```javascript
fetch('/case')
    .then(r => r.json())
    .then(cases => {
        const tbody = document.querySelector('.cases-table tbody');
        tbody.innerHTML = cases.map(c => `
            <tr>
                <td>${c.case_id}</td>
                <td>${c.title}</td>
                <td>${c.evidence_count}</td>
                <td>${c.status}</td>
            </tr>
        `).join('');
    });
```

---

## 🔐 Implement Authentication (Higher Effort)

### Current State
- Login works (JWT tokens issued)
- Dashboard loads for everyone
- No session check on page

### Add Session Validation
**Edit `static/unified-app.js` (top of file):**

```javascript
// Check if user is logged in
window.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/auth.html';
        return;
    }
    
    // Verify token is valid
    fetch('/auth/users', {
        headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(r => {
        if (r.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/auth.html';
        }
        return r.json();
    })
    .then(user => {
        document.getElementById('user-name').textContent = user.username;
        document.getElementById('user-email').textContent = user.email;
    });
});
```

---

## 🎯 Implementation Roadmap

### Today (Easy - 30 mins)
- [x] ✅ Test new dashboard
- [x] ✅ Explore all pages
- [x] ✅ Try theme toggle
- [ ] TODO: Change colors to match your brand
- [ ] TODO: Add custom navigation items

### This Week (Medium - 4 hours)
- [ ] TODO: Connect user profile to real data
- [ ] TODO: Wire dashboard metrics
- [ ] TODO: Load compliance data
- [ ] TODO: Implement logout

### Next Week (Harder - 8 hours)
- [ ] TODO: Load real case data
- [ ] TODO: Implement search functionality
- [ ] TODO: Add case creation form
- [ ] TODO: Implement filtering

### Next Month (Advanced - 20 hours)
- [ ] TODO: Export to PDF/CSV
- [ ] TODO: Real-time dashboard updates
- [ ] TODO: Mobile app shell
- [ ] TODO: Dark mode theme

---

## 🆘 Common Tasks

### Task: Change Sidebar Background Color
**File:** `static/unified-style.css` (search for `.sidebar`)

Find:
```css
.sidebar {
    background-color: #F8F9FA;  /* ← Change this */
}
```

### Task: Change Button Colors
**File:** `static/unified-style.css` (search for `.btn-primary`)

Find:
```css
.btn-primary {
    background-color: var(--primary-color);  /* Uses CSS variable */
    color: white;
}
```

### Task: Add More Metric Cards
**File:** `static/unified-app.js` (Dashboard template)

Copy-paste and modify:
```html
<div class="metric-card">
    <div class="metric-label">Your Metric Name</div>
    <div class="metric-value">123</div>
    <div class="metric-change positive">↑ 5%</div>
    <div class="metric-icon"><i class="bi bi-your-icon"></i></div>
</div>
```

### Task: Make a Status Badge Red
```html
<span class="badge badge-danger">Failed</span>
```

Color options:
- `.badge-success` - Green
- `.badge-warning` - Yellow
- `.badge-danger` - Red
- `.badge-info` - Blue
- `.badge-pending` - Gray

---

## 📚 File Reference

### Main Files You'll Work With
```
static/base.html               - Layout (when changing structure)
static/unified-style.css       - Colors/styling (when changing look)
static/unified-app.js          - Content/data (when changing pages)
app/main.py                    - Routes (when adding endpoints)
```

### Documentation Files
```
UNIFIED_DASHBOARD_GUIDE.md     - User guide
UI_IMPLEMENTATION_STATUS.md    - Status & checklists
```

---

## ✅ Success Checklist

Before showing to others, verify:
- [ ] Dashboard loads without errors
- [ ] Sidebar navigation works
- [ ] Page switching works
- [ ] Theme toggle works
- [ ] Responsive on mobile (resize browser to test)
- [ ] All icons display correctly
- [ ] Logout button works
- [ ] Login redirects to dashboard
- [ ] User profile shows correctly
- [ ] No console errors (open F12 to check)

---

## 🚀 Deploy to Production

When ready for production:

1. **Build Check**
   ```bash
   python -m pytest tests/
   # Should see: 5 passed
   ```

2. **Update Environment**
   ```bash
   # Set these in .env or system variables:
   MASTER_KEY_PASSWORD=your-secure-password
   SECRET_KEY=your-long-random-secret
   ```

3. **Collect Static Files**
   ```bash
   # Make sure all static files are in place:
   # static/base.html
   # static/unified-style.css
   # static/unified-app.js
   ```

4. **Deploy**
   ```bash
   # Use Gunicorn for production:
   gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
   ```

---

## 💡 Pro Tips

1. **Use Browser DevTools (F12)** - Inspect HTML, debug JavaScript, see network calls
2. **Check Console** - Errors show here if something breaks
3. **Responsive Testing** - Press F12, then Ctrl+Shift+M to test mobile
4. **CSS Variables** - Change one color and whole theme updates
5. **Page Templates** - Add to PAGE_TEMPLATES object, not HTML files
6. **Bootstrap Icons** - Browse at https://icons.getbootstrap.com/
7. **Keyboard Shortcut** - Ctrl+Shift+Delete to clear browser cache

---

## 🎯 Next After Testing

Once you've tested and customized:

1. **Connect Real Data** (Pick easiest first)
   - User profile display
   - Evidence count metric
   - Case list

2. **Add Missing Features**
   - Search functionality
   - Export buttons
   - Filtering options

3. **Security Review**
   - Token refresh logic
   - Permission checks
   - Input validation

4. **Performance Optimization**
   - Cache data
   - Lazy load pages
   - Minify CSS/JS

---

**Questions?** Check the utility files or review the code comments!

**Ready?** Start the app and visit http://localhost:8000 🚀

---

*Generated: April 1, 2026*
*Your Tracey's Sentinel Dashboard v2.0 is ready!*
