/* KCC ClassStamp — Core: Modern Glassmorphic Confirm Dialog */
(function (window) {
  'use strict';

  window.App = window.App || {};

  /* ── Modern Glassmorphic Confirm Dialog ─────────────────────── */
  window.App.confirm = function (opts) {
    opts = opts || {};
    var title = opts.title || 'Please Confirm';
    var message = opts.message || 'Are you sure you want to proceed?';
    var confirmText = opts.confirmText || 'Confirm';
    var cancelText = opts.cancelText || 'Cancel';
    var type = opts.type || 'danger';
    var confirmClass = opts.confirmClass || (type === 'primary' ? 'btn-primary' : (type === 'warning' ? 'btn-warning' : 'btn-danger'));

    var iconClass = 'fas fa-triangle-exclamation';
    if (type === 'primary') iconClass = 'fas fa-circle-question';
    if (type === 'warning') iconClass = 'fas fa-triangle-exclamation';

    return new Promise(function (resolve) {
      var modal = document.getElementById('appConfirmModal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'appConfirmModal';
        modal.className = 'modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.innerHTML =
          '<div class="modal-dialog modal-dialog--sm confirm-dialog">' +
          '  <div class="confirm-dialog-header" style="display: flex; gap: 14px; align-items: flex-start; padding: 22px 24px 14px;">' +
          '    <div id="confirmDialogIcon" class="confirm-dialog-icon confirm-dialog-icon--danger">' +
          '      <i class="fas fa-triangle-exclamation"></i>' +
          '    </div>' +
          '    <div style="flex: 1;">' +
          '      <h4 id="confirmDialogTitle" class="confirm-dialog-title" style="margin: 0 0 6px; font-size: 1.05rem; font-weight: 700; color: var(--text-primary);"></h4>' +
          '      <p id="confirmDialogMsg" class="confirm-dialog-msg" style="margin: 0; font-size: 0.875rem; color: var(--text-muted); line-height: 1.45;"></p>' +
          '    </div>' +
          '  </div>' +
          '  <div class="modal-footer" style="padding: 14px 24px; display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--glass-border);">' +
          '    <button type="button" id="confirmDialogCancelBtn" class="btn btn-outline btn-sm">' + cancelText + '</button>' +
          '    <button type="button" id="confirmDialogOkBtn" class="btn btn-sm">' + confirmText + '</button>' +
          '  </div>' +
          '</div>';
        document.body.appendChild(modal);
      }

      var titleEl = modal.querySelector('#confirmDialogTitle');
      var msgEl = modal.querySelector('#confirmDialogMsg');
      var iconContainer = modal.querySelector('#confirmDialogIcon');
      var okBtn = modal.querySelector('#confirmDialogOkBtn');
      var cancelBtn = modal.querySelector('#confirmDialogCancelBtn');

      if (titleEl) titleEl.textContent = title;
      if (msgEl) msgEl.textContent = message;

      if (iconContainer) {
        iconContainer.className = 'confirm-dialog-icon confirm-dialog-icon--' + type;
        iconContainer.innerHTML = '<i class="' + iconClass + '"></i>';
      }

      if (okBtn) {
        okBtn.className = 'btn btn-sm ' + confirmClass;
        okBtn.textContent = confirmText;
      }
      if (cancelBtn) {
        cancelBtn.textContent = cancelText;
      }

      function cleanup(res) {
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        modal.removeEventListener('click', onBackdrop);
        document.removeEventListener('keydown', onKey);
        if (typeof window.closeModal === 'function') {
          window.closeModal('appConfirmModal');
        } else if (window.App && window.App.closeModal) {
          window.App.closeModal('appConfirmModal');
        }
        resolve(res);
      }

      function onOk() { cleanup(true); }
      function onCancel() { cleanup(false); }
      function onBackdrop(e) {
        if (e.target === modal) cleanup(false);
      }
      function onKey(e) {
        if (e.key === 'Escape') cleanup(false);
      }

      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      modal.addEventListener('click', onBackdrop);
      document.addEventListener('keydown', onKey);

      if (typeof window.openModal === 'function') {
        window.openModal('appConfirmModal');
      } else if (window.App && window.App.openModal) {
        window.App.openModal('appConfirmModal');
      }

      setTimeout(function () {
        if (cancelBtn) cancelBtn.focus();
      }, 70);
    });
  };
})(window);
