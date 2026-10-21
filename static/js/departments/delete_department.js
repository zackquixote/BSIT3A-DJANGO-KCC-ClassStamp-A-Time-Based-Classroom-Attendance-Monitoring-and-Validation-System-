/* KCC ClassStamp — Departments: Delete Department Controller */
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

  function initDeleteDepartment() {
    var deleteForm    = getEl('deleteDeptForm');
    var deleteCode    = getEl('delete_dept_code');
    var deleteWarning = getEl('delete_dept_warning');
    var confirmBtn    = getEl('confirmDeleteDeptBtn');

    if (!deleteForm) return;

    // Handle Delete button click (event delegation)
    document.addEventListener('click', function (e) {
      var delBtn = e.target.closest('[data-modal-target="deleteDeptModal"]');
      if (!delBtn) return;

      var deptId = delBtn.getAttribute('data-id');
      var deptCode = delBtn.getAttribute('data-code');
      var progCount = parseInt(delBtn.getAttribute('data-programs') || '0', 10);
      var facCount = parseInt(delBtn.getAttribute('data-faculty') || '0', 10);

      if (deleteCode) deleteCode.textContent = deptCode;
      deleteForm.action = '/departments/delete/' + deptId + '/';

      if (deleteWarning) {
        if (progCount > 0 || facCount > 0) {
          deleteWarning.style.display = 'flex';
        } else {
          deleteWarning.style.display = 'none';
        }
      }

      var App = getApp();
      if (App) {
        App.showModal('deleteDeptModal');
      } else if (typeof window.openModal === 'function') {
        window.openModal('deleteDeptModal');
      } else {
        var modal = getEl('deleteDeptModal');
        if (modal) modal.classList.add('is-active');
      }
    });

    // AJAX delete with form submit fallback
    deleteForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (confirmBtn) confirmBtn.disabled = true;

      fetch(deleteForm.action, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCSRF()
        }
      })
      .then(function (r) {
        return r.json().then(function (data) {
          return { status: r.status, data: data };
        });
      })
      .then(function () {
        if (confirmBtn) confirmBtn.disabled = false;
        var App = getApp();
        if (App) App.hideModal('deleteDeptModal');
        else if (typeof window.closeModal === 'function') window.closeModal('deleteDeptModal');
        window.location.reload();
      })
      .catch(function () {
        if (confirmBtn) confirmBtn.disabled = false;
        deleteForm.submit(); // fallback to standard POST
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteDepartment);
  } else {
    initDeleteDepartment();
  }
})(window);
