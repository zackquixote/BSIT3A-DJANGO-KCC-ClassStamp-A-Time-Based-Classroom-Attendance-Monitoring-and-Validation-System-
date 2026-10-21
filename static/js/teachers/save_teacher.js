/* KCC ClassStamp — Teachers: Save (Create / Update) Controller */
(function (window) {
  'use strict';

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  function initSaveTeacher() {
    // Guard: only run if the save button exists on this page
    var saveBtn = getEl('teacherModalSave');
    if (!saveBtn) return;

    saveBtn.addEventListener('click', async function () {
      var profileId = getEl('teacherId').value;
      var isEdit = !!profileId;
      var form = getEl('teacherForm');
      if (!form) return;

      var fd = new FormData(form);
      var activeEl = getEl('teacherIsActive');
      fd.set('is_active', (activeEl && activeEl.checked) ? '1' : '0');

      var errEl = getEl('teacherFormError');
      var App = getApp();

      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      try {
        var url = isEdit ? '/teachers/update/' + profileId + '/' : '/teachers/create/';
        var res = await fetch(url, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() },
          body: fd,
        });
        var data = await res.json();

        if (data.ok) {
          if (data.generated_password) {
            var gpwEl = getEl('teacherGeneratedPw');
            if (App) App.showAlert(gpwEl, '\u2705 Account created. Temporary password: ' + data.generated_password, 'success');
            else if (gpwEl) { gpwEl.style.display = 'block'; gpwEl.textContent = '\u2705 Account created. Temporary password: ' + data.generated_password; }
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Teacher';
            setTimeout(function () { location.reload(); }, 5000);
          } else {
            if (App) App.hideModal('teacherModal');
            else { var m = getEl('teacherModal'); if (m) { m.classList.remove('is-active'); document.body.style.overflow = ''; } }

            var successEl = getEl('teacherSuccess');
            if (App) App.showAlert(successEl, data.message, 'success');
            else if (successEl) { successEl.style.display = 'block'; successEl.textContent = data.message; }
            setTimeout(function () { location.reload(); }, 1000);
          }
        } else {
          if (App) App.showAlert(errEl, data.error);
          else if (errEl) { errEl.style.display = 'block'; errEl.textContent = data.error; }
          saveBtn.disabled = false;
          saveBtn.innerHTML = isEdit
            ? '<i class="fas fa-floppy-disk"></i> Update Teacher'
            : '<i class="fas fa-user-plus"></i> Create Teacher';
        }
      } catch (err) {
        if (App) App.showAlert(errEl, 'Network error. Please try again.');
        else if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Network error. Please try again.'; }
        saveBtn.disabled = false;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSaveTeacher);
  } else {
    initSaveTeacher();
  }
})(window);
