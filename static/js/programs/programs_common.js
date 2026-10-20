/* KCC ClassStamp — Programs: Common Utilities & Helpers */
(function (window) {
  'use strict';

  window.ProgramsApp = window.ProgramsApp || {};

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
    var alertBox = getEl('progAlert');
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
  Object.defineProperty(window.ProgramsApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.ProgramsApp.getCSRFToken = getCSRFToken;
  window.ProgramsApp.getEl = getEl;
  window.ProgramsApp.showAlert = showAlert;
  window.ProgramsApp.showModal = showModal;
  window.ProgramsApp.hideModal = hideModal;
})(window);
