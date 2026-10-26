/* KCC ClassStamp — Subjects: Add Subject Controller */
(function (window) {
  'use strict';

  function getApp() { return window.SubjectsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    const App = getApp();
    if (App && App.CSRF) return App.CSRF;
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  function initAddSubject() {
    // Guard: only run if the add/edit subject modal exists on this page
    if (!getEl('addSubjectBtn')) return;

    const inlineDeptSel = getEl('inlineDept');
    const inlineProgSel = getEl('inlineProgram');
    const inlineYearSel = getEl('inlineYearLevel');

    // Inline curriculum cascade
    if (inlineDeptSel) {
      inlineDeptSel.addEventListener('change', function () {
        const App = getApp();
        if (App) App.populatePrograms(inlineProgSel, this.value, inlineYearSel);
      });
    }
    if (inlineProgSel) {
      inlineProgSel.addEventListener('change', function () {
        const App = getApp();
        if (App) App.populateYears(inlineProgSel, inlineYearSel);
      });
    }

    // Toggle collapsible curriculum section
    const toggleBtn = getEl('toggleCurrSection');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        const section = getEl('inlineCurrSection');
        const icon = getEl('toggleCurrIcon');
        if (!section) return;
        const open = section.style.display === 'none';
        section.style.display = open ? 'block' : 'none';
        if (icon) icon.style.transform = open ? 'rotate(90deg)' : '';
      });
    }

    // Add Subject button click
    const addBtn = getEl('addSubjectBtn');
    if (addBtn) {
      addBtn.addEventListener('click', function () {
        const titleEl = getEl('subjectModalTitle'); if (titleEl) titleEl.textContent = 'Add Subject';
        const idEl    = getEl('subjectId');          if (idEl)    idEl.value = '';
        const codeEl  = getEl('subjectCode');        if (codeEl)  codeEl.value = '';
        const nameEl  = getEl('subjectName');        if (nameEl)  nameEl.value = '';
        const descEl  = getEl('subjectDesc');        if (descEl)  descEl.value = '';
        const actEl   = getEl('subjectActive');      if (actEl)   actEl.checked = true;
        const errEl   = getEl('subjectFormError');   if (errEl)   errEl.style.display = 'none';

        // Reset inline curriculum section
        const inlineCurrSection = getEl('inlineCurrSection');
        if (inlineCurrSection) inlineCurrSection.style.display = 'none';
        const toggleCurrIcon = getEl('toggleCurrIcon');
        if (toggleCurrIcon) toggleCurrIcon.style.transform = '';
        if (inlineDeptSel) inlineDeptSel.value = '';
        if (inlineProgSel) { inlineProgSel.innerHTML = '<option value="">— program —</option>'; inlineProgSel.disabled = true; }
        if (inlineYearSel) { inlineYearSel.innerHTML = '<option value="">— year —</option>'; inlineYearSel.disabled = true; }

        const App = getApp();
        if (typeof window.openModal === 'function') {
          window.openModal('subjectModal', addBtn);
        } else if (App && App.showModal) {
          App.showModal('subjectModal');
        } else {
          const m = getEl('subjectModal');
          if (m) { m.classList.add('is-active', 'is-open'); document.body.style.overflow = 'hidden'; }
        }
      });
    }

    // Save Subject (+ optional inline curriculum)
    const saveBtn = getEl('subjectModalSave');
    if (saveBtn) {
      saveBtn.addEventListener('click', async function () {
        const form = getEl('subjectForm');
        if (!form) return;

        const fd = new FormData(form);
        const activeEl = getEl('subjectActive');
        fd.set('is_active', (activeEl && activeEl.checked) ? '1' : '0');

        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(saveBtn, true, 'Saving Subject...');
        } else {
          saveBtn.disabled = true;
          saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving\u2026';
        }

        const App = getApp();

        try {
          const res = await fetch('/subjects/save/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
            body: fd,
          });
          const data = await res.json();
          if (!data.ok) {
            const errEl = getEl('subjectFormError');
            if (window.App && window.App.toast) {
              window.App.toast('error', data.error || 'Failed to save subject.');
            } else if (errEl) { errEl.style.display = 'block'; errEl.textContent = data.error; }
            return;
          }

          // Optionally assign to curriculum right now if inputs provided
          const progId = inlineProgSel && inlineProgSel.value;
          const yearLevel = inlineYearSel && inlineYearSel.value;
          if (data.subject && progId && yearLevel) {
            const cfd = new FormData();
            cfd.append('subject_id', data.subject.id);
            cfd.append('program_id', progId);
            cfd.append('year_level', yearLevel);
            try {
              await fetch('/subjects/curriculum/assign/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCSRF() },
                body: cfd,
              });
            } catch (_) { /* non-fatal */ }
          }

          if (typeof window.closeModal === 'function') {
            window.closeModal('subjectModal');
          } else if (App && App.hideModal) {
            App.hideModal('subjectModal');
          } else {
            const m = getEl('subjectModal');
            if (m) { m.classList.remove('is-active', 'is-open'); document.body.style.overflow = ''; }
          }

          const successEl = getEl('subjectSuccess');
          if (window.App && window.App.toast) {
            window.App.toast('success', data.message);
          } else if (successEl) { successEl.style.display = 'block'; successEl.textContent = data.message; }
          setTimeout(function () { location.reload(); }, 600);
        } catch (err) {
          const errEl = getEl('subjectFormError');
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Server or network error');
          } else if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Server or network error'; }
        } finally {
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(saveBtn, false);
          } else {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-floppy-disk"></i> Save Subject';
          }
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAddSubject);
  } else {
    initAddSubject();
  }
})(window);
