/* KCC ClassStamp — Users: Common Utilities & Helpers */
(function (window) {
  'use strict';

  window.UsersApp = window.UsersApp || {};

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
    if (isError === undefined) isError = false;
    var alertBox  = getEl('userAlert');
    var alertText = getEl('userAlertText');
    if (!alertBox || !alertText) return;
    alertText.textContent = msg;
    alertBox.className = 'toast ' + (isError ? 'toast--error' : 'toast--success') + ' mb-4';
    alertBox.style.display = 'flex';
    setTimeout(function () { alertBox.style.display = 'none'; }, 4500);
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
  Object.defineProperty(window.UsersApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.UsersApp.getCSRFToken = getCSRFToken;
  window.UsersApp.getEl = getEl;
  window.UsersApp.showAlert = showAlert;
  window.UsersApp.showModal = showModal;
  window.UsersApp.hideModal = hideModal;
})(window);
