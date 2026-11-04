/* KCC ClassStamp — Subjects: Edit Subject Controller */
(function (window) {
  'use strict';

  function getApp() {
    return window.SubjectsApp || null;
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function initEditSubject() {
    // Guard: only run if the edit modal exists on this page
    if (!getEl('subjectModal')) return;

    // Event delegation on document to catch all Edit button clicks reliably
    document.addEventListener('click', async function (e) {
      const editBtn = e.target.closest('.js-edit-subject');
      if (!editBtn) return;

      e.preventDefault();
      const subjectId = editBtn.dataset.id;
      if (!subjectId) return;

      // Provide visual loading indicator on the edit button
      const originalHtml = editBtn.innerHTML;
      editBtn.disabled = true;
      editBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      try {
        const res = await fetch('/subjects/get/' + subjectId + '/');
        const data = await res.json();
        if (!data.ok) {
          if (window.App && window.App.toast) {
            window.App.toast('error', data.error || 'Failed to load subject details.');
          } else {
            alert(data.error || 'Failed to load subject details.');
          }
          return;
        }

        const s = data.subject;

        const titleEl = getEl('subjectModalTitle');
        if (titleEl) titleEl.textContent = 'Edit Subject';
        const saveBtn = getEl('subjectModalSave');
        if (saveBtn) saveBtn.innerHTML = '<i class="fas fa-floppy-disk"></i> Save Changes';

        const idEl = getEl('subjectId');
        if (idEl) idEl.value = s.id;

        const codeEl = getEl('subjectCode');
        if (codeEl) codeEl.value = s.code;

        const nameEl = getEl('subjectName');
        if (nameEl) nameEl.value = s.name;

        const descEl = getEl('subjectDesc');
        if (descEl) descEl.value = s.description || '';

        const unitEl = getEl('subjectUnits');
        if (unitEl) unitEl.value = s.units || 3;

        const activeEl = getEl('subjectActive');
        if (activeEl) activeEl.checked = Boolean(s.is_active);

        const placement = getEl('subjectCurriculumPlacement');
        if (placement) placement.style.display = 'none';
        const curriculumProgram = getEl('subjectCurriculumProgram');
        if (curriculumProgram) curriculumProgram.value = '';
        const curriculumYear = getEl('subjectCurriculumYear');
        if (curriculumYear) {
          curriculumYear.innerHTML = '<option value="">Select program first</option>';
          curriculumYear.disabled = true;
        }
        const curriculumSemester = getEl('subjectCurriculumSemester');
        if (curriculumSemester) {
          curriculumSemester.value = '';
          curriculumSemester.disabled = true;
        }
        const curriculumMajor = getEl('subjectCurriculumMajor');
        if (curriculumMajor) {
          curriculumMajor.checked = false;
          curriculumMajor.disabled = true;
        }

        const errEl = getEl('subjectFormError');
        if (errEl) errEl.style.display = 'none';

        const App = getApp();
        if (typeof window.openModal === 'function') {
          window.openModal('subjectModal', editBtn);
        } else if (App && App.showModal) {
          App.showModal('subjectModal');
        } else {
          const m = getEl('subjectModal');
          if (m) { m.classList.add('is-active', 'is-open'); document.body.style.overflow = 'hidden'; }
        }
      } catch (err) {
        console.error('Error fetching subject details:', err);
        if (window.App && window.App.toast) {
          window.App.toast('error', 'Network error while loading subject details.');
        } else {
          alert('Network error while loading subject details.');
        }
      } finally {
        editBtn.disabled = false;
        editBtn.innerHTML = originalHtml;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEditSubject);
  } else {
    initEditSubject();
  }
})(window);
