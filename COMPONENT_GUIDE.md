# 🎨 Tracey's Sentinel — Visual Component Guide

## Quick Reference for UI Components
## 🎯 Button Styles

```html
<!-- Primary Button (Blue) -->
<button class="primary">Primary Action</button>

<!-- Danger Button (Red) -->
<button class="danger">Delete</button>

<!-- Success Button (Green) -->
<button class="success">Confirm</button>

<!-- Warning Button (Orange) -->
<button class="warning">Caution</button>

<!-- Ghost Button (Transparent) -->
<button class="ghost">Secondary</button>
```

---

## 🏷️ Badge Classes

```html
<!-- Success Badge -->
<span class="badge badge-success">✓ Valid</span>

<!-- Danger Badge -->
<span class="badge badge-danger">✕ Invalid</span>

<!-- Warning Badge -->
<span class="badge badge-warning">⚠ Pending</span>

<!-- Info Badge -->
<span class="badge badge-info">ℹ Information</span>

<!-- Primary Badge -->
<span class="badge badge-primary">◆ Primary</span>
```

---

## 📋 Card Structure

```html
<section class="card">
  <!-- Header with title and subtitle -->
  <div class="card-header">
    <div>
      <h3 class="card-title">Card Title</h3>
      <p class="card-subtitle">Optional subtitle or description</p>
    </div>
  </div>

  <!-- Main content area -->
  <div class="card-body">
    <p>Card content goes here...</p>
  </div>

  <!-- Action buttons footer -->
  <div class="card-footer">
    <button class="primary">Save</button>
    <button class="ghost">Cancel</button>
  </div>
</section>
```

---

## 📝 Form Layouts
### Single Field
```html
<div class="form-group">
  <label for="field-id">Field Label</label>
  <input id="field-id" type="text" placeholder="Enter value">
</div>
```

### Multiple Fields in Row
```html
<div class="form-row">
  <div class="form-group">
    <label>First Name</label>
    <input type="text">
  </div>
  <div class="form-group">
    <label>Last Name</label>
    <input type="text">
  </div>
</div>
```

### Textarea
```html
<div class="form-group">
  <label for="message">Message</label>
  <textarea id="message" rows="4"></textarea>
</div>
```

### Select/Dropdown
```html
<div class="form-group">
  <label for="option">Select an option</label>
  <select id="option">
    <option>Option 1</option>
    <option>Option 2</option>
  </select>
</div>
```

---

## ⚠️ Alert Messages

```html
<!-- Success Alert -->
<div class="alert alert-success">
  ✓ Operation completed successfully
</div>

<!-- Danger Alert -->
<div class="alert alert-danger">
  ✕ An error occurred during processing
</div>

<!-- Warning Alert -->
<div class="alert alert-warning">
  ⚠ Please review before proceeding
</div>

<!-- Info Alert -->
<div class="alert alert-info">
  ℹ This is informational
</div>
```

---

## 📊 Table Structure

```html
<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        <th>Column 1</th>
        <th>Column 2</th>
        <th>Column 3</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Data 1</td>
        <td>Data 2</td>
        <td><button>Action</button></td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## 📈 Timeline Events

```html
<div class="timeline">
  <article class="timeline-item">
    <span class="event-type">TRANSFER</span>
    <div>Evidence transferred to Lab</div>
    <span class="event-time">2026-03-17 14:30</span>
  </article>
  
  <article class="timeline-item">
    <span class="event-type">ANALYSIS</span>
    <div>Forensic analysis completed</div>
    <span class="event-time">2026-03-18 09:15</span>
  </article>
</div>
```

---

## 🎭 Status Indicators

```html
<!-- Success Status -->
<span class="status success">Ready</span>

<!-- Warning Status -->
<span class="status warning">Pending</span>

<!-- Danger Status -->
<span class="status danger">Failed</span>

<!-- Info Status -->
<span class="status info">Processing</span>
```

---

## 🎨 Color Usage

### For Text
```html
<!-- Primary text -->
<p style="color: var(--text-primary)">Main content</p>

<!-- Secondary text -->
<p style="color: var(--text-secondary)">Supporting text</p>

<!-- Success text -->
<p style="color: var(--color-success)">✓ Success message</p>

<!-- Error text -->
<p style="color: var(--color-danger)">✕ Error message</p>
```

### For Backgrounds
```html
<!-- Light background -->
<div style="background: var(--bg-secondary)">Content</div>

<!-- Card background -->
<div style="background: var(--card)">Card content</div>

<!-- Dark background -->
<div style="background: var(--bg-primary)">Dark content</div>
```

---

## 🔤 Typography Styles

### Headings
```html
<h1>Page Title</h1>           <!-- Largest, main title -->
<h2>Section Heading</h2>      <!-- Section titles -->
<h3>Subsection</h3>           <!-- Card titles -->
<h4>Small Heading</h4>        <!-- Field groups -->
```

### Text Styles
```html
<p>Regular paragraph text</p>
<small>Smaller helper text</small>
<strong>Bold emphasis</strong>
<code>Code snippet or ID</code>
<a href="#">Link text</a>
```

---

## 🎯 Utility Classes

### Flexibility & Layout
```html
<!-- Flex row with gap -->
<div class="flex-row">Items here</div>

<!-- Flex column with gap -->
<div class="flex-column">Items here</div>

<!-- Grid layout -->
<div class="console-grid">Cards here</div>

<!-- Two-column grid -->
<div class="grid-2">Content here</div>

<!-- Full width -->
<div class="wide">Spans all columns</div>
```

### Visibility
```html
<!-- Hidden element -->
<div class="hidden">Not visible</div>

<!-- Invisible but takes space -->
<div class="invisible">Hidden but space taken</div>

<!-- Show only to screen readers -->
<span class="sr-only">Screen reader only</span>
```

### Opacity & Spacing
```html
<!-- Opacity 50% -->
<div class="opacity-50">Semi-transparent</div>

<!-- Opacity 75% -->
<div class="opacity-75">More visible</div>

<!-- Gap utilities -->
<div class="gap-sm">Small gap</div>
<div class="gap-md">Medium gap</div>
<div class="gap-lg">Large gap</div>
```

---

## 🎬 Animation Classes

### Used with Framer Motion (React)
```jsx
// Fade in animation
initial={{ opacity: 0 }}
animate={{ opacity: 1 }}
transition={{ duration: 0.3 }}

// Slide up animation
initial={{ opacity: 0, y: 20 }}
animate={{ opacity: 1, y: 0 }}

// Scale animation
whileHover={{ scale: 1.05 }}

// Hover elevation
whileHover={{ y: -2 }}
```

---

## 📱 Responsive Prefixes

All utilities work at different breakpoints:

```css
/* Desktop (1200px+) */
.card { }

/* Tablet (768px-1200px) */
@media (max-width: 768px) {
  .card { }
}

/* Mobile (480px-768px) */
@media (max-width: 480px) {
  .card { }
}

/* Small Mobile (<480px) */
@media (max-width: 480px) {
  .card { }
}
```

---

## ✨ Special Effects

### Card Hover
```css
.card:hover {
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary);
}
```

### Button Hover
```css
button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}
```

### Timeline Dot
```css
.timeline-item::before {
  content: "";
  width: 12px;
  height: 12px;
  background: var(--color-primary);
  border-radius: 50%;
}
```

### Loading Spinner
```html
<div class="spinner"></div>
```

---

## 🎯 CSS Variables Quick Access

```css
/* Colors */
--color-primary: #1e40af
--color-danger: #dc2626
--color-success: #16a34a
--color-warning: #ea580c
--color-info: #0891b2

/* Spacing */
--spacing-sm: 0.5rem     (8px)
--spacing-md: 1rem       (16px)
--spacing-lg: 1.5rem     (24px)
--spacing-xl: 2rem       (32px)

/* Typography */
--font-size-sm: 0.875rem
--font-size-base: 1rem
--font-size-lg: 1.125rem
--font-size-xl: 1.25rem
--font-size-2xl: 1.5rem

/* Radius */
--radius-md: 0.5rem
--radius-lg: 0.75rem
--radius-xl: 1rem
--radius-full: 9999px

/* Shadows */
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1)

/* Transitions */
--transition-fast: 150ms
--transition-base: 200ms
--transition-slow: 300ms
```

---

## 📚 Component Patterns

### Info Card with Icon
```html
<div class="card">
  <div style="display: flex; gap: 12px;">
    <span style="font-size: 1.5rem;">🔐</span>
    <div>
      <strong>Security Status</strong>
      <p>All systems secure</p>
    </div>
  </div>
</div>
```

### Icon + Text Button
```html
<button class="primary">
  📱 Open QR Code
</button>
```

### Metric Display
```html
<div class="card">
  <small style="color: var(--text-secondary)">Total Evidence</small>
  <strong style="font-size: 1.5rem;">42</strong>
</div>
```

### Status Label Row
```html
<div class="flex-row">
  <span class="badge badge-success">✓ Valid</span>
  <span class="badge badge-info">ℹ 3 Events</span>
  <span class="badge badge-warning">⚠ Pending Endorsement</span>
</div>
```

---

## 🎓 Implementation Examples

### Full Evidence Card
```jsx
<section className="card">
  <div className="card-header">
    <h3 className="card-title">🔍 Evidence Details</h3>
    <p className="card-subtitle">Complete custody information</p>
  </div>
  <div className="card-body">
    <div className="form-row">
      <div className="form-group">
        <label>Evidence ID</label>
        <input value={id} readOnly />
      </div>
      <div className="form-group">
        <label>Status</label>
        <span className="badge badge-success">✓ Valid</span>
      </div>
    </div>
  </div>
  <div className="card-footer">
    <button className="primary">Verify Integrity</button>
    <button className="ghost">Download Report</button>
  </div>
</section>
```

### Success Message
```jsx
{message && (
  <div className="alert alert-success" role="alert">
    ✓ {message}
  </div>
)}
```

### Form with Validation
```jsx
<div className="form-group">
  <label htmlFor="email">Email *</label>
  <input 
    id="email"
    type="email"
    required
    placeholder="name@example.com"
  />
  {errors.email && (
    <small style={{ color: 'var(--color-danger)' }}>
      {errors.email}
    </small>
  )}
</div>
```

---

## 🚀 Performance Tips

✓ Use semantic HTML
✓ Leverage CSS variables
✓ Minimize specificity conflicts
✓ Use flexbox over float
✓ Optimize animations
✓ Test on real devices
✓ Check accessibility
✓ Monitor bundle size

---

**Version**: 2.0 | **Last Updated**: March 17, 2026

