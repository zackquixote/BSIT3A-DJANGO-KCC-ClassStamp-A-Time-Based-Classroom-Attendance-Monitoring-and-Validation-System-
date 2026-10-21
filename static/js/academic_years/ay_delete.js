/* KCC ClassStamp — Academic Years: Delete Academic Year Controller */
(function (window) {
  'use strict';

  var deleteTargetId = null;

  function getApp() { return window.AcademicYearsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initAyDelete() {
    var modal = getEl('ayDeleteModal');

    // Open delete modal (event delegation)
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.js-delete-ay');
      if (!btn) return;

      deleteTargetId = btn.dataset.id;
      var nameEl = getEl('ayDeleteName');
      var errEl  = getEl('ayDeleteError');
      if (nameEl) nameEl.textContent = btn.dataset.name || '';
      if (errEl)  errEl.style.display = 'none';

      var App = getApp();
      if (App) App.showModal('ayDeleteModal');
      else if (window.openModal) window.openModal('ayDeleteModal');
      else if (modal) modal.classList.add('is-active');
    });

    // Close delete modal handlers
    ['ayDeleteModalClose', 'ayDeleteCancel'].forEach(function (btnId) {
      var el = getEl(btnId);
      if (el) {
        el.addEventListener('click', function () {
          var App = getApp();
          if (App) App.hideModal('ayDeleteModal');
          else if (window.closeModal) window.closeModal('ayDeleteModal');
          else if (modal) modal.classList.remove('is-active');
        });
      }
    });

    // Confirm delete click
    var confirmBtn = getEl('ayDeleteConfirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', async function () {
        var errEl = getEl('ayDeleteError');
        var successEl = getEl('aySuccess');
        var App = getApp();

        if (!deleteTargetId) return;

        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
          var res = await fetch('/academic-years/delete/' + deleteTargetId + '/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() }
          });
          var data = await res.json();
          if (data.ok) {
            if (App) App.hideModal('ayDeleteModal');
            else if (window.closeModal) window.closeModal('ayDeleteModal');
            else if (modal) modal.classList.remove('is-active');

            if (App) App.showAlert(successEl, data.message, 'success');
            setTimeout(function () { location.reload(); }, 800);
          } else {
            if (App) App.showAlert(errEl, data.error);
            else if (errEl) { errEl.textContent = data.error; errEl.style.display = 'block'; }
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
          }
        } catch (_) {
          if (App) App.showAlert(errEl, 'Network error');
          else if (errEl) { errEl.textContent = 'Network error'; errEl.style.display = 'block'; }
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Remove';
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAyDelete);
  } else {
    initAyDelete();
  }
})(window);
