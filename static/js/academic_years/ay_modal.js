/* KCC ClassStamp — Academic Years: Add / Edit Modal & Save Controller */
(function (window) {
  'use strict';

  function getApp() { return window.AcademicYearsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initAyModal() {
    var addBtn = getEl('addAyBtn');
    var modal = getEl('ayModal');
    if (!modal && !addBtn) return;

    var modalTitle = getEl('ayModalTitle');
    var ayId       = getEl('ayId');
    var ayName     = getEl('ayName');
    var ayStartsOn = getEl('ayStartsOn');
    var ayEndsOn   = getEl('ayEndsOn');
    var ayIsActive = getEl('ayIsActive');
    var formError  = getEl('ayFormError');
    var saveBtn    = getEl('ayModalSave');

    // Open modal (create)
    if (addBtn) {
      addBtn.addEventListener('click', function () {
        if (modalTitle) modalTitle.textContent = 'Add Academic Year';
        if (ayId)       ayId.value = '';
        if (ayName)     ayName.value = '';
        if (ayStartsOn) ayStartsOn.value = '';
        if (ayEndsOn)   ayEndsOn.value = '';
        if (ayIsActive) ayIsActive.checked = false;
        if (formError)  formError.style.display = 'none';

        var App = getApp();
        if (App) App.showModal('ayModal');
        else if (window.openModal) window.openModal('ayModal');
        else if (modal) modal.classList.add('is-active');
      });
    }

    // Close modal handlers
    ['ayModalClose', 'ayModalCancel'].forEach(function (btnId) {
      var el = getEl(btnId);
      if (el) {
        el.addEventListener('click', function () {
          var App = getApp();
          if (App) App.hideModal('ayModal');
          else if (window.closeModal) window.closeModal('ayModal');
          else if (modal) modal.classList.remove('is-active');
        });
      }
    });

    // Save Academic Year
    if (saveBtn) {
      saveBtn.addEventListener('click', async function () {
        var form = getEl('ayForm');
        var errEl = getEl('ayFormError');
        var successEl = getEl('aySuccess');
        var App = getApp();

        if (!form) return;

        var fd = new FormData(form);
        fd.set('is_active', (ayIsActive && ayIsActive.checked) ? '1' : '0');

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

        try {
          var res = await fetch('/academic-years/save/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
            body: fd
          });
          var data = await res.json();
          if (data.ok) {
            if (App) App.hideModal('ayModal');
            else if (window.closeModal) window.closeModal('ayModal');
            else if (modal) modal.classList.remove('is-active');

            if (App) App.showAlert(successEl, data.message, 'success');
            setTimeout(function () { location.reload(); }, 1000);
          } else {
            if (App) App.showAlert(errEl, data.error);
            else if (errEl) { errEl.textContent = data.error; errEl.style.display = 'block'; }
          }
        } catch (_) {
          if (App) App.showAlert(errEl, 'Server or network error');
          else if (errEl) { errEl.textContent = 'Server or network error'; errEl.style.display = 'block'; }
        } finally {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '<i class="fas fa-floppy-disk"></i> Save Term';
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAyModal);
  } else {
    initAyModal();
  }
})(window);
