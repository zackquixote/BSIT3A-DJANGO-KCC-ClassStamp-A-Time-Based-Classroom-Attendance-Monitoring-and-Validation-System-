/* KCC ClassStamp — Core: Unified Toast Notifications */
(function (window) {
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

  // Enhance server-rendered Django toasts on DOMContentLoaded
  function initServerToasts() {
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initServerToasts);
  } else {
    initServerToasts();
  }
})(window);
