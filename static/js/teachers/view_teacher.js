/* KCC ClassStamp — Teachers: View Teacher Detail Controller */
(function (window) {
  'use strict';

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }

  function initViewTeacher() {
    // Guard: only run if the detail modal exists on this page
    if (!getEl('teacherDetailModal')) return;

    // Event delegation on document to catch View button clicks reliably
    document.addEventListener('click', async function (e) {
      var viewBtn = e.target.closest('.js-view-teacher');
      if (!viewBtn) return;

      e.preventDefault();
      var bodyEl = getEl('teacherDetailBody');
      if (bodyEl) bodyEl.innerHTML = '<div class="text-muted text-center" style="padding:40px;">Loading...</div>';

      var App = getApp();
      if (App) App.showModal('teacherDetailModal');
      else { var m = getEl('teacherDetailModal'); if (m) { m.classList.add('is-active'); document.body.style.overflow = 'hidden'; } }

      try {
        var res = await fetch('/teachers/get/' + viewBtn.dataset.id + '/');
        var data = await res.json();
        if (!data.ok) return;
        var t = data.teacher;

        var classesList = t.classes.length ? t.classes.map(function (c) {
          return '<div style="padding:10px 14px;border:1px solid var(--glass-border);border-radius:var(--radius-md);margin-bottom:8px;background:rgba(255,255,255,0.02);display:flex;align-items:center;justify-content:space-between;">'
            + '<div>'
            + '<span class="badge badge--primary font-mono">' + c.class_code + '</span>'
            + '<span class="text-sm font-semibold ml-2 text-primary">' + c.subject_code + ' \u2014 ' + c.subject_name + '</span>'
            + '<div class="text-muted text-xs mt-1"><i class="fas fa-calendar-day text-gold mr-1"></i> ' + c.academic_year + '</div>'
            + '</div>'
            + (c.is_active ? '<span class="badge badge--green text-xs">Active</span>' : '<span class="badge badge--muted text-xs">Archived</span>')
            + '</div>';
        }).join('') : '<div class="text-muted text-sm" style="padding:16px 0;text-align:center;">No class sections assigned yet.</div>';

        if (bodyEl) {
          bodyEl.innerHTML =
            '<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;">'
            + '<div style="width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,var(--accent-blue),var(--accent-purple));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.4rem;color:#fff;">' + (t.first_name[0] || '') + (t.last_name[0] || '') + '</div>'
            + '<div>'
            + '<div class="font-semibold text-primary" style="font-size:1.1rem;">' + t.full_name + '</div>'
            + '<div class="text-muted text-sm">@' + t.username + ' &nbsp;&middot;&nbsp; ' + t.email + '</div>'
            + '<div class="mt-1"><span class="badge badge--blue">' + t.department_code + '</span>&nbsp;<span class="badge ' + (t.is_active ? 'badge--green' : 'badge--muted') + '">' + (t.is_active ? 'Active' : 'Inactive') + '</span></div>'
            + '</div>'
            + '</div>'
            + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">'
            + '<div class="card" style="padding:12px;"><div class="text-muted text-xs mb-1">Department</div><div class="font-semibold">' + t.department_name + '</div></div>'
            + '<div class="card" style="padding:12px;"><div class="text-muted text-xs mb-1">Classes Assigned</div><div class="font-semibold">' + t.class_count + '</div></div>'
            + '<div class="card" style="padding:12px;"><div class="text-muted text-xs mb-1">Date Joined</div><div class="font-semibold">' + t.date_joined + '</div></div>'
            + '<div class="card" style="padding:12px;"><div class="text-muted text-xs mb-1">Approved At</div><div class="font-semibold">' + t.approved_at + '</div></div>'
            + '</div>'
            + '<div class="font-semibold text-primary mb-2">Assigned Class Sections</div>'
            + classesList;
        }
      } catch (err) {
        if (bodyEl) bodyEl.innerHTML = '<div class="text-danger text-center" style="padding:20px;">Failed to load teacher details.</div>';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initViewTeacher);
  } else {
    initViewTeacher();
  }
})(window);
