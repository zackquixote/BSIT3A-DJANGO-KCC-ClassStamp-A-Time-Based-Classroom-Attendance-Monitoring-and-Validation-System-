# 🎨 KCC ClassStamp — UI/UX Design System

This document defines the complete design language for KCC ClassStamp.
All templates, pages, and components **must** follow these standards.

---

## 🌈 Color Palette

```css
:root {
  /* Backgrounds */
  --bg-base:        #0f172a;   /* Deep navy — main background */
  --bg-surface:     #1e293b;   /* Cards, sidebars */
  --bg-elevated:    #334155;   /* Hover states, dropdowns */

  /* Glass */
  --glass-bg:       rgba(255, 255, 255, 0.05);
  --glass-border:   rgba(255, 255, 255, 0.10);
  --glass-blur:     blur(12px);

  /* Accent Colors */
  --accent-gold:    #f59e0b;   /* KCC brand gold — CTAs, highlights */
  --accent-gold-h:  #fbbf24;   /* Hover gold */
  --accent-blue:    #3b82f6;   /* Info, links */
  --accent-blue-h:  #60a5fa;   /* Hover blue */

  /* Status Colors */
  --success:        #22c55e;   /* Present */
  --warning:        #f59e0b;   /* Late */
  --danger:         #ef4444;   /* Absent */
  --info:           #3b82f6;   /* Info / Excused */
  --muted:          #64748b;   /* Disabled, secondary text */

  /* Text */
  --text-primary:   #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted:     #64748b;

  /* Role Colors */
  --role-admin:     #a855f7;   /* Purple */
  --role-teacher:   #f59e0b;   /* Gold */
  --role-student:   #22c55e;   /* Green */
}
```

---

## 📐 Typography

```css
/* Import in base template <head> */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
  background-color: var(--bg-base);
}

/* Scale */
h1 { font-size: 2rem;    font-weight: 700; }
h2 { font-size: 1.5rem;  font-weight: 600; }
h3 { font-size: 1.25rem; font-weight: 600; }
h4 { font-size: 1rem;    font-weight: 600; }
p  { font-size: 0.9375rem; color: var(--text-secondary); }

.text-xs  { font-size: 0.75rem; }
.text-sm  { font-size: 0.875rem; }
.text-lg  { font-size: 1.125rem; }
.text-xl  { font-size: 1.25rem; }
.text-2xl { font-size: 1.5rem; }
.text-3xl { font-size: 2rem; }
```

---

## 🃏 Component Library

### Glass Card
```html
<div class="card">
  <!-- content -->
</div>
```
```css
.card {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 24px;
  transition: all 0.3s ease;
}
.card:hover {
  border-color: rgba(255,255,255,0.15);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
```

---

### Stat Card (Dashboards)
```html
<div class="stat-card">
  <div class="stat-icon">
    <i class="icon-users"></i>  <!-- use any icon lib -->
  </div>
  <div class="stat-info">
    <span class="stat-value">42</span>
    <span class="stat-label">Pending Accounts</span>
  </div>
</div>
```
```css
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 20px 24px;
  backdrop-filter: var(--glass-blur);
  transition: all 0.3s ease;
}
.stat-icon {
  width: 48px; height: 48px;
  border-radius: 12px;
  background: rgba(245,158,11,0.15);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem;
  color: var(--accent-gold);
}
.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
}
.stat-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

---

### Primary Button
```html
<button class="btn btn-primary">Approve</button>
<button class="btn btn-danger">Reject</button>
<button class="btn btn-outline">Cancel</button>
```
```css
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
  text-decoration: none;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent-gold), #d97706);
  color: #0f172a;
}
.btn-primary:hover {
  background: linear-gradient(135deg, var(--accent-gold-h), var(--accent-gold));
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(245,158,11,0.4);
}
.btn-danger {
  background: rgba(239,68,68,0.15);
  color: #ef4444;
  border: 1px solid rgba(239,68,68,0.3);
}
.btn-danger:hover { background: rgba(239,68,68,0.25); }
.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--glass-border);
}
.btn-outline:hover { border-color: var(--accent-gold); color: var(--accent-gold); }
```

---

### Role Badge
```html
<span class="role-badge role-admin">Admin</span>
<span class="role-badge role-teacher">Teacher</span>
<span class="role-badge role-student">Student</span>
```
```css
.role-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.role-admin   { background: rgba(168,85,247,0.15); color: #a855f7; border: 1px solid rgba(168,85,247,0.3); }
.role-teacher { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.role-student { background: rgba(34,197,94,0.15);  color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
```

---

### Attendance Status Badge
```html
<span class="status-badge status-present">Present</span>
<span class="status-badge status-late">Late</span>
<span class="status-badge status-absent">Absent</span>
<span class="status-badge status-excused">Excused</span>
```
```css
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}
.status-present { background: rgba(34,197,94,0.15);  color: #22c55e; }
.status-late    { background: rgba(245,158,11,0.15); color: #f59e0b; }
.status-absent  { background: rgba(239,68,68,0.15);  color: #ef4444; }
.status-excused { background: rgba(59,130,246,0.15); color: #3b82f6; }
```

---

### QR Code Card (Student)
```html
<div class="qr-card">
  <div class="qr-header">
    <h3>My Attendance QR</h3>
    <p>Show this to your teacher at the start of class</p>
  </div>
  <div class="qr-image-wrap">
    <img src="{{ qr_data_url }}" alt="Your QR Code" class="qr-image">
    <div class="qr-glow"></div>
  </div>
  <div class="qr-timer">
    <span>Refreshes in <strong id="qr-countdown">30</strong>s</span>
    <div class="qr-progress-bar">
      <div class="qr-progress-fill" id="qr-fill"></div>
    </div>
  </div>
</div>
```
```css
.qr-card {
  max-width: 360px;
  margin: 0 auto;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 24px;
  padding: 32px;
  text-align: center;
  backdrop-filter: var(--glass-blur);
}
.qr-image-wrap {
  position: relative;
  display: inline-block;
  margin: 24px 0;
}
.qr-image {
  width: 220px; height: 220px;
  border-radius: 16px;
  border: 4px solid var(--accent-gold);
}
.qr-glow {
  position: absolute; inset: -8px;
  border-radius: 20px;
  background: radial-gradient(circle, rgba(245,158,11,0.2) 0%, transparent 70%);
  pointer-events: none;
  animation: qr-pulse 2s ease-in-out infinite;
}
@keyframes qr-pulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50%       { opacity: 1;   transform: scale(1.03); }
}
.qr-progress-bar {
  height: 4px; border-radius: 2px;
  background: rgba(255,255,255,0.1);
  margin-top: 8px; overflow: hidden;
}
.qr-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-gold), var(--accent-blue));
  transition: width 1s linear;
}
```

---

### Scanner Card (Teacher)
```css
.scanner-card {
  background: var(--glass-bg);
  border: 2px dashed var(--glass-border);
  border-radius: 24px;
  padding: 24px;
  min-height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
/* Scanning laser line */
.scanner-line {
  position: absolute;
  left: 10%; right: 10%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent-gold), transparent);
  animation: scan 2s ease-in-out infinite;
}
@keyframes scan {
  0%   { top: 10%; opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { top: 90%; opacity: 0; }
}
```

---

### Absence Warning Banner
```html
<div class="absence-warning warning-{{ level }}">
  <span class="warning-icon">⚠️</span>
  <div>
    <strong>{{ absences }} of {{ max_absences }} absences used</strong>
    <p>{{ warning_message }}</p>
  </div>
</div>
```
```css
.absence-warning {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px; border-radius: 12px;
  border-left: 4px solid;
}
.warning-safe     { background: rgba(34,197,94,0.1);  border-color: #22c55e; }
.warning-caution  { background: rgba(245,158,11,0.1); border-color: #f59e0b; }
.warning-danger   { background: rgba(239,68,68,0.1);  border-color: #ef4444; }
.warning-critical { background: rgba(239,68,68,0.2);  border-color: #ef4444; animation: warning-pulse 1s ease-in-out infinite; }
@keyframes warning-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.7; }
}
```

---

## 🔲 Sidebar Navigation

```html
<nav class="sidebar">
  <div class="sidebar-brand">
    <span class="brand-icon">📋</span>
    <span class="brand-name">ClassStamp</span>
  </div>
  <ul class="sidebar-nav">
    <li class="nav-item active">
      <a href="/teacher/" class="nav-link">
        <span class="nav-icon">🏠</span>
        <span>Dashboard</span>
      </a>
    </li>
    <!-- more items -->
  </ul>
  <div class="sidebar-footer">
    <div class="user-chip">
      <div class="user-avatar">{{ user.first_name|first }}</div>
      <div class="user-info">
        <span class="user-name">{{ user.get_full_name }}</span>
        <span class="role-badge role-teacher">Teacher</span>
      </div>
    </div>
    <a href="/logout/" class="btn btn-outline btn-sm">Logout</a>
  </div>
</nav>
```
```css
.sidebar {
  width: 260px; height: 100vh;
  background: var(--bg-surface);
  border-right: 1px solid var(--glass-border);
  display: flex; flex-direction: column;
  padding: 24px 16px;
  position: fixed; left: 0; top: 0;
}
.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 0 8px 24px;
  border-bottom: 1px solid var(--glass-border);
  margin-bottom: 16px;
}
.brand-name { font-size: 1.25rem; font-weight: 700; color: var(--accent-gold); }
.sidebar-nav { list-style: none; padding: 0; margin: 0; flex: 1; }
.nav-link {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 10px;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.2s ease;
}
.nav-link:hover, .nav-item.active .nav-link {
  background: rgba(245,158,11,0.1);
  color: var(--accent-gold);
}
.nav-item.active .nav-link {
  font-weight: 600;
}
.user-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-gold), var(--accent-blue));
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 0.875rem; color: #0f172a;
}
```

---

## 📱 Responsive Breakpoints

```css
/* Mobile-first approach */
@media (max-width: 768px) {
  .sidebar { transform: translateX(-100%); z-index: 1000; }
  .sidebar.open { transform: translateX(0); }
  .main-content { margin-left: 0 !important; }
  .stat-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 480px) {
  .stat-grid { grid-template-columns: 1fr; }
  .qr-image { width: 180px; height: 180px; }
}
```

---

## ✅ Design Rules (DO and DON'T)

### ✅ DO
- Use `backdrop-filter: blur()` on all floating cards
- Add `transition: all 0.2s-0.3s ease` to every interactive element
- Use role colors consistently (purple = admin, gold = teacher, green = student)
- Add hover states to every clickable element
- Use gradient accents on primary actions

### ❌ DON'T
- Use plain white backgrounds (`#ffffff`) anywhere
- Use default browser blue for links
- Use `font-weight: normal` on anything important
- Skip hover states on buttons/cards
- Mix border radius sizes inconsistently
