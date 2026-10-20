/* KCC ClassStamp — Teachers: Delete Teacher Controller */
(function (window) {
  'use strict';

  var deleteTeacherId = null;

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  function initDeleteTeacher() {
    // Guard: only run if the delete modal exists on this page
    if (!getEl('teacherDeleteModal')) return;

    // Event delegation on document to catch Delete button clicks reliably
    document.addEventListener('click', function (e) {
      var delBtn = e.target.closest('.js-delete-teacher');
      if (!delBtn) return;

      e.preventDefault();
      deleteTeacherId = delBtn.dataset.id;
      if (!deleteTeacherId) return;

      var nameEl = getEl('teacherDeleteName');
      if (nameEl) nameEl.textContent = delBtn.dataset.name || '';

      var errEl = getEl('teacherDeleteError');
      if (errEl) errEl.style.display = 'none';

      var App = getApp();
      if (App) App.showModal('teacherDeleteModal');
      else { var m = getEl('teacherDeleteModal'); if (m) { m.classList.add('is-active'); document.body.style.overflow = 'hidden'; } }
    });

    // Confirm deletion
    var confirmBtn = getEl('teacherDeleteConfirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', async function () {
        if (!deleteTeacherId) return;

        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing\u2026';

        var App = getApp();

        try {
          var res = await fetch('/teachers/delete/' + deleteTeacherId + '/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
          });
          var data = await res.json();
          if (data.ok) {
            if (App) App.hideModal('teacherDeleteModal');
            else { var m = getEl('teacherDeleteModal'); if (m) { m.classList.remove('is-active'); document.body.style.overflow = ''; } }

            var successEl = getEl('teacherSuccess');
            if (App) App.showAlert(successEl, data.message, 'success');
            else if (successEl) { successEl.style.display = 'block'; successEl.textContent = data.message; }
            setTimeout(function () { location.reload(); }, 800);
          } else {
            var errEl = getEl('teacherDeleteError');
            if (App) App.showAlert(errEl, data.error);
            else if (errEl) { errEl.style.display = 'block'; errEl.textContent = data.error; }
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
          }
        } catch (err) {
          var errEl = getEl('teacherDeleteError');
          if (App) App.showAlert(errEl, 'Network error');
          else if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Network error'; }
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteTeacher);
  } else {
    initDeleteTeacher();
  }
})(window);
