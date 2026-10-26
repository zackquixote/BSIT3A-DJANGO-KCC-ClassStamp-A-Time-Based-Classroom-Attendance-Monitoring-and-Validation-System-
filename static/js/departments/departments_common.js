/* KCC ClassStamp — Departments: Common Utilities & Helpers */
(function (window) {
  'use strict';

  window.DepartmentsApp = window.DepartmentsApp || {};

  function getCSRFToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) {
      return meta.getAttribute('content');
    }
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
      return input.value;
    }
    return '';
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function showAlert(msg, isError) {
    if (isError === undefined) isError = true;
    if (window.App && window.App.toast) { window.App.toast(isError ? 'error' : 'success', msg); return; }
    var alertBox = getEl('deptAlert');
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.className = 'toast ' + (isError ? 'toast--error' : 'toast--success') + ' mb-4';
    alertBox.style.display = 'flex';
    setTimeout(function () { alertBox.style.display = 'none'; }, 4000);
  }

  function showModal(id) {
    if (typeof window.openModal === 'function') {
      window.openModal(id);
    } else {
      var m = getEl(id);
      if (m) m.classList.add('is-active');
    }
  }

  function hideModal(id) {
    if (typeof window.closeModal === 'function') {
      window.closeModal(id);
    } else {
      var m = getEl(id);
      if (m) m.classList.remove('is-active');
    }
  }

  // Export to namespace
  Object.defineProperty(window.DepartmentsApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.DepartmentsApp.getCSRFToken = getCSRFToken;
  window.DepartmentsApp.getEl = getEl;
  window.DepartmentsApp.showAlert = showAlert;
  window.DepartmentsApp.showModal = showModal;
  window.DepartmentsApp.hideModal = hideModal;
})(window);
