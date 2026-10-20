/**
 * KCC ClassStamp — Class Section Attendance Matrix Sheet Controller
 * Handles:
 * 1. Fetching session date columns & student records for a class
 * 2. Rendering the 2D spreadsheet matrix with sticky headers and pinned student column
 * 3. Status badge styling (Present, Late, Absent, Excused)
 * 4. Summary column computations & section attendance compliance telemetry
 * 5. Direct CSV Export link configuration
 */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  const matrixModal = document.getElementById('matrixModal');
  const closeMatrixModal = document.getElementById('closeMatrixModal');
  const matrixClassCode = document.getElementById('matrixClassCode');
  const matrixSubheading = document.getElementById('matrixSubheading');
  const matrixTotalStudents = document.getElementById('matrixTotalStudents');
  const matrixTotalSessions = document.getElementById('matrixTotalSessions');
  const matrixOverallRate = document.getElementById('matrixOverallRate');
  const matrixExportCsvBtn = document.getElementById('matrixExportCsvBtn');
  const matrixTableContainer = document.getElementById('matrixTableContainer');

  if (!matrixModal) return;

  function closeModal() {
    matrixModal.classList.remove('is-open');
  }

  if (closeMatrixModal) {
    closeMatrixModal.addEventListener('click', closeModal);
  }

  matrixModal.addEventListener('click', function (e) {
    if (e.target === matrixModal) {
      closeModal();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && matrixModal.classList.contains('is-open')) {
      closeModal();
    }
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

  function renderStatusBadge(status) {
    if (status === 'PRESENT') {
      return '<span class="badge badge--success badge--xs" style="padding: 2px 6px; font-weight: 700;" title="Present">P</span>';
    }
    if (status === 'LATE') {
      return '<span class="badge badge--warning badge--xs" style="padding: 2px 6px; font-weight: 700;" title="Late">L</span>';
    }
    if (status === 'ABSENT') {
      return '<span class="badge badge--danger badge--xs" style="padding: 2px 6px; font-weight: 700;" title="Absent">A</span>';
    }
    if (status === 'EXCUSED') {
      return '<span class="badge badge--info badge--xs" style="padding: 2px 6px; font-weight: 700;" title="Excused">E</span>';
    }
    return '<span class="text-muted" style="opacity: 0.4;">—</span>';
  }

  function renderMatrix(data) {
    if (!matrixTableContainer) return;

    if (!data.students || data.students.length === 0) {
      matrixTableContainer.innerHTML =
        '<div style="padding: 50px 20px; text-align: center;">' +
        '  <i class="fas fa-users-slash text-muted" style="font-size: 2rem;"></i>' +
        '  <p class="text-sm text-primary font-bold mt-2">No Students Enrolled</p>' +
        '  <p class="text-xs text-muted">Use the "Roster" action on this class to enlist students.</p>' +
        '</div>';
      return;
    }

    if (!data.sessions || data.sessions.length === 0) {
      matrixTableContainer.innerHTML =
        '<div style="padding: 50px 20px; text-align: center;">' +
        '  <i class="fas fa-calendar-xmark text-muted" style="font-size: 2rem;"></i>' +
        '  <p class="text-sm text-primary font-bold mt-2">No Sessions Recorded Yet</p>' +
        '  <p class="text-xs text-muted">Attendance scans will populate as sessions are conducted by faculty.</p>' +
        '</div>';
      return;
    }

    let html = '<table class="table" style="margin: 0; min-width: 100%; border-collapse: separate; border-spacing: 0;">';

    // Table Header
    html += '<thead style="position: sticky; top: 0; z-index: 10;">';
    html += '<tr>';
    html += '<th style="position: sticky; left: 0; z-index: 12; background: var(--bg-card); min-width: 220px; border-right: 1px solid var(--glass-border);">Student</th>';

    data.sessions.forEach(function (sess) {
      html +=
        '<th style="text-align: center; min-width: 60px; padding: 6px 4px; font-size: 0.68rem; background: var(--bg-card);">' +
        '  <div style="font-weight: 700;">' + escapeHtml(sess.display_date) + '</div>' +
        '  <div class="text-muted" style="font-size: 0.58rem; text-transform: uppercase;">' + escapeHtml(sess.weekday) + '</div>' +
        '</th>';
    });

    html += '<th style="text-align: center; min-width: 45px; background: var(--bg-card);" title="Total Present">Pres</th>';
    html += '<th style="text-align: center; min-width: 45px; background: var(--bg-card);" title="Total Late">Late</th>';
    html += '<th style="text-align: center; min-width: 45px; background: var(--bg-card);" title="Total Absent">Abs</th>';
    html += '<th style="text-align: center; min-width: 45px; background: var(--bg-card);" title="Total Excused">Exc</th>';
    html += '<th style="text-align: center; min-width: 65px; background: var(--bg-card); border-left: 1px solid var(--glass-border);">Rate %</th>';
    html += '</tr>';
    html += '</thead>';

    // Table Body
    html += '<tbody>';
    data.students.forEach(function (st) {
      const rateColor = st.rate >= 80 ? 'text-green' : (st.rate >= 60 ? 'text-gold' : 'text-danger');

      html += '<tr>';
      // Sticky Student Column
      html +=
        '<td style="position: sticky; left: 0; z-index: 5; background: var(--bg-card); border-right: 1px solid var(--glass-border); padding: 8px 10px;">' +
        '  <div class="font-bold text-xs text-primary" style="line-height: 1.2;">' + escapeHtml(st.name) + '</div>' +
        '  <div class="text-muted" style="font-size: 0.65rem; margin-top: 2px;">' +
        '    <span>' + escapeHtml(st.student_number) + '</span>' +
        '    <span class="badge badge--dark badge--xs" style="padding: 1px 4px; font-size: 0.58rem; margin-left: 4px;">' + escapeHtml(st.program) + '</span>' +
        '  </div>' +
        '</td>';

      // Session Cells
      st.cells.forEach(function (cell) {
        html += '<td style="text-align: center; padding: 6px 4px;">' + renderStatusBadge(cell.status) + '</td>';
      });

      // Summary Columns
      html += '<td style="text-align: center; font-size: 0.72rem; font-weight: 600; color: #4ade80;">' + st.present + '</td>';
      html += '<td style="text-align: center; font-size: 0.72rem; font-weight: 600; color: #fbbf24;">' + st.late + '</td>';
      html += '<td style="text-align: center; font-size: 0.72rem; font-weight: 600; color: #f87171;">' + st.absent + '</td>';
      html += '<td style="text-align: center; font-size: 0.72rem; font-weight: 600; color: #60a5fa;">' + st.excused + '</td>';
      html +=
        '<td style="text-align: center; border-left: 1px solid var(--glass-border); font-size: 0.75rem; font-weight: 800;" class="' + rateColor + '">' +
        st.rate + '%' +
        '</td>';

      html += '</tr>';
    });
    html += '</tbody>';
    html += '</table>';

    matrixTableContainer.innerHTML = html;
  }

  // Bind Open Buttons
  document.querySelectorAll('.js-open-matrix').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const classId = btn.getAttribute('data-class-id');
      const classCode = btn.getAttribute('data-class-code') || '—';
      const matrixUrl = btn.getAttribute('data-matrix-url') || ('/classes/' + classId + '/matrix/');

      if (matrixClassCode) matrixClassCode.textContent = classCode;
      if (matrixSubheading) matrixSubheading.textContent = 'Loading section metadata...';
      if (matrixExportCsvBtn) matrixExportCsvBtn.href = matrixUrl + (matrixUrl.indexOf('?') > -1 ? '&' : '?') + 'format=csv';

      if (matrixTableContainer) {
        matrixTableContainer.innerHTML =
          '<div style="padding: 40px; text-align: center;" id="matrixLoadingState">' +
          '  <i class="fas fa-spinner fa-spin text-gold" style="font-size: 1.5rem;"></i>' +
          '  <p class="text-xs text-muted mt-2">Loading attendance matrix sheet...</p>' +
          '</div>';
      }

      matrixModal.classList.add('is-open');

      fetch(matrixUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          if (!data || !data.success) {
            throw new Error(data.error || 'Failed to load attendance matrix');
          }

          if (matrixSubheading) {
            matrixSubheading.textContent =
              (data.subject_code ? data.subject_code + ' — ' : '') +
              (data.subject_name || '') +
              ' · Instructor: ' +
              (data.teacher_name || '—') +
              ' (' + (data.academic_year || '—') + ')';
          }

          if (matrixTotalStudents) matrixTotalStudents.textContent = data.summary.total_students;
          if (matrixTotalSessions) matrixTotalSessions.textContent = data.summary.total_sessions;
          if (matrixOverallRate) matrixOverallRate.textContent = data.summary.overall_rate + '%';

          renderMatrix(data);
        })
        .catch(function (err) {
          console.error('Matrix load error:', err);
          if (matrixTableContainer) {
            matrixTableContainer.innerHTML =
              '<div style="padding: 40px; text-align: center;">' +
              '  <i class="fas fa-triangle-exclamation text-danger" style="font-size: 1.5rem;"></i>' +
              '  <p class="text-xs text-danger mt-2">Failed to load attendance matrix. Please try again.</p>' +
              '</div>';
          }
        });
    });
  });
});
