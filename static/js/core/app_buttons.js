/* KCC ClassStamp — Core: Button State & Loading Helper */
(function (window) {
  'use strict';

  window.App = window.App || {};

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
})(window);
