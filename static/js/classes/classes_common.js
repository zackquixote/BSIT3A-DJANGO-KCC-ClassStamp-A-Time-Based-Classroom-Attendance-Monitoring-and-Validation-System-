/* KCC ClassStamp — Classes: Common Utilities & Modal Helpers */
(function (window) {
  'use strict';

  window.ClassesApp = window.ClassesApp || {};

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

  function showModal(id) {
    var el = getEl(id);
    if (el) el.classList.add('is-open');
  }

  function hideModal(id) {
    var el = getEl(id);
    if (el) el.classList.remove('is-open');
  }

  function initCommon() {
    var slotsModal  = getEl('slotsModal');
    var rosterModal = getEl('rosterModal');
    var allModals   = [slotsModal, rosterModal];

    // Backdrop click close for all modals
    allModals.forEach(function (m) {
      if (m) {
        m.addEventListener('click', function (e) {
          if (e.target === m) m.classList.remove('is-open');
        });
      }
    });

    // Escape key close for all modals
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        allModals.forEach(function (m) {
          if (m) m.classList.remove('is-open');
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCommon);
  } else {
    initCommon();
  }

  // Export to namespace
  Object.defineProperty(window.ClassesApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.ClassesApp.getCSRFToken = getCSRFToken;
  window.ClassesApp.getEl = getEl;
  window.ClassesApp.showModal = showModal;
  window.ClassesApp.hideModal = hideModal;
})(window);
