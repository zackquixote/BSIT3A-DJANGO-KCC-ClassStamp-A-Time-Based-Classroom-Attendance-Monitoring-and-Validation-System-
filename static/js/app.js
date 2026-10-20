/* KCC ClassStamp — App JS (Vanilla, no framework) */

(function () {
  'use strict';

  window.App = window.App || {};

  /* ── Unified Modern Toast Notification System ───────────────── */
  window.App.toast = function (type, message, duration) {
    if (!message) return;
    type = type || 'info';

    // Normalize type
    if (type === 'danger') type = 'error';
    if (type === 'warn') type = 'warning';

    // Ensure container exists
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    // Determine icon
    var iconClass = 'fas fa-circle-info';
    if (type === 'success') {
      iconClass = 'fas fa-circle-check';
    } else if (type === 'error') {
      iconClass = 'fas fa-circle-xmark';
    } else if (type === 'warning') {
      iconClass = 'fas fa-triangle-exclamation';
    }

    var toast = document.createElement('div');
    toast.className = 'toast toast--' + type;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');

    var iconEl = document.createElement('i');
    iconEl.className = iconClass + ' toast-icon';
    toast.appendChild(iconEl);

    var contentEl = document.createElement('span');
    contentEl.className = 'toast-content';
    contentEl.textContent = message;
    toast.appendChild(contentEl);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'toast-dismiss';
    closeBtn.setAttribute('aria-label', 'Dismiss notification');
    closeBtn.innerHTML = '&times;';
    toast.appendChild(closeBtn);

    var dismissed = false;
    function dismissToast() {
      if (dismissed) return;
      dismissed = true;
      toast.classList.add('toast--closing');
      setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 250);
    }

    closeBtn.addEventListener('click', dismissToast);
    container.appendChild(toast);

    var timeoutMs = typeof duration === 'number' ? duration : 4000;
    setTimeout(dismissToast, timeoutMs);

    return toast;
  };

  // Global alias for quick calling
  window.toast = window.App.toast;

  /* ── Button Loading & Double-Submission Prevention ──────────── */
  window.App.setButtonLoading = function (btn, isLoading, loadingText) {
    if (!btn) return;

    if (isLoading) {
      if (btn.disabled && btn.classList.contains('is-loading')) return;
      btn.dataset.originalHtml = btn.innerHTML;
      var width = btn.offsetWidth;
      if (width > 0) {
        btn.style.minWidth = width + 'px';
      }
      btn.disabled = true;
      btn.classList.add('is-loading');
      var text = loadingText || btn.getAttribute('data-loading-text') || 'Saving...';
      btn.innerHTML = '<i class="fas fa-spinner fa-spin" style="margin-right: 6px;"></i> ' + text;
    } else {
      btn.disabled = false;
      btn.classList.remove('is-loading');
      btn.style.minWidth = '';
      if (btn.dataset.originalHtml) {
        btn.innerHTML = btn.dataset.originalHtml;
        delete btn.dataset.originalHtml;
      }
    }
  };

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
    document.body.style.overflow = '';

    // Smoothly return focus to the trigger button
    if (modal.id && modalTriggers[modal.id]) {
      var trigger = modalTriggers[modal.id];
      delete modalTriggers[modal.id];
      if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger)) {
        trigger.focus();
      }
    }
  };

  // Global click delegate for open/close modals
  document.addEventListener('click', function (e) {
    var targetBtn = e.target.closest('[data-modal-target]');
    if (targetBtn) {
      e.preventDefault();
      var modalId = targetBtn.getAttribute('data-modal-target');
      window.openModal(modalId, targetBtn);
      return;
    }

    var dismissBtn = e.target.closest('[data-modal-dismiss]');
    if (dismissBtn) {
      e.preventDefault();
      var targetModal = dismissBtn.closest('.modal');
      if (targetModal) {
        window.closeModal(targetModal.id || targetModal);
      } else {
        var dismissId = dismissBtn.getAttribute('data-modal-dismiss');
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

  /* ── DOM Ready Initializers ─────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss and enhance server-rendered Django toasts
    document.querySelectorAll('.toast').forEach(function (toast) {
      if (!toast.querySelector('.toast-dismiss')) {
        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'toast-dismiss';
        closeBtn.setAttribute('aria-label', 'Dismiss notification');
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', function () {
          toast.classList.add('toast--closing');
          setTimeout(function () { toast.remove(); }, 250);
        });
        toast.appendChild(closeBtn);
      }

      setTimeout(function () {
        toast.classList.add('toast--closing');
        setTimeout(function () { toast.remove(); }, 250);
      }, 5000);
    });

    // Mobile sidebar toggle & backdrop handling
    var menuBtn = document.getElementById('sidebar-toggle');
    var closeBtn = document.getElementById('sidebar-close');
    var sidebar = document.getElementById('sidebar');
    var backdrop = document.getElementById('sidebar-backdrop');

    function openSidebar() {
      if (sidebar) sidebar.classList.add('is-open');
      if (backdrop) backdrop.classList.add('is-active');
      document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove('is-open');
      if (backdrop) backdrop.classList.remove('is-active');
      document.body.style.overflow = '';
    }

    if (menuBtn) {
      menuBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (sidebar && sidebar.classList.contains('is-open')) {
          closeSidebar();
        } else {
          openSidebar();
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeSidebar();
      });
    }

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        closeSidebar();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) {
        closeSidebar();
      }
    });

    // Active nav link highlight
    var currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(function (link) {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
      }
    });
  });

  /* ── Back-Forward Cache (bfcache) Invalidation ───────────────── */
  window.addEventListener('pageshow', function (event) {
    var navEntries = (window.performance && performance.getEntriesByType)
      ? performance.getEntriesByType('navigation')
      : [];
    var isBackForward = event.persisted ||
      (navEntries.length > 0 && navEntries[0].type === 'back_forward') ||
      (window.performance && window.performance.navigation && window.performance.navigation.type === 2);

    if (isBackForward) {
      window.location.reload();
    }
  });

})();

