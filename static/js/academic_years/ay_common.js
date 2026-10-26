/* KCC ClassStamp — Academic Years: Common Utilities & Helpers */
(function (window) {
  'use strict';

  window.AcademicYearsApp = window.AcademicYearsApp || {};

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

  function showAlert(el, msg, type) {
    if (!type) type = 'error';
    if (window.App && window.App.toast) { window.App.toast(type, msg); return; }
    if (!el) return;
    el.style.display = 'block';
    el.className = 'toast toast--' + type + ' mb-4';
    el.textContent = msg;
    if (type === 'success') {
      setTimeout(function () { el.style.display = 'none'; }, 4000);
    }
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
  Object.defineProperty(window.AcademicYearsApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.AcademicYearsApp.getCSRFToken = getCSRFToken;
  window.AcademicYearsApp.getEl = getEl;
  window.AcademicYearsApp.showAlert = showAlert;
  window.AcademicYearsApp.showModal = showModal;
  window.AcademicYearsApp.hideModal = hideModal;
})(window);
