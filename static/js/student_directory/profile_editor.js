/* KCC ClassStamp — Student Directory: In-Place Profile Editor (A-03) */
(function () {
  'use strict';

  function getEl(id) { return document.getElementById(id); }

  function toast(type, msg) {
    if (window.App && typeof window.App.toast === 'function') {
      window.App.toast(type, msg);
      return;
    }
    var alertBox = getEl('studentEditAlert');
    if (alertBox) {
      alertBox.textContent = msg;
      alertBox.className = 'toast toast--' + (type === 'error' ? 'error' : 'success') + ' mb-4';
      alertBox.style.display = 'flex';
      setTimeout(function () { alertBox.style.display = 'none'; }, 5000);
    }
  }

  function openModal() {
    if (window.openModal) { window.openModal('studentEditModal'); return; }
    var m = getEl('studentEditModal');
    if (m) m.classList.add('is-active');
  }

  function closeModal() {
    if (window.closeModal) { window.closeModal('studentEditModal'); return; }
    var m = getEl('studentEditModal');
    if (m) m.classList.remove('is-active');
  }

  function filterPrograms(deptId) {
    var prog = getEl('studentEditProg');
    if (!prog) return;
    var current = prog.value;
    var sawCurrent = false;
    Array.prototype.forEach.call(prog.options, function (opt) {
      if (!opt.value) { opt.hidden = false; return; }
      var matches = !deptId || opt.getAttribute('data-dept') === deptId;
      opt.hidden = !matches;
      if (matches && opt.value === current) sawCurrent = true;
    });
    if (!sawCurrent) prog.value = '';
  }

  function openEditor(btn) {
    getEl('studentEditId').value = btn.getAttribute('data-student-id');
    getEl('studentEditFirstName').value = btn.getAttribute('data-first-name') || '';
    getEl('studentEditLastName').value = btn.getAttribute('data-last-name') || '';
    getEl('studentEditNumber').value = btn.getAttribute('data-student-number') || '';
    getEl('studentEditYear').value = btn.getAttribute('data-year-level') || '1';
    getEl('studentEditDept').value = btn.getAttribute('data-dept-id') || '';
    getEl('studentEditProg').value = btn.getAttribute('data-prog-id') || '';
    getEl('studentEditResetQr').checked = false;
    var alertBox = getEl('studentEditAlert');
    if (alertBox) alertBox.style.display = 'none';
    filterPrograms(btn.getAttribute('data-dept-id') || '');
    openModal();
  }

  function initialsOf(first, last) {
    var f = (first || '').trim().charAt(0).toUpperCase();
    var l = (last || '').trim().charAt(0).toUpperCase();
    return (f || '?') + (l || '?');
  }

  function updateRow(data, studentId) {
    var row = document.getElementById('student-row-' + studentId);
    if (!row) return;

    var oldNumber = row.querySelector('.cell-id .student-id-tag');
    var oldNumberText = oldNumber ? oldNumber.textContent.trim() : '';
    var newNumber = data.student_number || '';

    var idTag = row.querySelector('.cell-id .student-id-tag');
    if (idTag) idTag.textContent = newNumber || '—';

    var nameLinks = row.querySelectorAll('.student-name a, .student-cell-profile > a');
    nameLinks.forEach(function (link) {
      if (oldNumberText && newNumber && oldNumberText !== newNumber) {
        link.href = link.href.replace(encodeURIComponent(oldNumberText), encodeURIComponent(newNumber));
      }
      link.title = data.full_name;
    });

    var nameAnchor = row.querySelector('.student-name a');
    if (nameAnchor) nameAnchor.textContent = data.full_name;

    var avatar = row.querySelector('.student-avatar-initial');
    if (avatar) avatar.textContent = initialsOf(data.full_name.split(' ')[0], data.full_name.split(' ').slice(1).join(' '));

    var deptCell = row.querySelector('.cell-dept');
    if (deptCell) {
      deptCell.innerHTML = data.department_code
        ? '<span class="font-semibold text-primary">' + data.department_code + '</span>'
        : '<span class="text-muted">—</span>';
    }

    var progCell = row.querySelector('.cell-prog');
    if (progCell) {
      progCell.innerHTML = data.program_code
        ? '<span class="font-semibold text-gold">' + data.program_code + '</span>' +
          '<span class="text-muted text-xs block" style="max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="' + data.program_name + '">' + data.program_name + '</span>'
        : '<span class="text-muted">—</span>';
    }

    var yearCell = row.querySelector('.cell-year');
    if (yearCell) {
      yearCell.innerHTML = data.year_level
        ? '<span class="badge badge--purple font-semibold">Yr ' + data.year_level + '</span>'
        : '<span class="text-muted">—</span>';
    }
  }

  function init() {
    var deptSelect = getEl('studentEditDept');
    if (deptSelect) deptSelect.addEventListener('change', function () { filterPrograms(deptSelect.value); });

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.js-edit-student');
      if (btn) { e.preventDefault(); openEditor(btn); }
    });

    var form = getEl('studentEditForm');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var alertBox = getEl('studentEditAlert');
        var config = window.ProfileEditorConfig || {};
        var csrf = form.querySelector('[name=csrfmiddlewaretoken]');
        var saveBtn = getEl('studentEditSaveBtn');
        var studentId = getEl('studentEditId').value;

        if (saveBtn) saveBtn.disabled = true;

        fetch(config.updateUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf ? csrf.value : '' },
          body: new FormData(form)
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
          if (saveBtn) saveBtn.disabled = false;
          if (res.ok && res.data.status === 'success') {
            updateRow(res.data, studentId);
            closeModal();
            var msg = 'Student profile updated.' + (res.data.qr_reset ? ' TOTP QR secret has been reset.' : '');
            toast('success', msg);
          } else {
            var errors = (res.data && res.data.errors) || {};
            var text = Object.keys(errors).map(function (k) { return errors[k]; }).join(' ') || 'Failed to update student profile.';
            if (alertBox) {
              alertBox.textContent = text;
              alertBox.style.display = 'flex';
            }
          }
        })
        .catch(function () {
          if (saveBtn) saveBtn.disabled = false;
          if (alertBox) {
            alertBox.textContent = 'Network communication error while saving.';
            alertBox.style.display = 'flex';
          }
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
