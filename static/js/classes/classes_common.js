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
    var classModal  = getEl('classModal');
    var slotsModal  = getEl('slotsModal');
    var rosterModal = getEl('rosterModal');
    var allModals   = [classModal, slotsModal, rosterModal];

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

    var params = new URLSearchParams(window.location.search);
    var setupClassId = params.get('setup_class');
    var setupAction = params.get('setup_action');
    if (setupClassId && setupAction) {
      window.setTimeout(function () {
        var row = getEl('class-' + setupClassId);
        var actionSelectors = {
          teacher: '.btn-edit-class',
          schedule: '.btn-manage-slots',
          roster: '.btn-manage-roster',
          join_code: '.action-dropdown-toggle',
        };
        var selector = actionSelectors[setupAction];
        var actionButton = row && selector ? row.querySelector(selector) : null;
        if (!row || !actionButton) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Could not open that section setup. Find the section in the list and try again.');
          }
          return;
        }
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        actionButton.click();
      }, 0);
    }
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
