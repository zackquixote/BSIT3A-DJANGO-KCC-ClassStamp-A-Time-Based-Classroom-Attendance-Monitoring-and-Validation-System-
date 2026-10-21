/* KCC ClassStamp — Teachers: Common Utilities & Helpers */
(function (window) {
  'use strict';

  window.TeachersApp = window.TeachersApp || {};

  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) {
      return meta.getAttribute('content');
    }
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
      return input.value;
    }
    return '';
  }

  function showAlert(el, msg, type) {
    type = type || 'error';
    if (!el) return;
    el.style.display = 'block';
    el.className = 'toast toast--' + type + ' mb-4';
    el.textContent = msg;
    if (type === 'success') setTimeout(function () { el.style.display = 'none'; }, 5000);
  }

  function showModal(id) {
    if (typeof window.openModal === 'function') {
      window.openModal(id);
    } else {
      var el = document.getElementById(id);
      if (el) {
        el.classList.add('is-active');
        document.body.style.overflow = 'hidden';
      }
    }
  }

  function hideModal(id) {
    if (typeof window.closeModal === 'function') {
      window.closeModal(id);
    } else {
      var el = document.getElementById(id);
      if (el) {
        el.classList.remove('is-active');
        document.body.style.overflow = '';
      }
    }
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function initCommon() {
    // Modal dismiss bindings
    ['teacherModalClose', 'teacherModalCancel'].forEach(function (id) {
      var el = getEl(id);
      if (el) el.addEventListener('click', function () { hideModal('teacherModal'); });
    });

    ['teacherDeleteClose', 'teacherDeleteCancel'].forEach(function (id) {
      var el = getEl(id);
      if (el) el.addEventListener('click', function () { hideModal('teacherDeleteModal'); });
    });

    var detailClose = getEl('teacherDetailClose');
    if (detailClose) {
      detailClose.addEventListener('click', function () { hideModal('teacherDetailModal'); });
    }

    // Teaching load modal dismiss (with reload)
    document.querySelectorAll('[data-modal-dismiss="teachingLoadModal"]').forEach(function (el) {
      el.addEventListener('click', function () {
        hideModal('teachingLoadModal');
        location.reload();
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCommon);
  } else {
    initCommon();
  }

  // Export to namespace
  Object.defineProperty(window.TeachersApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.TeachersApp.getCSRFToken = getCSRFToken;
  window.TeachersApp.showAlert = showAlert;
  window.TeachersApp.showModal = showModal;
  window.TeachersApp.hideModal = hideModal;
  window.TeachersApp.getEl = getEl;
})(window);
