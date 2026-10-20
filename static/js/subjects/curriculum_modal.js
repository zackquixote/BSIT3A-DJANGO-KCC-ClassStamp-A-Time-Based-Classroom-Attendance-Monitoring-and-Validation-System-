/* KCC ClassStamp — Subjects: Curriculum Mapping Modal Controller */
(function (window) {
  'use strict';

  let activeCurrSubjectId = null;

  function getApp() { return window.SubjectsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    const App = getApp();
    if (App && App.CSRF) return App.CSRF;
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  async function loadCurriculumEntries() {
    const container = getEl('curriculumEntries');
    if (!container || !activeCurrSubjectId) return;

    container.innerHTML = '<div class="text-muted text-sm text-center" style="padding:20px;"><i class="fas fa-spinner fa-spin"></i> Loading mappings\u2026</div>';

    try {
      const res = await fetch('/subjects/' + activeCurrSubjectId + '/curriculum/');
      const data = await res.json();
      if (!data.entries || !data.entries.length) {
        container.innerHTML = '<div class="text-muted text-sm text-center" style="padding:20px;">No curriculum mappings yet.</div>';
        return;
      }

      const App = getApp();
      container.innerHTML = data.entries.map(function (e) {
        const ordinal = App ? App.ordinalSuffix(e.year_level) : e.year_level;
        return '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border:1px solid var(--glass-border);border-radius:8px;margin-bottom:8px;">'
          + '<span>'
          + '<span class="badge badge--purple">' + e.program_code + '</span>'
          + ' <span class="text-muted text-sm">' + ordinal + ' Year</span>'
          + '</span>'
          + '<button type="button" class="btn btn-danger btn-sm js-remove-curr" data-id="' + e.id + '">'
          + '<i class="fas fa-xmark"></i> Remove'
          + '</button>'
          + '</div>';
      }).join('');
    } catch (err) {
      container.innerHTML = '<div class="text-danger text-sm text-center" style="padding:20px;">Failed to load curriculum entries.</div>';
    }
  }

  function initCurriculumModal() {
    // Guard: only run if curriculum modal exists on this page
    if (!getEl('curriculumModal')) return;

    const currDeptSel = getEl('currDept');
    const currProgSel = getEl('currProgram');
    const currYearSel = getEl('currYearLevel');

    // Cascades inside curriculum modal
    if (currDeptSel) {
      currDeptSel.addEventListener('change', function () {
        const App = getApp();
        if (App) App.populatePrograms(currProgSel, this.value, currYearSel);
      });
    }
    if (currProgSel) {
      currProgSel.addEventListener('change', function () {
        const App = getApp();
        if (App) App.populateYears(currProgSel, currYearSel);
      });
    }

    // Event delegation for opening the curriculum modal
    document.addEventListener('click', async function (e) {
      // 1. Clicked on the curriculum sitemap action button
      const currBtn = e.target.closest('.js-curriculum-btn');
      if (currBtn) {
        e.preventDefault();
        activeCurrSubjectId = currBtn.dataset.id;

        const codeEl = getEl('currSubjectCode');
        if (codeEl) codeEl.textContent = currBtn.dataset.code || '';

        const errEl = getEl('currAssignError');
        if (errEl) errEl.style.display = 'none';

        // Reset cascade
        if (currDeptSel) currDeptSel.value = '';
        if (currProgSel) { currProgSel.innerHTML = '<option value="">— program —</option>'; currProgSel.disabled = true; }
        if (currYearSel) { currYearSel.innerHTML = '<option value="">— year —</option>'; currYearSel.disabled = true; }

        const App = getApp();
        if (App) App.showModal('curriculumModal');
        else { const m = getEl('curriculumModal'); if (m) { m.classList.add('is-active'); document.body.style.overflow = 'hidden'; } }

        await loadCurriculumEntries();
        return;
      }

      // 2. Clicked on the curriculum counter badge in the table
      const badge = e.target.closest('.js-curr-badge');
      if (badge) {
        e.preventDefault();
        const row = badge.closest('tr');
        const actionBtn = row && row.querySelector('.js-curriculum-btn');
        if (actionBtn) actionBtn.click();
        return;
      }

      // 3. Clicked on remove curriculum mapping button inside the modal
      const removeBtn = e.target.closest('.js-remove-curr');
      if (removeBtn) {
        var confirmed = window.App && window.App.confirm
          ? await window.App.confirm({
              title: 'Remove Curriculum Entry',
              message: 'Are you sure you want to remove this curriculum mapping entry?',
              confirmText: 'Remove',
              confirmClass: 'btn-danger',
              type: 'danger'
            })
          : confirm('Remove this curriculum entry?');

        if (!confirmed) return;
        removeBtn.disabled = true;
        removeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
          const r = await fetch('/subjects/curriculum/remove/' + removeBtn.dataset.id + '/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
          });
          const d = await r.json();
          if (d.ok) {
            if (window.App && window.App.toast) {
              window.App.toast('success', 'Curriculum mapping removed.');
            }
            await loadCurriculumEntries();
          } else {
            if (window.App && window.App.toast) {
              window.App.toast('error', d.error || 'Failed to remove curriculum entry.');
            } else {
              alert(d.error || 'Failed to remove curriculum entry.');
            }
            removeBtn.disabled = false;
            removeBtn.innerHTML = '<i class="fas fa-xmark"></i> Remove';
          }
        } catch (err) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Network error while removing curriculum mapping.');
          } else {
            alert('Network error while removing curriculum mapping.');
          }
          removeBtn.disabled = false;
          removeBtn.innerHTML = '<i class="fas fa-xmark"></i> Remove';
        }
        return;
      }
    });

    // Assign to curriculum button click
    const assignBtn = getEl('currAssignBtn');
    if (assignBtn) {
      assignBtn.addEventListener('click', async function () {
        const programId = currProgSel && currProgSel.value;
        const yearLevel = currYearSel && currYearSel.value;
        const errEl = getEl('currAssignError');
        const App = getApp();

        if (!currDeptSel || !currDeptSel.value) { if (App) App.showAlert(errEl, 'Please select a department first.'); return; }
        if (!programId)  { if (App) App.showAlert(errEl, 'Please select a program.'); return; }
        if (!yearLevel)  { if (App) App.showAlert(errEl, 'Please select a year level.'); return; }

        assignBtn.disabled = true;
        assignBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        const fd = new FormData();
        fd.append('subject_id', activeCurrSubjectId);
        fd.append('program_id', programId);
        fd.append('year_level', yearLevel);

        try {
          const res = await fetch('/subjects/curriculum/assign/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
            body: fd,
          });
          const data = await res.json();
          if (data.ok) {
            if (errEl) errEl.style.display = 'none';
            await loadCurriculumEntries();
          } else {
            if (App) App.showAlert(errEl, data.error);
            else if (errEl) { errEl.style.display = 'block'; errEl.textContent = data.error; }
          }
        } catch (err) {
          if (App) App.showAlert(errEl, 'Failed to assign curriculum entry.');
          else if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Failed to assign curriculum entry.'; }
        } finally {
          assignBtn.disabled = false;
          assignBtn.innerHTML = '<i class="fas fa-plus"></i> Assign';
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCurriculumModal);
  } else {
    initCurriculumModal();
  }
})(window);
