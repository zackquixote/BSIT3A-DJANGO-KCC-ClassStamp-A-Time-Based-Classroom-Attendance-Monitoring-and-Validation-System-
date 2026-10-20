/* KCC ClassStamp — Programs: Add / Edit Modal & Save Controller */
(function (window) {
  'use strict';

  function getApp() { return window.ProgramsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initProgramModal() {
    var form       = getEl('editProgForm');
    var errorBox   = getEl('progFormError');
    var errorMsg   = getEl('progFormErrorMsg');
    var modalTitle = getEl('editProgModalTitle');
    var saveBtn    = getEl('saveProgBtn');

    if (!form) return;

    // Handle Edit / Create button clicks (event delegation)
    document.addEventListener('click', function (e) {
      var editBtn = e.target.closest('[data-modal-target="editProgModal"]');
      if (!editBtn) return;

      if (errorBox) errorBox.style.display = 'none';
      var mode = editBtn.getAttribute('data-mode');

      if (mode === 'edit') {
        if (modalTitle) modalTitle.textContent = 'Edit Program';
        var idEl = getEl('prog_id');
        var deptEl = getEl('prog_department');
        var codeEl = getEl('prog_code');
        var nameEl = getEl('prog_name');
        var yearsEl = getEl('prog_years');
        var actEl = getEl('prog_is_active');

        if (idEl)    idEl.value    = editBtn.getAttribute('data-id') || '';
        if (deptEl)  deptEl.value  = editBtn.getAttribute('data-dept') || '';
        if (codeEl)  codeEl.value  = editBtn.getAttribute('data-code') || '';
        if (nameEl)  nameEl.value  = editBtn.getAttribute('data-name') || '';
        if (yearsEl) yearsEl.value = editBtn.getAttribute('data-years') || '4';
        if (actEl)   actEl.checked = editBtn.getAttribute('data-active') === 'true';
      } else {
        if (modalTitle) modalTitle.textContent = 'Add Program';
        form.reset();
        var idEl2 = getEl('prog_id');
        var yearsEl2 = getEl('prog_years');
        var actEl2 = getEl('prog_is_active');
        if (idEl2)    idEl2.value = '';
        if (yearsEl2) yearsEl2.value = '4';
        if (actEl2)   actEl2.checked = true;
      }

      var App = getApp();
      if (App) {
        App.showModal('editProgModal');
      } else if (typeof window.openModal === 'function') {
        window.openModal('editProgModal');
      } else {
        var modal = getEl('editProgModal');
        if (modal) modal.classList.add('is-active');
      }
    });

    // AJAX save with validation
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var formData = new FormData(form);
      if (saveBtn) saveBtn.disabled = true;

      var saveUrl = form.action || '/programs/save/';

      fetch(saveUrl, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCSRF()
        },
        body: formData
      })
      .then(function (r) {
        return r.json().then(function (data) {
          return { status: r.status, data: data };
        });
      })
      .then(function (res) {
        if (saveBtn) saveBtn.disabled = false;
        if (res.status === 200 && res.data.status === 'success') {
          var App = getApp();
          if (App) App.hideModal('editProgModal');
          else if (typeof window.closeModal === 'function') window.closeModal('editProgModal');
          window.location.reload();
        } else {
          if (errorMsg) errorMsg.textContent = res.data.error || 'Failed to save program.';
          if (errorBox) errorBox.style.display = 'flex';
        }
      })
      .catch(function () {
        if (saveBtn) saveBtn.disabled = false;
        if (errorMsg) errorMsg.textContent = 'Network or server error occurred.';
        if (errorBox) errorBox.style.display = 'flex';
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProgramModal);
  } else {
    initProgramModal();
  }
})(window);
