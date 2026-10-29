/* KCC ClassStamp — Subjects: Common Utilities & Filter Cascade */
(function (window) {
  'use strict';

  window.SubjectsApp = window.SubjectsApp || {};

  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) {
      return meta.getAttribute('content');
    }
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
      return input.value;
    }
    if (window.SUBJECTS_CONFIG && window.SUBJECTS_CONFIG.csrf) {
      return window.SUBJECTS_CONFIG.csrf;
    }
    return '';
  }

  function showAlert(el, msg, type = 'error') {
    if (window.App && window.App.toast) { window.App.toast(type, msg); return; }
    if (!el) return;
    el.style.display = 'block';
    el.className = `toast toast--${type} mb-4`;
    el.textContent = msg;
    if (type === 'success') setTimeout(() => { el.style.display = 'none'; }, 4000);
  }

  function showModal(id) {
    if (typeof window.openModal === 'function') {
      window.openModal(id);
    } else {
      const el = document.getElementById(id);
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
      const el = document.getElementById(id);
      if (el) {
        el.classList.remove('is-active');
        document.body.style.overflow = '';
      }
    }
  }

  function initCommon() {
    // Filter bar cascade
    const filterDeptEl = document.getElementById('filterDept');
    const filterProgEl = document.getElementById('filterProgram');

    filterDeptEl?.addEventListener('change', function () {
      const deptId = this.value;
      if (!filterProgEl) return;
      filterProgEl.querySelectorAll('option').forEach(opt => {
        if (!opt.value) return;
        opt.hidden = deptId ? opt.dataset.dept !== deptId : false;
      });
      if (filterProgEl.selectedOptions[0]?.hidden) filterProgEl.value = '';
    });

    if (filterDeptEl?.value && filterProgEl) {
      const deptId = filterDeptEl.value;
      filterProgEl.querySelectorAll('option').forEach(opt => {
        if (!opt.value) return;
        opt.hidden = opt.dataset.dept !== deptId;
      });
    }

    // Modal dismiss bindings
    ['subjectModalClose', 'subjectModalCancel'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', () => hideModal('subjectModal'));
    });
    ['subjectDeleteClose', 'subjectDeleteCancel'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', () => hideModal('subjectDeleteModal'));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCommon);
  } else {
    initCommon();
  }

  // Export to namespace
  Object.defineProperty(window.SubjectsApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  window.SubjectsApp.getCSRFToken = getCSRFToken;
  window.SubjectsApp.showAlert = showAlert;
  window.SubjectsApp.showModal = showModal;
  window.SubjectsApp.hideModal = hideModal;
})(window);
