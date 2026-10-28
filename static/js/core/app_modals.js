/* KCC ClassStamp — Core: Modal Dialog Manager */
(function (window) {
  'use strict';

  window.App = window.App || {};

  /* ── Modal Dialog Manager (Global & Accessible) ─────────────── */
  var modalTriggers = {};

  window.openModal = function (modalId, triggerEl) {
    var modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
    if (!modal) return;

    var trigger = triggerEl || document.activeElement;
    if (trigger && modal.id) {
      modalTriggers[modal.id] = trigger;
    }

    modal.classList.add('is-active', 'is-open');
    document.body.style.overflow = 'hidden';

    // Auto-focus first visible input field after modal transitions
    setTimeout(function () {
      var firstField = modal.querySelector(
        'input:not([type="hidden"]):not([disabled]):not([readonly]), select:not([disabled]), textarea:not([disabled]), [autofocus]'
      );
      if (firstField && typeof firstField.focus === 'function') {
        firstField.focus();
      }
    }, 60);
  };

  window.closeModal = function (modalId) {
    var modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
    if (!modal) return;

    modal.classList.remove('is-active', 'is-open');
    var remainingModal = document.querySelector('.modal.is-active, .modal.is-open');
    if (!remainingModal) {
      document.body.style.overflow = '';
    }

    // Smoothly return focus to the trigger button
    if (modal.id && modalTriggers[modal.id]) {
      var trigger = modalTriggers[modal.id];
      delete modalTriggers[modal.id];
      if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger)) {
        trigger.focus();
      }
    }
  };

  // Expose on window.App as well for consistent namespacing
  window.App.openModal = window.openModal;
  window.App.closeModal = window.closeModal;

  // Global click delegate for open/close modals
  document.addEventListener('click', function (e) {
    var targetBtn = e.target.closest('[data-modal-target]');
    if (targetBtn) {
      e.preventDefault();
      var modalId = targetBtn.getAttribute('data-modal-target');
      window.openModal(modalId, targetBtn);
      return;
    }

    var dismissBtn = e.target.closest('[data-modal-dismiss], [data-modal-close], .modal-close');
    if (dismissBtn) {
      e.preventDefault();
      var targetModal = dismissBtn.closest('.modal');
      if (targetModal) {
        window.closeModal(targetModal.id || targetModal);
      } else {
        var dismissId = dismissBtn.getAttribute('data-modal-dismiss') || dismissBtn.getAttribute('data-modal-close');
        if (dismissId) window.closeModal(dismissId);
      }
      return;
    }

    // Backdrop click
    if (e.target.classList && (e.target.classList.contains('modal') || e.target.classList.contains('modal-overlay'))) {
      window.closeModal(e.target.id || e.target);
    }
  });

  // Escape key closes active modal
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var activeModal = document.querySelector('.modal.is-active, .modal.is-open');
      if (activeModal) window.closeModal(activeModal.id || activeModal);
    }
  });
})(window);
