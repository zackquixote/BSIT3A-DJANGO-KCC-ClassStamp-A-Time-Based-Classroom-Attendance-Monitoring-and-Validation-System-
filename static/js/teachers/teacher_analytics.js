/**
 * KCC ClassStamp — Teacher & Faculty Analytics Controller
 * Handles:
 * 1. Fetching teaching load and attendance compliance metrics for an instructor
 * 2. Rendering telemetry cards & class breakdown table
 * 3. Modal lifecycle and error handling
 */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  const modal = document.getElementById('teacherAnalyticsModal');
  if (!modal) return;

  const avatarEl = document.getElementById('analyticsAvatar');
  const nameEl = document.getElementById('analyticsTeacherName');
  const metaEl = document.getElementById('analyticsTeacherMeta');
  const deptEl = document.getElementById('analyticsDeptBadge');
  const classesKpi = document.getElementById('analyticsTotalClasses');
  const studentsKpi = document.getElementById('analyticsTotalStudents');
  const sessionsKpi = document.getElementById('analyticsTotalSessions');
  const rateKpi = document.getElementById('analyticsOverallRate');
  const container = document.getElementById('analyticsClassesContainer');

  function openModal() {
    modal.classList.add('is-open');
  }

  function closeModal() {
    modal.classList.remove('is-open');
  }

  modal.querySelectorAll('[data-modal-dismiss="teacherAnalyticsModal"]').forEach(function (btn) {
    btn.addEventListener('click', closeModal);
  });

  modal.addEventListener('click', function (e) {
    if (e.target === modal) closeModal();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
  });

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderClassesTable(classes) {
    if (!container) return;

    if (!classes || classes.length === 0) {
      container.innerHTML =
        '<div style="padding: 30px; text-align: center;">' +
        '  <i class="fas fa-book-open text-muted" style="font-size: 1.5rem;"></i>' +
        '  <p class="text-xs text-muted mt-2">No active class offerings assigned to this instructor.</p>' +
        '</div>';
      return;
    }

    let html = '<table class="table" style="margin: 0; min-width: 100%;">';
    html += '<thead><tr>';
    html += '<th>Section Code</th>';
    html += '<th>Subject</th>';
    html += '<th style="text-align: center;">Slots</th>';
    html += '<th style="text-align: center;">Enrolled</th>';
    html += '<th style="text-align: center;">Sessions</th>';
    html += '<th style="text-align: center;">Attendance</th>';
    html += '</tr></thead><tbody>';

    classes.forEach(function (c) {
      const rateColor = c.attendance_rate >= 80 ? 'text-green' : (c.attendance_rate >= 60 ? 'text-gold' : 'text-danger');
      const statusBadge = c.is_active
        ? '<span class="badge badge--success badge--xs" style="padding: 1px 4px; font-size: 0.58rem; margin-left: 4px;">Active</span>'
        : '<span class="badge badge--dark badge--xs" style="padding: 1px 4px; font-size: 0.58rem; margin-left: 4px;">Archived</span>';

      html += '<tr>';
      html +=
        '<td>' +
        '  <span class="font-mono font-bold text-xs text-primary">' + escapeHtml(c.class_code) + '</span>' +
        statusBadge +
        '  <div class="text-muted text-xs" style="font-size: 0.65rem;">' + escapeHtml(c.academic_year) + '</div>' +
        '</td>';
      html +=
        '<td>' +
        '  <div class="font-semibold text-xs text-primary">' + escapeHtml(c.subject_code) + '</div>' +
        '  <div class="text-muted text-xs" style="font-size: 0.68rem;">' + escapeHtml(c.subject_name) + '</div>' +
        '</td>';
      html += '<td style="text-align: center; font-size: 0.75rem;">' + c.slots_count + '</td>';
      html += '<td style="text-align: center; font-size: 0.75rem; font-weight: 600;">' + c.enrolled_count + '</td>';
      html += '<td style="text-align: center; font-size: 0.75rem;">' + c.sessions_count + '</td>';
      html +=
        '<td style="text-align: center; font-size: 0.75rem; font-weight: 800;" class="' + rateColor + '">' +
        c.attendance_rate + '%' +
        '</td>';
      html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
  }

  document.querySelectorAll('.js-teacher-analytics').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const teacherId = btn.getAttribute('data-id');
      const teacherName = btn.getAttribute('data-name') || 'Faculty Member';

      if (nameEl) nameEl.textContent = teacherName;
      if (metaEl) metaEl.textContent = 'Loading faculty profile...';
      if (avatarEl) {
        const parts = teacherName.trim().split(' ');
        const initials = (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
        avatarEl.textContent = initials;
      }

      if (container) {
        container.innerHTML =
          '<div style="padding: 30px; text-align: center;" id="analyticsLoading">' +
          '  <i class="fas fa-spinner fa-spin text-gold" style="font-size: 1.5rem;"></i>' +
          '  <p class="text-xs text-muted mt-2">Loading teaching load analytics...</p>' +
          '</div>';
      }

      openModal();

      fetch('/teachers/' + teacherId + '/analytics/', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          if (!data || !data.success) {
            throw new Error(data.error || 'Failed to load teacher analytics');
          }

          if (metaEl) {
            metaEl.textContent = data.teacher.email || '-';
          }
          if (deptEl) deptEl.textContent = data.teacher.department || 'General';

          if (classesKpi) classesKpi.textContent = data.summary.active_classes;
          if (studentsKpi) studentsKpi.textContent = data.summary.total_students_taught;
          if (sessionsKpi) sessionsKpi.textContent = data.summary.total_sessions;
          if (rateKpi) rateKpi.textContent = data.summary.overall_compliance + '%';

          renderClassesTable(data.classes);
        })
        .catch(function (err) {
          console.error('Teacher analytics error:', err);
          if (container) {
            container.innerHTML =
              '<div style="padding: 30px; text-align: center;">' +
              '  <i class="fas fa-triangle-exclamation text-danger" style="font-size: 1.5rem;"></i>' +
              '  <p class="text-xs text-danger mt-2">Failed to load analytics telemetry. Please try again.</p>' +
              '</div>';
          }
        });
    });
  });
});
