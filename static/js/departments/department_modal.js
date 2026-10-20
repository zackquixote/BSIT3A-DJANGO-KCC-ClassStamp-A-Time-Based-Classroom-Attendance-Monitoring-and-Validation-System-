/* KCC ClassStamp — Departments: Add / Edit Modal & Save Controller */
(function (window) {
  'use strict';

  function getApp() { return window.DepartmentsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initDepartmentModal() {
    var form       = getEl('editDeptForm');
    var errorBox   = getEl('deptFormError');
    var errorMsg   = getEl('deptFormErrorMsg');
    var modalTitle = getEl('editDeptModalTitle');
    var saveBtn    = getEl('saveDeptBtn');

    if (!form) return;

    // Handle Edit / Create button clicks (event delegation)
    document.addEventListener('click', function (e) {
      var editBtn = e.target.closest('[data-modal-target="editDeptModal"]');
      if (!editBtn) return;

      if (errorBox) errorBox.style.display = 'none';
      var mode = editBtn.getAttribute('data-mode');

      if (mode === 'edit') {
        if (modalTitle) modalTitle.textContent = 'Edit Department';
        var idEl = getEl('dept_id');
        var codeEl = getEl('dept_code');
        var nameEl = getEl('dept_name');
        var actEl = getEl('dept_is_active');

        if (idEl)   idEl.value   = editBtn.getAttribute('data-id') || '';
        if (codeEl) codeEl.value = editBtn.getAttribute('data-code') || '';
        if (nameEl) nameEl.value = editBtn.getAttribute('data-name') || '';
        if (actEl)  actEl.checked = editBtn.getAttribute('data-active') === 'true';
      } else {
        if (modalTitle) modalTitle.textContent = 'Add Department';
        form.reset();
        var idEl2 = getEl('dept_id');
        var actEl2 = getEl('dept_is_active');
        if (idEl2)  idEl2.value = '';
        if (actEl2) actEl2.checked = true;
      }

      var App = getApp();
      if (App) {
        App.showModal('editDeptModal');
      } else if (typeof window.openModal === 'function') {
        window.openModal('editDeptModal');
      } else {
        var modal = getEl('editDeptModal');
        if (modal) modal.classList.add('is-active');
      }
    });

    // AJAX save with validation
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var formData = new FormData(form);
      if (saveBtn) saveBtn.disabled = true;

      var saveUrl = form.action || '/departments/save/';

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
          if (App) App.hideModal('editDeptModal');
          else if (typeof window.closeModal === 'function') window.closeModal('editDeptModal');
          window.location.reload();
        } else {
          if (errorMsg) errorMsg.textContent = res.data.error || 'Failed to save department.';
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
    document.addEventListener('DOMContentLoaded', initDepartmentModal);
  } else {
    initDepartmentModal();
  }
})(window);
