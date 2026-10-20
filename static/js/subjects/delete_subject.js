/* KCC ClassStamp — Subjects: Delete Subject Controller */
(function (window) {
  'use strict';

  let deleteSubjectId = null;

  function getApp() {
    return window.SubjectsApp || null;
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function initDeleteSubject() {
    // Guard: only run if the delete modal exists on this page
    if (!getEl('subjectDeleteModal')) return;

    // Event delegation on document to catch Delete button clicks reliably
    document.addEventListener('click', function (e) {
      const delBtn = e.target.closest('.js-delete-subject');
      if (!delBtn) return;

      e.preventDefault();
      deleteSubjectId = delBtn.dataset.id;
      if (!deleteSubjectId) return;

      const codeEl = getEl('subjectDeleteCode');
      if (codeEl) codeEl.textContent = delBtn.dataset.code || '';

      const errEl = getEl('subjectDeleteError');
      if (errEl) errEl.style.display = 'none';

      const App = getApp();
      if (App) {
        App.showModal('subjectDeleteModal');
      } else {
        const m = getEl('subjectDeleteModal');
        if (m) { m.classList.add('is-active'); document.body.style.overflow = 'hidden'; }
      }
    });

    // Confirm deletion
    const confirmBtn = getEl('subjectDeleteConfirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', async function () {
        if (!deleteSubjectId) return;

        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing\u2026';

        const App = getApp();
        const csrf = App ? App.CSRF : (
          (document.querySelector('meta[name="csrf-token"]') || {}).getAttribute
            ? document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            : ''
        );

        try {
          const res = await fetch('/subjects/delete/' + deleteSubjectId + '/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf },
          });
          const data = await res.json();
          if (data.ok) {
            if (App) App.hideModal('subjectDeleteModal');
            else {
              const m = getEl('subjectDeleteModal');
              if (m) { m.classList.remove('is-active'); document.body.style.overflow = ''; }
            }
            const successEl = getEl('subjectSuccess');
            if (App) App.showAlert(successEl, data.message, 'success');
            else if (successEl) { successEl.style.display = 'block'; successEl.textContent = data.message; }
            setTimeout(function () { location.reload(); }, 800);
          } else {
            const errEl = getEl('subjectDeleteError');
            if (App) App.showAlert(errEl, data.error);
            else if (errEl) { errEl.style.display = 'block'; errEl.textContent = data.error; }
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
          }
        } catch (err) {
          const errEl = getEl('subjectDeleteError');
          if (App) App.showAlert(errEl, 'Network error');
          else if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Network error'; }
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteSubject);
  } else {
    initDeleteSubject();
  }
})(window);
